#!/usr/bin/env python3
"""
Исправляет проблему с переводами на странице /services.

Проблема: в page.tsx есть локальный объект labels где значения на русском
это ключи переводов (типа '(main).page.сервисы'), которых НЕТ в ru.json.

Решение: заменить локальный объект labels и функцию t() на использование
глобального хука useTranslation() с прямыми строками.
"""

from pathlib import Path
import re

def fix_services_page():
    """Исправляет page.tsx - убирает локальный объект labels."""
    file_path = Path('apps/frontend/src/app/(main)/services/page.tsx')

    content = file_path.read_text(encoding='utf-8')

    # Заменяем локальную функцию t() на использование глобального хука
    # Находим строку: const { language } = useLanguageStore();
    # И добавляем после неё: const { t } = useTranslation();

    # Паттерн: const { language } = useLanguageStore();
    # Заменяем на: const { t, language } = useTranslation();
    content = re.sub(
        r'const\s+{\s*language\s*}\s*=\s*useLanguageStore\(\);',
        "const { t } = useTranslation();",
        content
    )

    # Удаляем локальную функцию t()
    # Паттерн: const t = (key: string): string => { ... };
    content = re.sub(
        r'const\s+t\s*=\s*\(key:\s*string\):\s*string\s*=>\s*{\s*return\s+labels\[key\]\?\.\[language\][^}]+};\s*',
        '',
        content,
        flags=re.DOTALL
    )

    # Удаляем весь объект labels (большой блок)
    # Находим от "const labels: Record<string" до закрывающей скобки
    content = re.sub(
        r'const\s+labels:\s*Record<string,\s*Record<Language,\s*string>>\s*=\s*{[^}]+};',
        '',
        content,
        flags=re.DOTALL | re.MULTILINE
    )

    # Теперь заменяем все вызовы t() с короткими ключами на прямые строки
    replacements = {
        "t('title')": "t('services.title')",
        "t('tipTitle')": "t('services.tipTitle')",
        "t('tipText')": "t('services.tipText')",
        "t('govApps')": "t('services.govApps')",
        "t('ruidDesc')": "t('services.ruidDesc')",
        "t('aminaDesc')": "t('services.aminaDesc')",
        "t('helpTitle')": "t('services.helpTitle')",
        "t('helpText')": "t('services.helpText')",
        "t('getHelp')": "t('services.getHelp')",
        "t('usefulLinks')": "t('services.usefulLinks')",
        "t('gosuslugi')": "t('services.gosuslugi')",
        "t('gosuslugiDesc')": "t('services.gosuslugiDesc')",
        "t('guvm')": "t('services.guvm')",
        "t('guvmDesc')": "t('services.guvmDesc')",
    }

    for old, new in replacements.items():
        content = content.replace(old, new)

    # Записываем обратно
    file_path.write_text(content, encoding='utf-8')
    print(f"✅ Исправлено: {file_path}")

def add_missing_translations():
    """Добавляет недостающие ключи переводов в ru.json."""
    import json

    locales_dir = Path('apps/frontend/src/locales')

    # Ключи которые нужно добавить
    new_keys = {
        'services': {
            'title': 'Услуги',
            'tipTitle': 'Совет дня',
            'tipText': 'Проверяйте базу запретов каждые 30 дней, чтобы избежать проблем при выезде из России.',
            'govApps': 'Гос. приложения для мигрантов',
            'ruidDesc': 'Заявление на въезд, проверка запретов, цифровой профиль',
            'aminaDesc': 'Миграционный учёт в Москве (обязательно с 01.09.2025)',
            'helpTitle': 'Помощь по установке',
            'helpText': 'Нужна помощь с установкой ruID или Amina? Наш ИИ-ассистент проведёт вас шаг за шагом.',
            'getHelp': 'Получить помощь',
            'usefulLinks': 'Полезные ссылки',
            'gosuslugi': 'Госуслуги',
            'gosuslugiDesc': 'Портал госуслуг РФ',
            'guvm': 'ГУВМ МВД',
            'guvmDesc': 'Миграционная служба',
        }
    }

    for locale_file in locales_dir.glob('*.json'):
        data = json.load(open(locale_file, encoding='utf-8'))

        # Добавляем или обновляем ключи
        if 'services' not in data:
            data['services'] = {}

        for key, value in new_keys['services'].items():
            if key not in data['services']:
                # Для русского используем значение, для остальных пока тоже русский
                # (потом можно перевести через auto_translate.py)
                data['services'][key] = value

        # Записываем обратно с красивым форматированием
        with open(locale_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✅ Обновлено: {locale_file.name}")

def main():
    print("🔧 ИСПРАВЛЕНИЕ ПЕРЕВОДОВ НА СТРАНИЦЕ /services")
    print("=" * 60)

    # Шаг 1: Добавляем недостающие ключи в JSON
    print("\n1️⃣ Добавление ключей переводов...")
    add_missing_translations()

    # Шаг 2: Исправляем код страницы
    print("\n2️⃣ Исправление кода page.tsx...")
    fix_services_page()

    print("\n" + "=" * 60)
    print("✅ Готово! Перезагрузите страницу в браузере.")

if __name__ == '__main__':
    main()
