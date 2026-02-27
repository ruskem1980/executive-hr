#!/usr/bin/env python3
"""
Генератор отчетов i18n в различных форматах (Markdown, HTML, CSV).
"""
import json
import os
import argparse
import csv
from datetime import datetime
from typing import Dict, Any

class I18nReportGenerator:
    """
    Генератор отчетов i18n в различных форматах.
    """

    def __init__(self, json_report_path: str):
        with open(json_report_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

    def generate_markdown(self, output_path: str):
        """Генерация Markdown отчета"""
        summary = self.data["summary"]
        stats = self.data["statistics"]
        issues = self.data["issues"]
        coverage = self.data["component_coverage"]

        lines = []
        lines.append("# Отчет о состоянии локализации (i18n)\n")
        lines.append(f"**Дата анализа:** {self.data['timestamp']}\n")

        lines.append("## 📊 Сводка\n")
        lines.append(f"- **Базовый язык:** {summary.get('base_lang', 'ru')}\n")
        lines.append(f"- **Всего ключей в базе:** {summary['total_keys_base']}\n")
        lines.append(f"- **Языки:** {', '.join(summary['languages'])}\n")
        lines.append(f"- **Всего проблем:** {summary['total_issues']} (Критических: {summary['critical_issues']})\n")

        lines.append("\n## 📈 Статистика по языкам\n")
        lines.append("| Язык | Ключи | Слова | Символы | Покрытие |\n")
        lines.append("|------|-------|-------|----------|----------|\n")
        for lang, s in stats.items():
            lines.append(f"| {lang} | {s['keys_count']} | {s['word_count']} | {s['char_count']} | {s['coverage_percent']:.1f}% |\n")

        lines.append("\n## 🛠 Покрытие кода\n")
        lines.append(f"- Используется ключей в коде: {coverage['used_keys_count']}\n")
        lines.append(f"- Неиспользуемых ключей в JSON: {coverage['unused_keys_count']}\n")
        lines.append(f"- Ключей в коде, но нет в JSON: {coverage['missing_keys_in_code_count']}\n")
        lines.append(f"- Хардкодных строк найдено: {coverage['hardcoded_strings_count']}\n")

        if coverage.get('hardcoded_samples'):
            lines.append("\n### Примеры хардкода:\n")
            lines.append("| Файл | Текст |\n")
            lines.append("|------|-------|\n")
            for item in coverage['hardcoded_samples']:
                lines.append(f"| `{item['file']}` | {item['text']} |\n")

        lines.append("\n## ⚠️ Список проблем\n")
        lines.append("| Тип | Важность | Язык | Ключ | Описание |\n")
        lines.append("|-----|----------|------|------|----------|\n")
        for issue in issues:
            lines.append(f"| {issue['type']} | {issue['severity']} | {issue['lang']} | `{issue['key']}` | {issue['description']} |\n")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

    def generate_csv(self, output_path: str):
        """Генерация CSV отчета"""
        issues = self.data["issues"]
        if not issues:
            return

        keys = issues[0].keys()
        with open(output_path, 'w', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=keys)
            writer.writeheader()
            writer.writerows(issues)

    def generate_html(self, output_path: str):
        """Генерация HTML отчета"""
        lines = []
        lines.append("<html>\n")
        lines.append("<head>\n")
        lines.append("    <title>i18n Report</title>\n")
        lines.append("    <style>\n")
        lines.append("        body { font-family: sans-serif; margin: 40px; line-height: 1.6; }\n")
        lines.append("        table { border-collapse: collapse; width: 100%; margin-bottom: 20px; }\n")
        lines.append("        th, td { border: 1px solid #ddd; padding: 8px; text-align: left; }\n")
        lines.append("        th { background-color: #f2f2f2; }\n")
        lines.append("        .error { color: red; }\n")
        lines.append("        .warning { color: orange; }\n")
        lines.append("    </style>\n")
        lines.append("</head>\n")
        lines.append("<body>\n")
        lines.append("    <h1>Отчет i18n</h1>\n")
        lines.append(f"    <p>Дата: {self.data['timestamp']}</p>\n")
        lines.append("    <h2>Статистика</h2>\n")
        lines.append("    <table>\n")
        lines.append("        <tr><th>Язык</th><th>Ключи</th><th>Слова</th><th>Символы</th><th>Покрытие</th></tr>\n")

        for lang, s in self.data["statistics"].items():
            lines.append(f"        <tr><td>{lang}</td><td>{s['keys_count']}</td><td>{s['word_count']}</td><td>{s['char_count']}</td><td>{s['coverage_percent']:.1f}%</td></tr>\n")

        lines.append("    </table>\n")
        lines.append("    <h2>Проблемы</h2>\n")
        lines.append("    <table>\n")
        lines.append("        <tr><th>Тип</th><th>Важность</th><th>Язык</th><th>Ключ</th><th>Описание</th></tr>\n")

        for issue in self.data["issues"]:
            severity_class = "error" if issue['severity'] == 'error' else "warning"
            lines.append(f"        <tr><td>{issue['type']}</td><td class='{severity_class}'>{issue['severity']}</td><td>{issue['lang']}</td><td>{issue['key']}</td><td>{issue['description']}</td></tr>\n")

        lines.append("    </table>\n")
        lines.append("</body>\n")
        lines.append("</html>\n")

        with open(output_path, 'w', encoding='utf-8') as f:
            f.writelines(lines)

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Генератор отчетов i18n")
    parser.add_argument("report", help="Путь к JSON отчету анализатора")
    parser.add_argument("--format", choices=["markdown", "csv", "html", "all"], default="all", help="Формат отчета")
    parser.add_argument("--output-dir", default="reports/i18n", help="Директория для вывода")

    args = parser.parse_args()

    gen = I18nReportGenerator(args.report)
    base_name = os.path.basename(args.report).replace('.json', '')

    os.makedirs(args.output_dir, exist_ok=True)

    if args.format in ["markdown", "all"]:
        gen.generate_markdown(os.path.join(args.output_dir, f"{base_name}.md"))
    if args.format in ["csv", "all"]:
        gen.generate_csv(os.path.join(args.output_dir, f"{base_name}.csv"))
    if args.format in ["html", "all"]:
        gen.generate_html(os.path.join(args.output_dir, f"{base_name}.html"))

    print(f"Отчеты сгенерированы в {args.output_dir}")
