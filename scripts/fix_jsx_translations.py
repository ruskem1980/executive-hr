#!/usr/bin/env python3
"""
Исправляет голые ключи в JSX: {'key'} → {t('key')}
"""

import re
from pathlib import Path

def fix_file(file_path: Path) -> bool:
    """Исправляет голые ключи в JSX."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except:
        return False

    original = content

    # {'key.with.dots'} → {t('key.with.dots')}
    # Только ключи с точками
    content = re.sub(
        r"\{'([a-z]+\.[a-z.]+)'\}",
        r"{t('\1')}",
        content,
        flags=re.IGNORECASE
    )

    # {"key.with.dots"} → {t("key.with.dots")}
    content = re.sub(
        r'\{"([a-z]+\.[a-z.]+)"\}',
        r'{t("\1")}',
        content,
        flags=re.IGNORECASE
    )

    if content != original:
        try:
            file_path.write_text(content, encoding='utf-8')
            return True
        except:
            return False

    return False

def main():
    src_dir = Path('apps/frontend/src')
    all_files = list(src_dir.rglob('*.tsx'))

    print(f"🔧 ИСПРАВЛЕНИЕ ГОЛЫХ КЛЮЧЕЙ В JSX ({len(all_files)} файлов)")
    print("=" * 60)

    fixed = 0
    for file_path in sorted(all_files):
        if fix_file(file_path):
            rel_path = file_path.relative_to(src_dir)
            print(f"✅ {rel_path}")
            fixed += 1

    print(f"\n{'='*60}")
    print(f"✅ Исправлено: {fixed} файлов")

if __name__ == '__main__':
    main()
