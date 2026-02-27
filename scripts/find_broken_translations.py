#!/usr/bin/env python3
"""
Находит места где t() был неправильно удалён - голые ключи переводов в JSX.
Ищет паттерны типа {'key.name'} или ("key.name") в JSX.
"""

import re
from pathlib import Path

def find_broken_translations(file_path: Path):
    """Находит голые ключи переводов в JSX/коде."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except:
        return []

    issues = []
    lines = content.split('\n')

    for i, line in enumerate(lines, start=1):
        # Паттерн: {'key.with.dots'} или ("key.with.dots") или (\'key.with.dots\')
        # Ключи переводов обычно содержат точки
        patterns = [
            r"\{['\"]([a-z]+\.[a-z.]+)['\"]\\}",  # {'key.name'}
            r"\(['\"]([a-z]+\.[a-z.]+)['\"]\)",   # ('key.name') или ("key.name")
            r"&&\s+\(['\"]([a-z]+\.[a-z.]+)['\"]\)",  # && ('key.name')
        ]

        for pattern in patterns:
            matches = re.finditer(pattern, line, re.IGNORECASE)
            for match in matches:
                key = match.group(1)
                # Игнорируем импорты и const
                if 'import' not in line and 'const ' not in line and 'from' not in line:
                    issues.append((i, line.strip(), key))

    return issues

def main():
    src_dir = Path('apps/frontend/src')
    all_files = list(src_dir.rglob('*.tsx')) + list(src_dir.rglob('*.ts'))

    print("🔍 ПОИСК ГОЛЫХ КЛЮЧЕЙ ПЕРЕВОДОВ (без t())")
    print("=" * 60)
    print()

    total_issues = 0
    problematic_files = []

    for file_path in sorted(all_files):
        issues = find_broken_translations(file_path)
        if issues:
            rel_path = file_path.relative_to(src_dir)
            problematic_files.append((rel_path, issues))
            total_issues += len(issues)

    if not problematic_files:
        print("✅ Не найдено голых ключей переводов")
        return

    print(f"❌ Найдено {total_issues} проблем в {len(problematic_files)} файлах:\n")

    for file_path, issues in problematic_files[:20]:  # Первые 20
        print(f"📁 {file_path}")
        for line_num, line_content, key in issues[:5]:  # Первые 5 на файл
            print(f"   Строка {line_num}: {line_content[:80]}")
            print(f"   → Ключ: {key}")
        if len(issues) > 5:
            print(f"   ... и ещё {len(issues) - 5} проблем")
        print()

    print(f"\n{'='*60}")
    print(f"ИТОГО: {total_issues} проблем в {len(problematic_files)} файлах")
    print("\nНужно восстановить t() вокруг этих ключей")

if __name__ == '__main__':
    main()
