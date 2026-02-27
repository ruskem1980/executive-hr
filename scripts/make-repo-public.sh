#!/usr/bin/env bash
# make-repo-public.sh — Сделать репозиторий публичным для интеграционного скрипта

set -euo pipefail

echo "🔓 Делаю репозиторий PT_Standart публичным..."

# Проверка gh CLI
if ! command -v gh &>/dev/null; then
    echo "❌ gh CLI не найден. Установите: https://cli.github.com/"
    exit 1
fi

# Делаем репо публичным
gh repo edit ruskem1980/PT_Standart --visibility public

echo "✅ Репозиторий теперь публичный!"
echo ""
echo "Теперь можно использовать одну команду для установки:"
echo ""
echo "  bash <(curl -sL https://raw.githubusercontent.com/ruskem1980/PT_Standart/main/scripts/integrate-auto.sh)"
echo ""
