#!/usr/bin/env python3
"""
Скрипт исправления проблем с переводами (раунд 3):
1. ChecksScreen.tsx — raw ключи в labels (ru/tg/ky)
2. CheckCard.tsx — raw ключи в labels (ru/tg/ky)
3. CalculatorsScreen.tsx — raw ключи в labels (ru/tg/ky)
4. StayCalculator.tsx — bare strings без t() (строки 116-118)
5. JSON файлы (ru/en/uz/tg/ky) — quickActions + services.calculator
"""

import json
import os

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(BASE, 'apps', 'frontend', 'src')
LOCALES = os.path.join(FRONTEND, 'locales')

fixes_applied = 0


def fix_file(path, replacements):
    """Замена строк в файле."""
    global fixes_applied
    with open(path, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    for old, new in replacements:
        if old in content:
            content = content.replace(old, new)
            fixes_applied += 1
        else:
            print(f"  [!] Не найдено: {old[:70]}...")

    if content != original:
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"  [OK] Исправлен: {os.path.relpath(path, BASE)}")
    else:
        print(f"  [--] Без изменений: {os.path.relpath(path, BASE)}")


# ============================================================
# 1. ChecksScreen.tsx
# ============================================================
print("\n=== 1. ChecksScreen.tsx — исправляем labels ===")
checks_screen = os.path.join(FRONTEND, 'components', 'checks', 'ChecksScreen.tsx')
fix_file(checks_screen, [
    ("ru: 'checks.checksscreen.проверки'", "ru: 'Проверки'"),
    ("tg: 'checks.checksscreen.санишо'", "tg: 'Санҷишҳо'"),
    ("ky: 'checks.checksscreen.текшеруулор'", "ky: 'Текшерүүлөр'"),
    ("ru: 'checks.checksscreen.проверьте_свои_документы'", "ru: 'Проверьте свои документы и статусы онлайн'"),
    ("tg: 'checks.checksscreen.уато_ва_вазъиятои'", "tg: 'Ҳуҷҷатҳо ва вазъиятҳои худро онлайн санҷед'"),
    ("ky: 'checks.checksscreen.документтериниз_менен_статустарынызды'", "ky: 'Документтериңизди жана статустарыңызды онлайн текшериңиз'"),
    ("ru: 'checks.checksscreen.запрет_на_въезд'", "ru: 'Запрет на въезд'"),
    ("tg: 'checks.checksscreen.манъи_воридот'", "tg: 'Манъи воридот'"),
    ("ky: 'checks.checksscreen.кирууго_тыюу'", "ky: 'Кирүүгө тыюу'"),
    ("ru: 'checks.checksscreen.проверьте_нет_ли'", "ru: 'Проверьте, нет ли ограничений на въезд в Россию'"),
    ("tg: 'checks.checksscreen.санед_ки_о'", "tg: 'Санҷед, ки оё маҳдудияти воридот ба Русия ҳаст'"),
    ("ky: 'checks.checksscreen.россияга_кирууго_чектоо'", "ky: 'Россияга кирүүгө чектөө бар-жогун текшериңиз'"),
    ("ru: 'checks.checksscreen.действительность_паспорта'", "ru: 'Действительность паспорта'"),
    ("tg: 'checks.checksscreen.эътибори_шиноснома'", "tg: 'Эътибори шиноснома'"),
    ("ky: 'checks.checksscreen.паспорттун_жарактуулугу'", "ky: 'Паспорттун жарактуулугу'"),
    ("ru: 'checks.checksscreen.проверка_по_базе'", "ru: 'Проверка по базе МВД России'"),
    ("tg: 'checks.checksscreen.саниш_аз_ри'", "tg: 'Санҷиш аз рӯи базаи ВКД Русия'"),
    ("ky: 'checks.checksscreen.россия_иим_базасы'", "ky: 'Россия ИИМ базасы боюнча текшерүү'"),
    ("ru: 'checks.checksscreen.статус_патента'", "ru: 'Статус патента'"),
    ("tg: 'checks.checksscreen.вазъияти_патент'", "tg: 'Вазъияти патент'"),
    ("ky: 'checks.checksscreen.патент_статусу'", "ky: 'Патент статусу'"),
    ("ru: 'checks.checksscreen.проверка_действительности_патента'", "ru: 'Проверка действительности патента на работу'"),
    ("tg: 'checks.checksscreen.саниши_эътибори_патенти'", "tg: 'Санҷиши эътибори патенти кор'"),
    ("ky: 'checks.checksscreen.жумуш_патентинин_жарактуулугун'", "ky: 'Жумуш патентинин жарактуулугун текшерүү'"),
    ("ru: 'checks.checksscreen.инн'", "ru: 'ИНН'"),
    ("tg: 'checks.checksscreen.инн'", "tg: 'ИНН'"),
    ("ky: 'checks.checksscreen.инн'", "ky: 'ИНН'"),
    ("ru: 'checks.checksscreen.проверка_индивидуального_номера'", "ru: 'Проверка индивидуального номера налогоплательщика'"),
    ("tg: 'checks.checksscreen.саниши_раами_инфиродии'", "tg: 'Санҷиши рақами инфиродии андозсупоранда'"),
    ("ky: 'checks.checksscreen.салык_толоочунун_жеке'", "ky: 'Салык төлөөчүнүн жеке номерин текшерүү'"),
    ("ru: 'checks.checksscreen.долги_фссп'", "ru: 'Долги ФССП'"),
    ("tg: 'checks.checksscreen.арзои_фссп'", "tg: 'Қарзҳои ФССП'"),
    ("ky: 'checks.checksscreen.фссп_карыздары'", "ky: 'ФССП карыздары'"),
    ("ru: 'checks.checksscreen.проверка_задолженностей_по'", "ru: 'Проверка задолженностей по исполнительным производствам'"),
    ("tg: 'checks.checksscreen.саниши_арздорио_аз'", "tg: 'Санҷиши қарздориҳо аз рӯи иҷроия'"),
    ("ky: 'checks.checksscreen.аткаруу_иштери_боюнча'", "ky: 'Аткаруу иштери боюнча карыздарды текшерүү'"),
    ("ru: 'checks.checksscreen.штрафы_гибдд'", "ru: 'Штрафы ГИБДД'"),
    ("tg: 'checks.checksscreen.аримаои_гибдд'", "tg: 'Ҷаримаҳои ГИБДД'"),
    ("ky: 'checks.checksscreen.жол_кыймылынын_айыбы'", "ky: 'Жол кыймылынын айыптары'"),
    ("ru: 'checks.checksscreen.проверка_неоплаченных_штрафов'", "ru: 'Проверка неоплаченных штрафов за нарушение ПДД'"),
    ("tg: 'checks.checksscreen.саниши_аримаои_пардохтнашуда'", "tg: 'Санҷиши ҷаримаҳои пардохтнашуда барои вайронкунии қоидаҳои роҳ'"),
    ("ky: 'checks.checksscreen.жол_эрежелерин_бузгандыгы'", "ky: 'Жол эрежелерин бузгандыгы үчүн төлөнбөгөн айыптарды текшерүү'"),
    ("ru: 'checks.checksscreen.разрешение_на_работу'", "ru: 'Разрешение на работу'"),
    ("tg: 'checks.checksscreen.иозатномаи_кор'", "tg: 'Иҷозатномаи кор'"),
    ("ky: 'checks.checksscreen.иш_уруксаты'", "ky: 'Иш уруксаты'"),
    ("ru: 'checks.checksscreen.проверка_действительности_разрешения'", "ru: 'Проверка действительности разрешения на работу'"),
    ("tg: 'checks.checksscreen.саниши_эътибори_иозатномаи'", "tg: 'Санҷиши эътибори иҷозатномаи кор'"),
    ("ky: 'checks.checksscreen.иш_уруксатынын_жарактуулугун'", "ky: 'Иш уруксатынын жарактуулугун текшерүү'"),
])


# ============================================================
# 2. CheckCard.tsx
# ============================================================
print("\n=== 2. CheckCard.tsx — исправляем labels.free ===")
check_card = os.path.join(FRONTEND, 'components', 'checks', 'CheckCard.tsx')
fix_file(check_card, [
    ("ru: 'checks.checkcard.бесплатно'", "ru: 'Бесплатно'"),
    ("tg: 'checks.checkcard.ройгон'", "tg: 'Ройгон'"),
    ("ky: 'checks.checkcard.акысыз'", "ky: 'Акысыз'"),
])


# ============================================================
# 3. CalculatorsScreen.tsx
# ============================================================
print("\n=== 3. CalculatorsScreen.tsx — исправляем labels ===")
calc_screen = os.path.join(FRONTEND, 'components', 'calculators', 'CalculatorsScreen.tsx')
fix_file(calc_screen, [
    ("ru: 'calculators.calculatorsscreen.калькуляторы'", "ru: 'Калькуляторы'"),
    ("tg: 'calculators.calculatorsscreen.исобкунако'", "tg: 'Ҳисобкунакҳо'"),
    ("ky: 'calculators.calculatorsscreen.калькуляторлор'", "ky: 'Калькуляторлор'"),
    ("ru: 'calculators.calculatorsscreen.рассчитайте_сроки_пребывания'", "ru: 'Рассчитайте сроки пребывания и стоимость патента'"),
    ("tg: 'calculators.calculatorsscreen.млати_истиомат_ва'", "tg: 'Мӯҳлати истиқомат ва нархи патентро ҳисоб кунед'"),
    ("ky: 'calculators.calculatorsscreen.жашоо_мнтн_жана'", "ky: 'Жашоо мөөнөтүн жана патент баасын эсептеңиз'"),
    ("ru: 'calculators.calculatorsscreen.правило_90180'", "ru: 'Правило 90/180'"),
    ("tg: 'calculators.calculatorsscreen.оидаи_90180'", "tg: 'Қоидаи 90/180'"),
    ("ru: 'calculators.calculatorsscreen.рассчитайте_оставшиеся_дни'", "ru: 'Рассчитайте оставшиеся дни пребывания в РФ без патента'"),
    ("tg: 'calculators.calculatorsscreen.рзои_боимондаи_будубош'", "tg: 'Рӯзҳои боқимондаи будубош дар Русия бе патентро ҳисоб кунед'"),
    ("ky: 'calculators.calculatorsscreen.россияда_патентсиз_калган'", "ky: 'Россияда патентсиз калган күндөрдү эсептеңиз'"),
    ("ru: 'calculators.calculatorsscreen.стоимость_патента'", "ru: 'Стоимость патента'"),
    ("tg: 'calculators.calculatorsscreen.нархи_патент'", "tg: 'Нархи патент'"),
    ("ky: 'calculators.calculatorsscreen.патенттин_баасы'", "ky: 'Патенттин баасы'"),
    ("ru: 'calculators.calculatorsscreen.узнайте_ежемесячный_платеж'", "ru: 'Узнайте ежемесячный платёж НДФЛ для вашего региона'"),
    ("tg: 'calculators.calculatorsscreen.пардохти_армоаи_адш'", "tg: 'Пардохти ҳармоҳаи АДШ барои минтақаи шуморо фаҳмед'"),
    ("ky: 'calculators.calculatorsscreen.аймагыыз_боюнча_айлык'", "ky: 'Аймагыңыз боюнча айлык НДФЛ төлөмүн билиңиз'"),
])


# ============================================================
# 4. StayCalculator.tsx — bare strings без t()
# ============================================================
print("\n=== 4. StayCalculator.tsx — оборачиваем bare strings в t() ===")
stay_calc = os.path.join(FRONTEND, 'features', 'services', 'components', 'StayCalculator.tsx')
fix_file(stay_calc, [
    ("? 'services.calculator.penalty.deportation'", "? t('services.calculator.penalty.deportation')"),
    (": 'services.calculator.penalty.noDeportation'", ": t('services.calculator.penalty.noDeportation')"),
])


# ============================================================
# 5. JSON файлы — quickActions + services.calculator
# ============================================================
print("\n=== 5. JSON файлы — quickActions + services.calculator ===")

TRANSLATIONS = {
    'ru': {
        'quickActions': {
            'selectPayment': 'Выберите платёж',
            'selectCalculator': 'Выберите калькулятор',
            'paymentOptions': {
                'transfer': {'title': 'Денежный перевод', 'description': 'Перевод денег на родину'},
                'patent': {'title': 'Патент (НДФЛ)', 'description': 'Оплата НДФЛ за патент'},
                'rvp': {'title': 'Госпошлина РВП', 'description': 'Разрешение на временное проживание'},
                'vnzh': {'title': 'Госпошлина ВНЖ', 'description': 'Вид на жительство'},
                'citizenship': {'title': 'Гражданство', 'description': 'Госпошлина за гражданство'},
                'registration': {'title': 'Регистрация', 'description': 'Постановка на учёт'},
                'invitation': {'title': 'Приглашение', 'description': 'Приглашение иностранца в РФ'},
                'fines': {'title': 'Штрафы', 'description': 'Оплата штрафов'},
                'exam': {'title': 'Экзамен', 'description': 'Русский язык, история, право'},
                'medical': {'title': 'Медкомиссия', 'description': 'Медицинское обследование'},
                'dms': {'title': 'Полис ДМС', 'description': 'Добровольное медстрахование'},
                'fingerprint': {'title': 'Дактилоскопия', 'description': 'Снятие отпечатков пальцев'},
                'notary': {'title': 'Нотариус', 'description': 'Перевод и заверение документов'},
                'workPermit': {'title': 'Разрешение на работу', 'description': 'Для визовых стран'},
                'driving': {'title': 'Водительские права', 'description': 'Обмен или получение прав'},
                'birthCert': {'title': 'Свидетельство о рождении', 'description': 'Регистрация рождения ребёнка'},
                'marriage': {'title': 'Регистрация брака', 'description': 'Заключение брака в РФ'},
            },
        },
        'services.calculator': {
            'title': 'Калькулятор 90/180',
            'region': 'Регион',
            'regionRequired': 'Выберите регион',
            'searchCityOrRegion': 'Поиск города или региона',
            'refresh': 'Обновить',
            'found': 'Найдено',
            'totalRegions': 'Всего регионов',
            'standardFines': 'Стандартные штрафы',
            'increasedFines': 'Повышенные штрафы',
            'periods.title': 'Периоды пребывания',
            'periods.count': '{count} записей',
            'periods.addEntry': 'Добавить период',
            'resetLimit.title': 'Сброс лимита',
            'resetLimit.date': '1 января {year} года',
            'penalty.title': 'Штрафные санкции',
            'deportationMode.title': 'Режим высылки',
        },
    },
    'en': {
        'quickActions': {
            'selectPayment': 'Select payment',
            'selectCalculator': 'Select calculator',
            'paymentOptions': {
                'transfer': {'title': 'Money transfer', 'description': 'Send money home'},
                'patent': {'title': 'Patent (Income Tax)', 'description': 'Patent tax payment'},
                'rvp': {'title': 'Temporary Residence Permit', 'description': 'Temporary residence permit fee'},
                'vnzh': {'title': 'Residence Permit', 'description': 'Residence permit fee'},
                'citizenship': {'title': 'Citizenship', 'description': 'State fee for citizenship'},
                'registration': {'title': 'Registration', 'description': 'Registration fee'},
                'invitation': {'title': 'Invitation', 'description': 'Invite foreigner to Russia'},
                'fines': {'title': 'Fines', 'description': 'Pay fines'},
                'exam': {'title': 'Exam', 'description': 'Russian language, history, law'},
                'medical': {'title': 'Medical exam', 'description': 'Medical examination'},
                'dms': {'title': 'Health insurance', 'description': 'Voluntary medical insurance'},
                'fingerprint': {'title': 'Fingerprinting', 'description': 'Fingerprint registration'},
                'notary': {'title': 'Notary', 'description': 'Translation and certification'},
                'workPermit': {'title': 'Work Permit', 'description': 'For visa countries'},
                'driving': {'title': 'Driver\'s license', 'description': 'Exchange or obtain license'},
                'birthCert': {'title': 'Birth certificate', 'description': 'Child birth registration'},
                'marriage': {'title': 'Marriage registration', 'description': 'Marriage registration in RF'},
            },
        },
        'services.calculator': {
            'title': '90/180 Calculator',
            'region': 'Region',
            'regionRequired': 'Select a region',
            'searchCityOrRegion': 'Search city or region',
            'refresh': 'Refresh',
            'found': 'Found',
            'totalRegions': 'Total regions',
            'standardFines': 'Standard fines',
            'increasedFines': 'Increased fines',
            'periods.title': 'Stay periods',
            'periods.count': '{count} records',
            'periods.addEntry': 'Add period',
            'resetLimit.title': 'Limit reset',
            'resetLimit.date': 'January 1, {year}',
            'penalty.title': 'Penalty sanctions',
            'deportationMode.title': 'Deportation mode',
        },
    },
    'uz': {
        'quickActions': {
            'selectPayment': 'To\'lovni tanlang',
            'selectCalculator': 'Kalkulyatorni tanlang',
            'paymentOptions': {
                'transfer': {'title': 'Pul o\'tkazmasi', 'description': 'Vatanga pul o\'tkazish'},
                'patent': {'title': 'Patent (JSHDS)', 'description': 'Patent uchun JSHDS to\'lovi'},
                'rvp': {'title': 'VMR davlat boji', 'description': 'Vaqtinchalik yashash ruxsati'},
                'vnzh': {'title': 'YOL davlat boji', 'description': 'Yashash uchun oliy litsenziya'},
                'citizenship': {'title': 'Fuqarolik', 'description': 'Fuqarolik uchun davlat boji'},
                'registration': {'title': 'Ro\'yxatdan o\'tish', 'description': 'Hisobga qo\'yish'},
                'invitation': {'title': 'Taklifnoma', 'description': 'Chet ellikni Rossiyaga taklif qilish'},
                'fines': {'title': 'Jarimalar', 'description': 'Jarimalarni to\'lash'},
                'exam': {'title': 'Imtihon', 'description': 'Rus tili, tarix, huquq'},
                'medical': {'title': 'Tibbiy ko\'rik', 'description': 'Tibbiy tekshiruv'},
                'dms': {'title': 'DMS polisi', 'description': 'Ixtiyoriy tibbiy sug\'urta'},
                'fingerprint': {'title': 'Barmoq izi', 'description': 'Barmoq izini olish'},
                'notary': {'title': 'Notarius', 'description': 'Tarjima va tasdiqlash'},
                'workPermit': {'title': 'Ish ruxsatnomasi', 'description': 'Vizali mamlakatlar uchun'},
                'driving': {'title': 'Haydovchilik guvohnomasi', 'description': 'Almashtirish yoki olish'},
                'birthCert': {'title': 'Tug\'ilganlik guvohnomasi', 'description': 'Bola tug\'ilishini ro\'yxatdan o\'tkazish'},
                'marriage': {'title': 'Nikoh ro\'yxati', 'description': 'RFda nikoh tuzish'},
            },
        },
        'services.calculator': {
            'title': '90/180 Kalkulyator',
            'region': 'Mintaqa',
            'regionRequired': 'Mintaqani tanlang',
            'searchCityOrRegion': 'Shahar yoki mintaqani qidiring',
            'refresh': 'Yangilash',
            'found': 'Topildi',
            'totalRegions': 'Jami mintaqalar',
            'standardFines': 'Standart jarimalar',
            'increasedFines': 'Oshirilgan jarimalar',
            'periods.title': 'Yashash davrlari',
            'periods.count': '{count} yozuv',
            'periods.addEntry': 'Davr qo\'shish',
            'resetLimit.title': 'Limit yangilanishi',
            'resetLimit.date': '{year} yil 1 yanvar',
            'penalty.title': 'Jarima sanksiyalari',
            'deportationMode.title': 'Deportatsiya rejimi',
        },
    },
    'tg': {
        'quickActions': {
            'selectPayment': 'Пардохтро интихоб кунед',
            'selectCalculator': 'Ҳисобкунакро интихоб кунед',
            'paymentOptions': {
                'transfer': {'title': 'Интиқоли пул', 'description': 'Фиристодани пул ба ватан'},
                'patent': {'title': 'Патент (АДШ)', 'description': 'Пардохти АДШ барои патент'},
                'rvp': {'title': 'Боҷи давлатии РВП', 'description': 'Иҷозати зиндагии муваққатӣ'},
                'vnzh': {'title': 'Боҷи давлатии ВНЖ', 'description': 'Иҷозати зиндагӣ'},
                'citizenship': {'title': 'Шаҳрвандӣ', 'description': 'Боҷи давлатии шаҳрвандӣ'},
                'registration': {'title': 'Бақайдгирӣ', 'description': 'Ба ҳисоб гузоштан'},
                'invitation': {'title': 'Даъватнома', 'description': 'Даъват кардани хориҷӣ ба Русия'},
                'fines': {'title': 'Ҷаримаҳо', 'description': 'Пардохти ҷаримаҳо'},
                'exam': {'title': 'Имтиҳон', 'description': 'Забони русӣ, таърих, ҳуқуқ'},
                'medical': {'title': 'Комиссияи тиббӣ', 'description': 'Муоинаи тиббӣ'},
                'dms': {'title': 'Полиси ДМС', 'description': 'Суғуртаи ихтиёрии тиббӣ'},
                'fingerprint': {'title': 'Дактилоскопия', 'description': 'Гирифтани нақши ангушт'},
                'notary': {'title': 'Нотариус', 'description': 'Тарҷума ва тасдиқ'},
                'workPermit': {'title': 'Иҷозатномаи кор', 'description': 'Барои кишварҳои визагӣ'},
                'driving': {'title': 'Гувоҳномаи ронандагӣ', 'description': 'Иваз ё гирифтани гувоҳнома'},
                'birthCert': {'title': 'Шаҳодатномаи таваллуд', 'description': 'Бақайдгирии таваллуди кӯдак'},
                'marriage': {'title': 'Бақайдгирии никоҳ', 'description': 'Баста шудани никоҳ дар Русия'},
            },
        },
        'services.calculator': {
            'title': 'Ҳисобкунаки 90/180',
            'region': 'Минтақа',
            'regionRequired': 'Минтақаро интихоб кунед',
            'searchCityOrRegion': 'Ҷустуҷӯи шаҳр ё минтақа',
            'refresh': 'Навсозӣ',
            'found': 'Ёфт шуд',
            'totalRegions': 'Ҳамагӣ минтақаҳо',
            'standardFines': 'Ҷаримаҳои стандартӣ',
            'increasedFines': 'Ҷаримаҳои баландшуда',
            'periods.title': 'Давраҳои истиқомат',
            'periods.count': '{count} сабт',
            'periods.addEntry': 'Илова кардани давра',
            'resetLimit.title': 'Нав шудани лимит',
            'resetLimit.date': '1 январи соли {year}',
            'penalty.title': 'Санксияҳои ҷаримавӣ',
            'deportationMode.title': 'Режими ихроҷ',
        },
    },
    'ky': {
        'quickActions': {
            'selectPayment': 'Төлөмдү тандаңыз',
            'selectCalculator': 'Калькуляторду тандаңыз',
            'paymentOptions': {
                'transfer': {'title': 'Акча которуу', 'description': 'Мекенге акча жөнөтүү'},
                'patent': {'title': 'Патент (НДФЛ)', 'description': 'Патент үчүн НДФЛ төлөмү'},
                'rvp': {'title': 'РВП мамбожу', 'description': 'Убактылуу жашоо уруксаты'},
                'vnzh': {'title': 'ВНЖ мамбожу', 'description': 'Жашоо уруксаты'},
                'citizenship': {'title': 'Жарандык', 'description': 'Жарандык үчүн мамбож'},
                'registration': {'title': 'Каттоо', 'description': 'Эсепке коюу'},
                'invitation': {'title': 'Чакыруу', 'description': 'Чет элдикти Россияга чакыруу'},
                'fines': {'title': 'Айыптар', 'description': 'Айыптарды төлөө'},
                'exam': {'title': 'Экзамен', 'description': 'Орус тили, тарых, укук'},
                'medical': {'title': 'Медкомиссия', 'description': 'Медициналык текшерүү'},
                'dms': {'title': 'ДМС полиси', 'description': 'Ыктыярдуу медициналык камсыздандыруу'},
                'fingerprint': {'title': 'Манжа изи', 'description': 'Манжа изин алуу'},
                'notary': {'title': 'Нотариус', 'description': 'Которуу жана күбөлөндүрүү'},
                'workPermit': {'title': 'Иш уруксаты', 'description': 'Визалуу өлкөлөр үчүн'},
                'driving': {'title': 'Айдоочулук күбөлүк', 'description': 'Алмаштыруу же алуу'},
                'birthCert': {'title': 'Туулгандык күбөлүк', 'description': 'Баланын туулушун каттоо'},
                'marriage': {'title': 'Нике каттоо', 'description': 'Россияда нике кыюу'},
            },
        },
        'services.calculator': {
            'title': '90/180 Калькулятор',
            'region': 'Аймак',
            'regionRequired': 'Аймакты тандаңыз',
            'searchCityOrRegion': 'Шаар же аймакты издеңиз',
            'refresh': 'Жаңылоо',
            'found': 'Табылды',
            'totalRegions': 'Бардык аймактар',
            'standardFines': 'Стандарттык айыптар',
            'increasedFines': 'Жогорулатылган айыптар',
            'periods.title': 'Жашоо мезгилдери',
            'periods.count': '{count} жазуу',
            'periods.addEntry': 'Мезгил кошуу',
            'resetLimit.title': 'Лимиттин жаңыруусу',
            'resetLimit.date': '{year}-жылдын 1-январы',
            'penalty.title': 'Айып санкциялары',
            'deportationMode.title': 'Депортация режими',
        },
    },
}

for lang in ['ru', 'en', 'uz', 'tg', 'ky']:
    filepath = os.path.join(LOCALES, f'{lang}.json')
    print(f"\n  [{lang}.json]")

    with open(filepath, 'r', encoding='utf-8') as f:
        data = json.load(f)

    tr = TRANSLATIONS[lang]
    changed = False

    # --- quickActions ---
    if 'quickActions' not in data:
        data['quickActions'] = {}

    qa = tr['quickActions']

    for key in ['selectPayment', 'selectCalculator']:
        old_val = data['quickActions'].get(key, '')
        new_val = qa[key]
        if old_val != new_val:
            data['quickActions'][key] = new_val
            changed = True
            fixes_applied += 1
            print(f"    [OK] quickActions.{key}: '{old_val}' -> '{new_val}'")

    if 'paymentOptions' not in data['quickActions']:
        data['quickActions']['paymentOptions'] = {}

    for opt_key, opt_data in qa['paymentOptions'].items():
        if opt_key not in data['quickActions']['paymentOptions']:
            data['quickActions']['paymentOptions'][opt_key] = {}

        for field, value in opt_data.items():
            old_val = data['quickActions']['paymentOptions'][opt_key].get(field, '')
            if old_val != value:
                data['quickActions']['paymentOptions'][opt_key][field] = value
                changed = True
                fixes_applied += 1
                print(f"    [OK] quickActions.paymentOptions.{opt_key}.{field}")

    # --- services.calculator ---
    if 'services' not in data:
        data['services'] = {}
    if 'calculator' not in data['services']:
        data['services']['calculator'] = {}

    calc = tr['services.calculator']
    for key, value in calc.items():
        if '.' in key:
            parts = key.split('.')
            parent, child = parts[0], parts[1]
            if parent not in data['services']['calculator']:
                data['services']['calculator'][parent] = {}
            old_val = data['services']['calculator'][parent].get(child, '')
            if old_val != value:
                data['services']['calculator'][parent][child] = value
                changed = True
                fixes_applied += 1
                print(f"    [OK] services.calculator.{key}")
        else:
            old_val = data['services']['calculator'].get(key, '')
            if old_val != value:
                data['services']['calculator'][key] = value
                changed = True
                fixes_applied += 1
                print(f"    [OK] services.calculator.{key}: '{old_val}' -> '{value}'")

    if changed:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
            f.write('\n')
        print(f"  [OK] Сохранён: {lang}.json")
    else:
        print(f"  [--] Без изменений: {lang}.json")

print(f"\n{'='*60}")
print(f"ИТОГО исправлений: {fixes_applied}")
print(f"{'='*60}")
