#!/usr/bin/env bash
# workflow-record.sh — Записывает вызов LLM (ШАГ 3).
# Использование: bash .claude/helpers/workflow-record.sh <model> <role> <input_tokens> <output_tokens>

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CURRENT_TASK="$PROJECT_ROOT/.claude/tracking/current_task"
TRACKER="$SCRIPT_DIR/token-tracker.py"

MODEL="${1:?Укажите модель: opus/flash/pro/sonnet}"
ROLE="${2:?Укажите роль: classifier/executor/reviewer/validator/direct}"
INPUT_TOKENS="${3:?Укажите input_tokens}"
OUTPUT_TOKENS="${4:?Укажите output_tokens}"

if [[ ! -f "$CURRENT_TASK" ]]; then
  echo "ОШИБКА: Нет активного workflow. Сначала: bash .claude/helpers/workflow-start.sh" >&2
  exit 1
fi

TASK_ID=$(python3 -c "import json; print(json.load(open('$CURRENT_TASK'))['task_id'])" 2>/dev/null || echo "")

if [[ -z "$TASK_ID" ]]; then
  echo "ОШИБКА: Не удалось прочитать task_id из $CURRENT_TASK" >&2
  exit 1
fi

if [[ -f "$TRACKER" ]]; then
  python3 "$TRACKER" record "$TASK_ID" "$MODEL" "$ROLE" "$INPUT_TOKENS" "$OUTPUT_TOKENS"
fi

echo "Записано: $MODEL ($ROLE) in:$INPUT_TOKENS out:$OUTPUT_TOKENS"
