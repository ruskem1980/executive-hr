#!/usr/bin/env python3
"""
Реструктуризация системы переводов.
Разделяет смешанный ru.json на правильные языковые файлы.
"""
import json
import re
from pathlib import Path
from typing import Dict, Any
import shutil
from datetime import datetime

PROJECT_ROOT = Path.cwd()
LOCALES_DIR = PROJECT_ROOT / "apps" / "frontend" / "src" / "locales"

# Специфичные символы для определения языка
TAJIK_CHARS = set('ӣӯҳҷқғ')  # Таджикские буквы
KYRGYZ_CHARS = set('өүң')     # Киргизские буквы
UZBEK_LATIN = set('oʻgʻ')     # Узбекские латинские

class LocaleRestructurer:
    def __init__(self):
        self.ru_data = {}
        self.en_data = {}
        self.tg_data = {}
        self.ky_data = {}
        self.uz_data = {}

        self.load_current_files()

    def load_current_files(self):
        """Загружает текущие файлы"""
        for lang in ['ru', 'en', 'tg', 'ky', 'uz']:
            path = LOCALES_DIR / f"{lang}.json"
            if path.exists():
                with open(path, 'r', encoding='utf-8') as f:
                    setattr(self, f'{lang}_data', json.load(f))

    def detect_language(self, text: str) -> str:
        """Определяет язык текста"""
        if not isinstance(text, str) or len(text) < 2:
            return 'ru'

        # Убираем префиксы если есть
        text = re.sub(r'^\[EN\]\s*', '', text)
        text = re.sub(r'^\[FIXME\]\s*', '', text)

        # Проверяем специфичные символы
        text_chars = set(text.lower())

        # Таджикский (ӣ, ӯ, ҳ, ҷ, қ, ғ)
        if text_chars & TAJIK_CHARS:
            return 'tg'

        # Киргизский (ө, ү, ң)
        if text_chars & KYRGYZ_CHARS:
            return 'ky'

        # Узбекский (латиница с oʻ, gʻ или без кириллицы вообще)
        has_cyrillic = bool(re.search(r'[а-яА-ЯёЁ]', text))
        has_latin = bool(re.search(r'[a-zA-Z]', text))

        if has_latin and not has_cyrillic and len(text) > 5:
            # Проверяем, не английский ли это уже
            common_english = ['the', 'is', 'are', 'and', 'or', 'for', 'to', 'of']
            if any(word in text.lower() for word in common_english):
                return 'en'  # Уже переведено
            return 'uz'

        # По умолчанию - русский
        return 'ru'

    def restructure_recursive(self, ru_obj: Any, en_obj: Any, path: str = "") -> Dict[str, Any]:
        """
        Рекурсивно реструктурирует данные.
        Возвращает словарь с ключами: ru, en, tg, ky, uz
        """
        if isinstance(ru_obj, dict):
            result = {
                'ru': {},
                'en': {},
                'tg': {},
                'ky': {},
                'uz': {}
            }

            for key in ru_obj:
                en_value = en_obj.get(key) if isinstance(en_obj, dict) else None
                sub_result = self.restructure_recursive(ru_obj[key], en_value, f"{path}.{key}" if path else key)

                for lang in ['ru', 'en', 'tg', 'ky', 'uz']:
                    if sub_result[lang]:
                        result[lang][key] = sub_result[lang]

            return result

        elif isinstance(ru_obj, str):
            # Определяем реальный язык текста
            detected_lang = self.detect_language(ru_obj)

            # Если в en уже есть английский перевод - берем его
            en_detected = 'en' if (isinstance(en_obj, str) and self.detect_language(en_obj) == 'en') else None

            result = {
                'ru': '',
                'en': '',
                'tg': '',
                'ky': '',
                'uz': ''
            }

            # Распределяем текст по языкам
            clean_text = re.sub(r'^\[EN\]\s*', '', ru_obj)
            clean_text = re.sub(r'^\[FIXME\]\s*', '', clean_text)

            if detected_lang == 'ru':
                result['ru'] = clean_text
                # Если есть английский перевод - используем его
                if en_detected:
                    en_clean = re.sub(r'^\[EN\]\s*', '', en_obj)
                    en_clean = re.sub(r'^\[FIXME\]\s*', '', en_clean)
                    result['en'] = en_clean
            elif detected_lang in ['tg', 'ky', 'uz']:
                result[detected_lang] = clean_text
                # Для национальных языков ru остается пустым (нужен перевод)
            elif detected_lang == 'en':
                # Уже английский - это артефакт, скорее всего
                result['ru'] = clean_text  # Сохраняем как русский

            return result

        else:
            # Для остальных типов (списки, числа и т.д.) - просто копируем
            return {
                'ru': ru_obj,
                'en': ru_obj,
                'tg': ru_obj,
                'ky': ru_obj,
                'uz': ru_obj
            }

    def save_backup(self):
        """Создает бэкапы текущих файлов"""
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_dir = LOCALES_DIR.parent / 'locales_backup_before_restructure' / timestamp
        backup_dir.mkdir(parents=True, exist_ok=True)

        for lang in ['ru', 'en', 'tg', 'ky', 'uz']:
            src = LOCALES_DIR / f"{lang}.json"
            if src.exists():
                dst = backup_dir / f"{lang}.json"
                shutil.copy2(src, dst)

        print(f"📦 Бэкап создан: {backup_dir}")
        return backup_dir

    def save_restructured(self, restructured: Dict[str, Any]):
        """Сохраняет реструктурированные файлы"""
        for lang in ['ru', 'en', 'tg', 'ky', 'uz']:
            path = LOCALES_DIR / f"{lang}.json"
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(restructured[lang], f, ensure_ascii=False, indent=2, sort_keys=True)
            print(f"✅ Сохранен {lang}.json")

    def run(self):
        """Запускает реструктуризацию"""
        print("\n" + "="*60)
        print("🔄 РЕСТРУКТУРИЗАЦИЯ СИСТЕМЫ ПЕРЕВОДОВ")
        print("="*60)

        # Создаем бэкап
        backup_dir = self.save_backup()

        # Анализируем текущее состояние
        print("\n📊 Анализ текущих файлов...")

        def count_by_lang(obj, lang_counter):
            if isinstance(obj, str):
                lang = self.detect_language(obj)
                lang_counter[lang] = lang_counter.get(lang, 0) + 1
            elif isinstance(obj, dict):
                for v in obj.values():
                    count_by_lang(v, lang_counter)

        ru_lang_counter = {}
        count_by_lang(self.ru_data, ru_lang_counter)

        print(f"\nВ ru.json найдено:")
        for lang, count in sorted(ru_lang_counter.items()):
            lang_name = {'ru': 'Русский', 'tg': 'Таджикский', 'ky': 'Киргизский', 'uz': 'Узбекский', 'en': 'Английский'}
            print(f"  {lang_name.get(lang, lang)}: {count} строк")

        # Реструктурируем
        print("\n🔧 Реструктуризация...")
        restructured = self.restructure_recursive(self.ru_data, self.en_data)

        # Проверяем результат
        print("\n📊 Результат реструктуризации:")
        for lang in ['ru', 'en', 'tg', 'ky', 'uz']:
            lang_counter = {}
            count_by_lang(restructured[lang], lang_counter)
            total = sum(lang_counter.values())
            print(f"  {lang}.json: {total} строк")

        # Сохраняем
        print("\n💾 Сохранение файлов...")
        self.save_restructured(restructured)

        print("\n" + "="*60)
        print("✅ РЕСТРУКТУРИЗАЦИЯ ЗАВЕРШЕНА")
        print("="*60)
        print(f"\n📦 Бэкапы сохранены в:")
        print(f"   {backup_dir}")
        print(f"\n💡 Следующие шаги:")
        print(f"   1. Проверьте файлы переводов")
        print(f"   2. Запустите валидатор: python3 scripts/i18n_validator.py --check")
        print(f"   3. Переведите русский на английский через Gemini Pro")

def main():
    restructurer = LocaleRestructurer()
    restructurer.run()

if __name__ == '__main__':
    main()
