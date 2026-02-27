"""
Модуль интеллектуальной предобработки запросов.

Компоненты:
- hybrid_classifier: Гибридная классификация (keyword + LLM fallback)
- tool_orchestrator: Оркестрация инструментов статического анализа
- smart_executor: Умное выполнение тестов и анализа
"""

from .hybrid_classifier import HybridClassifier, RequestType
from .tool_orchestrator import ToolOrchestrator
from .smart_executor import SmartExecutor

__all__ = [
    "HybridClassifier",
    "RequestType",
    "ToolOrchestrator",
    "SmartExecutor",
]

__version__ = "1.0.0"
