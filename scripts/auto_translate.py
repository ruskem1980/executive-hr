#!/usr/bin/env python3
"""
Автоматический переводчик JSON файлов.
Заменяет заглушки [EN], [UZ], [TG], [KY] на реальные переводы.
"""
import json
import re
import subprocess
import tempfile
from pathlib import Path
from typing import Dict, List, Tuple

PROJECT_ROOT = Path.cwd()
LOCALES_DIR = PROJECT_ROOT / "apps" / "frontend" / "src" / "locales"

# Маппинг языков
LANGUAGE_MAPPING = {
    'en': {
        'name': 'English',
        'code': 'en',
        'gemini_prompt': 'English'
    },
    'uz': {
        'name': 'Uzbek (Latin)',
        'code': 'uz',
        'gemini_prompt': 'Uzbek in Latin script'
    },
    'tg': {
        'name': 'Tajik (Cyrillic)',
        'code': 'tg',
        'gemini_prompt': 'Tajik in Cyrillic script'
    },
    'ky': {
        'name': 'Kyrgyz (Cyrillic)',
        'code': 'ky',
        'gemini_prompt': 'Kyrgyz in Cyrillic script'
    }
}

class AutoTranslator:
    def __init__(self):
        self.translations = {}
        self.load_all_locales()

    def load_all_locales(self):
        """Загружает все языковые файлы"""
        for lang in ['ru', 'en', 'uz', 'tg', 'ky']:
            path = LOCALES_DIR / f"{lang}.json"
            with open(path, 'r', encoding='utf-8') as f:
                self.translations[lang] = json.load(f)

    def save_locale(self, lang: str):
        """Сохраняет языковой файл"""
        path = LOCALES_DIR / f"{lang}.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.translations[lang], f, ensure_ascii=False, indent=2, sort_keys=True)

    def collect_placeholders(self, lang: str) -> List[Tuple[List[str], str, str]]:
        """Собирает все заглушки для языка"""
        placeholders = []
        prefix = f'[{lang.upper()}]'

        def traverse(obj, path=[]):
            if isinstance(obj, str):
                if obj.startswith(prefix):
                    russian_text = obj[len(prefix):].strip()
                    placeholders.append((path.copy(), russian_text, obj))
            elif isinstance(obj, dict):
                for key, value in obj.items():
                    traverse(value, path + [key])
            elif isinstance(obj, list):
                for i, item in enumerate(obj):
                    traverse(item, path + [f'[{i}]'])

        traverse(self.translations[lang])
        return placeholders

    def translate_batch_via_gemini(self, texts: List[str], target_lang: str) -> List[str]:
        """Переводит пакет текстов через Gemini Flash"""
        if not texts:
            return []

        lang_info = LANGUAGE_MAPPING[target_lang]

        # Создаём промпт для Gemini
        prompt = f"""You are a professional translator. Translate the following Russian texts to {lang_info['gemini_prompt']}.

CRITICAL RULES:
- Output ONLY the translations, one per line
- Preserve the EXACT number of lines as input
- NO explanations, NO numbering, NO markdown
- Keep technical terms and numbers unchanged
- Preserve formatting like "24/7", "Пн-Пт 9:00-18:00"

Russian texts to translate:
{chr(10).join(f"{i+1}. {text}" for i, text in enumerate(texts))}

{lang_info['gemini_prompt']} translations (one per line):"""

        try:
            # Вызываем Gemini через bridge напрямую
            result = subprocess.run(
                ['bash', '.claude/helpers/gemini-bridge.sh', 'flash', prompt],
                capture_output=True,
                text=True,
                timeout=120
            )

            if result.returncode != 0:
                print(f"⚠️ Ошибка Gemini: {result.stderr}")
                return texts  # Возвращаем оригиналы при ошибке

            # Парсим ответ
            response = result.stdout.strip()

            # Убираем markdown блоки если есть
            response = re.sub(r'^```.*?\n', '', response, flags=re.MULTILINE)
            response = re.sub(r'\n```$', '', response, flags=re.MULTILINE)

            # Разбиваем на строки и убираем нумерацию
            lines = response.split('\n')
            translations = []
            for line in lines:
                # Убираем нумерацию "1. ", "2. " и т.д.
                clean_line = re.sub(r'^\d+\.\s*', '', line).strip()
                if clean_line:
                    translations.append(clean_line)

            # Проверяем что количество совпадает
            if len(translations) != len(texts):
                print(f"⚠️ Несовпадение количества: {len(texts)} → {len(translations)}")
                # Дополняем или обрезаем
                while len(translations) < len(texts):
                    translations.append(texts[len(translations)])
                translations = translations[:len(texts)]

            return translations

        except Exception as e:
            print(f"⚠️ Ошибка перевода: {e}")
            return texts

    def replace_placeholders(self, lang: str, placeholders: List[Tuple[List[str], str, str]], translations: List[str]):
        """Заменяет заглушки на переводы"""
        for (path, russian_text, original), translation in zip(placeholders, translations):
            # Навигируемся по пути и заменяем значение
            current = self.translations[lang]
            for key in path[:-1]:
                if key.startswith('[') and key.endswith(']'):
                    idx = int(key[1:-1])
                    current = current[idx]
                else:
                    current = current[key]

            last_key = path[-1]
            if last_key.startswith('[') and last_key.endswith(']'):
                idx = int(last_key[1:-1])
                current[idx] = translation
            else:
                current[last_key] = translation

    def translate_language(self, lang: str, batch_size: int = 10):
        """Переводит один язык"""
        print(f"\n🌍 Перевод на {LANGUAGE_MAPPING[lang]['name']} ({lang})...")

        # Собираем заглушки
        placeholders = self.collect_placeholders(lang)
        total = len(placeholders)

        if total == 0:
            print(f"  ✅ Заглушек не найдено, язык уже переведён")
            return

        print(f"  📝 Найдено заглушек: {total}")

        # Переводим пакетами
        all_translations = []
        for i in range(0, total, batch_size):
            batch_placeholders = placeholders[i:i + batch_size]
            batch_texts = [text for _, text, _ in batch_placeholders]

            print(f"  🔄 Перевод пакета {i//batch_size + 1}/{(total + batch_size - 1)//batch_size} ({len(batch_texts)} фраз)...")

            batch_translations = self.translate_batch_via_gemini(batch_texts, lang)
            all_translations.extend(batch_translations)

        # Применяем переводы
        print(f"  💾 Применение переводов...")
        self.replace_placeholders(lang, placeholders, all_translations)

        # Сохраняем
        self.save_locale(lang)
        print(f"  ✅ {lang}.json обновлён ({total} переводов)")

def main():
    import sys

    print("🚀 Запуск автоматического переводчика...")
    translator = AutoTranslator()

    # Определяем языки для перевода
    languages = ['en', 'uz', 'tg', 'ky']

    # Если указан конкретный язык в аргументах
    if len(sys.argv) > 1:
        lang = sys.argv[1].lower()
        if lang in languages:
            languages = [lang]
        else:
            print(f"❌ Неизвестный язык: {lang}")
            print(f"Доступные: {', '.join(languages)}")
            return

    # Переводим все языки
    for lang in languages:
        try:
            translator.translate_language(lang, batch_size=10)
        except Exception as e:
            print(f"❌ Ошибка при переводе {lang}: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*50)
    print("✅ ПЕРЕВОД ЗАВЕРШЁН")
    print("="*50)
    print("\n💡 Проверьте переводы:")
    for lang in languages:
        print(f"  apps/frontend/src/locales/{lang}.json")

    print("\n🧪 Запустите валидатор:")
    print("  python3 scripts/i18n_validator.py --check")

if __name__ == '__main__':
    main()
