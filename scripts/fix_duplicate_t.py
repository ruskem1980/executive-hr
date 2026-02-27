#!/usr/bin/env python3
"""
Скрипт для массового исправления дублирующего определения `t`:
- Удаляет `import { useTranslation } from '@/lib/i18n';` (или из useTranslation)
- Удаляет `const { t } = useTranslation();`
- Оставляет локальную функцию `const t = (key: string)...`

Это исправляет ошибку сборки:
"the name `t` is defined multiple times"
"""

import re
import os

BASE = os.path.join(os.path.dirname(__file__), '..', 'apps', 'frontend', 'src')

# Все файлы с проблемой (из вывода сборки)
FILES = [
    'app/(main)/family/schools/page.tsx',
    'components/family/CostSummary.tsx',
    'components/family/DocumentCalculator.tsx',
    'components/family/DocumentItem.tsx',
    'components/family/SchoolCard.tsx',
    'components/family/SchoolDocuments.tsx',
    'components/family/SchoolSearch.tsx',
    'components/housing/ContractCheckResult.tsx',
    'components/housing/ContractGenerator.tsx',
    'components/housing/ContractPreview.tsx',
    'components/housing/ContractStep1.tsx',
    'components/housing/ContractStep2.tsx',
    'components/housing/ContractStep3.tsx',
    'components/housing/ContractStep4.tsx',
    'components/housing/CreateReviewForm.tsx',
    'components/housing/HousingCard.tsx',
    'components/housing/HousingFilters.tsx',
    'components/housing/HousingSearchHub.tsx',
    'components/housing/LandlordCheckForm.tsx',
    'components/housing/LandlordCheckResult.tsx',
    'components/housing/LandlordRating.tsx',
    'components/housing/LandlordReviews.tsx',
    'components/housing/RegistrationGuide.tsx',
    'components/work/ContractCheckResult.tsx',
    'components/work/EmployerCheck.tsx',
    'components/work/EmployerComplaint.tsx',
    'components/work/EmployerRating.tsx',
    'components/work/EmploymentContractCheck.tsx',
    'components/work/reviews/ReviewFormWizard.tsx',
]

total_fixes = 0

for rel_path in FILES:
    full_path = os.path.join(BASE, rel_path)
    if not os.path.exists(full_path):
        print(f'  [SKIP] {rel_path} — файл не найден')
        continue

    with open(full_path, 'r', encoding='utf-8') as f:
        content = f.read()

    original = content
    fixes = 0

    # 1. Удаляем import useTranslation (различные варианты)
    # Вариант: import { useTranslation } from '@/lib/i18n';
    # Вариант: import { useTranslation } from '@/lib/i18n/useTranslation';
    patterns_import = [
        r"import\s*\{\s*useTranslation\s*\}\s*from\s*'@/lib/i18n(?:/useTranslation)?'\s*;\s*\n",
        r"import\s*\{\s*useTranslation\s*\}\s*from\s*'@/lib/i18n(?:/useTranslation)?'\s*;\s*\n?",
    ]

    for pattern in patterns_import:
        new_content = re.sub(pattern, '', content)
        if new_content != content:
            fixes += 1
            content = new_content
            break

    # 2. Удаляем const { t } = useTranslation(); (с пробелами и переводами строк)
    # Вариант: const { t } = useTranslation();
    # Вариант: const { t, language } = useTranslation();  — НЕ удаляем, нужен language
    # Проверяем, используется ли language из useTranslation

    uses_language_from_translation = bool(re.search(
        r'const\s*\{\s*t\s*,\s*\w+.*?\}\s*=\s*useTranslation\s*\(\s*\)', content
    ))

    if uses_language_from_translation:
        # Удаляем только t из деструктуризации, оставляем остальное
        # const { t, language } = useTranslation(); → const { language } = useTranslation();
        content_new = re.sub(
            r'const\s*\{\s*t\s*,\s*(\w+(?:\s*,\s*\w+)*)\s*\}\s*=\s*useTranslation\s*\(\s*\)\s*;',
            r'const { \1 } = useTranslation();',
            content
        )
        if content_new != content:
            fixes += 1
            content = content_new
    else:
        # Удаляем всю строку const { t } = useTranslation();
        content_new = re.sub(
            r'\s*const\s*\{\s*t\s*\}\s*=\s*useTranslation\s*\(\s*\)\s*;\s*\n',
            '\n',
            content
        )
        if content_new != content:
            fixes += 1
            content = content_new

    # 3. Проверяем: если useTranslation больше не используется (не осталось вызовов),
    #    но import всё ещё есть — удаляем import
    if 'useTranslation' not in content.split('import')[0] and 'useTranslation' in content:
        # Если useTranslation только в import и больше нигде
        remaining_uses = len(re.findall(r'useTranslation', content))
        import_uses = len(re.findall(r'import.*useTranslation', content))
        if remaining_uses == import_uses:
            # Удаляем import useTranslation
            for pattern in patterns_import:
                new_content = re.sub(pattern, '', content)
                if new_content != content:
                    fixes += 1
                    content = new_content
                    break

    # 4. Также удаляем пустые строки от удалённого import (двойные пустые строки)
    content = re.sub(r'\n{3,}', '\n\n', content)

    if content != original:
        with open(full_path, 'w', encoding='utf-8') as f:
            f.write(content)
        total_fixes += fixes
        print(f'  [OK] {rel_path} — {fixes} исправлений')
    else:
        print(f'  [NO CHANGE] {rel_path}')

print(f'\nИтого: {total_fixes} исправлений в {len(FILES)} файлах')
