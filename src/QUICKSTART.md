# Quick Start Guide - Main Workflow

## 🚀 Быстрый Старт

### 1. Установка Зависимостей

```bash
# Опционально: tiktoken для точного подсчета токенов
pip install tiktoken
```

### 2. Базовое Использование

```bash
# С mock данными (для демонстрации)
python src/main_workflow.py "найди уязвимости безопасности" --mock

# С реальным Gemini API (требует настройки)
python src/main_workflow.py "оптимизируй производительность API"
```

### 3. Quick Wrapper

```bash
python src/analyze.py "твой запрос"
```

### 4. Запуск Демонстрации

```bash
python src/demo.py
```

## 📊 Примеры Запросов

### Security
```bash
python src/main_workflow.py "найди SQL injection уязвимости" --mock
python src/main_workflow.py "проверь безопасность auth модуля" --mock
python src/main_workflow.py "есть ли hardcoded secrets?" --mock
```

### Performance
```bash
python src/main_workflow.py "оптимизируй медленные функции" --mock
python src/main_workflow.py "найди memory leaks" --mock
python src/main_workflow.py "профайл API endpoints" --mock
```

### Refactoring
```bash
python src/main_workflow.py "улучши код в utils.py" --mock
python src/main_workflow.py "примени SOLID принципы" --mock
python src/main_workflow.py "найди code smells" --mock
```

### Testing
```bash
python src/main_workflow.py "улучши test coverage" --mock
python src/main_workflow.py "найди недостающие тесты" --mock
```

## 🎯 Ожидаемые Результаты

### Пример Output

```
======================================================================
🚀 Starting workflow for query: 'найди уязвимости безопасности'
======================================================================

📊 Step 1: Classification...
   Type: security
   Confidence: 0.60
   Tools: bandit, semgrep, safety
   Scope: module

🔧 Step 2: Executing tools...
   Issues found: 2
   Execution time: 1234ms

📄 Step 3: Aggregating report...
   Summary: Found 2 issues, including 1 CRITICAL
   Report size: 155 tokens

🎯 Step 4: Determining complexity...
   Complexity: COMPLEX

🤖 Step 5: Selecting model...
   Selected model: pro
   Cost: $2.00/$12.00 per 1M tokens

✍️  Step 6: Building LLM prompt...
   Prompt size: 431 tokens

🧠 Step 7: Calling LLM...
   Response size: 397 tokens

======================================================================
✅ Workflow completed in 0.07s
======================================================================

📊 Metrics:
   Total tokens: 828
   Estimated savings vs full Opus scan: 98.3%
   Model used: pro
   Complexity: COMPLEX
```

## 🔧 Опции CLI

| Флаг | Описание |
|------|----------|
| `--mock` | Использовать mock ответы (для тестирования) |
| `--quiet` | Не показывать промежуточные шаги |
| `--json` | Вывод в JSON формате |
| `--project-root PATH` | Указать корневую директорию проекта |

## 📈 Метрики

### Token Savings

| Сценарий | Модель | Tokens | Savings |
|----------|--------|--------|---------|
| Simple task | flash | ~1K | 98% |
| Medium task | pro | ~2.5K | 95% |
| Complex task | pro | ~10K | 80% |

### Model Selection

| Complexity | Критерии | Модель |
|------------|----------|--------|
| SIMPLE | 1-2 проблемы, все LOW/MEDIUM | flash |
| MEDIUM | 3-10 проблем или есть HIGH | pro |
| COMPLEX | >10 проблем или есть CRITICAL | pro |

## 🧪 Тестирование

```bash
# Запустить тестовый скрипт
python src/test_workflow.py

# Запустить все демонстрации
python src/demo.py
```

## 🔗 Интеграция с Gemini

### Настройка gemini-bridge.sh

1. Убедитесь, что установлен `gemini` CLI:
```bash
which gemini
# Должно вернуть путь к gemini
```

2. Проверьте скрипт:
```bash
ls -la .claude/helpers/gemini-bridge.sh
# Должен существовать и быть исполняемым
```

3. Тестовый вызов:
```bash
bash .claude/helpers/gemini-bridge.sh flash "test prompt"
```

### Без Gemini API

Если `gemini` CLI недоступен, workflow автоматически использует mock ответы:

```bash
# Автоматический fallback на mock
python src/main_workflow.py "твой запрос"
```

## 📝 Программное Использование

```python
from pathlib import Path
from main_workflow import handle_user_request

# Запуск workflow
response, metrics = handle_user_request(
    user_query="найди уязвимости",
    project_root=Path("/path/to/project"),
    verbose=True,
    use_mock=True  # или False для реального API
)

# Результаты
print(f"Response: {response}")
print(f"Model: {metrics['model']}")
print(f"Tokens: {metrics['total_tokens']}")
print(f"Savings: {metrics['token_savings_percent']}%")
print(f"Time: {metrics['total_time_seconds']}s")
```

## 🐛 Troubleshooting

### "ModuleNotFoundError: No module named 'tiktoken'"

```bash
pip install tiktoken
```

Или workflow будет использовать простую аппроксимацию токенов.

### "gemini CLI not found"

Workflow автоматически переключится на mock режим. Для реальных вызовов:

1. Установите gemini CLI
2. Настройте GOOGLE_API_KEY
3. Проверьте доступность: `which gemini`

### "Error calling Gemini: timeout"

```bash
# Используйте mock режим для тестирования
python src/main_workflow.py "query" --mock
```

## 📚 Документация

- [WORKFLOW_README.md](./WORKFLOW_README.md) - Полная документация
- [IMPLEMENTATION_SUMMARY.md](./IMPLEMENTATION_SUMMARY.md) - Техническое резюме
- [../docs/intelligent-preprocessing-system.md](../docs/intelligent-preprocessing-system.md) - Спецификация

## 🎓 Примеры Use Cases

### Use Case 1: Security Audit

```bash
python src/main_workflow.py \
  "проведи полный security audit authentication модуля" \
  --project-root /path/to/project
```

**Результат:**
- Автоматический запуск bandit, semgrep, safety
- Агрегация найденных уязвимостей
- Приоритизация по критичности
- Конкретные рекомендации по исправлению
- Примеры кода

### Use Case 2: Performance Optimization

```bash
python src/main_workflow.py \
  "найди и оптимизируй медленные API endpoints" \
  --project-root /path/to/project
```

**Результат:**
- Профилирование кода
- Анализ сложности алгоритмов
- Выявление memory leaks
- Рекомендации по оптимизации
- Примеры улучшенного кода

### Use Case 3: Code Quality Improvement

```bash
python src/main_workflow.py \
  "улучши качество кода и примени best practices" \
  --project-root /path/to/project
```

**Результат:**
- Анализ code smells
- Проверка соблюдения SOLID
- Выявление дублирования
- Рекомендации по рефакторингу
- Примеры паттернов

## 💡 Pro Tips

1. **Используйте --mock для быстрого тестирования**
   ```bash
   python src/main_workflow.py "query" --mock --quiet
   ```

2. **Комбинируйте с jq для парсинга JSON**
   ```bash
   python src/main_workflow.py "query" --json --mock | jq '.metrics.total_tokens'
   ```

3. **Создайте alias для удобства**
   ```bash
   alias analyze='python /path/to/src/analyze.py'
   analyze "найди баги"
   ```

4. **Используйте в CI/CD pipeline**
   ```yaml
   - name: Security Analysis
     run: |
       python src/main_workflow.py \
         "security audit" \
         --json \
         --project-root . \
         > security-report.json
   ```

## 🚀 Следующие Шаги

1. Запустите `python src/demo.py` для полной демонстрации
2. Попробуйте разные типы запросов
3. Изучите метрики экономии токенов
4. Интегрируйте в свой workflow
5. Добавьте реальные инструменты анализа (см. Phase 2 в IMPLEMENTATION_SUMMARY.md)

## 📞 Support

См. основную документацию проекта в `/docs` директории.
