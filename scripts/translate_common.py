#!/usr/bin/env python3
"""
Переводчик с базовыми словарями для частых UI фраз.
Переводит навигацию, кнопки, общие фразы. Остальное остаётся для ручного перевода.
"""
import json
from pathlib import Path
from typing import Dict

PROJECT_ROOT = Path.cwd()
LOCALES_DIR = PROJECT_ROOT / "apps" / "frontend" / "src" / "locales"

# Базовый словарь для общих UI фраз (русский → переводы)
COMMON_PHRASES = {
    # Навигация
    "Главная": {"en": "Home", "uz": "Bosh sahifa", "tg": "Асосӣ", "ky": "Башкы"},
    "Вопросы и ответы": {"en": "FAQ", "uz": "Savol-javoblar", "tg": "Саволу ҷавобҳо", "ky": "Суроо-жооптор"},
    "Сервисы": {"en": "Services", "uz": "Xizmatlar", "tg": "Хизматҳо", "ky": "Кызматтар"},
    "Профиль": {"en": "Profile", "uz": "Profil", "tg": "Профил", "ky": "Профиль"},
    "Настройки": {"en": "Settings", "uz": "Sozlamalar", "tg": "Танзимот", "ky": "Жөндөөлөр"},
    "SOS": {"en": "SOS", "uz": "SOS", "tg": "SOS", "ky": "SOS"},
    "Основная навигация": {"en": "Main navigation", "uz": "Asosiy navigatsiya", "tg": "Навигатсияи асосӣ", "ky": "Негизги навигация"},

    # Кнопки и действия
    "Загрузка...": {"en": "Loading...", "uz": "Yuklanmoqda...", "tg": "Боргирӣ...", "ky": "Жүктөлүүдө..."},
    "Сохранить": {"en": "Save", "uz": "Saqlash", "tg": "Сабт кардан", "ky": "Сактоо"},
    "Отмена": {"en": "Cancel", "uz": "Bekor qilish", "tg": "Бекор кардан", "ky": "Жокко чыгаруу"},
    "Назад": {"en": "Back", "uz": "Orqaga", "tg": "Бозгашт", "ky": "Артка"},
    "Далее": {"en": "Next", "uz": "Keyingi", "tg": "Навбатӣ", "ky": "Кийинки"},
    "Продолжить": {"en": "Continue", "uz": "Davom etish", "tg": "Давом додан", "ky": "Улантуу"},
    "Готово": {"en": "Done", "uz": "Tayyor", "tg": "Тайёр", "ky": "Даяр"},
    "Закрыть": {"en": "Close", "uz": "Yopish", "tg": "Пӯшидан", "ky": "Жабуу"},
    "Поиск": {"en": "Search", "uz": "Qidirish", "tg": "Ҷустуҷӯ", "ky": "Издөө"},
    "Да": {"en": "Yes", "uz": "Ha", "tg": "Ҳа", "ky": "Ооба"},
    "Нет": {"en": "No", "uz": "Yo'q", "tg": "Не", "ky": "Жок"},
    "ОК": {"en": "OK", "uz": "OK", "tg": "OK", "ky": "Макул"},
    "Удалить": {"en": "Delete", "uz": "O'chirish", "tg": "Нест кардан", "ky": "Өчүрүү"},
    "Редактировать": {"en": "Edit", "uz": "Tahrirlash", "tg": "Таҳрир кардан", "ky": "Түзөтүү"},
    "Добавить": {"en": "Add", "uz": "Qo'shish", "tg": "Илова кардан", "ky": "Кошуу"},
    "Скачать": {"en": "Download", "uz": "Yuklab olish", "tg": "Боргирӣ кардан", "ky": "Жүктөп алуу"},
    "Отправить": {"en": "Send", "uz": "Yuborish", "tg": "Фиристодан", "ky": "Жөнөтүү"},

    # Документы
    "Мои документы": {"en": "My Documents", "uz": "Mening hujjatlarim", "tg": "Ҳуҷҷатҳои ман", "ky": "Менин документтерим"},
    "Документы": {"en": "Documents", "uz": "Hujjatlar", "tg": "Ҳуҷҷатҳо", "ky": "Документтер"},
    "Бланки": {"en": "Forms", "uz": "Blankalar", "tg": "Бланкҳо", "ky": "Бланкалар"},
    "Паспорт": {"en": "Passport", "uz": "Pasport", "tg": "Шиноснома", "ky": "Паспорт"},
    "Миграционная карта": {"en": "Migration Card", "uz": "Migratsiya kartasi", "tg": "Корти миграсионӣ", "ky": "Миграциялык карта"},
    "Регистрация": {"en": "Registration", "uz": "Ro'yxatdan o'tish", "tg": "Бақайдгирӣ", "ky": "Каттоо"},
    "Патент на работу": {"en": "Work Patent", "uz": "Ish patenti", "tg": "Патенти кор", "ky": "Иш патенти"},
    "ИНН": {"en": "TIN", "uz": "INN", "tg": "ИНН", "ky": "ИНН"},
    "СНИЛС": {"en": "SNILS", "uz": "SNILS", "tg": "СНИЛС", "ky": "СНИЛС"},

    # Статусы
    "Частично": {"en": "Partial", "uz": "Qisman", "tg": "Қисман", "ky": "Жарым-жартылай"},
    "Заполнен": {"en": "Filled", "uz": "To'ldirilgan", "tg": "Пур", "ky": "Толтурулган"},

    # Время
    "24/7": {"en": "24/7", "uz": "24/7", "tg": "24/7", "ky": "24/7"},

    # Прочее
    "Экспорт": {"en": "Export", "uz": "Eksport", "tg": "Содирот", "ky": "Экспорт"},
    "Ошибка": {"en": "Error", "uz": "Xato", "tg": "Хато", "ky": "Ката"},
    "Попробовать снова": {"en": "Try again", "uz": "Qayta urinish", "tg": "Дубора кӯшиш кардан", "ky": "Кайра аракет кылуу"},
    "Ничего не найдено": {"en": "Nothing found", "uz": "Hech narsa topilmadi", "tg": "Ҳеҷ чиз ёфт нашуд", "ky": "Эч нерсе табылган жок"},
}

class CommonTranslator:
    def __init__(self):
        self.translations = {}
        self.load_all_locales()

    def load_all_locales(self):
        """Загружает все языковые файлы"""
        for lang in ['ru', 'en', 'uz', 'tg', 'ky']:
            path = LOCALES_DIR / f"{lang}.json"
            with open(path, 'r', encoding='utf-8') as f:
                self.translations[lang] = json.load(f)

    def save_locale(self, lang: str):
        """Сохраняет языковой файл"""
        path = LOCALES_DIR / f"{lang}.json"
        # Создаём бэкап
        backup_path = path.with_suffix('.json.before_common_translate')
        import shutil
        shutil.copy(path, backup_path)

        with open(path, 'w', encoding='utf-8') as f:
            json.dump(self.translations[lang], f, ensure_ascii=False, indent=2, sort_keys=True)

    def translate_language(self, lang: str):
        """Переводит один язык используя словарь"""
        print(f"\n🌍 Перевод частых фраз на {lang.upper()}...")

        prefix = f'[{lang.upper()}]'
        replaced_count = 0
        total_count = 0

        def replace_in_obj(obj):
            nonlocal replaced_count, total_count
            if isinstance(obj, str):
                if obj.startswith(prefix):
                    total_count += 1
                    russian_text = obj[len(prefix):].strip()

                    # Проверяем есть ли перевод в словаре
                    if russian_text in COMMON_PHRASES:
                        translation = COMMON_PHRASES[russian_text][lang]
                        replaced_count += 1
                        return translation
                return obj
            elif isinstance(obj, dict):
                return {k: replace_in_obj(v) for k, v in obj.items()}
            elif isinstance(obj, list):
                return [replace_in_obj(item) for item in obj]
            return obj

        self.translations[lang] = replace_in_obj(self.translations[lang])
        self.save_locale(lang)

        print(f"  ✅ Переведено: {replaced_count} из {total_count} заглушек ({replaced_count/total_count*100:.1f}%)")
        print(f"  ⚠️  Осталось для ручного перевода: {total_count - replaced_count}")

def main():
    import sys

    print("🚀 Запуск переводчика частых фраз...")
    print(f"📚 Словарь содержит {len(COMMON_PHRASES)} фраз\n")

    translator = CommonTranslator()

    languages = ['en', 'uz', 'tg', 'ky']

    if len(sys.argv) > 1:
        lang = sys.argv[1].lower()
        if lang in languages:
            languages = [lang]

    for lang in languages:
        translator.translate_language(lang)

    print("\n" + "="*60)
    print("✅ ЧАСТИЧНЫЙ ПЕРЕВОД ЗАВЕРШЁН")
    print("="*60)
    print("\n📝 Что дальше:")
    print("  1. Частые UI фразы переведены")
    print("  2. Сложные юридические термины остались с префиксами [EN], [UZ], etc.")
    print("  3. Используйте профессиональный перевод для оставшихся фраз")
    print("  4. Или переведите вручную, найдя по префиксу [EN] в файлах")

if __name__ == '__main__':
    main()
