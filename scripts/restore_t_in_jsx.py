#!/usr/bin/env python3
"""
Восстанавливает t() в JSX где рендерятся ключи переводов.
Заменяет {'key.name'} на {t('key.name')} и ("key.name") на {t("key.name")}
ТОЛЬКО в JSX контексте.
"""

import re
from pathlib import Path

def restore_t_in_jsx(file_path: Path) -> bool:
    """Восстанавливает t() в JSX. Возвращает True если были изменения."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except:
        return False

    original = content

    # Паттерн 1: {('key.with.dots')} → {t('key.with.dots')}
    # Только ключи с точками (это ключи переводов)
    content = re.sub(
        r"\{\('([a-z]+\.[a-z.]+)'\)\}",
        r"{t('\1')}",
        content,
        flags=re.IGNORECASE
    )

    # Паттерн 2: {("key.with.dots")} → {t("key.with.dots")}
    content = re.sub(
        r'\{\("([a-z]+\.[a-z.]+)"\)\}',
        r'{t("\1")}',
        content,
        flags=re.IGNORECASE
    )

    # Паттерн 3: && ('key') → && t('key')
    content = re.sub(
        r"&&\s+\('([a-z]+\.[a-z.]+)'\)",
        r"&& t('\1')",
        content,
        flags=re.IGNORECASE
    )

    # Паттерн 4: && ("key") → && t("key")
    content = re.sub(
        r'&&\s+\("([a-z]+\.[a-z.]+)"\)',
        r'&& t("\1")',
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

    # Только .tsx файлы (компоненты)
    all_files = list(src_dir.rglob('*.tsx'))

    print("🔧 ВОССТАНОВЛЕНИЕ t() В JSX")
    print("=" * 60)

    fixed = 0
    for file_path in sorted(all_files):
        if restore_t_in_jsx(file_path):
            rel_path = file_path.relative_to(src_dir)
            print(f"✅ {rel_path}")
            fixed += 1

    print(f"\n{'='*60}")
    print(f"✅ Исправлено: {fixed} файлов")

if __name__ == '__main__':
    main()
