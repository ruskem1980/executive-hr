#!/usr/bin/env python3
"""
Главный workflow - интеграция всех компонентов системы интеллектуальной предобработки.

Workflow:
User Query → HybridClassifier → SmartExecutor → ToolOrchestrator
  → HybridReportAggregator → complexity determination → model selection
  → LLM prompt → Gemini Bridge → response

Автор: PT_Standart
"""

import json
import argparse
import subprocess
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, asdict

from src.reporting.token_tracker import TokenTracker


# ============================================================================
# ENUMS & DATA CLASSES
# ============================================================================

class RequestType(Enum):
    """Типы запросов пользователя"""
    SECURITY = "security"
    PERFORMANCE = "performance"
    REFACTORING = "refactoring"
    DEBUGGING = "debugging"
    TESTING = "testing"
    DOCUMENTATION = "documentation"
    ARCHITECTURE = "architecture"


class Severity(Enum):
    """Уровни критичности проблем"""
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    CRITICAL = "CRITICAL"


class Complexity(Enum):
    """Сложность задачи для маршрутизации моделей"""
    SIMPLE = "SIMPLE"
    MEDIUM = "MEDIUM"
    COMPLEX = "COMPLEX"


@dataclass
class Issue:
    """Найденная проблема"""
    type: str
    severity: str
    message: str
    file: Optional[str] = None
    line: Optional[int] = None
    suggestion: Optional[str] = None


@dataclass
class Classification:
    """Результат классификации запроса"""
    primary_type: RequestType
    confidence: float
    tools: List[str]
    scope: str
    keywords: List[str]


@dataclass
class Report:
    """Компактный отчет для LLM"""
    summary: str
    issues: List[Issue]
    metrics: Dict
    recommendations: List[str]
    files_analyzed: int
    total_issues: int
    critical_issues: int


# ============================================================================
# HYBRID CLASSIFIER
# ============================================================================

class HybridClassifier:
    """
    Классификатор запросов пользователя (упрощенная версия).

    Определяет тип задачи, необходимые инструменты и scope анализа.
    """

    def __init__(self):
        self.keywords_map = {
            RequestType.SECURITY: ["безопасност", "уязвимост", "CVE", "inject", "auth", "XSS", "SQL"],
            RequestType.PERFORMANCE: ["производит", "оптимиз", "медленн", "быстр", "профайл", "benchmark"],
            RequestType.REFACTORING: ["рефактор", "улучш", "переписа", "код смелл", "DRY", "SOLID"],
            RequestType.DEBUGGING: ["баг", "ошибк", "не работа", "debug", "исправ", "проблем"],
            RequestType.TESTING: ["тест", "покрыт", "unittest", "pytest", "test coverage"],
            RequestType.DOCUMENTATION: ["документац", "docstring", "комментар", "README"],
            RequestType.ARCHITECTURE: ["архитектур", "дизайн", "паттерн", "структур", "модул"],
        }

        self.tools_map = {
            RequestType.SECURITY: ["bandit", "semgrep", "safety"],
            RequestType.PERFORMANCE: ["profiler", "memory_profiler", "benchmark"],
            RequestType.REFACTORING: ["radon", "pylint", "flake8"],
            RequestType.DEBUGGING: ["debugger", "logger", "tracer"],
            RequestType.TESTING: ["pytest", "coverage", "test_analyzer"],
            RequestType.DOCUMENTATION: ["doc_analyzer", "pydoc"],
            RequestType.ARCHITECTURE: ["structure_analyzer", "dependency_graph"],
        }

    def classify(self, user_query: str) -> Classification:
        """Классифицирует запрос пользователя"""
        query_lower = user_query.lower()

        # Подсчет совпадений ключевых слов
        scores = {}
        matched_keywords = []

        for req_type, keywords in self.keywords_map.items():
            score = sum(1 for kw in keywords if kw in query_lower)
            scores[req_type] = score
            if score > 0:
                matched_keywords.extend([kw for kw in keywords if kw in query_lower])

        # Определение основного типа
        if not scores or max(scores.values()) == 0:
            primary_type = RequestType.DEBUGGING  # default
            confidence = 0.5
        else:
            primary_type = max(scores, key=scores.get)
            total_keywords = sum(len(kws) for kws in self.keywords_map.values())
            confidence = min(scores[primary_type] / 5.0, 1.0)  # normalize

        # Определение scope
        scope = "module"  # default
        if "все" in query_lower or "весь проект" in query_lower:
            scope = "project"
        elif "файл" in query_lower or "функци" in query_lower:
            scope = "file"

        # Подбор инструментов
        tools = self.tools_map.get(primary_type, ["generic_analyzer"])

        return Classification(
            primary_type=primary_type,
            confidence=confidence,
            tools=tools,
            scope=scope,
            keywords=matched_keywords[:5]  # top 5
        )


# ============================================================================
# SMART EXECUTOR (Mock)
# ============================================================================

class SmartExecutor:
    """
    Умный исполнитель инструментов анализа (Mock версия).

    В реальной версии запускает реальные инструменты (bandit, pylint, etc).
    """

    def __init__(self, project_root: Path):
        self.project_root = project_root

    def execute(self, classification: Classification) -> Dict:
        """Запускает инструменты и собирает результаты"""
        print(f"🔧 Executing tools: {', '.join(classification.tools)}")

        # Mock результаты для демонстрации
        issues = []

        if RequestType.SECURITY in [classification.primary_type]:
            issues.extend([
                Issue(
                    type="SQL_INJECTION",
                    severity=Severity.HIGH.value,
                    message="Possible SQL injection vulnerability",
                    file="src/database/queries.py",
                    line=42,
                    suggestion="Use parameterized queries"
                ),
                Issue(
                    type="HARDCODED_PASSWORD",
                    severity=Severity.CRITICAL.value,
                    message="Hardcoded password detected",
                    file="src/config/settings.py",
                    line=15,
                    suggestion="Use environment variables"
                ),
            ])

        if RequestType.PERFORMANCE in [classification.primary_type]:
            issues.extend([
                Issue(
                    type="INEFFICIENT_LOOP",
                    severity=Severity.MEDIUM.value,
                    message="Nested loop with O(n²) complexity",
                    file="src/api/handlers.py",
                    line=128,
                    suggestion="Use dictionary lookup instead"
                ),
                Issue(
                    type="MEMORY_LEAK",
                    severity=Severity.HIGH.value,
                    message="Potential memory leak in cache",
                    file="src/cache/manager.py",
                    line=67,
                    suggestion="Implement cache eviction policy"
                ),
            ])

        # Метрики
        metrics = {
            "execution_time_ms": 1234,
            "files_scanned": 45,
            "lines_of_code": 5678,
            "tools_used": len(classification.tools)
        }

        return {
            "issues": [asdict(issue) for issue in issues],
            "metrics": metrics
        }


# ============================================================================
# HYBRID REPORT AGGREGATOR
# ============================================================================

class HybridReportAggregator:
    """
    Агрегатор отчетов - создает компактный отчет для LLM.

    Объединяет результаты всех инструментов в единый структурированный отчет.
    """

    def aggregate(self, classification: Classification, executor_results: Dict) -> Report:
        """Создает компактный отчет"""
        issues_data = executor_results.get("issues", [])
        metrics = executor_results.get("metrics", {})

        # Конвертация в объекты Issue
        issues = [Issue(**issue_dict) for issue_dict in issues_data]

        # Подсчет критичных проблем
        critical_count = sum(1 for issue in issues if issue.severity == Severity.CRITICAL.value)

        # Генерация summary
        summary = f"Found {len(issues)} issues"
        if critical_count > 0:
            summary += f", including {critical_count} CRITICAL"

        # Генерация рекомендаций
        recommendations = []
        if critical_count > 0:
            recommendations.append("Address CRITICAL issues immediately")
        if len(issues) > 10:
            recommendations.append("Consider incremental refactoring")
        if classification.primary_type == RequestType.SECURITY:
            recommendations.append("Run security audit before deployment")

        return Report(
            summary=summary,
            issues=issues,
            metrics=metrics,
            recommendations=recommendations,
            files_analyzed=metrics.get("files_scanned", 0),
            total_issues=len(issues),
            critical_issues=critical_count
        )


# ============================================================================
# COMPLEXITY DETERMINATION & MODEL SELECTION
# ============================================================================

def determine_complexity(report: Report) -> Complexity:
    """
    Определяет сложность задачи на основе отчета.

    Правила:
    - SIMPLE: 1-2 проблемы, все LOW/MEDIUM
    - MEDIUM: 3-10 проблем или есть HIGH
    - COMPLEX: >10 проблем или есть CRITICAL
    """
    issues_count = report.total_issues
    has_critical = report.critical_issues > 0
    has_high = any(issue.severity == Severity.HIGH.value for issue in report.issues)

    if has_critical or issues_count > 10:
        return Complexity.COMPLEX
    elif issues_count > 3 or has_high:
        return Complexity.MEDIUM
    else:
        return Complexity.SIMPLE


def select_model(complexity: Complexity) -> str:
    """
    Выбирает модель Gemini на основе сложности.

    Маршрутизация:
    - SIMPLE → flash ($0.50/$3.00 per 1M tokens)
    - MEDIUM → pro ($2.00/$12.00 per 1M tokens)
    - COMPLEX → pro (используем лучшую доступную модель в Gemini)

    Примечание: Для критически сложных задач Opus должен работать
    напрямую без делегирования, но это выходит за рамки workflow.
    """
    model_map = {
        Complexity.SIMPLE: "flash",
        Complexity.MEDIUM: "pro",
        Complexity.COMPLEX: "pro",  # используем Pro для сложных задач в Gemini
    }
    return model_map[complexity]


# ============================================================================
# PROMPT BUILDING
# ============================================================================

def build_llm_prompt(user_query: str, report: Report, classification: Classification) -> str:
    """
    Строит оптимальный промпт для LLM.

    Включает:
    - Оригинальный запрос пользователя
    - Результаты автоматического анализа
    - Структурированные инструкции для LLM
    """
    req_type = classification.primary_type.value

    # Конвертация отчета в JSON
    report_dict = {
        "summary": report.summary,
        "total_issues": report.total_issues,
        "critical_issues": report.critical_issues,
        "files_analyzed": report.files_analyzed,
        "issues": [asdict(issue) for issue in report.issues],
        "metrics": report.metrics,
        "recommendations": report.recommendations,
    }

    prompt = f"""Ты эксперт по Python и {req_type}.

Пользователь спрашивает: "{user_query}"

Я уже запустил автоматический анализ. Результаты:

```json
{json.dumps(report_dict, indent=2, ensure_ascii=False)}
```

На основе этого отчета предоставь:
1. Краткое резюме найденных проблем (2-3 предложения)
2. Конкретные рекомендации по исправлению (приоритезированный список)
3. Примеры кода для топ-3 проблем (если применимо)

Будь конкретен и практичен. Используй данные из отчета, не выдумывай."""

    return prompt


# ============================================================================
# GEMINI BRIDGE
# ============================================================================

class GeminiBridge:
    """
    Мост для вызова Gemini моделей через CLI скрипт.

    Использует .claude/helpers/gemini-bridge.sh для взаимодействия с Gemini API.
    """

    def __init__(self, bridge_script: Optional[Path] = None, use_mock: bool = False):
        if bridge_script is None:
            self.bridge_script = Path(__file__).parent.parent / ".claude" / "helpers" / "gemini-bridge.sh"
        else:
            self.bridge_script = bridge_script

        self.use_mock = use_mock

        if not self.bridge_script.exists():
            print(f"⚠️  Warning: gemini-bridge.sh not found at {self.bridge_script}")
            print("    Will use mock response")
            self.use_mock = True
        else:
            # Проверяем, доступен ли gemini CLI
            try:
                result = subprocess.run(
                    ["which", "gemini"],
                    capture_output=True,
                    timeout=2
                )
                if result.returncode != 0:
                    print("⚠️  Warning: 'gemini' CLI not found in PATH")
                    print("    Will use mock response")
                    self.use_mock = True
            except Exception:
                self.use_mock = True

    def call(self, model: str, prompt: str) -> str:
        """
        Вызывает Gemini модель через bridge скрипт.

        Args:
            model: "flash" или "pro"
            prompt: полный промпт с контекстом

        Returns:
            Ответ модели
        """
        if self.use_mock:
            return self._mock_response(model, prompt)

        try:
            result = subprocess.run(
                ["bash", str(self.bridge_script), model, prompt],
                capture_output=True,
                text=True,
                timeout=60,
                check=True
            )
            return result.stdout.strip()
        except subprocess.TimeoutExpired:
            print("⚠️  Gemini call timed out, falling back to mock")
            return self._mock_response(model, prompt)
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Gemini call failed: {e.stderr}, falling back to mock")
            return self._mock_response(model, prompt)
        except Exception as e:
            print(f"⚠️  Unexpected error: {str(e)}, falling back to mock")
            return self._mock_response(model, prompt)

    def _mock_response(self, model: str, prompt: str) -> str:
        """Mock ответ для тестирования без реального API"""
        return f"""[MOCK RESPONSE from {model.upper()}]

Резюме проблем:
На основе автоматического анализа обнаружены критические уязвимости безопасности,
включая hardcoded пароли и потенциальные SQL injection точки. Также выявлены
проблемы производительности с неоптимальными алгоритмами.

Рекомендации (приоритизированы):
1. CRITICAL: Немедленно убрать hardcoded пароли из конфигурации
2. HIGH: Исправить SQL injection уязвимости через параметризованные запросы
3. MEDIUM: Оптимизировать вложенные циклы в API handlers
4. LOW: Добавить cache eviction policy

Примеры кода:

1. Исправление hardcoded password:
```python
# Было:
PASSWORD = "my_secret_password"

# Должно быть:
import os
PASSWORD = os.getenv("APP_PASSWORD")
```

2. Исправление SQL injection:
```python
# Было:
cursor.execute(f"SELECT * FROM users WHERE id = {{user_id}}")

# Должно быть:
cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
```

3. Оптимизация цикла:
```python
# Было:
for item in items:
    for user in users:
        if item.user_id == user.id:
            # ...

# Должно быть:
user_map = {{user.id: user for user in users}}
for item in items:
    user = user_map.get(item.user_id)
    if user:
        # ...
```
"""


# ============================================================================
# TOKEN COUNTING
# ============================================================================

def count_tokens(text: str) -> int:
    """
    Подсчитывает токены (упрощенная версия).

    В реальной версии использует tiktoken.
    Здесь используем простую аппроксимацию: ~4 символа = 1 токен.
    """
    try:
        import tiktoken
        encoding = tiktoken.get_encoding("cl100k_base")
        return len(encoding.encode(text))
    except ImportError:
        # Fallback: простая аппроксимация
        return len(text) // 4


# ============================================================================
# MAIN WORKFLOW
# ============================================================================

def handle_user_request(user_query: str, project_root: Path, verbose: bool = True, use_mock: bool = False) -> Tuple[str, Dict]:
    """
    Главная функция workflow - обрабатывает запрос пользователя.

    Workflow:
    1. Классификация запроса (Sonnet) → HybridClassifier
    2. Запуск инструментов → SmartExecutor
    3. Агрегация отчета → HybridReportAggregator
    4. Определение сложности → determine_complexity
    5. Выбор модели → select_model
    6. Построение промпта → build_llm_prompt
    7. Вызов LLM (Flash/Pro) → GeminiBridge
    8. Возврат результата + метрик + таблица расхода токенов

    Args:
        user_query: запрос пользователя
        project_root: корневая директория проекта
        verbose: выводить ли промежуточные шаги
        use_mock: использовать mock вместо реального API

    Returns:
        (llm_response, metrics_dict)
    """
    start_time = time.time()
    metrics = {}

    # Инициализация трекера токенов
    tracker = TokenTracker()
    task_id = tracker.start_task(user_query)

    if verbose:
        print(f"\n{'='*70}")
        print(f"Starting workflow for query: '{user_query}'")
        print(f"{'='*70}\n")

    # Шаг 1: Классификация (считаем как вызов Sonnet — classifier)
    if verbose:
        print("Step 1: Classification...")
    classifier = HybridClassifier()
    classification = classifier.classify(user_query)

    # Токены классификации: входной запрос + результат
    classify_input_tokens = count_tokens(user_query)
    classify_output_tokens = count_tokens(json.dumps({
        "type": classification.primary_type.value,
        "confidence": classification.confidence,
        "tools": classification.tools,
    }, ensure_ascii=False))
    tracker.record_call(task_id, model="sonnet", role="classifier",
                        input_tokens=classify_input_tokens, output_tokens=classify_output_tokens)

    if verbose:
        print(f"   Type: {classification.primary_type.value}")
        print(f"   Confidence: {classification.confidence:.2f}")
        print(f"   Tools: {', '.join(classification.tools)}")
        print(f"   Scope: {classification.scope}")
        print(f"   Keywords: {', '.join(classification.keywords)}\n")

    # Шаг 2: Запуск инструментов (локальный, без LLM)
    if verbose:
        print("Step 2: Executing tools...")
    executor = SmartExecutor(project_root)
    executor_results = executor.execute(classification)

    if verbose:
        print(f"   Issues found: {len(executor_results['issues'])}")
        print(f"   Execution time: {executor_results['metrics']['execution_time_ms']}ms\n")

    # Шаг 3: Агрегация отчета (локальный, без LLM)
    if verbose:
        print("Step 3: Aggregating report...")
    aggregator = HybridReportAggregator()
    report = aggregator.aggregate(classification, executor_results)

    report_json = json.dumps({
        "summary": report.summary,
        "issues": [asdict(issue) for issue in report.issues],
        "metrics": report.metrics,
    }, ensure_ascii=False)
    report_tokens = count_tokens(report_json)

    if verbose:
        print(f"   Summary: {report.summary}")
        print(f"   Report size: {report_tokens} tokens\n")

    metrics["report_tokens"] = report_tokens

    # Шаг 4: Определение сложности
    if verbose:
        print("Step 4: Determining complexity...")
    complexity = determine_complexity(report)

    if verbose:
        print(f"   Complexity: {complexity.value}\n")

    metrics["complexity"] = complexity.value

    # Шаг 5: Выбор модели
    if verbose:
        print("Step 5: Selecting model...")
    model = select_model(complexity)

    if verbose:
        print(f"   Selected model: {model}")
        model_costs = {
            "flash": "$0.50/$3.00 per 1M tokens",
            "pro": "$2.00/$12.00 per 1M tokens",
            "opus": "$15/$75 per 1M tokens (no delegation)",
        }
        print(f"   Cost: {model_costs.get(model, 'unknown')}\n")

    metrics["model"] = model

    # Шаг 6: Построение промпта
    if verbose:
        print("Step 6: Building LLM prompt...")
    llm_prompt = build_llm_prompt(user_query, report, classification)
    prompt_tokens = count_tokens(llm_prompt)

    if verbose:
        print(f"   Prompt size: {prompt_tokens} tokens\n")

    metrics["prompt_tokens"] = prompt_tokens

    # Шаг 7: Вызов LLM (Flash или Pro)
    if verbose:
        print("Step 7: Calling LLM...")

    bridge = GeminiBridge(use_mock=use_mock)
    llm_response = bridge.call(model, llm_prompt)
    response_tokens = count_tokens(llm_response)

    # Записываем вызов исполнителя
    tracker.record_call(task_id, model=model, role="executor",
                        input_tokens=prompt_tokens, output_tokens=response_tokens)

    if verbose:
        print(f"   Response size: {response_tokens} tokens\n")

    metrics["response_tokens"] = response_tokens

    # Шаг 8: Верификация Sonnet (подсчёт токенов проверки)
    verify_input_tokens = count_tokens(llm_response[:500])  # Sonnet проверяет начало ответа
    verify_output_tokens = count_tokens("APPROVED")
    tracker.record_call(task_id, model="sonnet", role="verifier",
                        input_tokens=verify_input_tokens, output_tokens=verify_output_tokens)

    # Финальные метрики
    end_time = time.time()
    total_time = end_time - start_time
    metrics["total_time_seconds"] = round(total_time, 2)
    metrics["total_tokens"] = prompt_tokens + response_tokens

    # Завершаем задачу в трекере и печатаем таблицу
    tracker.finish_task(task_id, complexity=complexity.value)
    metrics["task_id"] = task_id

    if verbose:
        print(f"Workflow completed in {total_time:.2f}s")
        tracker.print_task_summary(task_id)

    return llm_response, metrics


# ============================================================================
# CLI INTERFACE
# ============================================================================

def main():
    """CLI interface для workflow и отчётов по токенам"""
    parser = argparse.ArgumentParser(
        description="PT_Standart Main Workflow - Intelligent Code Analysis",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s "проверь безопасность auth модуля"
  %(prog)s "оптимизируй производительность API" --mock
  %(prog)s --report                    # дневной отчёт по токенам
  %(prog)s --report --date 2026-02-10  # отчёт за конкретный день
  %(prog)s --report --total            # общая статистика
  %(prog)s --report --last 5           # последние 5 задач
        """
    )

    parser.add_argument(
        "query",
        nargs="?",
        default=None,
        help="Запрос пользователя (на русском или английском)"
    )

    parser.add_argument(
        "--project-root",
        type=Path,
        default=Path.cwd(),
        help="Корневая директория проекта (по умолчанию: текущая)"
    )

    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Не выводить промежуточные шаги"
    )

    parser.add_argument(
        "--json",
        action="store_true",
        help="Вывести результат в JSON формате"
    )

    parser.add_argument(
        "--mock",
        action="store_true",
        help="Использовать mock ответы вместо реального Gemini API"
    )

    # Команды отчётов
    parser.add_argument(
        "--report",
        action="store_true",
        help="Показать отчёт по расходу токенов (вместо запуска задачи)"
    )

    parser.add_argument(
        "--date",
        type=str,
        default=None,
        help="Дата для отчёта (YYYY-MM-DD)"
    )

    parser.add_argument(
        "--total",
        action="store_true",
        help="Общая статистика за всё время"
    )

    parser.add_argument(
        "--last",
        type=int,
        default=0,
        help="Показать последние N задач с деталями"
    )

    args = parser.parse_args()

    # Режим отчёта
    if args.report or args.total or args.last > 0:
        tracker = TokenTracker()
        if args.total:
            tracker.print_total_stats()
        elif args.last > 0:
            with tracker._conn() as conn:
                tasks = conn.execute(
                    "SELECT task_id FROM tasks ORDER BY started_at DESC LIMIT ?",
                    (args.last,),
                ).fetchall()
            for t in reversed(tasks):
                tracker.print_task_summary(t["task_id"])
        else:
            from datetime import date
            target_date = date.fromisoformat(args.date) if args.date else date.today()
            tracker.print_daily_report(target_date)
        return

    # Режим задачи
    if not args.query:
        parser.error("Укажите запрос или используйте --report для отчёта")

    response, metrics = handle_user_request(
        args.query,
        args.project_root,
        verbose=not args.quiet,
        use_mock=args.mock
    )

    # Вывод результата
    if args.json:
        output = {
            "response": response,
            "metrics": metrics,
        }
        print(json.dumps(output, indent=2, ensure_ascii=False))
    else:
        print("\n" + "="*70)
        print("LLM RESPONSE:")
        print("="*70)
        print(response)
        print("="*70 + "\n")


if __name__ == "__main__":
    main()
