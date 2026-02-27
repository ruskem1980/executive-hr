#!/usr/bin/env python3
"""
Validator - валидация полноты и качества переводов.

Двухфазная валидация:
1. Python (алгоритмическая) - формирует детальный отчёт:
   - Наличие перевода для каждого элемента
   - Целостность плейсхолдеров
   - Консистентность терминологии
   - Покрытие по категориям и файлам
   - Обнаружение непереведённых фрагментов внутри переведённых строк

2. LLM (выборочная) - получает отчёт и:
   - Проверяет качество случайной выборки переводов
   - Предлагает исправления для обнаруженных проблем
   - Применяет точечные правки к каталогу
"""

import json
import re
import random
import subprocess
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, field, asdict

from .catalog import TranslationCatalog, TranslationEntry
from .scanner import ProjectScanner, detect_language, has_translatable_content


# ============================================================================
# ФАЗА 1: АЛГОРИТМИЧЕСКАЯ ВАЛИДАЦИЯ (Python)
# ============================================================================

@dataclass
class ValidationIssue:
    """Проблема валидации."""
    severity: str           # critical | warning | info
    category: str           # missing | placeholder | consistency | quality | orphan
    original: str
    translated: str = ""
    message: str = ""
    file: str = ""
    line: int = 0
    suggestion: str = ""


@dataclass
class ValidationReport:
    """Отчёт валидации."""
    timestamp: str = ""
    source_locale: str = ""
    target_locale: str = ""

    # Общая статистика
    total_strings: int = 0
    translated_count: int = 0
    missing_count: int = 0
    coverage_percent: float = 0.0

    # Детализация
    by_category: Dict = field(default_factory=dict)
    by_file: Dict = field(default_factory=dict)
    by_severity: Dict = field(default_factory=dict)

    # Проблемы
    issues: List[dict] = field(default_factory=list)

    # Для LLM
    sample_for_review: List[dict] = field(default_factory=list)
    llm_corrections: List[dict] = field(default_factory=list)

    def to_dict(self) -> Dict:
        return asdict(self)

    def to_json(self, compact: bool = False) -> str:
        if compact:
            return json.dumps(self.to_dict(), ensure_ascii=False, separators=(',', ':'))
        return json.dumps(self.to_dict(), ensure_ascii=False, indent=2)

    @property
    def has_critical_issues(self) -> bool:
        return self.by_severity.get("critical", 0) > 0

    @property
    def is_complete(self) -> bool:
        return self.missing_count == 0 and not self.has_critical_issues


class TranslationValidator:
    """
    Валидатор переводов.

    Фаза 1 (Python):
    - Полнота покрытия переводами
    - Целостность плейсхолдеров
    - Консистентность терминов
    - Обнаружение смешанных языков
    - Формирование отчёта

    Фаза 2 (LLM):
    - Выборочная проверка качества
    - Предложение исправлений
    - Применение точечных правок
    """

    def __init__(self, catalog: TranslationCatalog,
                 project_root: Optional[Path] = None):
        self.catalog = catalog
        self.project_root = project_root or Path.cwd()

        # Терминологический глоссарий (ожидаемые переводы ключевых терминов)
        self.glossary = {
            "en_to_ru": {
                "security": "безопасност",
                "performance": "производительност",
                "coverage": "покрыт",
                "vulnerability": "уязвимост",
                "issue": "проблем",
                "error": "ошибк",
                "warning": "предупрежден",
                "recommendation": "рекомендаци",
                "analysis": "анализ",
                "report": "отчёт",
                "test": "тест",
                "quality": "качеств",
            },
            "ru_to_en": {
                "безопасность": "security",
                "производительность": "performance",
                "покрытие": "coverage",
                "уязвимость": "vulnerability",
                "проблема": "issue",
                "ошибка": "error",
                "предупреждение": "warning",
                "рекомендация": "recommendation",
                "анализ": "analysis",
                "отчёт": "report",
                "тест": "test",
                "качество": "quality",
            }
        }

    # =========================================================================
    # ФАЗА 1: АЛГОРИТМИЧЕСКАЯ ВАЛИДАЦИЯ
    # =========================================================================

    def validate(self, source_locale: str, target_locale: str,
                 sample_size: int = 20) -> ValidationReport:
        """
        Запускает полную валидацию переводов.

        Args:
            source_locale: Исходный язык
            target_locale: Целевой язык
            sample_size: Размер выборки для LLM-проверки

        Returns:
            ValidationReport с полным отчётом
        """
        report = ValidationReport(
            timestamp=datetime.now().isoformat(),
            source_locale=source_locale,
            target_locale=target_locale,
        )

        entries = self.catalog.load_full(target_locale)
        if not entries:
            report.total_strings = 0
            report.issues.append(asdict(ValidationIssue(
                severity="critical",
                category="missing",
                original="",
                message=f"Каталог для локали '{target_locale}' пуст или отсутствует"
            )))
            return report

        report.total_strings = len(entries)

        # 1. Проверка наличия переводов
        self._check_completeness(entries, report)

        # 2. Проверка плейсхолдеров
        self._check_placeholders(entries, report)

        # 3. Проверка консистентности терминов
        self._check_terminology(entries, source_locale, target_locale, report)

        # 4. Проверка смешанных языков
        self._check_mixed_languages(entries, target_locale, report)

        # 5. Проверка длины переводов (аномалии)
        self._check_length_anomalies(entries, report)

        # 6. Статистика по категориям и файлам
        self._compute_category_stats(entries, report)
        self._compute_file_stats(entries, report)

        # 7. Подсчёт severity
        severity_counts = {}
        for issue in report.issues:
            sev = issue.get("severity", "info")
            severity_counts[sev] = severity_counts.get(sev, 0) + 1
        report.by_severity = severity_counts

        # 8. Формируем выборку для LLM
        report.sample_for_review = self._select_sample_for_llm(
            entries, report, sample_size
        )

        return report

    def _check_completeness(self, entries: Dict[str, TranslationEntry],
                            report: ValidationReport):
        """Проверяет наличие перевода для каждой строки."""
        translated = 0
        missing = 0

        for key, entry in entries.items():
            if entry.status == "orphaned":
                continue  # Пропускаем удалённые

            if entry.translated and entry.translated.strip():
                translated += 1
            else:
                missing += 1
                report.issues.append(asdict(ValidationIssue(
                    severity="critical",
                    category="missing",
                    original=key[:100],
                    message="Отсутствует перевод",
                    file=entry.source_file,
                    line=entry.source_line,
                )))

        report.translated_count = translated
        report.missing_count = missing
        report.coverage_percent = round(
            translated / max(len(entries), 1) * 100, 1
        )

    def _check_placeholders(self, entries: Dict[str, TranslationEntry],
                            report: ValidationReport):
        """Проверяет сохранность плейсхолдеров в переводах."""
        placeholder_pattern = re.compile(r'\{[^}]*\}|%[sd]|%\([^)]+\)[sd]')

        for key, entry in entries.items():
            if not entry.translated:
                continue

            original_ph = set(placeholder_pattern.findall(key))
            translated_ph = set(placeholder_pattern.findall(entry.translated))

            if original_ph and original_ph != translated_ph:
                missing_ph = original_ph - translated_ph
                extra_ph = translated_ph - original_ph

                msg_parts = []
                if missing_ph:
                    msg_parts.append(f"потеряны: {', '.join(missing_ph)}")
                if extra_ph:
                    msg_parts.append(f"добавлены: {', '.join(extra_ph)}")

                report.issues.append(asdict(ValidationIssue(
                    severity="critical",
                    category="placeholder",
                    original=key[:80],
                    translated=entry.translated[:80],
                    message=f"Несовпадение плейсхолдеров: {'; '.join(msg_parts)}",
                    file=entry.source_file,
                    suggestion=f"Плейсхолдеры в оригинале: {', '.join(original_ph)}"
                )))

    def _check_terminology(self, entries: Dict[str, TranslationEntry],
                           source_locale: str, target_locale: str,
                           report: ValidationReport):
        """Проверяет консистентность ключевых терминов."""
        direction = f"{source_locale}_to_{target_locale}"
        glossary = self.glossary.get(direction, {})

        if not glossary:
            return

        for key, entry in entries.items():
            if not entry.translated:
                continue

            for source_term, expected_root in glossary.items():
                # Проверяем только если оригинал содержит термин
                if source_term.lower() not in key.lower():
                    continue

                # Проверяем наличие ожидаемого корня в переводе
                if expected_root.lower() not in entry.translated.lower():
                    report.issues.append(asdict(ValidationIssue(
                        severity="warning",
                        category="consistency",
                        original=key[:80],
                        translated=entry.translated[:80],
                        message=f"Термин '{source_term}' обычно переводится с корнем '{expected_root}'",
                        suggestion=f"Проверьте перевод термина '{source_term}'"
                    )))

    def _check_mixed_languages(self, entries: Dict[str, TranslationEntry],
                                target_locale: str,
                                report: ValidationReport):
        """Обнаруживает непереведённые фрагменты внутри переведённых строк."""
        # Определяем какой алфавит ожидается
        if target_locale == "ru":
            # Для русского - ищем длинные латинские фразы (не технические термины)
            unexpected_pattern = re.compile(
                r'(?<![A-Z_])\b[a-z]{3,}\s+[a-z]{3,}(?:\s+[a-z]{3,})*\b'
            )
        elif target_locale == "en":
            # Для английского - ищем кириллицу
            unexpected_pattern = re.compile(r'[а-яА-ЯёЁ]{3,}')
        else:
            return

        # Технические термины которые НЕ нужно переводить
        tech_terms = {
            "sql", "api", "json", "yaml", "xml", "html", "css", "http", "https",
            "pytest", "bandit", "pylint", "radon", "flake8", "semgrep", "coverage",
            "cve", "xss", "csrf", "dry", "solid", "cprofile", "memory_profiler",
            "pydeps", "mccabe", "ruff", "mypy", "safety", "pip", "npm",
            "git", "docker", "redis", "nginx", "postgresql", "mongodb",
        }

        for key, entry in entries.items():
            if not entry.translated:
                continue

            matches = unexpected_pattern.findall(entry.translated)
            non_tech_matches = [
                m for m in matches
                if m.lower().strip() not in tech_terms and len(m) > 5
            ]

            if non_tech_matches:
                report.issues.append(asdict(ValidationIssue(
                    severity="warning",
                    category="quality",
                    original=key[:80],
                    translated=entry.translated[:80],
                    message=f"Возможно непереведённые фрагменты: {', '.join(non_tech_matches[:3])}",
                    suggestion="Проверьте полноту перевода"
                )))

    def _check_length_anomalies(self, entries: Dict[str, TranslationEntry],
                                 report: ValidationReport):
        """Обнаруживает аномалии длины переводов."""
        for key, entry in entries.items():
            if not entry.translated:
                continue

            orig_len = len(key)
            trans_len = len(entry.translated)

            # Перевод значительно короче (возможно неполный)
            if orig_len > 20 and trans_len < orig_len * 0.3:
                report.issues.append(asdict(ValidationIssue(
                    severity="warning",
                    category="quality",
                    original=key[:60],
                    translated=entry.translated[:60],
                    message=f"Перевод подозрительно короткий ({trans_len} vs {orig_len} символов)",
                    suggestion="Проверьте полноту перевода"
                )))

            # Перевод = оригинал (не переведено?)
            if key == entry.translated and detect_language(key) != "unknown":
                lang = detect_language(key)
                if lang not in ("unknown", "mixed"):
                    report.issues.append(asdict(ValidationIssue(
                        severity="info",
                        category="quality",
                        original=key[:60],
                        message="Перевод идентичен оригиналу",
                        suggestion="Возможно строка не была переведена"
                    )))

    def _compute_category_stats(self, entries: Dict[str, TranslationEntry],
                                 report: ValidationReport):
        """Считает статистику по категориям."""
        cats: Dict[str, Dict] = {}

        for entry in entries.values():
            cat = entry.category or "unknown"
            if cat not in cats:
                cats[cat] = {"total": 0, "translated": 0, "missing": 0}
            cats[cat]["total"] += 1
            if entry.translated:
                cats[cat]["translated"] += 1
            else:
                cats[cat]["missing"] += 1

        for cat, data in cats.items():
            data["coverage"] = round(
                data["translated"] / max(data["total"], 1) * 100, 1
            )

        report.by_category = cats

    def _compute_file_stats(self, entries: Dict[str, TranslationEntry],
                             report: ValidationReport):
        """Считает статистику по файлам."""
        files: Dict[str, Dict] = {}

        for entry in entries.values():
            f = entry.source_file or "unknown"
            if f not in files:
                files[f] = {"total": 0, "translated": 0, "missing": 0}
            files[f]["total"] += 1
            if entry.translated:
                files[f]["translated"] += 1
            else:
                files[f]["missing"] += 1

        for f, data in files.items():
            data["coverage"] = round(
                data["translated"] / max(data["total"], 1) * 100, 1
            )

        report.by_file = files

    def _select_sample_for_llm(self, entries: Dict[str, TranslationEntry],
                                report: ValidationReport,
                                sample_size: int) -> List[dict]:
        """
        Формирует выборку для LLM-проверки.

        Стратегия: приоритет строкам с warning/info issues + случайные.
        """
        sample = []

        # 1. Строки с проблемами (не critical - те уже очевидны)
        issue_keys = set()
        for issue in report.issues:
            if issue.get("severity") in ("warning", "info"):
                key = issue.get("original", "")
                if key and key in entries and entries[key].translated:
                    issue_keys.add(key)

        for key in list(issue_keys)[:sample_size // 2]:
            entry = entries[key]
            sample.append({
                "original": key,
                "translated": entry.translated,
                "category": entry.category,
                "context": entry.context,
                "file": entry.source_file,
            })

        # 2. Случайные переведённые строки
        remaining = sample_size - len(sample)
        translated_keys = [
            k for k, v in entries.items()
            if v.translated and k not in issue_keys
        ]
        random_keys = random.sample(
            translated_keys, min(remaining, len(translated_keys))
        )

        for key in random_keys:
            entry = entries[key]
            sample.append({
                "original": key,
                "translated": entry.translated,
                "category": entry.category,
                "context": entry.context,
                "file": entry.source_file,
            })

        return sample

    # =========================================================================
    # ФАЗА 2: LLM ПРОВЕРКА И ПРАВКИ
    # =========================================================================

    def llm_review(self, report: ValidationReport,
                   source_locale: str, target_locale: str,
                   llm_backend: str = "gemini",
                   llm_model: str = "pro",
                   gemini_bridge_path: str = "") -> ValidationReport:
        """
        Отправляет отчёт + выборку в LLM для проверки качества.

        LLM получает:
        - Сводку отчёта (статистика, проблемы)
        - Выборку переводов
        - Просьбу проверить и предложить исправления

        Returns:
            Обновлённый отчёт с llm_corrections
        """
        if not report.sample_for_review:
            print("  Нет строк для LLM-проверки")
            return report

        prompt = self._build_review_prompt(report, source_locale, target_locale)

        try:
            response = self._call_review_llm(
                prompt, llm_backend, llm_model, gemini_bridge_path
            )
            corrections = self._parse_review_response(response)
            report.llm_corrections = corrections

            print(f"  LLM предложил {len(corrections)} исправлений")

        except Exception as e:
            print(f"  Ошибка LLM-проверки: {e}")
            report.llm_corrections = []

        return report

    def apply_corrections(self, report: ValidationReport,
                          target_locale: str,
                          auto_apply: bool = False) -> int:
        """
        Применяет LLM-исправления к каталогу.

        Args:
            report: Отчёт с llm_corrections
            target_locale: Целевая локаль
            auto_apply: Применить без подтверждения

        Returns:
            Количество применённых исправлений
        """
        if not report.llm_corrections:
            return 0

        entries = self.catalog.load_full(target_locale)
        applied = 0

        for correction in report.llm_corrections:
            original = correction.get("original", "")
            new_translation = correction.get("corrected", "")
            reason = correction.get("reason", "")

            if not original or not new_translation:
                continue

            if original not in entries:
                continue

            old_translation = entries[original].translated

            if auto_apply:
                entries[original].translated = new_translation
                entries[original].status = "reviewed"
                entries[original].translator = "llm_review"
                entries[original].updated_at = datetime.now().isoformat()
                applied += 1
                print(f"    Исправлено: '{old_translation[:40]}' -> '{new_translation[:40]}' ({reason})")
            else:
                print(f"\n  Предложение:")
                print(f"    Оригинал:  {original[:60]}")
                print(f"    Было:      {old_translation[:60]}")
                print(f"    Стало:     {new_translation[:60]}")
                print(f"    Причина:   {reason}")

        if applied > 0:
            self.catalog.save(target_locale, entries)

        return applied

    def _build_review_prompt(self, report: ValidationReport,
                             source_locale: str, target_locale: str) -> str:
        """Строит промпт для LLM-проверки."""
        locale_names = {
            "ru": "русский", "en": "английский", "de": "немецкий",
            "fr": "французский", "es": "испанский",
        }
        source_name = locale_names.get(source_locale, source_locale)
        target_name = locale_names.get(target_locale, target_locale)

        # Формируем сводку отчёта
        summary = (
            f"Проект: система анализа кода (IT-инструмент)\n"
            f"Перевод: {source_name} -> {target_name}\n"
            f"Всего строк: {report.total_strings}\n"
            f"Переведено: {report.translated_count} ({report.coverage_percent}%)\n"
            f"Проблем: {len(report.issues)} "
            f"(critical: {report.by_severity.get('critical', 0)}, "
            f"warning: {report.by_severity.get('warning', 0)})\n"
        )

        # Проблемные строки
        issues_text = ""
        warning_issues = [i for i in report.issues if i.get("severity") == "warning"]
        if warning_issues:
            issues_lines = []
            for issue in warning_issues[:10]:
                issues_lines.append(
                    f"  - [{issue.get('category')}] '{issue.get('original', '')[:50]}' -> "
                    f"'{issue.get('translated', '')[:50]}': {issue.get('message', '')}"
                )
            issues_text = "ОБНАРУЖЕННЫЕ ПРОБЛЕМЫ:\n" + "\n".join(issues_lines)

        # Выборка для проверки
        sample_lines = []
        for item in report.sample_for_review:
            sample_lines.append(
                f"  Оригинал ({source_locale}): {item['original'][:80]}\n"
                f"  Перевод ({target_locale}): {item['translated'][:80]}\n"
                f"  Категория: {item.get('category', 'unknown')}\n"
            )
        sample_text = "\n".join(sample_lines)

        prompt = f"""Ты эксперт по локализации IT-продуктов.

ОТЧЁТ ВАЛИДАЦИИ:
{summary}

{issues_text}

ВЫБОРКА ПЕРЕВОДОВ ДЛЯ ПРОВЕРКИ:
{sample_text}

ЗАДАЧА:
1. Проверь качество переводов в выборке
2. Найди ошибки: неточные переводы, стилистические проблемы, потерянный контекст
3. Предложи исправления ТОЛЬКО для реально некачественных переводов

ФОРМАТ ОТВЕТА - JSON массив исправлений:
[
  {{
    "original": "исходная строка",
    "corrected": "исправленный перевод",
    "reason": "причина исправления (кратко)"
  }}
]

Если все переводы хорошие, верни пустой массив: []
Верни ТОЛЬКО JSON, без пояснений."""

        return prompt

    def _call_review_llm(self, prompt: str, backend: str,
                         model: str, bridge_path: str) -> str:
        """Вызывает LLM для проверки."""
        if backend == "gemini":
            if bridge_path and Path(bridge_path).exists():
                result = subprocess.run(
                    ["bash", bridge_path, model, prompt],
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode == 0:
                    return result.stdout.strip()
                raise Exception(f"Gemini bridge error: {result.stderr}")
            else:
                # Прямой вызов gemini CLI
                try:
                    result = subprocess.run(
                        ["gemini", "-m", f"gemini-2.5-{model}", "-p", prompt],
                        capture_output=True, text=True, timeout=120
                    )
                    if result.returncode == 0:
                        return result.stdout.strip()
                    raise Exception(f"Gemini CLI error: {result.stderr}")
                except FileNotFoundError:
                    raise Exception("Gemini CLI не найден")
        else:
            raise Exception(f"Backend '{backend}' для review пока не поддержан")

    def _parse_review_response(self, response: str) -> List[dict]:
        """Парсит ответ LLM с исправлениями."""
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r'```(?:json)?\n?', '', cleaned).strip()

        try:
            corrections = json.loads(cleaned)
            if isinstance(corrections, list):
                # Валидируем формат
                valid = []
                for c in corrections:
                    if isinstance(c, dict) and "original" in c and "corrected" in c:
                        valid.append({
                            "original": c["original"],
                            "corrected": c["corrected"],
                            "reason": c.get("reason", ""),
                        })
                return valid
        except json.JSONDecodeError:
            pass

        return []

    # =========================================================================
    # ГЕНЕРАЦИЯ ОТЧЁТА
    # =========================================================================

    def print_report(self, report: ValidationReport):
        """Выводит отчёт в консоль."""
        print(f"\n{'='*70}")
        print(f"  ОТЧЁТ ВАЛИДАЦИИ ПЕРЕВОДОВ")
        print(f"  {report.source_locale} -> {report.target_locale}")
        print(f"  {report.timestamp}")
        print(f"{'='*70}\n")

        # Общая статистика
        status = "PASS" if report.is_complete else "FAIL"
        emoji = "✅" if report.is_complete else "❌"
        print(f"  {emoji} Статус: {status}")
        print(f"  Всего строк:     {report.total_strings}")
        print(f"  Переведено:      {report.translated_count}")
        print(f"  Не переведено:   {report.missing_count}")
        print(f"  Покрытие:        {report.coverage_percent}%")

        # Проблемы по severity
        if report.by_severity:
            print(f"\n  Проблемы:")
            for sev, count in sorted(report.by_severity.items()):
                icon = {"critical": "🔴", "warning": "🟡", "info": "🔵"}.get(sev, "⚪")
                print(f"    {icon} {sev}: {count}")

        # По категориям
        if report.by_category:
            print(f"\n  Покрытие по категориям:")
            for cat, data in sorted(report.by_category.items()):
                bar = self._progress_bar(data.get("coverage", 0))
                print(f"    {cat:<20} {bar} {data.get('coverage', 0)}% "
                      f"({data.get('translated', 0)}/{data.get('total', 0)})")

        # По файлам
        if report.by_file:
            print(f"\n  Покрытие по файлам:")
            for f, data in sorted(report.by_file.items(),
                                   key=lambda x: x[1].get("coverage", 0)):
                bar = self._progress_bar(data.get("coverage", 0))
                print(f"    {f:<35} {bar} {data.get('coverage', 0)}%")

        # Критические проблемы (первые 10)
        critical = [i for i in report.issues if i.get("severity") == "critical"]
        if critical:
            print(f"\n  🔴 Критические проблемы ({len(critical)}):")
            for issue in critical[:10]:
                print(f"    [{issue.get('category')}] {issue.get('message')}")
                print(f"      Строка: '{issue.get('original', '')[:60]}'")
                if issue.get("file"):
                    print(f"      Файл: {issue.get('file')}:{issue.get('line', '')}")

        # LLM-исправления
        if report.llm_corrections:
            print(f"\n  🤖 LLM предложил исправления ({len(report.llm_corrections)}):")
            for c in report.llm_corrections:
                print(f"    Оригинал:   {c.get('original', '')[:50]}")
                print(f"    Исправлено: {c.get('corrected', '')[:50]}")
                print(f"    Причина:    {c.get('reason', '')}")
                print()

        print(f"{'='*70}\n")

    def save_report(self, report: ValidationReport, output_path: Path):
        """Сохраняет отчёт в JSON-файл."""
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            f.write(report.to_json())
        print(f"  Отчёт сохранён: {output_path}")

    @staticmethod
    def _progress_bar(percent: float, width: int = 20) -> str:
        """Текстовый прогресс-бар."""
        filled = int(width * percent / 100)
        bar = "█" * filled + "░" * (width - filled)
        return f"[{bar}]"
