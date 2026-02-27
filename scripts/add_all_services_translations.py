#!/usr/bin/env python3
"""
Добавляет все переводы для страницы /services напрямую в JSON файлы.
Берёт значения из объекта labels и добавляет как ключи services.*
"""

import json
from pathlib import Path

# Все ключи и их переводы (из объекта labels в page.tsx)
TRANSLATIONS = {
    'ru': {
        'services.map.title': 'Карта мигранта',
        'services.map.description': 'МВД, ММЦ, медцентры',
        'services.exam.title': 'Экзамен по русскому',
        'services.exam.description': 'Тренажёр',
        'services.translator.title': 'Переводчик',
        'services.translator.description': 'Яндекс.Переводчик',
        'services.mosques.title': 'Карта мечетей',
        'services.mosques.description': 'Найти мечеть',
        'services.scenario.title': 'Тренажёр ситуаций',
        'services.scenario.description': 'Диалоги с ИИ',
    },
    'en': {
        'services.map.title': 'Migrant Map',
        'services.map.description': 'Police, Migration Centers, Clinics',
        'services.exam.title': 'Russian Language Exam',
        'services.exam.description': 'Practice Test',
        'services.translator.title': 'Translator',
        'services.translator.description': 'Yandex Translate',
        'services.mosques.title': 'Mosque Map',
        'services.mosques.description': 'Find a mosque',
        'services.scenario.title': 'Scenario Trainer',
        'services.scenario.description': 'AI Dialogues',
    },
    'uz': {
        'services.map.title': 'Migrant xaritasi',
        'services.map.description': 'IIV, MMM, Tibbiy markazlar',
        'services.exam.title': 'Rus tili imtihoni',
        'services.exam.description': 'Mashq testi',
        'services.translator.title': 'Tarjimon',
        'services.translator.description': 'Yandex Tarjimon',
        'services.mosques.title': 'Masjidlar xaritasi',
        'services.mosques.description': 'Masjid topish',
        'services.scenario.title': 'Vaziyat trenajyori',
        'services.scenario.description': 'AI bilan suhbatlar',
    },
}

def set_nested_key(data: dict, key_path: str, value: str):
    """Устанавливает значение по вложенному ключу 'services.map.title'."""
    parts = key_path.split('.')
    current = data

    for part in parts[:-1]:
        if part not in current:
            current[part] = {}
        current = current[part]

    current[parts[-1]] = value

def main():
    locales_dir = Path('apps/frontend/src/locales')

    for locale_code, translations in TRANSLATIONS.items():
        locale_file = locales_dir / f'{locale_code}.json'

        if not locale_file.exists():
            print(f"⚠️  {locale_file.name} не найден, пропускаем")
            continue

        data = json.load(open(locale_file, encoding='utf-8'))

        # Добавляем каждый ключ
        for key_path, value in translations.items():
            set_nested_key(data, key_path, value)

        # Записываем обратно
        with open(locale_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✅ Обновлено: {locale_file.name} (+{len(translations)} ключей)")

    print("\n✅ Все переводы добавлены!")

if __name__ == '__main__':
    main()
