#!/usr/bin/env python3
"""
Анализ A/B тестирования ML vs Rules классификации.

Парсит ab_test_log.jsonl и сравнивает результаты:
- Согласованность ML и rules
- Confidence по группам
- Распределение по сложности
- Статистика fallback-ов

Использование:
    python3 scripts/ab_analysis.py                    # Полный отчёт
    python3 scripts/ab_analysis.py --json              # JSON формат
    python3 scripts/ab_analysis.py --since 2026-02-13  # С определённой даты
"""

import sys
import os
import json
import argparse
from datetime import datetime
from collections import Counter, defaultdict

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
AB_LOG_PATH = os.path.join(ROOT, '.claude', 'tracking', 'ab_test_log.jsonl')


def load_ab_data(since: str = None) -> list:
    """Загрузка данных A/B тестирования."""
    if not os.path.exists(AB_LOG_PATH):
        print(f"❌ Файл не найден: {AB_LOG_PATH}")
        return []

    entries = []
    with open(AB_LOG_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if since and entry.get('timestamp', '') < since:
                    continue
                entries.append(entry)
            except json.JSONDecodeError:
                continue

    return entries


def analyze(entries: list) -> dict:
    """Комплексный анализ A/B данных."""
    if not entries:
        return {'error': 'Нет данных для анализа'}

    # Базовые подсчёты
    total = len(entries)
    ab_groups = Counter(e.get('abGroup') for e in entries)
    methods = Counter(e.get('classificationMethod') for e in entries)
    final_levels = Counter(e.get('finalLevel') for e in entries)
    rules_levels = Counter(e.get('rulesLevel') for e in entries)

    # ML-специфичная аналитика
    ml_entries = [e for e in entries if e.get('mlLevel') is not None]
    ml_methods = Counter(e.get('mlMethod') for e in ml_entries)

    # Согласованность ML и rules
    agreement_count = 0
    disagreement_details = []
    for e in ml_entries:
        if e.get('mlLevel') == e.get('rulesLevel'):
            agreement_count += 1
        else:
            disagreement_details.append({
                'task': e.get('task', '')[:60],
                'rules': e.get('rulesLevel'),
                'ml': e.get('mlLevel'),
                'final': e.get('finalLevel'),
                'ml_conf': e.get('mlConfidence'),
                'rules_conf': e.get('rulesConfidence')
            })

    agreement_rate = agreement_count / len(ml_entries) if ml_entries else 0

    # Confidence статистика
    rules_confidences = [e.get('rulesConfidence', 0) for e in entries if e.get('rulesConfidence')]
    ml_confidences = [e.get('mlConfidence', 0) for e in ml_entries if e.get('mlConfidence')]

    avg_rules_conf = sum(rules_confidences) / len(rules_confidences) if rules_confidences else 0
    avg_ml_conf = sum(ml_confidences) / len(ml_confidences) if ml_confidences else 0

    # ML fallback анализ
    ml_direct = sum(1 for e in ml_entries if e.get('mlMethod') == 'ml')
    ml_fallback = sum(1 for e in ml_entries
                      if e.get('mlMethod', '').startswith('fallback'))
    ml_direct_rate = ml_direct / len(ml_entries) if ml_entries else 0

    # Временная динамика
    timestamps = sorted(set(e.get('timestamp', '')[:10] for e in entries))

    return {
        'summary': {
            'total_entries': total,
            'unique_tasks': len(set(e.get('task', '') for e in entries)),
            'date_range': {
                'from': timestamps[0] if timestamps else None,
                'to': timestamps[-1] if timestamps else None,
            }
        },
        'ab_groups': dict(ab_groups),
        'classification_methods': dict(methods),
        'final_levels': dict(final_levels),
        'rules_levels': dict(rules_levels),
        'ml_analysis': {
            'total_ml_calls': len(ml_entries),
            'ml_methods': dict(ml_methods),
            'ml_direct_rate': round(ml_direct_rate, 3),
            'ml_fallback_count': ml_fallback,
            'agreement_with_rules': round(agreement_rate, 3),
            'disagreements': disagreement_details[:10],  # Топ-10
        },
        'confidence': {
            'rules_avg': round(avg_rules_conf, 3),
            'ml_avg': round(avg_ml_conf, 3),
            'rules_min': round(min(rules_confidences), 3) if rules_confidences else 0,
            'rules_max': round(max(rules_confidences), 3) if rules_confidences else 0,
            'ml_min': round(min(ml_confidences), 3) if ml_confidences else 0,
            'ml_max': round(max(ml_confidences), 3) if ml_confidences else 0,
        },
        'recommendations': generate_recommendations(
            agreement_rate, avg_ml_conf, ml_direct_rate,
            len(ml_entries), total
        )
    }


def generate_recommendations(agreement: float, ml_conf: float,
                              ml_direct: float, ml_count: int,
                              total: int) -> list:
    """Генерация рекомендаций по результатам A/B тестирования."""
    recs = []

    if ml_count < 20:
        recs.append("⚠️  Мало ML-данных ({} записей). Увеличьте mlRatio или подождите больше задач.".format(ml_count))

    if ml_conf < 0.7 and ml_count > 0:
        recs.append("📉 Средний ML confidence ({:.1%}) ниже порога 70%. Нужно больше обучающих данных или тюнинг модели.".format(ml_conf))

    if ml_direct < 0.3 and ml_count > 10:
        recs.append("🔄 ML напрямую используется только в {:.0%} случаев. Большинство решений — fallback на rules.".format(ml_direct))

    if agreement > 0.9 and ml_count > 20:
        recs.append("✅ ML и rules согласованы в {:.0%} случаев. Можно увеличить mlRatio до 0.7-0.8.".format(agreement))
    elif agreement < 0.5 and ml_count > 10:
        recs.append("⚠️  Низкая согласованность ML/rules ({:.0%}). Проверьте обучающие данные.".format(agreement))

    if not recs:
        recs.append("✅ Система работает стабильно. Продолжайте сбор данных.")

    return recs


def print_report(analysis: dict):
    """Печать красивого отчёта."""
    if 'error' in analysis:
        print(f"❌ {analysis['error']}")
        return

    s = analysis['summary']
    print("=" * 70)
    print("📊 АНАЛИЗ A/B ТЕСТИРОВАНИЯ: ML vs RULES")
    print("=" * 70)
    print(f"  Период: {s['date_range']['from']} — {s['date_range']['to']}")
    print(f"  Записей: {s['total_entries']}, уникальных задач: {s['unique_tasks']}")

    print("\n--- A/B Группы ---")
    for group, count in analysis['ab_groups'].items():
        pct = count / s['total_entries'] * 100
        print(f"  {group:>10}: {count:>4} ({pct:.0f}%)")

    print("\n--- Методы классификации ---")
    for method, count in analysis['classification_methods'].items():
        pct = count / s['total_entries'] * 100
        print(f"  {method:>25}: {count:>4} ({pct:.0f}%)")

    print("\n--- Распределение по сложности (финальное) ---")
    for level in ['program', 'simple', 'medium', 'complex']:
        count = analysis['final_levels'].get(level, 0)
        pct = count / s['total_entries'] * 100
        bar = "█" * int(pct / 2)
        print(f"  {level:>10}: {count:>4} ({pct:>5.1f}%) {bar}")

    ml = analysis['ml_analysis']
    print(f"\n--- ML Анализ ({ml['total_ml_calls']} вызовов) ---")
    if ml['total_ml_calls'] > 0:
        print(f"  ML напрямую:        {ml['ml_direct_rate']:.0%}")
        print(f"  ML fallback:        {ml['ml_fallback_count']} раз")
        print(f"  Согласие с rules:   {ml['agreement_with_rules']:.0%}")
        print(f"  ML методы:          {ml['ml_methods']}")

        if ml['disagreements']:
            print(f"\n  Разногласия ML/rules (топ-{len(ml['disagreements'])}):")
            for d in ml['disagreements'][:5]:
                print(f"    «{d['task']}»")
                print(f"      rules={d['rules']} vs ml={d['ml']} → final={d['final']}"
                      f" (ml_conf={d['ml_conf']:.2f})")
    else:
        print("  Нет ML вызовов в логе.")

    c = analysis['confidence']
    print(f"\n--- Confidence ---")
    print(f"  Rules:  avg={c['rules_avg']:.2f}  min={c['rules_min']:.2f}  max={c['rules_max']:.2f}")
    if c['ml_avg'] > 0:
        print(f"  ML:     avg={c['ml_avg']:.2f}  min={c['ml_min']:.2f}  max={c['ml_max']:.2f}")

    print(f"\n--- Рекомендации ---")
    for rec in analysis['recommendations']:
        print(f"  {rec}")

    print("=" * 70)


def main():
    parser = argparse.ArgumentParser(description='Анализ A/B тестирования ML vs Rules')
    parser.add_argument('--json', action='store_true', help='Вывод в JSON')
    parser.add_argument('--since', type=str, help='Анализ с даты (YYYY-MM-DD)')

    args = parser.parse_args()

    entries = load_ab_data(since=args.since)
    analysis = analyze(entries)

    if args.json:
        print(json.dumps(analysis, indent=2, ensure_ascii=False))
    else:
        print_report(analysis)


if __name__ == '__main__':
    main()
