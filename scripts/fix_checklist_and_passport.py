#!/usr/bin/env python3
"""
Скрипт исправления:
1. PassportValidityModal.tsx — ошибка сборки (дублирование `t`) + неправильные labels
2. checklist/page.tsx — отсутствующие t() обёртки для deadline_passed/deadline_today
3. Все JSON-файлы переводов — недостающие/неправильные ключи checklist.*
"""

import json
import os
import re

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
LOCALES_DIR = os.path.join(BASE_DIR, 'apps', 'frontend', 'src', 'locales')
FRONTEND_SRC = os.path.join(BASE_DIR, 'apps', 'frontend', 'src')

# =============================================================================
# ЧАСТЬ 1: Исправление PassportValidityModal.tsx
# =============================================================================

def fix_passport_validity_modal():
    filepath = os.path.join(
        FRONTEND_SRC, 'components', 'prototype', 'services', 'PassportValidityModal.tsx'
    )

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # 1.1. Убираем import useTranslation (т.к. компонент использует свой labels dict)
    content = content.replace(
        "import { useTranslation } from '@/lib/i18n';\n\n",
        ""
    )

    # 1.2. Убираем вызов useTranslation() из компонента
    content = content.replace(
        "  const { t } = useTranslation();\n",
        ""
    )

    # 1.3. Исправляем labels — заменяем сырые ключи на реальный текст
    # Русские переводы
    labels_fixes = {
        # title
        "'prototype.passportvaliditymodal.проверка_паспорта'": "'Проверка паспорта'",
        # subtitle
        "'prototype.passportvaliditymodal.проверка_действительности_паспорта'": "'Проверка действительности паспорта РФ'",
        # series
        "'prototype.passportvaliditymodal.серия_паспорта'": "'Серия паспорта'",
        # number
        "'prototype.passportvaliditymodal.номер_паспорта'": "'Номер паспорта'",
        # checkButton
        "'prototype.passportvaliditymodal.проверить'": "'Проверить'",
        # valid
        "'prototype.passportvaliditymodal.паспорт_действителен'": "'Паспорт действителен'",
        # validDescription
        "'prototype.passportvaliditymodal.паспорт_не_найден'": "'Паспорт не найден в базе недействительных'",
        # invalid
        "'prototype.passportvaliditymodal.паспорт_недействителен'": "'Паспорт недействителен'",
        # invalidDescription
        "'prototype.passportvaliditymodal.паспорт_числится_в'": "'Паспорт числится в базе недействительных'",
        # notFound (duplicate key name — same as validDescription fix, handle separately)
        # notFoundDescription — already covered
        # unknown
        "'prototype.passportvaliditymodal.статус_неизвестен'": "'Статус неизвестен'",
        # unknownDescription
        "'prototype.passportvaliditymodal.не_удалось_определить'": "'Не удалось определить статус. Попробуйте позже.'",
        # checkAnother
        "'prototype.passportvaliditymodal.проверить_другой'": "'Проверить другой'",
        # done
        "'prototype.passportvaliditymodal.готово'": "'Готово'",
        # source
        "'prototype.passportvaliditymodal.источник'": "'Источник'",
        # checked
        "'prototype.passportvaliditymodal.проверено'": "'Проверено'",
        # testData
        "'prototype.passportvaliditymodal.тестовые_данные'": "'Тестовые данные'",
        # testDataWarning
        "'prototype.passportvaliditymodal.сервис_проверки_отключен'": "'Сервис проверки отключён. Показаны тестовые данные. Для реальной проверки используйте официальный сайт МВД.'",
        # fallbackWarning
        "'prototype.passportvaliditymodal.сервис_временно_недоступен'": "'Сервис временно недоступен. Попробуйте позже или проверьте на официальном сайте МВД.'",
        # officialSite
        "'prototype.passportvaliditymodal.официальный_сайт_мвд'": "'Официальный сайт МВД'",
        # infoText
        "'prototype.passportvaliditymodal.проверка_выполняется_через'": "'Проверка выполняется через базу недействительных паспортов МВД РФ. Если паспорт не найден в базе — он считается действительным.'",
        # error
        "'prototype.passportvaliditymodal.произошла_ошибка_при'": "'Произошла ошибка при проверке. Попробуйте позже.'",
        # recommendation
        "'prototype.passportvaliditymodal.рекомендация'": "'Рекомендация'",
        # invalidRecommendation
        "'prototype.passportvaliditymodal.если_ваш_паспорт'": "'Если ваш паспорт числится как недействительный, обратитесь в паспортный стол для выяснения причин и получения нового паспорта.'",
        # passportData
        "'prototype.passportvaliditymodal.данные_паспорта'": "'Данные паспорта'",
    }

    # Таджикские переводы
    tg_fixes = {
        "'prototype.passportvaliditymodal.саниши_шиноснома'": "'Санҷиши шиноснома'",
        "'prototype.passportvaliditymodal.саниши_эътибори_шиносномаи'": "'Санҷиши эътибори шиносномаи РФ'",
        "'prototype.passportvaliditymodal.силсилаи_шиноснома'": "'Силсилаи шиноснома'",
        "'prototype.passportvaliditymodal.раами_шиноснома'": "'Рақами шиноснома'",
        "'prototype.passportvaliditymodal.санидан'": "'Санҷидан'",
        "'prototype.passportvaliditymodal.шиноснома_эътибор_дорад'": "'Шиноснома эътибор дорад'",
        "'prototype.passportvaliditymodal.шиноснома_дар_базаи'": "'Шиноснома дар базаи беэътибор ёфт нашуд'",
        "'prototype.passportvaliditymodal.шиноснома_беэътибор_аст'": "'Шиноснома беэътибор аст'",
        "'prototype.passportvaliditymodal.шиноснома_фт_нашуд'": "'Шиноснома ёфт нашуд'",
        "'prototype.passportvaliditymodal.вазъият_номаълум'": "'Вазъият номаълум'",
        "'prototype.passportvaliditymodal.вазъияти_шиносномаро_муайян'": "'Вазъияти шиносномаро муайян кардан наметавонад. Баъдтар аз нав кӯшиш кунед.'",
        "'prototype.passportvaliditymodal.дигареро_санидан'": "'Дигареро санҷидан'",
        "'prototype.passportvaliditymodal.тайр'": "'Тайёр'",
        "'prototype.passportvaliditymodal.сарчашма'": "'Сарчашма'",
        "'prototype.passportvaliditymodal.санида_шуд'": "'Санҷида шуд'",
        "'prototype.passportvaliditymodal.маълумоти_озмоиш'": "'Маълумоти озмоишӣ'",
        "'prototype.passportvaliditymodal.хидмати_саниш_хомуш'": "'Хидмати санҷиш хомӯш аст. Маълумоти озмоишӣ нишон дода мешавад.'",
        "'prototype.passportvaliditymodal.хидмат_муваатан_дастрас'": "'Хидмат муваққатан дастрас нест. Баъдтар кӯшиш кунед.'",
        "'prototype.passportvaliditymodal.сайти_расмии_вкд'": "'Сайти расмии ВКД'",
        "'prototype.passportvaliditymodal.саниш_тавассути_базаи'": "'Санҷиш тавассути базаи шиносномаҳои беэътибори ВКД РФ анҷом дода мешавад.'",
        "'prototype.passportvaliditymodal.ангоми_саниш_хатог'": "'Ҳангоми санҷиш хатогӣ рӯй дод. Баъдтар кӯшиш кунед.'",
        "'prototype.passportvaliditymodal.тавсия'": "'Тавсия'",
        "'prototype.passportvaliditymodal.агар_шиносномаи_шумо'": "'Агар шиносномаи шумо ҳамчун беэътибор қайд шудааст, ба шӯъбаи шиноснома муроҷиат кунед.'",
        "'prototype.passportvaliditymodal.маълумоти_шиноснома'": "'Маълумоти шиноснома'",
    }

    # Кыргызские переводы
    ky_fixes = {
        "'prototype.passportvaliditymodal.паспорт_текшеруусу'": "'Паспорт текшерүүсү'",
        "'prototype.passportvaliditymodal.рф_паспортунун_жарактуулугун'": "'РФ паспортунун жарактуулугун текшерүү'",
        "'prototype.passportvaliditymodal.паспорт_сериясы'": "'Паспорт сериясы'",
        "'prototype.passportvaliditymodal.паспорт_номери'": "'Паспорт номери'",
        "'prototype.passportvaliditymodal.текшеруу'": "'Текшерүү'",
        "'prototype.passportvaliditymodal.паспорт_жарактуу'": "'Паспорт жарактуу'",
        "'prototype.passportvaliditymodal.паспорт_жарактуу_эмес'": "'Паспорт жарактуу эмес'",
        "'prototype.passportvaliditymodal.паспорт_табылган_жок'": "'Паспорт табылган жок'",
        "'prototype.passportvaliditymodal.статусу_белгисиз'": "'Статусу белгисиз'",
        "'prototype.passportvaliditymodal.паспорт_статусун_аныктоо'": "'Паспорт статусун аныктоо мүмкүн болгон жок. Кийинчерээк аракет кылыңыз.'",
        "'prototype.passportvaliditymodal.башкасын_текшеруу'": "'Башкасын текшерүү'",
        "'prototype.passportvaliditymodal.даяр'": "'Даяр'",
        "'prototype.passportvaliditymodal.булак'": "'Булак'",
        "'prototype.passportvaliditymodal.текшерилди'": "'Текшерилди'",
        "'prototype.passportvaliditymodal.тест_маалыматтары'": "'Тест маалыматтары'",
        "'prototype.passportvaliditymodal.текшеруу_кызматы_ошурулду'": "'Текшерүү кызматы өчүрүлдү. Тест маалыматтары көрсөтүлүүдө.'",
        "'prototype.passportvaliditymodal.кызмат_убактылуу_жеткиликтуу'": "'Кызмат убактылуу жеткиликсиз. Кийинчерээк аракет кылыңыз.'",
        "'prototype.passportvaliditymodal.иимдин_расмий_сайты'": "'ИИМдин расмий сайты'",
        "'prototype.passportvaliditymodal.текшеруу_россия_ииминин'": "'Текшерүү Россия ИИМинин жарактуу эмес паспорттор базасы аркылуу жүргүзүлөт.'",
        "'prototype.passportvaliditymodal.текшеруу_учурунда_ката'": "'Текшерүү учурунда ката кетти. Кийинчерээк аракет кылыңыз.'",
        "'prototype.passportvaliditymodal.сунуштама'": "'Сунуштама'",
        "'prototype.passportvaliditymodal.эгерде_сиздин_паспортунуз'": "'Эгерде сиздин паспортуңуз жарактуу эмес деп белгиленсе, паспорт бөлүмүнө кайрылыңыз.'",
        "'prototype.passportvaliditymodal.паспорт_маалыматтары'": "'Паспорт маалыматтары'",
    }

    all_fixes = {**labels_fixes, **tg_fixes, **ky_fixes}
    for old, new in all_fixes.items():
        content = content.replace(old, new)

    # 1.4. Исправляем голые строки в JSX — заменяем {'key'} на {t('key')}
    jsx_bare_strings = [
        ("{'series'}", "{t('series')}"),
        ("{'number'}", "{t('number')}"),
        ("{'checking'}", "{t('checking')}"),
        ("{'recommendation'}", "{t('recommendation')}"),
        ("{'source'}", "{t('source')}"),
        ("{'checked'}", "{t('checked')}"),
        ("{'done'}", "{t('done')}"),
        ("{'subtitle'}", "{t('subtitle')}"),
    ]
    for old, new in jsx_bare_strings:
        content = content.replace(old, new)

    # Проверяем что файл изменился
    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  [OK] PassportValidityModal.tsx — исправлено")
    else:
        print(f"  [SKIP] PassportValidityModal.tsx — изменений нет")

    return content != original


# =============================================================================
# ЧАСТЬ 2: Исправление checklist/page.tsx
# =============================================================================

def fix_checklist_page():
    filepath = os.path.join(
        FRONTEND_SRC, 'app', '(main)', 'checklist', 'page.tsx'
    )

    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content

    # 2.1. Обёртываем deadline_passed и deadline_today в t()
    content = content.replace(
        "? 'checklist.deadline_passed'",
        "? t('checklist.deadline_passed')"
    )
    content = content.replace(
        "? 'checklist.deadline_today'",
        "? t('checklist.deadline_today')"
    )

    if content != original:
        with open(filepath, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  [OK] checklist/page.tsx — исправлено")
    else:
        print(f"  [SKIP] checklist/page.tsx — изменений нет")

    return content != original


# =============================================================================
# ЧАСТЬ 3: Исправление JSON-файлов переводов
# =============================================================================

# Полный набор ключей checklist для каждого языка
CHECKLIST_TRANSLATIONS = {
    'ru': {
        'title': 'Чеклист документов',
        'subtitle': 'Моделируйте ситуацию и отслеживайте сроки',
        'simulator_title': 'Симулятор сроков',
        'use_profile_data': 'Из профиля',
        'entry_date': 'Дата въезда в РФ',
        'citizenship': 'Гражданство',
        'select_citizenship': 'Выберите гражданство',
        'entry_point': 'Пункт въезда',
        'purpose': 'Цель визита',
        'required_documents': 'Необходимые документы',
        'fill_simulator': 'Заполните дату въезда и гражданство для расчёта сроков',
        'info': 'Отмечайте документы по мере их получения.',
        'legal_disclaimer': 'Информация носит справочный характер. Сроки могут отличаться в зависимости от региона и индивидуальной ситуации.',
        'migration_card_info': 'Выдаётся при пересечении границы',
        'eaeu_info': 'Граждане ЕАЭС (Казахстан, Кыргызстан, Армения, Беларусь) имеют упрощённые условия пребывания и трудоустройства в РФ.',
        'deadline_date': 'До {{date}}',
        'deadline_passed': 'Просрочено',
        'deadline_today': 'Сегодня',
        'days_left': 'Осталось {{count}} дн.',
        'term_info': 'Срок: {{days}} дней с момента въезда',
        # Пункты въезда
        'entry_air': 'Авиаперелёт',
        'entry_land_kz': 'Авто/ж/д из Казахстана',
        'entry_land_by': 'Авто/ж/д из Беларуси',
        'entry_land_other': 'Авто/ж/д из другой страны',
        # Цели визита
        'purpose_work': 'Работа',
        'purpose_private': 'Частный визит',
        'purpose_tourism': 'Туризм',
        'purpose_study': 'Учёба',
        'purpose_business': 'Деловой визит',
        'purpose_transit': 'Транзит',
        'purpose_official': 'Служебный визит',
        # Страны
        'countries': {
            'uzbekistan': 'Узбекистан',
            'tajikistan': 'Таджикистан',
            'kyrgyzstan': 'Кыргызстан',
            'kazakhstan': 'Казахстан',
            'armenia': 'Армения',
            'azerbaijan': 'Азербайджан',
            'moldova': 'Молдова',
            'belarus': 'Беларусь',
            'ukraine': 'Украина',
            'georgia': 'Грузия',
            'turkmenistan': 'Туркменистан',
            'other_country': 'Другая страна',
        },
        # Пункты чеклиста
        'items': {
            'migration_card': 'Миграционная карта',
            'registration': 'Регистрация по месту пребывания',
            'medical': 'Медицинские справки',
            'patent': 'Подача заявления на патент',
            'fingerprints': 'Дактилоскопия',
            'stay_limit': 'Срок пребывания (90 дней)',
            'enrollment': 'Подтверждение зачисления в вуз',
        },
        # Риски
        'risks': {
            'registration': 'Штраф 2-5 тыс. ₽, возможна депортация и запрет въезда',
            'medical': 'Без справок патент не выдадут',
            'patent': 'Штраф 5-7 тыс. ₽, невозможность легально работать',
            'fingerprints': 'Обязательно при подаче на патент',
            'stay_limit': 'Нарушение режима пребывания, депортация, запрет въезда на 3-10 лет',
            'enrollment': 'Без подтверждения зачисления студенческая виза может быть аннулирована',
        },
    },
    'en': {
        'title': 'Document Checklist',
        'subtitle': 'Simulate your situation and track deadlines',
        'simulator_title': 'Deadline Simulator',
        'use_profile_data': 'From profile',
        'entry_date': 'Entry date to Russia',
        'citizenship': 'Citizenship',
        'select_citizenship': 'Select citizenship',
        'entry_point': 'Entry point',
        'purpose': 'Purpose of visit',
        'required_documents': 'Required Documents',
        'fill_simulator': 'Enter your entry date and citizenship to calculate deadlines',
        'info': 'Check off documents as you receive them.',
        'legal_disclaimer': 'This information is for reference only. Deadlines may vary by region and individual circumstances.',
        'migration_card_info': 'Issued at border crossing',
        'eaeu_info': 'Eurasian Economic Union citizens (Kazakhstan, Kyrgyzstan, Armenia, Belarus) have simplified conditions for staying and working in Russia.',
        'deadline_date': 'Until {{date}}',
        'deadline_passed': 'Overdue',
        'deadline_today': 'Today',
        'days_left': '{{count}} days left',
        'term_info': 'Period: {{days}} days from the date of entry',
        'entry_air': 'By air',
        'entry_land_kz': 'Road/Rail from Kazakhstan',
        'entry_land_by': 'Road/Rail from Belarus',
        'entry_land_other': 'Road/Rail from other country',
        'purpose_work': 'Work',
        'purpose_private': 'Private visit',
        'purpose_tourism': 'Tourism',
        'purpose_study': 'Study',
        'purpose_business': 'Business',
        'purpose_transit': 'Transit',
        'purpose_official': 'Official visit',
        'countries': {
            'uzbekistan': 'Uzbekistan',
            'tajikistan': 'Tajikistan',
            'kyrgyzstan': 'Kyrgyzstan',
            'kazakhstan': 'Kazakhstan',
            'armenia': 'Armenia',
            'azerbaijan': 'Azerbaijan',
            'moldova': 'Moldova',
            'belarus': 'Belarus',
            'ukraine': 'Ukraine',
            'georgia': 'Georgia',
            'turkmenistan': 'Turkmenistan',
            'other_country': 'Other country',
        },
        'items': {
            'migration_card': 'Migration Card',
            'registration': 'Registration at place of stay',
            'medical': 'Medical certificates',
            'patent': 'Work patent application',
            'fingerprints': 'Fingerprinting',
            'stay_limit': 'Period of stay (90 days)',
            'enrollment': 'Confirmation of university enrollment',
        },
        'risks': {
            'registration': 'Fine 2-5K ₽, possible deportation and entry ban',
            'medical': 'Patent will not be issued without certificates',
            'patent': 'Fine 5-7K ₽, unable to work legally',
            'fingerprints': 'Required when applying for patent',
            'stay_limit': 'Violation of stay rules, deportation, 3-10 year entry ban',
            'enrollment': 'Student visa may be cancelled without enrollment confirmation',
        },
    },
    'uz': {
        'title': 'Hujjatlar roʻyxati',
        'subtitle': 'Vaziyatingizni modellashtiring va muddatlarni kuzating',
        'simulator_title': 'Muddat simulyatori',
        'use_profile_data': 'Profildan',
        'entry_date': 'Rossiyaga kirish sanasi',
        'citizenship': 'Fuqarolik',
        'select_citizenship': 'Fuqarolikni tanlang',
        'entry_point': 'Kirish nuqtasi',
        'purpose': 'Tashrif maqsadi',
        'required_documents': 'Zarur hujjatlar',
        'fill_simulator': 'Muddatlarni hisoblash uchun kirish sanasi va fuqarolikni kiriting',
        'info': 'Hujjatlarni olgach belgilang.',
        'legal_disclaimer': 'Maʼlumot maʼlumotnoma xarakteriga ega. Muddatlar mintaqa va individual holatlarga qarab farq qilishi mumkin.',
        'migration_card_info': 'Chegaradan oʻtishda beriladi',
        'eaeu_info': 'YaIIT fuqarolari (Qozogʻiston, Qirgʻiziston, Armaniston, Belarus) RF da yashash va ishlash boʻyicha soddalashtirilgan shartlarga ega.',
        'deadline_date': '{{date}} gacha',
        'deadline_passed': 'Muddati oʻtgan',
        'deadline_today': 'Bugun',
        'days_left': '{{count}} kun qoldi',
        'term_info': 'Muddat: kirish kunidan {{days}} kun',
        'entry_air': 'Samolyot bilan',
        'entry_land_kz': 'Qozogʻistondan avto/temir yoʻl',
        'entry_land_by': 'Belarusdan avto/temir yoʻl',
        'entry_land_other': 'Boshqa mamlakatdan avto/temir yoʻl',
        'purpose_work': 'Ish',
        'purpose_private': 'Shaxsiy tashrif',
        'purpose_tourism': 'Turizm',
        'purpose_study': 'Oʻqish',
        'purpose_business': 'Biznes',
        'purpose_transit': 'Tranzit',
        'purpose_official': 'Rasmiy tashrif',
        'countries': {
            'uzbekistan': 'Oʻzbekiston',
            'tajikistan': 'Tojikiston',
            'kyrgyzstan': 'Qirgʻiziston',
            'kazakhstan': 'Qozogʻiston',
            'armenia': 'Armaniston',
            'azerbaijan': 'Ozarbayjon',
            'moldova': 'Moldova',
            'belarus': 'Belarus',
            'ukraine': 'Ukraina',
            'georgia': 'Gruziya',
            'turkmenistan': 'Turkmaniston',
            'other_country': 'Boshqa mamlakat',
        },
        'items': {
            'migration_card': 'Migratsiya kartasi',
            'registration': 'Yashash joyida roʻyxatga olish',
            'medical': 'Tibbiy maʼlumotnomalar',
            'patent': 'Ish patentiga ariza',
            'fingerprints': 'Barmoq izlari',
            'stay_limit': 'Yashash muddati (90 kun)',
            'enrollment': 'Universitetga qabul qilinganlik tasdiqi',
        },
        'risks': {
            'registration': 'Jarima 2-5 ming ₽, deportatsiya va kirish taqiqi mumkin',
            'medical': 'Maʼlumotnomalar boʻlmasa patent berilmaydi',
            'patent': 'Jarima 5-7 ming ₽, qonuniy ishlash imkoniyati yoʻq',
            'fingerprints': 'Patentga ariza berishda majburiy',
            'stay_limit': 'Yashash tartibini buzish, deportatsiya, 3-10 yilga kirish taqiqi',
            'enrollment': 'Qabul tasdig\'isiz talaba vizasi bekor qilinishi mumkin',
        },
    },
    'tg': {
        'title': 'Рӯйхати ҳуҷҷатҳо',
        'subtitle': 'Вазъиятро моделсозӣ кунед ва мӯҳлатҳоро назорат кунед',
        'simulator_title': 'Симулятори мӯҳлатҳо',
        'use_profile_data': 'Аз профил',
        'entry_date': 'Санаи воридшавӣ ба РФ',
        'citizenship': 'Шаҳрвандӣ',
        'select_citizenship': 'Шаҳрвандиро интихоб кунед',
        'entry_point': 'Нуқтаи воридшавӣ',
        'purpose': 'Мақсади ташриф',
        'required_documents': 'Ҳуҷҷатҳои зарурӣ',
        'fill_simulator': 'Барои ҳисоби мӯҳлатҳо санаи воридшавӣ ва шаҳрвандиро ворид кунед',
        'info': 'Ҳуҷҷатҳоро пас аз гирифтан қайд кунед.',
        'legal_disclaimer': 'Маълумот хусусияти маълумотномавӣ дорад. Мӯҳлатҳо аз минтақа вобаста фарқ карда метавонанд.',
        'migration_card_info': 'Ҳангоми гузаштан аз сарҳад дода мешавад',
        'eaeu_info': 'Шаҳрвандони ИОИА (Қазоқистон, Қирғизистон, Арманистон, Беларус) шартҳои соддакардашуда доранд.',
        'deadline_date': 'То {{date}}',
        'deadline_passed': 'Мӯҳлат гузашт',
        'deadline_today': 'Имрӯз',
        'days_left': '{{count}} рӯз монд',
        'term_info': 'Мӯҳлат: {{days}} рӯз аз лаҳзаи воридшавӣ',
        'entry_air': 'Бо ҳавопаймо',
        'entry_land_kz': 'Аз Қазоқистон бо авто/роҳи оҳан',
        'entry_land_by': 'Аз Беларус бо авто/роҳи оҳан',
        'entry_land_other': 'Аз кишвари дигар бо авто/роҳи оҳан',
        'purpose_work': 'Кор',
        'purpose_private': 'Ташрифи шахсӣ',
        'purpose_tourism': 'Сайёҳӣ',
        'purpose_study': 'Таҳсил',
        'purpose_business': 'Тиҷоратӣ',
        'purpose_transit': 'Транзит',
        'purpose_official': 'Ташрифи расмӣ',
        'countries': {
            'uzbekistan': 'Ӯзбекистон',
            'tajikistan': 'Тоҷикистон',
            'kyrgyzstan': 'Қирғизистон',
            'kazakhstan': 'Қазоқистон',
            'armenia': 'Арманистон',
            'azerbaijan': 'Озарбойҷон',
            'moldova': 'Молдова',
            'belarus': 'Беларус',
            'ukraine': 'Украина',
            'georgia': 'Гурҷистон',
            'turkmenistan': 'Туркманистон',
            'other_country': 'Кишвари дигар',
        },
        'items': {
            'migration_card': 'Кортаи муҳоҷират',
            'registration': 'Бақайдгирӣ дар ҷойи зист',
            'medical': 'Маълумотномаҳои тиббӣ',
            'patent': 'Аризаи патенти корӣ',
            'fingerprints': 'Дактилоскопия',
            'stay_limit': 'Мӯҳлати истиқомат (90 рӯз)',
            'enrollment': 'Тасдиқи қабул ба донишгоҳ',
        },
        'risks': {
            'registration': 'Ҷарима 2-5 ҳазор ₽, депортатсия ва манъи воридшавӣ имконпазир',
            'medical': 'Бе маълумотнома патент дода намешавад',
            'patent': 'Ҷарима 5-7 ҳазор ₽, имконияти қонунӣ кор кардан нест',
            'fingerprints': 'Ҳангоми додани ариза барои патент ҳатмист',
            'stay_limit': 'Вайронкунии тартиби истиқомат, депортатсия, манъи воридшавӣ 3-10 сол',
            'enrollment': 'Бе тасдиқи қабул визаи донишҷӯйӣ бекор карда мешавад',
        },
    },
    'ky': {
        'title': 'Документтер тизмеси',
        'subtitle': 'Жагдайыңызды моделдеп, мөөнөттөрдү көзөмөлдөңүз',
        'simulator_title': 'Мөөнөт симулятору',
        'use_profile_data': 'Профилден',
        'entry_date': 'РФга кирген дата',
        'citizenship': 'Жарандык',
        'select_citizenship': 'Жарандыкты тандаңыз',
        'entry_point': 'Кирүү пункту',
        'purpose': 'Баруу максаты',
        'required_documents': 'Зарыл документтер',
        'fill_simulator': 'Мөөнөттөрдү эсептөө үчүн кирген датаны жана жарандыкты киргизиңиз',
        'info': 'Документтерди алган сайын белгилеңиз.',
        'legal_disclaimer': 'Маалымат маалымдама мүнөзүнө ээ. Мөөнөттөр аймакка жана жеке жагдайга жараша айырмаланышы мүмкүн.',
        'migration_card_info': 'Чек арадан өткөндө берилет',
        'eaeu_info': 'ЕАЭБ жарандары (Казакстан, Кыргызстан, Армения, Беларусь) РФда жашоо жана иштөө боюнча жеңилдетилген шарттарга ээ.',
        'deadline_date': '{{date}} чейин',
        'deadline_passed': 'Мөөнөтү өткөн',
        'deadline_today': 'Бүгүн',
        'days_left': '{{count}} күн калды',
        'term_info': 'Мөөнөт: кирген күндөн {{days}} күн',
        'entry_air': 'Учак менен',
        'entry_land_kz': 'Казакстандан авто/темир жол',
        'entry_land_by': 'Беларустан авто/темир жол',
        'entry_land_other': 'Башка өлкөдөн авто/темир жол',
        'purpose_work': 'Иш',
        'purpose_private': 'Жеке баруу',
        'purpose_tourism': 'Туризм',
        'purpose_study': 'Окуу',
        'purpose_business': 'Бизнес',
        'purpose_transit': 'Транзит',
        'purpose_official': 'Расмий баруу',
        'countries': {
            'uzbekistan': 'Өзбекстан',
            'tajikistan': 'Тажикстан',
            'kyrgyzstan': 'Кыргызстан',
            'kazakhstan': 'Казакстан',
            'armenia': 'Армения',
            'azerbaijan': 'Азербайжан',
            'moldova': 'Молдова',
            'belarus': 'Беларусь',
            'ukraine': 'Украина',
            'georgia': 'Грузия',
            'turkmenistan': 'Түркмөнстан',
            'other_country': 'Башка өлкө',
        },
        'items': {
            'migration_card': 'Миграция картасы',
            'registration': 'Жашаган жерде каттоо',
            'medical': 'Медициналык справкалар',
            'patent': 'Жумуш патентине арыз',
            'fingerprints': 'Манжа изи',
            'stay_limit': 'Жашоо мөөнөтү (90 күн)',
            'enrollment': 'Университетке кабыл алуу тастыктамасы',
        },
        'risks': {
            'registration': 'Айып 2-5 миң ₽, депортация жана кирүүгө тыюу мүмкүн',
            'medical': 'Справкасыз патент берилбейт',
            'patent': 'Айып 5-7 миң ₽, мыйзамдуу иштөө мүмкүнчүлүгү жок',
            'fingerprints': 'Патентке арыз бергенде милдеттүү',
            'stay_limit': 'Жашоо тартибин бузуу, депортация, 3-10 жылга кирүүгө тыюу',
            'enrollment': 'Кабыл алуу тастыктамасысыз студенттик виза жокко чыгарылышы мүмкүн',
        },
    },
}


def deep_merge(base: dict, updates: dict) -> dict:
    """Глубокое объединение словарей — обновляет только значения, не удаляет существующие."""
    result = base.copy()
    for key, value in updates.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def fix_translations():
    """Обновляет все JSON-файлы переводов с недостающими/неправильными ключами checklist."""

    for lang, translations in CHECKLIST_TRANSLATIONS.items():
        filepath = os.path.join(LOCALES_DIR, f'{lang}.json')

        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Получаем или создаём секцию checklist
        if 'checklist' not in data:
            data['checklist'] = {}

        # Глубокое объединение — обновляем существующие и добавляем новые
        data['checklist'] = deep_merge(data['checklist'], translations)

        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')

        print(f"  [OK] {lang}.json — обновлены ключи checklist")


# =============================================================================
# MAIN
# =============================================================================

def main():
    print("=" * 70)
    print("Скрипт исправления: PassportValidityModal + Checklist + Переводы")
    print("=" * 70)

    print("\n1. Исправление PassportValidityModal.tsx (ошибка сборки)...")
    fix_passport_validity_modal()

    print("\n2. Исправление checklist/page.tsx (отсутствующие t() обёртки)...")
    fix_checklist_page()

    print("\n3. Обновление JSON-файлов переводов (5 языков)...")
    fix_translations()

    print("\n" + "=" * 70)
    print("Готово! Все исправления применены.")
    print("=" * 70)


if __name__ == '__main__':
    main()
