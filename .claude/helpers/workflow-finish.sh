#!/usr/bin/env bash
# workflow-finish.sh — Завершает workflow (ШАГ 4).
# Выводит отчёт о токенах и удаляет маркер.
# Использование: bash .claude/helpers/workflow-finish.sh

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
CURRENT_TASK="$PROJECT_ROOT/.claude/tracking/current_task"
TRACKER="$SCRIPT_DIR/token-tracker.py"

if [[ ! -f "$CURRENT_TASK" ]]; then
  echo "ОШИБКА: Нет активного workflow для завершения." >&2
  exit 1
fi

TASK_ID=$(python3 -c "import json; print(json.load(open('$CURRENT_TASK'))['task_id'])" 2>/dev/null || echo "")

if [[ -n "$TASK_ID" ]] && [[ -f "$TRACKER" ]]; then
  python3 "$TRACKER" finish "$TASK_ID"
fi

# Удаляем маркер — блокировка Edit/Write снова активна
rm -f "$CURRENT_TASK"

echo "Workflow завершён."
