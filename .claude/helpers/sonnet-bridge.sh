#!/usr/bin/env bash
# sonnet-bridge.sh — Мост Claude Code → Claude Sonnet 4.5 API (headless)
# Использование: bash .claude/helpers/sonnet-bridge.sh "<промпт>" [max_tokens]
# Все комментарии на русском
set -euo pipefail

PROMPT="${1:?Укажите промпт}"
MAX_TOKENS="${2:-4096}"
MODEL="claude-sonnet-4-5-20250929"
API_URL="https://api.anthropic.com/v1/messages"

# Проверка наличия API ключа
if [[ -z "${ANTHROPIC_API_KEY:-}" ]]; then
  echo "ОШИБКА: ANTHROPIC_API_KEY не установлен" >&2
  exit 1
fi

# Формируем JSON-тело через jq (безопасное экранирование промпта)
JSON_BODY=$(jq -n \
  --arg model "$MODEL" \
  --arg prompt "$PROMPT" \
  --argjson max_tokens "$MAX_TOKENS" \
  '{
    model: $model,
    max_tokens: $max_tokens,
    messages: [{role: "user", content: $prompt}]
  }')

# Вызов API через curl с таймаутом 60 секунд
RESPONSE=$(curl -s --max-time 60 \
  "$API_URL" \
  -H "content-type: application/json" \
  -H "x-api-key: $ANTHROPIC_API_KEY" \
  -H "anthropic-version: 2023-06-01" \
  -d "$JSON_BODY")

# Проверка что curl вернул непустой ответ
if [[ -z "$RESPONSE" ]]; then
  echo "ОШИБКА: Пустой ответ от API (таймаут или сетевая ошибка)" >&2
  exit 1
fi

# Проверка на ошибки API
if echo "$RESPONSE" | jq -e '.error' >/dev/null 2>&1; then
  echo "ОШИБКА API:" >&2
  echo "$RESPONSE" | jq -r '.error.message // .error.type // "Неизвестная ошибка"' >&2
  exit 1
fi

# Извлечение и вывод текста ответа
echo "$RESPONSE" | jq -r '.content[0].text // empty'
