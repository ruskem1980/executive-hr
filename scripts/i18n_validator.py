#!/usr/bin/env python3
"""
Утилита для валидации и автоматического исправления переводов i18n

Задача:
1. Найти все недостающие ключи во всех языках (когда в ru есть, а в uz/en/tg/ky нет)
2. Найти пустые значения или значения-заглушки
3. Найти несоответствия структуры JSON между языками
4. Автоматически добавить недостающие ключи с fallback на русский язык
5. Генерировать отчёт о проблемах

Использование:
    python3 scripts/i18n_validator.py --check    # Только проверка
    python3 scripts/i18n_validator.py --fix      # Проверка + автоисправление
    python3 scripts/i18n_validator.py --report   # Детальный отчёт
"""

import json
import os
import sys
from pathlib import Path
from typing import Dict, List, Set, Tuple, Any
from collections import defaultdict

# Цвета для терминала
class Colors:
    RED = '\033[91m'
    GREEN = '\033[92m'
    YELLOW = '\033[93m'
    BLUE = '\033[94m'
    MAGENTA = '\033[95m'
    CYAN = '\033[96m'
    WHITE = '\033[97m'
    RESET = '\033[0m'
    BOLD = '\033[1m'


class TranslationValidator:
    """Валидатор и автоисправитель переводов"""

    def __init__(self, locales_dir: str):
        self.locales_dir = Path(locales_dir)
        self.languages = ['ru', 'en', 'uz', 'tg', 'ky']
        self.reference_lang = 'ru'  # Русский как reference
        self.translations: Dict[str, Dict] = {}
        self.issues: List[Dict[str, Any]] = []

    def load_translations(self) -> bool:
        """Загрузить все файлы переводов"""
        print(f"{Colors.CYAN}Загрузка файлов переводов...{Colors.RESET}")

        for lang in self.languages:
            file_path = self.locales_dir / f"{lang}.json"
            if not file_path.exists():
                print(f"{Colors.RED}✗ Файл не найден: {file_path}{Colors.RESET}")
                return False

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    self.translations[lang] = json.load(f)
                print(f"{Colors.GREEN}✓ Загружен {lang}.json{Colors.RESET}")
            except json.JSONDecodeError as e:
                print(f"{Colors.RED}✗ Ошибка JSON в {lang}.json: {e}{Colors.RESET}")
                return False

        return True

    def get_all_keys(self, obj: Dict, prefix: str = '') -> Set[str]:
        """Рекурсивно получить все ключи из вложенного объекта"""
        keys = set()

        for key, value in obj.items():
            full_key = f"{prefix}.{key}" if prefix else key
            keys.add(full_key)

            if isinstance(value, dict):
                keys.update(self.get_all_keys(value, full_key))

        return keys

    def get_value_by_path(self, obj: Dict, path: str) -> Any:
        """Получить значение по пути (напр. 'common.buttons.save')"""
        keys = path.split('.')
        current = obj

        for key in keys:
            if isinstance(current, dict) and key in current:
                current = current[key]
            else:
                return None

        return current

    def set_value_by_path(self, obj: Dict, path: str, value: Any):
        """Установить значение по пути"""
        keys = path.split('.')
        current = obj

        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]

        current[keys[-1]] = value

    def check_missing_keys(self) -> List[Dict]:
        """Найти недостающие ключи в переводах"""
        print(f"\n{Colors.CYAN}Проверка недостающих ключей...{Colors.RESET}")

        reference_keys = self.get_all_keys(self.translations[self.reference_lang])
        missing = []

        for lang in self.languages:
            if lang == self.reference_lang:
                continue

            lang_keys = self.get_all_keys(self.translations[lang])
            missing_keys = reference_keys - lang_keys

            if missing_keys:
                print(f"{Colors.YELLOW}Язык {lang}: {len(missing_keys)} недостающих ключей{Colors.RESET}")
                for key in sorted(missing_keys):
                    ref_value = self.get_value_by_path(self.translations[self.reference_lang], key)
                    missing.append({
                        'type': 'missing_key',
                        'lang': lang,
                        'key': key,
                        'reference_value': ref_value
                    })
            else:
                print(f"{Colors.GREEN}✓ Язык {lang}: все ключи присутствуют{Colors.RESET}")

        return missing

    def check_empty_values(self) -> List[Dict]:
        """Найти пустые значения"""
        print(f"\n{Colors.CYAN}Проверка пустых значений...{Colors.RESET}")

        empty = []

        for lang in self.languages:
            keys = self.get_all_keys(self.translations[lang])

            for key in keys:
                value = self.get_value_by_path(self.translations[lang], key)

                # Проверка на пустые строки или None
                if value is None or (isinstance(value, str) and not value.strip()):
                    ref_value = self.get_value_by_path(self.translations[self.reference_lang], key)
                    empty.append({
                        'type': 'empty_value',
                        'lang': lang,
                        'key': key,
                        'reference_value': ref_value
                    })

        if empty:
            print(f"{Colors.YELLOW}Найдено {len(empty)} пустых значений{Colors.RESET}")
        else:
            print(f"{Colors.GREEN}✓ Пустые значения не найдены{Colors.RESET}")

        return empty

    def check_extra_keys(self) -> List[Dict]:
        """Найти лишние ключи (есть в переводе, но нет в reference)"""
        print(f"\n{Colors.CYAN}Проверка лишних ключей...{Colors.RESET}")

        reference_keys = self.get_all_keys(self.translations[self.reference_lang])
        extra = []

        for lang in self.languages:
            if lang == self.reference_lang:
                continue

            lang_keys = self.get_all_keys(self.translations[lang])
            extra_keys = lang_keys - reference_keys

            if extra_keys:
                print(f"{Colors.YELLOW}Язык {lang}: {len(extra_keys)} лишних ключей{Colors.RESET}")
                for key in sorted(extra_keys):
                    extra.append({
                        'type': 'extra_key',
                        'lang': lang,
                        'key': key
                    })

        if not extra:
            print(f"{Colors.GREEN}✓ Лишние ключи не найдены{Colors.RESET}")

        return extra

    def validate(self) -> bool:
        """Полная валидация переводов"""
        if not self.load_translations():
            return False

        self.issues = []
        self.issues.extend(self.check_missing_keys())
        self.issues.extend(self.check_empty_values())
        self.issues.extend(self.check_extra_keys())

        return True

    def fix_issues(self) -> int:
        """Автоматически исправить найденные проблемы"""
        print(f"\n{Colors.CYAN}Автоисправление проблем...{Colors.RESET}")

        fixed_count = 0

        for issue in self.issues:
            issue_type = issue['type']
            lang = issue['lang']
            key = issue['key']

            if issue_type == 'missing_key':
                # Добавить недостающий ключ с reference значением
                ref_value = issue['reference_value']
                self.set_value_by_path(self.translations[lang], key, ref_value)
                print(f"{Colors.GREEN}✓ Добавлен ключ {key} в {lang}{Colors.RESET}")
                fixed_count += 1

            elif issue_type == 'empty_value':
                # Заменить пустое значение на reference
                ref_value = issue['reference_value']
                if ref_value:
                    self.set_value_by_path(self.translations[lang], key, ref_value)
                    print(f"{Colors.GREEN}✓ Исправлено пустое значение {key} в {lang}{Colors.RESET}")
                    fixed_count += 1

        return fixed_count

    def save_translations(self) -> bool:
        """Сохранить исправленные переводы"""
        print(f"\n{Colors.CYAN}Сохранение файлов...{Colors.RESET}")

        for lang in self.languages:
            file_path = self.locales_dir / f"{lang}.json"

            try:
                with open(file_path, 'w', encoding='utf-8') as f:
                    json.dump(
                        self.translations[lang],
                        f,
                        ensure_ascii=False,
                        indent=2,
                        sort_keys=True
                    )
                print(f"{Colors.GREEN}✓ Сохранён {lang}.json{Colors.RESET}")
            except Exception as e:
                print(f"{Colors.RED}✗ Ошибка сохранения {lang}.json: {e}{Colors.RESET}")
                return False

        return True

    def generate_report(self) -> str:
        """Генерировать детальный отчёт"""
        report = []
        report.append(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}")
        report.append(f"{Colors.BOLD}ОТЧЁТ О ВАЛИДАЦИИ ПЕРЕВОДОВ{Colors.RESET}")
        report.append(f"{Colors.BOLD}{'='*60}{Colors.RESET}\n")

        # Группировка по типам
        by_type = defaultdict(list)
        for issue in self.issues:
            by_type[issue['type']].append(issue)

        # Статистика
        report.append(f"{Colors.CYAN}Общая статистика:{Colors.RESET}")
        report.append(f"  Всего проблем: {len(self.issues)}")
        report.append(f"  Недостающие ключи: {len(by_type['missing_key'])}")
        report.append(f"  Пустые значения: {len(by_type['empty_value'])}")
        report.append(f"  Лишние ключи: {len(by_type['extra_key'])}\n")

        # Детали по языкам
        by_lang = defaultdict(int)
        for issue in self.issues:
            by_lang[issue['lang']] += 1

        report.append(f"{Colors.CYAN}Проблемы по языкам:{Colors.RESET}")
        for lang, count in sorted(by_lang.items()):
            report.append(f"  {lang}: {count} проблем(ы)")

        # Примеры проблем (первые 10)
        if self.issues:
            report.append(f"\n{Colors.CYAN}Примеры проблем (первые 10):{Colors.RESET}")
            for i, issue in enumerate(self.issues[:10], 1):
                report.append(f"\n{i}. [{issue['type']}] {issue['lang']} - {issue['key']}")
                if 'reference_value' in issue:
                    ref = str(issue['reference_value'])[:50]
                    report.append(f"   Reference: {ref}")

        report.append(f"\n{Colors.BOLD}{'='*60}{Colors.RESET}\n")

        return '\n'.join(report)


def main():
    """Главная функция"""
    import argparse

    parser = argparse.ArgumentParser(description='Валидация и исправление переводов i18n')
    parser.add_argument('--check', action='store_true', help='Только проверка без исправления')
    parser.add_argument('--fix', action='store_true', help='Проверка + автоисправление')
    parser.add_argument('--report', action='store_true', help='Детальный отчёт')
    parser.add_argument('--locales-dir', default='apps/frontend/src/locales', help='Путь к директории с переводами')

    args = parser.parse_args()

    # Если не указано ни одного флага, по умолчанию --check
    if not (args.check or args.fix or args.report):
        args.check = True

    # Определение пути
    if os.path.isabs(args.locales_dir):
        locales_dir = args.locales_dir
    else:
        # Относительно корня проекта
        project_root = Path(__file__).parent.parent
        locales_dir = project_root / args.locales_dir

    print(f"{Colors.BOLD}I18N VALIDATOR{Colors.RESET}")
    print(f"Директория переводов: {locales_dir}\n")

    validator = TranslationValidator(str(locales_dir))

    # Валидация
    if not validator.validate():
        sys.exit(1)

    # Отчёт
    if args.report or args.check:
        print(validator.generate_report())

    # Исправление
    if args.fix and validator.issues:
        fixed = validator.fix_issues()

        if fixed > 0:
            if validator.save_translations():
                print(f"\n{Colors.GREEN}{Colors.BOLD}✓ Успешно исправлено {fixed} проблем(ы){Colors.RESET}")
            else:
                print(f"\n{Colors.RED}✗ Ошибка сохранения файлов{Colors.RESET}")
                sys.exit(1)
        else:
            print(f"\n{Colors.YELLOW}Нет проблем для автоисправления{Colors.RESET}")

    # Результат
    if validator.issues and not args.fix:
        print(f"\n{Colors.YELLOW}Найдено проблем: {len(validator.issues)}")
        print(f"Запустите с --fix для автоисправления{Colors.RESET}")
        sys.exit(1)
    elif not validator.issues:
        print(f"\n{Colors.GREEN}{Colors.BOLD}✓ Все переводы корректны!{Colors.RESET}")
        sys.exit(0)


if __name__ == '__main__':
    main()
