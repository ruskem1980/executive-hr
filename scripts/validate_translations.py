#!/usr/bin/env python3
"""
Валидатор переводов для migranthub_g

Проверяет:
1. Полноту переводов (все ключи из ru.json есть в других языках)
2. Совпадение плейсхолдеров {{var}}
3. Аномалии длины (>200% разница)
4. Пустые значения
5. Смешанные алфавиты
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Any, Set
from dataclasses import dataclass
from enum import Enum
import sys


class Severity(Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
    INFO = "INFO"


@dataclass
class Issue:
    severity: Severity
    key: str
    language: str
    message: str


class TranslationValidator:
    def __init__(self, locales_dir: Path, reference_lang: str = "ru"):
        self.locales_dir = locales_dir
        self.reference_lang = reference_lang
        self.translations = {}
        self.issues = []

    def load_translations(self):
        """Загрузить все JSON файлы переводов"""
        for file in self.locales_dir.glob("*.json"):
            lang = file.stem
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    self.translations[lang] = json.load(f)
            except Exception as e:
                print(f"Ошибка загрузки {file}: {e}")
                sys.exit(1)

    def flatten_dict(self, d: Dict, parent_key: str = '') -> Dict[str, str]:
        """Преобразовать вложенный dict в плоский с dot-notation ключами"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self.flatten_dict(v, new_key).items())
            else:
                items.append((new_key, str(v) if v is not None else ""))
        return dict(items)

    def check_completeness(self):
        """Проверка 1: Все ключи из reference есть в других языках"""
        ref_flat = self.flatten_dict(self.translations[self.reference_lang])
        ref_keys = set(ref_flat.keys())

        for lang in self.translations:
            if lang == self.reference_lang:
                continue

            lang_flat = self.flatten_dict(self.translations[lang])
            lang_keys = set(lang_flat.keys())

            # Пропущенные ключи
            missing = ref_keys - lang_keys
            for key in missing:
                self.issues.append(Issue(
                    Severity.ERROR,
                    key,
                    lang,
                    f"Отсутствует перевод (есть в {self.reference_lang}, нет в {lang})"
                ))

            # Лишние ключи
            extra = lang_keys - ref_keys
            for key in extra:
                self.issues.append(Issue(
                    Severity.WARNING,
                    key,
                    lang,
                    f"Лишний ключ (есть в {lang}, нет в {self.reference_lang})"
                ))

    def check_placeholders(self):
        """Проверка 2: Плейсхолдеры {{var}} совпадают между языками"""
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

                # Извлечь плейсхолдеры {{var}}
                ref_placeholders = set(re.findall(r'\{\{(\w+)\}\}', ref_text))
                lang_placeholders = set(re.findall(r'\{\{(\w+)\}\}', lang_text))

                if ref_placeholders != lang_placeholders:
                    self.issues.append(Issue(
                        Severity.ERROR,
                        key,
                        lang,
                        f"Плейсхолдеры не совпадают: {self.reference_lang}={ref_placeholders}, {lang}={lang_placeholders}"
                    ))

    def check_length_anomalies(self):
        """Проверка 3: Длина перевода не отличается >200% от reference"""
        ref_flat = self.flatten_dict(self.translations[self.reference_lang])

        for lang in self.translations:
            if lang == self.reference_lang:
                continue

            lang_flat = self.flatten_dict(self.translations[lang])

            for key in ref_flat:
                if key not in lang_flat:
                    continue

                ref_len = len(ref_flat[key])
                lang_len = len(lang_flat[key])

                if ref_len == 0:
                    continue

                ratio = lang_len / ref_len
                if ratio > 3.0 or ratio < 0.33:
                    self.issues.append(Issue(
                        Severity.WARNING,
                        key,
                        lang,
                        f"Аномальная длина: {ref_len} ({self.reference_lang}) vs {lang_len} ({lang}) [ratio={ratio:.2f}]"
                    ))

    def check_empty_values(self):
        """Проверка 4: Пустые значения"""
        for lang, data in self.translations.items():
            flat = self.flatten_dict(data)
            for key, value in flat.items():
                if not value or not value.strip():
                    self.issues.append(Issue(
                        Severity.ERROR,
                        key,
                        lang,
                        "Пустое значение"
                    ))

    def check_mixed_languages(self):
        """Проверка 5: Смешанные алфавиты"""
        cyrillic_pattern = re.compile(r'[а-яА-ЯёЁ]')

        for lang, data in self.translations.items():
            flat = self.flatten_dict(data)

            for key, value in flat.items():
                # Пропустить технические ключи
                if any(skip in key.lower() for skip in ['code', 'id', 'key', 'url', 'link']):
                    continue

                has_cyrillic = bool(cyrillic_pattern.search(value))

                # en не должен содержать кириллицу
                if lang == 'en' and has_cyrillic:
                    preview = value[:50] + ("..." if len(value) > 50 else "")
                    self.issues.append(Issue(
                        Severity.WARNING,
                        key,
                        lang,
                        f"Кириллица в английском: '{preview}'"
                    ))

    def validate_all(self):
        """Запустить все проверки"""
        print("=" * 80)
        print("ЗАПУСК ВАЛИДАЦИИ ПЕРЕВОДОВ")
        print("=" * 80)
        print()

        self.load_translations()

        print(f"Загружено языков: {', '.join(sorted(self.translations.keys()))}")
        print(f"Эталонный язык: {self.reference_lang}")

        # Вывести количество ключей
        for lang in sorted(self.translations.keys()):
            flat = self.flatten_dict(self.translations[lang])
            print(f"  - {lang}: {len(flat)} ключей")
        print()

        print("Проверка 1/5: Полнота переводов...")
        self.check_completeness()

        print("Проверка 2/5: Плейсхолдеры {{var}}...")
        self.check_placeholders()

        print("Проверка 3/5: Аномалии длины...")
        self.check_length_anomalies()

        print("Проверка 4/5: Пустые значения...")
        self.check_empty_values()

        print("Проверка 5/5: Смешанные алфавиты...")
        self.check_mixed_languages()

        print("Все проверки завершены.")
        print()

    def print_report(self):
        """Вывести отчёт"""
        errors = [i for i in self.issues if i.severity == Severity.ERROR]
        warnings = [i for i in self.issues if i.severity == Severity.WARNING]

        print("=" * 80)
        print("ОТЧЁТ ПО ВАЛИДАЦИИ")
        print("=" * 80)
        print()

        print(f"Всего проблем: {len(self.issues)}")
        print(f"  - Ошибки (ERROR): {len(errors)}")
        print(f"  - Предупреждения (WARNING): {len(warnings)}")
        print()

        if errors:
            print("ОШИБКИ (ERROR):")
            print("-" * 80)
            for i, issue in enumerate(errors[:50], 1):
                print(f"{i}. [{issue.language}] {issue.key}")
                print(f"   → {issue.message}")
                print()

            if len(errors) > 50:
                print(f"... и ещё {len(errors) - 50} ошибок (показаны первые 50)")
                print()

        if warnings:
            print("ПРЕДУПРЕЖДЕНИЯ (WARNING):")
            print("-" * 80)
            for i, issue in enumerate(warnings[:30], 1):
                print(f"{i}. [{issue.language}] {issue.key}")
                print(f"   → {issue.message}")
                print()

            if len(warnings) > 30:
                print(f"... и ещё {len(warnings) - 30} предупреждений (показаны первые 30)")
                print()

        # Статистика по языкам
        print("СТАТИСТИКА ПО ЯЗЫКАМ:")
        print("-" * 80)
        for lang in sorted(self.translations.keys()):
            flat = self.flatten_dict(self.translations[lang])
            lang_issues = [i for i in self.issues if i.language == lang]
            lang_errors = len([i for i in lang_issues if i.severity == Severity.ERROR])
            lang_warnings = len([i for i in lang_issues if i.severity == Severity.WARNING])

            status = "✅" if lang_errors == 0 else "❌"
            print(f"{status} {lang}: {len(flat)} ключей | {lang_errors} ошибок | {lang_warnings} предупреждений")
        print()

        if errors:
            print("=" * 80)
            print(f"❌ ВАЛИДАЦИЯ НЕ ПРОЙДЕНА: {len(errors)} ошибок")
            print("=" * 80)
        else:
            print("=" * 80)
            print(f"✅ ВАЛИДАЦИЯ ПРОЙДЕНА ({len(warnings)} предупреждений)")
            print("=" * 80)

        return len(errors)


def main():
    locales_dir = Path(__file__).parent.parent / "apps" / "frontend" / "src" / "locales"

    if not locales_dir.exists():
        print(f"❌ Директория не найдена: {locales_dir}")
        return 1

    validator = TranslationValidator(locales_dir, reference_lang="ru")
    validator.validate_all()
    error_count = validator.print_report()

    return 1 if error_count > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
