#!/usr/bin/env python3
"""
Удаляет вызовы t() на уровне модуля, заменяя t('key') на 'key'.
Работает только в export const объектах/массивах.
"""

import re
from pathlib import Path
from typing import List

def remove_t_calls_from_file(file_path: Path) -> bool:
    """
    Удаляет все t('...') и t("...") вызовы, оставляя только строку внутри.
    Возвращает True если были изменения.
    """
    try:
        content = file_path.read_text(encoding='utf-8')
    except Exception as e:
        print(f"  ❌ Ошибка чтения {file_path}: {e}")
        return False

    original = content

    # Паттерн: t('...') или t("...")
    # Заменяем на просто '...' или "..."
    # Сохраняем тип кавычек

    # Вариант 1: t('single quotes')
    content = re.sub(r"\bt\('([^']+)'\)", r"'\1'", content)

    # Вариант 2: t("double quotes")
    content = re.sub(r'\bt\("([^"]+)"\)', r'"\1"', content)

    if content != original:
        try:
            file_path.write_text(content, encoding='utf-8')
            return True
        except Exception as e:
            print(f"  ❌ Ошибка записи {file_path}: {e}")
            return False

    return False

def main():
    src_dir = Path('apps/frontend/src')

    print("🔧 УДАЛЕНИЕ t() ВЫЗОВОВ НА УРОВНЕ МОДУЛЯ")
    print("=" * 60)
    print()

    # Список проблемных файлов из предыдущего скрипта
    # Можно получить динамически, но для скорости используем хардкод основных
    problem_patterns = [
        '**/*-data.ts',
        '**/page.tsx',
        '**/*Screen.tsx',
        '**/*Modal.tsx',
        '**/*Card.tsx',
        '**/*Calculator.tsx',
    ]

    all_files = set()
    for pattern in problem_patterns:
        all_files.update(src_dir.glob(pattern))

    fixed_count = 0
    error_count = 0

    print(f"Обрабатываю {len(all_files)} файлов...\n")

    for file_path in sorted(all_files):
        try:
            if remove_t_calls_from_file(file_path):
                rel_path = file_path.relative_to(Path('apps/frontend/src'))
                print(f"  ✅ {rel_path}")
                fixed_count += 1
        except Exception as e:
            print(f"  ❌ {file_path}: {e}")
            error_count += 1

    print(f"\n{'='*60}")
    print(f"✅ Исправлено файлов: {fixed_count}")
    print(f"❌ Ошибок: {error_count}")
    print(f"⏭️  Без изменений: {len(all_files) - fixed_count - error_count}")

if __name__ == '__main__':
    main()
