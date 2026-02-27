#!/usr/bin/env python3
"""
Автоматический классификатор сложности задач для принудительного делегирования

Анализирует описание задачи и определяет сложность:
- simple: 1-2 файла, простые изменения
- medium: 3-5 файлов, новые фичи, API endpoints
- complex: 6+ файлов, архитектура, безопасность

Использование:
    python3 .claude/helpers/task-classifier.py "Описание задачи"

Выход:
    JSON: {"complexity": "medium", "reason": "...", "recommended_approach": "..."}
"""

import sys
import json
import re
from typing import Dict, Tuple

class TaskClassifier:
    """Классификатор сложности задач"""

    # Индикаторы сложности
    SIMPLE_INDICATORS = [
        r'исправ(ить|ление) опечатк',
        r'изменить текст',
        r'добавить комментари',
        r'обновить README',
        r'фикс бага',
        r'простое изменение',
        r'один файл',
        r'одна строк',
    ]

    MEDIUM_INDICATORS = [
        r'новая фича',
        r'новый функционал',
        r'новый компонент',
        r'API endpoint',
        r'форма',
        r'модуль',
        r'рефакторинг',
        r'несколько файлов',
        r'3-5 файл',
        r'интеграция',
    ]

    COMPLEX_INDICATORS = [
        r'архитектур',
        r'безопасность',
        r'миграция',
        r'много файлов',
        r'6\+ файл',
        r'database schema',
        r'авторизация',
        r'аутентификация',
        r'масштабирование',
        r'оптимизация производительности',
        r'рефакторинг всего',
    ]

    def __init__(self):
        self.simple_patterns = [re.compile(p, re.IGNORECASE) for p in self.SIMPLE_INDICATORS]
        self.medium_patterns = [re.compile(p, re.IGNORECASE) for p in self.MEDIUM_INDICATORS]
        self.complex_patterns = [re.compile(p, re.IGNORECASE) for p in self.COMPLEX_INDICATORS]

    def classify(self, description: str) -> Dict:
        """Классифицировать задачу по описанию"""

        # Подсчёт совпадений
        simple_score = sum(1 for p in self.simple_patterns if p.search(description))
        medium_score = sum(1 for p in self.medium_patterns if p.search(description))
        complex_score = sum(1 for p in self.complex_patterns if p.search(description))

        # Определение сложности
        if complex_score > 0:
            complexity = "complex"
            reason = f"Найдено {complex_score} индикаторов сложной задачи"
            approach = "opus_direct"
            savings = 0
        elif medium_score > simple_score:
            complexity = "medium"
            reason = f"Найдено {medium_score} индикаторов средней сложности"
            approach = "opus_classify -> flash_execute -> pro_review -> opus_verify"
            savings = 80  # 80% экономия
        elif simple_score > 0:
            complexity = "simple"
            reason = f"Найдено {simple_score} индикаторов простой задачи"
            approach = "opus_direct"
            savings = 0
        else:
            # По умолчанию: средняя (безопаснее использовать делегирование)
            complexity = "medium"
            reason = "Не найдено явных индикаторов, используется средняя сложность по умолчанию"
            approach = "opus_classify -> flash_execute -> pro_review -> opus_verify"
            savings = 80

        return {
            "complexity": complexity,
            "reason": reason,
            "recommended_approach": approach,
            "estimated_savings_percent": savings,
            "delegation_required": complexity == "medium",
            "scores": {
                "simple": simple_score,
                "medium": medium_score,
                "complex": complex_score
            }
        }


def main():
    if len(sys.argv) < 2:
        print("Usage: task-classifier.py <task_description>", file=sys.stderr)
        sys.exit(1)

    description = " ".join(sys.argv[1:])
    classifier = TaskClassifier()
    result = classifier.classify(description)

    # Вывод JSON
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == '__main__':
    main()
