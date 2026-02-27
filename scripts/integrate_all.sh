#!/usr/bin/env bash
# Массовая интеграция Claude Flow V3 во все проекты репозитория
# Принудительная перезапись всех настроек

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
INTEGRATE_SCRIPT="${PT_STANDART_DIR}/scripts/integrate.sh"

# Лог-файл
LOG_FILE="${PT_STANDART_DIR}/data/integration_log_$(date +%Y%m%d_%H%M%S).txt"

# Счётчики
TOTAL=0
SUCCESS=0
SKIPPED=0
FAILED=0

echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Массовая интеграция Claude Flow V3${NC}"
echo -e "${BLUE}  Принудительная перезапись во все проекты${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""

# Проверка наличия скрипта интеграции
if [[ ! -f "$INTEGRATE_SCRIPT" ]]; then
    echo -e "${RED}[ERROR] Скрипт интеграции не найден: $INTEGRATE_SCRIPT${NC}"
    exit 1
fi

# Создание лог-файла
echo "Лог интеграции — $(date)" > "$LOG_FILE"
echo "Директория проектов: $PROJECTS_DIR" >> "$LOG_FILE"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$LOG_FILE"
echo "" >> "$LOG_FILE"

# Функция интеграции для одного проекта
integrate_project() {
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

    # Принудительное обновление из удалённого репозитория
    echo -e "${BLUE}  [GIT] Принудительное обновление из remote...${NC}"
    echo "Git: принудительное обновление" >> "$LOG_FILE"

    # Получаем текущую ветку
    CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD 2>/dev/null || echo "main")
    echo "Текущая ветка: ${CURRENT_BRANCH}" >> "$LOG_FILE"

    # Сохраняем локальные изменения в stash
    if git diff --quiet && git diff --cached --quiet; then
        echo "  [GIT] Нет локальных изменений" >> "$LOG_FILE"
    else
        echo -e "${YELLOW}  [GIT] Сохраняю локальные изменения в stash...${NC}"
        git stash push -u -m "Auto-stash before integration $(date +%Y%m%d_%H%M%S)" >> "$LOG_FILE" 2>&1
        echo "Локальные изменения сохранены в stash" >> "$LOG_FILE"
    fi

    # Проверяем наличие remote
    if git remote get-url origin >/dev/null 2>&1; then
        echo -e "${BLUE}  [GIT] Fetch from origin...${NC}"
        if git fetch origin >> "$LOG_FILE" 2>&1; then
            echo "Fetch: SUCCESS" >> "$LOG_FILE"

            # Принудительный reset на origin/BRANCH
            echo -e "${BLUE}  [GIT] Reset --hard origin/${CURRENT_BRANCH}...${NC}"
            if git reset --hard "origin/${CURRENT_BRANCH}" >> "$LOG_FILE" 2>&1; then
                echo "Reset: SUCCESS" >> "$LOG_FILE"
            else
                echo -e "${YELLOW}  [WARN] Не удалось сделать reset (возможно, ветка не на remote)${NC}"
                echo "Reset: FAILED (ветка не на remote)" >> "$LOG_FILE"
            fi
        else
            echo -e "${YELLOW}  [WARN] Не удалось сделать fetch${NC}"
            echo "Fetch: FAILED" >> "$LOG_FILE"
        fi
    else
        echo -e "${YELLOW}  [WARN] Нет удалённого репозитория (origin)${NC}"
        echo "Remote: отсутствует" >> "$LOG_FILE"
    fi

    # Запуск интеграции с автоответом "1" (перезапись CLAUDE.md)
    echo -e "${BLUE}  [INTEGRATE] Запуск интеграции Claude Flow V3...${NC}"
    echo "Интеграция: начало" >> "$LOG_FILE"

    if bash "$INTEGRATE_SCRIPT" <<< "1" >> "$LOG_FILE" 2>&1; then
        echo -e "${GREEN}[✓] Успешно интегрирован${NC}"
        echo "Статус: SUCCESS" >> "$LOG_FILE"
        ((SUCCESS++))
    else
        echo -e "${RED}[✗] Ошибка интеграции${NC}"
        echo "Статус: FAILED" >> "$LOG_FILE"
        ((FAILED++))
    fi

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

# Интеграция каждого проекта
for project in "${PROJECTS[@]}"; do
    integrate_project "$project"
done

# Итоговый отчёт
echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo -e "${BLUE}  Итоговый отчёт${NC}"
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
echo -e "Всего проектов:       ${TOTAL}"
echo -e "${GREEN}Успешно:              ${SUCCESS}${NC}"
echo -e "${BLUE}Пропущено:            ${SKIPPED}${NC}"
echo -e "${RED}Ошибок:               ${FAILED}${NC}"
echo ""
echo -e "${BLUE}Лог сохранён: ${LOG_FILE}${NC}"
echo ""

# Итоговая статистика в лог
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━" >> "$LOG_FILE"
echo "ИТОГОВАЯ СТАТИСТИКА" >> "$LOG_FILE"
echo "Всего:    ${TOTAL}" >> "$LOG_FILE"
echo "Успешно:  ${SUCCESS}" >> "$LOG_FILE"
echo "Пропущено: ${SKIPPED}" >> "$LOG_FILE"
echo "Ошибок:   ${FAILED}" >> "$LOG_FILE"
echo "Завершено: $(date)" >> "$LOG_FILE"

# Код возврата
if [[ $FAILED -gt 0 ]]; then
    exit 1
else
    exit 0
fi
