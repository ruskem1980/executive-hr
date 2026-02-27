#!/usr/bin/env python3
"""
Quick wrapper для main_workflow.py

Использование:
    python src/analyze.py "ваш запрос"
"""

import sys
from pathlib import Path
from main_workflow import handle_user_request


def main():
    if len(sys.argv) < 2:
        print("Usage: python src/analyze.py 'your query'")
        print("\nExamples:")
        print('  python src/analyze.py "найди уязвимости безопасности"')
        print('  python src/analyze.py "оптимизируй производительность API"')
        print('  python src/analyze.py "улучши тестовое покрытие"')
        sys.exit(1)

    query = " ".join(sys.argv[1:])
    project_root = Path(__file__).parent.parent

    print(f"\n🔍 Analyzing: '{query}'\n")

    response, metrics = handle_user_request(query, project_root, verbose=True)

    print("\n" + "="*70)
    print("📊 SUMMARY")
    print("="*70)
    print(f"Model used: {metrics['model']}")
    print(f"Total tokens: {metrics['total_tokens']}")
    print(f"Token savings: {metrics['token_savings_percent']}%")
    print(f"Execution time: {metrics['total_time_seconds']}s")
    print("="*70 + "\n")


if __name__ == "__main__":
    main()
