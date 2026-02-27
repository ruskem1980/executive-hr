#!/usr/bin/env python3
"""
АГРЕССИВНОЕ удаление ВСЕХ t() на уровне модуля во ВСЕХ .ts/.tsx файлах.
Заменяет t('...') на '...' и t("...") на "..."
"""

import re
from pathlib import Path

def fix_file(file_path: Path) -> bool:
    """Удаляет все t() вызовы. Возвращает True если были изменения."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except:
        return False

    original = content

    # t('single quotes') → 'single quotes'
    content = re.sub(r"\bt\('([^']+)'\)", r"'\1'", content)

    # t("double quotes") → "double quotes"
    content = re.sub(r'\bt\("([^"]+)"\)', r'"\1"', content)

    if content != original:
        try:
            file_path.write_text(content, encoding='utf-8')
            return True
        except:
            return False

    return False

def main():
    src_dir = Path('apps/frontend/src')

    # ВСЕ .ts и .tsx файлы
    all_files = list(src_dir.rglob('*.ts')) + list(src_dir.rglob('*.tsx'))

    print(f"🔧 ОБРАБОТКА {len(all_files)} ФАЙЛОВ")
    print("=" * 60)

    fixed = 0
    for file_path in all_files:
        if fix_file(file_path):
            fixed += 1
            print(f"✅ {file_path.relative_to(src_dir)}")

    print(f"\n{'='*60}")
    print(f"✅ Исправлено: {fixed} файлов")
    print(f"⏭️  Без изменений: {len(all_files) - fixed}")

if __name__ == '__main__':
    main()
