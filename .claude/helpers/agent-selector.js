#!/usr/bin/env node
/**
 * Agent Selector - Определение оптимального набора агентов для задачи
 *
 * Использует:
 * - Rule-based templates для типовых задач
 * - Adaptive adjustments на основе complexity и criticality
 * - Минималистичный подход (start small)
 */

const fs = require('fs');
const path = require('path');

// Rule-based templates для типовых задач
const AGENT_TEMPLATES = {
  'bug-fix': ['researcher', 'coder', 'tester'],
  'feature': ['researcher', 'system-architect', 'coder', 'tester', 'reviewer'],
  'refactor': ['system-architect', 'coder', 'reviewer'],
  'security': ['security-architect', 'security-auditor', 'coder', 'tester'],
  'performance': ['performance-engineer', 'coder', 'tester'],
  'documentation': ['researcher', 'api-docs'],
  'testing': ['tester', 'coder'],
  'review': ['reviewer', 'security-auditor']
};

// Mapping complexity к минимальному набору агентов
const COMPLEXITY_ADJUSTMENTS = {
  'program': [],  // Задача решается скриптом, агенты не нужны
  'simple': ['coder'],  // Только coder для простых задач
  'medium': null,  // Используем template без изменений
  'complex': null,  // Используем полный template
  'very_complex': null  // Используем template + дополнительные
};

// Критичность влияет на добавление агентов
const CRITICALITY_ADDITIONS = {
  'critical': ['security-auditor', 'reviewer'],  // Дополнительная проверка
  'high': ['reviewer'],  // Обязательное ревью
  'medium': [],  // Без изменений
  'low': []  // Без изменений
};

/**
 * Определяет тип задачи из описания
 */
function detectTaskType(description) {
  const lowerDesc = description.toLowerCase();

  // Паттерны для определения типа
  const patterns = {
    'bug-fix': /\b(fix|bug|error|issue|problem|исправ|ошибк|баг)\b/,
    'feature': /\b(feature|add|new|implement|создать|добавить|новый|фича|функционал)\b/,
    'refactor': /\b(refactor|restructure|improve|optimize|рефактор|улучш|оптимиз)\b/,
    'security': /\b(security|vulnerability|auth|permission|безопасн|уязвим|аутент)\b/,
    'performance': /\b(performance|speed|optimize|slow|быстродейств|производ|оптимиз)\b/,
    'documentation': /\b(document|docs|readme|comment|документ|описание|комментар)\b/,
    'testing': /\b(test|testing|coverage|тест)\b/,
    'review': /\b(review|audit|check|ревью|проверк)\b/
  };

  // Находим первый подходящий тип
  for (const [type, pattern] of Object.entries(patterns)) {
    if (pattern.test(lowerDesc)) {
      return type;
    }
  }

  // Дефолт - feature (наиболее универсальный)
  return 'feature';
}

/**
 * Подсчитывает количество файлов упомянутых в задаче
 */
function estimateFileCount(description) {
  // Простая эвристика: считаем упоминания путей и имён файлов
  const filePatterns = [
    /\b[\w-]+\.[\w]+\b/g,  // file.ext
    /\b[\w/-]+\/[\w.-]+\b/g  // path/to/file
  ];

  let count = 0;
  for (const pattern of filePatterns) {
    const matches = description.match(pattern);
    if (matches) {
      count += matches.length;
    }
  }

  return count;
}

/**
 * Выбирает оптимальный набор агентов
 */
function selectAgents(taskDescription, complexity = 'medium', criticality = 'medium') {
  // Если program - агенты не нужны
  if (complexity === 'program') {
    return {
      agents: [],
      reasoning: 'Задача решается программой/скриптом без участия агентов',
      taskType: 'program',
      useSwarm: false
    };
  }

  // Определяем тип задачи
  const taskType = detectTaskType(taskDescription);

  // Получаем базовый template
  let agents = [...(AGENT_TEMPLATES[taskType] || AGENT_TEMPLATES['feature'])];

  // Adjustments на основе complexity
  const complexityAdjustment = COMPLEXITY_ADJUSTMENTS[complexity];
  if (complexityAdjustment !== null) {
    if (complexity === 'simple') {
      // Для simple - минимальный набор
      agents = complexityAdjustment;
    }
    // medium и complex используют template без изменений
  }

  // Adjustments на основе criticality
  const criticalityAdditions = CRITICALITY_ADDITIONS[criticality] || [];
  for (const agent of criticalityAdditions) {
    if (!agents.includes(agent)) {
      agents.push(agent);
    }
  }

  // Убираем дубликаты
  agents = [...new Set(agents)];

  // Определяем нужен ли swarm (3+ агентов)
  const useSwarm = agents.length >= 3;

  // Reasoning
  let reasoning = `Тип задачи: ${taskType}, сложность: ${complexity}, критичность: ${criticality}. `;
  reasoning += `Выбрано ${agents.length} агент(ов). `;
  if (useSwarm) {
    reasoning += 'Рекомендуется использовать swarm для координации.';
  } else {
    reasoning += 'Swarm не требуется (< 3 агентов).';
  }

  return {
    agents,
    reasoning,
    taskType,
    useSwarm,
    recommendedTopology: useSwarm ? 'hierarchical' : null,
    estimatedFileCount: estimateFileCount(taskDescription)
  };
}

/**
 * CLI entry point
 */
function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.error('Использование: node agent-selector.js "<описание задачи>" [complexity] [criticality]');
    console.error('');
    console.error('Примеры:');
    console.error('  node agent-selector.js "Fix login bug" simple low');
    console.error('  node agent-selector.js "Add new user authentication" complex critical');
    process.exit(1);
  }

  const taskDescription = args[0];
  const complexity = args[1] || 'medium';
  const criticality = args[2] || 'medium';

  const result = selectAgents(taskDescription, complexity, criticality);

  // Выводим JSON для использования в других скриптах
  console.log(JSON.stringify(result, null, 2));
}

// Если запущен напрямую
if (require.main === module) {
  main();
}

module.exports = { selectAgents, detectTaskType };
