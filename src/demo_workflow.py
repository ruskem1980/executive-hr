#!/usr/bin/env python3
"""
Тестовый скрипт для демонстрации main_workflow.py

Запускает несколько примеров запросов и показывает результаты.
"""

from pathlib import Path
from main_workflow import handle_user_request


def test_security_query():
    """Тест: запрос безопасности"""
    print("\n" + "="*80)
    print("TEST 1: SECURITY QUERY")
    print("="*80)

    query = "Найди уязвимости безопасности в auth модуле"
    project_root = Path(__file__).parent.parent

    response, metrics = handle_user_request(query, project_root, verbose=True, use_mock=True)

    print("\n✅ Test 1 completed")
    print(f"   Tokens used: {metrics['total_tokens']}")
    print(f"   Model: {metrics['model']}")
    print(f"   Savings: {metrics['token_savings_percent']}%")


def test_performance_query():
    """Тест: запрос производительности"""
    print("\n" + "="*80)
    print("TEST 2: PERFORMANCE QUERY")
    print("="*80)

    query = "Оптимизируй производительность API, особенно медленные endpoints"
    project_root = Path(__file__).parent.parent

    response, metrics = handle_user_request(query, project_root, verbose=True)

    print("\n✅ Test 2 completed")
    print(f"   Tokens used: {metrics['total_tokens']}")
    print(f"   Model: {metrics['model']}")
    print(f"   Savings: {metrics['token_savings_percent']}%")


def test_simple_query():
    """Тест: простой запрос (должен использовать Flash)"""
    print("\n" + "="*80)
    print("TEST 3: SIMPLE QUERY (should use Flash)")
    print("="*80)

    query = "Проверь форматирование кода в utils.py"
    project_root = Path(__file__).parent.parent

    response, metrics = handle_user_request(query, project_root, verbose=True)

    print("\n✅ Test 3 completed")
    print(f"   Tokens used: {metrics['total_tokens']}")
    print(f"   Model: {metrics['model']} (expected: flash)")
    print(f"   Savings: {metrics['token_savings_percent']}%")


def test_quiet_mode():
    """Тест: quiet режим"""
    print("\n" + "="*80)
    print("TEST 4: QUIET MODE")
    print("="*80)

    query = "Найди все TODO комментарии в проекте"
    project_root = Path(__file__).parent.parent

    response, metrics = handle_user_request(query, project_root, verbose=False)

    print("\n✅ Test 4 completed (quiet mode)")
    print(f"   Tokens used: {metrics['total_tokens']}")
    print(f"   Model: {metrics['model']}")


def main():
    """Запускает все тесты"""
    print("\n" + "="*80)
    print("🧪 TESTING MAIN_WORKFLOW.PY")
    print("="*80)

    try:
        # Run only first test for demo
        test_security_query()
        # test_performance_query()
        # test_simple_query()
        # test_quiet_mode()

        print("\n" + "="*80)
        print("🎉 TEST COMPLETED SUCCESSFULLY")
        print("="*80)

    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()
