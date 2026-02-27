#!/usr/bin/env python3
"""
Находит все использования t() на уровне модуля (вне функций).
Это ошибки, так как t() - функция из хука, доступная только внутри компонентов.
"""

import re
from pathlib import Path
from typing import List, Tuple

def is_inside_function(lines: List[str], line_num: int) -> bool:
    """
    Проверяет, находится ли строка внутри функции/компонента.
    Упрощённая эвристика: ищем function/const/export function выше.
    """
    # Ищем назад до начала файла
    indent_level = len(lines[line_num]) - len(lines[line_num].lstrip())

    for i in range(line_num - 1, -1, -1):
        line = lines[i]
        current_indent = len(line) - len(line.lstrip())

        # Если нашли строку с меньшим отступом - это потенциально объемлющий блок
        if current_indent < indent_level:
            # Проверяем, это функция или объект/массив
            if re.search(r'(function|const \w+ = \(|export function)', line):
                return True
            # Если это export const ARRAY = [ или export const OBJ = {
            if re.search(r'export const \w+ = [\[\{]', line):
                return False

    return False

def find_module_level_t_calls(file_path: Path) -> List[Tuple[int, str]]:
    """
    Находит все вызовы t() на уровне модуля (вне функций).
    Возвращает [(line_number, line_content), ...]
    """
    try:
        content = file_path.read_text(encoding='utf-8')
        lines = content.split('\n')
    except Exception as e:
        return []

    issues = []

    for i, line in enumerate(lines, start=1):
        # Ищем t('...')  или t("...")
        if re.search(r"\bt\(['\"]", line):
            # Проверяем, находится ли внутри функции
            if not is_inside_function(lines, i - 1):  # i-1 потому что enumerate с 1
                issues.append((i, line.strip()))

    return issues

def main():
    src_dir = Path('apps/frontend/src')

    print("🔍 ПОИСК ВЫЗОВОВ t() НА УРОВНЕ МОДУЛЯ")
    print("=" * 60)
    print()

    # Ищем во всех .ts, .tsx файлах
    all_files = list(src_dir.rglob('*.ts')) + list(src_dir.rglob('*.tsx'))

    total_issues = 0
    problematic_files = []

    for file_path in sorted(all_files):
        issues = find_module_level_t_calls(file_path)
        if issues:
            try:
                rel_path = file_path.relative_to(Path.cwd())
            except ValueError:
                rel_path = file_path
            problematic_files.append((rel_path, issues))
            total_issues += len(issues)

    if not problematic_files:
        print("✅ Не найдено вызовов t() на уровне модуля")
        return

    print(f"❌ Найдено {total_issues} проблем в {len(problematic_files)} файлах:\n")

    for file_path, issues in problematic_files:
        print(f"📁 {file_path}")
        for line_num, line_content in issues:
            print(f"   Строка {line_num}: {line_content[:80]}")
        print()

    print("=" * 60)
    print(f"ИТОГО: {total_issues} проблем(ы) в {len(problematic_files)} файлах")
    print()
    print("💡 Эти файлы используют t() на уровне модуля.")
    print("   Решение: переместить в функцию или использовать хардкод.")

if __name__ == '__main__':
    main()
