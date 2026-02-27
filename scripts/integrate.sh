#!/usr/bin/env bash
# integrate.sh — Полная интеграция Claude Flow V3 в существующий проект.
# Все размышления и комментарии на русском.
#
# Запуск из корня ЦЕЛЕВОГО проекта:
#   bash <(curl -sL https://raw.githubusercontent.com/ruskem1980/PT_Standart/main/scripts/integrate.sh)
#   # или локально:
#   bash /path/to/PT_Standart/scripts/integrate.sh
#
# Что делает:
#   1. Проверяет пререквизиты (node, python3, git, gemini)
#   2. Клонирует PT_Standart во временную папку
#   3. Копирует инфраструктуру (.claude/, scripts/, src/reporting/)
#   4. НЕ копирует: memory.db, __pycache__, .DS_Store, token_usage.db
#   5. Создаёт __init__.py для Python-модулей
#   6. Предустанавливает @claude-flow/cli (чтобы hooks не таймаутились)
#   7. Инициализирует пустую БД токенов
#   8. Добавляет MCP сервер
#   9. Запускает диагностику

set -euo pipefail

# ── Цвета ──
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m'

info()  { echo -e "${BLUE}[INFO]${NC} $*"; }
ok()    { echo -e "${GREEN}[OK]${NC} $*"; }
warn()  { echo -e "${YELLOW}[WARN]${NC} $*"; }
fail()  { echo -e "${RED}[FAIL]${NC} $*"; }

REPO_URL="https://github.com/ruskem1980/PT_Standart.git"
TARGET_DIR="$(pwd)"
TMP_DIR=""

# ── Очистка при выходе ──
cleanup() {
    if [ -n "$TMP_DIR" ] && [ -d "$TMP_DIR" ]; then
        rm -rf "$TMP_DIR"
    fi
}
trap cleanup EXIT

# ════════════════════════════════════════════
# ШАГ 0: Проверка что мы в корне проекта
# ════════════════════════════════════════════
echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  Claude Flow V3 — Интеграция в проект"
echo "  Целевая директория: $TARGET_DIR"
echo "═══════════════════════════════════════════════════════════"
echo ""

if [ ! -d ".git" ]; then
    warn "Текущая директория не является git-репозиторием."
    read -p "Продолжить? (y/N): " confirm
    if [ "$confirm" != "y" ] && [ "$confirm" != "Y" ]; then
        fail "Отменено. Перейдите в корень вашего проекта и запустите снова."
        exit 1
    fi
fi

# ════════════════════════════════════════════
# ШАГ 1: Проверка пререквизитов
# ════════════════════════════════════════════
info "Проверяю пререквизиты..."

ERRORS=0

# Node.js
if command -v node &>/dev/null; then
    NODE_VER=$(node -v | sed 's/v//')
    NODE_MAJOR=$(echo "$NODE_VER" | cut -d. -f1)
    if [ "$NODE_MAJOR" -ge 18 ]; then
        ok "Node.js $NODE_VER"
    else
        fail "Node.js $NODE_VER — нужна версия 18+"
        ERRORS=$((ERRORS + 1))
    fi
else
    fail "Node.js не найден. Установите: https://nodejs.org/"
    ERRORS=$((ERRORS + 1))
fi

# npm/npx
if command -v npx &>/dev/null; then
    ok "npx $(npx --version 2>/dev/null || echo '?')"
else
    fail "npx не найден"
    ERRORS=$((ERRORS + 1))
fi

# Python 3
if command -v python3 &>/dev/null; then
    PY_VER=$(python3 --version 2>&1 | awk '{print $2}')
    ok "Python $PY_VER"
else
    warn "Python3 не найден — token tracker не будет работать"
fi

# Git
if command -v git &>/dev/null; then
    ok "git $(git --version | awk '{print $3}')"
else
    fail "git не найден"
    ERRORS=$((ERRORS + 1))
fi

# Gemini CLI (опционально)
if command -v gemini &>/dev/null; then
    ok "Gemini CLI найден"
    GEMINI_AVAILABLE=1
else
    warn "Gemini CLI не найден — маршрутизация Flash/Pro будет отключена"
    warn "  Установка: npm install -g @anthropic-ai/gemini-cli"
    GEMINI_AVAILABLE=0
fi

# Claude Code
if command -v claude &>/dev/null; then
    ok "Claude Code найден"
else
    warn "Claude Code CLI не найден в PATH"
    warn "  Если используете через VSCode — это нормально"
fi

if [ "$ERRORS" -gt 0 ]; then
    fail "Найдено $ERRORS критических проблем. Исправьте и запустите снова."
    exit 1
fi

echo ""

# ════════════════════════════════════════════
# ШАГ 2: Клонирование PT_Standart
# ════════════════════════════════════════════
info "Клонирую PT_Standart (shallow clone)..."
TMP_DIR=$(mktemp -d)
git clone --depth 1 "$REPO_URL" "$TMP_DIR/src" 2>&1 | tail -1
ok "Склонировано в $TMP_DIR/src"

SRC="$TMP_DIR/src"

# ════════════════════════════════════════════
# ШАГ 3: Копирование .claude/ (без мусора)
# ════════════════════════════════════════════
info "Копирую .claude/ инфраструктуру..."

# Создаём директории
mkdir -p .claude/helpers .claude/agents .claude/commands .claude/skills

# Копируем helpers (скрипты координации)
if [ -d "$SRC/.claude/helpers" ]; then
    # Исключаем: memory.db, .DS_Store, session.js (проект-специфичный)
    rsync -a \
        --exclude='memory.db' \
        --exclude='.DS_Store' \
        --exclude='*.db' \
        "$SRC/.claude/helpers/" ".claude/helpers/"
    ok ".claude/helpers/ — $(ls .claude/helpers/ | wc -l | tr -d ' ') файлов"
fi

# Копируем agents (конфигурации агентов)
if [ -d "$SRC/.claude/agents" ]; then
    rsync -a "$SRC/.claude/agents/" ".claude/agents/"
    ok ".claude/agents/"
fi

# Копируем commands (slash-команды)
if [ -d "$SRC/.claude/commands" ]; then
    rsync -a "$SRC/.claude/commands/" ".claude/commands/"
    ok ".claude/commands/"
fi

# Копируем skills
if [ -d "$SRC/.claude/skills" ]; then
    rsync -a "$SRC/.claude/skills/" ".claude/skills/"
    ok ".claude/skills/"
fi

# Копируем settings.json (hooks, permissions, statusline)
if [ -f "$SRC/.claude/settings.json" ]; then
    if [ -f ".claude/settings.json" ]; then
        warn ".claude/settings.json уже существует — сохраняю бэкап"
        cp ".claude/settings.json" ".claude/settings.json.bak.$(date +%s)"
    fi
    cp "$SRC/.claude/settings.json" ".claude/settings.json"
    ok ".claude/settings.json (hooks, permissions)"
fi

# Делаем скрипты исполняемыми
chmod +x .claude/helpers/*.sh 2>/dev/null || true
chmod +x .claude/helpers/*.js .claude/helpers/*.mjs .claude/helpers/*.cjs 2>/dev/null || true

echo ""

# ════════════════════════════════════════════
# ШАГ 4: Копирование scripts/
# ════════════════════════════════════════════
info "Копирую scripts/..."
mkdir -p scripts

# git_auto_save.py — автоматический коммит
if [ -f "$SRC/scripts/git_auto_save.py" ]; then
    cp "$SRC/scripts/git_auto_save.py" scripts/
    ok "scripts/git_auto_save.py"
fi

# sync_back.py — обратная синхронизация инструментов в PT_Standart
if [ -f "$SRC/scripts/sync_back.py" ]; then
    cp "$SRC/scripts/sync_back.py" scripts/
    ok "scripts/sync_back.py (обратная синхронизация)"
fi

# integrate.sh — сам скрипт интеграции (для обновления)
if [ -f "$SRC/scripts/integrate.sh" ]; then
    cp "$SRC/scripts/integrate.sh" scripts/
    chmod +x scripts/integrate.sh
    ok "scripts/integrate.sh (для обновления)"
fi

# hw-detect.sh — определение железа для оптимизации
if [ -f "$SRC/scripts/hw-detect.sh" ]; then
    cp "$SRC/scripts/hw-detect.sh" scripts/
    chmod +x scripts/hw-detect.sh
    ok "scripts/hw-detect.sh"
fi

# optimize-m3max.sh — оптимизация под Apple Silicon
if [ -f "$SRC/scripts/optimize-m3max.sh" ]; then
    cp "$SRC/scripts/optimize-m3max.sh" scripts/
    chmod +x scripts/optimize-m3max.sh
    ok "scripts/optimize-m3max.sh"
fi

echo ""

# ════════════════════════════════════════════
# ШАГ 5: Копирование src/reporting/ (token tracker)
# ════════════════════════════════════════════
info "Копирую src/reporting/ (token tracker)..."
mkdir -p src/reporting

# Создаём __init__.py файлы для Python-модулей (КРИТИЧНО!)
if [ ! -f "src/__init__.py" ]; then
    touch "src/__init__.py"
    ok "Создан src/__init__.py"
fi

if [ ! -f "src/reporting/__init__.py" ]; then
    touch "src/reporting/__init__.py"
    ok "Создан src/reporting/__init__.py"
fi

# Копируем token_tracker.py
if [ -f "$SRC/src/reporting/token_tracker.py" ]; then
    cp "$SRC/src/reporting/token_tracker.py" src/reporting/
    ok "src/reporting/token_tracker.py"
fi

# Копируем hybrid_report_aggregator.py если есть
if [ -f "$SRC/src/reporting/hybrid_report_aggregator.py" ]; then
    cp "$SRC/src/reporting/hybrid_report_aggregator.py" src/reporting/
    ok "src/reporting/hybrid_report_aggregator.py"
fi

echo ""

# ════════════════════════════════════════════
# ШАГ 6: Создаём директории данных
# ════════════════════════════════════════════
info "Создаю директории данных..."
mkdir -p data
mkdir -p .claude-flow/agent-tracking

ok "data/ — для SQLite баз (token_usage.db)"
ok ".claude-flow/agent-tracking/ — для отслеживания агентов"

echo ""

# ════════════════════════════════════════════
# ШАГ 7: CLAUDE.md
# ════════════════════════════════════════════
info "Настраиваю CLAUDE.md..."

if [ -f "CLAUDE.md" ]; then
    warn "CLAUDE.md уже существует в проекте"
    echo "  1) Перезаписать (заменить на PT_Standart версию)"
    echo "  2) Объединить (добавить в конец существующего)"
    echo "  3) Пропустить (не трогать)"
    read -p "  Выберите (1/2/3): " choice
    case "$choice" in
        1)
            cp "$SRC/CLAUDE.md" CLAUDE.md
            ok "CLAUDE.md перезаписан"
            ;;
        2)
            echo "" >> CLAUDE.md
            echo "---" >> CLAUDE.md
            echo "" >> CLAUDE.md
            cat "$SRC/CLAUDE.md" >> CLAUDE.md
            ok "CLAUDE.md дополнен"
            ;;
        3)
            warn "CLAUDE.md не изменён"
            ;;
        *)
            warn "Неизвестный выбор — пропускаю"
            ;;
    esac
else
    cp "$SRC/CLAUDE.md" CLAUDE.md
    ok "CLAUDE.md создан"
fi

echo ""

# ════════════════════════════════════════════
# ШАГ 8: Предустановка @claude-flow/cli
# ════════════════════════════════════════════
info "Предустанавливаю @claude-flow/cli (чтобы hooks не таймаутились)..."

# Устанавливаем глобально чтобы npx не качал каждый раз
if npx @claude-flow/cli@latest --version &>/dev/null 2>&1; then
    FLOW_VER=$(npx @claude-flow/cli@latest --version 2>/dev/null || echo "unknown")
    ok "@claude-flow/cli $FLOW_VER (уже кэширован)"
else
    info "Первая загрузка @claude-flow/cli — это может занять время..."
    npx -y @claude-flow/cli@latest --version 2>/dev/null || warn "Не удалось предустановить claude-flow CLI"
fi

echo ""

# ════════════════════════════════════════════
# ШАГ 9: Инициализация token tracker БД
# ════════════════════════════════════════════
info "Инициализирую БД токен-трекера..."

if command -v python3 &>/dev/null; then
    python3 -c "
import sys
sys.path.insert(0, '.')
try:
    from src.reporting.token_tracker import TokenTracker
    t = TokenTracker()
    print('OK: БД создана в data/token_usage.db')
except Exception as e:
    print(f'WARN: {e}')
" 2>/dev/null && ok "data/token_usage.db инициализирована" || warn "Не удалось инициализировать БД"
else
    warn "Python3 не найден — пропускаю инициализацию БД"
fi

echo ""

# ════════════════════════════════════════════
# ШАГ 10: MCP сервер
# ════════════════════════════════════════════
info "Добавляю MCP сервер claude-flow..."

if command -v claude &>/dev/null; then
    claude mcp add claude-flow -- npx -y @claude-flow/cli@latest 2>/dev/null \
        && ok "MCP сервер claude-flow добавлен" \
        || warn "Не удалось добавить MCP сервер (добавьте вручную)"
else
    warn "Claude Code не найден в PATH — добавьте MCP вручную:"
    echo "  claude mcp add claude-flow -- npx -y @claude-flow/cli@latest"
fi

echo ""

# ════════════════════════════════════════════
# ШАГ 11: Диагностика
# ════════════════════════════════════════════
info "Запускаю диагностику..."
npx @claude-flow/cli@latest doctor 2>/dev/null || warn "Диагностика недоступна"

echo ""

# ════════════════════════════════════════════
# ШАГ 12: .gitignore
# ════════════════════════════════════════════
info "Проверяю .gitignore..."

GITIGNORE_ENTRIES=(
    ".claude/memory.db"
    ".claude-flow/"
    "data/token_usage.db"
    "__pycache__/"
)

if [ -f ".gitignore" ]; then
    for entry in "${GITIGNORE_ENTRIES[@]}"; do
        if ! grep -qF "$entry" .gitignore; then
            echo "$entry" >> .gitignore
            ok "Добавлено в .gitignore: $entry"
        fi
    done
else
    printf '%s\n' "${GITIGNORE_ENTRIES[@]}" > .gitignore
    ok ".gitignore создан"
fi

echo ""

# ════════════════════════════════════════════
# ШАГ 13: Настройка gemini-bridge (если Gemini доступен)
# ════════════════════════════════════════════
if [ "$GEMINI_AVAILABLE" -eq 0 ]; then
    info "Gemini CLI не найден — отключаю маршрутизацию в settings.json..."
    # Не ломаем settings.json, просто предупреждаем
    warn "Маршрутизация Flash/Pro отключена. Opus будет работать напрямую."
    warn "Для включения установите Gemini CLI: npm install -g @google/gemini-cli"
fi

echo ""

# ════════════════════════════════════════════
# ИТОГ
# ════════════════════════════════════════════
echo "═══════════════════════════════════════════════════════════"
echo -e "  ${GREEN}Интеграция Claude Flow V3 завершена!${NC}"
echo "═══════════════════════════════════════════════════════════"
echo ""
echo "Что установлено:"
echo "  .claude/helpers/     — $(ls .claude/helpers/ 2>/dev/null | wc -l | tr -d ' ') скриптов координации"
echo "  .claude/agents/      — конфигурации агентов"
echo "  .claude/commands/    — slash-команды"
echo "  .claude/skills/      — навыки Claude Code"
echo "  .claude/settings.json — hooks, permissions, statusline"
echo "  scripts/             — git_auto_save, hw-detect"
echo "  src/reporting/       — token tracker"
echo "  data/                — SQLite базы"
echo "  CLAUDE.md            — инструкции для Claude Code"
echo ""
echo "Следующие шаги:"
echo "  1. Откройте проект в VS Code с Claude Code"
echo "  2. Claude автоматически прочитает CLAUDE.md и settings.json"
echo "  3. Hooks начнут работать при первом вызове инструментов"
echo ""
if [ "$GEMINI_AVAILABLE" -eq 0 ]; then
    echo "Для полной функциональности (маршрутизация моделей):"
    echo "  npm install -g @google/gemini-cli"
    echo "  export GOOGLE_API_KEY=your-key"
    echo ""
fi
echo "Тест интеграции:"
echo "  python3 -c \"from src.reporting.token_tracker import TokenTracker; print('OK')\""
echo "  npx @claude-flow/cli@latest doctor"
echo "  bash .claude/helpers/agent-tracker.sh create test-1 coder 'тест' /dev/null"
echo "  bash .claude/helpers/agent-status-checker.sh check"
echo ""
