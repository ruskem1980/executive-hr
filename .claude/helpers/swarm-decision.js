#!/usr/bin/env node
/**
 * Swarm Decision Logic - Определение нужен ли swarm для задачи
 *
 * Правила для spawning swarm:
 * - 3+ файлов → swarm
 * - Новая feature → swarm
 * - Security/performance задачи → swarm
 * - Complexity = complex → swarm
 * - Minimal sizing: начинаем с 2-3 агентов, масштабируем по необходимости
 */

const fs = require('fs');
const path = require('path');

/**
 * Оценка количества файлов из описания задачи
 */
function estimateFileCount(description) {
  // Подсчёт упоминаний файлов и путей
  const filePatterns = [
    /\b[\w-]+\.[\w]+\b/g,  // file.ext
    /\b[\w/-]+\/[\w.-]+\b/g,  // path/to/file
    /\b\d+\+?\s+files?\b/gi  // "3 files", "5+ files"
  ];

  let count = 0;
  for (const pattern of filePatterns) {
    const matches = description.match(pattern);
    if (matches) {
      // Для явного указания "N files" берём число
      if (pattern.source.includes('files?')) {
        const num = parseInt(matches[0]);
        if (!isNaN(num)) {
          count = Math.max(count, num);
        }
      } else {
        count += matches.length;
      }
    }
  }

  return count;
}

/**
 * Определяет тип задачи
 */
function detectTaskType(description) {
  const lowerDesc = description.toLowerCase();

  const types = {
    feature: /\b(feature|new|add|implement|создать|добавить|новый|фича)\b/,
    security: /\b(security|vulnerability|auth|безопасн|уязвим)\b/,
    performance: /\b(performance|optimize|speed|производ|оптимиз)\b/,
    refactor: /\b(refactor|restructure|рефактор)\b/,
    bugfix: /\b(fix|bug|error|исправ|ошибк|баг)\b/
  };

  for (const [type, pattern] of Object.entries(types)) {
    if (pattern.test(lowerDesc)) {
      return type;
    }
  }

  return 'other';
}

/**
 * Определяет нужен ли swarm и рекомендуемые агенты
 */
function shouldUseSwarm(taskDescription, complexity = 'medium') {
  const fileCount = estimateFileCount(taskDescription);
  const taskType = detectTaskType(taskDescription);

  let useSwarm = false;
  let reasoning = [];
  let recommendedAgents = [];
  let minAgents = 1;
  let maxAgents = 8;

  // Правило 1: 3+ файлов → swarm
  if (fileCount >= 3) {
    useSwarm = true;
    reasoning.push(`3+ файлов в задаче (${fileCount})`);
    minAgents = Math.max(minAgents, 3);
  }

  // Правило 2: Новая feature → swarm
  if (taskType === 'feature') {
    useSwarm = true;
    reasoning.push('Новая фича требует нескольких специалистов');
    minAgents = Math.max(minAgents, 3);
    recommendedAgents = ['researcher', 'system-architect', 'coder', 'tester', 'reviewer'];
  }

  // Правило 3: Security задачи → swarm
  if (taskType === 'security') {
    useSwarm = true;
    reasoning.push('Security задачи требуют специализированных агентов');
    minAgents = Math.max(minAgents, 3);
    recommendedAgents = ['security-architect', 'security-auditor', 'coder', 'tester'];
  }

  // Правило 4: Performance задачи → swarm
  if (taskType === 'performance') {
    useSwarm = true;
    reasoning.push('Performance optimization требует специалистов');
    minAgents = Math.max(minAgents, 3);
    recommendedAgents = ['performance-engineer', 'coder', 'tester'];
  }

  // Правило 5: Complexity = complex → swarm
  if (complexity === 'complex' || complexity === 'very_complex') {
    useSwarm = true;
    reasoning.push(`Высокая сложность (${complexity})`);
    minAgents = Math.max(minAgents, 4);
  }

  // Правило 6: Refactor across modules → swarm
  if (taskType === 'refactor' && fileCount >= 2) {
    useSwarm = true;
    reasoning.push('Рефакторинг нескольких модулей');
    minAgents = Math.max(minAgents, 3);
    recommendedAgents = ['system-architect', 'coder', 'reviewer'];
  }

  // Если swarm не нужен
  if (!useSwarm) {
    reasoning.push('Задача достаточно проста для single agent');
    minAgents = 1;
    maxAgents = 1;
    recommendedAgents = ['coder'];  // Только один агент
  }

  // Minimal sizing: для simple задач начинаем с 2-3 агентов
  if (complexity === 'simple' && useSwarm) {
    minAgents = 2;
    maxAgents = 3;
  }

  // Рекомендуемая топология
  let recommendedTopology = null;
  let consensusStrategy = null;

  if (useSwarm) {
    if (minAgents >= 5) {
      recommendedTopology = 'hierarchical';
      consensusStrategy = 'raft';
      reasoning.push('Hierarchical topology для 5+ агентов (anti-drift)');
    } else {
      recommendedTopology = 'mesh';
      consensusStrategy = 'byzantine';
      reasoning.push('Mesh topology для небольшого swarm');
    }
  }

  return {
    useSwarm,
    reasoning: reasoning.join('; '),
    taskType,
    fileCount,
    complexity,
    minAgents,
    maxAgents,
    recommendedAgents: recommendedAgents.length > 0 ? recommendedAgents : null,
    recommendedTopology,
    consensusStrategy,
    coordinatorNeeded: minAgents >= 4  // Coordinator для 4+ агентов
  };
}

/**
 * CLI entry point
 */
function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.error('Использование: node swarm-decision.js "<описание задачи>" [complexity]');
    console.error('');
    console.error('Примеры:');
    console.error('  node swarm-decision.js "Fix bug in login.js" simple');
    console.error('  node swarm-decision.js "Add JWT authentication across 5 modules" complex');
    process.exit(1);
  }

  const taskDescription = args[0];
  const complexity = args[1] || 'medium';

  const result = shouldUseSwarm(taskDescription, complexity);

  // Выводим JSON
  console.log(JSON.stringify(result, null, 2));
}

// Если запущен напрямую
if (require.main === module) {
  main();
}

module.exports = { shouldUseSwarm, estimateFileCount, detectTaskType };
