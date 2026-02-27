#!/usr/bin/env python3
"""
ML AgentSelector — ранжирование агентов для задачи.

Использование:
    python3 scripts/ml_agent_rank.py <complexity_num> <has_security> <has_performance>

Выход: JSON массив [{type, score}, ...]
"""

import sys
import os
import json

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

AGENTS = [
    {'type': 'coder', 'past_performance': 0.85, 'current_load': 0.3,
     'specialization': ['backend', 'api', 'code-generation']},
    {'type': 'reviewer', 'past_performance': 0.9, 'current_load': 0.2,
     'specialization': ['security', 'quality']},
    {'type': 'tester', 'past_performance': 0.8, 'current_load': 0.1,
     'specialization': ['testing', 'coverage']},
    {'type': 'researcher', 'past_performance': 0.85, 'current_load': 0.15,
     'specialization': ['documentation', 'analysis']},
    {'type': 'architect', 'past_performance': 0.9, 'current_load': 0.4,
     'specialization': ['architecture', 'design']},
    {'type': 'security-architect', 'past_performance': 0.88, 'current_load': 0.3,
     'specialization': ['security']},
    {'type': 'performance-engineer', 'past_performance': 0.87, 'current_load': 0.2,
     'specialization': ['performance']},
]


def rank_agents(complexity_num: int, has_security: int, has_performance: int) -> list:
    """Ранжирование агентов через ML модель."""
    try:
        from src.ml.agent_selector import AgentSelector

        selector = AgentSelector()
        selector.load(os.path.join(ROOT, 'data', 'models', 'agent_selector.pkl'))

        task_features = {
            'complexity_num': complexity_num,
            'requires_security': has_security,
            'requires_performance': has_performance,
            'domain': 'backend'
        }

        ranked = selector.rank_agents(task_features, AGENTS)
        return [
            {'type': a['type'],
             'score': round(a.get('ml_score', a.get('rule_score', 0)), 3)}
            for a in ranked
        ]
    except Exception:
        return []


def main():
    if len(sys.argv) < 4:
        print(json.dumps([]))
        return

    complexity_num = int(sys.argv[1])
    has_security = int(sys.argv[2])
    has_performance = int(sys.argv[3])

    result = rank_agents(complexity_num, has_security, has_performance)
    print(json.dumps(result))


if __name__ == '__main__':
    main()
