# Main Workflow - Intelligent Code Analysis System

Главный workflow системы интеллектуальной предобработки PT_Standart.

## 🎯 Назначение

Обрабатывает запросы пользователя с использованием:
1. **Автоматической классификации** - определяет тип задачи
2. **Умной предобработки** - запускает специализированные инструменты
3. **Маршрутизации на модели** - выбирает оптимальную LLM модель по сложности
4. **Экономии токенов** - до 95% экономии по сравнению с прямым вызовом Opus

## 📊 Архитектура

```
User Query
    ↓
[HybridClassifier] → определяет тип запроса (security/performance/etc)
    ↓
[SmartExecutor] → запускает специализированные инструменты (bandit/pylint/etc)
    ↓
[HybridReportAggregator] → создает компактный отчет
    ↓
[determine_complexity] → оценивает сложность (SIMPLE/MEDIUM/COMPLEX)
    ↓
[select_model] → выбирает модель (flash/pro/opus)
    ↓
[build_llm_prompt] → строит оптимальный промпт с контекстом
    ↓
[GeminiBridge] → вызывает Gemini API через CLI
    ↓
LLM Response + Metrics
```

## 🚀 Использование

### CLI Interface

```bash
# Базовое использование
python src/main_workflow.py "проверь безопасность auth модуля"

# С указанием проекта
python src/main_workflow.py "оптимизируй производительность API" --project-root /path/to/project

# Quiet режим (без промежуточных шагов)
python src/main_workflow.py "найди баги в queries.py" --quiet

# JSON output
python src/main_workflow.py "улучши тестовое покрытие" --json
```

### Programmatic Interface

```python
from pathlib import Path
from main_workflow import handle_user_request

# Запуск workflow
response, metrics = handle_user_request(
    user_query="Найди уязвимости безопасности",
    project_root=Path("/path/to/project"),
    verbose=True
)

print(f"Response: {response}")
print(f"Tokens used: {metrics['total_tokens']}")
print(f"Model: {metrics['model']}")
print(f"Savings: {metrics['token_savings_percent']}%")
```

## 🎯 Маршрутизация Моделей

### Правила Сложности

| Сложность | Критерии | Модель | Стоимость |
|-----------|----------|--------|-----------|
| **SIMPLE** | 1-2 проблемы, все LOW/MEDIUM | `flash` | $0.50/$3.00 per 1M |
| **MEDIUM** | 3-10 проблем или есть HIGH | `pro` | $2.00/$12.00 per 1M |
| **COMPLEX** | >10 проблем или есть CRITICAL | `pro` | $2.00/$12.00 per 1M |

**Примечание**: Для критически сложных задач можно использовать Opus напрямую (без workflow), но это требует отдельной интеграции.

### Пример Маршрутизации

```python
# Input: "проверь безопасность auth"
# → Classifier: RequestType.SECURITY
# → Executor: запускает bandit, semgrep, safety
# → Aggregator: находит 2 CRITICAL issues
# → Complexity: COMPLEX (критичные проблемы)
# → Model: opus (сложная задача требует лучшей модели)
```

## 📦 Компоненты

### 1. HybridClassifier

Классифицирует запросы пользователя по типам:
- SECURITY - уязвимости, CVE, injection
- PERFORMANCE - оптимизация, профилирование
- REFACTORING - улучшение кода, паттерны
- DEBUGGING - поиск багов, исправление
- TESTING - покрытие тестами, unittest
- DOCUMENTATION - docstrings, README
- ARCHITECTURE - структура, модули

```python
classifier = HybridClassifier()
classification = classifier.classify("найди SQL injection")

# Result:
# {
#   "primary_type": RequestType.SECURITY,
#   "confidence": 0.85,
#   "tools": ["bandit", "semgrep", "safety"],
#   "scope": "module",
#   "keywords": ["SQL", "inject"]
# }
```

### 2. SmartExecutor

Запускает специализированные инструменты анализа:
- `bandit` - security scanner
- `pylint` - code quality
- `radon` - complexity metrics
- `pytest` - test runner
- `coverage` - test coverage

```python
executor = SmartExecutor(project_root)
results = executor.execute(classification)

# Result:
# {
#   "issues": [
#     {
#       "type": "SQL_INJECTION",
#       "severity": "HIGH",
#       "file": "queries.py",
#       "line": 42,
#       "suggestion": "Use parameterized queries"
#     }
#   ],
#   "metrics": {
#     "execution_time_ms": 1234,
#     "files_scanned": 45
#   }
# }
```

### 3. HybridReportAggregator

Создает компактный отчет для LLM:

```python
aggregator = HybridReportAggregator()
report = aggregator.aggregate(classification, results)

# Result:
# Report(
#   summary="Found 5 issues, including 2 CRITICAL",
#   issues=[...],
#   metrics={...},
#   recommendations=["Address CRITICAL issues immediately"],
#   total_issues=5,
#   critical_issues=2
# )
```

### 4. GeminiBridge

Вызывает Gemini API через CLI скрипт:

```python
bridge = GeminiBridge()
response = bridge.call(model="flash", prompt="...")

# Использует: .claude/helpers/gemini-bridge.sh
# Формат: bash gemini-bridge.sh flash "prompt text"
```

## 📊 Метрики и Экономия

### Пример Output

```json
{
  "response": "LLM analysis...",
  "metrics": {
    "report_tokens": 342,
    "prompt_tokens": 1234,
    "response_tokens": 567,
    "total_tokens": 1801,
    "complexity": "MEDIUM",
    "model": "pro",
    "total_time_seconds": 2.34,
    "token_savings_percent": 96.4
  }
}
```

### Сравнение Подходов

| Подход | Токены | Стоимость (in) | Экономия |
|--------|--------|----------------|----------|
| **Прямой вызов Opus** на весь проект | ~50,000 | $0.75 | - |
| **Intelligent Workflow** (Flash) | ~1,800 | $0.001 | 96.4% |
| **Intelligent Workflow** (Pro) | ~2,500 | $0.005 | 95.0% |
| **Intelligent Workflow** (Opus) | ~10,000 | $0.15 | 80.0% |

## 🧪 Тестирование

```bash
# Запуск тестов
python src/test_workflow.py

# Ожидаемый output:
# TEST 1: SECURITY QUERY → model: pro/opus
# TEST 2: PERFORMANCE QUERY → model: pro/opus
# TEST 3: SIMPLE QUERY → model: flash
# TEST 4: QUIET MODE → minimal output
```

## 🔧 Конфигурация

### Переменные Окружения

```bash
# Gemini API Key (опционально, если используете gemini-bridge.sh)
export GOOGLE_API_KEY="your-key-here"

# Project root (по умолчанию: текущая директория)
export PT_STANDART_ROOT="/path/to/project"
```

### Настройка gemini-bridge.sh

Убедитесь, что скрипт `.claude/helpers/gemini-bridge.sh` существует и настроен:

```bash
# Проверка
ls -la .claude/helpers/gemini-bridge.sh

# Должен быть исполняемым
chmod +x .claude/helpers/gemini-bridge.sh
```

## 📝 Примеры Запросов

### Security

```bash
python src/main_workflow.py "найди уязвимости безопасности в authentication модуле"
python src/main_workflow.py "проверь на SQL injection в database/queries.py"
python src/main_workflow.py "есть ли hardcoded secrets в config файлах?"
```

### Performance

```bash
python src/main_workflow.py "оптимизируй производительность API endpoints"
python src/main_workflow.py "найди медленные функции с высокой сложностью"
python src/main_workflow.py "проверь memory leaks в cache manager"
```

### Refactoring

```bash
python src/main_workflow.py "улучши код в utils модуле, убери дублирование"
python src/main_workflow.py "найди code smells и предложи рефакторинг"
python src/main_workflow.py "применить SOLID принципы к service классам"
```

### Testing

```bash
python src/main_workflow.py "улучши тестовое покрытие для API handlers"
python src/main_workflow.py "найди недостающие unit tests"
python src/main_workflow.py "проверь quality тестов с помощью mutation testing"
```

## 🚧 Ограничения Текущей Версии

### Mock Компоненты

Текущая версия использует **mock данные** для демонстрации:
- `SmartExecutor` возвращает предзаданные проблемы
- `GeminiBridge` может использовать mock ответ, если gemini-bridge.sh не найден

### Интеграция с Реальными Инструментами

Для production использования нужно добавить:
1. Реальные вызовы `bandit`, `pylint`, `radon`, etc
2. Parsing их output в структурированный формат
3. Error handling для сбоя инструментов
4. Caching результатов анализа

## 🔮 Roadmap

### Phase 1 (Текущая версия)
- ✅ Полный workflow pipeline
- ✅ Маршрутизация на модели
- ✅ CLI interface
- ✅ Mock данные для демонстрации

### Phase 2
- ⬜ Интеграция реальных инструментов (bandit, pylint, radon)
- ⬜ Caching и incremental analysis
- ⬜ Multi-project support

### Phase 3
- ⬜ Web UI dashboard
- ⬜ Real-time monitoring
- ⬜ Team collaboration features

## 📚 Связанная Документация

- [Intelligent Preprocessing System](../docs/intelligent-preprocessing-system.md)
- [Hybrid Test Execution Strategy](../docs/hybrid-test-execution-strategy.md)
- [Self-Improving Test Ecosystem](../docs/self-improving-test-ecosystem.md)

## 🤝 Contributing

См. основной CONTRIBUTING.md проекта.

## 📄 License

См. основной LICENSE файл проекта.
