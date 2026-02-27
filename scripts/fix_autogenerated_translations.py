#!/usr/bin/env python3
"""
Исправляет автогенерированные английские переводы на правильные русские.
"""

import json
from pathlib import Path

LOCALES_DIR = Path('apps/frontend/src/locales')

# Правильные переводы для известных проблемных ключей
FIXES = {
    'ru': {
        'knowledgeBase.title': 'База знаний',
        'knowledgeBase.questionsCount': 'вопросов',
        'knowledgeBase.categories.documents': 'Документы',
        'knowledgeBase.categories.emergency': 'Экстренная помощь',
        'knowledgeBase.categories.family': 'Семья',
        'knowledgeBase.categories.finance': 'Финансы',
        'knowledgeBase.categories.healthcare': 'Здоровье',
        'knowledgeBase.categories.housing': 'Жильё',
        'knowledgeBase.categories.integration': 'Интеграция',
        'knowledgeBase.categories.rights': 'Права',
        'db.types.паспорт': 'Паспорт',
        'db.types.миграционная_карта': 'Миграционная карта',
        'documents.types.migration_card': 'Миграционная карта',
        'profile.sections.personal': 'Личные данные',
        'profile.sections.documents': 'Документы',
        'profile.sections.work': 'Работа',
        'profile.sections.family': 'Семья',
    },
    'en': {
        'knowledgeBase.title': 'Knowledge Base',
        'knowledgeBase.questionsCount': 'questions',
        'knowledgeBase.categories.documents': 'Documents',
        'knowledgeBase.categories.emergency': 'Emergency',
        'knowledgeBase.categories.family': 'Family',
        'knowledgeBase.categories.finance': 'Finance',
        'knowledgeBase.categories.healthcare': 'Healthcare',
        'knowledgeBase.categories.housing': 'Housing',
        'knowledgeBase.categories.integration': 'Integration',
        'knowledgeBase.categories.rights': 'Rights',
        'db.types.паспорт': 'Passport',
        'db.types.миграционная_карта': 'Migration Card',
        'documents.types.migration_card': 'Migration Card',
        'profile.sections.personal': 'Personal Data',
        'profile.sections.documents': 'Documents',
        'profile.sections.work': 'Work',
        'profile.sections.family': 'Family',
    },
    'uz': {
        'knowledgeBase.title': 'Bilimlar bazasi',
        'knowledgeBase.questionsCount': 'savollar',
        'knowledgeBase.categories.documents': 'Hujjatlar',
        'knowledgeBase.categories.emergency': 'Favqulodda yordam',
        'knowledgeBase.categories.family': 'Oila',
        'knowledgeBase.categories.finance': 'Moliya',
        'knowledgeBase.categories.healthcare': 'Sog\'liqni saqlash',
        'knowledgeBase.categories.housing': 'Uy-joy',
        'knowledgeBase.categories.integration': 'Integratsiya',
        'knowledgeBase.categories.rights': 'Huquqlar',
        'db.types.паспорт': 'Pasport',
        'db.types.миграционная_карта': 'Migratsiya kartasi',
        'documents.types.migration_card': 'Migratsiya kartasi',
        'profile.sections.personal': 'Shaxsiy ma\'lumotlar',
        'profile.sections.documents': 'Hujjatlar',
        'profile.sections.work': 'Ish',
        'profile.sections.family': 'Oila',
    },
    'tg': {
        'knowledgeBase.title': 'Пойгоҳи дониш',
        'knowledgeBase.questionsCount': 'саволҳо',
        'knowledgeBase.categories.documents': 'Ҳуҷҷатҳо',
        'knowledgeBase.categories.emergency': 'Кӯмаки фаврӣ',
        'knowledgeBase.categories.family': 'Оила',
        'knowledgeBase.categories.finance': 'Молия',
        'knowledgeBase.categories.healthcare': 'Тандурустӣ',
        'knowledgeBase.categories.housing': 'Хонасозӣ',
        'knowledgeBase.categories.integration': 'Интегратсия',
        'knowledgeBase.categories.rights': 'Ҳуқуқҳо',
        'db.types.паспорт': 'Шиноснома',
        'db.types.миграционная_карта': 'Корти муҳоҷират',
        'documents.types.migration_card': 'Корти муҳоҷират',
        'profile.sections.personal': 'Маълумоти шахсӣ',
        'profile.sections.documents': 'Ҳуҷҷатҳо',
        'profile.sections.work': 'Кор',
        'profile.sections.family': 'Оила',
    },
    'ky': {
        'knowledgeBase.title': 'Билим базасы',
        'knowledgeBase.questionsCount': 'суроолор',
        'knowledgeBase.categories.documents': 'Документтер',
        'knowledgeBase.categories.emergency': 'Шашылыш жардам',
        'knowledgeBase.categories.family': 'Үй-бүлө',
        'knowledgeBase.categories.finance': 'Каржы',
        'knowledgeBase.categories.healthcare': 'Саламаттык',
        'knowledgeBase.categories.housing': 'Турак жай',
        'knowledgeBase.categories.integration': 'Интеграция',
        'knowledgeBase.categories.rights': 'Укуктар',
        'db.types.паспорт': 'Паспорт',
        'db.types.миграционная_карта': 'Миграция картасы',
        'documents.types.migration_card': 'Миграция картасы',
        'profile.sections.personal': 'Жеке маалымат',
        'profile.sections.documents': 'Документтер',
        'profile.sections.work': 'Жумуш',
        'profile.sections.family': 'Үй-бүлө',
    },
}

def get_nested_value(data: dict, key_path: str):
    """Получает значение по вложенному ключу."""
    parts = key_path.split('.')
    current = data
    for part in parts:
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current

def set_nested_value(data: dict, key_path: str, value):
    """Устанавливает значение по вложенному ключу."""
    parts = key_path.split('.')
    current = data

    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        elif not isinstance(current[part], dict):
            # Конфликт - пропускаем
            return False
        current = current[part]

    if not isinstance(current, dict):
        return False

    current[parts[-1]] = value
    return True

def main():
    print("🔧 ИСПРАВЛЕНИЕ АВТОГЕНЕРИРОВАННЫХ ПЕРЕВОДОВ")
    print("=" * 70)

    for locale in ['ru', 'en', 'uz', 'tg', 'ky']:
        if locale not in FIXES:
            continue

        locale_file = LOCALES_DIR / f'{locale}.json'
        if not locale_file.exists():
            print(f"⚠️  {locale}.json не найден")
            continue

        data = json.load(open(locale_file, encoding='utf-8'))

        fixed_count = 0
        for key_path, correct_value in FIXES[locale].items():
            current_value = get_nested_value(data, key_path)

            # Проверяем нужно ли исправление
            if current_value != correct_value:
                if set_nested_value(data, key_path, correct_value):
                    fixed_count += 1
                    print(f"  {locale.upper()}: {key_path}")
                    print(f"    ❌ {current_value}")
                    print(f"    ✅ {correct_value}")

        # Сохраняем
        with open(locale_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        if fixed_count > 0:
            print(f"\n  {locale.upper()}: исправлено {fixed_count} ключей ✓\n")
        else:
            print(f"  {locale.upper()}: все значения корректны ✓\n")

    print("=" * 70)
    print("✅ ИСПРАВЛЕНИЕ ЗАВЕРШЕНО!")

if __name__ == '__main__':
    main()
