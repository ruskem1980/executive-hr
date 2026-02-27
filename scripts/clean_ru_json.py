#!/usr/bin/env python3
"""
Окончательная очистка ru.json от национальных текстов.
Удаляет из ru.json все тексты, которые совпадают с tg/ky/uz.
"""
import json
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path.cwd()
LOCALES_DIR = PROJECT_ROOT / "apps" / "frontend" / "src" / "locales"

def clean_ru_recursive(ru_obj: Any, tg_obj: Any, ky_obj: Any, uz_obj: Any) -> Any:
    """
    Рекурсивно очищает ru_obj от национальных текстов.
    Если текст в ru совпадает с tg/ky/uz - заменяем на пустую строку.
    """
    if isinstance(ru_obj, dict):
        result = {}
        for key in ru_obj:
            tg_val = tg_obj.get(key) if isinstance(tg_obj, dict) else None
            ky_val = ky_obj.get(key) if isinstance(ky_obj, dict) else None
            uz_val = uz_obj.get(key) if isinstance(uz_obj, dict) else None

            result[key] = clean_ru_recursive(ru_obj[key], tg_val, ky_val, uz_val)

        return result

    elif isinstance(ru_obj, str):
        # Проверяем, совпадает ли с национальными языками
        if tg_obj and ru_obj == tg_obj:
            print(f"  Найден таджикский текст: {ru_obj[:60]}")
            return ""  # Пустая строка - требует перевода
        elif ky_obj and ru_obj == ky_obj:
            print(f"  Найден киргизский текст: {ru_obj[:60]}")
            return ""
        elif uz_obj and ru_obj == uz_obj:
            print(f"  Найден узбекский текст: {ru_obj[:60]}")
            return ""

        return ru_obj

    else:
        return ru_obj

def main():
    print("\n" + "="*60)
    print("🧹 ОКОНЧАТЕЛЬНАЯ ОЧИСТКА RU.JSON")
    print("="*60)

    # Загружаем все файлы
    print("\n📂 Загрузка файлов...")
    with open(LOCALES_DIR / "ru.json", 'r', encoding='utf-8') as f:
        ru_data = json.load(f)

    with open(LOCALES_DIR / "tg.json", 'r', encoding='utf-8') as f:
        tg_data = json.load(f)

    with open(LOCALES_DIR / "ky.json", 'r', encoding='utf-8') as f:
        ky_data = json.load(f)

    with open(LOCALES_DIR / "uz.json", 'r', encoding='utf-8') as f:
        uz_data = json.load(f)

    # Создаем бэкап
    backup_path = LOCALES_DIR / "ru.json.before_final_clean"
    import shutil
    shutil.copy2(LOCALES_DIR / "ru.json", backup_path)
    print(f"📦 Бэкап создан: {backup_path.name}")

    # Очищаем
    print("\n🔧 Удаление национальных текстов из ru.json...")
    cleaned_ru = clean_ru_recursive(ru_data, tg_data, ky_data, uz_data)

    # Сохраняем
    print("\n💾 Сохранение...")
    with open(LOCALES_DIR / "ru.json", 'w', encoding='utf-8') as f:
        json.dump(cleaned_ru, f, ensure_ascii=False, indent=2, sort_keys=True)

    print("\n" + "="*60)
    print("✅ ОЧИСТКА ЗАВЕРШЕНА")
    print("="*60)
    print(f"\n💡 Следующий шаг:")
    print(f"   python3 scripts/i18n_validator.py --fix")

if __name__ == '__main__':
    main()
