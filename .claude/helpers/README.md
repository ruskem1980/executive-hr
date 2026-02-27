# Claude Flow V3 Helpers — Полная база знаний инструментов

> Последнее обновление: 2026-02-13 (синхронизация из migranthub_g)

## Каталог инструментов (56 файлов)

---

## 1. WORKFLOW & TOKEN ROUTING (Основной pipeline)

### `router.js` — Маршрутизатор задач (6 уровней сложности)
```bash
node .claude/helpers/router.js "описание задачи"
# → {"complexity": "program|trivial|simple|medium|complex|very_complex", "pipeline": [...]}
```
**Уровни:** program (скрипт), trivial (1 строка), simple (1-2 файла), medium (3-5 файлов), complex (6+), very_complex (архитектура)
**ML A/B тестирование:** Интегрирован с `scripts/ml_classify.py` для автоматического обучения

### `workflow-helper.sh` — Главный workflow-хелпер (source-based)
```bash
source .claude/helpers/workflow-helper.sh
workflow_start "описание задачи"          # ШАГ 1+2: router + token_tracker
workflow_record opus classifier 200 50     # ШАГ 3: запись LLM вызовов
workflow_execute_gemini flash "промпт"     # Вызов Gemini
workflow_finish                            # ШАГ 4: отчёт + cleanup
workflow_status                            # Текущий статус
```

### `workflow-start.sh` — Standalone начало workflow (ШАГ 1+2)
```bash
bash .claude/helpers/workflow-start.sh "описание задачи"
# → Создаёт .claude/tracking/current_task (разблокирует Edit/Write)
# → Выводит: Сложность, Task ID, Ожидаемая экономия
```

### `workflow-record.sh` — Standalone запись LLM вызова (ШАГ 3)
```bash
bash .claude/helpers/workflow-record.sh opus classifier 200 50
bash .claude/helpers/workflow-record.sh flash executor 2500 800
```

### `workflow-finish.sh` — Standalone завершение workflow (ШАГ 4)
```bash
bash .claude/helpers/workflow-finish.sh
# → Выводит отчёт о токенах + удаляет маркер current_task
```

### `task-enforcer.sh` — Проверка compliance (4 шага)
```bash
bash .claude/helpers/task-enforcer.sh check $TASK_ID   # ✅/❌ каждый шаг
bash .claude/helpers/task-enforcer.sh verify-before-write  # Проверка перед Edit
bash .claude/helpers/task-enforcer.sh report            # Статус текущей задачи
```

---

## 2. TOKEN TRACKING & ЭКОНОМИЯ

### `token-tracker.py` — Standalone Token Tracker (без зависимостей от src/)
```bash
python3 .claude/helpers/token-tracker.py start "Описание" "simple"   # → TASK_ID
python3 .claude/helpers/token-tracker.py record TASK_ID opus classifier 200 50
python3 .claude/helpers/token-tracker.py finish TASK_ID              # → Отчёт
python3 .claude/helpers/token-tracker.py report --last 5
python3 .claude/helpers/token-tracker.py report --date 2026-02-13
python3 .claude/helpers/token-tracker.py report --total
```
**Цены:** opus $15/$75, sonnet $3/$15, flash $0.50/$3, pro $2/$12 за 1M токенов.
**БД:** `data/token_usage.db` (SQLite)

---

## 3. ЗАЩИТА ДЕЛЕГИРОВАНИЯ

### `delegation-guard.sh` — Защита от нарушения правил делегирования
```bash
bash .claude/helpers/delegation-guard.sh opus direct 50000 10000
# → ❌ БЛОКИРОВКА для medium задач с большими токенами
# → ✅ Разрешено для simple/complex задач
```
**Правило:** Для medium задач opus direct с >10K токенов = БЛОКИРОВКА (~80% потеря экономии)

---

## 4. GEMINI ИНТЕГРАЦИЯ

### `gemini-bridge.sh` — Мост Claude → Gemini CLI (headless)
```bash
bash .claude/helpers/gemini-bridge.sh flash "Промпт с полным контекстом"
bash .claude/helpers/gemini-bridge.sh pro "Промпт для глубокого анализа"
```
**Режим:** headless, --approval-mode yolo, чистый текст

### `gemini-router.sh` — Специализированные задачи через Gemini
```bash
bash .claude/helpers/gemini-router.sh analyze src/module/    # Анализ модуля (Flash)
bash .claude/helpers/gemini-router.sh review src/api.py      # Code review (Flash)
bash .claude/helpers/gemini-router.sh audit src/auth/         # Security аудит (Flash)
bash .claude/helpers/gemini-router.sh docs src/              # Генерация docs (Flash)
bash .claude/helpers/gemini-router.sh bugs src/              # Поиск багов (Flash)
bash .claude/helpers/gemini-router.sh architecture           # Архитектура (Pro)
bash .claude/helpers/gemini-router.sh custom "промпт" path   # Произвольный (Flash)
bash .claude/helpers/gemini-router.sh stats                  # Статистика вызовов
```
**Автоматический fallback:** Flash → Pro → уведомление об Opus при rate limits

### `model-fallback.sh` — Цепочки fallback при rate limits
```bash
bash .claude/helpers/model-fallback.sh get coding           # Лучшая модель для задачи
bash .claude/helpers/model-fallback.sh block gemini-flash 15 # Блокировка на 15мин
bash .claude/helpers/model-fallback.sh unblock sonnet       # Разблокировка
bash .claude/helpers/model-fallback.sh detect "$OUTPUT" flash  # Детекция rate limit
bash .claude/helpers/model-fallback.sh status               # Статус всех моделей
bash .claude/helpers/model-fallback.sh reset                # Сброс блокировок
bash .claude/helpers/model-fallback.sh chain coding         # Цепочка для задачи
```
**Цепочки:** haiku/sonnet → gemini-flash → gemini-pro → opus
**Задачи:** search, docs, tests, analyze, review, audit, coding, refactoring, architecture, security

### `sonnet-bridge.sh` — Мост Claude → Sonnet
```bash
bash .claude/helpers/sonnet-bridge.sh "промпт"
```

---

## 5. ML КЛАССИФИКАЦИЯ (PT_Standart_Agents-эксклюзив)

### `agent-model-router.js` — Маршрутизация модели для агентов
### `agent-selector.js` — ML-основанный выбор агента
### `skill-param-inference.js` — Инференс параметров скиллов
### `skills-detector.js` — Детектор доступных скиллов
### `swarm-decision.js` — Принятие решений в swarm

---

## 6. AGЕНТ МОНИТОРИНГ & SWARM

### `agent-tracker.sh` — Трекинг агентов
```bash
bash .claude/helpers/agent-tracker.sh create "ID" "type" "task" "output_file"
bash .claude/helpers/agent-tracker.sh heartbeat "ID" 5 1000
bash .claude/helpers/agent-tracker.sh complete "ID" "success" "summary"
bash .claude/helpers/agent-tracker.sh cleanup   # Удаление старых (>24ч)
```

### `agent-status-checker.sh` — Проверка статуса агентов
```bash
bash .claude/helpers/agent-status-checker.sh check     # Проверить всех
bash .claude/helpers/agent-status-checker.sh report     # Быстрый отчёт
bash .claude/helpers/agent-status-checker.sh hung       # Зависшие агенты
bash .claude/helpers/agent-status-checker.sh completed   # Завершённые
```

### `swarm-hooks.sh` — Хуки координации swarm
### `swarm-comms.sh` — Коммуникация между агентами
### `swarm-monitor.sh` — Мониторинг swarm

---

## 7. DAEMON & HOOKS

### `daemon-watchdog.sh` — Здоровье демона + очистка stale PID
```bash
bash .claude/helpers/daemon-watchdog.sh check    # Проверка + очистка stale
bash .claude/helpers/daemon-watchdog.sh start    # Запуск hook relay
bash .claude/helpers/daemon-watchdog.sh stop     # Остановка relay
bash .claude/helpers/daemon-watchdog.sh restart  # Перезапуск
bash .claude/helpers/daemon-watchdog.sh status   # Полный статус
```
**Функции:** Очистка zombie PID, убийство orphan процессов, дубликаты MCP

### `daemon-manager.sh` — Управление демоном claude-flow
### `cf-hook.sh` — Быстрый executor хуков (socket relay ~5ms → npx fallback ~2s)
```bash
bash .claude/helpers/cf-hook.sh hooks post-edit --file "path" --success true
# → Приоритет: Unix socket relay (быстро) → npx fallback (медленно)
```

### `learning-hooks.sh` — Хуки самообучения
### `learning-optimizer.sh` — Оптимизация обучения
### `learning-service.mjs` — Сервис обучения (Node.js)
### `guidance-hook.sh` / `guidance-hooks.sh` — Хуки наведения

---

## 8. GIT & GITHUB

### `auto-commit.sh` — Автоматический коммит
### `github-safe.js` — Безопасные GitHub операции
### `github-setup.sh` — Настройка GitHub интеграции
### `pre-commit` / `post-commit` — Git hooks

---

## 9. ИНФРАСТРУКТУРА & МОНИТОРИНГ

### `health-monitor.sh` — Мониторинг здоровья системы
### `statusline.js` / `statusline.cjs` — Статусная строка
### `statusline-hook.sh` — Хук статусной строки
### `metrics-db.mjs` — БД метрик (Node.js)
### `memory.js` / `session.js` — Память и сессии
### `checkpoint-manager.sh` — Управление чекпоинтами
### `standard-checkpoint-hooks.sh` — Стандартные хуки чекпоинтов

---

## 10. V3 СПЕЦИФИЧЕСКИЕ

### `v3.sh` — Основной CLI для V3
```bash
.claude/helpers/v3.sh help       # Все команды
.claude/helpers/v3.sh status     # Статус разработки
.claude/helpers/v3.sh validate   # Валидация конфигурации
```

### `update-v3-progress.sh` — Обновление прогресса V3
### `v3-quick-status.sh` — Быстрый статус V3
### `validate-v3-config.sh` — Валидация конфигурации
### `sync-v3-metrics.sh` — Синхронизация метрик V3
### `adr-compliance.sh` — Проверка соответствия ADR
### `ddd-tracker.sh` — Трекер DDD
### `perf-worker.sh` — Performance worker
### `worker-manager.sh` — Управление воркерами
### `security-scanner.sh` — Сканер безопасности
### `pattern-consolidator.sh` — Консолидация паттернов
### `setup-mcp.sh` / `quick-start.sh` — Быстрая настройка

---

## 11. SCRIPTS (Python утилиты)

### `scripts/git_auto_save.py` — Авто-коммит + пуш при каждом Write/Edit
```bash
python3 scripts/git_auto_save.py                   # Все изменения
python3 scripts/git_auto_save.py --file src/main.py # Конкретный файл
python3 scripts/git_auto_save.py --no-push          # Без пуша
python3 scripts/git_auto_save.py --check            # Проверка
```

### `scripts/sync_back.py` — Синхронизация в PT_Standart
```bash
python3 scripts/sync_back.py --dry-run  # Что синхронизируется
python3 scripts/sync_back.py --auto     # Синхронизировать всё
python3 scripts/sync_back.py --file src/reporting/new_tool.py
```

### `scripts/ml_classify.py` — ML классификатор (используется router.js)
```bash
python3 scripts/ml_classify.py "описание задачи"
# → {"complexity": "medium", "confidence": 0.85, ...}
```

### `scripts/train_ml_models.py` — Обучение ML моделей классификации

---

## Правила применения (ОБЯЗАТЕЛЬНО)

### Для КАЖДОЙ задачи с кодом:
```
1. router.js → определить сложность
2. token-tracker → начать трекинг
3. program/simple/medium → Gemini, complex → Opus напрямую
4. token-tracker → отчёт с экономией
```

### Цепочки fallback при rate limits:
```
Claude (haiku/sonnet) → Gemini Flash → Gemini Pro → Opus
```

### Delegation Guard:
```
medium + opus direct + >10K токенов → БЛОКИРОВКА
simple → Opus разрешён
complex → Opus разрешён
```
