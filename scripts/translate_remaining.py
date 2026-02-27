#!/usr/bin/env python3
"""
Переводит оставшиеся фразы с префиксами [EN], [UZ], etc через Gemini Flash.
Работает пакетами по 100 фраз для скорости.
"""
import json
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Set

PROJECT_ROOT = Path.cwd()
LOCALES_DIR = PROJECT_ROOT / "apps" / "frontend" / "src" / "locales"

LANG_INFO = {
    'en': 'English',
    'uz': 'Uzbek (Latin script)',
    'tg': 'Tajik (Cyrillic script)',
    'ky': 'Kyrgyz (Cyrillic script)'
}

class RemainingTranslator:
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
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.translations[lang], f, ensure_ascii=False, indent=2, sort_keys=True)

    def collect_remaining_phrases(self, lang: str) -> List[str]:
        """Собирает оставшиеся фразы с префиксами"""
        phrases = []
        prefix = f'[{lang.upper()}]'

        def traverse(obj):
            if isinstance(obj, str):
                if obj.startswith(prefix):
                    russian_text = obj[len(prefix):].strip()
                    if russian_text not in phrases:
                        phrases.append(russian_text)
            elif isinstance(obj, dict):
                for value in obj.values():
                    traverse(value)
            elif isinstance(obj, list):
                for item in obj:
                    traverse(item)

        traverse(self.translations[lang])
        return phrases

    def translate_batch(self, batch: List[str], lang: str) -> Dict[str, str]:
        """Переводит пакет фраз через Gemini Flash"""
        # Создаём компактный промпт
        numbered_batch = "\n".join(f"{i+1}|{phrase}" for i, phrase in enumerate(batch))

        prompt = f"""Translate to {LANG_INFO[lang]}. Output format: number|translation

Input (Russian):
{numbered_batch}

Output ({LANG_INFO[lang]}):"""

        try:
            result = subprocess.run(
                ['bash', '.claude/helpers/gemini-bridge.sh', 'flash', prompt],
                capture_output=True,
                text=True,
                timeout=60
            )

            if result.returncode != 0:
                return {}

            # Парсим ответ
            translations = {}
            for line in result.stdout.strip().split('\n'):
                line = line.strip()
                if '|' in line:
                    parts = line.split('|', 1)
                    if len(parts) == 2:
                        try:
                            idx = int(parts[0].strip()) - 1
                            translation = parts[1].strip()
                            if 0 <= idx < len(batch):
                                translations[batch[idx]] = translation
                        except ValueError:
                            continue

            return translations

        except Exception as e:
            print(f"    ⚠️ Ошибка: {e}")
            return {}

    def apply_translations(self, lang: str, translations: Dict[str, str]):
        """Применяет переводы"""
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

        self.translations[lang] = replace_in_obj(self.translations[lang])
        self.save_locale(lang)
        return replaced_count

    def translate_language(self, lang: str, batch_size: int = 100):
        """Переводит язык пакетами"""
        print(f"\n🌍 Перевод оставшихся фраз на {lang.upper()}...")

        phrases = self.collect_remaining_phrases(lang)
        total = len(phrases)

        if total == 0:
            print(f"  ✅ Нет оставшихся фраз")
            return

        print(f"  📝 Найдено фраз: {total}")
        print(f"  📦 Пакетов по {batch_size}: {(total + batch_size - 1) // batch_size}")

        all_translations = {}
        completed_batches = 0

        for i in range(0, total, batch_size):
            batch = phrases[i:i + batch_size]
            batch_num = i // batch_size + 1
            total_batches = (total + batch_size - 1) // batch_size

            print(f"  🔄 Пакет {batch_num}/{total_batches} ({len(batch)} фраз)...", end=' ', flush=True)

            batch_translations = self.translate_batch(batch, lang)
            all_translations.update(batch_translations)

            completed_batches += 1
            success_rate = len(batch_translations) / len(batch) * 100
            print(f"OK ({success_rate:.0f}%)")

            # Пауза между запросами (rate limiting)
            if batch_num < total_batches:
                time.sleep(1)

        # Применяем переводы
        print(f"  💾 Применение переводов...")
        replaced = self.apply_translations(lang, all_translations)

        print(f"  ✅ Переведено: {replaced}/{total} ({replaced/total*100:.1f}%)")

def main():
    import sys

    print("🚀 Запуск перевода оставшихся фраз через Gemini Flash...")
    print("⏱️  Примерное время: ~10 минут для всех языков\n")

    translator = RemainingTranslator()

    languages = ['en', 'uz', 'tg', 'ky']

    if len(sys.argv) > 1:
        lang = sys.argv[1].lower()
        if lang in languages:
            languages = [lang]

    start_time = time.time()

    for lang in languages:
        translator.translate_language(lang, batch_size=100)

    elapsed = time.time() - start_time

    print("\n" + "="*60)
    print("✅ ПЕРЕВОД ЗАВЕРШЁН")
    print("="*60)
    print(f"⏱️  Время выполнения: {elapsed/60:.1f} минут")
    print("\n🧪 Запустите валидатор:")
    print("  python3 scripts/i18n_validator.py --check")

if __name__ == '__main__':
    main()
