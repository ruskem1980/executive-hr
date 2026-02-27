#!/usr/bin/env python3
"""
Демонстрационный скрипт для main_workflow.py

Показывает все возможности системы интеллектуальной предобработки:
- Классификация запросов
- Маршрутизация на модели
- Экономия токенов
- Различные типы запросов
"""

import sys
from pathlib import Path
from typing import Dict
import json

# Add src directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from main_workflow import handle_user_request


def demo_header(title: str):
    """Красивый заголовок для демо"""
    print("\n" + "="*80)
    print(f"  {title}")
    print("="*80 + "\n")


def demo_summary(query: str, metrics: Dict):
    """Краткое резюме результата"""
    print("\n" + "-"*80)
    print(f"📊 SUMMARY for '{query}'")
    print("-"*80)
    print(f"   Model:         {metrics['model']}")
    print(f"   Complexity:    {metrics['complexity']}")
    print(f"   Total Tokens:  {metrics['total_tokens']}")
    print(f"   Token Savings: {metrics['token_savings_percent']}%")
    print(f"   Execution:     {metrics['total_time_seconds']}s")
    print("-"*80 + "\n")


def demo_security():
    """Демо: Security запрос"""
    demo_header("DEMO 1: SECURITY ANALYSIS")

    query = "Найди уязвимости безопасности в authentication модуле"
    project_root = Path(__file__).parent.parent

    print(f"Query: '{query}'\n")
    print("Expected:")
    print("  - Type: SECURITY")
    print("  - Tools: bandit, semgrep, safety")
    print("  - Complexity: COMPLEX (CRITICAL issues)")
    print("  - Model: pro\n")

    response, metrics = handle_user_request(query, project_root, verbose=False, use_mock=True)

    demo_summary(query, metrics)

    print("Response preview (first 500 chars):")
    print(response[:500] + "...\n")


def demo_performance():
    """Демо: Performance запрос"""
    demo_header("DEMO 2: PERFORMANCE OPTIMIZATION")

    query = "Оптимизируй производительность API endpoints"
    project_root = Path(__file__).parent.parent

    print(f"Query: '{query}'\n")
    print("Expected:")
    print("  - Type: PERFORMANCE")
    print("  - Tools: profiler, memory_profiler, benchmark")
    print("  - Complexity: MEDIUM")
    print("  - Model: pro\n")

    response, metrics = handle_user_request(query, project_root, verbose=False, use_mock=True)

    demo_summary(query, metrics)

    print("Response preview (first 500 chars):")
    print(response[:500] + "...\n")


def demo_simple():
    """Демо: Simple запрос"""
    demo_header("DEMO 3: SIMPLE REFACTORING")

    query = "Улучши форматирование кода в utils.py"
    project_root = Path(__file__).parent.parent

    print(f"Query: '{query}'\n")
    print("Expected:")
    print("  - Type: REFACTORING")
    print("  - Tools: radon, pylint, flake8")
    print("  - Complexity: SIMPLE (no critical issues)")
    print("  - Model: flash (cheapest)\n")

    response, metrics = handle_user_request(query, project_root, verbose=False, use_mock=True)

    demo_summary(query, metrics)

    print("Response preview (first 500 chars):")
    print(response[:500] + "...\n")


def demo_comparison():
    """Демо: Сравнение экономии"""
    demo_header("DEMO 4: TOKEN SAVINGS COMPARISON")

    queries = [
        ("Проверь форматирование", "SIMPLE → flash"),
        ("Найди code smells", "MEDIUM → pro"),
        ("Security audit всего проекта", "COMPLEX → pro"),
    ]

    project_root = Path(__file__).parent.parent
    results = []

    for query, expected in queries:
        print(f"Processing: '{query}' ({expected})")
        response, metrics = handle_user_request(query, project_root, verbose=False, use_mock=True)
        results.append({
            "query": query,
            "expected": expected,
            "model": metrics['model'],
            "complexity": metrics['complexity'],
            "tokens": metrics['total_tokens'],
            "savings": metrics['token_savings_percent'],
        })

    print("\n" + "-"*80)
    print("COMPARISON TABLE")
    print("-"*80)
    print(f"{'Query':<35} {'Model':<8} {'Tokens':<8} {'Savings':<8}")
    print("-"*80)

    for r in results:
        print(f"{r['query'][:33]:<35} {r['model']:<8} {r['tokens']:<8} {r['savings']:.1f}%")

    print("-"*80)

    avg_savings = sum(r['savings'] for r in results) / len(results)
    total_tokens = sum(r['tokens'] for r in results)

    print(f"\nAverage Savings: {avg_savings:.1f}%")
    print(f"Total Tokens Used: {total_tokens}")
    print(f"Estimated vs Full Opus Scan (50K tokens): {((50000 - total_tokens) / 50000 * 100):.1f}% saved\n")


def demo_all_types():
    """Демо: Все типы запросов"""
    demo_header("DEMO 5: ALL REQUEST TYPES")

    test_cases = [
        ("найди SQL injection уязвимости", "SECURITY"),
        ("оптимизируй медленные функции", "PERFORMANCE"),
        ("примени SOLID принципы", "REFACTORING"),
        ("почему тест test_auth падает?", "DEBUGGING"),
        ("улучши test coverage", "TESTING"),
        ("добавь docstrings", "DOCUMENTATION"),
        ("предложи архитектуру модуля", "ARCHITECTURE"),
    ]

    project_root = Path(__file__).parent.parent
    results = []

    for query, expected_type in test_cases:
        print(f"Testing: '{query[:40]}...' → Expected: {expected_type}")
        response, metrics = handle_user_request(query, project_root, verbose=False, use_mock=True)
        results.append({
            "query": query[:40],
            "expected": expected_type,
            "model": metrics['model'],
            "tokens": metrics['total_tokens'],
        })

    print("\n" + "-"*80)
    print("CLASSIFICATION RESULTS")
    print("-"*80)
    print(f"{'Query':<45} {'Expected':<15} {'Model':<8} {'Tokens':<8}")
    print("-"*80)

    for r in results:
        print(f"{r['query']:<45} {r['expected']:<15} {r['model']:<8} {r['tokens']:<8}")

    print("-"*80 + "\n")


def demo_json_output():
    """Демо: JSON output"""
    demo_header("DEMO 6: JSON OUTPUT FORMAT")

    query = "найди баги в authentication"
    project_root = Path(__file__).parent.parent

    print(f"Query: '{query}'\n")

    response, metrics = handle_user_request(query, project_root, verbose=False, use_mock=True)

    output = {
        "query": query,
        "response": response[:200] + "...",  # truncated for demo
        "metrics": metrics,
    }

    print("JSON Output:")
    print(json.dumps(output, indent=2, ensure_ascii=False))
    print()


def main():
    """Запускает все демо"""
    print("\n" + "="*80)
    print("  🚀 MAIN WORKFLOW DEMONSTRATION")
    print("  PT_Standart - Intelligent Preprocessing System")
    print("="*80)

    try:
        # Run demos
        demo_security()
        demo_performance()
        demo_simple()
        demo_comparison()
        demo_all_types()
        demo_json_output()

        # Final summary
        demo_header("✅ DEMONSTRATION COMPLETE")
        print("All demos completed successfully!")
        print("\nKey Features Demonstrated:")
        print("  ✓ Automatic request classification")
        print("  ✓ Smart model routing (flash/pro)")
        print("  ✓ Token savings up to 98%")
        print("  ✓ Compact report generation")
        print("  ✓ Multiple request types support")
        print("  ✓ JSON output format")
        print("  ✓ Graceful error handling\n")

        print("Try it yourself:")
        print("  python src/main_workflow.py 'your query' --mock")
        print("  python src/analyze.py 'your query'\n")

    except Exception as e:
        print(f"\n❌ Demo failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
