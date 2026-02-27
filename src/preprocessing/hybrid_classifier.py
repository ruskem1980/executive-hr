"""
HybridClassifier - гибридный классификатор запросов с keyword + LLM fallback.

Модуль реализует двухступенчатую классификацию:
1. Keyword-based классификация с confidence score
2. LLM fallback для сложных случаев (confidence < 0.7)

Автор: Claude Code (PT_Standart)
Версия: 1.0.0
"""

import json
import re
import subprocess
from enum import Enum
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class RequestType(Enum):
    """Типы запросов для анализа кода."""

    SECURITY = "SECURITY"
    PERFORMANCE = "PERFORMANCE"
    QUALITY = "QUALITY"
    COVERAGE = "COVERAGE"
    ARCHITECTURE = "ARCHITECTURE"
    DOCUMENTATION = "DOCUMENTATION"
    GENERAL = "GENERAL"


class HybridClassifier:
    """
    Гибридный классификатор запросов с fallback на LLM.

    Использует keyword-based подход для простых случаев и переключается на LLM
    (Gemini Flash) для сложных или неоднозначных запросов.

    Attributes:
        categories (Dict): Категории с keywords, весами и инструментами.
        confidence_threshold (float): Порог confidence для перехода на LLM.

    Example:
        >>> classifier = HybridClassifier()
        >>> result = classifier.classify("Проверь безопасность модуля auth")
        >>> print(result)
        {
            "method": "keyword",
            "confidence": 0.85,
            "type": "SECURITY",
            "tests_to_run": ["tests/unit/auth/test_security.py::test_password"],
            "tools": ["bandit", "safety", "semgrep"],
            "scope": "src/auth/"
        }
    """

    def __init__(self, confidence_threshold: float = 0.7):
        """
        Инициализирует классификатор.

        Args:
            confidence_threshold (float): Минимальный confidence для keyword метода.
                Если ниже - переключается на LLM. По умолчанию 0.7.
        """
        self.confidence_threshold = confidence_threshold
        self.categories = self._initialize_categories()

    def _initialize_categories(self) -> Dict:
        """
        Инициализирует категории с keywords и конфигурацией.

        Returns:
            Dict: Словарь категорий с keywords, весами, patterns и tools.
        """
        return {
            "SECURITY": {
                "keywords": {
                    "безопасност": 1.0,
                    "security": 1.0,
                    "уязвим": 1.0,
                    "vulnerability": 1.0,
                    "cve": 0.9,
                    "audit": 0.8,
                    "inject": 0.9,
                    "xss": 0.9,
                    "csrf": 0.9,
                    "sql injection": 1.0,
                    "authentication": 0.8,
                    "authorization": 0.8,
                },
                "tests_pattern": "security",
                "tools": ["bandit", "safety", "semgrep"],
            },
            "PERFORMANCE": {
                "keywords": {
                    "производительност": 1.0,
                    "performance": 1.0,
                    "оптимиз": 1.0,
                    "optimize": 1.0,
                    "медленн": 0.9,
                    "slow": 0.9,
                    "узк": 0.8,
                    "bottleneck": 0.8,
                    "profil": 0.9,
                    "memory leak": 0.9,
                    "cpu": 0.7,
                    "latency": 0.8,
                },
                "tests_pattern": "performance",
                "tools": ["cProfile", "memory_profiler", "py-spy"],
            },
            "QUALITY": {
                "keywords": {
                    "качеств": 1.0,
                    "quality": 1.0,
                    "code smell": 0.9,
                    "рефактор": 0.8,
                    "refactor": 0.8,
                    "сложност": 0.8,
                    "complexity": 0.8,
                    "maintainability": 0.8,
                    "cyclomatic": 0.9,
                    "duplication": 0.8,
                },
                "tests_pattern": "quality",
                "tools": ["radon", "pylint", "flake8"],
            },
            "COVERAGE": {
                "keywords": {
                    "coverage": 1.0,
                    "покрыти": 1.0,
                    "тест": 0.7,
                    "test": 0.7,
                    "gap": 0.8,
                    "пробел": 0.8,
                    "uncovered": 0.9,
                    "missing": 0.7,
                },
                "tests_pattern": "test",
                "tools": ["coverage", "pytest-cov"],
            },
            "ARCHITECTURE": {
                "keywords": {
                    "архитектур": 1.0,
                    "architecture": 1.0,
                    "design": 0.8,
                    "структур": 0.8,
                    "modularity": 0.9,
                    "coupling": 0.8,
                    "cohesion": 0.8,
                    "dependencies": 0.7,
                },
                "tests_pattern": "architecture",
                "tools": ["pydeps", "mccabe"],
            },
            "DOCUMENTATION": {
                "keywords": {
                    "документац": 1.0,
                    "documentation": 1.0,
                    "docstring": 0.9,
                    "comment": 0.7,
                    "комментари": 0.8,
                    "readme": 0.8,
                    "api docs": 0.9,
                },
                "tests_pattern": "doc",
                "tools": ["pydocstyle", "interrogate"],
            },
        }

    def classify(self, user_query: str) -> Dict:
        """
        Классифицирует пользовательский запрос.

        Сначала пытается использовать keyword-based метод. Если confidence < threshold,
        переключается на LLM классификатор (Gemini Flash).

        Args:
            user_query (str): Запрос пользователя на естественном языке.

        Returns:
            Dict: Результат классификации с полями:
                - method (str): "keyword" или "llm"
                - confidence (float): Уверенность в классификации (0.0-1.0)
                - type (str): Тип запроса (RequestType)
                - tests_to_run (List[str]): Список pytest тестов для запуска
                - tools (List[str]): Рекомендуемые инструменты анализа
                - scope (str): Область анализа (путь к модулю/файлу)
                - rationale (str, optional): Обоснование (только для LLM)

        Example:
            >>> classifier = HybridClassifier()
            >>> result = classifier.classify("Найди уязвимости в billing модуле")
            >>> print(f"Type: {result['type']}, Confidence: {result['confidence']}")
            Type: SECURITY, Confidence: 0.92
        """
        if not user_query or not user_query.strip():
            return self._empty_result("Empty query provided")

        # Шаг 1: Попробовать keyword classification
        keyword_result = self._keyword_classify(user_query)

        # Шаг 2: Если confidence высокий - используем keyword результат
        if keyword_result["confidence"] >= self.confidence_threshold:
            keyword_result["method"] = "keyword"
            return keyword_result

        # Шаг 3: Иначе - fallback на LLM
        print(
            f"⚠️  Low confidence ({keyword_result['confidence']:.2f}), "
            f"using LLM classifier..."
        )
        try:
            llm_result = self._llm_classify(user_query)
            llm_result["method"] = "llm"
            return llm_result
        except Exception as e:
            print(f"❌ LLM classification failed: {e}")
            print("↩️  Falling back to keyword result")
            keyword_result["method"] = "keyword_fallback"
            return keyword_result

    def _keyword_classify(self, query: str) -> Dict:
        """
        Keyword-based классификация с расчетом confidence score.

        Подсчитывает взвешенные совпадения keywords для каждой категории
        и выбирает категорию с максимальным normalized score.

        Args:
            query (str): Запрос пользователя.

        Returns:
            Dict: Результат keyword классификации.
        """
        query_lower = query.lower()
        scores = {}

        # Подсчет scores для каждой категории
        for category, config in self.categories.items():
            score = 0
            matches = 0
            matched_weights = []

            for keyword, weight in config["keywords"].items():
                # Используем partial matching для русских слов (без word boundaries)
                # и exact matching для английских технических терминов
                if keyword in query_lower:
                    score += weight
                    matches += 1
                    matched_weights.append(weight)

            if matches > 0:
                # Нормализуем по среднему весу совпавших keywords
                # Это дает более справедливую оценку при малом количестве совпадений
                avg_weight = sum(matched_weights) / len(matched_weights)
                # Base score = среднее значение совпавших весов
                normalized_score = min(avg_weight, 1.0)
                scores[category] = {
                    "score": normalized_score,
                    "matches": matches,
                    "config": config,
                }

        # Если ничего не найдено
        if not scores:
            return {
                "confidence": 0.0,
                "type": RequestType.GENERAL.value,
                "tests_to_run": [],
                "tools": [],
                "scope": self._extract_scope(query),
            }

        # Выбираем категорию с максимальным score
        best_category = max(scores.items(), key=lambda x: x[1]["score"])
        category_name = best_category[0]
        category_data = best_category[1]

        # Confidence = normalized score * (1 + 0.1 * num_matches)
        # Больше совпадений = выше confidence (но не больше 1.0)
        confidence = min(
            category_data["score"] * (1 + 0.1 * category_data["matches"]), 1.0
        )

        # Определяем scope
        scope = self._extract_scope(query)

        # Определяем какие тесты запустить
        tests_to_run = self._find_relevant_tests(
            category_data["config"]["tests_pattern"], scope
        )

        return {
            "confidence": confidence,
            "type": category_name,
            "tests_to_run": tests_to_run,
            "tools": category_data["config"]["tools"],
            "scope": scope,
        }

    def _llm_classify(self, query: str) -> Dict:
        """
        LLM-based классификация для сложных случаев.

        Использует Gemini Flash через gemini_bridge для анализа неоднозначных запросов.

        Args:
            query (str): Запрос пользователя.

        Returns:
            Dict: Результат LLM классификации.

        Raises:
            Exception: Если не удалось вызвать LLM или распарсить ответ.
        """
        # Динамический импорт для избежания circular dependencies
        try:
            from .gemini_bridge import GeminiBridge
        except ImportError:
            raise ImportError(
                "GeminiBridge not found. Please implement gemini_bridge.py"
            )

        prompt = f"""Classify this code analysis request:

"{query}"

Return ONLY valid JSON (no markdown, no explanation):
{{
  "type": "SECURITY|PERFORMANCE|QUALITY|COVERAGE|ARCHITECTURE|DOCUMENTATION",
  "tests_pattern": "keyword for pytest -k",
  "tools": ["tool1", "tool2"],
  "scope": "path in src/",
  "rationale": "1 sentence why"
}}"""

        bridge = GeminiBridge()
        response = bridge.call("flash", prompt)

        # Parse JSON response
        try:
            # Убираем возможные markdown блоки
            response_clean = response.strip()
            if response_clean.startswith("```"):
                response_clean = re.sub(r"```(?:json)?\n?", "", response_clean).strip()

            result = json.loads(response_clean)
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse LLM response as JSON: {e}\n{response}")

        # Валидация типа
        valid_types = {rt.value for rt in RequestType}
        if result.get("type") not in valid_types:
            result["type"] = RequestType.GENERAL.value

        # Находим тесты на основе pattern
        tests_to_run = self._find_relevant_tests(
            result.get("tests_pattern", ""), result.get("scope", "src/")
        )

        return {
            "confidence": 1.0,  # LLM всегда уверен
            "type": result["type"],
            "tests_to_run": tests_to_run,
            "tools": result.get("tools", []),
            "scope": result.get("scope", "src/"),
            "rationale": result.get("rationale", "LLM classification"),
        }

    def _extract_scope(self, query: str) -> str:
        """
        Извлекает scope (область анализа) из запроса.

        Ищет упоминания файлов, модулей, директорий в тексте запроса.

        Args:
            query (str): Запрос пользователя.

        Returns:
            str: Путь к области анализа (например, "src/auth/").

        Example:
            >>> classifier = HybridClassifier()
            >>> scope = classifier._extract_scope("Проверь auth модуль")
            >>> print(scope)
            src/auth/
        """
        # Поиск упоминаний файлов Python
        file_pattern = r"(\w+\.py)"
        file_matches = re.findall(file_pattern, query)
        if file_matches:
            return f"src/{file_matches[0]}"

        # Поиск директорий
        dir_pattern = r"(\w+/)"
        dir_matches = re.findall(dir_pattern, query)
        if dir_matches:
            return f"src/{dir_matches[0]}"

        # Поиск известных модулей
        module_pattern = (
            r"\b(auth|api|models|utils|services|handlers|billing|payment|"
            r"preprocessing|analysis|reporting|core|database|cache|queue)\b"
        )
        match = re.search(module_pattern, query.lower())
        if match:
            return f"src/{match.group(1)}/"

        # Default scope
        return "src/"

    def _find_relevant_tests(self, pattern: str, scope: str) -> List[str]:
        """
        Находит релевантные pytest тесты по pattern и scope.

        Использует `pytest --collect-only` для поиска тестов без их выполнения.

        Args:
            pattern (str): Keyword для pytest -k фильтра.
            scope (str): Область анализа (путь к модулю).

        Returns:
            List[str]: Список путей к тестам в формате pytest
                (например, "tests/unit/auth/test_security.py::test_password").

        Example:
            >>> classifier = HybridClassifier()
            >>> tests = classifier._find_relevant_tests("security", "src/auth/")
            >>> print(tests)
            ['tests/unit/auth/test_security.py::test_password_strength']
        """
        if not pattern:
            return []

        # Формируем команду pytest
        cmd = ["pytest", "--collect-only", "-q", "-k", pattern, "tests/"]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=10, check=False
            )

            # Парсим вывод pytest
            tests = []
            for line in result.stdout.split("\n"):
                # Формат: tests/unit/auth/test_security.py::test_password_strength
                if "::" in line and not line.startswith(" "):
                    test_path = line.strip()
                    # Фильтруем по scope если указан
                    if scope and scope != "src/":
                        # Извлекаем имя модуля из scope (src/auth/ -> auth)
                        scope_module = scope.replace("src/", "").replace("/", "")
                        if scope_module in test_path:
                            tests.append(test_path)
                    else:
                        tests.append(test_path)

            return tests

        except subprocess.TimeoutExpired:
            print(f"⚠️  Timeout while searching tests for pattern: {pattern}")
            return []
        except FileNotFoundError:
            print("⚠️  pytest not found in PATH")
            return []
        except Exception as e:
            print(f"❌ Error finding tests: {e}")
            return []

    def _empty_result(self, reason: str) -> Dict:
        """
        Возвращает пустой результат с указанием причины.

        Args:
            reason (str): Причина пустого результата.

        Returns:
            Dict: Пустой результат классификации.
        """
        return {
            "method": "none",
            "confidence": 0.0,
            "type": RequestType.GENERAL.value,
            "tests_to_run": [],
            "tools": [],
            "scope": "src/",
            "error": reason,
        }


def main():
    """
    Демонстрационный пример использования HybridClassifier.
    """
    classifier = HybridClassifier()

    # Тестовые запросы
    test_queries = [
        "Проверь безопасность модуля auth",
        "Найди узкие места производительности в billing",
        "Какое покрытие тестами у API?",
        "Оцени качество кода в utils",
        "Проанализируй архитектуру приложения",
        "Сложный запрос без явных keywords - нужен глубокий анализ всей системы",
    ]

    print("=" * 80)
    print("HybridClassifier Demo")
    print("=" * 80)

    for i, query in enumerate(test_queries, 1):
        print(f"\n{i}. Query: {query}")
        result = classifier.classify(query)
        print(f"   Method: {result['method']}")
        print(f"   Type: {result['type']}")
        print(f"   Confidence: {result['confidence']:.2f}")
        print(f"   Scope: {result['scope']}")
        print(f"   Tools: {', '.join(result['tools'])}")
        print(f"   Tests: {len(result['tests_to_run'])} found")
        if "rationale" in result:
            print(f"   Rationale: {result['rationale']}")


if __name__ == "__main__":
    main()
