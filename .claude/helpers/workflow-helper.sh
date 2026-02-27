#!/usr/bin/env bash
# workflow-helper.sh — Автоматизация обязательного workflow
# Использование: source .claude/helpers/workflow-helper.sh
#
# Экспортирует функции для Claude Code:
# - workflow_start "задача"     → ШАГ 1 + ШАГ 2 (router + token tracker start)
# - workflow_record model role input_tokens output_tokens  → ШАГ 3 (record_call)
# - workflow_finish             → ШАГ 4 (finish + отчёт)
#
# Все комментарии на русском

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TRACKING_DIR="$PROJECT_ROOT/.claude/tracking"

# Глобальные переменные для workflow
export WORKFLOW_TASK_ID=""
export WORKFLOW_COMPLEXITY=""
export WORKFLOW_PIPELINE=""

# ШАГ 1 + ШАГ 2: Начало workflow (router.js + token_tracker.start_task)
workflow_start() {
  local task_description="$1"

  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "🚀 НАЧАЛО WORKFLOW"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  # ШАГ 1: Классификация через router.js
  echo "ШАГ 1: Классификация сложности (router.js)..."
  local route_result=$(node "$SCRIPT_DIR/router.js" "$task_description")

  WORKFLOW_COMPLEXITY=$(echo "$route_result" | jq -r '.complexity')
  WORKFLOW_PIPELINE=$(echo "$route_result" | jq -c '.pipeline')
  local estimated_saving=$(echo "$route_result" | jq -r '.estimatedCostReduction')

  echo "  Сложность: $WORKFLOW_COMPLEXITY"
  echo "  Ожидаемая экономия: $estimated_saving"
  echo "  Pipeline: $WORKFLOW_PIPELINE"
  echo ""

  # ШАГ 2: Начало трекинга токенов (standalone token-tracker.py)
  echo "ШАГ 2: Начало трекинга токенов..."
  WORKFLOW_TASK_ID=$(python3 "$SCRIPT_DIR/token-tracker.py" start "$task_description" "$WORKFLOW_COMPLEXITY")

  echo "  Task ID: $WORKFLOW_TASK_ID"
  echo ""

  # Создаём tracking-файл для enforcer (JSON формат)
  mkdir -p "$TRACKING_DIR"
  cat <<EOF > "$TRACKING_DIR/task_$WORKFLOW_TASK_ID"
{
  "task_id": "$WORKFLOW_TASK_ID",
  "description": "$task_description",
  "complexity": "$WORKFLOW_COMPLEXITY",
  "pipeline": $WORKFLOW_PIPELINE,
  "executed_steps": []
}
EOF

  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "✅ Workflow начат. Можно приступать к выполнению."
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  # Экспортируем переменные для использования в сессии
  export WORKFLOW_TASK_ID
  export WORKFLOW_COMPLEXITY
  export WORKFLOW_PIPELINE
}

# ШАГ 3: Запись вызова LLM (record_call)
workflow_record() {
  local model="$1"
  local role="$2"
  local input_tokens="$3"
  local output_tokens="$4"
  local RED='\033[0;31m'
  local NC='\033[0m'

  if [[ -z "$WORKFLOW_TASK_ID" ]]; then
    echo -e "${RED}❌ ОШИБКА: workflow_start не был вызван${NC}"
    echo "   Сначала вызови: workflow_start \"описание задачи\""
    exit 1
  fi

  local tracking_file="$TRACKING_DIR/task_$WORKFLOW_TASK_ID"

  # Проверка соответствия pipeline (если файл в JSON формате)
  if [[ -f "$tracking_file" ]]; then
    local content=$(cat "$tracking_file")
    if [[ "$content" == "{"* ]]; then
      local step_index=$(echo "$content" | jq '.executed_steps | length')
      local expected_model=$(echo "$content" | jq -r ".pipeline[$step_index].model // empty")

      if [[ -n "$expected_model" ]]; then
        # Приводим к нижнему регистру для гибкого сравнения (например, opus vs claude-3-opus)
        local model_lower=$(echo "$model" | tr '[:upper:]' '[:lower:]')
        local expected_lower=$(echo "$expected_model" | tr '[:upper:]' '[:lower:]')

        if [[ "$model_lower" != *"$expected_lower"* ]]; then
          echo -e "${RED}⚠️  НАРУШЕНИЕ PIPELINE!${NC}"
          echo -e "${RED}Ожидалась модель: $expected_model, использована: $model${NC}"
        fi
      fi

      # Добавляем выполненный шаг в executed_steps
      local updated_content=$(echo "$content" | jq --arg m "$model" --arg r "$role" '.executed_steps += [{"model": $m, "role": $r}]')
      echo "$updated_content" > "$tracking_file"
    fi
  fi

  echo "📊 Запись вызова: $model ($role) - in:$input_tokens out:$output_tokens"

  python3 "$SCRIPT_DIR/token-tracker.py" record "$WORKFLOW_TASK_ID" "$model" "$role" "$input_tokens" "$output_tokens"
}

# ШАГ 4: Завершение workflow (finish + отчёт)
workflow_finish() {
  local RED='\033[0;31m'
  local NC='\033[0m'

  if [[ -z "$WORKFLOW_TASK_ID" ]]; then
    echo -e "${RED}❌ ОШИБКА: workflow_start не был вызван${NC}"
    exit 1
  fi

  local tracking_file="$TRACKING_DIR/task_$WORKFLOW_TASK_ID"

  # Получаем описание задачи для LearningLibrary (экранируем кавычки)
  local task_description_escaped=""
  if [[ -f "$tracking_file" ]]; then
    task_description_escaped=$(cat "$tracking_file" | jq -r '.description // ""' | sed "s/'/\\\\'/g")
  fi

  # Проверка выполнения всех шагов pipeline (если файл в JSON формате)
  if [[ -f "$tracking_file" ]]; then
    local content=$(cat "$tracking_file")
    if [[ "$content" == "{"* ]]; then
      local pipeline_len=$(echo "$content" | jq '.pipeline | length')
      local executed_len=$(echo "$content" | jq '.executed_steps | length')

      if [[ $executed_len -lt $pipeline_len ]]; then
        echo -e "${RED}⚠️  ПРЕДУПРЕЖДЕНИЕ: Выполнены не все шаги pipeline ($executed_len из $pipeline_len)${NC}"
      fi
    fi
  fi

  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "🏁 ЗАВЕРШЕНИЕ WORKFLOW"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  python3 "$SCRIPT_DIR/token-tracker.py" finish "$WORKFLOW_TASK_ID"

  # Удаляем tracking-файл
  rm -f "$tracking_file"

  # Очищаем переменные
  export WORKFLOW_TASK_ID=""
  export WORKFLOW_COMPLEXITY=""
  export WORKFLOW_PIPELINE=""

  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "✅ Workflow завершён. Задача выполнена."
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo ""

  # LearningLibrary: сохраняем паттерн завершённой задачи для обучения
  # Запускается фоново, не блокируя workflow
  (python3 -c "
try:
    from src.ml.learning_library import LearningLibrary
    lib = LearningLibrary()
    lib.add_pattern(
        task_id='$WORKFLOW_TASK_ID',
        description='$task_description_escaped',
        solution='complexity=$WORKFLOW_COMPLEXITY',
        metadata={'complexity': '$WORKFLOW_COMPLEXITY', 'success_score': 1.0}
    )
except Exception:
    pass  # LearningLibrary опциональна
" 2>/dev/null &) || true

  # Auto-retrain: проверяем, нужно ли переобучить модели
  # Запускается фоново, не блокируя workflow
  (python3 "$PROJECT_ROOT/scripts/auto_retrain.py" --threshold 20 2>/dev/null &) || true
}

# Вспомогательная функция: исполнение через Gemini (для simple/medium)
workflow_execute_gemini() {
  local model_alias="$1"  # flash или pro
  local prompt="$2"

  if [[ -z "$WORKFLOW_TASK_ID" ]]; then
    echo "❌ ОШИБКА: workflow_start не был вызван"
    exit 1
  fi

  echo "🤖 Выполнение через Gemini ($model_alias)..."

  # Вызов gemini-bridge.sh
  local result=$(bash "$SCRIPT_DIR/gemini-bridge.sh" "$model_alias" "$prompt")

  echo "$result"
}

# Вспомогательная функция: исполнение через Sonnet (для medium)
workflow_execute_sonnet() {
  local prompt="$1"

  if [[ -z "$WORKFLOW_TASK_ID" ]]; then
    echo "❌ ОШИБКА: workflow_start не был вызван"
    exit 1
  fi

  echo "🤖 Выполнение через Claude Sonnet 4.5..."

  # Вызов sonnet-bridge.sh
  local result=$(bash "$SCRIPT_DIR/sonnet-bridge.sh" "$prompt")

  echo "$result"
}

# Вспомогательная функция: исполнение через Opus (для complex/very_complex)
workflow_execute_opus() {
  local prompt="$1"

  if [[ -z "$WORKFLOW_TASK_ID" ]]; then
    echo "❌ ОШИБКА: workflow_start не был вызван"
    exit 1
  fi

  echo "🤖 Выполнение через Claude Opus 4.6..."

  # Создаём временный файл для API запроса
  local temp_prompt=$(mktemp)
  echo "$prompt" > "$temp_prompt"

  # Escape промпта для JSON
  local escaped_prompt=$(jq -Rs . < "$temp_prompt")
  rm -f "$temp_prompt"

  # Вызов Claude Opus API
  local response=$(curl -s https://api.anthropic.com/v1/messages \
    -H "anthropic-version: 2023-06-01" \
    -H "x-api-key: $ANTHROPIC_API_KEY" \
    -H "content-type: application/json" \
    -d "{
      \"model\": \"claude-opus-4-6\",
      \"max_tokens\": 16384,
      \"messages\": [{\"role\": \"user\", \"content\": $escaped_prompt}]
    }")

  # Проверка на ошибки API
  if echo "$response" | jq -e '.error' >/dev/null 2>&1; then
    echo "❌ Ошибка API:" >&2
    echo "$response" | jq -r '.error.message' >&2
    return 1
  fi

  # Извлечение текста ответа
  echo "$response" | jq -r '.content[0].text'
}

# Вспомогательная функция: выполнение через ПРОГРАММУ (для program complexity)
workflow_execute_program() {
  local program_cmd="$1"

  if [[ -z "$WORKFLOW_TASK_ID" ]]; then
    echo "❌ ОШИБКА: workflow_start не был вызван"
    exit 1
  fi

  echo "🔧 Выполнение через программу: $program_cmd"
  echo ""

  # Запускаем программу и сохраняем результат
  local result=$(eval "$program_cmd" 2>&1)
  local exit_code=$?

  if [[ $exit_code -eq 0 ]]; then
    echo "✅ Программа выполнена успешно"
  else
    echo "⚠️  Программа завершилась с ошибкой (код: $exit_code)"
  fi

  echo ""
  echo "Результат программы:"
  echo "----------------------------------------"
  echo "$result"
  echo "----------------------------------------"
  echo ""

  # Записываем 0 токенов для программы (script/execute)
  # Opus только проверит результат
  return $exit_code
}

# Показывает текущий статус workflow
workflow_status() {
  if [[ -z "$WORKFLOW_TASK_ID" ]]; then
    echo "Нет активного workflow"
    return
  fi

  echo "Текущий workflow:"
  echo "  Task ID: $WORKFLOW_TASK_ID"
  echo "  Сложность: $WORKFLOW_COMPLEXITY"
  echo "  Pipeline: $WORKFLOW_PIPELINE"
}

# Показываем справку при вызове напрямую
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
  cat <<EOF
Использование: source .claude/helpers/workflow-helper.sh

Экспортируемые функции:

  workflow_start "описание задачи"
    Выполняет ШАГ 1 (router.js) + ШАГ 2 (start_task)
    Экспортирует: WORKFLOW_TASK_ID, WORKFLOW_COMPLEXITY, WORKFLOW_PIPELINE

  workflow_record <model> <role> <input_tokens> <output_tokens>
    Выполняет ШАГ 3 (record_call)
    Пример: workflow_record opus classifier 200 50

  workflow_finish
    Выполняет ШАГ 4 (finish_task + print_task_summary)
    Показывает таблицу расхода токенов

  workflow_execute_gemini <flash|pro> "<prompt>"
    Вспомогательная функция для вызова Gemini (simple/medium small context)

  workflow_execute_sonnet "<prompt>"
    Вспомогательная функция для вызова Sonnet (medium)

  workflow_execute_opus "<prompt>"
    Вспомогательная функция для вызова Opus (complex/very_complex)

  workflow_status
    Показывает статус текущего workflow

Пример использования:

  source .claude/helpers/workflow-helper.sh

  workflow_start "Добавить валидацию email"
  # → complexity="simple", TASK_ID=20260211_154530_a1b2c3

  workflow_record opus classifier 180 40
  result=\$(workflow_execute_gemini flash "промпт")
  workflow_record flash executor 2200 650
  workflow_record opus validator 800 150

  workflow_finish
  # → Таблица с расходом токенов и экономией
EOF
fi
