#!/usr/bin/env python3
"""
Wrapper для ML классификации задач из JavaScript.

Использование:
    python3 scripts/ml_classify.py "Описание задачи"

Возвращает JSON:
    {
        "complexity": "program|simple|medium|complex",
        "confidence": 0.85,
        "method": "ml|fallback|fallback_no_model|fallback_error"
    }
"""

import sys
import json
from pathlib import Path

# Добавить src в PYTHONPATH
sys.path.insert(0, str(Path(__file__).parent.parent))

# Опциональные импорты — работают только в PT_Standart_Agents.
# В интегрированных проектах используется rule-based fallback.
try:
    from src.ml import TaskClassifier
    from src.ml.feature_store import FeatureStore
    _SRC_ML_AVAILABLE = True
except ImportError:
    _SRC_ML_AVAILABLE = False
    TaskClassifier = None
    FeatureStore = None


def _simple_rule_fallback(task: str) -> str:
    """Keyword fallback когда src.ml недоступен (для интегрированных проектов)."""
    t = task.lower()
    complex_kw = ['архитектур', 'рефакторинг', 'jwt', 'auth', 'kubernetes', 'helm',
                  'microservice', 'migration', 'deploy', 'infrastructure', 'oauth']
    medium_kw = ['добавить', 'создать', 'update', 'endpoint', 'api', 'test', 'тест',
                 'валидация', 'validation', 'middleware', 'service', 'feature']
    program_kw = ['отчёт', 'report', 'show', 'список', 'list', 'проверить', 'check',
                  'скрипт', 'script', 'статистика', 'stats']
    if any(kw in t for kw in complex_kw):
        return 'complex'
    if any(kw in t for kw in medium_kw):
        return 'medium'
    if any(kw in t for kw in program_kw):
        return 'program'
    return 'simple'


def _compute_keyword_features(task: str) -> dict:
    """
    Вычислить keyword-features для сохранения в feature store.

    Повторяет логику TaskClassifier._extract_keyword_features, но для одной задачи
    и возвращает словарь вместо numpy array.
    """
    if not _SRC_ML_AVAILABLE:
        return {}
    import re
    task_lower = task.lower()

    prog_hits = sum(1 for kw in TaskClassifier.PROGRAM_KEYWORDS if kw in task_lower)
    comp_hits = sum(1 for kw in TaskClassifier.COMPLEX_KEYWORDS if kw in task_lower)
    med_hits = sum(1 for kw in TaskClassifier.MEDIUM_KEYWORDS if kw in task_lower)

    return {
        'program_hits': min(prog_hits / 3.0, 1.0),
        'complex_hits': min(comp_hits / 3.0, 1.0),
        'medium_hits': min(med_hits / 3.0, 1.0),
        'text_length': min(len(task) / 100.0, 1.0),
        'word_count': min(len(task.split()) / 15.0, 1.0),
        'has_file_count': 1.0 if re.search(r'\d+\s*файл', task_lower) else 0.0,
    }


def _record_to_feature_store(task_description: str, result: dict):
    """
    Сохранить результат классификации в feature store.

    Не блокирует основной flow — при ошибке просто игнорируем.
    """
    if not _SRC_ML_AVAILABLE:
        return
    try:
        store = FeatureStore()
        keyword_features = _compute_keyword_features(task_description)
        store.record(
            task_description=task_description,
            complexity_label=result.get('complexity', 'simple'),
            confidence=result.get('confidence', 0.0),
            method=result.get('method', 'unknown'),
            keyword_features=keyword_features,
        )
    except Exception:
        # Feature store не должен блокировать классификацию
        pass


def classify_task(task_description: str) -> dict:
    """
    Классификация задачи через ML.

    Args:
        task_description: Описание задачи

    Returns:
        {
            'complexity': 'program|simple|medium|complex',
            'confidence': 0.85,
            'method': 'ml|fallback|fallback_no_model|fallback_error',
            'ml_prediction': 'medium' (опционально, при fallback)
        }
    """
    # Если src.ml недоступен (интегрированный проект) — keyword fallback
    if not _SRC_ML_AVAILABLE:
        return {
            'complexity': _simple_rule_fallback(task_description),
            'confidence': 0.5,
            'method': 'fallback_no_src',
            'message': 'src.ml not available, using keyword fallback'
        }
    try:
        # Путь к обученной модели
        classifier = TaskClassifier()
        model_path = Path(__file__).parent.parent / 'data/models/task_classifier.pkl'

        # Проверка существования модели
        if not model_path.exists():
            # Модель не обучена - использовать правила
            complexity = TaskClassifier.rule_based_fallback(task_description)
            return {
                'complexity': complexity,
                'confidence': 0.5,
                'method': 'fallback_no_model',
                'message': f'Model not found at {model_path}. Using rule-based fallback.'
            }

        # Загрузка модели
        classifier.load(str(model_path))

        # ML предсказание
        complexity, confidence = classifier.predict(
            task_description,
            return_confidence=True
        )

        # Если уверенность низкая - fallback на правила
        if confidence < 0.7:
            fallback_complexity = TaskClassifier.rule_based_fallback(task_description)
            return {
                'complexity': fallback_complexity,
                'confidence': float(confidence),
                'method': 'fallback_low_conf',
                'ml_prediction': complexity,
                'message': f'Low ML confidence ({confidence:.2f}). Using rule-based fallback.'
            }

        # Успешное ML предсказание
        return {
            'complexity': complexity,
            'confidence': float(confidence),
            'method': 'ml'
        }

    except Exception as e:
        # При любой ошибке - fallback на правила
        complexity = TaskClassifier.rule_based_fallback(task_description)
        return {
            'complexity': complexity,
            'confidence': 0.0,
            'method': 'fallback_error',
            'error': str(e),
            'message': 'ML classification failed. Using rule-based fallback.'
        }


def main():
    """CLI интерфейс для вызова из JavaScript."""
    if len(sys.argv) < 2:
        result = {
            'error': 'Task description required',
            'usage': 'python3 scripts/ml_classify.py "Task description"'
        }
        print(json.dumps(result), file=sys.stderr)
        sys.exit(1)

    # Объединить все аргументы в описание задачи
    task_description = ' '.join(sys.argv[1:])

    # Классификация
    result = classify_task(task_description)

    # Сохранение в feature store (не блокирует основной flow)
    _record_to_feature_store(task_description, result)

    # Вывод JSON
    print(json.dumps(result))
    sys.exit(0)


if __name__ == '__main__':
    main()
