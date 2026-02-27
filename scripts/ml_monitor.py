#!/usr/bin/env python3
"""
Мониторинг деградации ML моделей.

Загружает обученную модель TaskClassifier, тестирует на бенчмарке
(синтетические + реальные данные), сравнивает accuracy с предыдущим
значением и выдаёт алерты при деградации.

Использование:
    python3 scripts/ml_monitor.py              # Проверка + алерт
    python3 scripts/ml_monitor.py --auto-fix   # Проверка + автоматическое переобучение
    python3 scripts/ml_monitor.py --history    # История проверок
    python3 scripts/ml_monitor.py --threshold 90  # Пользовательский порог
"""

import os
import sys
import json
import argparse
import io
from contextlib import redirect_stdout
from datetime import datetime
from typing import List, Tuple, Dict

# Корень проекта
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

from sklearn.metrics import accuracy_score, f1_score, classification_report

from src.ml.task_classifier import TaskClassifier
from scripts.train_ml_models import generate_synthetic_data, load_training_data_from_db
from scripts.auto_retrain import retrain_models

# Константы путей
MODEL_PATH = os.path.join(ROOT, 'data', 'models', 'task_classifier.pkl')
RETRAIN_STATE_FILE = os.path.join(ROOT, 'data', 'models', 'retrain_state.json')
MONITOR_LOG_FILE = os.path.join(ROOT, 'data', 'models', 'monitor_log.jsonl')
DB_PATH = os.path.join(ROOT, 'data', 'token_usage.db')

# Пороговые значения
DEFAULT_THRESHOLD = 85.0
CRITICAL_THRESHOLD = 70.0
DEGRADATION_DELTA = -5.0  # Процентные пункты

# Классы модели
CLASSES = ['program', 'simple', 'medium', 'complex']


def load_model() -> TaskClassifier:
    """Загрузка обученной модели TaskClassifier с диска."""
    if not os.path.exists(MODEL_PATH):
        print(f"  Файл модели не найден: {MODEL_PATH}")
        print("  Запустите обучение: python3 scripts/train_ml_models.py --synthetic")
        sys.exit(1)

    classifier = TaskClassifier()
    try:
        classifier.load(MODEL_PATH)
        return classifier
    except Exception as e:
        print(f"  Ошибка загрузки модели: {e}")
        sys.exit(1)


def build_benchmark_dataset() -> Tuple[List[str], List[str]]:
    """
    Построение бенчмарк-набора из синтетических и реальных данных.

    Подавляет stdout от generate_synthetic_data / load_training_data_from_db,
    чтобы не засорять вывод мониторинга.
    """
    # Подавляем вывод функций, которые печатают статистику
    buf = io.StringIO()
    with redirect_stdout(buf):
        synth_tasks, synth_labels = generate_synthetic_data()
        db_tasks, db_labels = load_training_data_from_db(DB_PATH)

    tasks = synth_tasks + db_tasks
    labels = synth_labels + db_labels

    if not tasks:
        print("  Нет данных для бенчмарка.")
        print("  БД пуста и синтетические данные не загружены.")
        sys.exit(1)

    return tasks, labels


def evaluate_model(classifier: TaskClassifier,
                   tasks: List[str],
                   labels: List[str]) -> Dict:
    """
    Оценка модели на бенчмарке.

    Возвращает словарь с метриками:
    - accuracy (в процентах)
    - per_class_f1
    - classification_report
    - total_samples
    """
    y_pred = classifier.predict_batch(tasks)

    acc = accuracy_score(labels, y_pred) * 100.0

    # Per-class F1
    f1_vals = f1_score(
        labels, y_pred,
        average=None, labels=CLASSES, zero_division=0
    )
    per_class_f1 = {cls: float(val) for cls, val in zip(CLASSES, f1_vals)}

    # Полный отчёт
    report = classification_report(
        labels, y_pred,
        labels=CLASSES, zero_division=0
    )

    return {
        'accuracy': acc,
        'per_class_f1': per_class_f1,
        'classification_report': report,
        'total_samples': len(tasks),
    }


def load_previous_accuracy() -> float:
    """
    Загрузка предыдущего значения accuracy из retrain_state.json.

    Значение в файле хранится в диапазоне 0.0-1.0,
    возвращаем в процентах.
    """
    if not os.path.exists(RETRAIN_STATE_FILE):
        return 0.0

    try:
        with open(RETRAIN_STATE_FILE, 'r', encoding='utf-8') as f:
            state = json.load(f)
        raw = float(state.get('last_accuracy', 0.0))
        # Значение <= 1.0 — интерпретируем как долю, конвертируем в %
        if raw <= 1.0:
            return raw * 100.0
        return raw
    except (json.JSONDecodeError, ValueError, TypeError):
        return 0.0


def log_result(result: Dict):
    """Запись результата мониторинга в monitor_log.jsonl."""
    os.makedirs(os.path.dirname(MONITOR_LOG_FILE), exist_ok=True)

    entry = {
        'timestamp': datetime.now().isoformat(),
        'accuracy': round(result['accuracy'], 2),
        'previous_accuracy': round(result['previous_accuracy'], 2),
        'delta': round(result['delta'], 2),
        'status': result['status'],
        'per_class_f1': {k: round(v, 4) for k, v in result['per_class_f1'].items()},
        'threshold': result['threshold'],
        'total_samples': result.get('total_samples', 0),
    }

    with open(MONITOR_LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(json.dumps(entry, ensure_ascii=False) + '\n')


def show_history():
    """Отображение истории проверок из monitor_log.jsonl."""
    if not os.path.exists(MONITOR_LOG_FILE):
        print("  История мониторинга пуста. Запустите проверку хотя бы раз.")
        return

    entries = []
    with open(MONITOR_LOG_FILE, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    if not entries:
        print("  История мониторинга пуста.")
        return

    sep = "\u2550" * 75
    print(sep)
    print("  ИСТОРИЯ МОНИТОРИНГА ML МОДЕЛИ")
    print(sep)
    print(f"  {'Дата/время':<20} {'Accuracy':>10} {'Дельта':>10} {'Статус':<10} {'Порог':>7}")
    print("\u2500" * 75)

    for e in entries:
        dt = datetime.fromisoformat(e['timestamp']).strftime('%Y-%m-%d %H:%M')
        acc = f"{e['accuracy']:.1f}%"
        delta = f"{e['delta']:+.1f}%"
        status = e['status']
        thresh = f"{e.get('threshold', DEFAULT_THRESHOLD):.0f}%"
        print(f"  {dt:<20} {acc:>10} {delta:>10} {status:<10} {thresh:>7}")

    print(sep)
    print(f"  Всего проверок: {len(entries)}")
    print(sep)


def determine_status(current_acc: float, prev_acc: float,
                     delta: float, threshold: float) -> str:
    """
    Определение статуса модели.

    Приоритет: CRITICAL > ALERT > WARN > OK
    """
    if current_acc < CRITICAL_THRESHOLD:
        return "CRITICAL"
    if current_acc < threshold:
        return "ALERT"
    # Проверка резкой деградации (падение > 5 п.п. от предыдущей)
    if prev_acc > 0 and delta < DEGRADATION_DELTA:
        return "WARN"
    return "OK"


def format_status_indicator(status: str) -> str:
    """Текстовый индикатор статуса."""
    indicators = {
        'OK': 'OK (выше порога)',
        'WARN': 'WARN (деградация > 5 п.п.)',
        'ALERT': 'ALERT (ниже порога)',
        'CRITICAL': 'CRITICAL (ниже 70%)',
    }
    return indicators.get(status, status)


def format_delta_indicator(delta: float) -> str:
    """Индикатор дельты: зелёная галка или красный крест."""
    if delta >= -1.0:
        return f"{delta:+.1f}% [OK]"
    elif delta >= DEGRADATION_DELTA:
        return f"{delta:+.1f}% [!]"
    else:
        return f"{delta:+.1f}% [ДЕГРАДАЦИЯ]"


def run_monitor(threshold: float, auto_fix: bool):
    """
    Основной процесс мониторинга.

    1. Загружает модель
    2. Строит бенчмарк
    3. Оценивает accuracy и per-class F1
    4. Сравнивает с предыдущим значением
    5. Выводит отчёт
    6. Логирует результат
    7. При CRITICAL + auto_fix — запускает переобучение
    """
    sep = "\u2550" * 55

    # 1. Загрузка модели
    classifier = load_model()

    # 2. Построение бенчмарка
    tasks, labels = build_benchmark_dataset()

    # 3. Оценка
    metrics = evaluate_model(classifier, tasks, labels)
    current_acc = metrics['accuracy']

    # 4. Предыдущая accuracy
    prev_acc = load_previous_accuracy()
    delta = current_acc - prev_acc

    # 5. Статус
    status = determine_status(current_acc, prev_acc, delta, threshold)

    # 6. Вывод отчёта
    print(sep)
    print("  ML МОНИТОРИНГ ДЕГРАДАЦИИ")
    print(sep)
    print(f"  Текущая accuracy:    {current_acc:.1f}%")
    print(f"  Предыдущая accuracy: {prev_acc:.1f}%")
    print(f"  Дельта:              {format_delta_indicator(delta)}")
    print(f"  Выборка бенчмарка:   {metrics['total_samples']} примеров")
    print()
    print("  Per-class F1:")
    for cls in CLASSES:
        f1 = metrics['per_class_f1'].get(cls, 0.0)
        print(f"    {cls:<10}: {f1:.2f}")
    print()
    print(f"  Порог:  {threshold:.0f}%")
    print(f"  Статус: {format_status_indicator(status)}")
    print(sep)

    # 7. Логирование
    result = {
        'accuracy': current_acc,
        'previous_accuracy': prev_acc,
        'delta': delta,
        'status': status,
        'per_class_f1': metrics['per_class_f1'],
        'threshold': threshold,
        'total_samples': metrics['total_samples'],
    }
    log_result(result)

    # 8. Автоматическое переобучение при CRITICAL
    if status == "CRITICAL" and auto_fix:
        print()
        print("  ОБНАРУЖЕНА КРИТИЧЕСКАЯ ДЕГРАДАЦИЯ!")
        print("  Запуск принудительного переобучения...")
        print()
        try:
            retrain_models(force=True)
            print()
            print("  Переобучение завершено.")
        except Exception as e:
            print(f"  Ошибка при переобучении: {e}")
    elif status == "CRITICAL" and not auto_fix:
        print()
        print("  Рекомендация: запустите с флагом --auto-fix для")
        print("  автоматического переобучения модели.")
    elif status == "ALERT":
        print()
        print(f"  Accuracy ниже порога ({threshold:.0f}%). Рассмотрите переобучение:")
        print("  python3 scripts/auto_retrain.py --force")
    elif status == "WARN":
        print()
        print("  Обнаружена деградация > 5 п.п. от предыдущего значения.")
        print("  Рекомендуется наблюдение и планирование переобучения.")

    return status


def main():
    parser = argparse.ArgumentParser(
        description='Мониторинг деградации ML моделей классификации задач'
    )
    parser.add_argument(
        '--auto-fix', action='store_true',
        help='Автоматическое переобучение при статусе CRITICAL (<70%%)'
    )
    parser.add_argument(
        '--history', action='store_true',
        help='Показать историю проверок из лога'
    )
    parser.add_argument(
        '--threshold', type=float, default=DEFAULT_THRESHOLD,
        help=f'Порог accuracy для статуса ALERT (по умолчанию {DEFAULT_THRESHOLD}%%)'
    )

    args = parser.parse_args()

    if args.history:
        show_history()
    else:
        run_monitor(args.threshold, args.auto_fix)


if __name__ == '__main__':
    main()
