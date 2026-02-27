#!/usr/bin/env python3
"""
Comprehensive i18n scanner и автоматический fixer.
Находит все захардкоженные русские строки и исправляет их.
"""
import os
import re
import json
import shutil
import difflib
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass, field

# --- КОНФИГУРАЦИЯ ---
PROJECT_ROOT = Path.cwd()
SRC_DIR = PROJECT_ROOT / "apps/frontend/src"
COMPONENTS_DIR = SRC_DIR / "components"
LOCALES_DIR = SRC_DIR / "locales"
LANGUAGES = ["ru", "en", "uz", "tg", "ky"]
BACKUP_DIR = PROJECT_ROOT / "i18n_backups" / datetime.now().strftime("%Y%m%d_%H%M%S")
PATCHES_DIR = PROJECT_ROOT / "i18n_patches"

# Регулярные выражения для поиска кириллицы
CYRILLIC_REGEX = r'[\u0400-\u04FF]+'
# 1. Текст внутри JSX: <div>Текст</div>
JSX_TEXT_PATTERN = re.compile(r'>\s*([^<{]*[\u0400-\u04FF][^<{]*?)\s*<')
# 2. Строковые литералы: 'Текст', "Текст", `Текст` (но не ключи объектов)
STRING_LITERAL_PATTERN = re.compile(r'(?<![a-zA-Z0-9_])["\'`]([\u0400-\u04FF][^"\'`]*?)["\'`](?!\s*[:])')
# 3. Props со значениями: label="Текст"
PROP_VALUE_PATTERN = re.compile(r'(title|label|placeholder|aria-label|description|text)\s*=\s*["\']([\u0400-\u04FF][^"\']+)["\']')

@dataclass
class Finding:
    file_path: Path
    line_number: int
    original_text: str
    context_type: str  # 'jsx', 'string', 'prop'
    suggested_key: str = ""
    full_line: str = ""

class I18nFixer:
    def __init__(self):
        self.findings: List[Finding] = []
        self.translations: Dict[str, Dict[str, str]] = {lang: self._load_locale(lang) for lang in LANGUAGES}
        self.new_keys_count = 0

    def _load_locale(self, lang: str) -> Dict:
        path = LOCALES_DIR / f"{lang}.json"
        if path.exists():
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _save_locales(self):
        BACKUP_DIR.mkdir(parents=True, exist_ok=True)
        for lang, data in self.translations.items():
            path = LOCALES_DIR / f"{lang}.json"
            # Делаем бэкап
            if path.exists():
                shutil.copy(path, BACKUP_DIR / f"{lang}.json.bak")
            # Сохраняем с сортировкой и отступами
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2, sort_keys=True)

    def slugify(self, text: str) -> str:
        """Утилита для создания части ключа из текста"""
        text = text.lower()
        # Очень упрощенная транслитерация или просто удаление спецсимволов
        text = re.sub(r'[^а-яa-z0-9\s]', '', text)
        words = text.split()[:3] # Берем первые 3 слова
        return "_".join(words)

    def generate_key(self, finding: Finding) -> str:
        """Генерирует ключ типа 'paywall.sheet.select_plan'"""
        rel_path = finding.file_path.relative_to(SRC_DIR)
        parts = list(rel_path.parent.parts)
        # Добавляем имя файла без расширения
        filename = finding.file_path.stem
        if filename not in parts:
            parts.append(filename)

        # Очищаем части пути
        section = parts[1] if len(parts) > 1 else "common"
        subsection = parts[-1].lower()

        # Если это пропс, используем его имя в ключе
        if finding.context_type == 'prop':
            match = PROP_VALUE_PATTERN.search(finding.full_line)
            if match:
                prop_name = match.group(1)
                return f"{section}.{subsection}.{prop_name}"

        suffix = self.slugify(finding.original_text)
        return f"{section}.{subsection}.{suffix}"

    def scan(self):
        """Сканирует компоненты, страницы, данные и конфиги на наличие хардкода"""
        # Сканируем все директории: components, app, data, config, lib
        scan_dirs = [
            COMPONENTS_DIR,
            SRC_DIR / "app",
            SRC_DIR / "data",
            SRC_DIR / "config",
            SRC_DIR / "lib"
        ]

        files = []
        for scan_dir in scan_dirs:
            if scan_dir.exists():
                files.extend(scan_dir.glob("**/*.tsx"))
                files.extend(scan_dir.glob("**/*.ts"))

        print(f"  Найдено {len(files)} файлов для сканирования...")

        for file_path in files:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()

            for i, line in enumerate(lines):
                # Пропускаем импорты и комментарии
                if line.strip().startswith(('import', '//', '*', '/*')):
                    continue

                # Поиск в JSX текстах
                for match in JSX_TEXT_PATTERN.finditer(line):
                    text = match.group(1).strip()
                    if text:
                        self.findings.append(Finding(file_path, i+1, text, 'jsx', full_line=line))

                # Поиск в кавычках (строки)
                for match in STRING_LITERAL_PATTERN.finditer(line):
                    text = match.group(1).strip()
                    # Игнорируем если это уже похоже на ключ (содержит точку и нет пробелов)
                    if '.' in text and ' ' not in text:
                        continue
                    self.findings.append(Finding(file_path, i+1, text, 'string', full_line=line))

                # Поиск в пропсах
                for match in PROP_VALUE_PATTERN.finditer(line):
                    prop_name = match.group(1)
                    text = match.group(2).strip()
                    self.findings.append(Finding(file_path, i+1, text, 'prop', full_line=line))

    def update_json_files(self):
        """Добавляет новые ключи в JSON"""
        for finding in self.findings:
            key = self.generate_key(finding)
            finding.suggested_key = key

            keys = key.split('.')

            # Обновляем все языки
            for lang in LANGUAGES:
                current = self.translations[lang]
                for i, k in enumerate(keys[:-1]):
                    if k not in current:
                        current[k] = {}
                    current = current[k]

                last_key = keys[-1]
                if last_key not in current:
                    if lang == 'ru':
                        current[last_key] = finding.original_text
                    else:
                        # Заглушка для других языков
                        current[last_key] = f"[{lang.upper()}] {finding.original_text}"
                    self.new_keys_count += 1

        self._save_locales()

    def create_patches(self):
        """Создает патчи для файлов"""
        if PATCHES_DIR.exists():
            shutil.rmtree(PATCHES_DIR)
        PATCHES_DIR.mkdir(parents=True)

        # Группируем находки по файлам
        file_map: Dict[Path, List[Finding]] = {}
        for f in self.findings:
            if f.file_path not in file_map:
                file_map[f.file_path] = []
            file_map[f.file_path].append(f)

        for file_path, findings in file_map.items():
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            new_content = content

            # 1. Проверяем/Добавляем импорт
            if "useTranslation" not in new_content:
                import_stmt = "import { useTranslation } from '@/lib/i18n';\n"
                new_content = import_stmt + new_content

            # 2. Добавляем хук в компонент (очень упрощенно - ищем первую функцию)
            if "const { t } = useTranslation" not in new_content:
                # Ищем начало функционального компонента
                new_content = re.sub(
                    r'(export (function|const) \w+.*?[{=(].*?\n)',
                    r'\1  const { t } = useTranslation();\n',
                    new_content,
                    count=1
                )

            # 3. Заменяем текст на t('key')
            # Сортируем находки по длине текста (сначала длинные), чтобы избежать частичных замен
            findings.sort(key=lambda x: len(x.original_text), reverse=True)

            processed_texts = set()
            for f in findings:
                if f.original_text in processed_texts: continue

                key = f.suggested_key
                if f.context_type == 'jsx':
                    # <div>Текст</div> -> <div>{t('key')}</div>
                    new_content = new_content.replace(f">{f.original_text}<", f">{{t('{key}')}}<")
                elif f.context_type == 'prop':
                    # label="Текст" -> label={t('key')}
                    new_content = re.sub(
                        rf'{f.context_type}="({re.escape(f.original_text)})"',
                        f'{f.context_type}={{t(\'{key}\')}}',
                        new_content
                    )
                else:
                    # 'Текст' -> t('key')
                    new_content = new_content.replace(f"'{f.original_text}'", f"t('{key}')")
                    new_content = new_content.replace(f'"{f.original_text}"', f"t('{key}')")

                processed_texts.add(f.original_text)

            # Создаем патч
            diff = difflib.unified_diff(
                content.splitlines(keepends=True),
                new_content.splitlines(keepends=True),
                fromfile=str(file_path),
                tofile=str(file_path)
            )

            patch_name = f"{file_path.stem}.patch"
            with open(PATCHES_DIR / patch_name, 'w', encoding='utf-8') as f:
                f.writelines(diff)

    def print_report(self):
        print("\n" + "═"*50)
        print("🔍 СКАНИРОВАНИЕ ЗАВЕРШЕНО")
        print("═"*50)
        print(f"Файлов проверено:     {len(set(f.file_path for f in self.findings))}")
        print(f"Найдено хардкода:     {len(self.findings)}")
        print(f"Новых ключей создано: {self.new_keys_count}")

        print("\n📊 ТОП ПРОБЛЕМНЫХ ФАЙЛОВ:")
        file_counts = {}
        for f in self.findings:
            file_counts[f.file_path.name] = file_counts.get(f.file_path.name, 0) + 1

        sorted_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)[:5]
        for name, count in sorted_files:
            print(f"  {name:<30} | {count} строк")

        print("\n✅ ЛОКАЛИ ОБНОВЛЕНЫ (Backups in i18n_backups/)")
        print("🔧 ПАТЧИ СОЗДАНЫ в i18n_patches/")
        print("\n💡 СЛЕДУЮЩИЕ ШАГИ:")
        print("  1. Проверьте i18n_patches/*.patch")
        print("  2. Примените их: `patch -p0 < i18n_patches/File.patch` или `git apply` если в корне")
        print("  3. Запустите тесты фронтенда")

    def apply_changes_directly(self):
        """Применяет изменения напрямую в файлы (без патчей)"""
        print("  Применение изменений напрямую в файлы...")

        # Группируем находки по файлам
        file_map: Dict[Path, List[Finding]] = {}
        for f in self.findings:
            if f.file_path not in file_map:
                file_map[f.file_path] = []
            file_map[f.file_path].append(f)

        changed_count = 0
        for file_path, findings in file_map.items():
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()

            original_content = content
            new_content = content

            # 1. Проверяем/Добавляем импорт
            if "useTranslation" not in new_content and "'use client'" in new_content:
                # Добавляем импорт после 'use client'
                new_content = new_content.replace(
                    "'use client';",
                    "'use client';\n\nimport { useTranslation } from '@/lib/i18n';"
                )

            # 2. Добавляем хук в компонент (более надёжно)
            if "const { t } = useTranslation" not in new_content and "useTranslation" in new_content:
                # Ищем export function ИмяКомпонента или export default function
                # Добавляем хук сразу после открывающей фигурной скобки
                function_pattern = r'(export\s+(default\s+)?function\s+\w+[^{]*\{)'
                if re.search(function_pattern, new_content):
                    new_content = re.sub(
                        function_pattern,
                        r'\1\n  const { t } = useTranslation();',
                        new_content,
                        count=1
                    )

            # 3. Заменяем текст на t('key')
            findings.sort(key=lambda x: len(x.original_text), reverse=True)

            processed_texts = set()
            for f in findings:
                if f.original_text in processed_texts:
                    continue

                key = f.suggested_key
                escaped_text = re.escape(f.original_text)

                # JSX текст
                if f.context_type == 'jsx':
                    new_content = new_content.replace(
                        f">{f.original_text}<",
                        f">{{t('{key}')}}<"
                    )

                # Props
                elif f.context_type == 'prop':
                    new_content = re.sub(
                        rf'(title|label|placeholder|aria-label|description|text)="({escaped_text})"',
                        rf'\1={{t(\'{key}\')}}',
                        new_content
                    )

                # Строковые литералы
                else:
                    new_content = new_content.replace(f"'{f.original_text}'", f"t('{key}')")
                    new_content = new_content.replace(f'"{f.original_text}"', f"t('{key}')")

                processed_texts.add(f.original_text)

            # Записываем только если были изменения
            if new_content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(new_content)
                changed_count += 1

        print(f"  ✅ Изменено файлов: {changed_count}")

def main():
    import sys

    print("🚀 Запуск Total i18n Fixer...")
    fixer = I18nFixer()

    print("📁 Сканирование компонентов...")
    fixer.scan()

    if not fixer.findings:
        print("✨ Чисто! Захардкоженных строк не найдено.")
        return

    print(f"📝 Обработка {len(fixer.findings)} находок...")
    fixer.update_json_files()

    # Проверяем флаг --apply
    if '--apply' in sys.argv:
        print("🔧 Применение изменений напрямую...")
        fixer.apply_changes_directly()
    else:
        print("🛠 Генерация патчей...")
        fixer.create_patches()

    fixer.print_report()

    if '--apply' not in sys.argv:
        print("\n💡 Для автоматического применения используйте: python3 scripts/i18n_total_fixer.py --apply")

if __name__ == "__main__":
    main()
