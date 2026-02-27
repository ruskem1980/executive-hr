#!/usr/bin/env python3
"""
Универсальный валидатор JSON-переводов для TypeScript/JavaScript проектов

Применяет правила Platinum Standard:
1. Полнота переводов (все ключи из reference есть в других языках)
2. Совпадение плейсхолдеров {{var}} между языками
3. Аномалии длины (>200% разница)
4. Пустые значения
5. Смешанные алфавиты

Использование:
    python -m src.i18n.json_validator --locales-dir /path/to/locales --reference ru

Пример для Next.js:
    python -m src.i18n.json_validator --locales-dir ./apps/frontend/src/locales --reference ru
"""

import json
import re
import argparse
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


class JSONTranslationValidator:
    """Валидатор JSON-переводов с правилами PT_Standart"""

    def __init__(self, locales_dir: Path, reference_lang: str = "ru"):
        self.locales_dir = Path(locales_dir)
        self.reference_lang = reference_lang
        self.translations = {}
        self.issues = []

    def load_translations(self):
        """Загрузить все JSON файлы переводов"""
        if not self.locales_dir.exists():
            raise FileNotFoundError(f"Директория не найдена: {self.locales_dir}")

        json_files = list(self.locales_dir.glob("*.json"))
        if not json_files:
            raise FileNotFoundError(f"JSON файлы не найдены в {self.locales_dir}")

        for file in json_files:
            lang = file.stem
            try:
                with open(file, 'r', encoding='utf-8') as f:
                    self.translations[lang] = json.load(f)
            except Exception as e:
                print(f"Ошибка загрузки {file}: {e}")
                sys.exit(1)

        if self.reference_lang not in self.translations:
            raise ValueError(
                f"Эталонный язык '{self.reference_lang}' не найден. "
                f"Доступны: {list(self.translations.keys())}"
            )

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

    def check_length_anomalies(self, threshold: float = 3.0):
        """Проверка 3: Длина перевода не отличается >threshold от reference"""
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
                if ratio > threshold or ratio < (1 / threshold):
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
        print("ЗАПУСК ВАЛИДАЦИИ ПЕРЕВОДОВ (Platinum Standard Rules)")
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

    def print_report(self, max_errors: int = 50, max_warnings: int = 30):
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
            for i, issue in enumerate(errors[:max_errors], 1):
                print(f"{i}. [{issue.language}] {issue.key}")
                print(f"   → {issue.message}")
                print()

            if len(errors) > max_errors:
                print(f"... и ещё {len(errors) - max_errors} ошибок (показаны первые {max_errors})")
                print()

        if warnings:
            print("ПРЕДУПРЕЖДЕНИЯ (WARNING):")
            print("-" * 80)
            for i, issue in enumerate(warnings[:max_warnings], 1):
                print(f"{i}. [{issue.language}] {issue.key}")
                print(f"   → {issue.message}")
                print()

            if len(warnings) > max_warnings:
                print(f"... и ещё {len(warnings) - max_warnings} предупреждений (показаны первые {max_warnings})")
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
    parser = argparse.ArgumentParser(
        description="Валидация JSON-переводов с правилами Platinum Standard"
    )
    parser.add_argument(
        "--locales-dir",
        type=str,
        required=True,
        help="Путь к директории с JSON файлами переводов"
    )
    parser.add_argument(
        "--reference",
        type=str,
        default="ru",
        help="Эталонный язык (по умолчанию: ru)"
    )
    parser.add_argument(
        "--max-errors",
        type=int,
        default=50,
        help="Максимум ошибок для вывода (по умолчанию: 50)"
    )
    parser.add_argument(
        "--max-warnings",
        type=int,
        default=30,
        help="Максимум предупреждений для вывода (по умолчанию: 30)"
    )

    args = parser.parse_args()

    try:
        validator = JSONTranslationValidator(args.locales_dir, args.reference)
        validator.validate_all()
        error_count = validator.print_report(args.max_errors, args.max_warnings)
        return 1 if error_count > 0 else 0
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
