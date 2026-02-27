#!/usr/bin/env bash
# workflow_test_example.sh — Тестовый пример использования обязательного workflow
# Демонстрирует правильное выполнение задачи с соблюдением всех правил
#
# Использование: bash scripts/workflow_test_example.sh
# Все комментарии на русском

set -euo pipefail

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🧪 ТЕСТОВЫЙ ПРИМЕР: Обязательный workflow для задач с кодом"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""

# Подключаем workflow-helper
source .claude/helpers/workflow-helper.sh

# ═════════════════════════════════════════════════════════════════════
# ПРИМЕР: Добавить функцию проверки email в validators.py
# Сложность: simple (1 файл, простая функция)
# ═════════════════════════════════════════════════════════════════════

TASK_DESC="Добавить функцию validate_email в src/validators.py"

# ШАГ 1 + ШАГ 2: Начало workflow
echo "┌─────────────────────────────────────────────────────────────────┐"
echo "│ ШАГ 1+2: Классификация + начало трекинга                        │"
echo "└─────────────────────────────────────────────────────────────────┘"
workflow_start "$TASK_DESC"
echo ""

# Сохраняем переменные для дальнейшего использования
TASK_ID="$WORKFLOW_TASK_ID"
COMPLEXITY="$WORKFLOW_COMPLEXITY"

echo "Результат классификации:"
echo "  Task ID: $TASK_ID"
echo "  Сложность: $COMPLEXITY"
echo ""

# ШАГ 3: Выполнение (эмуляция)
echo "┌─────────────────────────────────────────────────────────────────┐"
echo "│ ШАГ 3: Выполнение задачи                                        │"
echo "└─────────────────────────────────────────────────────────────────┘"
echo ""

if [[ "$COMPLEXITY" == "simple" ]] || [[ "$COMPLEXITY" == "medium" ]]; then
  echo "➤ Сложность $COMPLEXITY → маршрутизация через Gemini Flash"
  echo ""

  # 3.1 Opus классификация (эмуляция)
  echo "  1. Opus классификация (оценка задачи)..."
  workflow_record opus classifier 180 40
  echo "     ✅ Записано: opus/classifier - 180 in, 40 out"
  echo ""

  # 3.2 Чтение файла (эмуляция)
  echo "  2. Чтение src/validators.py через Read..."
  echo "     (эмуляция чтения файла)"
  echo ""

  # 3.3 Gemini Flash выполнение (эмуляция)
  echo "  3. Gemini Flash - реализация кода..."
  echo "     Промпт: \"Добавь validate_email() с проверкой @ и точки\""
  # В реальности здесь был бы вызов:
  # FLASH_CODE=$(workflow_execute_gemini flash "промпт с контекстом")
  echo "     (эмуляция выполнения Flash)"
  workflow_record flash executor 2200 650
  echo "     ✅ Записано: flash/executor - 2200 in, 650 out"
  echo ""

  # 3.4 Opus валидация (эмуляция)
  echo "  4. Opus валидация результата..."
  echo "     Проверка: корректность, безопасность, стиль"
  workflow_record opus validator 800 150
  echo "     ✅ Записано: opus/validator - 800 in, 150 out"
  echo ""

  # 3.5 Применение кода (эмуляция)
  echo "  5. Применение кода через Edit..."
  echo "     (эмуляция Edit/Write)"
  echo ""

elif [[ "$COMPLEXITY" == "complex" ]]; then
  echo "➤ Сложность complex → Opus работает напрямую"
  echo ""

  # Opus direct execution (эмуляция)
  echo "  1. Opus прямое выполнение..."
  workflow_record opus direct 8000 3500
  echo "     ✅ Записано: opus/direct - 8000 in, 3500 out"
  echo ""
fi

# ШАГ 4: Завершение и отчёт
echo "┌─────────────────────────────────────────────────────────────────┐"
echo "│ ШАГ 4: Завершение и отчёт о расходе токенов                     │"
echo "└─────────────────────────────────────────────────────────────────┘"
echo ""
workflow_finish

# Проверка compliance
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "🔍 ПРОВЕРКА СОБЛЮДЕНИЯ ПРАВИЛ"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
bash .claude/helpers/task-enforcer.sh check "$TASK_ID"

echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✅ ТЕСТ ЗАВЕРШЁН УСПЕШНО"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "Этот пример демонстрирует правильное выполнение workflow:"
echo "  ✅ ШАГ 1: router.js классификация"
echo "  ✅ ШАГ 2: token_tracker.start_task"
echo "  ✅ ШАГ 3: Выполнение с record_call для каждого LLM"
echo "  ✅ ШАГ 4: finish_task + print_task_summary (отчёт)"
echo ""
echo "Все 4 шага выполнены → задача завершена корректно."
echo ""
