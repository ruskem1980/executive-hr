#!/usr/bin/env python3
"""
Быстрый массовый переводчик через Gemini Pro.
Переводит все уникальные фразы одним запросом для каждого языка.
"""
import json
import subprocess
from pathlib import Path
from typing import Dict, Set, List

PROJECT_ROOT = Path.cwd()
LOCALES_DIR = PROJECT_ROOT / "apps" / "frontend" / "src" / "locales"

class BulkTranslator:
    def __init__(self):
        self.ru_json = self._load_json('ru')
        self.unique_phrases = set()

    def _load_json(self, lang: str) -> dict:
        """Загружает JSON файл"""
        path = LOCALES_DIR / f"{lang}.json"
        with open(path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def _save_json(self, lang: str, data: dict):
        """Сохраняет JSON файл"""
        path = LOCALES_DIR / f"{lang}.json"
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)

    def collect_unique_phrases(self, lang: str) -> Set[str]:
        """Собирает все уникальные русские фразы из заглушек"""
        phrases = set()
        prefix = f'[{lang.upper()}]'

        target_json = self._load_json(lang)

        def traverse(obj):
            if isinstance(obj, str):
                if obj.startswith(prefix):
                    russian_text = obj[len(prefix):].strip()
                    phrases.add(russian_text)
            elif isinstance(obj, dict):
                for value in obj.values():
                    traverse(value)
            elif isinstance(obj, list):
                for item in obj:
                    traverse(item)

        traverse(target_json)
        return phrases

    def translate_phrases_via_gemini(self, phrases: List[str], target_lang: str) -> Dict[str, str]:
        """Переводит список уникальных фраз через Gemini Pro"""
        if not phrases:
            return {}

        lang_names = {
            'en': 'English',
            'uz': 'Uzbek (Latin script)',
            'tg': 'Tajik (Cyrillic script)',
            'ky': 'Kyrgyz (Cyrillic script)'
        }

        # Создаём пронумерованный список фраз
        numbered_phrases = "\n".join(f"{i+1}. {phrase}" for i, phrase in enumerate(phrases))

        prompt = f"""Translate these {len(phrases)} Russian phrases to {lang_names[target_lang]}.

STRICT FORMAT:
- Output ONLY the translations
- One translation per line
- Keep the EXACT same order and line count
- NO numbering, NO markdown, NO explanations
- Preserve technical terms, numbers, time formats (24/7, Пн-Пт 9:00-18:00)
- Keep proper nouns unchanged

Russian phrases:
{numbered_phrases}

{lang_names[target_lang]} translations:"""

        print(f"  🔄 Отправка {len(phrases)} фраз в Gemini Pro...")

        try:
            result = subprocess.run(
                ['bash', '.claude/helpers/gemini-bridge.sh', 'pro', prompt],
                capture_output=True,
                text=True,
                timeout=180
            )

            if result.returncode != 0:
                print(f"  ⚠️ Gemini ошибка: {result.stderr}")
                return {}

            response = result.stdout.strip()

            # Убираем markdown если есть
            import re
            response = re.sub(r'^```.*?\n', '', response, flags=re.MULTILINE)
            response = re.sub(r'\n```$', '', response)

            # Разбиваем на строки
            lines = [line.strip() for line in response.split('\n') if line.strip()]

            # Создаём словарь
            translations = {}
            for i, (phrase, translation) in enumerate(zip(phrases, lines)):
                translations[phrase] = translation

            if len(translations) != len(phrases):
                print(f"  ⚠️ Получено {len(translations)} переводов из {len(phrases)}")

            return translations

        except subprocess.TimeoutExpired:
            print(f"  ❌ Timeout при переводе")
            return {}
        except Exception as e:
            print(f"  ❌ Ошибка: {e}")
            return {}

    def apply_translations(self, lang: str, translations: Dict[str, str]):
        """Применяет переводы к языковому файлу"""
        target_json = self._load_json(lang)
        prefix = f'[{lang.upper()}]'
        replaced_count = 0

        def replace_in_obj(obj):
            nonlocal replaced_count
            if isinstance(obj, str):
                if obj.startswith(prefix):
                    russian_text = obj[len(prefix):].strip()
                    if russian_text in translations:
                        replaced_count += 1
                        return translations[russian_text]
                return obj
            elif isinstance(obj, dict):
                return {k: replace_in_obj(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_in_obj(item) for item in obj]
            return obj

        updated_json = replace_in_obj(target_json)
        self._save_json(lang, updated_json)

        print(f"  ✅ Заменено {replaced_count} переводов в {lang}.json")

    def translate_language(self, lang: str, chunk_size: int = 500):
        """Переводит один язык"""
        print(f"\n🌍 Перевод на {lang.upper()}...")

        # Собираем уникальные фразы
        phrases = self.collect_unique_phrases(lang)
        total = len(phrases)

        if total == 0:
            print(f"  ✅ Заглушек не найдено")
            return

        print(f"  📝 Найдено уникальных фраз: {total}")

        # Переводим чанками по 500 фраз
        phrases_list = sorted(list(phrases))  # Сортируем для консистентности
        all_translations = {}

        for i in range(0, total, chunk_size):
            chunk = phrases_list[i:i + chunk_size]
            print(f"  📦 Чанк {i//chunk_size + 1}/{(total + chunk_size - 1)//chunk_size} ({len(chunk)} фраз)")

            chunk_translations = self.translate_phrases_via_gemini(chunk, lang)
            all_translations.update(chunk_translations)

        # Применяем переводы
        print(f"  💾 Применение переводов...")
        self.apply_translations(lang, all_translations)

def main():
    import sys

    print("🚀 Запуск быстрого массового переводчика...")
    translator = BulkTranslator()

    languages = ['en', 'uz', 'tg', 'ky']

    if len(sys.argv) > 1:
        lang = sys.argv[1].lower()
        if lang in languages:
            languages = [lang]

    for lang in languages:
        try:
            translator.translate_language(lang, chunk_size=500)
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            import traceback
            traceback.print_exc()

    print("\n" + "="*50)
    print("✅ ПЕРЕВОД ЗАВЕРШЁН")
    print("="*50)

if __name__ == '__main__':
    main()
