#!/usr/bin/env bash
# task-enforcer.sh — Проверка соблюдения обязательного workflow
# Использование: bash .claude/helpers/task-enforcer.sh check <task_id>
#
# Проверяет что задача прошла все 4 обязательных шага:
# 1. router.js (классификация)
# 2. token_tracker start_task
# 3. execution (record_call для каждого LLM)
# 4. finish_task + print_task_summary
#
# Все комментарии на русском

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
TRACKING_DIR="$PROJECT_ROOT/.claude/tracking"
DB_PATH="$PROJECT_ROOT/data/token_usage.db"

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

usage() {
  cat <<EOF
Использование: task-enforcer.sh <command> [args]

Команды:
  check <task_id>        Проверить соблюдение workflow для задачи
  verify-before-write    Проверить что router.js и start_task уже вызваны
  report                 Показать статус текущей задачи

Примеры:
  # Проверить завершённую задачу
  bash .claude/helpers/task-enforcer.sh check 20260211_143022_a4f2b9

  # Перед Write/Edit проверить что workflow начат
  bash .claude/helpers/task-enforcer.sh verify-before-write
EOF
}

# Проверяет что задача существует в БД и имеет все записи
check_task() {
  local task_id="$1"

  if [[ ! -f "$DB_PATH" ]]; then
    echo -e "${RED}❌ База данных не найдена: $DB_PATH${NC}"
    echo "   Запусти: python3 -c 'from src.reporting.token_tracker import TokenTracker; TokenTracker()'"
    exit 1
  fi

  echo "Проверка задачи: $task_id"
  echo ""

  # Проверка 1: Задача существует
  local task_exists=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM tasks WHERE task_id = '$task_id';")
  if [[ "$task_exists" -eq 0 ]]; then
    echo -e "${RED}❌ ШАГ 2 НЕ ВЫПОЛНЕН: start_task не был вызван${NC}"
    echo "   Задача $task_id не найдена в базе"
    exit 1
  fi
  echo -e "${GREEN}✅ ШАГ 2: start_task выполнен${NC}"

  # Проверка 2: Есть вызовы LLM
  local calls_count=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM calls WHERE task_id = '$task_id';")
  if [[ "$calls_count" -eq 0 ]]; then
    echo -e "${RED}❌ ШАГ 3 НЕ ВЫПОЛНЕН: record_call не вызывался${NC}"
    echo "   Нет записей LLM вызовов для задачи"
    exit 1
  fi
  echo -e "${GREEN}✅ ШАГ 3: record_call выполнен ($calls_count вызовов)${NC}"

  # Проверка 3: Задача завершена
  local finished_at=$(sqlite3 "$DB_PATH" "SELECT finished_at FROM tasks WHERE task_id = '$task_id';")
  if [[ -z "$finished_at" || "$finished_at" == "NULL" ]]; then
    echo -e "${YELLOW}⚠️  ШАГ 4 НЕ ЗАВЕРШЁН: finish_task не вызван${NC}"
    echo "   Задача всё ещё в процессе выполнения"
    exit 1
  fi
  echo -e "${GREEN}✅ ШАГ 4: finish_task выполнен${NC}"

  # Проверка 4: Есть итоговая стоимость
  local total_cost=$(sqlite3 "$DB_PATH" "SELECT total_cost_usd FROM tasks WHERE task_id = '$task_id';")
  if [[ -z "$total_cost" || "$total_cost" == "0.0" ]]; then
    echo -e "${RED}❌ ОШИБКА: Задача завершена но стоимость = 0${NC}"
    echo "   Проверь что record_call вызывался с правильными токенами"
    exit 1
  fi

  echo ""
  echo -e "${GREEN}✅ Все 4 шага выполнены корректно${NC}"
  echo ""

  # Краткая статистика (standalone token-tracker.py)
  python3 "$SCRIPT_DIR/token-tracker.py" summary "$task_id"
}

# Проверяет что перед Write/Edit уже вызваны router.js и start_task
verify_before_write() {
  # Ищем последний task_id в tracking директории
  mkdir -p "$TRACKING_DIR"

  local latest_task=$(ls -t "$TRACKING_DIR"/task_* 2>/dev/null | head -n 1 | xargs basename 2>/dev/null || echo "")

  if [[ -z "$latest_task" ]]; then
    echo -e "${RED}❌ НАРУШЕНИЕ WORKFLOW${NC}"
    echo "   Не найден активный task_id"
    echo ""
    echo "   Перед Write/Edit/Bash с изменениями кода ОБЯЗАТЕЛЬНО:"
    echo "   1. node .claude/helpers/router.js \"задача\""
    echo "   2. python3 -c \"from src.reporting.token_tracker import TokenTracker; ...\""
    echo ""
    exit 1
  fi

  local task_id="${latest_task#task_}"

  # Проверяем что задача начата в БД
  if [[ ! -f "$DB_PATH" ]]; then
    echo -e "${RED}❌ База данных не создана${NC}"
    exit 1
  fi

  local task_exists=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM tasks WHERE task_id = '$task_id';")
  if [[ "$task_exists" -eq 0 ]]; then
    echo -e "${RED}❌ НАРУШЕНИЕ: task_id $task_id не найден в БД${NC}"
    echo "   Вызови start_task перед работой"
    exit 1
  fi

  echo -e "${GREEN}✅ Workflow начат корректно (task_id: $task_id)${NC}"
  echo "   Можно продолжать работу"
}

# Показывает текущий статус активной задачи
report() {
  mkdir -p "$TRACKING_DIR"

  local latest_task=$(ls -t "$TRACKING_DIR"/task_* 2>/dev/null | head -n 1 | xargs basename 2>/dev/null || echo "")

  if [[ -z "$latest_task" ]]; then
    echo "Нет активных задач"
    return
  fi

  local task_id="${latest_task#task_}"
  echo "Текущая задача: $task_id"

  if [[ -f "$DB_PATH" ]]; then
    local query=$(sqlite3 "$DB_PATH" "SELECT query FROM tasks WHERE task_id = '$task_id';")
    local calls=$(sqlite3 "$DB_PATH" "SELECT COUNT(*) FROM calls WHERE task_id = '$task_id';")
    local finished=$(sqlite3 "$DB_PATH" "SELECT finished_at FROM tasks WHERE task_id = '$task_id';")

    echo "  Описание: $query"
    echo "  LLM вызовов: $calls"
    if [[ -z "$finished" || "$finished" == "NULL" ]]; then
      echo -e "  Статус: ${YELLOW}В ПРОЦЕССЕ${NC}"
    else
      echo -e "  Статус: ${GREEN}ЗАВЕРШЕНА${NC}"
    fi
  fi
}

# Main
case "${1:-}" in
  check)
    if [[ -z "${2:-}" ]]; then
      echo "Ошибка: укажи task_id"
      echo "Использование: task-enforcer.sh check <task_id>"
      exit 1
    fi
    check_task "$2"
    ;;
  verify-before-write)
    verify_before_write
    ;;
  report)
    report
    ;;
  *)
    usage
    exit 1
    ;;
esac
