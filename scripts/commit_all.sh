#!/usr/bin/env bash
# Массовый коммит и пуш во все проекты репозитория
# Коммитит изменения интеграции Claude Flow V3

set -euo pipefail

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Директория с проектами
PROJECTS_DIR="/Users/at/Desktop/Проекты"
PT_STANDART_DIR="${PROJECTS_DIR}/PT_Standart"

# Лог-файл
LOG_FILE="${PT_STANDART_DIR}/data/commit_log_$(date +%Y%m%d_%H%M%S).txt"

# Счётчики
TOTAL=0
COMMITTED=0
PUSHED=0
SKIPPED=0
FAILED=0

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Массовый коммит Claude Flow V3 интеграции${NC}"
echo -e "${BLUE}  Коммит и пуш во все проекты${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# Создание лог-файла
echo "Лог коммитов — $(date)" > "$LOG_FILE"
echo "Директория проектов: $PROJECTS_DIR" >> "$LOG_FILE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Commit message
COMMIT_MSG="infra(claude-flow): интеграция Claude Flow V3

- 52 скрипта координации (.claude/helpers/)
- Конфигурации 60+ агентов (.claude/agents/)
- Slash-команды и навыки Claude Code
- TokenTracker для учёта расхода токенов
- Auto-save скрипты (git_auto_save.py)
- CLAUDE.md с полными инструкциями
- settings.json с hooks и permissions

Интегрировано из PT_Standart через integrate_all.sh

Co-Authored-By: Claude Sonnet 4.5 <noreply@anthropic.com>"

# Функция коммита для одного проекта
commit_project() {
    local project_path="$1"
    local project_name=$(basename "$project_path")

    echo -e "${YELLOW}[→] Обрабатываю: ${project_name}${NC}"
    echo "──────────────────────────────────────────────────────────" >> "$LOG_FILE"
    echo "Проект: ${project_name}" >> "$LOG_FILE"
    echo "Путь: ${project_path}" >> "$LOG_FILE"

    # Пропускаем PT_Standart (это исходник)
    if [[ "$project_name" == "PT_Standart" ]]; then
        echo -e "${BLUE}[SKIP] PT_Standart — исходный репозиторий${NC}"
        echo "Статус: SKIPPED (исходный репозиторий)" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
        ((SKIPPED++))
        return 0
    fi

    # Проверка, является ли директория Git-репозиторием
    if [[ ! -d "${project_path}/.git" ]]; then
        echo -e "${BLUE}[SKIP] Не Git-репозиторий${NC}"
        echo "Статус: SKIPPED (не Git-репозиторий)" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
        ((SKIPPED++))
        return 0
    fi

    cd "$project_path"

    # Проверка наличия изменений
    if git diff --quiet && git diff --cached --quiet && [[ -z $(git ls-files --others --exclude-standard) ]]; then
        echo -e "${BLUE}[SKIP] Нет изменений${NC}"
        echo "Статус: SKIPPED (нет изменений)" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
        ((SKIPPED++))
        return 0
    fi

    # Git add всех изменений
    echo -e "${BLUE}  [GIT] Добавляю изменения...${NC}"
    if git add -A >> "$LOG_FILE" 2>&1; then
        echo "Git add: SUCCESS" >> "$LOG_FILE"
    else
        echo -e "${RED}[✗] Ошибка git add${NC}"
        echo "Git add: FAILED" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
        ((FAILED++))
        return 1
    fi

    # Git commit
    echo -e "${BLUE}  [GIT] Коммичу изменения...${NC}"
    if git commit -m "$COMMIT_MSG" >> "$LOG_FILE" 2>&1; then
        echo -e "${GREEN}  [✓] Закоммичено${NC}"
        echo "Git commit: SUCCESS" >> "$LOG_FILE"
        ((COMMITTED++))
    else
        echo -e "${RED}[✗] Ошибка git commit${NC}"
        echo "Git commit: FAILED" >> "$LOG_FILE"
        echo "" >> "$LOG_FILE"
        ((FAILED++))
        return 1
    fi

    # Git push (только если есть remote)
    if git remote get-url origin >/dev/null 2>&1; then
        echo -e "${BLUE}  [GIT] Пушу в remote...${NC}"
        if git push origin HEAD >> "$LOG_FILE" 2>&1; then
            echo -e "${GREEN}  [✓] Запушено в remote${NC}"
            echo "Git push: SUCCESS" >> "$LOG_FILE"
            ((PUSHED++))
        else
            echo -e "${YELLOW}  [WARN] Не удалось запушить (проверьте права)${NC}"
            echo "Git push: FAILED" >> "$LOG_FILE"
        fi
    else
        echo -e "${BLUE}  [INFO] Нет remote — пуш пропущен${NC}"
        echo "Git push: SKIPPED (нет remote)" >> "$LOG_FILE"
    fi

    echo "Статус: SUCCESS" >> "$LOG_FILE"
    echo "" >> "$LOG_FILE"
}

# Поиск всех Git-репозиториев
echo -e "${BLUE}[INFO] Поиск проектов в: ${PROJECTS_DIR}${NC}"
echo ""

# Массив проектов (совместимость с macOS bash 3.x)
PROJECTS=()
while IFS= read -r line; do
    PROJECTS+=("$line")
done < <(find "$PROJECTS_DIR" -maxdepth 2 -type d -name ".git" | sed 's|/.git||' | sort)

TOTAL=${#PROJECTS[@]}

echo -e "${BLUE}[INFO] Найдено проектов: ${TOTAL}${NC}"
echo ""

# Коммит каждого проекта
for project in "${PROJECTS[@]}"; do
    commit_project "$project"
done

# Итоговый отчёт
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Итоговый отчёт${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Всего проектов:       ${TOTAL}"
echo -e "${GREEN}Закоммичено:          ${COMMITTED}${NC}"
echo -e "${GREEN}Запушено:             ${PUSHED}${NC}"
echo -e "${BLUE}Пропущено:            ${SKIPPED}${NC}"
echo -e "${RED}Ошибок:               ${FAILED}${NC}"
echo ""
echo -e "${BLUE}Лог сохранён: ${LOG_FILE}${NC}"
echo ""

# Итоговая статистика в лог
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$LOG_FILE"
echo "ИТОГОВАЯ СТАТИСТИКА" >> "$LOG_FILE"
echo "Всего:       ${TOTAL}" >> "$LOG_FILE"
echo "Закоммичено: ${COMMITTED}" >> "$LOG_FILE"
echo "Запушено:    ${PUSHED}" >> "$LOG_FILE"
echo "Пропущено:   ${SKIPPED}" >> "$LOG_FILE"
echo "Ошибок:      ${FAILED}" >> "$LOG_FILE"
echo "Завершено: $(date)" >> "$LOG_FILE"

# Код возврата
if [[ $FAILED -gt 0 ]]; then
    exit 1
else
    exit 0
fi
