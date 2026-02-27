#!/usr/bin/env bash
# install-pt-standart.sh — Установка PT_Standart системы в другой проект.
# Копирует: CLAUDE.md, хелперы, хуки, settings.json, token tracker, git auto-save.
# Использование: bash scripts/install-pt-standart.sh /path/to/target/project

set -euo pipefail

# Определяем корень PT_Standart (где лежит этот скрипт)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

TARGET="${1:?Укажите путь к целевому проекту}"
TARGET="$(cd "$TARGET" && pwd)"

echo "========================================"
echo "  Установка PT_Standart в: $TARGET"
echo "========================================"

# ── 1. Создаём структуру директорий ──
echo ""
echo "1/6 Создаю директории..."
mkdir -p "$TARGET/.claude/helpers"
mkdir -p "$TARGET/.claude/hooks"
mkdir -p "$TARGET/.claude/tracking"
mkdir -p "$TARGET/data"
mkdir -p "$TARGET/scripts"
mkdir -p "$TARGET/docs"

# ── 2. Копируем CLAUDE.md ──
echo "2/6 Копирую CLAUDE.md..."
if [[ -f "$TARGET/CLAUDE.md" ]]; then
  echo "  CLAUDE.md уже существует — создаю бэкап: CLAUDE.md.bak"
  cp "$TARGET/CLAUDE.md" "$TARGET/CLAUDE.md.bak"
fi
cp "$PT_ROOT/CLAUDE.md" "$TARGET/CLAUDE.md"

# ── 3. Копируем критические хелперы ──
echo "3/6 Копирую хелперы (.claude/helpers/)..."
HELPERS=(
  "workflow-start.sh"
  "workflow-record.sh"
  "workflow-finish.sh"
  "token-tracker.py"
  "router.js"
  "gemini-bridge.sh"
  "sonnet-bridge.sh"
  "workflow-helper.sh"
  "task-enforcer.sh"
  "agent-tracker.sh"
  "agent-status-checker.sh"
)
for h in "${HELPERS[@]}"; do
  if [[ -f "$PT_ROOT/.claude/helpers/$h" ]]; then
    cp "$PT_ROOT/.claude/helpers/$h" "$TARGET/.claude/helpers/$h"
    chmod +x "$TARGET/.claude/helpers/$h" 2>/dev/null || true
    echo "  + $h"
  else
    echo "  - $h (не найден, пропускаю)"
  fi
done

# ── 4. Копируем хуки ──
echo "4/6 Копирую хуки (.claude/hooks/)..."
HOOKS=("pre-edit" "pre-command")
for hook in "${HOOKS[@]}"; do
  if [[ -f "$PT_ROOT/.claude/hooks/$hook" ]]; then
    cp "$PT_ROOT/.claude/hooks/$hook" "$TARGET/.claude/hooks/$hook"
    chmod +x "$TARGET/.claude/hooks/$hook"
    echo "  + $hook"
  fi
done

# ── 5. Копируем settings.json (с мержем если есть) ──
echo "5/6 Настраиваю settings.json..."
if [[ -f "$TARGET/.claude/settings.json" ]]; then
  echo "  settings.json уже существует — создаю бэкап: settings.json.bak"
  cp "$TARGET/.claude/settings.json" "$TARGET/.claude/settings.json.bak"
fi
cp "$PT_ROOT/.claude/settings.json" "$TARGET/.claude/settings.json"

# ── 6. Копируем скрипты ──
echo "6/6 Копирую скрипты..."
if [[ -f "$PT_ROOT/scripts/git_auto_save.py" ]]; then
  cp "$PT_ROOT/scripts/git_auto_save.py" "$TARGET/scripts/git_auto_save.py"
  echo "  + git_auto_save.py"
fi
if [[ -f "$PT_ROOT/docs/claude-flow-reference.md" ]]; then
  cp "$PT_ROOT/docs/claude-flow-reference.md" "$TARGET/docs/claude-flow-reference.md"
  echo "  + claude-flow-reference.md"
fi

# ── Проверка ──
echo ""
echo "========================================"
echo "  Проверка установки"
echo "========================================"

ERRORS=0

check_file() {
  if [[ -f "$1" ]]; then
    echo "  OK  $2"
  else
    echo "  FAIL $2 ($1)"
    ERRORS=$((ERRORS + 1))
  fi
}

check_file "$TARGET/CLAUDE.md" "CLAUDE.md"
check_file "$TARGET/.claude/settings.json" "settings.json"
check_file "$TARGET/.claude/hooks/pre-edit" "pre-edit hook"
check_file "$TARGET/.claude/hooks/pre-command" "pre-command hook"
check_file "$TARGET/.claude/helpers/workflow-start.sh" "workflow-start.sh"
check_file "$TARGET/.claude/helpers/workflow-record.sh" "workflow-record.sh"
check_file "$TARGET/.claude/helpers/workflow-finish.sh" "workflow-finish.sh"
check_file "$TARGET/.claude/helpers/token-tracker.py" "token-tracker.py"
check_file "$TARGET/.claude/helpers/router.js" "router.js"
check_file "$TARGET/.claude/helpers/gemini-bridge.sh" "gemini-bridge.sh"

# Проверяем что хуки executable
for hook in "pre-edit" "pre-command"; do
  if [[ -x "$TARGET/.claude/hooks/$hook" ]]; then
    echo "  OK  $hook executable"
  else
    echo "  WARN $hook not executable"
    chmod +x "$TARGET/.claude/hooks/$hook" 2>/dev/null || true
  fi
done

# Тест blocking хука
echo ""
echo "Тест enforcement..."
rm -f "$TARGET/.claude/tracking/current_task"
if bash "$TARGET/.claude/hooks/pre-edit" 2>/dev/null; then
  echo "  FAIL pre-edit НЕ блокирует без workflow!"
  ERRORS=$((ERRORS + 1))
else
  echo "  OK  pre-edit блокирует без workflow"
fi

# Тест с workflow
echo '{"task_id":"test"}' > "$TARGET/.claude/tracking/current_task"
if bash "$TARGET/.claude/hooks/pre-edit" 2>/dev/null; then
  echo "  OK  pre-edit разрешает с workflow"
else
  echo "  FAIL pre-edit блокирует даже с workflow!"
  ERRORS=$((ERRORS + 1))
fi
rm -f "$TARGET/.claude/tracking/current_task"

echo ""
if [[ $ERRORS -eq 0 ]]; then
  echo "========================================"
  echo "  УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО"
  echo "========================================"
  echo ""
  echo "  Файлов установлено: $(find "$TARGET/.claude/helpers" -type f | wc -l | tr -d ' ') хелперов + $(find "$TARGET/.claude/hooks" -type f | wc -l | tr -d ' ') хуков"
  echo "  CLAUDE.md: $(wc -l < "$TARGET/CLAUDE.md" | tr -d ' ') строк (компактный)"
  echo ""
  echo "  Workflow готов. Enforcement активен."
else
  echo "========================================"
  echo "  УСТАНОВКА ЗАВЕРШЕНА С $ERRORS ОШИБКАМИ"
  echo "========================================"
fi
