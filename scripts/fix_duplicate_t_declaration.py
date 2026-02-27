#!/usr/bin/env python3
"""
Автоматическое исправление дублирования объявления функции t.
Удаляет строку 'const { t } = useTranslation();' в файлах где есть локальная функция 't'.
"""

import re
import sys
from pathlib import Path


def fix_file(file_path: Path) -> bool:
    """
    Исправляет файл, удаляя const { t } = useTranslation(); если есть локальная функция t.

    Returns:
        True если файл был изменён, False если нет.
    """
    content = file_path.read_text(encoding='utf-8')

    # Проверяем наличие обоих паттернов
    has_use_translation = 'const { t } = useTranslation();' in content
    has_local_t_function = re.search(r'const t = \(key: string\)', content)

    if not (has_use_translation and has_local_t_function):
        return False

    # Удаляем строку с useTranslation()
    # Паттерн: const { t } = useTranslation(); с возможными пробелами и переводом строки
    pattern = r'^\s*const\s+\{\s*t\s*\}\s*=\s*useTranslation\(\);?\s*$'

    lines = content.splitlines(keepends=True)
    new_lines = []
    removed = False

    for line in lines:
        if re.match(pattern, line):
            removed = True
            continue
        new_lines.append(line)

    if removed:
        file_path.write_text(''.join(new_lines), encoding='utf-8')
        return True

    return False


def main():
    """Основная функция."""
    base_dir = Path('apps/frontend/src')

    if not base_dir.exists():
        print(f"❌ Директория {base_dir} не найдена")
        sys.exit(1)

    # Найти все .tsx файлы
    tsx_files = list(base_dir.rglob('*.tsx'))

    fixed_count = 0
    fixed_files = []

    for file_path in tsx_files:
        try:
            if fix_file(file_path):
                fixed_count += 1
                fixed_files.append(str(file_path))
                print(f"✓ Исправлен: {file_path.relative_to('.')}")
        except Exception as e:
            print(f"❌ Ошибка при обработке {file_path}: {e}")

    print(f"\n{'='*70}")
    print(f"Итого исправлено файлов: {fixed_count}")
    if fixed_files:
        print(f"\nИсправленные файлы:")
        for f in fixed_files:
            print(f"  - {f}")
    print(f"{'='*70}")

    return 0 if fixed_count > 0 else 1


if __name__ == '__main__':
    sys.exit(main())
