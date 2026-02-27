#!/usr/bin/env python3
"""
Проверка полноты покрытия переводов

Тесты:
1. Все ключи из ru.json присутствуют во всех языках
2. Нет кириллицы в латинских языках (en, uz)
3. Нет пустых значений
4. Плейсхолдеры совпадают

Эта программа НЕ проверяет количество слов (т.к. это нормально для разных языков).
"""

import json
import re
from pathlib import Path
from typing import Dict, Set, List
from dataclasses import dataclass
import sys


@dataclass
class CoverageIssue:
    key: str
    language: str
    issue_type: str  # "missing", "cyrillic", "empty", "placeholder_mismatch"
    details: str


class LanguageCoverageChecker:
    def __init__(self, locales_dir: Path, reference_lang: str = "ru"):
        self.locales_dir = locales_dir
        self.reference_lang = reference_lang
        self.translations = {}
        self.issues = []

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

    def check_missing_keys(self):
        """Проверка 1: Все ключи из reference есть в других языках"""
        ref_flat = self.flatten_dict(self.translations[self.reference_lang])
        ref_keys = set(ref_flat.keys())

        for lang in self.translations:
            if lang == self.reference_lang:
                continue

            lang_flat = self.flatten_dict(self.translations[lang])
            lang_keys = set(lang_flat.keys())

            missing = ref_keys - lang_keys
            for key in missing:
                self.issues.append(CoverageIssue(
                    key=key,
                    language=lang,
                    issue_type="missing",
                    details=f"Ключ отсутствует в {lang}"
                ))

    def check_cyrillic_in_latin(self):
        """Проверка 2: Нет кириллицы в латинских языках"""
        cyrillic_pattern = re.compile(r'[а-яА-ЯёЁ]')
        latin_langs = ['en', 'uz']

        for lang in latin_langs:
            if lang not in self.translations:
                continue

            flat = self.flatten_dict(self.translations[lang])

            for key, value in flat.items():
                # Пропустить технические ключи
                if any(skip in key.lower() for skip in ['code', 'id', 'key', 'url', 'link']):
                    continue

                if cyrillic_pattern.search(value):
                    preview = value[:50] + ("..." if len(value) > 50 else "")
                    self.issues.append(CoverageIssue(
                        key=key,
                        language=lang,
                        issue_type="cyrillic",
                        details=f"Кириллица в латинском языке: '{preview}'"
                    ))

    def check_empty_values(self):
        """Проверка 3: Нет пустых значений"""
        for lang, data in self.translations.items():
            flat = self.flatten_dict(data)
            for key, value in flat.items():
                if not value or not value.strip():
                    self.issues.append(CoverageIssue(
                        key=key,
                        language=lang,
                        issue_type="empty",
                        details="Пустое значение"
                    ))

    def check_placeholder_mismatch(self):
        """Проверка 4: Плейсхолдеры {{var}} совпадают"""
        ref_flat = self.flatten_dict(self.translations[self.reference_lang])

        for lang in self.translations:
            if lang == self.reference_lang:
                continue

            lang_flat = self.flatten_dict(self.translations[lang])

            for key in ref_flat:
                if key not in lang_flat:
                    continue

                ref_text = ref_flat[key]
                lang_text = lang_flat[key]

                ref_placeholders = set(re.findall(r'\{\{(\w+)\}\}', ref_text))
                lang_placeholders = set(re.findall(r'\{\{(\w+)\}\}', lang_text))

                if ref_placeholders != lang_placeholders:
                    self.issues.append(CoverageIssue(
                        key=key,
                        language=lang,
                        issue_type="placeholder_mismatch",
                        details=f"Плейсхолдеры не совпадают: ru={ref_placeholders}, {lang}={lang_placeholders}"
                    ))

    def run_checks(self):
        """Запустить все проверки"""
        print("=" * 80)
        print("ПРОВЕРКА ПОЛНОТЫ ПОКРЫТИЯ ПЕРЕВОДОВ")
        print("=" * 80)
        print()

        self.load_translations()
        print(f"📦 Загружено языков: {', '.join(sorted(self.translations.keys()))}")
        print()

        print("🔍 Проверка 1/4: Пропущенные ключи...")
        self.check_missing_keys()

        print("🔍 Проверка 2/4: Кириллица в латинских языках...")
        self.check_cyrillic_in_latin()

        print("🔍 Проверка 3/4: Пустые значения...")
        self.check_empty_values()

        print("🔍 Проверка 4/4: Несовпадение плейсхолдеров...")
        self.check_placeholder_mismatch()

        print("✅ Все проверки завершены")
        print()

    def print_report(self):
        """Вывести отчёт"""
        print("=" * 80)
        print("ОТЧЁТ ПО ПОКРЫТИЮ ПЕРЕВОДОВ")
        print("=" * 80)
        print()

        if not self.issues:
            print("✅ ВСЕ ПРОВЕРКИ ПРОЙДЕНЫ!")
            print()
            print("Все языки полностью переведены:")
            for lang in sorted(self.translations.keys()):
                flat = self.flatten_dict(self.translations[lang])
                print(f"  ✅ {lang}: {len(flat)} ключей")
            print()
            return 0

        # Группировка по типам проблем
        issues_by_type = {
            "missing": [],
            "cyrillic": [],
            "empty": [],
            "placeholder_mismatch": []
        }

        for issue in self.issues:
            issues_by_type[issue.issue_type].append(issue)

        # Статистика
        print(f"Всего проблем: {len(self.issues)}")
        print(f"  - Пропущенные ключи: {len(issues_by_type['missing'])}")
        print(f"  - Кириллица в латинице: {len(issues_by_type['cyrillic'])}")
        print(f"  - Пустые значения: {len(issues_by_type['empty'])}")
        print(f"  - Несовпадение плейсхолдеров: {len(issues_by_type['placeholder_mismatch'])}")
        print()

        # Детальный отчёт по каждому типу
        for issue_type, title in [
            ("missing", "ПРОПУЩЕННЫЕ КЛЮЧИ"),
            ("empty", "ПУСТЫЕ ЗНАЧЕНИЯ"),
            ("placeholder_mismatch", "НЕСОВПАДЕНИЕ ПЛЕЙСХОЛДЕРОВ"),
            ("cyrillic", "КИРИЛЛИЦА В ЛАТИНИЦЕ")
        ]:
            issues = issues_by_type[issue_type]
            if not issues:
                continue

            print(f"{'=' * 80}")
            print(f"{title} ({len(issues)})")
            print(f"{'=' * 80}")
            print()

            # Группировка по языкам
            by_lang = {}
            for issue in issues:
                if issue.language not in by_lang:
                    by_lang[issue.language] = []
                by_lang[issue.language].append(issue)

            for lang in sorted(by_lang.keys()):
                lang_issues = by_lang[lang]
                print(f"🌍 {lang.upper()} ({len(lang_issues)} проблем)")
                print("-" * 80)

                for i, issue in enumerate(lang_issues[:20], 1):
                    print(f"{i}. {issue.key}")
                    print(f"   → {issue.details}")
                    print()

                if len(lang_issues) > 20:
                    print(f"... и ещё {len(lang_issues) - 20} проблем")
                    print()

        # Рекомендации
        print("=" * 80)
        print("РЕКОМЕНДАЦИИ")
        print("=" * 80)
        print()

        if issues_by_type["missing"]:
            print("1. Пропущенные ключи: запустите scripts/fix_translations.py")

        if issues_by_type["empty"]:
            print("2. Пустые значения: проверьте JSON файлы вручную")

        if issues_by_type["placeholder_mismatch"]:
            print("3. Плейсхолдеры: исправьте вручную - это может сломать приложение!")

        if issues_by_type["cyrillic"]:
            print("4. Кириллица: исправьте вручную или перегенерируйте переводы")

        print()

        return len(self.issues)


def main():
    locales_dir = Path(__file__).parent.parent / "apps" / "frontend" / "src" / "locales"

    if not locales_dir.exists():
        print(f"❌ Директория не найдена: {locales_dir}")
        return 1

    checker = LanguageCoverageChecker(locales_dir)
    checker.run_checks()
    error_count = checker.print_report()

    return 1 if error_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
