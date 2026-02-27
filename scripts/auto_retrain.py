#!/usr/bin/env python3
"""
Auto-retrain: автоматическое переобучение ML моделей.

Проверяет количество завершённых задач с момента последнего обучения
и переобучает модели если накопилось >= N новых задач.

Использование:
    python3 scripts/auto_retrain.py                 # Проверка и переобучение если нужно
    python3 scripts/auto_retrain.py --force          # Принудительное переобучение
    python3 scripts/auto_retrain.py --threshold 10   # Порог: 10 задач (по умолчанию 20)
    python3 scripts/auto_retrain.py --status          # Показать статус
"""

import sys
import os
import json
import sqlite3
import argparse
from datetime import datetime

# Корень проекта
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Файл метаданных последнего обучения
RETRAIN_STATE_FILE = os.path.join(ROOT, 'data', 'models', 'retrain_state.json')
DB_PATH = os.path.join(ROOT, 'data', 'token_usage.db')
DEFAULT_THRESHOLD = 20


def get_task_count_since(since_timestamp: str) -> int:
    """Количество завершённых задач с указанного момента."""
    if not os.path.exists(DB_PATH):
        return 0
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM tasks
        WHERE finished_at IS NOT NULL
        AND complexity IS NOT NULL
        AND started_at > ?
    """, (since_timestamp,))
    count = cursor.fetchone()[0]
    conn.close()
    return count


def get_total_task_count() -> int:
    """Общее количество завершённых задач с метками сложности."""
    if not os.path.exists(DB_PATH):
        return 0
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM tasks
        WHERE complexity IS NOT NULL
        AND complexity != ''
        AND query IS NOT NULL
        AND query != ''
    """)
    count = cursor.fetchone()[0]
    conn.close()
    return count


def load_retrain_state() -> dict:
    """Загрузка состояния последнего переобучения."""
    if os.path.exists(RETRAIN_STATE_FILE):
        with open(RETRAIN_STATE_FILE, 'r') as f:
            return json.load(f)
    return {
        'last_retrain': '2000-01-01T00:00:00',
        'last_task_count': 0,
        'retrain_count': 0,
        'last_accuracy': 0.0,
        'last_metrics': {}
    }


def save_retrain_state(state: dict):
    """Сохранение состояния переобучения."""
    os.makedirs(os.path.dirname(RETRAIN_STATE_FILE), exist_ok=True)
    with open(RETRAIN_STATE_FILE, 'w') as f:
        json.dump(state, f, indent=2, ensure_ascii=False)


def retrain_models(force: bool = False) -> dict:
    """
    Переобучение моделей TaskClassifier и AgentSelector.

    Returns:
        Словарь с метриками обучения
    """
    from scripts.train_ml_models import (
        load_training_data_from_db, generate_synthetic_data,
        train_task_classifier, train_agent_selector
    )

    print("\n" + "=" * 70)
    print("🔄 AUTO-RETRAIN: Переобучение ML моделей")
    print("=" * 70)
    print(f"📅 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"🔧 Режим: {'принудительный' if force else 'автоматический'}\n")

    # Обучение TaskClassifier с синтетикой
    classifier = train_task_classifier(use_synthetic=True)

    # Обучение AgentSelector
    train_agent_selector()

    # Сохранение состояния
    state = load_retrain_state()
    total_tasks = get_total_task_count()

    # Получение accuracy из последнего обучения
    accuracy = 0.0
    if classifier and classifier.is_trained:
        # Тестовое предсказание для проверки
        test_tasks = [
            "Покажи отчёт о токенах",
            "Исправь баг в main.py",
            "Создай API endpoint",
            "Рефактори архитектуру"
        ]
        expected = ['program', 'simple', 'medium', 'complex']
        predictions = classifier.predict_batch(test_tasks)
        correct = sum(1 for p, e in zip(predictions, expected) if p == e)
        accuracy = correct / len(expected)

    state.update({
        'last_retrain': datetime.now().isoformat(),
        'last_task_count': total_tasks,
        'retrain_count': state.get('retrain_count', 0) + 1,
        'last_accuracy': accuracy,
    })
    save_retrain_state(state)

    print(f"\n✅ AUTO-RETRAIN завершён")
    print(f"   Всего задач в БД: {total_tasks}")
    print(f"   Тестовая accuracy: {accuracy:.0%}")
    print(f"   Количество переобучений: {state['retrain_count']}")

    return state


def check_and_retrain(threshold: int = DEFAULT_THRESHOLD, force: bool = False) -> bool:
    """
    Проверка необходимости переобучения и запуск если нужно.

    Args:
        threshold: Минимум новых задач для запуска переобучения
        force: Принудительное переобучение

    Returns:
        True если переобучение было выполнено
    """
    state = load_retrain_state()
    new_tasks = get_task_count_since(state['last_retrain'])
    total_tasks = get_total_task_count()

    print(f"📊 Статус auto-retrain:")
    print(f"   Последнее обучение: {state['last_retrain']}")
    print(f"   Новых задач с тех пор: {new_tasks}")
    print(f"   Всего задач в БД: {total_tasks}")
    print(f"   Порог для переобучения: {threshold}")
    print(f"   Последняя accuracy: {state.get('last_accuracy', 'н/д')}")

    if force or new_tasks >= threshold:
        reason = "принудительно" if force else f"накопилось {new_tasks} новых задач (>= {threshold})"
        print(f"\n🔄 Запуск переобучения: {reason}")
        retrain_models(force=force)
        return True
    else:
        remaining = threshold - new_tasks
        print(f"\n⏳ Переобучение не требуется. Осталось {remaining} задач до порога.")
        return False


def show_status():
    """Показать текущий статус auto-retrain."""
    state = load_retrain_state()
    new_tasks = get_task_count_since(state['last_retrain'])
    total = get_total_task_count()

    print("=" * 50)
    print("📊 AUTO-RETRAIN СТАТУС")
    print("=" * 50)
    print(f"  Последнее обучение:     {state['last_retrain']}")
    print(f"  Количество переобучений: {state.get('retrain_count', 0)}")
    print(f"  Последняя accuracy:      {state.get('last_accuracy', 'н/д')}")
    print(f"  Всего задач в БД:        {total}")
    print(f"  Новых задач:             {new_tasks}")
    print(f"  Порог:                   {DEFAULT_THRESHOLD}")

    model_path = os.path.join(ROOT, 'data', 'models', 'task_classifier.pkl')
    if os.path.exists(model_path):
        mtime = os.path.getmtime(model_path)
        print(f"  Файл модели:             {datetime.fromtimestamp(mtime).strftime('%Y-%m-%d %H:%M')}")
    else:
        print(f"  Файл модели:             не найден")
    print("=" * 50)


def main():
    parser = argparse.ArgumentParser(description='Auto-retrain ML моделей')
    parser.add_argument('--force', action='store_true',
                        help='Принудительное переобучение')
    parser.add_argument('--threshold', type=int, default=DEFAULT_THRESHOLD,
                        help=f'Порог новых задач для переобучения (по умолчанию {DEFAULT_THRESHOLD})')
    parser.add_argument('--status', action='store_true',
                        help='Показать статус')
    args = parser.parse_args()

    if args.status:
        show_status()
    else:
        check_and_retrain(threshold=args.threshold, force=args.force)


if __name__ == '__main__':
    main()
