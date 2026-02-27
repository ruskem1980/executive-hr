#!/usr/bin/env python3
"""
Скрипт массового исправления проблем с переводами.
Найдены по скриншотам UI — непереведённые ключи и отсутствующие вызовы t().

Исправляет:
1. Плейсхолдеры в ru.json (cloudSafe, profile.dangerZone, common, examTrainer, scenarioTrainer)
2. Компоненты без t() (SectionHeader, DeadlinesSection, ProfileTabSwitcher, documents/page)
3. Синхронизация критичных ключей в en.json

Запуск: python3 scripts/fix_all_translation_issues.py [--dry-run]
"""

import json
import sys
import re
from pathlib import Path

DRY_RUN = '--dry-run' in sys.argv
BASE = Path(__file__).resolve().parent.parent
LOCALES = BASE / 'apps' / 'frontend' / 'src' / 'locales'
COMPONENTS = BASE / 'apps' / 'frontend' / 'src'

# ============================================================
# 1. ПЕРЕВОДЫ ДЛЯ ru.json
# ============================================================
RU_FIXES = {
    # cloudSafe — плейсхолдеры
    "cloudSafe.title": "Облачное хранилище",
    "cloudSafe.subtitle": "Зашифрованный бэкап ваших данных",
    "cloudSafe.createBackup": "Создать бэкап",
    "cloudSafe.restore": "Восстановить",
    "cloudSafe.creating": "Создание бэкапа...",
    "cloudSafe.restoring": "Восстановление...",
    "cloudSafe.backupDate": "Дата бэкапа",
    "cloudSafe.backupSize": "Размер",
    "cloudSafe.confirmPassword": "Подтвердите пароль",
    "cloudSafe.copyRecoveryCode": "Скопировать код восстановления",
    "cloudSafe.delete": "Удалить",
    "cloudSafe.encryption": "Шифрование AES-256",
    "cloudSafe.error": "Ошибка",
    "cloudSafe.lastBackup": "Последний бэкап",
    "cloudSafe.password": "Пароль",
    "cloudSafe.recoveryCode": "Код восстановления",
    "cloudSafe.recoveryCodeCopied": "Код скопирован",
    "cloudSafe.selectBackup": "Выберите бэкап",

    # profile.dangerZone — плейсхолдеры
    "profile.dangerZone.title": "Опасная зона",
    "profile.dangerZone.deleteAccount": "Удалить аккаунт",
    "profile.dangerZone.deleteForever": "Удалить навсегда",

    # common — плейсхолдеры
    "common.check": "Проверить",
    "common.checkAnother": "Проверить другой",
    "common.checked": "Проверено",
    "common.checking": "Проверка...",
    "common.clear": "Очистить",
    "common.comingSoon": "Скоро",
    "common.copied": "Скопировано",
    "common.copy": "Копировать",
    "common.delete": "Удалить",
    "common.done": "Готово",
    "common.download": "Скачать",
    "common.edit": "Редактировать",
    "common.encrypted": "Зашифровано",
    "common.goToServicesTab": "Перейдите на вкладку Сервисы",
    "common.more": "Ещё",
    "common.new": "Новый",
    "common.next": "Далее",
    "common.connected": "Подключено",

    # examTrainer — недостающие ключи
    "examTrainer.header.title": "Тренажёр экзамена",
    "examTrainer.info.passingScore": "Проходной балл",
    "examTrainer.info.passPercent": "{percent}%",
    "examTrainer.info.timeRegular": "30 мин",
    "examTrainer.modes.selectLabel": "Режим тренировки",
    "examTrainer.modes.practice.label": "Практика",
    "examTrainer.modes.exam.label": "Экзамен",
    "examTrainer.modes.learning.label": "Обучение",
    "examTrainer.difficulty.selectLabel": "Сложность",
    "examTrainer.difficulty.easy": "Лёгкие",
    "examTrainer.difficulty.medium": "Средние",
    "examTrainer.difficulty.hard": "Сложные",
    "examTrainer.categories.selectLabel": "Категория вопросов",
    "examTrainer.categories.questionsCount": "{count} вопросов",
    "examTrainer.categories.russian_language": "Русский язык",
    "examTrainer.categories.history": "История России",
    "examTrainer.categories.law": "Основы законодательства",
    "examTrainer.buttons.start": "Начать тест",
    "examTrainer.buttons.next": "Следующий вопрос",
    "examTrainer.buttons.finish": "Завершить",

    # scenarioTrainer — недостающие ключи
    "scenarioTrainer.header.title": "Тренажёр ситуаций",
    "scenarioTrainer.select.title": "Выберите сценарий",
    "scenarioTrainer.difficulty.1": "Очень лёгкий",
    "scenarioTrainer.difficulty.2": "Лёгкий",
    "scenarioTrainer.difficulty.3": "Средний",
    "scenarioTrainer.difficulty.4": "Сложный",
    "scenarioTrainer.difficulty.5": "Очень сложный",
    "scenarioTrainer.estimatedTime": "~{minutes} мин",
    "scenarioTrainer.buttons.start": "Начать",

    # profile.sections — для ProfileTabSwitcher
    "profile.sections.personal": "Личные данные",
    "profile.sections.documents": "Документы",
    "profile.sections.work": "Работа",
    "profile.sections.registration": "Регистрация",

    # documents page — описания типов документов
    "documents.descriptions.passport": "Основной документ, удостоверяющий личность",
    "documents.descriptions.migration_card": "Подтверждение легального въезда в РФ",
    "documents.descriptions.patent": "Разрешение на работу в РФ",
    "documents.descriptions.registration": "Миграционный учёт по месту пребывания",
    "documents.descriptions.inn": "Идентификационный номер налогоплательщика",
    "documents.descriptions.snils": "Страховой номер индивидуального лицевого счёта",
    "documents.descriptions.dms": "Добровольное медицинское страхование",

    # documents page — статусы
    "documents.status.empty": "Не заполнен",
    "documents.status.partial": "Частично заполнен",
    "documents.status.complete": "Заполнен",

    # settingsPage.sections — плейсхолдеры
    "settingsPage.sections.notifications": "Уведомления",
    "settingsPage.sections.notificationsDesc": "Настройте push и Telegram-уведомления",
    "settingsPage.sections.rateApp": "Оценить приложение",
    "settingsPage.sections.rateAppDesc": "Поставьте оценку в магазине приложений",
    "settingsPage.sections.security": "Безопасность",
    "settingsPage.sections.securityDesc": "Ключи шифрования и восстановление",
    "settingsPage.sections.subscriptions": "Подписка",
    "settingsPage.sections.subscriptionsDesc": "Управление тарифным планом",

    # settingsPage.subscription — плейсхолдеры
    "settingsPage.subscription.current": "Текущий",
    "settingsPage.subscription.currentPlan": "Текущий план",
    "settingsPage.subscription.free": "Бесплатно",
    "settingsPage.subscription.month": "мес",
    "settingsPage.subscription.popular": "Популярный",
    "settingsPage.subscription.restorePurchases": "Восстановить покупки",
    "settingsPage.subscription.upgrade": "Улучшить",

    # settingsPage.dataExport
    "settingsPage.dataExport.exporting": "Экспорт данных...",
    "settingsPage.dataExport.downloadButton": "Скачать мои данные",
    "settingsPage.dataExport.description": "Скачайте копию всех ваших данных в формате JSON (ст. 14 ФЗ-152)",

    # keyRecovery
    "keyRecovery.status.active": "Ключи настроены",
    "keyRecovery.status.notSetup": "Ключи не настроены",
    "keyRecovery.viewCode": "Показать код восстановления",
    "keyRecovery.setupButton": "Настроить ключи",

    # exportPdf — плейсхолдеры
    "exportPdf.documents": "Документы",
    "exportPdf.documentsCount": "{count} документов",
    "exportPdf.profile": "Профиль",
}

# ============================================================
# 2. ПЕРЕВОДЫ ДЛЯ en.json
# ============================================================
EN_FIXES = {
    "cloudSafe.title": "Cloud Storage",
    "cloudSafe.subtitle": "Encrypted backup of your data",
    "cloudSafe.createBackup": "Create Backup",
    "cloudSafe.restore": "Restore",
    "cloudSafe.creating": "Creating backup...",
    "cloudSafe.restoring": "Restoring...",
    "cloudSafe.backupDate": "Backup date",
    "cloudSafe.backupSize": "Size",
    "cloudSafe.confirmPassword": "Confirm password",
    "cloudSafe.copyRecoveryCode": "Copy recovery code",
    "cloudSafe.delete": "Delete",
    "cloudSafe.encryption": "AES-256 encryption",
    "cloudSafe.error": "Error",
    "cloudSafe.lastBackup": "Last backup",
    "cloudSafe.password": "Password",
    "cloudSafe.recoveryCode": "Recovery code",
    "cloudSafe.recoveryCodeCopied": "Code copied",
    "cloudSafe.selectBackup": "Select backup",

    "profile.dangerZone.title": "Danger Zone",
    "profile.dangerZone.deleteAccount": "Delete Account",
    "profile.dangerZone.deleteForever": "Delete Forever",

    "common.check": "Check",
    "common.checkAnother": "Check Another",
    "common.checked": "Checked",
    "common.checking": "Checking...",
    "common.clear": "Clear",
    "common.comingSoon": "Coming Soon",
    "common.copied": "Copied",
    "common.copy": "Copy",
    "common.delete": "Delete",
    "common.done": "Done",
    "common.download": "Download",
    "common.edit": "Edit",
    "common.encrypted": "Encrypted",
    "common.goToServicesTab": "Go to Services tab",
    "common.more": "More",
    "common.new": "New",
    "common.next": "Next",
    "common.connected": "Connected",

    "examTrainer.header.title": "Exam Trainer",
    "examTrainer.info.passingScore": "Passing score",
    "examTrainer.info.passPercent": "{percent}%",
    "examTrainer.info.timeRegular": "30 min",
    "examTrainer.modes.selectLabel": "Training mode",
    "examTrainer.modes.practice.label": "Practice",
    "examTrainer.modes.exam.label": "Exam",
    "examTrainer.modes.learning.label": "Learning",
    "examTrainer.difficulty.selectLabel": "Difficulty",
    "examTrainer.difficulty.easy": "Easy",
    "examTrainer.difficulty.medium": "Medium",
    "examTrainer.difficulty.hard": "Hard",
    "examTrainer.categories.selectLabel": "Question category",
    "examTrainer.categories.questionsCount": "{count} questions",
    "examTrainer.categories.russian_language": "Russian Language",
    "examTrainer.categories.history": "History of Russia",
    "examTrainer.categories.law": "Fundamentals of Law",
    "examTrainer.buttons.start": "Start Test",
    "examTrainer.buttons.next": "Next Question",
    "examTrainer.buttons.finish": "Finish",

    "scenarioTrainer.header.title": "Scenario Trainer",
    "scenarioTrainer.select.title": "Choose a Scenario",
    "scenarioTrainer.difficulty.1": "Very Easy",
    "scenarioTrainer.difficulty.2": "Easy",
    "scenarioTrainer.difficulty.3": "Medium",
    "scenarioTrainer.difficulty.4": "Hard",
    "scenarioTrainer.difficulty.5": "Very Hard",
    "scenarioTrainer.estimatedTime": "~{minutes} min",
    "scenarioTrainer.buttons.start": "Start",

    "profile.sections.personal": "Personal Info",
    "profile.sections.documents": "Documents",
    "profile.sections.work": "Work",
    "profile.sections.registration": "Registration",

    "documents.descriptions.passport": "Primary identity document",
    "documents.descriptions.migration_card": "Proof of legal entry to Russia",
    "documents.descriptions.patent": "Work permit in Russia",
    "documents.descriptions.registration": "Migration registration at place of stay",
    "documents.descriptions.inn": "Taxpayer Identification Number",
    "documents.descriptions.snils": "Individual Insurance Account Number",
    "documents.descriptions.dms": "Voluntary Health Insurance",

    "documents.status.empty": "Not filled",
    "documents.status.partial": "Partially filled",
    "documents.status.complete": "Filled",

    "settingsPage.sections.notifications": "Notifications",
    "settingsPage.sections.notificationsDesc": "Configure push and Telegram notifications",
    "settingsPage.sections.rateApp": "Rate App",
    "settingsPage.sections.rateAppDesc": "Leave a review in the app store",
    "settingsPage.sections.security": "Security",
    "settingsPage.sections.securityDesc": "Encryption keys and recovery",
    "settingsPage.sections.subscriptions": "Subscription",
    "settingsPage.sections.subscriptionsDesc": "Manage your subscription plan",

    "settingsPage.subscription.current": "Current",
    "settingsPage.subscription.currentPlan": "Current Plan",
    "settingsPage.subscription.free": "Free",
    "settingsPage.subscription.month": "mo",
    "settingsPage.subscription.popular": "Popular",
    "settingsPage.subscription.restorePurchases": "Restore Purchases",
    "settingsPage.subscription.upgrade": "Upgrade",

    "settingsPage.dataExport.exporting": "Exporting data...",
    "settingsPage.dataExport.downloadButton": "Download My Data",
    "settingsPage.dataExport.description": "Download a copy of all your data in JSON format (Art. 14, FZ-152)",

    "keyRecovery.status.active": "Keys configured",
    "keyRecovery.status.notSetup": "Keys not configured",
    "keyRecovery.viewCode": "View recovery code",
    "keyRecovery.setupButton": "Set up keys",

    "exportPdf.documents": "Documents",
    "exportPdf.documentsCount": "{count} documents",
    "exportPdf.profile": "Profile",
}

# ============================================================
# 3. ИСПРАВЛЕНИЯ КОМПОНЕНТОВ (замены в TSX)
# ============================================================
COMPONENT_FIXES = [
    # SectionHeader: action.label без t()
    {
        "file": "components/ui/SectionHeader.tsx",
        "old": "          {action.label}",
        "new": "          {t(action.label)}",
    },
    # ProfileTabSwitcher: section.label без t()
    {
        "file": "features/profile/components/profile-form/ProfileTabSwitcher.tsx",
        "old": "            <span className=\"text-sm font-medium\">{section.label}</span>",
        "new": "            <span className=\"text-sm font-medium\">{t(section.label)}</span>",
    },
    # DeadlinesSection: daysLabel как строковый литерал
    {
        "file": "components/personal/DeadlinesSection.tsx",
        "old": "  const daysLabel = 'common.daysShort';",
        "new": "  const daysLabel = t('common.daysShort');",
    },
    {
        "file": "components/personal/DeadlinesSection.tsx",
        "old": "  const daysFullLabel = 'common.days';",
        "new": "  const daysFullLabel = t('common.days');",
    },
    # documents/page.tsx: description без t()
    {
        "file": "app/(main)/documents/page.tsx",
        "old": "    description: '(main).page.основной_документ_удостоверяющий',",
        "new": "    description: 'documents.descriptions.passport',",
    },
    {
        "file": "app/(main)/documents/page.tsx",
        "old": "    description: '(main).page.подтверждение_легального_въезда',",
        "new": "    description: 'documents.descriptions.migration_card',",
    },
    {
        "file": "app/(main)/documents/page.tsx",
        "old": "    description: '(main).page.разрешение_на_работу',",
        "new": "    description: 'documents.descriptions.patent',",
    },
    {
        "file": "app/(main)/documents/page.tsx",
        "old": "    description: '(main).page.миграционный_учт_по',",
        "new": "    description: 'documents.descriptions.registration',",
    },
    {
        "file": "app/(main)/documents/page.tsx",
        "old": "    description: '(main).page.идентификационный_номер_налогоплательщика',",
        "new": "    description: 'documents.descriptions.inn',",
    },
    {
        "file": "app/(main)/documents/page.tsx",
        "old": "    description: '(main).page.страховой_номер_индивидуального',",
        "new": "    description: 'documents.descriptions.snils',",
    },
    {
        "file": "app/(main)/documents/page.tsx",
        "old": "    description: '(main).page.добровольное_медицинское_страхование',",
        "new": "    description: 'documents.descriptions.dms',",
    },
    # documents/page.tsx: config.description без t()
    {
        "file": "app/(main)/documents/page.tsx",
        "old": "                        {config.description}",
        "new": "                        {t(config.description)}",
    },
    # documents/page.tsx: statusLabel без t()
    {
        "file": "app/(main)/documents/page.tsx",
        "old": "                        {statusLabel}",
        "new": "                        {t(statusLabel)}",
    },
    # documents/page.tsx: getStatusLabel — ключи
    {
        "file": "app/(main)/documents/page.tsx",
        "old": "      return '(main).page.не_заполнен';",
        "new": "      return 'documents.status.empty';",
    },
    {
        "file": "app/(main)/documents/page.tsx",
        "old": "      return '(main).page.частично';",
        "new": "      return 'documents.status.partial';",
    },
    {
        "file": "app/(main)/documents/page.tsx",
        "old": "      return '(main).page.заполнен';",
        "new": "      return 'documents.status.complete';",
    },
]


def set_nested(data: dict, dotted_key: str, value: str):
    """Установить значение по точечному ключу: 'a.b.c' -> data['a']['b']['c'] = value"""
    keys = dotted_key.split('.')
    current = data
    for k in keys[:-1]:
        if k not in current or not isinstance(current[k], dict):
            current[k] = {}
        current = current[k]
    current[keys[-1]] = value


def get_nested(data: dict, dotted_key: str):
    """Получить значение по точечному ключу"""
    keys = dotted_key.split('.')
    current = data
    for k in keys:
        if not isinstance(current, dict) or k not in current:
            return None
        current = current[k]
    return current


def is_placeholder(value) -> bool:
    """Проверить, является ли значение плейсхолдером (не переведено)"""
    if not isinstance(value, str):
        return False
    # Плейсхолдеры: "Title", "Createbackup", "Deleteaccount", и т.д.
    # Это слова без пробелов, начинающиеся с заглавной, без кириллицы
    if re.match(r'^[A-Z][a-z]+$', value):
        return True
    # Слитные слова: "Createbackup", "Deleteaccount"
    if re.match(r'^[A-Z][a-z]+[a-z]+$', value) and len(value) > 8:
        return True
    return False


def fix_json(locale_file: Path, fixes: dict) -> int:
    """Исправить переводы в JSON файле"""
    with open(locale_file, 'r', encoding='utf-8') as f:
        data = json.load(f)

    count = 0
    for dotted_key, correct_value in fixes.items():
        current = get_nested(data, dotted_key)
        if current is None or is_placeholder(current) or current == "Title" or current == "Subtitle":
            set_nested(data, dotted_key, correct_value)
            count += 1
            print(f"  [FIX] {dotted_key}: {current!r} -> {correct_value!r}")

    if count > 0 and not DRY_RUN:
        with open(locale_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')

    return count


def fix_component(fix: dict) -> bool:
    """Исправить компонент (замена строки)"""
    filepath = COMPONENTS / fix["file"]
    if not filepath.exists():
        print(f"  [SKIP] Файл не найден: {fix['file']}")
        return False

    content = filepath.read_text(encoding='utf-8')
    if fix["old"] not in content:
        # Может уже исправлено
        if fix["new"] in content:
            print(f"  [OK] Уже исправлено: {fix['file']}")
            return False
        print(f"  [WARN] Строка не найдена в {fix['file']}: {fix['old'][:60]}...")
        return False

    new_content = content.replace(fix["old"], fix["new"], 1)
    if not DRY_RUN:
        filepath.write_text(new_content, encoding='utf-8')
    print(f"  [FIX] {fix['file']}: замена выполнена")
    return True


def main():
    mode = "DRY RUN" if DRY_RUN else "ПРИМЕНЕНИЕ"
    print(f"{'='*60}")
    print(f"  Массовое исправление переводов [{mode}]")
    print(f"{'='*60}")

    total_fixes = 0

    # 1. Исправление ru.json
    print(f"\n--- ru.json ---")
    ru_file = LOCALES / 'ru.json'
    if ru_file.exists():
        total_fixes += fix_json(ru_file, RU_FIXES)

    # 2. Исправление en.json
    print(f"\n--- en.json ---")
    en_file = LOCALES / 'en.json'
    if en_file.exists():
        total_fixes += fix_json(en_file, EN_FIXES)

    # 3. Исправление компонентов
    print(f"\n--- Компоненты ---")
    for fix in COMPONENT_FIXES:
        if fix_component(fix):
            total_fixes += 1

    print(f"\n{'='*60}")
    print(f"  Итого исправлений: {total_fixes}")
    if DRY_RUN:
        print(f"  (DRY RUN — файлы НЕ изменены)")
        print(f"  Для применения: python3 scripts/fix_all_translation_issues.py")
    print(f"{'='*60}")


if __name__ == '__main__':
    main()
