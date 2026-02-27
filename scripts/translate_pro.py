#!/usr/bin/env python3
"""
Профессиональный переводчик через Gemini Pro.
Высокое качество, медленнее но точнее чем Flash.
"""
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List

PROJECT_ROOT = Path.cwd()
LOCALES_DIR = PROJECT_ROOT / "apps" / "frontend" / "src" / "locales"

LANG_INFO = {
    'en': {
        'name': 'English',
        'prompt': 'professional English translation',
        'context': 'This is a legal assistance app for migrants in Russia. Use formal, professional language.'
    },
    'uz': {
        'name': 'Uzbek (Latin)',
        'prompt': 'professional Uzbek translation in Latin script',
        'context': 'Это приложение правовой помощи мигрантам в России. Используйте формальный, профессиональный язык.'
    },
    'tg': {
        'name': 'Tajik (Cyrillic)',
        'prompt': 'professional Tajik translation in Cyrillic script',
        'context': 'Это приложение правовой помощи мигрантам в России. Используйте формальный, профессиональный язык.'
    },
    'ky': {
        'name': 'Kyrgyz (Cyrillic)',
        'prompt': 'professional Kyrgyz translation in Cyrillic script',
        'context': 'Это приложение правовой помощи мигрантам в России. Используйте формальный, профессиональный язык.'
    }
}

class ProTranslator:
    def __init__(self):
        self.translations = {}
        self.load_all_locales()

    def load_all_locales(self):
        for lang in ['ru', 'en', 'uz', 'tg', 'ky']:
            path = LOCALES_DIR / f"{lang}.json"
            with open(path, 'r', encoding='utf-8') as f:
                self.translations[lang] = json.load(f)

    def save_locale(self, lang: str):
        path = LOCALES_DIR / f"{lang}.json"
        # Создаём бэкап
        backup_path = path.with_suffix('.json.pro_backup')
        if path.exists():
            import shutil
            shutil.copy2(path, backup_path)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.translations[lang], f, ensure_ascii=False, indent=2, sort_keys=True)

    def collect_phrases(self, lang: str) -> List[tuple]:
        """Собирает все фразы с префиксом [TRANSLATE] с путями"""
        phrases = []
        prefix = '[TRANSLATE]'

        def traverse(obj, path=[]):
            if isinstance(obj, str):
                if obj.startswith(prefix):
                    russian_text = obj[len(prefix):].strip()
                    phrases.append((path.copy(), russian_text, obj))
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    traverse(value, path + [key])
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    traverse(item, path + [i])

        traverse(self.translations[lang])
        return phrases

    def translate_batch_pro(self, batch: List[str], lang: str) -> Dict[str, str]:
        """Переводит пакет через Gemini Pro с высоким качеством"""
        if not batch:
            return {}

        # Создаём детальный промпт для Pro
        numbered_batch = "\n".join(f"{i+1}. {phrase}" for i, phrase in enumerate(batch))

        lang_info = LANG_INFO[lang]
        prompt = f"""You are a professional translator specializing in legal and governmental terminology.

CONTEXT: {lang_info['context']}

TASK: Translate the following Russian phrases into {lang_info['prompt']}.

REQUIREMENTS:
- Maintain professional, formal tone
- Use correct legal terminology
- Preserve formatting (capitalization, punctuation)
- Keep technical terms accurate
- For proper nouns (city names, country names), use standard transliterations

INPUT (Russian):
{numbered_batch}

OUTPUT FORMAT: Provide translations in the same numbered format:
1. [translation]
2. [translation]
etc.

TRANSLATIONS ({lang_info['name']}):"""

        try:
            print(f"    🔄 Вызов Gemini Pro (пакет из {len(batch)} фраз)...")
            result = subprocess.run(
                ['bash', '.claude/helpers/gemini-bridge.sh', 'pro', prompt],
                capture_output=True,
                text=True,
                timeout=120  # 2 минуты на пакет для Pro
            )

            if result.returncode != 0:
                print(f"    ❌ Ошибка вызова Gemini Pro: {result.stderr}")
                return {}

            # Парсим ответ
            translations = {}
            lines = result.stdout.strip().split('\n')

            for line in lines:
                line = line.strip()
                # Ищем формат "1. перевод" или "1) перевод"
                import re
                match = re.match(r'^(\d+)[.)]\s*(.+)$', line)
                if match:
                    idx = int(match.group(1)) - 1
                    translation = match.group(2).strip()
                    if 0 <= idx < len(batch):
                        translations[batch[idx]] = translation

            return translations

        except subprocess.TimeoutExpired:
            print(f"    ⏱️ Таймаут (120 сек)")
            return {}
        except Exception as e:
            print(f"    ❌ Ошибка: {e}")
            return {}

    def apply_translations(self, lang: str, phrases: List[tuple], translations: Dict[str, str]):
        """Применяет переводы к структуре данных"""
        for path, russian_text, original in phrases:
            if russian_text in translations:
                translation = translations[russian_text]

                # Навигация по пути
                current = self.translations[lang]
                for key in path[:-1]:
                    current = current[key]

                # Применение перевода
                current[path[-1]] = translation

    def translate_language(self, lang: str, batch_size: int = 5):
        """Переводит один язык через Gemini Pro"""
        print(f"\n{'='*60}")
        print(f"🌍 ПЕРЕВОД НА {LANG_INFO[lang]['name']} ({lang.upper()})")
        print(f"{'='*60}")

        # Собираем фразы
        phrases = self.collect_phrases(lang)
        total = len(phrases)

        if total == 0:
            print(f"  ✅ Фразы с префиксом [TRANSLATE] не найдены для {lang}")
            return

        print(f"  📝 Найдено фраз для перевода: {total}")
        print(f"  🎯 Используем Gemini Pro для профессионального качества")
        print(f"  📦 Размер пакета: {batch_size} фраз")
        print()

        # Переводим пакетами
        all_translations = {}
        texts_to_translate = [text for _, text, _ in phrases]

        for i in range(0, total, batch_size):
            batch = texts_to_translate[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size

            print(f"  📦 Пакет {batch_num}/{total_batches} ({len(batch)} фраз)")

            batch_translations = self.translate_batch_pro(batch, lang)

            if batch_translations:
                all_translations.update(batch_translations)
                print(f"    ✅ Переведено: {len(batch_translations)}/{len(batch)}")
            else:
                print(f"    ⚠️ Перевод не удался")

            # Пауза между пакетами (rate limit)
            if i + batch_size < total:
                print(f"    ⏸️ Пауза 2 сек...")
                time.sleep(2)

        # Применяем переводы
        print(f"\n  💾 Применение переводов...")
        self.apply_translations(lang, phrases, all_translations)

        # Сохраняем
        self.save_locale(lang)

        success_rate = len(all_translations) / total * 100 if total > 0 else 0
        print(f"  ✅ Сохранено в {lang}.json")
        print(f"  📊 Успешность: {len(all_translations)}/{total} ({success_rate:.1f}%)")

def main():
    import sys

    translator = ProTranslator()

    # Определяем языки для перевода
    languages = ['en', 'uz', 'tg', 'ky']

    if len(sys.argv) > 1:
        requested = sys.argv[1].lower()
        if requested in languages:
            languages = [requested]
        elif requested == 'all':
            pass  # Переводим все
        else:
            print(f"❌ Неизвестный язык: {requested}")
            print(f"Доступные: {', '.join(languages)}, all")
            return

    print("\n" + "="*60)
    print("🚀 ПРОФЕССИОНАЛЬНЫЙ ПЕРЕВОДЧИК (Gemini Pro)")
    print("="*60)
    print(f"📋 Языки: {', '.join(lang.upper() for lang in languages)}")
    print(f"🎯 Модель: Gemini Pro (высокое качество)")
    print(f"⏱️ Скорость: медленнее, но точнее")
    print("="*60)

    # Переводим каждый язык
    for lang in languages:
        try:
            translator.translate_language(lang, batch_size=5)
        except KeyboardInterrupt:
            print(f"\n\n⚠️ Прервано пользователем")
            translator.save_locale(lang)  # Сохраняем прогресс
            break
        except Exception as e:
            print(f"\n❌ Ошибка при переводе {lang}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*60)
    print("✅ ПЕРЕВОД ЗАВЕРШЁН")
    print("="*60)
    print("\n💡 Проверьте переводы:")
    for lang in languages:
        print(f"  apps/frontend/src/locales/{lang}.json")

    print("\n🧪 Запустите валидатор:")
    print("  python3 scripts/i18n_validator.py --check")

    print("\n📦 Бэкапы сохранены:")
    for lang in languages:
        print(f"  apps/frontend/src/locales/{lang}.json.pro_backup")

if __name__ == '__main__':
    main()
