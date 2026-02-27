#!/usr/bin/env bash
# workflow-start.sh — Начинает workflow (ШАГ 1+2).
# Создаёт файл .claude/tracking/current_task (разблокирует Edit/Write).
# Использование: bash .claude/helpers/workflow-start.sh "описание задачи"

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TRACKING_DIR="$PROJECT_ROOT/.claude/tracking"
TRACKER="$SCRIPT_DIR/token-tracker.py"
ROUTER="$SCRIPT_DIR/router.js"

TASK_DESC="${1:?Укажите описание задачи}"

mkdir -p "$TRACKING_DIR"

# ШАГ 1: Классификация через router.js
COMPLEXITY="complex"
PIPELINE="[]"
ESTIMATED_SAVING="0%"

if [[ -f "$ROUTER" ]] && command -v node &>/dev/null; then
  ROUTE_RESULT=$(node "$ROUTER" "$TASK_DESC" 2>/dev/null || echo '{"complexity":"complex","pipeline":[],"estimatedCostReduction":"0%"}')
  COMPLEXITY=$(echo "$ROUTE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('complexity','complex'))" 2>/dev/null || echo "complex")
  PIPELINE=$(echo "$ROUTE_RESULT" | python3 -c "import sys,json; print(json.dumps(json.load(sys.stdin).get('pipeline',[])))" 2>/dev/null || echo "[]")
  ESTIMATED_SAVING=$(echo "$ROUTE_RESULT" | python3 -c "import sys,json; print(json.load(sys.stdin).get('estimatedCostReduction','0%'))" 2>/dev/null || echo "0%")
fi

echo "Сложность: $COMPLEXITY"
echo "Ожидаемая экономия: $ESTIMATED_SAVING"

# ШАГ 2: Начало трекинга
# Для program-задач передаём оценочный baseline (типичная задача через Opus напрямую).
# Baseline используется для расчёта "экономии от скриптов" в итоговом отчёте.
# Оценка: program ≈ 3000 input + 800 output токенов Opus = ~$0.105
TASK_ID=""
if [[ -f "$TRACKER" ]]; then
  if [[ "$COMPLEXITY" == "program" ]]; then
    TASK_ID=$(python3 "$TRACKER" start "$TASK_DESC" "$COMPLEXITY" 3000 800 2>/dev/null || echo "")
  else
    TASK_ID=$(python3 "$TRACKER" start "$TASK_DESC" "$COMPLEXITY" 2>/dev/null || echo "")
  fi
fi

# Фолбэк: генерация task_id вручную
if [[ -z "$TASK_ID" ]]; then
  TASK_ID="$(date +%Y%m%d_%H%M%S)_$(head -c 3 /dev/urandom | xxd -p)"
fi

echo "Task ID: $TASK_ID"

# Создаём файл-маркер (разблокирует pre-edit/pre-command хуки)
cat > "$TRACKING_DIR/current_task" <<EOF
{
  "task_id": "$TASK_ID",
  "description": "$TASK_DESC",
  "complexity": "$COMPLEXITY",
  "pipeline": $PIPELINE,
  "started_at": "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
}
EOF

echo "Workflow начат. Edit/Write разблокированы."
