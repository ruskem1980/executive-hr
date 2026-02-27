#!/usr/bin/env python3
"""
Генерация недостающих переводов через Gemini Flash

Этапы:
1. Определить недостающие ключи для каждого языка
2. Извлечь эталонные значения из ru.json
3. Сгенерировать переводы через Gemini Flash (экономия токенов)
4. Обновить JSON файлы
5. Записать расход токенов через TokenTracker
"""

import json
import subprocess
import sys
import re
from pathlib import Path
from typing import Dict, List, Set, Any
from dataclasses import dataclass


@dataclass
class MissingTranslation:
    key: str
    ru_value: str
    nested_path: List[str]


class TranslationFixer:
    def __init__(self, locales_dir: Path, reference_lang: str = "ru"):
        self.locales_dir = locales_dir
        self.reference_lang = reference_lang
        self.translations = {}
        self.missing_by_lang = {}
        self.gemini_bridge = Path(__file__).parent.parent / ".claude" / "helpers" / "gemini-bridge.sh"

    def load_translations(self):
        """Загрузить все JSON файлы"""
        for file in self.locales_dir.glob("*.json"):
            lang = file.stem
            with open(file, 'r', encoding='utf-8') as f:
                self.translations[lang] = json.load(f)

    def flatten_dict(self, d: Dict, parent_key: str = '') -> Dict[str, str]:
        """Преобразовать в плоский dict"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self.flatten_dict(v, new_key).items())
            else:
                items.append((new_key, str(v) if v is not None else ""))
        return dict(items)

    def get_nested_value(self, data: Dict, key_path: str) -> Any:
        """Получить значение по dot-notation"""
        keys = key_path.split('.')
        value = data
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return None
        return value

    def set_nested_value(self, data: Dict, key_path: str, value: Any):
        """Установить значение по dot-notation"""
        keys = key_path.split('.')
        current = data

        for i, k in enumerate(keys[:-1]):
            if k not in current:
                current[k] = {}
            elif not isinstance(current[k], dict):
                # Конфликт: промежуточный узел не dict
                print(f"  ⚠️  Конфликт: {'.'.join(keys[:i+1])} не является объектом")
                return
            current = current[k]

        current[keys[-1]] = value

    def find_missing_keys(self):
        """Найти недостающие ключи для каждого языка"""
        ref_flat = self.flatten_dict(self.translations[self.reference_lang])
        ref_keys = set(ref_flat.keys())

        for lang in self.translations:
            if lang == self.reference_lang:
                continue

            lang_flat = self.flatten_dict(self.translations[lang])
            lang_keys = set(lang_flat.keys())

            missing = ref_keys - lang_keys
            if missing:
                self.missing_by_lang[lang] = [
                    MissingTranslation(
                        key=key,
                        ru_value=ref_flat[key],
                        nested_path=key.split('.')
                    )
                    for key in sorted(missing)
                ]

    def generate_translations_batch(self, lang: str, batch: List[MissingTranslation], lang_full_name: str) -> Dict[str, str]:
        """
        Сгенерировать переводы для батча через Gemini Flash

        Возвращает dict: {key: translated_value}
        """
        # Формируем JSON с ключами и русскими значениями
        translations_json = {item.key: item.ru_value for item in batch}

        # Промпт для Gemini
        prompt = f"""Ты профессиональный переводчик интерфейсов.

Задача: Перевести интерфейсные строки с русского на {lang_full_name} язык.

Контекст: Это строки для мобильного приложения MigrantHub — платформы юридической помощи мигрантам в России.

Входные данные (JSON):
{json.dumps(translations_json, ensure_ascii=False, indent=2)}

Требования:
1. Перевести ТОЛЬКО значения, ключи не трогать
2. Сохранить плейсхолдеры {{{{var}}}} без изменений
3. Сохранить форматирование (\\n, пробелы)
4. Использовать формальный стиль для официальных текстов
5. Для технических терминов (патент, РВП, ВНЖ, СНИЛС, ИНН) использовать общепринятые формы

Формат ответа: ТОЛЬКО JSON с переведёнными значениями, без комментариев.
Пример:
{{
  "key1": "перевод1",
  "key2": "перевод2"
}}

Верни ТОЛЬКО JSON, без markdown блоков, без текста до/после."""

        # Запуск Gemini Flash через bridge
        print(f"    🤖 Вызов Gemini Flash для {len(batch)} ключей...")

        try:
            result = subprocess.run(
                ["bash", str(self.gemini_bridge), "flash", prompt],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                print(f"    ❌ Ошибка вызова Gemini: {result.stderr}")
                return {}

            output = result.stdout.strip()

            # Убрать markdown блоки если есть
            output = re.sub(r'^```json\s*', '', output)
            output = re.sub(r'\s*```$', '', output)
            output = output.strip()

            # Парсинг JSON
            translated = json.loads(output)

            print(f"    ✅ Получено {len(translated)} переводов")
            return translated

        except subprocess.TimeoutExpired:
            print(f"    ❌ Таймаут при вызове Gemini")
            return {}
        except json.JSONDecodeError as e:
            print(f"    ❌ Ошибка парсинга JSON от Gemini: {e}")
            print(f"    Ответ: {output[:200]}...")
            return {}
        except Exception as e:
            print(f"    ❌ Ошибка: {e}")
            return {}

    def fix_language(self, lang: str, lang_full_name: str):
        """Исправить переводы для одного языка"""
        if lang not in self.missing_by_lang:
            print(f"  ✅ {lang}: Все переводы на месте")
            return 0

        missing = self.missing_by_lang[lang]
        print(f"  🔧 {lang}: Недостаёт {len(missing)} переводов")

        # Разбиваем на батчи по 50 ключей (чтобы не превышать лимиты контекста)
        batch_size = 50
        batches = [missing[i:i + batch_size] for i in range(0, len(missing), batch_size)]

        all_translations = {}

        for i, batch in enumerate(batches, 1):
            print(f"    📦 Батч {i}/{len(batches)} ({len(batch)} ключей)")
            translated = self.generate_translations_batch(lang, batch, lang_full_name)
            all_translations.update(translated)

        # Применить переводы к JSON
        if all_translations:
            print(f"    💾 Применение {len(all_translations)} переводов...")
            updated_data = self.translations[lang].copy()

            for key, value in all_translations.items():
                self.set_nested_value(updated_data, key, value)

            # Сохранить JSON
            output_file = self.locales_dir / f"{lang}.json"
            with open(output_file, 'w', encoding='utf-8') as f:
                json.dump(updated_data, f, ensure_ascii=False, indent=2)

            print(f"    ✅ Файл обновлён: {output_file}")
            return len(all_translations)
        else:
            print(f"    ⚠️  Не удалось сгенерировать переводы")
            return 0

    def fix_all(self):
        """Исправить переводы для всех языков"""
        print("=" * 80)
        print("ГЕНЕРАЦИЯ НЕДОСТАЮЩИХ ПЕРЕВОДОВ")
        print("=" * 80)
        print()

        self.load_translations()
        print(f"📦 Загружено языков: {', '.join(sorted(self.translations.keys()))}")
        print()

        self.find_missing_keys()

        if not self.missing_by_lang:
            print("✅ Все переводы на месте!")
            return {}

        print("🔍 Найдены пробелы:")
        for lang, missing in self.missing_by_lang.items():
            print(f"  - {lang}: {len(missing)} ключей")
        print()

        # Маппинг языковых кодов на полные названия
        lang_names = {
            "en": "английский (English)",
            "uz": "узбекский (O'zbek tili, латиница)",
            "tg": "таджикский (тоҷикӣ)",
            "ky": "киргизский (кыргызча)"
        }

        stats = {}

        for lang in sorted(self.missing_by_lang.keys()):
            lang_full = lang_names.get(lang, lang)
            print(f"🌍 Обработка: {lang} ({lang_full})")
            fixed_count = self.fix_language(lang, lang_full)
            stats[lang] = fixed_count
            print()

        return stats


def estimate_tokens(translations_count: int, avg_value_length: int = 50) -> tuple:
    """
    Оценить расход токенов

    Gemini Flash:
    - Input: промпт + JSON ключей (~200 токенов на ключ с контекстом)
    - Output: JSON переводов (~150 токенов на ключ)
    """
    input_per_key = 200
    output_per_key = 150

    total_input = translations_count * input_per_key
    total_output = translations_count * output_per_key

    return (total_input, total_output)


def main():
    locales_dir = Path(__file__).parent.parent / "apps" / "frontend" / "src" / "locales"

    if not locales_dir.exists():
        print(f"❌ Директория не найдена: {locales_dir}")
        return 1

    fixer = TranslationFixer(locales_dir)
    stats = fixer.fix_all()

    if stats:
        print("=" * 80)
        print("ИТОГИ ГЕНЕРАЦИИ")
        print("=" * 80)
        print()

        total_fixed = sum(stats.values())
        for lang, count in stats.items():
            print(f"  ✅ {lang}: {count} переводов добавлено")

        print()
        print(f"📊 Всего исправлено: {total_fixed} переводов")
        print()

        # Оценка токенов
        est_input, est_output = estimate_tokens(total_fixed)
        print("💰 Оценка расхода токенов (Gemini Flash):")
        print(f"  - Input:  ~{est_input:,} токенов")
        print(f"  - Output: ~{est_output:,} токенов")
        print(f"  - Стоимость: ~${(est_input * 0.5 + est_output * 3.0) / 1_000_000:.4f}")
        print()

        return 0
    else:
        print("✅ Нечего исправлять")
        return 0


if __name__ == "__main__":
    sys.exit(main())
