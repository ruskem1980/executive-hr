#!/bin/bash
# Защита от нарушения правил делегирования
# Блокирует запись "opus direct" с большими токенами для средних задач

set -euo pipefail

TASK_FILE=".claude/current-task.env"

RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m'

# Проверка вызова перед записью в TokenTracker
check_delegation_compliance() {
    local model="$1"
    local role="$2"
    local input_tokens="$3"
    local output_tokens="$4"

    # Проверка: есть ли активная задача?
    if [[ ! -f "$TASK_FILE" ]]; then
        return 0  # Нет активной задачи - пропускаем
    fi

    source "$TASK_FILE"

    # Правило: для средних задач запрещён opus direct с большими токенами
    if [[ "$CURRENT_TASK_COMPLEXITY" == "средняя" ]] || [[ "$CURRENT_TASK_COMPLEXITY" == "medium" ]]; then
        # Если это opus direct и токенов больше 10K
        if [[ "$model" == "opus" ]] && [[ "$role" == "direct" ]]; then
            local total_tokens=$((input_tokens + output_tokens))

            if [[ $total_tokens -gt 10000 ]]; then
                echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" >&2
                echo -e "${RED}✗ БЛОКИРОВКА: НАРУШЕНИЕ ПРАВИЛ ДЕЛЕГИРОВАНИЯ ✗${NC}" >&2
                echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" >&2
                echo -e "${YELLOW}Задача: $CURRENT_TASK_DESC${NC}" >&2
                echo -e "${YELLOW}Сложность: $CURRENT_TASK_COMPLEXITY${NC}" >&2
                echo -e "${YELLOW}Попытка записи: opus direct с $total_tokens токенами${NC}" >&2
                echo -e "\n${RED}ОШИБКА: Для средних задач ЗАПРЕЩЕНО прямое выполнение через Opus!${NC}" >&2
                echo -e "${RED}Это приведёт к потере ~80% экономии (\$1.24 на задачу)${NC}" >&2
                echo -e "\n${YELLOW}ОБЯЗАТЕЛЬНЫЙ ПРОТОКОЛ ДЛЯ СРЕДНИХ ЗАДАЧ:${NC}" >&2
                echo -e "  1. Классификация (Opus): record opus classifier 300 50" >&2
                echo -e "  2. Выполнение (Flash): record flash executor 60000 5000" >&2
                echo -e "  3. Ревью (Pro): record pro reviewer 7000 500" >&2
                echo -e "  4. Верификация (Opus): record opus verifier 500 100" >&2
                echo -e "\n${RED}Если задача оказалась сложнее - обновите сложность:${NC}" >&2
                echo -e "  bash .claude/helpers/auto-token-tracker.sh end" >&2
                echo -e "  bash .claude/helpers/mandatory-router.sh \"$CURRENT_TASK_DESC\"" >&2
                echo -e "  (выберите 'complex' при классификации)" >&2
                echo -e "${RED}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}" >&2
                return 1
            fi
        fi
    fi

    return 0
}

# Вызов проверки
check_delegation_compliance "$@"
