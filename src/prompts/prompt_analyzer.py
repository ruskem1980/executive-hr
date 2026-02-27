#!/usr/bin/env python3
"""
Prompt Analyzer - Анализ failures и implicit signals для улучшения промптов

Собирает:
- Failures агентов (task, error, context)
- Implicit signals (retry_count, edit_rate, execution_time)
- Explicit feedback (ratings если есть)

Анализирует:
- Common patterns в failures
- Correlation между промптом и результатом
- Recommendations для улучшения
"""

import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from collections import Counter, defaultdict

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.reporting.token_tracker import TokenTracker


class PromptAnalyzer:
    """
    Анализатор промптов для выявления проблем и рекомендаций

    Использует:
    - Failures из БД
    - Implicit signals (retry, time)
    - Pattern analysis
    """

    def __init__(self, db_path: Optional[str] = None):
        """
        Args:
            db_path: Путь к token_usage.db
        """
        self.db_path = db_path or os.path.join(PROJECT_ROOT, "data", "token_usage.db")
        self.tracker = TokenTracker(db_path=self.db_path)

    def collect_failures(self, agent_type: Optional[str] = None, days: int = 30) -> List[Dict]:
        """
        Собирает failures за период

        Args:
            agent_type: Фильтр по типу агента (coder, reviewer, etc.)
            days: Период в днях

        Returns:
            Список failures с метаданными
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        start_date = (datetime.now() - timedelta(days=days)).isoformat()

        # Failures = задачи с success=0
        query = """
            SELECT
                task_id,
                query,
                complexity,
                started_at,
                finished_at
            FROM tasks
            WHERE success = 0
              AND started_at >= ?
        """
        params = [start_date]

        cursor.execute(query, params)
        rows = cursor.fetchall()

        failures = []
        for row in rows:
            task_id, description, complexity, timestamp, end_time = row

            # Получаем LLM calls для этой задачи
            cursor.execute("""
                SELECT model, role, input_tokens, output_tokens
                FROM llm_calls
                WHERE task_id = ?
                ORDER BY call_order
            """, (task_id,))

            llm_calls = cursor.fetchall()

            failures.append({
                'task_id': task_id,
                'description': description,
                'complexity': complexity,
                'timestamp': timestamp,
                'end_time': end_time,
                'llm_calls': [
                    {
                        'model': call[0],
                        'role': call[1],
                        'input_tokens': call[2],
                        'output_tokens': call[3]
                    }
                    for call in llm_calls
                ]
            })

        conn.close()
        return failures

    def collect_implicit_signals(self, days: int = 30) -> Dict:
        """
        Собирает implicit signals (retry rate, execution time)

        Returns:
            Словарь с агрегированными сигналами
        """
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        start_date = (datetime.now() - timedelta(days=days)).isoformat()

        # Средний retry count (tasks с одинаковым query)
        cursor.execute("""
            SELECT query, COUNT(*) as attempts
            FROM tasks
            WHERE started_at >= ?
            GROUP BY query
            HAVING COUNT(*) > 1
            ORDER BY attempts DESC
            LIMIT 20
        """, (start_date,))

        retry_patterns = [
            {'description': row[0], 'retry_count': row[1]}
            for row in cursor.fetchall()
        ]

        # Среднее время выполнения по complexity
        cursor.execute("""
            SELECT
                complexity,
                AVG((julianday(finished_at) - julianday(started_at)) * 24 * 60) as avg_minutes
            FROM tasks
            WHERE started_at >= ? AND finished_at IS NOT NULL
            GROUP BY complexity
        """, (start_date,))

        avg_time_by_complexity = {
            row[0]: row[1] for row in cursor.fetchall()
        }

        # Задачи с необычно долгим выполнением (outliers)
        cursor.execute("""
            SELECT
                task_id,
                query,
                complexity,
                (julianday(finished_at) - julianday(started_at)) * 24 * 60 as minutes
            FROM tasks
            WHERE started_at >= ?
              AND finished_at IS NOT NULL
              AND minutes > (
                  SELECT AVG((julianday(finished_at) - julianday(started_at)) * 24 * 60) * 2
                  FROM tasks
                  WHERE complexity = tasks.complexity
              )
            ORDER BY minutes DESC
            LIMIT 10
        """, (start_date,))

        slow_tasks = [
            {
                'task_id': row[0],
                'description': row[1],
                'complexity': row[2],
                'minutes': row[3]
            }
            for row in cursor.fetchall()
        ]

        conn.close()

        return {
            'retry_patterns': retry_patterns,
            'avg_time_by_complexity': avg_time_by_complexity,
            'slow_tasks': slow_tasks
        }

    def analyze_patterns(self, failures: List[Dict]) -> Dict:
        """
        Анализирует patterns в failures

        Returns:
            Словарь с найденными паттернами
        """
        if not failures:
            return {
                'common_keywords': [],
                'complexity_distribution': {},
                'model_failure_rates': {},
                'recommendations': [],
                'total_failures': 0
            }

        # Извлекаем keywords из описаний failures
        keywords = []
        for failure in failures:
            desc = failure['description'].lower()
            # Простое извлечение слов (можно улучшить с NLP)
            words = desc.split()
            keywords.extend([w for w in words if len(w) > 3])

        common_keywords = Counter(keywords).most_common(10)

        # Распределение по complexity
        complexity_dist = Counter([f['complexity'] for f in failures])

        # Failure rate по модели (из LLM calls)
        model_calls = defaultdict(int)
        for failure in failures:
            for call in failure['llm_calls']:
                model_calls[call['model']] += 1

        return {
            'common_keywords': common_keywords,
            'complexity_distribution': dict(complexity_dist),
            'model_usage_in_failures': dict(model_calls),
            'total_failures': len(failures)
        }

    def generate_recommendations(
        self,
        failures: List[Dict],
        patterns: Dict,
        implicit_signals: Dict
    ) -> List[str]:
        """
        Генерирует рекомендации для улучшения промптов

        Returns:
            Список рекомендаций
        """
        recommendations = []

        # Рекомендация 1: Если много failures для complex задач
        if patterns['complexity_distribution'].get('complex', 0) > len(failures) * 0.5:
            recommendations.append(
                "📋 Много failures для complex задач. Рекомендация: "
                "Улучшить промпты для сложных задач - добавить больше контекста, "
                "examples, и step-by-step instructions."
            )

        # Рекомендация 2: Если высокий retry rate
        if implicit_signals['retry_patterns']:
            top_retry = implicit_signals['retry_patterns'][0]
            recommendations.append(
                f"🔄 Высокий retry rate для задач типа '{top_retry['description'][:50]}...'. "
                "Рекомендация: Уточнить промпт для этого типа задач, добавить constraints."
            )

        # Рекомендация 3: Если задачи выполняются слишком долго
        if implicit_signals['slow_tasks']:
            recommendations.append(
                "⏱️ Некоторые задачи выполняются необычно долго. Рекомендация: "
                "Оптимизировать промпты для снижения контекста или разбить на подзадачи."
            )

        # Рекомендация 4: Если определённая модель часто в failures
        if patterns['model_usage_in_failures']:
            most_used_model = max(
                patterns['model_usage_in_failures'].items(),
                key=lambda x: x[1]
            )[0]
            recommendations.append(
                f"🤖 Модель '{most_used_model}' часто встречается в failures. "
                "Рекомендация: Возможно нужен более мощный model для этих задач, "
                "или промпт не оптимизирован под эту модель."
            )

        # Рекомендация 5: Common keywords в failures
        if patterns['common_keywords']:
            top_keywords = [kw[0] for kw in patterns['common_keywords'][:3]]
            recommendations.append(
                f"🔍 Частые слова в failures: {', '.join(top_keywords)}. "
                "Рекомендация: Добавить специфичные инструкции для задач с этими keywords."
            )

        if not recommendations:
            recommendations.append("✅ Анализ не выявил критичных проблем. Промпты работают стабильно.")

        return recommendations

    def analyze_agent_type(self, agent_type: str, days: int = 30) -> Dict:
        """
        Полный анализ для конкретного типа агента

        Args:
            agent_type: Тип агента (coder, reviewer, etc.)
            days: Период анализа

        Returns:
            Полный отчёт с рекомендациями
        """
        # Собираем данные
        failures = self.collect_failures(agent_type=agent_type, days=days)
        implicit_signals = self.collect_implicit_signals(days=days)

        # Анализируем
        patterns = self.analyze_patterns(failures)
        recommendations = self.generate_recommendations(failures, patterns, implicit_signals)

        return {
            'agent_type': agent_type,
            'period_days': days,
            'analysis_timestamp': datetime.now().isoformat(),
            'failures': {
                'total': len(failures),
                'recent_examples': failures[:5]  # Топ-5 последних
            },
            'patterns': patterns,
            'implicit_signals': implicit_signals,
            'recommendations': recommendations
        }

    def print_analysis(self, analysis: Dict) -> None:
        """Вывод анализа в CLI"""
        print("\n" + "="*80)
        print(f"  📊 АНАЛИЗ ПРОМПТОВ - {analysis['agent_type']}")
        print(f"  Период: последние {analysis['period_days']} дней")
        print("="*80 + "\n")

        print(f"Failures: {analysis['failures']['total']}")
        print(f"\nРаспределение по сложности:")
        for complexity, count in analysis['patterns']['complexity_distribution'].items():
            print(f"  {complexity}: {count}")

        print(f"\nОбщие keywords в failures:")
        for keyword, count in analysis['patterns']['common_keywords'][:5]:
            print(f"  {keyword}: {count} раз")

        print(f"\n🎯 РЕКОМЕНДАЦИИ:\n")
        for i, rec in enumerate(analysis['recommendations'], 1):
            print(f"{i}. {rec}\n")

        print("="*80 + "\n")


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Анализ промптов и рекомендации")
    parser.add_argument('--agent-type', type=str, help='Тип агента для анализа')
    parser.add_argument('--days', type=int, default=30, help='Период для анализа (дней)')
    parser.add_argument('--export', type=str, help='Экспортировать в JSON')
    parser.add_argument('--db', type=str, help='Путь к базе данных')

    args = parser.parse_args()

    analyzer = PromptAnalyzer(db_path=args.db)

    if args.agent_type:
        analysis = analyzer.analyze_agent_type(args.agent_type, days=args.days)
        analyzer.print_analysis(analysis)

        if args.export:
            with open(args.export, 'w', encoding='utf-8') as f:
                json.dump(analysis, f, indent=2, ensure_ascii=False)
            print(f"Анализ экспортирован в {args.export}")
    else:
        # Общий анализ без фильтра по агенту
        analysis = analyzer.analyze_agent_type('all', days=args.days)
        analyzer.print_analysis(analysis)


if __name__ == "__main__":
    main()
