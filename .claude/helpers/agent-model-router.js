#!/usr/bin/env node
/**
 * Agent Model Router - Определение оптимальной модели для каждого типа агента
 *
 * Использует:
 * - Hardcoded defaults для быстрых решений
 * - JSON override из конфига (если есть)
 * - Экономия токенов через правильный выбор модели
 */

const fs = require('fs');
const path = require('path');

// Hardcoded defaults для каждого типа агента
const AGENT_MODEL_DEFAULTS = {
  // Исследование и анализ - Haiku достаточно
  'researcher': 'haiku',
  'explorer': 'haiku',

  // Написание кода - Sonnet для баланса качества и стоимости
  'coder': 'sonnet',
  'backend-dev': 'sonnet',
  'mobile-dev': 'sonnet',
  'ml-developer': 'sonnet',

  // Архитектура - Opus для критичных решений
  'system-architect': 'opus',
  'ddd-domain-expert': 'opus',

  // Безопасность - Opus для тщательности
  'security-architect': 'opus',
  'security-auditor': 'sonnet',  // Auditor может быть Sonnet

  // Производительность - Sonnet достаточно
  'performance-engineer': 'sonnet',
  'perf-analyzer': 'haiku',

  // Тестирование - Haiku для базовых тестов
  'tester': 'haiku',
  'tdd-london-swarm': 'sonnet',

  // Ревью - Sonnet для качественного ревью
  'reviewer': 'sonnet',
  'code-review-swarm': 'sonnet',

  // Документация - Haiku достаточно
  'api-docs': 'haiku',
  'documenter': 'haiku',

  // Координация - Sonnet для управления
  'task-orchestrator': 'sonnet',
  'swarm-coordinator': 'sonnet',
  'hierarchical-coordinator': 'sonnet',

  // Специализированные - индивидуально
  'production-validator': 'opus',  // Критичная проверка
  'cicd-engineer': 'sonnet',
  'repo-architect': 'opus'
};

// Цены моделей (для отчётности)
const MODEL_COSTS = {
  'opus': { input: 0.000015, output: 0.000075 },
  'sonnet': { input: 0.000003, output: 0.000015 },
  'haiku': { input: 0.000001, output: 0.000005 },
  'flash': { input: 0.0000005, output: 0.000003 },
  'pro': { input: 0.000002, output: 0.000012 }
};

/**
 * Загружает override конфиг если существует
 */
function loadConfigOverride() {
  const configPath = path.join(__dirname, '..', 'config', 'agent-models.json');

  if (fs.existsSync(configPath)) {
    try {
      const content = fs.readFileSync(configPath, 'utf8');
      return JSON.parse(content);
    } catch (err) {
      console.error(`Ошибка чтения конфига ${configPath}:`, err.message);
      return {};
    }
  }

  return {};
}

/**
 * Определяет модель для агента
 */
function getModelForAgent(agentType, configOverride = null) {
  // Загружаем override если не передан
  const override = configOverride || loadConfigOverride();

  // Проверяем override сначала
  if (override[agentType]) {
    return {
      model: override[agentType],
      source: 'config_override',
      cost: MODEL_COSTS[override[agentType]] || MODEL_COSTS['opus']
    };
  }

  // Fallback на defaults
  const model = AGENT_MODEL_DEFAULTS[agentType] || 'sonnet';  // Default = sonnet

  return {
    model,
    source: 'hardcoded_default',
    cost: MODEL_COSTS[model]
  };
}

/**
 * Получает routing для нескольких агентов
 */
function getRoutingForAgents(agentTypes) {
  const configOverride = loadConfigOverride();
  const routing = {};

  for (const agentType of agentTypes) {
    routing[agentType] = getModelForAgent(agentType, configOverride);
  }

  return routing;
}

/**
 * Подсчёт предполагаемой стоимости swarm
 */
function estimateSwarmCost(agentTypes, avgInputTokens = 3000, avgOutputTokens = 1000) {
  const routing = getRoutingForAgents(agentTypes);

  let totalCost = 0;
  const breakdown = [];

  for (const [agentType, info] of Object.entries(routing)) {
    const agentCost =
      (avgInputTokens * info.cost.input) +
      (avgOutputTokens * info.cost.output);

    totalCost += agentCost;
    breakdown.push({
      agent: agentType,
      model: info.model,
      cost: agentCost
    });
  }

  return {
    totalCost,
    breakdown,
    agentCount: agentTypes.length
  };
}

/**
 * Создаёт дефолтный конфиг файл
 */
function createDefaultConfig() {
  const configDir = path.join(__dirname, '..', 'config');
  const configPath = path.join(configDir, 'agent-models.json');

  if (!fs.existsSync(configDir)) {
    fs.mkdirSync(configDir, { recursive: true });
  }

  const defaultConfig = {
    "_comment": "Override для моделей агентов. Если не указано - используются hardcoded defaults.",
    "_example": {
      "coder": "sonnet",
      "security-architect": "opus"
    }
  };

  fs.writeFileSync(configPath, JSON.stringify(defaultConfig, null, 2));
  console.error(`Создан дефолтный конфиг: ${configPath}`);
}

/**
 * CLI entry point
 */
function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.error('Использование: node agent-model-router.js <agent-type> [agent-type2 ...]');
    console.error('             node agent-model-router.js --estimate <agent-type> [agent-type2 ...]');
    console.error('             node agent-model-router.js --create-config');
    console.error('');
    console.error('Примеры:');
    console.error('  node agent-model-router.js coder');
    console.error('  node agent-model-router.js coder tester reviewer');
    console.error('  node agent-model-router.js --estimate coder tester reviewer');
    console.error('  node agent-model-router.js --create-config');
    process.exit(1);
  }

  // Команда создания конфига
  if (args[0] === '--create-config') {
    createDefaultConfig();
    return;
  }

  // Команда оценки стоимости
  if (args[0] === '--estimate') {
    const agentTypes = args.slice(1);
    const estimate = estimateSwarmCost(agentTypes);
    console.log(JSON.stringify(estimate, null, 2));
    return;
  }

  // Обычный routing для агентов
  const agentTypes = args;
  const routing = getRoutingForAgents(agentTypes);

  console.log(JSON.stringify(routing, null, 2));
}

// Если запущен напрямую
if (require.main === module) {
  main();
}

module.exports = {
  getModelForAgent,
  getRoutingForAgents,
  estimateSwarmCost,
  AGENT_MODEL_DEFAULTS,
  MODEL_COSTS
};
