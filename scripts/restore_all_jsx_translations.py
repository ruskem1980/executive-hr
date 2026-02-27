#!/usr/bin/env python3
"""
Восстанавливает t() для ВСЕХ ключей переводов в JSX.
Находит паттерны {'key'} и {("key")} и заменяет на {t('key')}.

Ключ перевода определяется по:
- Содержит точки: key.subkey
- ИЛИ camelCase: tipTitle, helpText
- ИЛИ начинается со скобки: (main).page.xxx
- ИЛИ содержит подчёркивания: migration_card
- ИЛИ русские символы с подчёркиваниями
"""

import re
from pathlib import Path

def is_translation_key(s: str) -> bool:
    """Проверяет, является ли строка ключом перевода."""
    # Содержит точки
    if '.' in s:
        return True
    # Начинается со скобки (namespace)
    if s.startswith('('):
        return True
    # Содержит подчёркивания
    if '_' in s:
        return True
    # camelCase паттерн (tipTitle, helpText, etc)
    # Минимум 2 заглавные буквы внутри слова
    if re.search(r'[a-z][A-Z]', s):
        return True
    # Короткие служебные ключи (title, text, etc)
    if s in ['title', 'text', 'name', 'description', 'label', 'placeholder',
             'error', 'success', 'warning', 'info', 'map', 'exam', 'translator',
             'tipTitle', 'tipText', 'helpTitle', 'helpText', 'getHelp',
             'usefulLinks', 'govApps', 'gosuslugi', 'guvm']:
        return True
    return False

def fix_jsx_translations(file_path: Path) -> bool:
    """Восстанавливает t() в JSX. Возвращает True если были изменения."""
    try:
        content = file_path.read_text(encoding='utf-8')
    except:
        return False

    original = content

    # Паттерн 1: {'any-key'} → {t('any-key')}
    # Но только если это похоже на ключ перевода
    def replace_single_quote(match):
        key = match.group(1)
        if is_translation_key(key):
            return f"{{t('{key}')}}"
        return match.group(0)

    content = re.sub(
        r"\{'([^']+)'\}",
        replace_single_quote,
        content
    )

    # Паттерн 2: {"any-key"} → {t("any-key")}
    def replace_double_quote(match):
        key = match.group(1)
        if is_translation_key(key):
            return f'{{t("{key}")}}'
        return match.group(0)

    content = re.sub(
        r'\{"([^"]+)"\}',
        replace_double_quote,
        content
    )

    # Паттерн 3: {('key')} → {t('key')}
    def replace_paren_single(match):
        key = match.group(1)
        if is_translation_key(key):
            return f"{{t('{key}')}}"
        return match.group(0)

    content = re.sub(
        r"\{\('([^']+)'\)\}",
        replace_paren_single,
        content
    )

    # Паттерн 4: {("key")} → {t("key")}
    def replace_paren_double(match):
        key = match.group(1)
        if is_translation_key(key):
            return f'{{t("{key}")}}'
        return match.group(0)

    content = re.sub(
        r'\{\("([^"]+)"\)\}',
        replace_paren_double,
        content
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

    print("🔧 ВОССТАНОВЛЕНИЕ t() ДЛЯ ВСЕХ КЛЮЧЕЙ В JSX")
    print("=" * 60)

    fixed = 0
    for file_path in sorted(all_files):
        if fix_jsx_translations(file_path):
            rel_path = file_path.relative_to(src_dir)
            print(f"✅ {rel_path}")
            fixed += 1

    print(f"\n{'='*60}")
    print(f"✅ Исправлено: {fixed} файлов")

if __name__ == '__main__':
    main()
