#!/usr/bin/env python3
"""
Скрипт исправления сломанных ключей переводов:
1. Добавляет отсутствующие ключи emergency-contacts в ВСЕ locale файлы
2. Исправляет дубли ключей консульств (уникальные ключи для каждого города)
3. Исправляет DocumentsList.tsx — оборачивает documentTypeLabels в t()
4. Добавляет недостающие ключи db.types (инн, снилс, дмс)
5. Обновляет emergency-contacts.ts с уникальными ключами консульств
"""

import json
import re
import os
import sys
from pathlib import Path
from collections import OrderedDict

# Корень проекта
ROOT = Path(__file__).parent.parent
LOCALES_DIR = ROOT / "apps" / "frontend" / "src" / "locales"
EMERGENCY_DATA = ROOT / "apps" / "frontend" / "src" / "data" / "emergency-contacts.ts"
DOCUMENTS_LIST = ROOT / "apps" / "frontend" / "src" / "features" / "documents" / "components" / "DocumentsList.tsx"

# ============================================================
# 1. ОТСУТСТВУЮЩИЕ КЛЮЧИ emergency-contacts (ВСЕ языки)
# ============================================================

# Ключи, которые нужно добавить в emergency-contacts.emergency-contacts
MISSING_EMERGENCY_KEYS_RU = {
    # === Экстренные службы ===
    "полиция": "Полиция",
    "пожарная": "Пожарная",
    "пожарная_служба": "Пожарная служба",

    # === Горячие линии ===
    "миграционная_служба": "Миграционная служба",
    "вопросы_миграции": "Вопросы миграции",
    "пнпт_9001800": "Пн-Пт, 9:00-18:00",
    "пнпт_10001800": "Пн-Пт, 10:00-18:00",
    "нарушения_трудовых_прав": "Нарушения трудовых прав",
    "антидискриминационный_центр": "Антидискриминационный центр",
    "генеральная_прокуратура": "Генеральная прокуратура",

    # === Страны ===
    "узбекистан": "Узбекистан",
    "таджикистан": "Таджикистан",
    "кыргызстан": "Кыргызстан",
    "казахстан": "Казахстан",
    "армения": "Армения",
    "азербайджан": "Азербайджан",
    "молдова": "Молдова",
    "беларусь": "Беларусь",
    "украина": "Украина",
    "грузия": "Грузия",
    "туркменистан": "Туркменистан",

    # === Посольства (Москва) ===
    "посольство_узбекистана": "Посольство Узбекистана",
    "посольство_таджикистана": "Посольство Таджикистана",
    "посольство_кыргызстана": "Посольство Кыргызстана",
    "посольство_казахстана": "Посольство Казахстана",
    "посольство_армении": "Посольство Армении",
    "посольство_азербайджана": "Посольство Азербайджана",
    "посольство_молдовы": "Посольство Молдовы",
    "посольство_беларуси": "Посольство Беларуси",
    "посольство_украины": "Посольство Украины",
    "посольство_туркменистана": "Посольство Туркменистана",

    # === Адреса посольств (Москва) ===
    "москва_погорельский_пер": "Москва, Погорельский пер., 12",
    "москва_гранатный_пер": "Москва, Гранатный пер., 13",
    "москва_ул_б": "Москва, ул. Б. Ордынка, 64",
    "москва_чистопрудный_бульвар": "Москва, Чистопрудный бульвар, 3А",
    "москва_армянский_пер": "Москва, Армянский пер., 2",
    "москва_леонтьевский_пер": "Москва, Леонтьевский пер., 16",
    "москва_кузнецкий_мост": "Москва, Кузнецкий мост, 18",
    "москва_ул_маросейка": "Москва, ул. Маросейка, 17/6",
    "москва_малый_ржевский": "Москва, Малый Ржевский пер., 6",
    "москва_филипповский_пер": "Москва, Филипповский пер., 22",

    # === Генконсульства (уникальные ключи для каждого города) ===
    # Санкт-Петербург
    "генконсульство_узбекистана_спб": "Генконсульство Узбекистана в Санкт-Петербурге",
    "генконсульство_таджикистана_спб": "Генконсульство Таджикистана в Санкт-Петербурге",
    "представительство_кыргызстана_спб": "Представительство Кыргызстана в Санкт-Петербурге",
    "санктпетербург_ул_литейный": "Санкт-Петербург, Литейный пр., 49",
    "санктпетербург_ул_чайковского": "Санкт-Петербург, ул. Чайковского, 39",
    "санктпетербург_ул_гороховая": "Санкт-Петербург, ул. Гороховая, 3",

    # Екатеринбург
    "генконсульство_узбекистана_екб": "Генконсульство Узбекистана в Екатеринбурге",
    "генконсульство_таджикистана_екб": "Генконсульство Таджикистана в Екатеринбурге",
    "генконсульство_кыргызстана_екб": "Генконсульство Кыргызстана в Екатеринбурге",
    "екатеринбург_ул_гоголя": "Екатеринбург, ул. Гоголя, 15",
    "екатеринбург_ул_шейнкмана": "Екатеринбург, ул. Шейнкмана, 50",
    "екатеринбург_ул_чапаева": "Екатеринбург, ул. Чапаева, 7",

    # Новосибирск
    "генконсульство_узбекистана_нск": "Генконсульство Узбекистана в Новосибирске",
    "представительство_таджикистана_нск": "Представительство Таджикистана в Новосибирске",
    "генконсульство_кыргызстана_нск": "Генконсульство Кыргызстана в Новосибирске",
    "новосибирск_ул_вокзальная": "Новосибирск, ул. Вокзальная, 14",
    "новосибирск_красный_пр": "Новосибирск, Красный проспект, 56",
    "новосибирск_ул_депутатская": "Новосибирск, ул. Депутатская, 38",

    # Казань
    "генконсульство_узбекистана_кзн": "Генконсульство Узбекистана в Казани",
    "представительство_таджикистана_кзн": "Представительство Таджикистана в Казани",
    "представительство_кыргызстана_кзн": "Представительство Кыргызстана в Казани",
    "казань_ул_муштари": "Казань, ул. Муштари, 15",
    "казань_ул_островского": "Казань, ул. Островского, 25",
    "казань_ул_пушкина": "Казань, ул. Пушкина, 52",

    # === Экстренные гайды (шаги) ===
    "задержала_полиция": "Задержала полиция",
    "попросите_показать_удостоверение": "Попросите показать удостоверение сотрудника",
    "узнайте_причину_задержания": "Узнайте причину задержания",
    "требуйте_протокол_задержания": "Требуйте протокол задержания и копию",
    "потерял_документы": "Потерял документы",
    "соберите_доказательства_работы": "Соберите доказательства работы (переписка, пропуск, свидетели)",
    "найдите_бесплатную_юридическую": "Найдите бесплатную юридическую консультацию",
    "зафиксируйте_травмы_медицинские": "Зафиксируйте травмы — медицинские справки и фото",
}

# Переводы для других языков (базовые — можно уточнить позже)
MISSING_EMERGENCY_KEYS_EN = {
    "полиция": "Police",
    "пожарная": "Fire Department",
    "пожарная_служба": "Fire service",
    "миграционная_служба": "Migration Service",
    "вопросы_миграции": "Migration issues",
    "пнпт_9001800": "Mon-Fri, 9:00-18:00",
    "пнпт_10001800": "Mon-Fri, 10:00-18:00",
    "нарушения_трудовых_прав": "Labor rights violations",
    "антидискриминационный_центр": "Anti-discrimination Center",
    "генеральная_прокуратура": "General Prosecutor's Office",
    "узбекистан": "Uzbekistan",
    "таджикистан": "Tajikistan",
    "кыргызстан": "Kyrgyzstan",
    "казахстан": "Kazakhstan",
    "армения": "Armenia",
    "азербайджан": "Azerbaijan",
    "молдова": "Moldova",
    "беларусь": "Belarus",
    "украина": "Ukraine",
    "грузия": "Georgia",
    "туркменистан": "Turkmenistan",
    "посольство_узбекистана": "Embassy of Uzbekistan",
    "посольство_таджикистана": "Embassy of Tajikistan",
    "посольство_кыргызстана": "Embassy of Kyrgyzstan",
    "посольство_казахстана": "Embassy of Kazakhstan",
    "посольство_армении": "Embassy of Armenia",
    "посольство_азербайджана": "Embassy of Azerbaijan",
    "посольство_молдовы": "Embassy of Moldova",
    "посольство_беларуси": "Embassy of Belarus",
    "посольство_украины": "Embassy of Ukraine",
    "посольство_туркменистана": "Embassy of Turkmenistan",
    "задержала_полиция": "Detained by police",
    "попросите_показать_удостоверение": "Ask to see officer's ID",
    "узнайте_причину_задержания": "Find out reason for detention",
    "требуйте_протокол_задержания": "Request detention protocol and a copy",
    "потерял_документы": "Lost documents",
    "соберите_доказательства_работы": "Collect work evidence (messages, pass, witnesses)",
    "найдите_бесплатную_юридическую": "Find free legal consultation",
    "зафиксируйте_травмы_медицинские": "Document injuries — medical reports and photos",
}

# Для uz, tg, ky — используем русские значения как placeholder
# (они будут заменены при профессиональном переводе)

# ============================================================
# 2. МАППИНГ СТАРЫХ КЛЮЧЕЙ КОНСУЛЬСТВ → НОВЫЕ
# ============================================================

# Старые неуникальные ключи → новые уникальные (для emergency-contacts.ts)
CONSULATE_KEY_REMAP = {
    # Санкт-Петербург
    ("uz-spb", "name"): ("генконсульство_узбекистана_в", "генконсульство_узбекистана_спб"),
    ("tj-spb", "name"): ("генконсульство_таджикистана_в", "генконсульство_таджикистана_спб"),
    ("kg-spb", "name"): ("представительство_кыргызстана_в", "представительство_кыргызстана_спб"),
    # Екатеринбург
    ("uz-ekb", "name"): ("генконсульство_узбекистана_в", "генконсульство_узбекистана_екб"),
    ("tj-ekb", "name"): ("генконсульство_таджикистана_в", "генконсульство_таджикистана_екб"),
    ("kg-ekb", "name"): ("генконсульство_кыргызстана_в", "генконсульство_кыргызстана_екб"),
    # Новосибирск
    ("uz-nsk", "name"): ("генконсульство_узбекистана_в", "генконсульство_узбекистана_нск"),
    ("tj-nsk", "name"): ("представительство_таджикистана_в", "представительство_таджикистана_нск"),
    ("kg-nsk", "name"): ("генконсульство_кыргызстана_в", "генконсульство_кыргызстана_нск"),
    # Казань
    ("uz-kzn", "name"): ("генконсульство_узбекистана_в", "генконсульство_узбекистана_кзн"),
    ("tj-kzn", "name"): ("представительство_таджикистана_в", "представительство_таджикистана_кзн"),
    ("kg-kzn", "name"): ("представительство_кыргызстана_в", "представительство_кыргызстана_кзн"),
}


def load_json(path: Path) -> dict:
    """Загрузка JSON с сохранением порядка ключей"""
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f, object_pairs_hook=OrderedDict)


def save_json(path: Path, data: dict):
    """Сохранение JSON с читаемым форматированием"""
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write("\n")


def add_missing_keys_to_locale(locale_path: Path, lang: str) -> int:
    """Добавить отсутствующие ключи в файл локали. Возвращает количество добавленных."""
    data = load_json(locale_path)
    added = 0

    # --- emergency-contacts ---
    if "emergency-contacts" not in data:
        data["emergency-contacts"] = OrderedDict()
    if "emergency-contacts" not in data["emergency-contacts"]:
        data["emergency-contacts"]["emergency-contacts"] = OrderedDict()

    ec = data["emergency-contacts"]["emergency-contacts"]

    # Выбираем переводы в зависимости от языка
    if lang == "en":
        translations = MISSING_EMERGENCY_KEYS_EN
    else:
        translations = MISSING_EMERGENCY_KEYS_RU

    for key, value in translations.items():
        if key not in ec:
            # Для en — используем английский перевод, для остальных — русский
            if lang == "en":
                ec[key] = value
            elif lang == "ru":
                ec[key] = MISSING_EMERGENCY_KEYS_RU[key]
            else:
                # Для uz, tg, ky — пока ставим русское значение как placeholder
                ec[key] = MISSING_EMERGENCY_KEYS_RU[key]
            added += 1

    # Удаляем старые неуникальные ключи консульств (заменены на уникальные)
    old_keys_to_remove = [
        "генконсульство_узбекистана_в",
        "генконсульство_таджикистана_в",
        "представительство_кыргызстана_в",
        "представительство_таджикистана_в",
    ]
    for old_key in old_keys_to_remove:
        if old_key in ec:
            del ec[old_key]

    # Сортировка ключей для единообразия
    sorted_ec = OrderedDict(sorted(ec.items()))
    data["emergency-contacts"]["emergency-contacts"] = sorted_ec

    # --- db.types ---
    if "db" not in data:
        data["db"] = OrderedDict()
    if "types" not in data["db"]:
        data["db"]["types"] = OrderedDict()

    db_types = data["db"]["types"]
    missing_db = {
        "инн": {"ru": "ИНН", "en": "Tax ID (INN)"},
        "снилс": {"ru": "СНИЛС", "en": "SNILS"},
        "дмс": {"ru": "ДМС", "en": "Voluntary Health Insurance (VHI)"},
    }
    for key, vals in missing_db.items():
        if key not in db_types:
            db_types[key] = vals.get(lang, vals["ru"])
            added += 1

    save_json(locale_path, data)
    return added


def fix_emergency_contacts_ts() -> int:
    """Исправить emergency-contacts.ts — уникальные ключи для консульств"""
    content = EMERGENCY_DATA.read_text(encoding="utf-8")
    original = content
    replacements = 0

    # Замены для консульств Санкт-Петербурга
    remap = [
        # uz-spb
        ("id: 'uz-spb',\n    country: 'emergency-contacts.emergency-contacts.узбекистан',\n    countryCode: 'UZ',\n    flag: '\\u{1F1FA}\\u{1F1FF}',\n    name: 'emergency-contacts.emergency-contacts.генконсульство_узбекистана_в',\n    phone: '+7 (812) 315-15-30',\n    address: 'emergency-contacts.emergency-contacts.санктпетербург_ул_литейный',",
         "id: 'uz-spb',\n    country: 'emergency-contacts.emergency-contacts.узбекистан',\n    countryCode: 'UZ',\n    flag: '\\u{1F1FA}\\u{1F1FF}',\n    name: 'emergency-contacts.emergency-contacts.генконсульство_узбекистана_спб',\n    phone: '+7 (812) 315-15-30',\n    address: 'emergency-contacts.emergency-contacts.санктпетербург_ул_литейный',"),
        # tj-spb
        ("id: 'tj-spb',\n    country: 'emergency-contacts.emergency-contacts.таджикистан',\n    countryCode: 'TJ',\n    flag: '\\u{1F1F9}\\u{1F1EF}',\n    name: 'emergency-contacts.emergency-contacts.генконсульство_таджикистана_в',\n    phone: '+7 (812) 329-63-63',\n    address: 'emergency-contacts.emergency-contacts.санктпетербург_ул_чайковского',",
         "id: 'tj-spb',\n    country: 'emergency-contacts.emergency-contacts.таджикистан',\n    countryCode: 'TJ',\n    flag: '\\u{1F1F9}\\u{1F1EF}',\n    name: 'emergency-contacts.emergency-contacts.генконсульство_таджикистана_спб',\n    phone: '+7 (812) 329-63-63',\n    address: 'emergency-contacts.emergency-contacts.санктпетербург_ул_чайковского',"),
        # kg-spb
        ("id: 'kg-spb',\n    country: 'emergency-contacts.emergency-contacts.кыргызстан',\n    countryCode: 'KG',\n    flag: '\\u{1F1F0}\\u{1F1EC}',\n    name: 'emergency-contacts.emergency-contacts.представительство_кыргызстана_в',\n    phone: '+7 (812) 676-48-68',\n    address: 'emergency-contacts.emergency-contacts.санктпетербург_ул_гороховая',",
         "id: 'kg-spb',\n    country: 'emergency-contacts.emergency-contacts.кыргызстан',\n    countryCode: 'KG',\n    flag: '\\u{1F1F0}\\u{1F1EC}',\n    name: 'emergency-contacts.emergency-contacts.представительство_кыргызстана_спб',\n    phone: '+7 (812) 676-48-68',\n    address: 'emergency-contacts.emergency-contacts.санктпетербург_ул_гороховая',"),
    ]

    for old, new in remap:
        if old in content:
            content = content.replace(old, new)
            replacements += 1

    # Замены для Екатеринбурга — используем regex для надёжности
    ekb_remap = [
        # uz-ekb
        (r"(id: 'uz-ekb'[^}]*name: 'emergency-contacts\.emergency-contacts\.)генконсульство_узбекистана_в(')",
         r"\1генконсульство_узбекистана_екб\2"),
        # tj-ekb
        (r"(id: 'tj-ekb'[^}]*name: 'emergency-contacts\.emergency-contacts\.)генконсульство_таджикистана_в(')",
         r"\1генконсульство_таджикистана_екб\2"),
        # kg-ekb
        (r"(id: 'kg-ekb'[^}]*name: 'emergency-contacts\.emergency-contacts\.)генконсульство_кыргызстана_в(')",
         r"\1генконсульство_кыргызстана_екб\2"),
    ]

    nsk_remap = [
        # uz-nsk
        (r"(id: 'uz-nsk'[^}]*name: 'emergency-contacts\.emergency-contacts\.)генконсульство_узбекистана_в(')",
         r"\1генконсульство_узбекистана_нск\2"),
        # tj-nsk
        (r"(id: 'tj-nsk'[^}]*name: 'emergency-contacts\.emergency-contacts\.)представительство_таджикистана_в(')",
         r"\1представительство_таджикистана_нск\2"),
        # kg-nsk
        (r"(id: 'kg-nsk'[^}]*name: 'emergency-contacts\.emergency-contacts\.)генконсульство_кыргызстана_в(')",
         r"\1генконсульство_кыргызстана_нск\2"),
    ]

    kzn_remap = [
        # uz-kzn
        (r"(id: 'uz-kzn'[^}]*name: 'emergency-contacts\.emergency-contacts\.)генконсульство_узбекистана_в(')",
         r"\1генконсульство_узбекистана_кзн\2"),
        # tj-kzn
        (r"(id: 'tj-kzn'[^}]*name: 'emergency-contacts\.emergency-contacts\.)представительство_таджикистана_в(')",
         r"\1представительство_таджикистана_кзн\2"),
        # kg-kzn
        (r"(id: 'kg-kzn'[^}]*name: 'emergency-contacts\.emergency-contacts\.)представительство_кыргызстана_в(')",
         r"\1представительство_кыргызстана_кзн\2"),
    ]

    for remap_list in [ekb_remap, nsk_remap, kzn_remap]:
        for pattern, replacement in remap_list:
            new_content, count = re.subn(pattern, replacement, content, flags=re.DOTALL)
            if count > 0:
                content = new_content
                replacements += count

    if content != original:
        EMERGENCY_DATA.write_text(content, encoding="utf-8")

    return replacements


def fix_documents_list_tsx() -> bool:
    """Исправить DocumentsList.tsx — обернуть documentTypeLabels в t()"""
    content = DOCUMENTS_LIST.read_text(encoding="utf-8")
    original = content
    changed = False

    # Проверяем, импортирован ли useTranslation
    if "useTranslation" not in content:
        # Добавляем импорт useTranslation
        content = content.replace(
            "import type { TypedDocument, DocumentTypeValue, DocumentStatus } from '@/lib/db/types';",
            "import type { TypedDocument, DocumentTypeValue, DocumentStatus } from '@/lib/db/types';\nimport { useTranslation } from '@/lib/i18n';"
        )
        changed = True

    # Проверяем, есть ли const { t } = useTranslation() в компоненте
    # Ищем основной компонент
    if "const { t } = useTranslation();" not in content:
        # Находим начало функционального компонента и добавляем хук
        # Ищем паттерн "export function DocumentsList" или "export default function"
        # и добавляем t после первого { после определения
        func_patterns = [
            r"(export\s+function\s+DocumentsList\s*\([^)]*\)\s*\{)",
            r"(export\s+default\s+function\s+DocumentsList\s*\([^)]*\)\s*\{)",
            r"(function\s+DocumentsList\s*\([^)]*\)\s*\{)",
        ]
        for pat in func_patterns:
            match = re.search(pat, content)
            if match:
                insert_pos = match.end()
                content = content[:insert_pos] + "\n  const { t } = useTranslation();" + content[insert_pos:]
                changed = True
                break

    # Исправляем label: documentTypeLabels[type] → label: t(documentTypeLabels[type])
    # Строка 197: label: documentTypeLabels[type],
    old_pattern = "label: documentTypeLabels[type],"
    new_pattern = "label: t(documentTypeLabels[type]),"
    if old_pattern in content and new_pattern not in content:
        content = content.replace(old_pattern, new_pattern)
        changed = True

    # Исправляем {group.label} в заголовке группы — label уже будет переведён
    # Также исправляем {label} в select option (строка 576)
    old_option = "                {label}\n              </option>"
    new_option = "                {t(label)}\n              </option>"
    if old_option in content and new_option not in content:
        content = content.replace(old_option, new_option)
        changed = True

    # Исправляем typeLabel в поиске (строка 98)
    old_search = "const typeLabel = documentTypeLabels[doc.type].toLowerCase();"
    new_search = "const typeLabel = t(documentTypeLabels[doc.type]).toLowerCase();"
    if old_search in content and new_search not in content:
        content = content.replace(old_search, new_search)
        changed = True

    if changed:
        DOCUMENTS_LIST.write_text(content, encoding="utf-8")

    return changed


def fix_documents_page_tsx() -> bool:
    """Исправить documents/page.tsx — обернуть documentTypeLabels в t()"""
    doc_page = ROOT / "apps" / "frontend" / "src" / "app" / "(main)" / "documents" / "page.tsx"
    content = doc_page.read_text(encoding="utf-8")
    original = content
    changed = False

    # В этом файле documentTypeLabels импортируется из @/features/documents (schemas),
    # где значения — прямые строки ('Паспорт', 'Миграционная карта'),
    # НО лучше тоже заменить на i18n-ключи для мультиязычности.
    #
    # Однако для минимального исправления — этот файл уже работает
    # (на скриншоте проблема в DocumentsList.tsx, не в page.tsx)

    return changed


def main():
    print("=" * 60)
    print("  ИСПРАВЛЕНИЕ СЛОМАННЫХ КЛЮЧЕЙ ПЕРЕВОДОВ")
    print("=" * 60)
    print()

    total_fixes = 0

    # --- Шаг 1: Добавляем ключи во все locale файлы ---
    print("1. Добавление недостающих ключей в locale файлы...")
    locale_files = {
        "ru": LOCALES_DIR / "ru.json",
        "en": LOCALES_DIR / "en.json",
        "uz": LOCALES_DIR / "uz.json",
        "tg": LOCALES_DIR / "tg.json",
        "ky": LOCALES_DIR / "ky.json",
    }

    for lang, path in locale_files.items():
        if path.exists():
            added = add_missing_keys_to_locale(path, lang)
            print(f"   {lang}.json: +{added} ключей")
            total_fixes += added
        else:
            print(f"   {lang}.json: ФАЙЛ НЕ НАЙДЕН!")

    # --- Шаг 2: Исправляем emergency-contacts.ts ---
    print("\n2. Исправление emergency-contacts.ts (уникальные ключи консульств)...")
    ts_fixes = fix_emergency_contacts_ts()
    print(f"   Замен: {ts_fixes}")
    total_fixes += ts_fixes

    # --- Шаг 3: Исправляем DocumentsList.tsx ---
    print("\n3. Исправление DocumentsList.tsx (оборачивание в t())...")
    doc_fixed = fix_documents_list_tsx()
    print(f"   Изменён: {'Да' if doc_fixed else 'Нет (уже исправлен)'}")
    if doc_fixed:
        total_fixes += 1

    # --- Шаг 4: Верификация ---
    print("\n4. Верификация...")
    # Проверяем что все ключи из emergency-contacts.ts есть в ru.json
    ru_data = load_json(locale_files["ru"])
    ec_keys = ru_data.get("emergency-contacts", {}).get("emergency-contacts", {})

    ts_content = EMERGENCY_DATA.read_text(encoding="utf-8")
    # Извлекаем все ключи из TS файла
    key_pattern = r"'emergency-contacts\.emergency-contacts\.([^']+)'"
    used_keys = set(re.findall(key_pattern, ts_content))

    missing = used_keys - set(ec_keys.keys())
    if missing:
        print(f"   ВНИМАНИЕ! Остались пропущенные ключи ({len(missing)}):")
        for k in sorted(missing):
            print(f"     - {k}")
    else:
        print(f"   Все {len(used_keys)} ключей из emergency-contacts.ts найдены в ru.json")

    # Проверяем db.types
    db_types = ru_data.get("db", {}).get("types", {})
    required_db = ["паспорт", "миграционная_карта", "патент_на_работу", "регистрация", "инн", "снилс", "дмс"]
    missing_db = [k for k in required_db if k not in db_types]
    if missing_db:
        print(f"   ВНИМАНИЕ! Отсутствуют db.types: {missing_db}")
    else:
        print(f"   Все {len(required_db)} ключей db.types на месте")

    print(f"\n{'=' * 60}")
    print(f"  ИТОГО: {total_fixes} исправлений")
    print(f"{'=' * 60}")

    return 0 if not missing and not missing_db else 1


if __name__ == "__main__":
    sys.exit(main())
