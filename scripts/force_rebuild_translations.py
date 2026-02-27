#!/usr/bin/env python3
"""
ПРИНУДИТЕЛЬНО перезаписывает все JSON файлы переводов.
Это заставит Webpack/Turbopack перекомпилировать модули.
"""

import json
from pathlib import Path
import time

# Все недостающие ключи (собрано со скринов)
MISSING_KEYS = {
    'ru': {
        # Quick actions
        'dashboard': {
            'quickActions': 'Быстрые действия',
        },
        'nav': {
            'checklist': 'Чеклист',
            'checks': 'Проверки',
            'payments': 'Платежи',
            'calculators': 'Калькуляторы',
            'myDocuments': 'Мои документы',
            'housing': 'Жильё',
            'family': 'Семья',
        },
        'deadlines': {
            'title': 'Дедлайны',
        },
        'common': {
            'viewAll': 'Смотреть все',
            'daysShort': 'дн.',
        },
        'documents': {
            'myDocuments': 'Мои документы',
            'expires': 'Истекает',
            'freePlan': 'бесплатных',
        },
        'profile': {
            'title': 'Профиль',
            'tab': {
                'profile': 'Профиль',
                'documents': 'Документы',
            },
            'sections': {
                'personal': 'Личные данные',
                'documents': 'Документы',
                'work': 'Работа',
                'family': 'Семья',
            },
            'fields': {
                'fullNameLatin': 'ФИО латиницей',
                'citizenship': 'Гражданство',
            },
            'genders': {
                'male': 'Мужской',
                'female': 'Женский',
            },
            'saveChanges': 'Сохранить изменения',
        },
        'risk': {
            'factors': {
                'stay_90_days': {
                    'title': 'Правило 90 дней',
                },
            },
        },
    },
    'en': {
        'dashboard': {'quickActions': 'Quick Actions'},
        'nav': {
            'checklist': 'Checklist', 'checks': 'Checks', 'payments': 'Payments',
            'calculators': 'Calculators', 'myDocuments': 'My Documents',
            'housing': 'Housing', 'family': 'Family',
        },
        'deadlines': {'title': 'Deadlines'},
        'common': {'viewAll': 'View All', 'daysShort': 'd'},
        'documents': {'myDocuments': 'My Documents', 'expires': 'Expires', 'freePlan': 'free'},
        'profile': {
            'title': 'Profile',
            'tab': {'profile': 'Profile', 'documents': 'Documents'},
            'sections': {
                'personal': 'Personal', 'documents': 'Documents',
                'work': 'Work', 'family': 'Family',
            },
            'fields': {'fullNameLatin': 'Full Name (Latin)', 'citizenship': 'Citizenship'},
            'genders': {'male': 'Male', 'female': 'Female'},
            'saveChanges': 'Save Changes',
        },
    },
    'uz': {
        'dashboard': {'quickActions': 'Tez harakatlar'},
        'nav': {
            'checklist': 'Cheklista', 'checks': 'Tekshiruvlar', 'payments': 'To\'lovlar',
            'calculators': 'Kalkulyatorlar', 'myDocuments': 'Mening hujjatlarim',
            'housing': 'Uy-joy', 'family': 'Oila',
        },
        'deadlines': {'title': 'Muddatlar'},
        'common': {'viewAll': 'Hammasini ko\'rish', 'daysShort': 'k'},
        'documents': {'myDocuments': 'Mening hujjatlarim', 'expires': 'Amal qilish muddati', 'freePlan': 'bepul'},
    },
}

def deep_merge(target: dict, source: dict):
    """Глубокое слияние словарей."""
    for key, value in source.items():
        if key in target and isinstance(target[key], dict) and isinstance(value, dict):
            deep_merge(target[key], value)
        else:
            target[key] = value

def main():
    locales_dir = Path('apps/frontend/src/locales')

    print("🔄 ПРИНУДИТЕЛЬНОЕ ОБНОВЛЕНИЕ ПЕРЕВОДОВ")
    print("=" * 60)

    for locale_code, new_keys in MISSING_KEYS.items():
        locale_file = locales_dir / f'{locale_code}.json'

        if not locale_file.exists():
            print(f"⚠️  {locale_file.name} не найден, пропускаем")
            continue

        # Читаем существующие данные
        with open(locale_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Глубокое слияние
        deep_merge(data, new_keys)

        # ПЕРЕЗАПИСЫВАЕМ файл (это вызовет hot reload)
        with open(locale_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✅ {locale_file.name} перезаписан (+{len(new_keys)} разделов)")

        # Небольшая задержка чтобы Webpack заметил изменения
        time.sleep(0.1)

    print("\n" + "=" * 60)
    print("✅ Все файлы обновлены!")
    print("\n📝 Добавлено:")
    print("  - dashboard.quickActions")
    print("  - nav: checklist, checks, payments, calculators, myDocuments, housing, family")
    print("  - deadlines.title")
    print("  - common: viewAll, daysShort")
    print("  - documents: myDocuments, expires, freePlan")
    print("  - profile: title, tab, sections, fields, genders, saveChanges")
    print("  - risk.factors.stay_90_days.title")
    print("\n⚠️  Если голые ключи всё ещё видны:")
    print("  1. Подождите 2-3 секунды пока Turbopack перекомпилирует")
    print("  2. Сделайте hard refresh: Cmd+Shift+R")
    print("  3. Если не помогает - перезапустите dev сервер")

if __name__ == '__main__':
    main()
