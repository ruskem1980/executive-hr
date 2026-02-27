#!/usr/bin/env python3
"""
COMPREHENSIVE I18N SCANNER
Автоматически находит ВСЕ t('key') в коде, сравнивает с JSON, добавляет недостающие.
"""

import json
import re
from pathlib import Path
from typing import Dict, Set, List
from collections import defaultdict

# Пути
PROJECT_ROOT = Path('apps/frontend/src')
LOCALES_DIR = Path('apps/frontend/src/locales')
LANGUAGES = ['ru', 'en', 'uz', 'tg', 'ky']

# Базовые переводы для каждого языка (для автогенерации)
AUTO_TRANSLATIONS = {
    'en': {
        'title': 'Title', 'description': 'Description', 'name': 'Name',
        'status': 'Status', 'date': 'Date', 'address': 'Address',
        'phone': 'Phone', 'email': 'Email', 'city': 'City',
        'country': 'Country', 'submit': 'Submit', 'cancel': 'Cancel',
        'save': 'Save', 'edit': 'Edit', 'delete': 'Delete',
        'close': 'Close', 'open': 'Open', 'add': 'Add',
        'remove': 'Remove', 'update': 'Update', 'create': 'Create',
        'loading': 'Loading...', 'error': 'Error', 'success': 'Success',
    },
    'uz': {
        'title': 'Sarlavha', 'description': 'Tavsif', 'name': 'Ism',
        'status': 'Holat', 'date': 'Sana', 'address': 'Manzil',
        'phone': 'Telefon', 'email': 'Email', 'city': 'Shahar',
        'country': 'Mamlakat', 'submit': 'Yuborish', 'cancel': 'Bekor qilish',
        'save': 'Saqlash', 'edit': 'Tahrirlash', 'delete': "O'chirish",
        'close': 'Yopish', 'open': 'Ochish', 'add': "Qo'shish",
        'remove': 'Olib tashlash', 'update': 'Yangilash', 'create': 'Yaratish',
        'loading': 'Yuklanmoqda...', 'error': 'Xato', 'success': 'Muvaffaqiyat',
    },
    'tg': {
        'title': 'Сарлавҳа', 'description': 'Тавсиф', 'name': 'Ном',
        'status': 'Вазъият', 'date': 'Сана', 'address': 'Суроға',
        'phone': 'Телефон', 'email': 'Почта', 'city': 'Шаҳр',
        'country': 'Кишвар', 'submit': 'Фиристодан', 'cancel': 'Бекор кардан',
        'save': 'Захира кардан', 'edit': 'Таҳрир', 'delete': 'Нест кардан',
        'close': 'Пӯшидан', 'open': 'Кушодан', 'add': 'Илова кардан',
        'remove': 'Хориҷ кардан', 'update': 'Навсозӣ', 'create': 'Эҷод кардан',
        'loading': 'Бор мешавад...', 'error': 'Хато', 'success': 'Муваффақият',
    },
    'ky': {
        'title': 'Аталышы', 'description': 'Сүрөттөмө', 'name': 'Аты',
        'status': 'Статус', 'date': 'Күнү', 'address': 'Дареги',
        'phone': 'Телефон', 'email': 'Почта', 'city': 'Шаар',
        'country': 'Өлкө', 'submit': 'Жөнөтүү', 'cancel': 'Жокко чыгаруу',
        'save': 'Сактоо', 'edit': 'Оңдоо', 'delete': 'Өчүрүү',
        'close': 'Жабуу', 'open': 'Ачуу', 'add': 'Кошуу',
        'remove': 'Алып салуу', 'update': 'Жаңыртуу', 'create': 'Түзүү',
        'loading': 'Жүктөлүүдө...', 'error': 'Ката', 'success': 'Ийгилик',
    },
}

def find_all_translation_keys() -> Set[str]:
    """Находит ВСЕ ключи t('key') в коде."""
    keys = set()

    # Паттерны для поиска t('key') и t("key")
    patterns = [
        r't\([\'"]([^\'"]+)[\'"]\)',  # t('key') или t("key")
        r't\([\'"]([^\'"]+)[\'"],',   # t('key',
        r'titleKey:\s*[\'"]([^\'"]+)[\'"]',  # titleKey: 'key'
        r'descKey:\s*[\'"]([^\'"]+)[\'"]',   # descKey: 'key'
        r'labelKey:\s*[\'"]([^\'"]+)[\'"]',  # labelKey: 'key'
    ]

    compiled_patterns = [re.compile(p) for p in patterns]

    # Сканируем все .tsx и .ts файлы
    for file_path in PROJECT_ROOT.rglob('*.tsx'):
        try:
            content = file_path.read_text(encoding='utf-8')
            for pattern in compiled_patterns:
                matches = pattern.findall(content)
                keys.update(matches)
        except Exception as e:
            print(f"⚠️  Ошибка чтения {file_path}: {e}")

    for file_path in PROJECT_ROOT.rglob('*.ts'):
        if file_path.name.endswith('.test.ts') or file_path.name.endswith('.spec.ts'):
            continue
        try:
            content = file_path.read_text(encoding='utf-8')
            for pattern in compiled_patterns:
                matches = pattern.findall(content)
                keys.update(matches)
        except Exception as e:
            print(f"⚠️  Ошибка чтения {file_path}: {e}")

    return keys

def load_json_keys(locale: str) -> Set[str]:
    """Загружает все ключи из JSON файла (включая вложенные)."""
    locale_file = LOCALES_DIR / f'{locale}.json'

    if not locale_file.exists():
        return set()

    data = json.load(open(locale_file, encoding='utf-8'))

    def extract_keys(obj, prefix=''):
        """Рекурсивно извлекает все ключи включая вложенные."""
        keys = set()
        for key, value in obj.items():
            full_key = f'{prefix}.{key}' if prefix else key
            keys.add(full_key)
            if isinstance(value, dict):
                keys.update(extract_keys(value, full_key))
        return keys

    return extract_keys(data)

def get_nested_value(data: dict, key_path: str):
    """Получает значение по вложенному ключу 'common.status'."""
    parts = key_path.split('.')
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current

def set_nested_value(data: dict, key_path: str, value):
    """Устанавливает значение по вложенному ключу 'common.status'."""
    parts = key_path.split('.')
    current = data

    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        elif not isinstance(current[part], dict):
            # Если на этом пути уже есть строка/примитив - пропускаем этот ключ
            print(f"      ⚠️  Конфликт: {key_path} (путь занят примитивом)")
            return
        current = current[part]

    # Финальная проверка перед установкой
    if not isinstance(current, dict):
        print(f"      ⚠️  Конфликт: {key_path} (текущий узел не dict)")
        return

    current[parts[-1]] = value

def auto_translate_key(key: str, locale: str, ru_value: str) -> str:
    """Автоматический перевод ключа на основе паттернов."""
    # Последняя часть ключа
    last_part = key.split('.')[-1]

    # Проверяем словарь автопереводов
    if last_part.lower() in AUTO_TRANSLATIONS.get(locale, {}):
        return AUTO_TRANSLATIONS[locale][last_part.lower()]

    # Если это системный/кириллический ключ - оставляем как есть
    if any(ord(c) > 127 for c in last_part):
        return ru_value

    # По умолчанию - транслитерация последней части
    return last_part.replace('_', ' ').replace('-', ' ').title()

def main():
    print("🔍 COMPREHENSIVE I18N SCANNER")
    print("=" * 70)

    # Шаг 1: Находим все ключи в коде
    print("\n📝 Шаг 1: Сканирование кода...")
    code_keys = find_all_translation_keys()
    print(f"   Найдено уникальных ключей: {len(code_keys)}")

    # Шаг 2: Для каждого языка проверяем недостающие ключи
    print("\n📊 Шаг 2: Анализ по языкам...")

    missing_by_locale = {}

    for locale in LANGUAGES:
        json_keys = load_json_keys(locale)
        missing = code_keys - json_keys
        missing_by_locale[locale] = missing

        print(f"\n   {locale.upper()}:")
        print(f"   - В JSON: {len(json_keys)} ключей")
        print(f"   - В коде: {len(code_keys)} ключей")
        print(f"   - Недостаёт: {len(missing)} ключей")

    # Шаг 3: Добавляем недостающие ключи
    print("\n✍️  Шаг 3: Добавление недостающих ключей...")

    for locale in LANGUAGES:
        missing = missing_by_locale[locale]

        if not missing:
            print(f"   {locale.upper()}: Все ключи присутствуют ✓")
            continue

        locale_file = LOCALES_DIR / f'{locale}.json'
        data = json.load(open(locale_file, encoding='utf-8'))

        # Загружаем ru.json для reference
        ru_data = json.load(open(LOCALES_DIR / 'ru.json', encoding='utf-8'))

        added_count = 0
        for key in sorted(missing):
            # Пытаемся взять значение из ru.json
            ru_value = get_nested_value(ru_data, key)

            if ru_value and locale == 'ru':
                # Если это ru.json и значение есть - пропускаем (не должно случиться)
                continue

            # Генерируем перевод
            if locale == 'ru':
                # Для русского - используем последнюю часть ключа как fallback
                value = key.split('.')[-1].replace('_', ' ').replace('-', ' ').title()
            elif ru_value and isinstance(ru_value, str):
                # Если есть русское значение - используем автоперевод
                value = auto_translate_key(key, locale, ru_value)
            else:
                # Иначе - транслитерация
                value = key.split('.')[-1].replace('_', ' ').replace('-', ' ').title()

            set_nested_value(data, key, value)
            added_count += 1

        # Записываем обратно
        with open(locale_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"   {locale.upper()}: +{added_count} ключей добавлено ✓")

    print("\n" + "=" * 70)
    print("✅ СКАНИРОВАНИЕ ЗАВЕРШЕНО!")

    # Выводим топ-10 недостающих ключей (для информации)
    all_missing = set()
    for missing in missing_by_locale.values():
        all_missing.update(missing)

    if all_missing:
        print("\n📋 Примеры добавленных ключей:")
        for i, key in enumerate(sorted(all_missing)[:10], 1):
            print(f"   {i}. {key}")
        if len(all_missing) > 10:
            print(f"   ... и ещё {len(all_missing) - 10} ключей")

    print("\n💡 Рекомендации:")
    print("   1. Проверьте добавленные переводы в JSON файлах")
    print("   2. Замените автогенерированные переводы на правильные")
    print("   3. Перезапустите dev сервер для применения изменений")

if __name__ == '__main__':
    main()
