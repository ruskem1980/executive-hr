# ML модуль для интеллектуального роутинга

Машинное обучение для автоматической классификации задач и выбора оптимальных агентов.

## Компоненты

### 1. TaskClassifier
**Классификация сложности задач:** program | simple | medium | complex

```python
from src.ml import TaskClassifier

classifier = TaskClassifier()
classifier.load('data/models/task_classifier.pkl')

complexity = classifier.predict("Добавь валидацию email")
# → "simple"
```

### 2. AgentSelector
**Ранжирование агентов** по пригодности для задачи.

```python
from src.ml import AgentSelector

selector = AgentSelector()
selector.load('data/models/agent_selector.pkl')

task_features = {'complexity_num': 2.0, 'requires_security': 1}
agents = [{'type': 'coder', 'past_performance': 0.85, 'current_load': 0.3}, ...]

ranked = selector.rank_agents(task_features, agents)
# → топ-3 агента с ML оценками
```

### 3. LearningLibrary
**Векторный поиск** похожих успешных паттернов решения задач.

```python
from src.ml import LearningLibrary

library = LearningLibrary()
results = library.search_similar("Как реализовать JWT auth?", top_k=3)
# → 3 наиболее похожих паттерна с решениями
```

## Быстрый старт

### Установка зависимостей
```bash
pip install scikit-learn>=1.3.0 chromadb>=0.4.0 sentence-transformers>=2.2.2
```

### Обучение моделей
```bash
# С синтетическими данными (для начала)
python3 scripts/train_ml_models.py --synthetic

# Только из реальных данных token_usage.db
python3 scripts/train_ml_models.py
```

### Использование
```python
from src.ml import TaskClassifier, AgentSelector, LearningLibrary

# 1. Классифицировать задачу
classifier = TaskClassifier()
classifier.load('data/models/task_classifier.pkl')
complexity, confidence = classifier.predict(task_desc, return_confidence=True)

# Fallback на правила при низкой уверенности
if confidence < 0.7:
    complexity = TaskClassifier.rule_based_fallback(task_desc)

# 2. Выбрать агента
selector = AgentSelector()
selector.load('data/models/agent_selector.pkl')
top_agents = selector.rank_agents(task_features, available_agents)

# 3. Найти похожие решения
library = LearningLibrary()
similar = library.search_similar(task_desc, top_k=3)
```

## Архитектура

```
src/ml/
├── __init__.py              # Экспорт классов
├── task_classifier.py       # TF-IDF + RandomForest
├── agent_selector.py        # GradientBoosting регрессор
├── learning_library.py      # ChromaDB + Sentence Transformers
└── README.md               # Эта инструкция

data/
├── models/
│   ├── task_classifier.pkl
│   └── agent_selector.pkl
└── chroma_db/              # Векторная БД паттернов

scripts/
└── train_ml_models.py      # CLI для обучения

tests/unit/
└── test_ml_classifier.py   # 30+ тестов
```

## Метрики производительности

| Компонент | Скорость | Модель | Точность |
|-----------|----------|--------|----------|
| TaskClassifier | ~5ms | RandomForest (50 trees) | 85-90% |
| AgentSelector | ~3ms | GradientBoosting (100 trees) | R²=0.91 |
| LearningLibrary | ~50ms | Sentence-BERT embeddings | Cosine similarity |

## Hybrid подход

ML модели комбинируются с rule-based fallback:
- **Confidence >= 0.7**: использовать ML предсказание
- **Confidence < 0.7**: fallback на эвристики

Это обеспечивает:
- ✅ Высокую точность ML на типичных задачах
- ✅ Надёжность правил на edge cases
- ✅ Graceful degradation при отсутствии обученных моделей

## Примеры обучающих данных

### TaskClassifier
```python
tasks = [
    ("Покажи отчёт о токенах", "program"),
    ("Добавь валидацию email", "simple"),
    ("Создай API endpoint", "medium"),
    ("Рефактори архитектуру", "complex")
]
```

### AgentSelector
```python
# [similarity, performance, load, complexity, spec_match] → success_score
features = [
    [0.8, 0.9, 0.8, 2.0, 1.0],  # → 0.95 (отличное совпадение)
    [0.3, 0.5, 0.3, 3.0, 0.0],  # → 0.3 (плохое совпадение)
]
```

### LearningLibrary
```python
library.add_pattern(
    task_id='jwt_auth_001',
    description='Реализация JWT аутентификации',
    solution='PyJWT + refresh tokens в Redis',
    metadata={'complexity': 'medium', 'success_score': 0.95}
)
```

## Тестирование

```bash
# Запуск всех тестов ML модуля
pytest tests/unit/test_ml_classifier.py -v

# Конкретный компонент
pytest tests/unit/test_ml_classifier.py::test_task_classifier_train -v

# С покрытием
pytest tests/unit/test_ml_classifier.py --cov=src/ml --cov-report=html
```

## Roadmap

- [x] TaskClassifier (TF-IDF + RandomForest)
- [x] AgentSelector (GradientBoosting)
- [x] LearningLibrary (ChromaDB + SentenceTransformers)
- [x] CLI для обучения
- [x] 30+ юнит-тестов
- [ ] Интеграция в router.js
- [ ] XGBoost классификатор
- [ ] Neural network селектор
- [ ] Reinforcement learning оптимизация

## Документация

Полная документация: [docs/ml_components_guide.md](../../docs/ml_components_guide.md)

## Лицензия

MIT
