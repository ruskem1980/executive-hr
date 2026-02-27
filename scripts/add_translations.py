#!/usr/bin/env python3
"""
Скрипт для добавления недостающих ключей переводов во все языковые файлы.
Используется для исправления хардкод-строк в компонентах.
"""
import json
import sys
from pathlib import Path

# Директория с переводами
LOCALES_DIR = Path(__file__).parent.parent / "apps" / "frontend" / "src" / "locales"

# Новые ключи для добавления
NEW_TRANSLATIONS = {
    "dashboard": {
        "fillDocuments": {
            "ru": "Заполнить документы",
            "en": "Fill Documents",
            "uz": "Hujjatlarni to'ldiring",
            "tg": "Пур кардани ҳуҷҷатҳо",
            "ky": "Документтерди толтуруу"
        },
        "fillDocumentsDescription": {
            "ru": "Это позволит вам автоматически и бесплатно формировать документы, необходимые для подачи в государственные органы, осуществления платежей, формирования любых форм документов и QR-кода, содержащего выбранную вами информацию",
            "en": "This allows you to automatically and free form the documents required for submission to government agencies, making payments, generating any document forms and a QR code containing your selected information",
            "uz": "Bu sizga davlat organlariga topshirish, to'lovlar amalga oshirish, har qanday hujjat shakllarini va tanlangan ma'lumotlaringizni o'z ichiga olgan QR-kodni avtomatik va bepul shakllantirish imkonini beradi",
            "tg": "Ин ба шумо имкон медиҳад, ки ҳуҷҷатҳои зарурӣ барои пешниҳод ба мақомоти давлатӣ, иҷрои пардохтҳо, сохтани ҳар гуна шаклҳои ҳуҷҷатҳо ва рамзи QR-и дарбаргирандаи маълумоти интихобшударо ба таври худкор ва ройгон шакл диҳед",
            "ky": "Бул сизге мамлекеттик органдарга берүү үчүн керектүү документтерди, төлөмдөрдү жүргүзүү, документтердин бардык формаларын жана сиз тандаган маалыматты камтыган QR-кодун автоматтык жана акысыз түзүүгө мүмкүндүк берет"
        }
    }
}

def add_nested_key(data: dict, path: list, value: any) -> None:
    """Добавляет вложенный ключ в словарь."""
    for key in path[:-1]:
        if key not in data:
            data[key] = {}
        data = data[key]
    data[path[-1]] = value

def update_translation_file(lang: str) -> None:
    """Обновляет файл перевода для указанного языка."""
    file_path = LOCALES_DIR / f"{lang}.json"

    if not file_path.exists():
        print(f"❌ Файл {file_path} не найден")
        return

    # Читаем существующий файл
    with open(file_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    # Добавляем новые ключи
    updated = False
    for section, keys in NEW_TRANSLATIONS.items():
        if section not in data:
            data[section] = {}

        for key, translations in keys.items():
            if key not in data[section]:
                data[section][key] = translations[lang]
                updated = True
                print(f"  ➕ Добавлен {section}.{key}")

    if updated:
        # Записываем обратно с правильным форматированием
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"✅ Файл {lang}.json обновлён")
    else:
        print(f"ℹ️  Файл {lang}.json не требует обновления")

def main():
    """Основная функция."""
    print("🔄 Добавление недостающих переводов...")
    print()

    languages = ['ru', 'en', 'uz', 'tg', 'ky']

    for lang in languages:
        print(f"📝 Обновление {lang}.json:")
        update_translation_file(lang)
        print()

    print("✅ Все переводы добавлены!")
    return 0

if __name__ == "__main__":
    sys.exit(main())
