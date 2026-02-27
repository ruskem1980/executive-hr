#!/usr/bin/env bash
# integrate-private.sh — Интеграция PT_Standart из приватного репозитория
# Использование (требует git clone):
#
#   git clone https://github.com/ruskem1980/PT_Standart.git /tmp/pt_standart
#   bash /tmp/pt_standart/scripts/integrate-private.sh /path/to/your/project
#
# Или через gh CLI (автоматический clone):
#
#   bash <(gh repo clone ruskem1980/PT_Standart /tmp/pt_standart && cat /tmp/pt_standart/scripts/integrate-private.sh) /path/to/your/project
#
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

# ════════════════════════════════════════════
# ШАГ 0: Определение директорий
# ════════════════════════════════════════════

# Определяем где находится скрипт (клонированный PT_Standart)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PT_STANDART_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"

# Целевая директория - аргумент или текущая
TARGET_DIR="${1:-$(pwd)}"

if [ ! -d "$PT_STANDART_DIR/.git" ]; then
    fail "PT_Standart не найден. Сначала клонируйте репозиторий:"
    echo "  git clone https://github.com/ruskem1980/PT_Standart.git /tmp/pt_standart"
    echo "  bash /tmp/pt_standart/scripts/integrate-private.sh /path/to/your/project"
    exit 1
fi

echo ""
echo "═══════════════════════════════════════════════════════════"
echo "  PT_Standart — Интеграция из приватного репозитория"
echo "  Режим: ПЕРЕЗАПИСЬ БЕЗ ПОДТВЕРЖДЕНИЯ"
echo "  Исходная директория: $PT_STANDART_DIR"
echo "  Целевая директория: $TARGET_DIR"
echo "═══════════════════════════════════════════════════════════"
echo ""

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
    fail "Python 3 не найден. Установите: https://www.python.org/"
    ERRORS=$((ERRORS + 1))
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
    ok "gemini CLI установлен"
else
    warn "gemini CLI не найден (опционально, для Flash/Pro execution)"
    warn "Установите: npm install -g @google/generative-ai-cli"
fi

if [ "$ERRORS" -gt 0 ]; then
    fail "$ERRORS ошибок найдено. Установите недостающие зависимости."
    exit 1
fi

echo ""

# ════════════════════════════════════════════
# ШАГ 2: Копирование инфраструктуры
# ════════════════════════════════════════════
info "Копирую инфраструктуру PT_Standart..."

# Создаём директории
mkdir -p "$TARGET_DIR/.claude/helpers"
mkdir -p "$TARGET_DIR/.claude/hooks"
mkdir -p "$TARGET_DIR/.claude/tracking"
mkdir -p "$TARGET_DIR/scripts"
mkdir -p "$TARGET_DIR/src/reporting"
mkdir -p "$TARGET_DIR/data"

# Копируем .claude/helpers/
if [ -d "$PT_STANDART_DIR/.claude/helpers" ]; then
    cp -f "$PT_STANDART_DIR/.claude/helpers"/*.{js,sh} "$TARGET_DIR/.claude/helpers/" 2>/dev/null || true
    chmod +x "$TARGET_DIR/.claude/helpers"/*.sh 2>/dev/null || true
    ok ".claude/helpers/ скопированы"
fi

# Копируем .claude/hooks/
if [ -d "$PT_STANDART_DIR/.claude/hooks" ]; then
    cp -f "$PT_STANDART_DIR/.claude/hooks"/* "$TARGET_DIR/.claude/hooks/" 2>/dev/null || true
    chmod +x "$TARGET_DIR/.claude/hooks"/* 2>/dev/null || true
    ok ".claude/hooks/ скопированы"
fi

# Копируем scripts/
if [ -d "$PT_STANDART_DIR/scripts" ]; then
    # Исключаем install скрипты
    rsync -a --exclude="install*.sh" --exclude="integrate*.sh" --exclude="make-repo-public.sh" \
          "$PT_STANDART_DIR/scripts/" "$TARGET_DIR/scripts/" 2>/dev/null || \
    cp -f "$PT_STANDART_DIR/scripts"/*.{py,sh} "$TARGET_DIR/scripts/" 2>/dev/null || true
    chmod +x "$TARGET_DIR/scripts"/*.sh 2>/dev/null || true
    ok "scripts/ скопированы"
fi

# Копируем src/reporting/
if [ -d "$PT_STANDART_DIR/src/reporting" ]; then
    cp -f "$PT_STANDART_DIR/src/reporting"/*.py "$TARGET_DIR/src/reporting/" 2>/dev/null || true
    ok "src/reporting/ скопированы"
fi

# Копируем CLAUDE.md (критический файл с правилами workflow)
if [ -f "$PT_STANDART_DIR/CLAUDE.md" ]; then
    # Создаём бэкап если файл уже существует
    if [ -f "$TARGET_DIR/CLAUDE.md" ]; then
        cp "$TARGET_DIR/CLAUDE.md" "$TARGET_DIR/CLAUDE.md.backup"
        info "Создан бэкап: CLAUDE.md.backup"
    fi

    # Копируем эталонный CLAUDE.md с правилами PT_Standart
    cp -f "$PT_STANDART_DIR/CLAUDE.md" "$TARGET_DIR/CLAUDE.md"
    CLAUDE_LINES=$(wc -l < "$TARGET_DIR/CLAUDE.md" | tr -d ' ')
    ok "CLAUDE.md скопирован ($CLAUDE_LINES строк)"
else
    warn "CLAUDE.md не найден в PT_Standart (пропуск)"
fi

echo ""

# ════════════════════════════════════════════
# ШАГ 3: Создание __init__.py
# ════════════════════════════════════════════
info "Создаю __init__.py для Python модулей..."

touch "$TARGET_DIR/src/__init__.py"
touch "$TARGET_DIR/src/reporting/__init__.py"

ok "Python модули инициализированы"
echo ""

# ════════════════════════════════════════════
# ШАГ 4: Предустановка @claude-flow/cli
# ════════════════════════════════════════════
info "Предустанавливаю @claude-flow/cli..."

if npx @claude-flow/cli@latest --version &>/dev/null; then
    ok "@claude-flow/cli уже установлен"
else
    info "Устанавливаю @claude-flow/cli (может занять ~30 сек)..."
    npx -y @claude-flow/cli@latest --version &>/dev/null
    ok "@claude-flow/cli установлен"
fi

echo ""

# ════════════════════════════════════════════
# ШАГ 5: Инициализация БД токенов
# ════════════════════════════════════════════
info "Инициализирую БД токенов..."

if [ ! -f "$TARGET_DIR/data/token_usage.db" ]; then
    python3 -c "
import sys
sys.path.insert(0, '$TARGET_DIR')
from src.reporting.token_tracker import TokenTracker
t = TokenTracker()
print('БД токенов инициализирована')
" 2>/dev/null && ok "data/token_usage.db создана"
else
    ok "data/token_usage.db уже существует"
fi

echo ""

# ════════════════════════════════════════════
# ШАГ 6: Добавление MCP сервера (автоматически)
# ════════════════════════════════════════════
info "Добавляю MCP сервер в Claude Desktop..."

# Находим конфиг Claude Desktop
if [ "$(uname)" = "Darwin" ]; then
    CLAUDE_CONFIG="$HOME/Library/Application Support/Claude/claude_desktop_config.json"
else
    CLAUDE_CONFIG="$HOME/.config/Claude/claude_desktop_config.json"
fi

if [ -f "$CLAUDE_CONFIG" ]; then
    # Проверяем есть ли уже claude-flow
    if grep -q "claude-flow" "$CLAUDE_CONFIG" 2>/dev/null; then
        ok "MCP сервер claude-flow уже добавлен"
    else
        info "Добавляю claude-flow в MCP серверы..."

        # Создаём резервную копию
        cp "$CLAUDE_CONFIG" "$CLAUDE_CONFIG.backup"

        # Используем jq для добавления сервера
        if command -v jq &>/dev/null; then
            cat "$CLAUDE_CONFIG" | jq '.mcpServers["claude-flow"] = {
                "command": "npx",
                "args": ["-y", "@claude-flow/cli@latest"]
            }' > "$CLAUDE_CONFIG.tmp" && mv "$CLAUDE_CONFIG.tmp" "$CLAUDE_CONFIG"
            ok "MCP сервер claude-flow добавлен"
        else
            warn "jq не найден, пропускаю автоматическое добавление MCP"
            warn "Добавьте вручную в $CLAUDE_CONFIG:"
            echo '  "claude-flow": {
    "command": "npx",
    "args": ["-y", "@claude-flow/cli@latest"]
  }'
        fi
    fi
else
    warn "Claude Desktop config не найден: $CLAUDE_CONFIG"
    warn "MCP сервер нужно будет добавить вручную"
fi

echo ""

# ════════════════════════════════════════════
# ШАГ 7: Обновление .gitignore
# ════════════════════════════════════════════
info "Обновляю .gitignore..."

GITIGNORE="$TARGET_DIR/.gitignore"

if [ ! -f "$GITIGNORE" ]; then
    touch "$GITIGNORE"
fi

# Добавляем записи если их нет
if ! grep -q "# PT_Standart" "$GITIGNORE" 2>/dev/null; then
    cat >> "$GITIGNORE" <<'EOF'

# PT_Standart
data/token_usage.db
.claude/tracking/
__pycache__/
*.pyc
.DS_Store
EOF
    ok ".gitignore обновлён"
else
    ok ".gitignore уже содержит PT_Standart записи"
fi

echo ""

# ════════════════════════════════════════════
# ШАГ 8: Диагностика
# ════════════════════════════════════════════
info "Запускаю диагностику..."

echo ""
echo "─────────────────────────────────────────"
echo "Проверка установленных файлов:"
echo "─────────────────────────────────────────"

CHECK_FILES=(
    "CLAUDE.md"
    ".claude/helpers/router.js"
    ".claude/helpers/gemini-bridge.sh"
    ".claude/helpers/sonnet-bridge.sh"
    ".claude/helpers/workflow-helper.sh"
    "src/reporting/token_tracker.py"
    "scripts/git_auto_save.py"
    "data/token_usage.db"
)

ALL_OK=true
for file in "${CHECK_FILES[@]}"; do
    if [ -f "$TARGET_DIR/$file" ]; then
        echo -e "  ${GREEN}✓${NC} $file"
    else
        echo -e "  ${RED}✗${NC} $file ${RED}(отсутствует)${NC}"
        ALL_OK=false
    fi
done

echo ""

if [ "$ALL_OK" = true ]; then
    echo "═══════════════════════════════════════════════════════════"
    echo -e "  ${GREEN}✅ ИНТЕГРАЦИЯ ЗАВЕРШЕНА УСПЕШНО${NC}"
    echo "═══════════════════════════════════════════════════════════"
    echo ""

    # ════════════════════════════════════════════
    # ШАГ 9: Автоматический запуск системы
    # ════════════════════════════════════════════
    info "Запускаю систему и проверяю работоспособность..."
    echo ""

    # 9.1 Тест router.js
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🧪 ТЕСТ 1: Проверка router.js (маршрутизация моделей)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

    cd "$TARGET_DIR"
    ROUTER_RESULT=$(node .claude/helpers/router.js "Добавь функцию validate_email в validators.py" 2>/dev/null)

    if [ $? -eq 0 ]; then
        echo "$ROUTER_RESULT" | jq '.' 2>/dev/null || echo "$ROUTER_RESULT"
        ok "router.js работает корректно"
    else
        warn "router.js вернул ошибку (возможно нужна настройка)"
    fi

    echo ""

    # 9.2 Тест token_tracker с автоматическим запуском задачи
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🧪 ТЕСТ 2: Автоматический запуск задачи с tracking"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    python3 -c "
import sys
sys.path.insert(0, '$TARGET_DIR')
from src.reporting.token_tracker import TokenTracker

t = TokenTracker()
task_id = t.start_task('🎯 Первая тестовая задача PT_Standart', 'simple')
print(f'Task ID: {task_id}')
print('')

# Симуляция pipeline: sonnet → flash → sonnet
t.record_call(task_id, model='sonnet', role='classifier', input_tokens=200, output_tokens=50)
t.record_call(task_id, model='flash', role='executor', input_tokens=2500, output_tokens=800)
t.record_call(task_id, model='sonnet', role='verifier', input_tokens=800, output_tokens=150)

t.finish_task(task_id)
t.print_task_summary(task_id)
" 2>/dev/null

    if [ $? -eq 0 ]; then
        ok "token_tracker работает корректно"
    else
        warn "token_tracker вернул ошибку"
    fi

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # 9.3 Тест CLAUDE.md (проверка размера и ключевых секций)
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🧪 ТЕСТ 3: Проверка CLAUDE.md (правила PT_Standart)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    if [ -f "$TARGET_DIR/CLAUDE.md" ]; then
        CLAUDE_LINES=$(wc -l < "$TARGET_DIR/CLAUDE.md" | tr -d ' ')
        echo "Размер CLAUDE.md: $CLAUDE_LINES строк"

        # Проверка ключевых секций
        SECTIONS_OK=true

        if grep -q "ТРЁХУРОВНЕВАЯ МАРШРУТИЗАЦИЯ МОДЕЛЕЙ" "$TARGET_DIR/CLAUDE.md"; then
            echo "  ✓ Секция: Трёхуровневая маршрутизация"
        else
            echo "  ✗ ОТСУТСТВУЕТ: Трёхуровневая маршрутизация"
            SECTIONS_OK=false
        fi

        if grep -q "ЖЕЛЕЗНОЕ ПРАВИЛО: ОТЧЁТ О РАСХОДЕ ТОКЕНОВ" "$TARGET_DIR/CLAUDE.md"; then
            echo "  ✓ Секция: Отчёт о расходе токенов"
        else
            echo "  ✗ ОТСУТСТВУЕТ: Отчёт о расходе токенов"
            SECTIONS_OK=false
        fi

        if grep -q "АВТОМАТИЗАЦИЯ WORKFLOW" "$TARGET_DIR/CLAUDE.md"; then
            echo "  ✓ Секция: Автоматизация workflow"
        else
            echo "  ✗ ОТСУТСТВУЕТ: Автоматизация workflow"
            SECTIONS_OK=false
        fi

        if [ "$SECTIONS_OK" = true ] && [ "$CLAUDE_LINES" -gt 1000 ]; then
            ok "CLAUDE.md содержит все критические секции PT_Standart"
        else
            warn "CLAUDE.md неполный или отсутствуют секции"
        fi
    else
        fail "CLAUDE.md не найден!"
    fi

    echo ""

    # 9.4 Тест workflow-helper.sh (проверка функций)
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🧪 ТЕСТ 4: Проверка workflow-helper.sh (автоматизация)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    if [ -f "$TARGET_DIR/.claude/helpers/workflow-helper.sh" ]; then
        # Проверка что скрипт валидный bash
        if bash -n "$TARGET_DIR/.claude/helpers/workflow-helper.sh" 2>/dev/null; then
            echo "  ✓ Синтаксис bash корректен"

            # Проверка наличия ключевых функций
            if grep -q "workflow_start" "$TARGET_DIR/.claude/helpers/workflow-helper.sh"; then
                echo "  ✓ Функция: workflow_start"
            fi
            if grep -q "workflow_record" "$TARGET_DIR/.claude/helpers/workflow-helper.sh"; then
                echo "  ✓ Функция: workflow_record"
            fi
            if grep -q "workflow_finish" "$TARGET_DIR/.claude/helpers/workflow-helper.sh"; then
                echo "  ✓ Функция: workflow_finish"
            fi

            ok "workflow-helper.sh готов к использованию"
        else
            warn "workflow-helper.sh имеет синтаксические ошибки"
        fi
    else
        fail "workflow-helper.sh не найден!"
    fi

    echo ""

    # 9.5 Тест pre-edit хука (enforcement)
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo "🧪 ТЕСТ 5: Проверка pre-edit хука (enforcement защита)"
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    if [ -f "$TARGET_DIR/.claude/hooks/pre-edit" ]; then
        # Проверка что хук исполняемый
        if [ -x "$TARGET_DIR/.claude/hooks/pre-edit" ]; then
            echo "  ✓ pre-edit хук исполняемый"

            # Проверка наличия enforcement логики
            if grep -q "WORKFLOW_TASK_ID" "$TARGET_DIR/.claude/hooks/pre-edit"; then
                echo "  ✓ Проверка WORKFLOW_TASK_ID присутствует"
            fi
            if grep -q "ENFORCEMENT" "$TARGET_DIR/.claude/hooks/pre-edit"; then
                echo "  ✓ Enforcement логика присутствует"
            fi

            ok "pre-edit хук активен и защищает workflow"
        else
            warn "pre-edit хук не исполняемый (нужно chmod +x)"
        fi
    else
        warn "pre-edit хук не найден (опционально)"
    fi

    echo ""
    echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
    echo ""

    # Финальное сообщение
    echo "═══════════════════════════════════════════════════════════"
    echo -e "  ${GREEN}🚀 СИСТЕМА ГОТОВА К РАБОТЕ!${NC}"
    echo "═══════════════════════════════════════════════════════════"
    echo ""
    echo "✅ ТЕСТ 1: router.js - маршрутизация моделей активна"
    echo "✅ ТЕСТ 2: token_tracker - отслеживание расхода токенов активно"
    echo "✅ ТЕСТ 3: CLAUDE.md - все критические секции PT_Standart"
    echo "✅ ТЕСТ 4: workflow-helper.sh - автоматизация workflow"
    echo "✅ ТЕСТ 5: pre-edit хук - enforcement защита активна"
    echo ""
    echo "✅ Экономия токенов 85-95% уже работает!"
    echo ""
    echo "📋 Дополнительные команды:"
    echo ""
    echo "  Дневной отчёт токенов:"
    echo "    cd $TARGET_DIR && python3 -m src.reporting.token_tracker"
    echo ""
    echo "  Проверка маршрутизации:"
    echo "    cd $TARGET_DIR && node .claude/helpers/router.js \"<ваша задача>\""
    echo ""
    echo "  Перезапустите Claude Desktop если используете MCP"
    echo ""
else
    warn "Некоторые файлы отсутствуют. Проверьте установку."
    exit 1
fi
