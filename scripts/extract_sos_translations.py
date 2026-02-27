#!/usr/bin/env python3
"""
Скрипт для извлечения переводов из emergency-contacts.ts и добавления в языковые файлы.
Автоматически создаёт структуру sos секции с переводами для всех языков.
"""
import json
import re
from pathlib import Path

# Пути
PROJECT_ROOT = Path(__file__).parent.parent
DATA_FILE = PROJECT_ROOT / "apps" / "frontend" / "src" / "data" / "emergency-contacts.ts"
LOCALES_DIR = PROJECT_ROOT / "apps" / "frontend" / "src" / "locales"

# Секция SOS для переводов
SOS_TRANSLATIONS = {
    "sos": {
        "title": {
            "ru": "SOS Помощь",
            "en": "SOS Help",
            "uz": "SOS Yordam",
            "tg": "Ёрии SOS",
            "ky": "SOS Жардам"
        },
        "subtitle": {
            "ru": "Экстренные контакты и инструкции",
            "en": "Emergency contacts and instructions",
            "uz": "Favqulodda kontaktlar va ko'rsatmalar",
            "tg": "Тамосҳои фавқулодда ва дастурҳо",
            "ky": "Шашылыш байланыштар жана нускамалар"
        },
        "emergencyServices": {
            "title": {
                "ru": "Экстренные службы",
                "en": "Emergency Services",
                "uz": "Favqulodda xizmatlar",
                "tg": "Хизматҳои фавқулодда",
                "ky": "Шашылыш кызматтары"
            },
            "callNote": {
                "ru": "Нажмите для звонка. Бесплатно с любого телефона.",
                "en": "Tap to call. Free from any phone.",
                "uz": "Qo'ng'iroq qilish uchun bosing. Har qanday telefondan bepul.",
                "tg": "Барои занг задан пахш кунед. Аз ҳар як телефон ройгон.",
                "ky": "Чалуу үчүн басыңыз. Кандай болсо да телефондон акысыз."
            },
            "emergency": {
                "name": {
                    "ru": "Единый номер",
                    "en": "Unified Number",
                    "uz": "Yagona raqam",
                    "tg": "Рақами ягона",
                    "ky": "Бирдиктүү номер"
                },
                "description": {
                    "ru": "Все экстренные службы",
                    "en": "All emergency services",
                    "uz": "Barcha favqulodda xizmatlar",
                    "tg": "Ҳамаи хизматҳои фавқулодда",
                    "ky": "Бардык шашылыш кызматтары"
                }
            },
            "police": {
                "name": {
                    "ru": "Полиция",
                    "en": "Police",
                    "uz": "Politsiya",
                    "tg": "Полиция",
                    "ky": "Полиция"
                },
                "description": {
                    "ru": "Охрана правопорядка",
                    "en": "Law enforcement",
                    "uz": "Qonun-tartibotni saqlash",
                    "tg": "Ҳифзи қонун ва тартибот",
                    "ky": "Укук коргоо органдары"
                }
            },
            "ambulance": {
                "name": {
                    "ru": "Скорая помощь",
                    "en": "Ambulance",
                    "uz": "Tez yordam",
                    "tg": "Ёрии тез",
                    "ky": "Тез жардам"
                },
                "description": {
                    "ru": "Медицинская помощь",
                    "en": "Medical assistance",
                    "uz": "Tibbiy yordam",
                    "tg": "Ёрии тиббӣ",
                    "ky": "Медициналык жардам"
                }
            },
            "fire": {
                "name": {
                    "ru": "Пожарная",
                    "en": "Fire Department",
                    "uz": "Yong'in xizmati",
                    "tg": "Хизмати оташнишонӣ",
                    "ky": "Өрт өчүрүү кызматы"
                },
                "description": {
                    "ru": "Пожарная служба",
                    "en": "Fire service",
                    "uz": "Yong'in xizmati",
                    "tg": "Хизмати оташнишонӣ",
                    "ky": "Өрт өчүрүү кызматы"
                }
            }
        },
        "hotlines": {
            "title": {
                "ru": "Горячие линии",
                "en": "Hotlines",
                "uz": "Issiq liniyalar",
                "tg": "Хатҳои гарм",
                "ky": "Ысык линиялар"
            },
            "freeRussia": {
                "ru": "Бесплатно по России",
                "en": "Free in Russia",
                "uz": "Rossiyada bepul",
                "tg": "Дар Русия ройгон",
                "ky": "Россияда акысыз"
            },
            "hours247": {
                "ru": "24/7",
                "en": "24/7",
                "uz": "24/7",
                "tg": "24/7",
                "ky": "24/7"
            },
            "hoursWeekdays": {
                "ru": "Пн-Пт 9:00-18:00",
                "en": "Mon-Fri 9:00-18:00",
                "uz": "Dush-Jum 9:00-18:00",
                "tg": "Душ-Ҷум 9:00-18:00",
                "ky": "Дүй-Жум 9:00-18:00"
            }
        },
        "embassies": {
            "title": {
                "ru": "Посольства",
                "en": "Embassies",
                "uz": "Elchixonalar",
                "tg": "Сафоратхо",
                "ky": "Элчиликтер"
            },
            "yourCountry": {
                "ru": "Ваша страна",
                "en": "Your country",
                "uz": "Sizning mamlakatingiz",
                "tg": "Кишвари шумо",
                "ky": "Сиздин өлкөңүз"
            },
            "showAll": {
                "ru": "Показать все ({count}) посольств",
                "en": "Show all ({count}) embassies",
                "uz": "Barcha ({count}) elchixonalarni ko'rsatish",
                "tg": "Ҳамаи ({count}) сафоратхоро нишон диҳед",
                "ky": "Бардык ({count}) элчиликти көрсөтүү"
            }
        },
        "guides": {
            "title": {
                "ru": "Что делать, если...",
                "en": "What to do if...",
                "uz": "Nima qilish kerak, agar...",
                "tg": "Чӣ кор кардан лозим, агар...",
                "ky": "Эмне кылуу керек, эгерде..."
            },
            "policeStop": {
                "title": {
                    "ru": "Задержала полиция",
                    "en": "Detained by police",
                    "uz": "Politsiya ushlab qoldi",
                    "tg": "Полиция бозхост кард",
                    "ky": "Полиция кармады"
                },
                "steps": [
                    {
                        "ru": "Сохраняйте спокойствие, не спорьте",
                        "en": "Stay calm, don't argue",
                        "uz": "Xotirjam bo'ling, bahslashmang",
                        "tg": "Ором бошед, бањс накунед",
                        "ky": "Тынч болуңуз, талашпаңыз"
                    },
                    {
                        "ru": "Попросите показать удостоверение сотрудника",
                        "en": "Ask to see officer's ID",
                        "uz": "Xodimning guvohnomasini ko'rsatishni so'rang",
                        "tg": "Шиносномаи кормандро нишон додан хоҳед",
                        "ky": "Кызматкердин күбөлүгүн көрсөтүүнү сураңыз"
                    },
                    {
                        "ru": "Запишите или запомните ФИО и звание",
                        "en": "Write down or remember name and rank",
                        "uz": "F.I.O. va unvonini yozing yoki eslab qoling",
                        "tg": "Ном ва унвонро нависед ё дар хотир доред",
                        "ky": "Аты-жөнүн жана даражасын жазып алыңыз же эстеп калыңыз"
                    },
                    {
                        "ru": "Узнайте причину задержания",
                        "en": "Find out the reason for detention",
                        "uz": "Hibsga olish sababini bilib oling",
                        "tg": "Сабаби бозхостро донед",
                        "ky": "Кармоонун себебин билип алыңыз"
                    },
                    {
                        "ru": "Вы имеете право на звонок - позвоните в посольство",
                        "en": "You have the right to a phone call - call your embassy",
                        "uz": "Siz qo'ng'iroq qilish huquqiga egasiz - elchixonaga qo'ng'iroq qiling",
                        "tg": "Шумо ҳуқуқи занг задан доред - ба сафорат занг занед",
                        "ky": "Сизде чалуу укугу бар - элчилигиңизге чалыңыз"
                    },
                    {
                        "ru": "Не подписывайте документы без переводчика",
                        "en": "Don't sign documents without a translator",
                        "uz": "Tarjimon bo'lmaganida hujjatlarga imzo qo'ymang",
                        "tg": "Бе тарчумон ба ҳуҷҷатҳо имзо нагузоред",
                        "ky": "Котормочусуз документтерге кол коюшпаңыз"
                    },
                    {
                        "ru": "Требуйте протокол задержания",
                        "en": "Demand a detention protocol",
                        "uz": "Hibsga olish bayonnomasini talab qiling",
                        "tg": "Протоколи бозхостро талаб кунед",
                        "ky": "Кармоо протоколун талап кылыңыз"
                    }
                ]
            }
        }
    }
}

def update_locales():
    """Обновляет все языковые файлы с переводами SOS секции."""
    languages = ['ru', 'en', 'uz', 'tg', 'ky']

    print("🔄 Добавление переводов SOS секции...")
    print()

    for lang in languages:
        file_path = LOCALES_DIR / f"{lang}.json"

        if not file_path.exists():
            print(f"❌ Файл {file_path} не найден")
            continue

        # Читаем существующий файл
        with open(file_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Рекурсивно добавляем переводы
        def add_translations(source, target, lang):
            for key, value in source.items():
                if isinstance(value, dict):
                    # Проверяем, есть ли хотя бы один перевод (dict с языковыми ключами)
                    has_translation = any(k in ['ru', 'en', 'uz', 'tg', 'ky'] for k in value.keys())
                    if has_translation:
                        # Это конечная точка перевода
                        target[key] = value.get(lang, value.get('en', ''))
                    else:
                        # Это вложенная структура
                        if key not in target or not isinstance(target[key], dict):
                            target[key] = {}
                        add_translations(value, target[key], lang)

        # Добавляем SOS секцию
        if 'sos' not in data:
            data['sos'] = {}

        add_translations(SOS_TRANSLATIONS['sos'], data['sos'], lang)

        # Записываем обратно
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        print(f"✅ Файл {lang}.json обновлён")

    print()
    print("✅ Все переводы SOS секции добавлены!")

if __name__ == "__main__":
    update_locales()
