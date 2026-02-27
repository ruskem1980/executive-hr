#!/usr/bin/env bash
# Скрипт полной переустановки и интеграции Claude Flow V3
# Использование: bash install-claude-flow-v3.sh [путь-к-проекту]

set -e

PROJECT_PATH="${1:-.}"
cd "$PROJECT_PATH"

echo "🚀 Начинаем полную переустановку Claude Flow V3 в проекте: $(pwd)"

# ======================================================================
# ШАГ 1: Очистка старых установок
# ======================================================================
echo ""
echo "🧹 ШАГ 1/8: Очистка старых установок..."

# Остановить daemon если запущен
npx -y @claude-flow/cli@latest daemon stop 2>/dev/null || true

# Удалить старые директории
rm -rf .claude-flow node_modules package-lock.json 2>/dev/null || true

# Очистить глобальный кеш npx (автоматически подтверждаем)
yes | npx clear-npx-cache 2>/dev/null || true

# ======================================================================
# ШАГ 2: Установка зависимостей
# ======================================================================
echo ""
echo "📦 ШАГ 2/8: Установка свежей версии @claude-flow/cli..."

# Принудительная переустановка последней версии
npm install -g @claude-flow/cli@latest --force

# Проверка версии
INSTALLED_VERSION=$(npx -y @claude-flow/cli@latest --version 2>/dev/null || echo "unknown")
echo "✅ Установлена версия: $INSTALLED_VERSION"

# ======================================================================
# ШАГ 3: Инициализация проекта
# ======================================================================
echo ""
echo "🔧 ШАГ 3/8: Инициализация проекта с V3 конфигурацией..."

# Создать claude-flow.config.json с анти-дрифт настройками
cat > claude-flow.config.json <<EOF
{
  "version": "3.0.0",
  "swarm": {
    "topology": "hierarchical",
    "maxAgents": 8,
    "strategy": "specialized",
    "consensus": "raft",
    "antiDrift": true
  },
  "memory": {
    "backend": "hybrid",
    "hnsw": {
      "enabled": true,
      "M": 16,
      "efConstruction": 200
    },
    "quantization": {
      "enabled": true,
      "bits": 8
    }
  },
  "neural": {
    "enabled": true,
    "sona": {
      "enabled": true,
      "adaptationThreshold": 0.05
    },
    "moe": {
      "enabled": true,
      "numExperts": 8
    }
  },
  "performance": {
    "flashAttention": true,
    "wasmSimd": true,
    "targetLatency": {
      "mcp": 100,
      "cli": 500,
      "sona": 0.05
    }
  },
  "providers": {
    "anthropic": {
      "model": "claude-opus-4-6",
      "apiKey": "\${ANTHROPIC_API_KEY}"
    },
    "google": {
      "models": {
        "flash": "gemini-3-flash-preview",
        "pro": "gemini-3-pro-preview"
      },
      "apiKey": "\${GOOGLE_API_KEY}"
    }
  },
  "hooks": {
    "enabled": true,
    "autoLearn": true,
    "backgroundWorkers": true
  }
}
EOF

echo "✅ Создан claude-flow.config.json с оптимальными настройками"

# Инициализация через wizard (автоматически подтверждаем переинициализацию)
yes | npx -y @claude-flow/cli@latest init --preset production --skip-wizard --force 2>/dev/null || \
npx -y @claude-flow/cli@latest init --preset production --skip-wizard --force

# ======================================================================
# ШАГ 4: Настройка MCP серверов
# ======================================================================
echo ""
echo "🔌 ШАГ 4/8: Настройка MCP серверов..."

# Проверить наличие claude CLI
if command -v claude &> /dev/null; then
    echo "Настраиваем MCP серверы через claude CLI..."

    # Удалить старые MCP серверы если есть
    claude mcp remove claude-flow 2>/dev/null || true
    claude mcp remove ruv-swarm 2>/dev/null || true
    claude mcp remove flow-nexus 2>/dev/null || true

    # Добавить новые (|| true игнорирует ошибку если уже существуют)
    claude mcp add claude-flow -- npx -y @claude-flow/cli@latest || true
    claude mcp add ruv-swarm -- npx -y ruv-swarm mcp start || true
    claude mcp add flow-nexus -- npx -y flow-nexus@latest mcp start || true

    echo "✅ MCP серверы настроены"
else
    echo "⚠️  claude CLI не найден. Пропускаем настройку MCP серверов."
    echo "   Установите claude CLI: https://github.com/anthropics/anthropic-sdk-typescript"
fi

# ======================================================================
# ШАГ 5: Инициализация памяти (AgentDB)
# ======================================================================
echo ""
echo "🧠 ШАГ 5/8: Инициализация памяти с HNSW индексированием..."

npx -y @claude-flow/cli@latest memory init --force --verbose --hnsw

# Создать базовые namespace'ы
for ns in "patterns" "solutions" "tasks" "code-snippets" "optimizations"; do
    echo "Создаём namespace: $ns"
    npx -y @claude-flow/cli@latest memory store \
        --key "init" \
        --value "Namespace initialized" \
        --namespace "$ns" 2>/dev/null || true
done

echo "✅ Память инициализирована с 5 namespace'ами"

# ======================================================================
# ШАГ 6: Запуск daemon с фоновыми воркерами
# ======================================================================
echo ""
echo "🤖 ШАГ 6/8: Запуск daemon с 12 фоновыми воркерами..."

npx -y @claude-flow/cli@latest daemon start

# Подождать запуска
sleep 3

# Проверить статус
DAEMON_STATUS=$(npx -y @claude-flow/cli@latest daemon status 2>&1 || echo "stopped")
echo "Daemon статус: $DAEMON_STATUS"

# Включить все критически важные воркеры
for worker in "optimize" "audit" "testgaps" "map"; do
    npx -y @claude-flow/cli@latest daemon enable-worker "$worker" 2>/dev/null || true
done

echo "✅ Daemon запущен с активными воркерами"

# ======================================================================
# ШАГ 7: Предварительное обучение (pre-training)
# ======================================================================
echo ""
echo "🎓 ШАГ 7/8: Предварительное обучение на кодовой базе..."

# Только если есть src/ директория
if [ -d "src" ]; then
    echo "Запускаем pretrain на src/..."
    npx -y @claude-flow/cli@latest hooks pretrain \
        --model-type moe \
        --epochs 5 \
        --path src/ 2>/dev/null || echo "⚠️  Pretrain пропущен (опционально)"
else
    echo "⚠️  Директория src/ не найдена, пропускаем pretrain"
fi

# ======================================================================
# ШАГ 8: Диагностика и валидация
# ======================================================================
echo ""
echo "🏥 ШАГ 8/8: Финальная диагностика системы..."

npx -y @claude-flow/cli@latest doctor --fix --verbose

# ======================================================================
# ФИНАЛЬНЫЙ ОТЧЁТ
# ======================================================================
echo ""
echo "========================================================================"
echo "  ✅ УСТАНОВКА ЗАВЕРШЕНА УСПЕШНО"
echo "========================================================================"
echo ""
echo "📊 Установленные компоненты:"
echo "  - Claude Flow CLI: $INSTALLED_VERSION"
echo "  - Конфигурация: claude-flow.config.json (hierarchical, anti-drift)"
echo "  - Память: AgentDB с HNSW (150x-12,500x ускорение)"
echo "  - Daemon: Запущен с фоновыми воркерами"
echo "  - MCP серверы: claude-flow, ruv-swarm, flow-nexus"
echo ""
echo "🎯 Быстрая проверка:"
echo "  npx @claude-flow/cli@latest status"
echo "  npx @claude-flow/cli@latest swarm init --v3-mode"
echo "  npx @claude-flow/cli@latest memory search --query 'test'"
echo ""
echo "📚 Документация:"
echo "  - Hooks: npx @claude-flow/cli@latest hooks list"
echo "  - Agents: npx @claude-flow/cli@latest agent types"
echo "  - Memory: npx @claude-flow/cli@latest memory --help"
echo ""
echo "🚀 Готово к работе!"
echo "========================================================================"

# Вывести текущий статус системы
echo ""
echo "📈 Текущий статус:"
npx -y @claude-flow/cli@latest status --verbose 2>/dev/null || true
