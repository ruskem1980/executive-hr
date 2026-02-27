#!/usr/bin/env bash
# gemini-bridge.sh — Мост Claude Code → Gemini CLI (headless)
# Использование: bash .claude/helpers/gemini-bridge.sh <flash|pro> "<prompt>"
# Все комментарии на русском
set -euo pipefail

MODEL_ALIAS="${1:?Укажите модель: flash или pro}"
PROMPT="${2:?Укажите промпт}"

# ВРЕМЕННОЕ РЕШЕНИЕ: Gemini CLI не поддерживает явное указание модели через -m
# Используем дефолтную модель без параметра -m
# TODO: Выяснить правильные имена моделей для Gemini CLI

# Вызов Gemini CLI в headless-режиме (без указания модели)
# --approval-mode yolo: автоматическое одобрение всех действий
# -o text: чистый текстовый вывод
# 2>/dev/null: фильтрация stderr-шума (YOLO mode, Hook registry и т.д.)
gemini -p "$PROMPT" --approval-mode yolo -o text 2>/dev/null
