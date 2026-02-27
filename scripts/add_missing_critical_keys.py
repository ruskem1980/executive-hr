#!/usr/bin/env python3
"""
Добавляет критические недостающие ключи переводов в JSON файлы.
Эти ключи нужны для dashboard и навигации.
"""

import json
from pathlib import Path

# Критические ключи которых не хватает
TRANSLATIONS = {
    'ru': {
        'common': {
            'status': 'Статус',
            'days': 'дней',
            'close': 'Закрыть',
            'error': 'Ошибка',
            'loading': 'Загрузка...',
            'back': 'Назад',
            'save': 'Сохранить',
            'cancel': 'Отмена',
            'tryAgain': 'Попробовать снова',
        },
        'dashboard': {
            'statusValues': {
                'legal': 'Легально',
                'risk': 'Риск',
                'illegal': 'Нелегально',
            },
            'daysRemaining': 'Осталось дней',
        },
        'legalStatus': {
            'nextDeadline': 'Следующий дедлайн',
            'expired': 'Истекло',
            'daysAgo': 'дней назад',
            'showQR': 'Показать QR-код',
            'verificationQR': 'QR для проверки',
            'fullName': 'ФИО',
            'birthDate': 'Дата рождения',
            'passport': 'Паспорт',
            'number': 'Номер',
            'validUntil': 'Действителен до',
            'migrationCard': 'Миграционная карта',
            'entry': 'Въезд',
            'registration': 'Регистрация',
            'address': 'Адрес',
            'addDocumentsHint': 'Добавьте документы в профиль для отображения в QR',
            'showToPolice': 'Покажите этот QR-код полиции или в МФЦ',
        },
        'risk': {
            'title': 'Риски',
            'overall': {
                'LOW': 'Низкий',
                'MEDIUM': 'Средний',
                'HIGH': 'Высокий',
            },
            'factors': {
                'stay_90_days': {
                    'title': 'Правило 90 дней',
                },
            },
            'daysLeft': 'Дней осталось',
            'action': {
                'planDeparture': 'Спланировать выезд',
                'renewRegistration': 'Продлить регистрацию',
            },
        },
        'nav': {
            'home': 'Главная',
            'faq': 'FAQ',
            'services': 'Услуги',
            'profile': 'Профиль',
            'sos': 'SOS',
            'main': 'Главная навигация',
        },
        'profile': {
            'qrCode': {
                'noData': 'Нет данных для QR-кода',
                'fillProfile': 'Заполнить профиль',
                'constructor': 'Выберите данные для QR',
                'fields': {
                    'personal': 'Личные данные',
                    'passport': 'Паспорт',
                    'migrationCard': 'Миграционная карта',
                    'registration': 'Регистрация',
                    'status': 'Статус',
                },
            },
        },
        'ui': {
            'riskindicator': {
                'низкий_риск': 'Низкий риск',
                'средний_риск': 'Средний риск',
                'высокий_риск': 'Высокий риск',
            },
        },
        'platform': {
            'tg': {
                'authLoading': 'Загружаем через Telegram...',
                'loadingProfile': 'Загружаем профиль...',
                'authError': 'Ошибка авторизации',
            },
            'loading': 'Загрузка...',
        },
    },
    'en': {
        'common': {
            'status': 'Status',
            'days': 'days',
            'close': 'Close',
            'error': 'Error',
            'loading': 'Loading...',
            'back': 'Back',
            'save': 'Save',
            'cancel': 'Cancel',
            'tryAgain': 'Try again',
        },
        'dashboard': {
            'statusValues': {
                'legal': 'Legal',
                'risk': 'Risk',
                'illegal': 'Illegal',
            },
            'daysRemaining': 'Days remaining',
        },
        'legalStatus': {
            'nextDeadline': 'Next deadline',
            'expired': 'Expired',
            'daysAgo': 'days ago',
            'showQR': 'Show QR code',
            'verificationQR': 'Verification QR',
            'fullName': 'Full Name',
            'birthDate': 'Birth Date',
            'passport': 'Passport',
            'number': 'Number',
            'validUntil': 'Valid until',
            'migrationCard': 'Migration Card',
            'entry': 'Entry',
            'registration': 'Registration',
            'address': 'Address',
            'addDocumentsHint': 'Add documents to your profile to display in QR',
            'showToPolice': 'Show this QR code to police or MFC',
        },
        'risk': {
            'title': 'Risks',
            'overall': {
                'LOW': 'Low',
                'MEDIUM': 'Medium',
                'HIGH': 'High',
            },
            'factors': {
                'stay_90_days': {
                    'title': '90 days rule',
                },
            },
            'daysLeft': 'Days left',
            'action': {
                'planDeparture': 'Plan departure',
                'renewRegistration': 'Renew registration',
            },
        },
        'nav': {
            'home': 'Home',
            'faq': 'FAQ',
            'services': 'Services',
            'profile': 'Profile',
            'sos': 'SOS',
            'main': 'Main navigation',
        },
        'profile': {
            'qrCode': {
                'noData': 'No data for QR code',
                'fillProfile': 'Fill profile',
                'constructor': 'Select data for QR',
                'fields': {
                    'personal': 'Personal data',
                    'passport': 'Passport',
                    'migrationCard': 'Migration Card',
                    'registration': 'Registration',
                    'status': 'Status',
                },
            },
        },
        'ui': {
            'riskindicator': {
                'низкий_риск': 'Low risk',
                'средний_риск': 'Medium risk',
                'высокий_риск': 'High risk',
            },
        },
        'platform': {
            'tg': {
                'authLoading': 'Loading via Telegram...',
                'loadingProfile': 'Loading profile...',
                'authError': 'Authentication error',
            },
            'loading': 'Loading...',
        },
    },
    'uz': {
        'common': {
            'status': 'Holat',
            'days': 'kunlar',
            'close': 'Yopish',
            'error': 'Xato',
            'loading': 'Yuklanmoqda...',
            'back': 'Orqaga',
            'save': 'Saqlash',
            'cancel': 'Bekor qilish',
            'tryAgain': 'Qayta urinib ko\'ring',
        },
        'dashboard': {
            'statusValues': {
                'legal': 'Qonuniy',
                'risk': 'Xavf',
                'illegal': 'Noqonuniy',
            },
            'daysRemaining': 'Qolgan kunlar',
        },
        'nav': {
            'home': 'Bosh sahifa',
            'faq': 'FAQ',
            'services': 'Xizmatlar',
            'profile': 'Profil',
            'sos': 'SOS',
            'main': 'Asosiy navigatsiya',
        },
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

    for locale_code, translations in TRANSLATIONS.items():
        locale_file = locales_dir / f'{locale_code}.json'

        if not locale_file.exists():
            print(f"⚠️  {locale_file.name} не найден, создаём")
            data = {}
        else:
            data = json.load(open(locale_file, encoding='utf-8'))

        # Глубокое слияние
        deep_merge(data, translations)

        # Записываем обратно
        with open(locale_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✅ Обновлено: {locale_file.name}")

    print("\n✅ Все критические ключи добавлены!")
    print("\n📝 Добавлено:")
    print("  - common: status, days, close, error, loading, back, save, cancel, tryAgain")
    print("  - dashboard: statusValues (legal, risk, illegal), daysRemaining")
    print("  - legalStatus: все ключи для карты статуса и QR")
    print("  - risk: title, overall, factors, daysLeft, action")
    print("  - nav: home, faq, services, profile, sos, main")
    print("  - profile.qrCode: все ключи для QR конструктора")
    print("  - ui.riskindicator: низкий/средний/высокий риск")
    print("  - platform: tg.authLoading, tg.loadingProfile, loading")

if __name__ == '__main__':
    main()
