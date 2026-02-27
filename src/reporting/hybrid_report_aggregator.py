"""
HybridReportAggregator - агрегатор отчетов о тестировании

Объединяет:
- Результаты pytest (динамическое выполнение)
- Статический анализ (bandit, radon, coverage)
- Профилирование производительности

Генерирует компактные отчеты 200-500 токенов вместо 10,000+
"""

import json
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from enum import Enum


class ReportType(Enum):
    """Типы отчетов"""
    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    QUALITY = "QUALITY"
    COVERAGE = "COVERAGE"


class Severity(Enum):
    """Уровни критичности"""
    CRITICAL = "🔴"
    HIGH = "🟡"
    MEDIUM = "🟢"
    LOW = "⚪"


@dataclass
class CompactReport:
    """Компактное представление отчета"""
    method: str  # keyword|llm
    type: str  # SECURITY|PERFORMANCE|...
    scope: str  # Путь к файлам
    status: str  # ✅|❌|⚠️
    summary: str  # 1-2 предложения
    recommendations: List[str]  # Приоритизированный список
    existing_tests: Optional[Dict] = None
    static_analysis: Optional[Dict] = None
    dynamic_analysis: Optional[Dict] = None

    def to_dict(self) -> Dict:
        """Конвертирует в словарь"""
        result = {
            "method": self.method,
            "type": self.type,
            "scope": self.scope,
            "status": self.status,
            "summary": self.summary,
            "recommendations": self.recommendations
        }

        if self.existing_tests:
            result["existing_tests"] = self.existing_tests
        if self.static_analysis:
            result["static_analysis"] = self.static_analysis
        if self.dynamic_analysis:
            result["dynamic_analysis"] = self.dynamic_analysis

        return result


class HybridReportAggregator:
    """
    Агрегатор отчетов для гибридного тестирования

    Объединяет результаты pytest + статического анализа + профилирования
    в компактный отчет 200-500 токенов для LLM анализа.
    """

    def __init__(self):
        """Инициализирует агрегатор"""
        pass

    def aggregate(
        self,
        classification: Dict,
        execution_results: Dict
    ) -> Dict:
        """
        Создает единый компактный отчет

        Args:
            classification: Результат классификации требования
                {
                    "method": "keyword|llm",
                    "type": "SECURITY|PERFORMANCE|...",
                    "scope": "path/to/files"
                }
            execution_results: Результаты выполнения тестов
                {
                    "pytest": {...},
                    "static_analysis": {...},
                    "dynamic_analysis": {...}
                }

        Returns:
            Dict: Компактный отчет
                {
                    "method": "keyword",
                    "type": "SECURITY",
                    "scope": "src/auth",
                    "status": "❌",
                    "existing_tests": {...},
                    "static_analysis": {...},
                    "summary": "Found 3 high severity issues...",
                    "recommendations": ["Fix SQL injection...", ...]
                }
        """
        report_data = {
            "method": classification.get("method", "unknown"),
            "type": classification.get("type", "UNKNOWN"),
            "scope": classification.get("scope", "unknown"),
        }

        # Добавляем результаты pytest
        if "pytest" in execution_results:
            report_data["existing_tests"] = self._format_pytest_results(
                execution_results["pytest"]
            )

        # Добавляем статический анализ
        if "static_analysis" in execution_results:
            report_data["static_analysis"] = self._format_static_analysis(
                execution_results["static_analysis"]
            )

        # Добавляем динамический анализ (профилирование)
        if "dynamic_analysis" in execution_results:
            report_data["dynamic_analysis"] = self._format_dynamic_analysis(
                execution_results["dynamic_analysis"]
            )

        # Определяем общий статус
        report_data["status"] = self._determine_status(report_data)

        # Генерируем summary (1-2 предложения)
        report_data["summary"] = self._generate_summary(report_data)

        # Генерируем recommendations (приоритизированный список)
        report_data["recommendations"] = self._generate_recommendations(report_data)

        return report_data

    def _format_pytest_results(self, pytest_data: Dict) -> Dict:
        """
        Форматирует результаты pytest в компактный вид

        Args:
            pytest_data: Результаты pytest

        Returns:
            Dict: Компактное представление
        """
        failed = pytest_data.get("failed", 0)
        passed = pytest_data.get("passed", 0)

        return {
            "status": "✅" if failed == 0 else "❌",
            "✓": passed,
            "✗": failed,
            "⊘": pytest_data.get("skipped", 0),
            "⏱": f"{pytest_data.get('duration', 0):.2f}s",
            "failures": self._format_failures(pytest_data.get("failures", []))
        }

    def _format_failures(self, failures: List) -> List[Dict]:
        """
        Форматирует информацию о падениях тестов

        Args:
            failures: Список падений

        Returns:
            List[Dict]: Компактные описания
        """
        if not failures:
            return []

        # Берем только первые 3 самых критичных
        formatted = []
        for failure in failures[:3]:
            formatted.append({
                "test": self._shorten_path(failure.get("nodeid", "")),
                "err": failure.get("error_type", "Unknown"),
                "msg": self._truncate(failure.get("message", ""), 50),
                "loc": failure.get("location", "")
            })

        return formatted

    def _format_static_analysis(self, analysis: Dict) -> Dict:
        """
        Форматирует результаты статического анализа

        Args:
            analysis: Результаты инструментов статического анализа
                {
                    "bandit": {...},
                    "radon": {...},
                    "coverage": {...}
                }

        Returns:
            Dict: Компактное представление по типам
        """
        formatted = {}

        # Security (bandit)
        if "bandit" in analysis:
            bandit_data = analysis["bandit"]
            formatted["security"] = {
                "🔴": bandit_data.get("stats", {}).get("high", 0),
                "🟡": bandit_data.get("stats", {}).get("medium", 0),
                "🟢": bandit_data.get("stats", {}).get("low", 0),
                "score": bandit_data.get("score", 0),
                "top_issues": [
                    {
                        "type": issue.get("issue_type", ""),
                        "sev": issue.get("severity", ""),
                        "loc": f"{issue.get('filename', '')}:{issue.get('line', '')}"
                    }
                    for issue in bandit_data.get("issues", [])[:3]
                ]
            }

        # Performance (radon complexity)
        if "radon" in analysis:
            radon_data = analysis["radon"]
            formatted["performance"] = {
                "avg_complexity": radon_data.get("average_complexity", 0),
                "max_complexity": radon_data.get("max_complexity", 0),
                "hotspots": [
                    {
                        "func": h.get("name", ""),
                        "cc": h.get("complexity", 0),
                        "loc": h.get("location", "")
                    }
                    for h in radon_data.get("complex_functions", [])[:3]
                ]
            }

        # Quality (radon maintainability)
        if "quality" in analysis:
            quality_data = analysis["quality"]
            formatted["quality"] = {
                "score": quality_data.get("average_score", 0),
                "rank": quality_data.get("rank", ""),
                "violations": quality_data.get("violations", 0),
                "files_below_b": quality_data.get("files_below_threshold", 0)
            }

        # Coverage
        if "coverage" in analysis:
            cov_data = analysis["coverage"]
            formatted["coverage"] = {
                "total": f"{cov_data.get('percent', 0):.1f}%",
                "Δ": cov_data.get("delta", ""),
                "gaps": [
                    {
                        "file": gap.get("file", ""),
                        "lines": gap.get("lines", ""),
                        "priority": gap.get("priority", "")
                    }
                    for gap in cov_data.get("critical_gaps", [])[:3]
                ]
            }

        return formatted

    def _format_dynamic_analysis(self, dynamic: Dict) -> Dict:
        """
        Форматирует результаты динамического анализа (профилирование)

        Args:
            dynamic: Результаты профилирования

        Returns:
            Dict: Компактное представление
        """
        return {
            "bottlenecks": [
                {
                    "func": b.get("function", ""),
                    "time": f"{b.get('time', 0):.3f}s",
                    "calls": b.get("calls", 0)
                }
                for b in dynamic.get("bottlenecks", [])[:3]
            ],
            "memory_peak": dynamic.get("memory_peak", ""),
            "recommendations": dynamic.get("recommendations", [])[:2]
        }

    def _determine_status(self, report: Dict) -> str:
        """
        Определяет общий статус отчета

        Args:
            report: Данные отчета

        Returns:
            str: Статус-эмодзи (✅|❌|⚠️)
        """
        # Проверяем pytest
        if "existing_tests" in report:
            if report["existing_tests"].get("✗", 0) > 0:
                return "❌"

        # Проверяем статический анализ
        if "static_analysis" in report:
            static = report["static_analysis"]

            # Критичные проблемы безопасности
            if "security" in static:
                if static["security"].get("🔴", 0) > 0:
                    return "❌"
                if static["security"].get("🟡", 0) > 2:
                    return "⚠️"

            # Низкое покрытие
            if "coverage" in static:
                cov_percent = float(static["coverage"]["total"].rstrip("%"))
                if cov_percent < 70:
                    return "⚠️"

        return "✅"

    def _generate_summary(self, report: Dict) -> str:
        """
        Генерирует краткое резюме отчета (1-2 предложения)

        Args:
            report: Данные отчета

        Returns:
            str: Резюме
        """
        req_type = report.get("type", "UNKNOWN")
        scope = report.get("scope", "unknown")

        if req_type == "SECURITY":
            return self._generate_security_summary(report, scope)
        elif req_type == "PERFORMANCE":
            return self._generate_performance_summary(report, scope)
        elif req_type == "QUALITY":
            return self._generate_quality_summary(report, scope)
        elif req_type == "COVERAGE":
            return self._generate_coverage_summary(report, scope)
        else:
            return f"Analysis of {scope} completed with status {report.get('status', '?')}"

    def _generate_security_summary(self, report: Dict, scope: str) -> str:
        """Генерирует summary для security отчета"""
        static = report.get("static_analysis", {})
        security = static.get("security", {})

        high = security.get("🔴", 0)
        medium = security.get("🟡", 0)

        if high > 0:
            return f"🔴 Found {high} critical and {medium} medium security issues in {scope}. Immediate action required."
        elif medium > 0:
            return f"🟡 Found {medium} medium severity security issues in {scope}. Review recommended."
        else:
            return f"✅ No significant security issues found in {scope}."

    def _generate_performance_summary(self, report: Dict, scope: str) -> str:
        """Генерирует summary для performance отчета"""
        static = report.get("static_analysis", {})
        perf = static.get("performance", {})

        max_cc = perf.get("max_complexity", 0)
        avg_cc = perf.get("avg_complexity", 0)

        if max_cc > 15:
            return f"⚠️ High complexity detected in {scope} (max: {max_cc}, avg: {avg_cc:.1f}). Refactoring recommended."
        elif avg_cc > 10:
            return f"🟡 Moderate complexity in {scope} (avg: {avg_cc:.1f}). Consider simplification."
        else:
            return f"✅ Code complexity in {scope} is within acceptable range (avg: {avg_cc:.1f})."

    def _generate_quality_summary(self, report: Dict, scope: str) -> str:
        """Генерирует summary для quality отчета"""
        static = report.get("static_analysis", {})
        quality = static.get("quality", {})

        score = quality.get("score", 0)
        rank = quality.get("rank", "")
        violations = quality.get("violations", 0)

        if rank in ["A", "B"]:
            return f"✅ Code quality in {scope} is good (score: {score:.1f}, rank: {rank})."
        elif rank == "C":
            return f"🟡 Code quality in {scope} needs improvement (score: {score:.1f}, {violations} violations)."
        else:
            return f"🔴 Poor code quality in {scope} (score: {score:.1f}, rank: {rank}). Significant refactoring needed."

    def _generate_coverage_summary(self, report: Dict, scope: str) -> str:
        """Генерирует summary для coverage отчета"""
        static = report.get("static_analysis", {})
        coverage = static.get("coverage", {})

        total = coverage.get("total", "0%")
        gaps_count = len(coverage.get("gaps", []))

        percent = float(total.rstrip("%"))

        if percent >= 80:
            return f"✅ Test coverage in {scope} is good ({total})."
        elif percent >= 60:
            return f"🟡 Test coverage in {scope} is moderate ({total}). {gaps_count} critical gaps identified."
        else:
            return f"🔴 Low test coverage in {scope} ({total}). {gaps_count} critical gaps need attention."

    def _generate_recommendations(self, report: Dict) -> List[str]:
        """
        Генерирует приоритизированный список рекомендаций

        Args:
            report: Данные отчета

        Returns:
            List[str]: Список рекомендаций в порядке приоритета
        """
        recommendations = []

        # Из pytest failures
        if "existing_tests" in report:
            failed = report["existing_tests"].get("✗", 0)
            if failed > 0:
                recommendations.append(
                    f"🔴 Fix {failed} failing test{'s' if failed > 1 else ''}"
                )

        # Из статического анализа - security
        if "static_analysis" in report:
            static = report["static_analysis"]

            if "security" in static:
                security = static["security"]
                critical = security.get("🔴", 0)
                high = security.get("🟡", 0)

                if critical > 0:
                    recommendations.append(
                        f"🔴 Address {critical} critical security issue{'s' if critical > 1 else ''} immediately"
                    )
                elif high > 2:
                    recommendations.append(
                        f"🟡 Review and fix {high} medium security issues"
                    )

            # Performance
            if "performance" in static:
                perf = static["performance"]
                if perf.get("max_complexity", 0) > 15:
                    recommendations.append(
                        "🟡 Refactor high-complexity functions (CC > 15)"
                    )

            # Quality
            if "quality" in static:
                quality = static["quality"]
                if quality.get("rank", "") in ["D", "F"]:
                    recommendations.append(
                        "🟡 Improve code quality (current rank: {})".format(
                            quality.get("rank", "")
                        )
                    )

            # Coverage
            if "coverage" in static:
                cov = static["coverage"]
                percent = float(cov.get("total", "0%").rstrip("%"))
                gaps_count = len(cov.get("gaps", []))

                if percent < 80 and gaps_count > 0:
                    recommendations.append(
                        f"🟢 Add tests to cover {gaps_count} critical gap{'s' if gaps_count > 1 else ''}"
                    )

        # Из динамического анализа
        if "dynamic_analysis" in report:
            dynamic = report["dynamic_analysis"]
            bottlenecks = dynamic.get("bottlenecks", [])

            if bottlenecks:
                recommendations.append(
                    f"🟢 Optimize {len(bottlenecks)} performance bottleneck{'s' if len(bottlenecks) > 1 else ''}"
                )

        # Если нет рекомендаций, добавляем общую
        if not recommendations:
            recommendations.append("✅ All checks passed. No immediate actions required.")

        return recommendations

    def _shorten_path(self, path: str) -> str:
        """
        Сокращает путь к тесту для экономии токенов

        Args:
            path: Полный путь

        Returns:
            str: Сокращенный путь
        """
        return path.replace("tests/", "").replace("test_", "")

    def _truncate(self, text: str, max_length: int) -> str:
        """
        Обрезает текст с многоточием

        Args:
            text: Текст
            max_length: Максимальная длина

        Returns:
            str: Обрезанный текст
        """
        if len(text) <= max_length:
            return text
        return text[:max_length - 3] + "..."

    def to_json(self, report: Dict, compact: bool = True) -> str:
        """
        Конвертирует отчет в JSON

        Args:
            report: Данные отчета
            compact: Компактный формат (без пробелов)

        Returns:
            str: JSON строка
        """
        if compact:
            return json.dumps(
                report,
                ensure_ascii=False,
                separators=(',', ':')
            )
        else:
            return json.dumps(
                report,
                ensure_ascii=False,
                indent=2
            )

    def estimate_tokens(self, report: Dict) -> int:
        """
        Оценивает количество токенов в отчете

        Args:
            report: Данные отчета

        Returns:
            int: Примерное количество токенов
        """
        json_str = self.to_json(report, compact=True)
        # Приблизительная оценка: 1 токен ≈ 4 символа
        return len(json_str) // 4
