"""
Модуль агрегации и форматирования отчетов.

Компоненты:
- hybrid_report_aggregator: Агрегация результатов тестов и статического анализа
- token_tracker: Учёт расхода токенов LLM моделей
"""

from .hybrid_report_aggregator import HybridReportAggregator
from .token_tracker import TokenTracker

__all__ = [
    "HybridReportAggregator",
    "TokenTracker",
]

__version__ = "1.0.0"
