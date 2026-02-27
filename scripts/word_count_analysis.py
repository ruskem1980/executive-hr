#!/usr/bin/env python3
"""
Анализ количества слов в переводах

Функции:
1. Подсчёт слов в каждом языке
2. Сравнение количества слов между языками (русский как эталон)
3. Выявление аномалий (где количество слов сильно отличается)
4. Детальный отчёт по расхождениям

Критерии аномалий:
- Разница >50% слов считается значительной
- Разница >100% критичной
"""

import json
import re
from pathlib import Path
from typing import Dict, List, Tuple
from dataclasses import dataclass
from collections import defaultdict
import sys


@dataclass
class WordCountIssue:
    key: str
    ru_text: str
    ru_words: int
    lang_text: str
    lang_words: int
    diff_percent: float
    severity: str  # "significant" (50-100%) or "critical" (>100%)


class WordCountAnalyzer:
    def __init__(self, locales_dir: Path, reference_lang: str = "ru"):
        self.locales_dir = locales_dir
        self.reference_lang = reference_lang
        self.translations = {}
        self.issues = defaultdict(list)  # lang -> [WordCountIssue]

    def load_translations(self):
        """Загрузить все JSON файлы"""
        for file in self.locales_dir.glob("*.json"):
            lang = file.stem
            with open(file, 'r', encoding='utf-8') as f:
                self.translations[lang] = json.load(f)

    def flatten_dict(self, d: Dict, parent_key: str = '') -> Dict[str, str]:
        """Преобразовать в плоский dict"""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}.{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self.flatten_dict(v, new_key).items())
            else:
                items.append((new_key, str(v) if v is not None else ""))
        return dict(items)

    def count_words(self, text: str) -> int:
        """
        Подсчитать количество слов

        Обрабатывает:
        - Кириллицу (русский, киргизский, таджикский)
        - Латиницу (английский, узбекский)
        - Плейсхолдеры {{var}} не считаются
        """
        # Убрать плейсхолдеры
        text_clean = re.sub(r'\{\{[^}]+\}\}', '', text)

        # Убрать знаки препинания и спецсимволы, оставить только слова
        # Поддержка кириллицы и латиницы
        words = re.findall(r'[\w\u0400-\u04FF]+', text_clean, re.UNICODE)

        return len(words)

    def analyze_word_counts(self):
        """Анализ количества слов для всех языков"""
        ref_flat = self.flatten_dict(self.translations[self.reference_lang])

        for lang in self.translations:
            if lang == self.reference_lang:
                continue

            lang_flat = self.flatten_dict(self.translations[lang])

            for key in ref_flat:
                if key not in lang_flat:
                    continue

                ru_text = ref_flat[key]
                lang_text = lang_flat[key]

                ru_words = self.count_words(ru_text)
                lang_words = self.count_words(lang_text)

                # Пропустить если оба текста пустые или очень короткие
                if ru_words < 2:
                    continue

                # Вычислить разницу в процентах
                diff_percent = abs(lang_words - ru_words) / ru_words * 100

                # Определить severity
                severity = None
                if diff_percent > 100:
                    severity = "critical"
                elif diff_percent > 50:
                    severity = "significant"

                if severity:
                    self.issues[lang].append(WordCountIssue(
                        key=key,
                        ru_text=ru_text,
                        ru_words=ru_words,
                        lang_text=lang_text,
                        lang_words=lang_words,
                        diff_percent=diff_percent,
                        severity=severity
                    ))

    def print_report(self):
        """Вывести отчёт по анализу"""
        print("=" * 80)
        print("АНАЛИЗ КОЛИЧЕСТВА СЛОВ В ПЕРЕВОДАХ")
        print("=" * 80)
        print()

        # Общая статистика
        total_issues = sum(len(issues) for issues in self.issues.values())
        critical_issues = sum(
            len([i for i in issues if i.severity == "critical"])
            for issues in self.issues.values()
        )
        significant_issues = sum(
            len([i for i in issues if i.severity == "significant"])
            for issues in self.issues.values()
        )

        print(f"Всего проблем: {total_issues}")
        print(f"  - Критичных (>100% разница): {critical_issues}")
        print(f"  - Значительных (50-100% разница): {significant_issues}")
        print()

        if not total_issues:
            print("✅ Количество слов в переводах соответствует эталону!")
            print()
            return

        # Статистика по языкам
        print("СТАТИСТИКА ПО ЯЗЫКАМ:")
        print("-" * 80)
        for lang in sorted(self.issues.keys()):
            issues = self.issues[lang]
            critical = len([i for i in issues if i.severity == "critical"])
            significant = len([i for i in issues if i.severity == "significant"])

            status = "⚠️" if critical > 0 else "⚡"
            print(f"{status} {lang}: {len(issues)} проблем | {critical} критичных | {significant} значительных")
        print()

        # Детальный отчёт по каждому языку
        for lang in sorted(self.issues.keys()):
            issues = self.issues[lang]
            if not issues:
                continue

            print(f"{'=' * 80}")
            print(f"ЯЗЫК: {lang.upper()}")
            print(f"{'=' * 80}")
            print()

            # Сортировка: критичные сверху
            issues_sorted = sorted(
                issues,
                key=lambda x: (0 if x.severity == "critical" else 1, -x.diff_percent)
            )

            # Показать первые 20
            for i, issue in enumerate(issues_sorted[:20], 1):
                severity_icon = "🔴" if issue.severity == "critical" else "🟡"
                print(f"{i}. {severity_icon} {issue.key}")
                print(f"   Разница: {issue.diff_percent:.1f}%")
                print(f"   РУ ({issue.ru_words} слов): {issue.ru_text[:80]}{'...' if len(issue.ru_text) > 80 else ''}")
                print(f"   {lang.upper()} ({issue.lang_words} слов): {issue.lang_text[:80]}{'...' if len(issue.lang_text) > 80 else ''}")
                print()

            if len(issues_sorted) > 20:
                print(f"... и ещё {len(issues_sorted) - 20} проблем")
                print()

        # Рекомендации
        print("=" * 80)
        print("РЕКОМЕНДАЦИИ")
        print("=" * 80)
        print()
        print("1. Критичные проблемы (>100% разница) требуют пересмотра перевода")
        print("2. Значительные проблемы (50-100%) нужно проверить на точность")
        print("3. Используйте scripts/fix_translations.py для автоматической генерации")
        print("4. Или исправьте вручную в apps/frontend/src/locales/<lang>.json")
        print()

    def export_json(self, output_file: Path):
        """Экспортировать результаты в JSON для автоматической обработки"""
        export_data = {
            "summary": {
                "total_issues": sum(len(issues) for issues in self.issues.values()),
                "critical": sum(
                    len([i for i in issues if i.severity == "critical"])
                    for issues in self.issues.values()
                ),
                "significant": sum(
                    len([i for i in issues if i.severity == "significant"])
                    for issues in self.issues.values()
                )
            },
            "by_language": {}
        }

        for lang, issues in self.issues.items():
            export_data["by_language"][lang] = [
                {
                    "key": issue.key,
                    "ru_text": issue.ru_text,
                    "ru_words": issue.ru_words,
                    "lang_text": issue.lang_text,
                    "lang_words": issue.lang_words,
                    "diff_percent": round(issue.diff_percent, 2),
                    "severity": issue.severity
                }
                for issue in issues
            ]

        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        print(f"📄 Результаты экспортированы в: {output_file}")
        print()


def main():
    locales_dir = Path(__file__).parent.parent / "apps" / "frontend" / "src" / "locales"

    if not locales_dir.exists():
        print(f"❌ Директория не найдена: {locales_dir}")
        return 1

    analyzer = WordCountAnalyzer(locales_dir)

    print("🔍 Загрузка переводов...")
    analyzer.load_translations()

    print(f"📦 Загружено языков: {', '.join(sorted(analyzer.translations.keys()))}")
    print(f"📏 Эталонный язык: {analyzer.reference_lang}")
    print()

    print("⚙️  Анализ количества слов...")
    analyzer.analyze_word_counts()

    analyzer.print_report()

    # Экспорт в JSON
    output_file = Path(__file__).parent.parent / "data" / "word_count_analysis.json"
    output_file.parent.mkdir(parents=True, exist_ok=True)
    analyzer.export_json(output_file)

    # Код возврата
    if analyzer.issues:
        return 1  # Есть проблемы
    else:
        return 0  # Всё ок


if __name__ == "__main__":
    sys.exit(main())
