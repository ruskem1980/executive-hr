"""
ML модуль для интеллектуального роутинга задач.

Компоненты:
- TaskClassifier: Классификация сложности задач
- AgentSelector: Выбор оптимального агента для задачи
- FeatureStore: Хранилище признаков для переобучения
- LearningLibrary: Векторный поиск похожих паттернов
"""

from .task_classifier import TaskClassifier
from .agent_selector import AgentSelector
from .feature_store import FeatureStore

# LearningLibrary требует chromadb + sentence-transformers (тяжёлые зависимости)
# Ленивый импорт чтобы не блокировать использование TaskClassifier/AgentSelector
def __getattr__(name):
    if name == 'LearningLibrary':
        from .learning_library import LearningLibrary
        return LearningLibrary
    raise AttributeError(f"module 'src.ml' has no attribute {name}")

__all__ = ['TaskClassifier', 'AgentSelector', 'FeatureStore', 'LearningLibrary']
