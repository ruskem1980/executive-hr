#!/usr/bin/env python3
"""
Web Dashboard для ML метрик.

Генерирует HTML дашборд с визуализацией:
- Accuracy и confusion matrix
- A/B тестирование (ML vs Rules)
- Распределение задач по сложности
- Confidence histogram
- Метрики AgentSelector
- Тренд accuracy по времени

Использование:
    python3 scripts/ml_dashboard.py              # Генерация HTML
    python3 scripts/ml_dashboard.py --open        # Генерация + открытие в браузере
    python3 scripts/ml_dashboard.py --serve 8080  # HTTP сервер на порту
"""

import sys
import os
import json
import sqlite3
import argparse
from datetime import datetime
from collections import Counter
from typing import Dict, List

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

AB_LOG_PATH = os.path.join(ROOT, '.claude', 'tracking', 'ab_test_log.jsonl')
DB_PATH = os.path.join(ROOT, 'data', 'token_usage.db')
RETRAIN_STATE = os.path.join(ROOT, 'data', 'models', 'retrain_state.json')
OUTPUT_PATH = os.path.join(ROOT, 'docs', 'ml_dashboard.html')


def get_accuracy_data() -> dict:
    """Получение данных accuracy из модели."""
    try:
        from src.ml.task_classifier import TaskClassifier
        from scripts.train_ml_models import generate_synthetic_data, load_training_data_from_db
        from sklearn.metrics import confusion_matrix
        import numpy as np

        classifier = TaskClassifier()
        model_path = os.path.join(ROOT, 'data', 'models', 'task_classifier.pkl')
        if not os.path.exists(model_path):
            return {'error': 'Модель не найдена'}

        classifier.load(model_path)

        # Тестирование на синтетических данных
        synth_tasks, synth_labels = generate_synthetic_data()

        predictions = classifier.predict_batch(synth_tasks)
        correct = sum(1 for p, l in zip(predictions, synth_labels) if p == l)
        accuracy = correct / len(synth_labels)

        # Confusion matrix
        labels_order = ['program', 'simple', 'medium', 'complex']
        cm = confusion_matrix(synth_labels, predictions, labels=labels_order)

        # Per-class metrics
        per_class = {}
        for i, label in enumerate(labels_order):
            tp = cm[i][i]
            fp = sum(cm[j][i] for j in range(len(labels_order))) - tp
            fn = sum(cm[i][j] for j in range(len(labels_order))) - tp
            precision = tp / (tp + fp) if (tp + fp) > 0 else 0
            recall = tp / (tp + fn) if (tp + fn) > 0 else 0
            f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0
            per_class[label] = {
                'precision': round(precision, 3),
                'recall': round(recall, 3),
                'f1': round(f1, 3),
                'support': int(sum(cm[i]))
            }

        return {
            'accuracy': round(accuracy, 4),
            'confusion_matrix': cm.tolist(),
            'labels': labels_order,
            'per_class': per_class,
            'total_samples': len(synth_labels)
        }
    except Exception as e:
        return {'error': str(e)}


def get_ab_data() -> dict:
    """Получение данных A/B тестирования."""
    if not os.path.exists(AB_LOG_PATH):
        return {'entries': [], 'summary': {}}

    entries = []
    with open(AB_LOG_PATH, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    entries.append(json.loads(line))
                except json.JSONDecodeError:
                    continue

    ab_groups = Counter(e.get('abGroup') for e in entries)
    methods = Counter(e.get('classificationMethod') for e in entries)
    final_levels = Counter(e.get('finalLevel') for e in entries)

    ml_entries = [e for e in entries if e.get('mlLevel')]
    ml_confidences = [e.get('mlConfidence', 0) for e in ml_entries if e.get('mlConfidence')]
    rules_confidences = [e.get('rulesConfidence', 0) for e in entries if e.get('rulesConfidence')]

    agreement = sum(1 for e in ml_entries if e.get('mlLevel') == e.get('rulesLevel'))
    agreement_rate = agreement / len(ml_entries) if ml_entries else 0

    return {
        'total': len(entries),
        'ab_groups': dict(ab_groups),
        'methods': dict(methods),
        'final_levels': dict(final_levels),
        'ml_count': len(ml_entries),
        'agreement_rate': round(agreement_rate, 3),
        'ml_confidences': ml_confidences,
        'rules_confidences': rules_confidences,
        'avg_ml_conf': round(sum(ml_confidences) / len(ml_confidences), 3) if ml_confidences else 0,
        'avg_rules_conf': round(sum(rules_confidences) / len(rules_confidences), 3) if rules_confidences else 0,
    }


def get_token_data() -> dict:
    """Получение данных о расходе токенов."""
    if not os.path.exists(DB_PATH):
        return {'tasks': 0, 'total_tokens': 0}

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    cursor.execute("SELECT COUNT(*) FROM tasks WHERE finished_at IS NOT NULL")
    total_tasks = cursor.fetchone()[0]

    cursor.execute("SELECT SUM(input_tokens + output_tokens) FROM calls")
    total_tokens = cursor.fetchone()[0] or 0

    cursor.execute("""
        SELECT complexity, COUNT(*) as cnt
        FROM tasks
        WHERE complexity IS NOT NULL AND complexity != ''
        GROUP BY complexity
        ORDER BY cnt DESC
    """)
    by_complexity = dict(cursor.fetchall())

    cursor.execute("""
        SELECT model, SUM(input_tokens + output_tokens) as tokens, SUM(cost_usd) as cost
        FROM calls
        GROUP BY model
    """)
    by_model = {}
    for model, tokens, cost in cursor.fetchall():
        by_model[model] = {'tokens': int(tokens or 0), 'cost': round(float(cost or 0), 4)}

    conn.close()

    return {
        'total_tasks': total_tasks,
        'total_tokens': int(total_tokens),
        'by_complexity': by_complexity,
        'by_model': by_model,
    }


def get_retrain_data() -> dict:
    """Получение данных auto-retrain."""
    if os.path.exists(RETRAIN_STATE):
        with open(RETRAIN_STATE, 'r') as f:
            return json.load(f)
    return {}


def generate_html(accuracy_data: dict, ab_data: dict,
                  token_data: dict, retrain_data: dict) -> str:
    """Генерация HTML дашборда."""

    # Подготовка данных для confusion matrix
    cm_html = ""
    if 'confusion_matrix' in accuracy_data:
        cm = accuracy_data['confusion_matrix']
        labels = accuracy_data['labels']
        cm_html = "<table class='cm-table'><tr><th></th>"
        for l in labels:
            cm_html += f"<th>{l}</th>"
        cm_html += "</tr>"
        for i, row in enumerate(cm):
            cm_html += f"<tr><th>{labels[i]}</th>"
            for j, val in enumerate(row):
                cls = "cm-diag" if i == j else ("cm-off" if val > 0 else "cm-zero")
                cm_html += f"<td class='{cls}'>{val}</td>"
            cm_html += "</tr>"
        cm_html += "</table>"

    # Per-class metrics
    per_class_html = ""
    if 'per_class' in accuracy_data:
        per_class_html = "<table class='metrics-table'><tr><th>Класс</th><th>Precision</th><th>Recall</th><th>F1</th><th>Support</th></tr>"
        for cls, m in accuracy_data['per_class'].items():
            p_color = "good" if m['precision'] >= 0.8 else ("warn" if m['precision'] >= 0.5 else "bad")
            r_color = "good" if m['recall'] >= 0.8 else ("warn" if m['recall'] >= 0.5 else "bad")
            per_class_html += f"<tr><td><b>{cls}</b></td>"
            per_class_html += f"<td class='{p_color}'>{m['precision']:.0%}</td>"
            per_class_html += f"<td class='{r_color}'>{m['recall']:.0%}</td>"
            per_class_html += f"<td>{m['f1']:.0%}</td>"
            per_class_html += f"<td>{m['support']}</td></tr>"
        per_class_html += "</table>"

    # A/B распределение
    ab_levels = ab_data.get('final_levels', {})
    ab_chart_data = json.dumps(ab_levels)

    # Confidence histogram data
    ml_confs = json.dumps(ab_data.get('ml_confidences', []))
    rules_confs = json.dumps(ab_data.get('rules_confidences', []))

    # Token data
    model_data = json.dumps(token_data.get('by_model', {}))
    complexity_data = json.dumps(token_data.get('by_complexity', {}))

    accuracy_pct = accuracy_data.get('accuracy', 0) * 100
    accuracy_color = "#4caf50" if accuracy_pct >= 90 else ("#ff9800" if accuracy_pct >= 70 else "#f44336")

    now = datetime.now().strftime('%Y-%m-%d %H:%M')
    retrain_count = retrain_data.get('retrain_count', 0)
    last_retrain = retrain_data.get('last_retrain', 'никогда')

    return f"""<!DOCTYPE html>
<html lang="ru">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>ML Dashboard — PT Standart Agents</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4.4.0/dist/chart.umd.min.js"></script>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #0d1117; color: #c9d1d9; }}
.header {{ background: linear-gradient(135deg, #1a1b27 0%, #161b22 100%); padding: 24px; border-bottom: 1px solid #30363d; }}
.header h1 {{ font-size: 24px; color: #58a6ff; }}
.header .subtitle {{ color: #8b949e; margin-top: 4px; }}
.container {{ max-width: 1400px; margin: 0 auto; padding: 20px; }}
.grid {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(350px, 1fr)); gap: 20px; margin-top: 20px; }}
.card {{ background: #161b22; border: 1px solid #30363d; border-radius: 12px; padding: 20px; }}
.card h2 {{ font-size: 16px; color: #58a6ff; margin-bottom: 16px; border-bottom: 1px solid #21262d; padding-bottom: 8px; }}
.big-number {{ font-size: 48px; font-weight: bold; text-align: center; margin: 20px 0; }}
.stat-row {{ display: flex; justify-content: space-between; padding: 8px 0; border-bottom: 1px solid #21262d; }}
.stat-label {{ color: #8b949e; }}
.stat-value {{ font-weight: 600; }}
.good {{ color: #3fb950; }}
.warn {{ color: #d29922; }}
.bad {{ color: #f85149; }}
.cm-table {{ border-collapse: collapse; width: 100%; margin: 10px 0; }}
.cm-table th, .cm-table td {{ padding: 8px 12px; text-align: center; border: 1px solid #30363d; }}
.cm-table th {{ background: #21262d; color: #8b949e; font-size: 12px; }}
.cm-diag {{ background: #1a4d2e; color: #3fb950; font-weight: bold; font-size: 18px; }}
.cm-off {{ background: #4d1a1a; color: #f85149; }}
.cm-zero {{ color: #484f58; }}
.metrics-table {{ width: 100%; border-collapse: collapse; }}
.metrics-table th, .metrics-table td {{ padding: 8px; text-align: center; border: 1px solid #30363d; }}
.metrics-table th {{ background: #21262d; color: #8b949e; font-size: 12px; }}
.chart-container {{ position: relative; height: 250px; }}
.badge {{ display: inline-block; padding: 2px 8px; border-radius: 12px; font-size: 12px; font-weight: 600; }}
.badge-green {{ background: #1a4d2e; color: #3fb950; }}
.badge-yellow {{ background: #4d3a1a; color: #d29922; }}
.badge-red {{ background: #4d1a1a; color: #f85149; }}
.footer {{ text-align: center; padding: 20px; color: #484f58; font-size: 12px; margin-top: 20px; }}
</style>
</head>
<body>
<div class="header">
  <h1>ML Dashboard</h1>
  <div class="subtitle">PT Standart Agents | TaskClassifier + AgentSelector + A/B Testing | {now}</div>
</div>

<div class="container">
  <div class="grid">

    <!-- Accuracy Card -->
    <div class="card">
      <h2>Accuracy (TaskClassifier)</h2>
      <div class="big-number" style="color: {accuracy_color}">{accuracy_pct:.1f}%</div>
      <div class="stat-row">
        <span class="stat-label">Всего образцов</span>
        <span class="stat-value">{accuracy_data.get('total_samples', 'н/д')}</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Статус</span>
        <span class="stat-value">
          <span class="badge {'badge-green' if accuracy_pct >= 90 else 'badge-yellow' if accuracy_pct >= 70 else 'badge-red'}">
            {'GOOD' if accuracy_pct >= 90 else 'WARN' if accuracy_pct >= 70 else 'LOW'}
          </span>
        </span>
      </div>
    </div>

    <!-- Confusion Matrix -->
    <div class="card" style="grid-column: span 1;">
      <h2>Confusion Matrix</h2>
      {cm_html if cm_html else '<p style="color:#8b949e">Нет данных</p>'}
    </div>

    <!-- Per-class Metrics -->
    <div class="card">
      <h2>Метрики по классам</h2>
      {per_class_html if per_class_html else '<p style="color:#8b949e">Нет данных</p>'}
    </div>

    <!-- A/B Testing -->
    <div class="card">
      <h2>A/B Тестирование</h2>
      <div class="stat-row">
        <span class="stat-label">Записей</span>
        <span class="stat-value">{ab_data.get('total', 0)}</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">ML вызовов</span>
        <span class="stat-value">{ab_data.get('ml_count', 0)}</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Согласие ML/Rules</span>
        <span class="stat-value {'good' if ab_data.get('agreement_rate', 0) > 0.8 else 'warn'}">{ab_data.get('agreement_rate', 0):.0%}</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Средний ML confidence</span>
        <span class="stat-value">{ab_data.get('avg_ml_conf', 0):.1%}</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Средний Rules confidence</span>
        <span class="stat-value">{ab_data.get('avg_rules_conf', 0):.1%}</span>
      </div>
      <div class="chart-container" style="height:200px">
        <canvas id="abChart"></canvas>
      </div>
    </div>

    <!-- Complexity Distribution -->
    <div class="card">
      <h2>Распределение задач по сложности</h2>
      <div class="chart-container">
        <canvas id="complexityChart"></canvas>
      </div>
    </div>

    <!-- Token Usage -->
    <div class="card">
      <h2>Расход токенов по моделям</h2>
      <div class="stat-row">
        <span class="stat-label">Всего задач</span>
        <span class="stat-value">{token_data.get('total_tasks', 0)}</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Всего токенов</span>
        <span class="stat-value">{token_data.get('total_tokens', 0):,}</span>
      </div>
      <div class="chart-container">
        <canvas id="tokenChart"></canvas>
      </div>
    </div>

    <!-- Auto-Retrain -->
    <div class="card">
      <h2>Auto-Retrain</h2>
      <div class="stat-row">
        <span class="stat-label">Переобучений</span>
        <span class="stat-value">{retrain_count}</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Последнее</span>
        <span class="stat-value">{last_retrain[:19] if isinstance(last_retrain, str) else 'никогда'}</span>
      </div>
      <div class="stat-row">
        <span class="stat-label">Последняя accuracy</span>
        <span class="stat-value">{retrain_data.get('last_accuracy', 'н/д')}</span>
      </div>
    </div>

  </div>
</div>

<div class="footer">
  ML Dashboard | Автоматически генерируется: python3 scripts/ml_dashboard.py
</div>

<script>
// A/B Groups Chart
const abData = {ab_chart_data};
new Chart(document.getElementById('abChart'), {{
  type: 'doughnut',
  data: {{
    labels: Object.keys(abData),
    datasets: [{{ data: Object.values(abData), backgroundColor: ['#3fb950','#58a6ff','#d29922','#f85149','#8b949e'] }}]
  }},
  options: {{ responsive: true, maintainAspectRatio: false, plugins: {{ legend: {{ labels: {{ color: '#c9d1d9' }} }} }} }}
}});

// Complexity Chart
const compData = {json.dumps(token_data.get('by_complexity', ab_data.get('final_levels', {})))};
new Chart(document.getElementById('complexityChart'), {{
  type: 'bar',
  data: {{
    labels: Object.keys(compData),
    datasets: [{{ label: 'Задачи', data: Object.values(compData), backgroundColor: ['#1f6feb','#3fb950','#d29922','#f85149'] }}]
  }},
  options: {{
    responsive: true, maintainAspectRatio: false,
    scales: {{ y: {{ ticks: {{ color: '#8b949e' }}, grid: {{ color: '#21262d' }} }}, x: {{ ticks: {{ color: '#8b949e' }}, grid: {{ color: '#21262d' }} }} }},
    plugins: {{ legend: {{ display: false }} }}
  }}
}});

// Token Usage Chart
const modelData = {model_data};
const modelLabels = Object.keys(modelData);
const modelTokens = modelLabels.map(k => modelData[k].tokens);
const modelCosts = modelLabels.map(k => modelData[k].cost);
if (modelLabels.length > 0) {{
  new Chart(document.getElementById('tokenChart'), {{
    type: 'bar',
    data: {{
      labels: modelLabels,
      datasets: [
        {{ label: 'Токены', data: modelTokens, backgroundColor: '#58a6ff' }},
      ]
    }},
    options: {{
      responsive: true, maintainAspectRatio: false,
      scales: {{ y: {{ ticks: {{ color: '#8b949e' }}, grid: {{ color: '#21262d' }} }}, x: {{ ticks: {{ color: '#8b949e' }}, grid: {{ color: '#21262d' }} }} }},
      plugins: {{ legend: {{ labels: {{ color: '#c9d1d9' }} }} }}
    }}
  }});
}}
</script>
</body>
</html>"""


def main():
    parser = argparse.ArgumentParser(description='ML Dashboard генератор')
    parser.add_argument('--open', action='store_true', help='Открыть в браузере')
    parser.add_argument('--serve', type=int, help='Запустить HTTP сервер на порту')
    parser.add_argument('--output', type=str, default=OUTPUT_PATH, help='Путь для HTML')
    args = parser.parse_args()

    print("📊 Сбор данных для ML Dashboard...")

    accuracy_data = get_accuracy_data()
    ab_data = get_ab_data()
    token_data = get_token_data()
    retrain_data = get_retrain_data()

    print(f"  Accuracy: {accuracy_data.get('accuracy', 'ошибка')}")
    print(f"  A/B записей: {ab_data.get('total', 0)}")
    print(f"  Задач в БД: {token_data.get('total_tasks', 0)}")

    html = generate_html(accuracy_data, ab_data, token_data, retrain_data)

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    with open(args.output, 'w', encoding='utf-8') as f:
        f.write(html)
    print(f"\n✅ Dashboard сохранён: {args.output}")

    if args.open:
        import webbrowser
        webbrowser.open(f'file://{os.path.abspath(args.output)}')

    if args.serve:
        import http.server
        import socketserver
        os.chdir(os.path.dirname(args.output))
        handler = http.server.SimpleHTTPRequestHandler
        with socketserver.TCPServer(("", args.serve), handler) as httpd:
            print(f"🌐 Сервер запущен: http://localhost:{args.serve}/{os.path.basename(args.output)}")
            httpd.serve_forever()


if __name__ == '__main__':
    main()
