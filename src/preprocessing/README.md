# HybridClassifier - Гибридный Классификатор Запросов

## Описание

HybridClassifier реализует двухступенчатую систему классификации пользовательских запросов:

1. **Keyword-based классификация** - быстрый метод с расчетом confidence score
2. **LLM fallback** - использование Gemini Flash для сложных случаев (confidence < 0.7)

## Категории Классификации

| Категория | Описание | Инструменты |
|-----------|----------|-------------|
| `SECURITY` | Безопасность, уязвимости, аудит | bandit, safety, semgrep |
| `PERFORMANCE` | Производительность, оптимизация | cProfile, memory_profiler, py-spy |
| `QUALITY` | Качество кода, рефакторинг | radon, pylint, flake8 |
| `COVERAGE` | Покрытие тестами | coverage, pytest-cov |
| `ARCHITECTURE` | Архитектура, дизайн | pydeps, mccabe |
| `DOCUMENTATION` | Документация, docstrings | pydocstyle, interrogate |
| `GENERAL` | Общие запросы | - |

## Использование

### Базовый пример

```python
from preprocessing import HybridClassifier

classifier = HybridClassifier()

# Классификация запроса
result = classifier.classify("Проверь безопасность модуля auth")

print(f"Type: {result['type']}")           # SECURITY
print(f"Confidence: {result['confidence']}")  # 0.85
print(f"Method: {result['method']}")       # keyword
print(f"Tools: {result['tools']}")         # ['bandit', 'safety', 'semgrep']
print(f"Scope: {result['scope']}")         # src/auth/
print(f"Tests: {result['tests_to_run']}")  # [список pytest тестов]
```

### Настройка порога confidence

```python
# Изменить порог для fallback на LLM (по умолчанию 0.7)
classifier = HybridClassifier(confidence_threshold=0.8)
```

### Примеры запросов

#### Высокий confidence (keyword-based)

```python
queries = [
    "Найди уязвимости SQL injection в billing",     # SECURITY
    "Оптимизируй медленные запросы к базе",         # PERFORMANCE
    "Оцени качество кода в utils",                  # QUALITY
    "Какое покрытие тестами у API?",                # COVERAGE
]
```

#### Низкий confidence (LLM fallback)

```python
complex_queries = [
    "Сделай глубокий анализ всей системы",
    "Проверь всё что можно проверить",
    "Нужен комплексный обзор состояния кода",
]
```

## Структура результата

```python
{
    "method": "keyword" | "llm" | "keyword_fallback",
    "confidence": 0.0-1.0,
    "type": "SECURITY" | "PERFORMANCE" | ...,
    "tests_to_run": ["tests/unit/auth/test_security.py::test_password", ...],
    "tools": ["bandit", "safety", ...],
    "scope": "src/auth/",
    "rationale": "1 sentence why"  # Только для LLM метода
}
```

## Как это работает

### 1. Keyword Classification

1. Запрос сравнивается с keywords каждой категории
2. Подсчитываются взвешенные совпадения
3. Вычисляется normalized score
4. Confidence = score × (1 + 0.1 × num_matches)
5. Если confidence ≥ 0.7 → возврат результата

### 2. LLM Fallback (confidence < 0.7)

1. Формируется промпт для Gemini Flash
2. LLM анализирует запрос и возвращает JSON
3. Парсинг и валидация ответа
4. Поиск релевантных тестов
5. Возврат результата с confidence = 1.0

### 3. Извлечение Scope

Автоматически определяет область анализа из запроса:

- Файлы: `auth.py` → `src/auth.py`
- Директории: `billing/` → `src/billing/`
- Модули: `"модуль auth"` → `src/auth/`
- По умолчанию: `src/`

### 4. Поиск Тестов

Использует `pytest --collect-only -k <pattern>` для поиска релевантных тестов без их выполнения.

## Демонстрация

```bash
# Запуск демо скрипта
python examples/test_hybrid_classifier.py

# Запуск встроенного main()
python -m src.preprocessing.hybrid_classifier
```

## Зависимости

### Обязательные
- Python 3.8+
- pytest (для поиска тестов)

### Для LLM fallback
- `gemini_bridge.py` - интеграция с Gemini Flash

## Интеграция

### Gemini Bridge

Для работы LLM fallback требуется `gemini_bridge.py`:

```python
# src/preprocessing/gemini_bridge.py

class GeminiBridge:
    def call(self, model: str, prompt: str) -> str:
        """
        Вызов Gemini API.

        Args:
            model: "flash" | "pro"
            prompt: Промпт для модели

        Returns:
            str: Ответ модели
        """
        # Реализация вызова Gemini API
        pass
```

## Performance

- **Keyword classification**: < 1ms
- **LLM fallback**: ~500-1000ms (зависит от Gemini API)
- **Поиск тестов**: ~100-500ms (зависит от размера тестовой базы)

## Error Handling

Классификатор обрабатывает следующие edge cases:

1. **Пустой запрос** → `GENERAL` с confidence 0.0
2. **LLM API недоступен** → fallback на keyword результат
3. **pytest не установлен** → пустой список тестов
4. **Некорректный JSON от LLM** → exception с fallback

## Тестирование

```bash
# Запуск unit тестов (если созданы)
pytest tests/unit/test_hybrid_classifier.py -v

# Запуск integration тестов
pytest tests/integration/test_hybrid_classifier.py -v
```

## Дальнейшее Развитие

- [ ] Добавить кэширование результатов классификации
- [ ] Реализовать batch классификацию
- [ ] Добавить метрики accuracy для keyword vs LLM
- [ ] Интеграция с другими LLM (OpenAI, Anthropic)
- [ ] Автоматическое обучение весов keywords
- [ ] Support для multilingual queries

## Лицензия

Часть PT_Standart проекта. См. LICENSE.

## Автор

Claude Code (PT_Standart Implementation)
