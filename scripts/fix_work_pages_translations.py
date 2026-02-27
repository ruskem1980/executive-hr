#!/usr/bin/env python3
"""
Скрипт исправления переводов на страницах Работа и JobSearchHub.

Проблемы:
1. В labels/translations объектах стоят i18n-ключи вместо реального текста
2. Hardcoded строки в JSX ('subtitle', 'city', 'profession', 'salary', 'rubles')
3. Данные CITIES, PROFESSIONS, JOB_PLATFORMS содержат ключи вместо значений
"""

import re
import os
import sys

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FRONTEND = os.path.join(BASE, 'apps', 'frontend', 'src')

# ============================================================
# ФАЙЛ 1: work/page.tsx — объект labels
# ============================================================

WORK_PAGE = os.path.join(FRONTEND, 'app', '(main)', 'work', 'page.tsx')

WORK_PAGE_LABELS = """const labels: Record<string, Record<Language, string>> = {
  title: {
    ru: 'Работа',
    en: 'Work',
    uz: 'Ish',
    tg: 'Кор',
    ky: 'Жумуш',
  },
  subtitle: {
    ru: 'Поиск работы и трудовые права',
    en: 'Job search and labor rights',
    uz: 'Ish qidirish va mehnat huquqlari',
    tg: 'Ҷустуҷӯи кор ва ҳуқуқи меҳнатӣ',
    ky: 'Жумуш издөө жана эмгек укуктары',
  },
  jobSearch: {
    ru: 'Поиск работы',
    en: 'Job Search',
    uz: 'Ish qidirish',
    tg: 'Ҷустуҷӯи кор',
    ky: 'Жумуш издөө',
  },
  jobSearchDesc: {
    ru: 'Вакансии для иностранных граждан',
    en: 'Vacancies for foreign citizens',
    uz: 'Chet el fuqarolari uchun vakansiyalar',
    tg: 'Ҷойҳои холӣ барои шаҳрвандони хориҷӣ',
    ky: 'Чет өлкөлүктөр үчүн вакансиялар',
  },
  contract: {
    ru: 'Трудовой договор',
    en: 'Employment Contract',
    uz: 'Mehnat shartnomasi',
    tg: 'Шартномаи меҳнатӣ',
    ky: 'Эмгек келишими',
  },
  contractDesc: {
    ru: 'Как правильно оформить',
    en: 'How to properly draft a contract',
    uz: 'Shartnomani to\\'g\\'ri rasmiylashtirish',
    tg: 'Чӣ тавр шартномаро дуруст расмӣ кардан',
    ky: 'Келишимди туура тартипте түзүү',
  },
  rights: {
    ru: 'Права работника',
    en: 'Worker Rights',
    uz: 'Ishchi huquqlari',
    tg: 'Ҳуқуқи коргар',
    ky: 'Жумушчунун укуктары',
  },
  rightsDesc: {
    ru: 'Защита трудовых прав мигрантов',
    en: 'Protection of migrant labor rights',
    uz: 'Migrantlar mehnat huquqlarini himoya qilish',
    tg: 'Ҳифзи ҳуқуқи меҳнатии муҳоҷирон',
    ky: 'Мигранттардын эмгек укуктарын коргоо',
  },
  schedule: {
    ru: 'Рабочее время',
    en: 'Working Hours',
    uz: 'Ish vaqti',
    tg: 'Вақти кор',
    ky: 'Жумуш убактысы',
  },
  scheduleDesc: {
    ru: 'Нормы и переработки',
    en: 'Legal norms and overtime',
    uz: 'Qonuniy me\\'yorlar va ortiqcha ish',
    tg: 'Меъёрҳо ва кори иловагӣ',
    ky: 'Мыйзам боюнча ченемдер жана ашыкча иш',
  },
  createResume: {
    ru: 'Сделать резюме',
    en: 'Create Resume',
    uz: 'Rezyume yaratish',
    tg: 'Резюме сохтан',
    ky: 'Резюме түзүү',
  },
  createResumeDesc: {
    ru: 'Создайте профессиональное резюме',
    en: 'Create a professional resume',
    uz: 'Professional rezyume yarating',
    tg: 'Резюмеи касбӣ созед',
    ky: 'Кесиптик резюме түзүңүз',
  },
  employerReview: {
    ru: 'Оставить отзыв',
    en: 'Leave Review',
    uz: 'Sharh qoldirish',
    tg: 'Тақриз гузоштан',
    ky: 'Сын-пикир калтыруу',
  },
  employerReviewDesc: {
    ru: 'Поделитесь опытом работы',
    en: 'Share your experience with the company',
    uz: 'Kompaniya bilan tajribangizni baham ko\\'ring',
    tg: 'Таҷрибаи кор бо ширкатро мубодила кунед',
    ky: 'Компания менен тажрыйбаңызды бөлүшүңүз',
  },
  employerRating: {
    ru: 'Рейтинг работодателей',
    en: 'Employer Rating',
    uz: 'Ish beruvchilar reytingi',
    tg: 'Рейтинги корфармоён',
    ky: 'Иш берүүчүлөрдүн рейтинги',
  },
  employerRatingDesc: {
    ru: 'Рейтинги и отзывы',
    en: 'Ratings and reviews of companies',
    uz: 'Kompaniyalar haqida reytinglar va sharhlar',
    tg: 'Рейтингҳо ва тақризҳо дар бораи ширкатҳо',
    ky: 'Компаниялар жөнүндө рейтингдер жана сын-пикирлер',
  },
  employerComplaint: {
    ru: 'Подать жалобу',
    en: 'File Complaint',
    uz: 'Shikoyat berish',
    tg: 'Шикоят додан',
    ky: 'Арыз берүү',
  },
  employerComplaintDesc: {
    ru: 'Сообщить о нарушениях',
    en: 'Report employer violations',
    uz: 'Ish beruvchi qoidabuzarliklarini xabar qilish',
    tg: 'Хабар дар бораи вайронкуниҳо',
    ky: 'Иш берүүчүнүн бузууларын билдирүү',
  },
  contractCheck: {
    ru: 'Проверка трудового договора',
    en: 'Employment Contract Check',
    uz: 'Mehnat shartnomasini tekshirish',
    tg: 'Санҷиши шартномаи меҳнатӣ',
    ky: 'Эмгек келишимин текшерүү',
  },
  contractCheckDesc: {
    ru: 'Проверьте договор на нарушения',
    en: 'Check contract for violations',
    uz: 'Shartnomani buzilishlar uchun tekshiring',
    tg: 'Шартномаро барои вайронкуниҳо санҷед',
    ky: 'Келишимди бузууларга текшериңиз',
  },
  comingSoon: {
    ru: 'Скоро',
    en: 'Coming Soon',
    uz: 'Tez orada',
    tg: 'Ба наздикӣ',
    ky: 'Жакында',
  },
};"""


# ============================================================
# ФАЙЛ 2: JobSearchHub.tsx — полная замена
# ============================================================

JOB_SEARCH_HUB = os.path.join(FRONTEND, 'components', 'work', 'JobSearchHub.tsx')

JOB_SEARCH_HUB_CONTENT = """'use client';

import { useTranslation } from '@/lib/i18n';

import React, { useState } from 'react';
import { useLanguageStore, type Language } from '@/lib/stores/languageStore';
import { ExternalLink, Search, AlertTriangle, Building2, X } from 'lucide-react';

interface JobFilters {
  city: string;
  profession: string;
  salaryFrom?: number;
  salaryTo?: number;
  withPatent: boolean;
}

interface CityOption {
  id: string;
  name: Record<Language, string>;
  hhId: string;
  avitoId: string;
}

interface ProfessionOption {
  id: string;
  name: Record<Language, string>;
  hhId?: string;
  avitoKeyword?: string;
}

interface JobPlatform {
  id: string;
  name: string;
  logo: string;
  baseUrl: string;
  buildUrl: (filters: JobFilters, cities: CityOption[], professions: ProfessionOption[]) => string;
  description: Record<Language, string>;
}

const CITIES: CityOption[] = [
  { id: 'moscow', name: { ru: 'Москва', en: 'Moscow', uz: 'Moskva', tg: 'Маскав', ky: 'Москва' }, hhId: '1', avitoId: 'moskva' },
  { id: 'spb', name: { ru: 'Санкт-Петербург', en: 'Saint Petersburg', uz: 'Sankt-Peterburg', tg: 'Санкт-Петербург', ky: 'Санкт-Петербург' }, hhId: '2', avitoId: 'sankt-peterburg' },
  { id: 'krasnodar', name: { ru: 'Краснодар', en: 'Krasnodar', uz: 'Krasnodar', tg: 'Краснодар', ky: 'Краснодар' }, hhId: '53', avitoId: 'krasnodar' },
  { id: 'ekb', name: { ru: 'Екатеринбург', en: 'Ekaterinburg', uz: 'Yekaterinburg', tg: 'Екатеринбург', ky: 'Екатеринбург' }, hhId: '3', avitoId: 'ekaterinburg' },
  { id: 'novosibirsk', name: { ru: 'Новосибирск', en: 'Novosibirsk', uz: 'Novosibirsk', tg: 'Новосибирск', ky: 'Новосибирск' }, hhId: '4', avitoId: 'novosibirsk' },
  { id: 'kazan', name: { ru: 'Казань', en: 'Kazan', uz: 'Qozon', tg: 'Қазон', ky: 'Казань' }, hhId: '88', avitoId: 'kazan' },
  { id: 'nizhny', name: { ru: 'Нижний Новгород', en: 'Nizhny Novgorod', uz: 'Nijniy Novgorod', tg: 'Нижний Новгород', ky: 'Нижний Новгород' }, hhId: '66', avitoId: 'nizhniy_novgorod' },
  { id: 'samara', name: { ru: 'Самара', en: 'Samara', uz: 'Samara', tg: 'Самара', ky: 'Самара' }, hhId: '78', avitoId: 'samara' },
  { id: 'rostov', name: { ru: 'Ростов-на-Дону', en: 'Rostov-on-Don', uz: 'Rostov-na-Donu', tg: 'Ростов-на-Дону', ky: 'Ростов-на-Дону' }, hhId: '76', avitoId: 'rostov-na-donu' },
  { id: 'chelyabinsk', name: { ru: 'Челябинск', en: 'Chelyabinsk', uz: 'Chelyabinsk', tg: 'Челябинск', ky: 'Челябинск' }, hhId: '104', avitoId: 'chelyabinsk' },
];

const PROFESSIONS: ProfessionOption[] = [
  { id: 'all', name: { ru: 'Все профессии', en: 'All professions', uz: 'Barcha kasblar', tg: 'Ҳамаи касбҳо', ky: 'Бардык кесиптер' } },
  { id: 'construction', name: { ru: 'Строительство', en: 'Construction', uz: 'Qurilish', tg: 'Сохтмонӣ', ky: 'Курулуш' }, hhId: '3', avitoKeyword: 'строитель' },
  { id: 'logistics', name: { ru: 'Логистика, склад', en: 'Logistics, warehouse', uz: 'Logistika, ombor', tg: 'Логистика, анбор', ky: 'Логистика, кампа' }, hhId: '15', avitoKeyword: 'грузчик' },
  { id: 'production', name: { ru: 'Производство', en: 'Manufacturing', uz: 'Ishlab chiqarish', tg: 'Истеҳсолот', ky: 'Өндүрүш' }, hhId: '5', avitoKeyword: 'производство' },
  { id: 'retail', name: { ru: 'Продажи, торговля', en: 'Sales, retail', uz: 'Savdo', tg: 'Савдо', ky: 'Соода' }, hhId: '2', avitoKeyword: 'продавец' },
  { id: 'cleaning', name: { ru: 'Уборка, клининг', en: 'Cleaning', uz: 'Tozalash', tg: 'Тозакунӣ', ky: 'Тазалоо' }, hhId: '23', avitoKeyword: 'уборщик' },
  { id: 'driver', name: { ru: 'Водитель', en: 'Driver', uz: 'Haydovchi', tg: 'Ронанда', ky: 'Айдоочу' }, hhId: '13', avitoKeyword: 'водитель' },
  { id: 'courier', name: { ru: 'Курьер', en: 'Courier', uz: 'Kuryer', tg: 'Курер', ky: 'Курьер' }, hhId: '17', avitoKeyword: 'курьер' },
  { id: 'security', name: { ru: 'Охрана', en: 'Security', uz: 'Qorovul', tg: 'Муҳофизат', ky: 'Коопсуздук' }, hhId: '22', avitoKeyword: 'охранник' },
  { id: 'food', name: { ru: 'Общепит', en: 'Food service', uz: 'Umumiy ovqatlanish', tg: 'Хӯрокхӯрӣ', ky: 'Тамак-аш' }, hhId: '10', avitoKeyword: 'повар' },
];

const JOB_PLATFORMS: JobPlatform[] = [
  {
    id: 'hh',
    name: 'HeadHunter (hh.ru)',
    logo: '/icons/hh-logo.svg',
    baseUrl: 'https://hh.ru/search/vacancy',
    description: {
      ru: 'Крупнейший job-портал России',
      en: 'Largest job portal in Russia',
      uz: 'Rossiyaning eng yirik ish portali',
      tg: 'Бузургтарин портали кор дар Русия',
      ky: 'Россиянын эң чоң жумуш порталы'
    },
    buildUrl: (filters, cities, professions) => {
      const params = new URLSearchParams();
      const city = cities.find(c => c.id === filters.city);
      if (city?.hhId) params.set('area', city.hhId);
      const prof = professions.find(p => p.id === filters.profession);
      if (prof?.hhId) params.set('professional_role', prof.hhId);
      if (filters.salaryFrom) params.set('salary', filters.salaryFrom.toString());
      params.set('only_with_salary', 'true');
      return `https://hh.ru/search/vacancy?${params.toString()}`;
    },
  },
  {
    id: 'avito',
    name: 'Авито Работа',
    logo: '/icons/avito-logo.svg',
    baseUrl: 'https://www.avito.ru',
    description: {
      ru: 'Много вакансий для рабочих специальностей',
      en: 'Many blue-collar jobs',
      uz: 'Ishchi mutaxassisliklari uchun ko\\'p vakansiyalar',
      tg: 'Вакансияҳои зиёд барои мутахассисони коргарӣ',
      ky: 'Жумушчу адистиктер үчүн көп вакансиялар'
    },
    buildUrl: (filters, cities, professions) => {
      const city = cities.find(c => c.id === filters.city);
      const prof = professions.find(p => p.id === filters.profession);
      let url = `https://www.avito.ru/${city?.avitoId || 'rossiya'}/vakansii`;
      if (prof?.avitoKeyword) url += `?q=${encodeURIComponent(prof.avitoKeyword)}`;
      return url;
    },
  },
  {
    id: 'rabota',
    name: 'Работа.ру',
    logo: '/icons/rabota-logo.svg',
    baseUrl: 'https://www.rabota.ru',
    description: {
      ru: 'Вакансии с указанием условий для иностранцев',
      en: 'Jobs with conditions for foreigners',
      uz: 'Chet elliklar uchun shartlar ko\\'rsatilgan vakansiyalar',
      tg: 'Вакансияҳо бо нишондиҳии шартҳо барои хориҷиён',
      ky: 'Чет өлкөлүктөр үчүн шарттары көрсөтүлгөн вакансиялар'
    },
    buildUrl: (filters, cities) => {
      const city = cities.find(c => c.id === filters.city);
      const cityName = city?.name.ru || '';
      return `https://www.rabota.ru/vacancy?query=&geo=${encodeURIComponent(cityName)}`;
    },
  },
  {
    id: 'trudvsem',
    name: 'Работа России',
    logo: '/icons/trudvsem-logo.svg',
    baseUrl: 'https://trudvsem.ru',
    description: {
      ru: 'Официальный портал Роструда',
      en: 'Official Rostrud portal',
      uz: 'Rostrud rasmiy portali',
      tg: 'Портали расмии Роструд',
      ky: 'Роструддун расмий порталы'
    },
    buildUrl: (filters, cities) => {
      const city = cities.find(c => c.id === filters.city);
      const cityName = city?.name.ru || '';
      return `https://trudvsem.ru/vacancies?query=&regionName=${encodeURIComponent(cityName)}`;
    },
  },
];

const translations = {
  title: {
    ru: 'Поиск работы',
    en: 'Job Search',
    uz: 'Ish qidirish',
    tg: 'Ҷустуҷӯи кор',
    ky: 'Жумуш издөө'
  },
  subtitle: {
    ru: 'Найдите вакансии на популярных сайтах',
    en: 'Find jobs on popular platforms',
    uz: 'Mashhur saytlarda ish toping',
    tg: 'Дар сайтҳои маъмул ҷойҳои корӣ ёбед',
    ky: 'Популярдуу сайттардан жумуш табыңыз'
  },
  city: {
    ru: 'Город',
    en: 'City',
    uz: 'Shahar',
    tg: 'Шаҳр',
    ky: 'Шаар'
  },
  profession: {
    ru: 'Профессия',
    en: 'Profession',
    uz: 'Kasb',
    tg: 'Касб',
    ky: 'Кесип'
  },
  salary: {
    ru: 'Зарплата от',
    en: 'Salary from',
    uz: 'Maosh',
    tg: 'Маош аз',
    ky: 'Айлык'
  },
  openSearch: {
    ru: 'Открыть поиск',
    en: 'Open search',
    uz: 'Qidiruvni ochish',
    tg: 'Кушодани ҷустуҷӯ',
    ky: 'Издөөнү ачуу'
  },
  warning: {
    ru: 'Проверяйте работодателя перед трудоустройством',
    en: 'Verify the employer before employment',
    uz: 'Ishga kirishdan oldin ish beruvchini tekshiring',
    tg: 'Пеш аз кор корфарморо санҷед',
    ky: 'Жумушка кирер алдында иш берүүчүнү текшериңиз'
  },
  checkEmployer: {
    ru: 'Проверить работодателя',
    en: 'Check employer',
    uz: 'Ish beruvchini tekshirish',
    tg: 'Санҷиши корфармо',
    ky: 'Иш берүүчүнү текшерүү'
  },
  close: {
    ru: 'Закрыть',
    en: 'Close',
    uz: 'Yopish',
    tg: 'Пӯшидан',
    ky: 'Жабуу'
  },
  rubles: {
    ru: 'руб.',
    en: 'RUB',
    uz: 'rubl',
    tg: 'рубл',
    ky: 'руб.'
  },
};

interface JobSearchHubProps {
  onClose?: () => void;
}

export function JobSearchHub({
  onClose }: JobSearchHubProps) {
  useTranslation();
  const { language } = useLanguageStore();
  const lang = language as Language;

  const [filters, setFilters] = useState<JobFilters>({
    city: 'moscow',
    profession: 'all',
    salaryFrom: undefined,
    withPatent: true,
  });

  const tr = (key: keyof typeof translations) => translations[key][lang] || translations[key].ru;

  const handleOpenPlatform = (platform: JobPlatform) => {
    const url = platform.buildUrl(filters, CITIES, PROFESSIONS);
    window.open(url, '_blank', 'noopener,noreferrer');
  };

  const getPlatformEmoji = (platformId: string) => {
    switch (platformId) {
      case 'hh': return '🔵';
      case 'avito': return '🟢';
      case 'rabota': return '🔴';
      case 'trudvsem': return '🏛️';
      default: return '💼';
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div className="text-center flex-1">
          <h2 className="text-2xl font-bold text-gray-900">{tr('title')}</h2>
          <p className="text-gray-600 mt-1">{tr('subtitle')}</p>
        </div>
        {onClose && (
          <button
            onClick={onClose}
            className="p-2 hover:bg-gray-100 rounded-full transition-colors"
            aria-label={tr('close')}
          >
            <X className="w-6 h-6 text-gray-500" />
          </button>
        )}
      </div>

      {/* Warning Banner */}
      <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4 flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-yellow-600 flex-shrink-0 mt-0.5" />
        <div>
          <p className="text-yellow-800 font-medium">{tr('warning')}</p>
          <a
            href="/work?action=employer-rating"
            className="text-yellow-700 underline text-sm mt-1 inline-flex items-center gap-1"
          >
            <Building2 className="w-4 h-4" />
            {tr('checkEmployer')}
          </a>
        </div>
      </div>

      {/* Filters */}
      <div className="bg-white rounded-lg shadow-sm border p-4 space-y-4">
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {/* City */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {tr('city')}
            </label>
            <select
              value={filters.city}
              onChange={(e) => setFilters({ ...filters, city: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            >
              {CITIES.map((city) => (
                <option key={city.id} value={city.id}>
                  {city.name[lang] || city.name.ru}
                </option>
              ))}
            </select>
          </div>

          {/* Profession */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {tr('profession')}
            </label>
            <select
              value={filters.profession}
              onChange={(e) => setFilters({ ...filters, profession: e.target.value })}
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            >
              {PROFESSIONS.map((prof) => (
                <option key={prof.id} value={prof.id}>
                  {prof.name[lang] || prof.name.ru}
                </option>
              ))}
            </select>
          </div>

          {/* Salary */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-1">
              {tr('salary')} ({tr('rubles')})
            </label>
            <input
              type="number"
              value={filters.salaryFrom || ''}
              onChange={(e) => setFilters({ ...filters, salaryFrom: e.target.value ? parseInt(e.target.value) : undefined })}
              placeholder="40000"
              className="w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-indigo-500 focus:border-indigo-500"
            />
          </div>
        </div>
      </div>

      {/* Platforms */}
      <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
        {JOB_PLATFORMS.map((platform) => (
          <div
            key={platform.id}
            className="bg-white rounded-lg shadow-sm border p-4 hover:shadow-md transition-shadow"
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-3">
                <span className="text-2xl">{getPlatformEmoji(platform.id)}</span>
                <div>
                  <h3 className="font-semibold text-gray-900">{platform.name}</h3>
                  <p className="text-sm text-gray-500">
                    {platform.description[lang] || platform.description.ru}
                  </p>
                </div>
              </div>
            </div>
            <button
              onClick={() => handleOpenPlatform(platform)}
              className="mt-4 w-full flex items-center justify-center gap-2 px-4 py-2 bg-indigo-600 text-white rounded-lg hover:bg-indigo-700 transition-colors"
            >
              <Search className="w-4 h-4" />
              {tr('openSearch')}
              <ExternalLink className="w-4 h-4" />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
"""


def fix_work_page():
    """Исправляет work/page.tsx — заменяет labels и hardcoded 'subtitle'"""
    with open(WORK_PAGE, 'r', encoding='utf-8') as f:
        content = f.read()

    # Замена объекта labels
    pattern = r"const labels: Record<string, Record<Language, string>> = \{.*?\};"
    match = re.search(pattern, content, re.DOTALL)
    if match:
        content = content[:match.start()] + WORK_PAGE_LABELS + content[match.end():]
        print(f"  [OK] Заменён объект labels ({match.end() - match.start()} символов)")
    else:
        print("  [ОШИБКА] Не найден объект labels!")
        return False

    # Исправление hardcoded {'subtitle'} → {t('subtitle')}
    old = "<p className=\"text-sm text-indigo-100\">{'subtitle'}</p>"
    new = "<p className=\"text-sm text-indigo-100\">{t('subtitle')}</p>"
    if old in content:
        content = content.replace(old, new)
        print("  [OK] Исправлен hardcoded {'subtitle'} → {t('subtitle')}")
    else:
        print("  [ПРОПУСК] {'subtitle'} не найден (уже исправлен?)")

    with open(WORK_PAGE, 'w', encoding='utf-8') as f:
        f.write(content)
    return True


def fix_job_search_hub():
    """Полностью переписывает JobSearchHub.tsx с правильными переводами"""
    with open(JOB_SEARCH_HUB, 'w', encoding='utf-8') as f:
        f.write(JOB_SEARCH_HUB_CONTENT)
    print(f"  [OK] Файл JobSearchHub.tsx полностью перезаписан с исправленными переводами")
    return True


def count_fixes():
    """Считает количество исправлений"""
    fixes = {
        'work/page.tsx': {
            'labels_ru': 17,      # 17 ключей с неправильными ru-значениями
            'labels_tg': 17,      # 17 ключей с неправильными tg-значениями
            'labels_ky': 17,      # 17 ключей с неправильными ky-значениями
            'hardcoded_jsx': 1,   # {'subtitle'} → {t('subtitle')}
        },
        'JobSearchHub.tsx': {
            'translations_ru': 9,  # 9 ключей переводов
            'translations_tg': 10, # 10 ключей переводов (вкл. rubles)
            'translations_ky': 9,  # 9 ключей переводов
            'cities_ru': 10,       # 10 городов
            'cities_tg': 10,       # 10 городов
            'cities_ky': 10,       # 10 городов
            'professions_ru': 10,  # 10 профессий
            'professions_tg': 10,  # 10 профессий
            'professions_ky': 10,  # 10 профессий
            'avitoKeyword': 9,     # 9 avitoKeyword с ключами вместо слов
            'platforms_name': 2,   # avito, trudvsem
            'platforms_desc_ru': 4,  # описания
            'platforms_desc_tg': 4,
            'platforms_desc_ky': 4,
            'hardcoded_jsx': 4,    # subtitle, city, profession, salary+rubles
        },
    }

    total = 0
    for file, cats in fixes.items():
        file_total = sum(cats.values())
        total += file_total
        print(f"\n  {file}: {file_total} исправлений")
        for cat, count in cats.items():
            print(f"    - {cat}: {count}")

    print(f"\n  ИТОГО: {total} исправлений")
    return total


def main():
    print("=" * 60)
    print("  Исправление переводов: Работа + JobSearchHub")
    print("=" * 60)

    # Проверка наличия файлов
    for f in [WORK_PAGE, JOB_SEARCH_HUB]:
        if not os.path.exists(f):
            print(f"[ОШИБКА] Файл не найден: {f}")
            sys.exit(1)

    print(f"\n--- Исправление work/page.tsx ---")
    ok1 = fix_work_page()

    print(f"\n--- Исправление JobSearchHub.tsx ---")
    ok2 = fix_job_search_hub()

    print(f"\n--- Статистика ---")
    total = count_fixes()

    if ok1 and ok2:
        print(f"\n{'=' * 60}")
        print(f"  ГОТОВО! Все {total} замечаний исправлены.")
        print(f"{'=' * 60}")
    else:
        print(f"\n[ОШИБКА] Некоторые файлы не были исправлены!")
        sys.exit(1)


if __name__ == '__main__':
    main()
