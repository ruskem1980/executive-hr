#!/usr/bin/env python3
"""
Универсальный скрипт исправления ВСЕХ переводов во ВСЕХ компонентах frontend.

Два типа ошибок (повторяющийся паттерн во всём проекте):

  1. i18n-КЛЮЧИ ВМЕСТО ТЕКСТА:
     ru: '(main).page.рейтинг_арендодателей'  →  ru: 'Рейтинг арендодателей'
     tg: '(main).page.рейтинги_соибони_хона'  →  tg: 'Рейтинги соибони хона'
     ky: '(main).page.й_ээлеринин_рейтинги'   →  ky: 'Й ээлеринин рейтинги'

  2. HARDCODED JSX СТРОКИ (не вызвана функция перевода):
     {'subtitle'}  →  {t('subtitle')}
     {'back'}      →  {t('back')}
     {'search'}    →  {t('search')}
     {'hint'}      →  {t('hint')}

Использование:
  python3 scripts/fix_all_translations_universal.py              # Исправить всё
  python3 scripts/fix_all_translations_universal.py --dry-run    # Только отчёт
  python3 scripts/fix_all_translations_universal.py --verbose    # С деталями каждого исправления
"""

import re
import os
import sys
import glob

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND_SRC = os.path.join(BASE, 'apps', 'frontend', 'src')

DRY_RUN = '--dry-run' in sys.argv
VERBOSE = '--verbose' in sys.argv

# ============================================================
# ПАТТЕРН 1: i18n ключи как значения строк
# ============================================================
# Формат: 'prefix.component.кириллический_текст_с_подчёркиваниями'
# Примеры:
#   '(main).page.рейтинг_арендодателей'
#   'work.jobsearchhub.строительство'
#   'housing.contractaicheck.проверка'
#   'services.stayCalculator.калькулятор'
#
# НЕ ловит:
#   'Рейтинг арендодателей' (нет точек — уже правильный текст)
#   'https://example.com' (нет кириллицы после точек)
#   'Загрузка...' (нет namespace-формата)

I18N_KEY_RE = re.compile(
    r"'[a-z()]+\.[a-z0-9_]+\."    # prefix.component.
    r"[а-яёА-ЯЁ]"                  # минимум 1 кириллический символ
    r"[а-яёА-ЯЁ_a-zA-Z0-9]*'"    # остаток текста + закрывающая кавычка
)

# Также поддерживаем двойные кавычки (на случай если где-то используются)
I18N_KEY_RE_DQ = re.compile(
    r'"[a-z()]+\.[a-z0-9_]+\.'
    r'[а-яёА-ЯЁ]'
    r'[а-яёА-ЯЁ_a-zA-Z0-9]*"'
)


def key_to_text(key_with_quotes):
    """Конвертирует i18n ключ в текст для отображения.

    '(main).page.рейтинг_арендодателей' → Рейтинг арендодателей
    'work.jobsearchhub.москва'           → Москва
    '(main).page.бор_мешавад'            → Бор мешавад
    """
    quote_char = key_with_quotes[0]
    inner = key_with_quotes[1:-1]  # убираем кавычки

    # Получаем текстовую часть после последней точки
    text_part = inner.rsplit('.', 1)[1]

    # Заменяем подчёркивания на пробелы
    text = text_part.replace('_', ' ')

    # Капитализация первой буквы
    if text:
        text = text[0].upper() + text[1:]

    return f"{quote_char}{text}{quote_char}"


# ============================================================
# ПАТТЕРН 2: Hardcoded строки в JSX
# ============================================================
# {'keyword'} где keyword — ключ из labels/translations
# Должно быть: {t('keyword')} или {tr('keyword')}

def detect_translation_func(content):
    """Определяет имя функции перевода в файле (t или tr)."""
    # Ищем const tr = (key...) => ... (более специфичный)
    if re.search(r'const\s+tr\s*=\s*\(', content):
        return 'tr'
    # Ищем const t = (key...) => ...
    if re.search(r'const\s+t\s*=\s*\(', content):
        return 't'
    return None


def extract_label_keys(content):
    """Извлекает все ключи переводов из объектов labels/translations.

    Ищет паттерн:
      keyName: {
        ru: '...', en: '...', ...
      },
    или:
      keyName: { ru: '...', en: '...', ... },
    """
    keys = set()

    # Паттерн: "  keyName: {" с последующими языковыми ключами
    for m in re.finditer(r'^\s{2,6}(\w+):\s*\{', content, re.MULTILINE):
        key = m.group(1)
        pos = m.end()

        # Проверяем что внутри есть языковые ключи (ru: или en:)
        after = content[pos:pos+200]
        if re.search(r'\b(?:ru|en)\s*:', after):
            # Исключаем сами языковые ключи и служебные слова
            if key not in ('ru', 'en', 'uz', 'tg', 'ky',
                          'labels', 'translations', 'Record', 'Language',
                          'string', 'name', 'description', 'buildUrl'):
                keys.add(key)

    return keys


def fix_file(filepath):
    """Исправляет все проблемы с переводами в одном файле.

    Возвращает (key_fixes, jsx_fixes, details).
    """
    with open(filepath, 'r', encoding='utf-8') as f:
        original = f.read()

    content = original
    key_fixes = 0
    jsx_fixes = 0
    details = []

    # ── ШАГ 1: Заменяем i18n ключи на текст ──
    def replace_key(match):
        nonlocal key_fixes
        old = match.group(0)
        new = key_to_text(old)
        if old != new:
            key_fixes += 1
            if VERBOSE:
                details.append(f"    KEY: {old} → {new}")
        return new

    content = I18N_KEY_RE.sub(replace_key, content)
    content = I18N_KEY_RE_DQ.sub(replace_key, content)

    # ── ШАГ 2: Заменяем hardcoded JSX строки ──
    tr_func = detect_translation_func(content)
    if tr_func:
        label_keys = extract_label_keys(content)

        for key in sorted(label_keys):
            # Ищем {'key'} в JSX
            old_pattern = "{'" + key + "'}"
            new_pattern = "{" + tr_func + "('" + key + "')}"

            occurrences = content.count(old_pattern)
            if occurrences > 0:
                content = content.replace(old_pattern, new_pattern)
                jsx_fixes += occurrences
                if VERBOSE:
                    details.append(f"    JSX: {{'{key}'}} → {{{tr_func}('{key}')}} (x{occurrences})")

    # ── Запись ──
    if content != original:
        if not DRY_RUN:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(content)
        return key_fixes, jsx_fixes, details

    return 0, 0, []


def main():
    print("=" * 70)
    print("  УНИВЕРСАЛЬНОЕ ИСПРАВЛЕНИЕ ПЕРЕВОДОВ")
    print("  Все компоненты frontend")
    if DRY_RUN:
        print("  РЕЖИМ: Только отчёт (--dry-run)")
    print("=" * 70)

    # Собираем все .tsx и .ts файлы
    files = []
    for ext in ('**/*.tsx', '**/*.ts'):
        files.extend(glob.glob(os.path.join(FRONTEND_SRC, ext), recursive=True))

    # Исключаем node_modules и .next
    files = [f for f in files if 'node_modules' not in f and '.next' not in f]
    files.sort()

    print(f"\n  Сканирование {len(files)} файлов...\n")

    total_keys = 0
    total_jsx = 0
    fixed_files = 0
    file_results = []

    for filepath in files:
        key_fixes, jsx_fixes, details = fix_file(filepath)

        if key_fixes > 0 or jsx_fixes > 0:
            fixed_files += 1
            total_keys += key_fixes
            total_jsx += jsx_fixes
            rel = os.path.relpath(filepath, BASE)
            file_results.append((rel, key_fixes, jsx_fixes, details))

    # ── Отчёт ──
    print(f"{'─' * 70}")
    print(f"  {'Файл':<60} {'Ключи':>5} {'JSX':>5}")
    print(f"{'─' * 70}")

    for rel, kf, jf, details in file_results:
        # Укорачиваем путь для читаемости
        short = rel.replace('apps/frontend/src/', '')
        if len(short) > 58:
            short = '...' + short[-55:]
        print(f"  {short:<60} {kf:>5} {jf:>5}")
        if VERBOSE and details:
            for d in details:
                print(d)

    print(f"{'─' * 70}")
    print(f"  {'ИТОГО':<60} {total_keys:>5} {total_jsx:>5}")
    print(f"{'=' * 70}")
    print(f"\n  Файлов исправлено:  {fixed_files}")
    print(f"  Ключей → текст:    {total_keys}")
    print(f"  JSX hardcoded:      {total_jsx}")
    print(f"  ВСЕГО исправлений:  {total_keys + total_jsx}")

    if DRY_RUN:
        print(f"\n  Для применения запустите без --dry-run:")
        print(f"  python3 scripts/fix_all_translations_universal.py")
    else:
        print(f"\n  Все исправления применены.")

    print(f"{'=' * 70}")

    return total_keys + total_jsx


if __name__ == '__main__':
    total = main()
    sys.exit(0 if total >= 0 else 1)
