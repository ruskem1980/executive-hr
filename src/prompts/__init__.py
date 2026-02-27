"""
Модуль анализа промптов и template library.

Этот модуль предоставляет инструменты для:
- Анализа failures промптов
- Извлечения паттернов ошибок
- Генерации рекомендаций по улучшению
- Сборки промптов из templates с учетом сложности и контекста
- Оптимизации промптов через DSPy-подобную парадигму
- Автоматической калибровки промптов на основе feedback
"""

from .prompt_analyzer import PromptAnalyzer
from .prompt_builder import build_prompt
from .dspy_optimizer import DSPyOptimizer
from .auto_prompt_tuner import AutoPromptTuner

__all__ = [
    'PromptAnalyzer',
    'build_prompt',
    'DSPyOptimizer',
    'AutoPromptTuner',
]
