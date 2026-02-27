#!/usr/bin/env node
/**
 * Claude Flow Agent Router
 * Routes tasks to optimal agents based on learned patterns
 */

const AGENT_CAPABILITIES = {
  coder: ['code-generation', 'refactoring', 'debugging', 'implementation'],
  tester: ['unit-testing', 'integration-testing', 'coverage', 'test-generation'],
  reviewer: ['code-review', 'security-audit', 'quality-check', 'best-practices'],
  researcher: ['web-search', 'documentation', 'analysis', 'summarization'],
  architect: ['system-design', 'architecture', 'patterns', 'scalability'],
  'backend-dev': ['api', 'database', 'server', 'authentication'],
  'frontend-dev': ['ui', 'react', 'css', 'components'],
  devops: ['ci-cd', 'docker', 'deployment', 'infrastructure'],
};

// === ШЕСТИУРОВНЕВАЯ МАРШРУТИЗАЦИЯ МОДЕЛЕЙ (0-5) ===
// 0: Program, 1: Trivial, 2: Simple, 3: Medium, 4: Complex, 5: Very Complex
// Модели: дешёвая → дорогая. Цель — экономия токенов Opus 4.6
const MODEL_TIERS = {
  flash: {
    name: 'gemini-3-flash-preview',
    alias: 'flash',
    cost: { input: 0.50, output: 3.00 }, // USD за 1M токенов
    context: 1000000,
    role: 'реализация кода'
  },
  pro: {
    name: 'gemini-3-pro-preview',
    alias: 'pro',
    cost: { input: 2.00, output: 12.00 },
    context: 1000000,
    role: 'ревью кода, large context execution'
  },
  sonnet: {
    name: 'claude-sonnet-4-5-20250929',
    alias: 'sonnet',
    cost: { input: 3.00, output: 15.00 },
    context: 200000,
    role: 'классификация, средняя сложность, валидация'
  },
  opus: {
    name: 'claude-opus-4-6',
    alias: 'opus',
    cost: { input: 15.00, output: 75.00 },
    context: 200000,
    role: 'verifier, сложные задачи, security'
  }
};

// Индикаторы сложности (regex-паттерны)
const COMPLEXITY_INDICATORS = {
  // Уровень 0: Задачи решаемые программой/скриптом (без LLM-генерации кода)
  program: [
    /валидиру(й|ем|ет|ет).*json/i, /провер(ь|ка|ить).*json/i,
    /отчёт.*токен/i, /статистика.*токен/i, /расход.*токен/i,
    /синхрониз(ация|ируй|ировать)/i, /sync.*back/i,
    /провер(ь|ка|ить).*зависимост/i, /dependency.*check/i,
    /lint|format|prettier|eslint|flake8|black/i,
    /тест.*запуст/i, /run.*test/i, /coverage.*report/i,
    /запуст(и|ить).*pytest/i, /run.*pytest/i, /pytest/i,
    /запуст(и|ить).*npm.*test/i, /npm.*test/i,
    /анализ.*производительност/i, /benchmark/i,
    /сгенериру(й|ем).*отчёт/i, /generate.*report/i
  ],
  // Уровень 1: Тривиальные задачи (опечатки, форматирование, простые правки)
  trivial: [
    /исправ(ь|ить).*опечатк/i, /fix.*typo/i, /исправ(ь|ить).*\s+→\s+/i,
    /переименова(ть|й).*переменн/i, /rename.*variable/i,
    /форматирова(ние|ть)/i, /formatting/i,
    /комментари(й|и|ев)/i, /comment/i, /docstring/i,
    /удали(ть|).*console\.log/i, /remove.*print/i,
    /замени(ть|).*['"][^'"]{1,20}['"].*→/i  // Замена короткой строки
  ],
  // Уровень 5: Очень сложные задачи (10+ файлов, критичная безопасность)
  very_complex: [
    /10\+\s*файлов/i, /более.*10.*файлов/i,
    /полн(ая|ую|ый|ое).*переработк/i, /complete.*overhaul/i,
    /auth.*jwt.*oauth/i, /security.*audit.*full/i,
    /критическ.*безопасн/i, /critical.*security/i,
    /систем(ная|ное).*архитектур/i, /system.*architecture/i,
    /миграц.*\+.*rollback/i, /migration.*strategy/i
  ],
  // Уровень 4: Сложные задачи
  complex: [
    /архитектур/i, /безопасн/i, /security/i, /migration/i, /миграц/i,
    /рефакторинг.*(всего|полн|глобальн|систем)/i, /переписать/i,
    /6-10\s*файлов/i, /критическ/i, /distributed/i, /микросервис/i,
    /performance.*optim/i, /масштабируем/i, /алгоритм/i
  ],
  // Уровень 3: Средняя сложность
  medium: [
    /нов(ая|ую|ый|ое)\s*(фич|функци|feature)/i, /feature/i,
    /api\s*endpoint/i, /компонент/i, /модуль/i, /интеграц/i,
    /3-5\s*файлов/i, /несколько файлов/i, /добавить.*функцион/i,
    /implement|create|build/i, /тест.*покрыт/i
  ],
  // Паттерны для понижения сложности: простые повторяющиеся действия
  simple_repetitive: [
    /добав(ь|ить|ление).*логирован/i, /add.*logging/i,
    /добав(ь|ить).*во\s*все/i, /add.*to.*all/i,
    /добав(ь|ить).*в.*каждый/i, /add.*to.*each/i,
    /удали(ть|).*из.*всех/i, /remove.*from.*all/i,
    /форматирова(ние|ть).*всех/i, /format.*all/i,
    /переименова(ть|й).*во.*всех/i, /rename.*in.*all/i
  ]
};

// Пайплайны для каждого уровня сложности (базовые - без context-aware)
// Финальный pipeline генерируется в generatePipeline() с учётом contextSize
const EXECUTION_PIPELINES = {
  program: [
    { model: 'script', role: 'execute', description: 'Script: выполнение программы' },
    { model: 'opus',   role: 'verifier', description: 'Opus: проверка результата программы' }
  ],
  trivial: [
    { model: 'flash', role: 'direct', description: 'Flash: прямое выполнение (skip classify)' }
  ],
  simple_small: [
    { model: 'sonnet', role: 'classifier', description: 'Sonnet: классификация' },
    { model: 'flash',  role: 'executor',   description: 'Flash: реализация кода' },
    { model: 'sonnet', role: 'verifier',   description: 'Sonnet: проверка корректности' }
  ],
  simple_large: [
    { model: 'sonnet', role: 'classifier', description: 'Sonnet: классификация' },
    { model: 'flash',  role: 'executor',   description: 'Flash: реализация (large context 1M)' },
    { model: 'pro',    role: 'reviewer',   description: 'Pro: ревью (large context 1M)' }
  ],
  medium_small: [
    { model: 'sonnet', role: 'classifier', description: 'Sonnet: классификация' },
    { model: 'sonnet', role: 'executor',   description: 'Sonnet: реализация' },
    { model: 'pro',    role: 'reviewer',   description: 'Pro: ревью кода' },
    { model: 'opus',   role: 'verifier',   description: 'Opus: финальная экспертиза' },
    { model: 'sonnet', role: 'applicator', description: 'Sonnet: применение правок' }
  ],
  medium_large: [
    { model: 'sonnet', role: 'classifier', description: 'Sonnet: классификация' },
    { model: 'pro',    role: 'executor',   description: 'Pro: реализация (large context 1M)' },
    { model: 'pro',    role: 'reviewer',   description: 'Pro: ревью (large context 1M)' },
    { model: 'opus',   role: 'verifier',   description: 'Opus: финальная экспертиза' },
    { model: 'sonnet', role: 'applicator', description: 'Sonnet: применение правок' }
  ],
  complex_small: [
    { model: 'opus', role: 'direct', description: 'Opus: прямое выполнение' }
  ],
  complex_large: [
    { model: 'opus', role: 'classifier', description: 'Opus: классификация' },
    { model: 'pro',  role: 'gatherer',   description: 'Pro: сбор контекста (large 1M)' },
    { model: 'opus', role: 'designer',   description: 'Opus: проектирование стратегии' },
    { model: 'pro',  role: 'executor',   description: 'Pro: выполнение по стратегии (large 1M)' },
    { model: 'opus', role: 'verifier',   description: 'Opus: финальная проверка' }
  ],
  very_complex: [
    { model: 'opus', role: 'direct', description: 'Opus: прямое выполнение (very complex)' }
  ]
};

/**
 * Оценивает примерный размер контекста задачи в токенах
 * @param {string} task — описание задачи
 * @returns {number} - оценка токенов контекста
 */
function estimateContextSize(task) {
  const taskLower = task.toLowerCase();

  // Паттерны для оценки количества файлов
  const filePatterns = [
    { pattern: /1\s*файл/i, tokens: 5000 },
    { pattern: /2\s*файл/i, tokens: 10000 },
    { pattern: /3-5\s*файл/i, tokens: 60000 },
    { pattern: /6-10\s*файл/i, tokens: 150000 },
    { pattern: /10\+\s*файл/i, tokens: 300000 },
    { pattern: /15-20\s*файл/i, tokens: 400000 },
    { pattern: /20\+\s*файл/i, tokens: 500000 },
    { pattern: /30\+\s*файл/i, tokens: 700000 },
  ];

  for (const { pattern, tokens } of filePatterns) {
    if (pattern.test(task)) return tokens;
  }

  // Паттерны для количества endpoint'ов или компонентов (числа)
  const numberMatch = task.match(/(\d+)\s*(endpoints?|файл|компонент|модул|api)/i);
  if (numberMatch) {
    const count = parseInt(numberMatch[1]);

    // Более точная оценка на основе типа файла и действия
    let tokensPerFile = 7000;  // Базовое значение

    // Корректировка для типа задачи
    if (/логирован|logging|добав.*строк|add.*line/i.test(task)) {
      tokensPerFile = 3000;  // Простое добавление строк - файлы меньше
    } else if (/рефактор/i.test(task)) {
      tokensPerFile = 10000;  // Рефакторинг - нужно больше контекста
    } else if (/миграц|migration/i.test(task)) {
      tokensPerFile = 15000;  // Миграции - много контекста
    }

    const estimatedTokens = count * tokensPerFile;

    // Ограничиваем разумными пределами
    if (estimatedTokens > 1000000) return 1000000;  // Max 1M (Gemini limit)
    if (estimatedTokens < 5000) return 5000;  // Min 5K

    return estimatedTokens;
  }

  // Паттерны для "во всех", "всех N"
  if (/во всех|all.*endpoint|всех.*файлах/i.test(task)) {
    // Если не указано число, предполагаем ~15-20
    return 150000;
  }

  // Паттерны для типов задач
  if (/рефакторинг.*модул/i.test(task)) return 200000;
  if (/миграц/i.test(task)) return 500000;

  // По умолчанию - малый контекст
  return 5000;
}

/**
 * Определяет критичность задачи
 * @param {string} task — описание задачи
 * @returns {string} - 'low' | 'medium' | 'high' | 'critical'
 */
function detectCriticality(task) {
  const taskLower = task.toLowerCase();

  // Critical
  if (/security.*audit|безопасн.*аудит|critical.*security|критическ.*безопасн/i.test(taskLower)) {
    return 'critical';
  }

  // High
  if (/auth|jwt|oauth|payment|финанс|миграц|migration|безопасн|security/i.test(taskLower)) {
    return 'high';
  }

  // Medium
  if (/api.*endpoint|новая.*фича|feature|интеграц|integration/i.test(taskLower)) {
    return 'medium';
  }

  // Low (по умолчанию)
  return 'low';
}

/**
 * Генерирует оптимальный pipeline с учётом сложности, контекста и критичности
 * @param {string} complexity - уровень сложности
 * @param {number} contextSize - размер контекста в токенах
 * @param {string} criticality - критичность задачи
 * @returns {Array} - массив шагов pipeline
 */
function generatePipeline(complexity, contextSize, criticality) {
  const CONTEXT_THRESHOLD = 100000; // 100K токенов - порог для large context

  if (complexity === 'program' || complexity === 'trivial' || complexity === 'very_complex') {
    return EXECUTION_PIPELINES[complexity];
  }

  if (complexity === 'simple') {
    return contextSize > CONTEXT_THRESHOLD
      ? EXECUTION_PIPELINES.simple_large
      : EXECUTION_PIPELINES.simple_small;
  }

  if (complexity === 'medium') {
    return contextSize > CONTEXT_THRESHOLD
      ? EXECUTION_PIPELINES.medium_large
      : EXECUTION_PIPELINES.medium_small;
  }

  if (complexity === 'complex') {
    return contextSize > CONTEXT_THRESHOLD
      ? EXECUTION_PIPELINES.complex_large
      : EXECUTION_PIPELINES.complex_small;
  }

  return EXECUTION_PIPELINES.simple_small; // fallback
}

/**
 * Оценивает стоимость выполнения pipeline
 * @param {Array} pipeline - массив шагов pipeline
 * @param {number} contextSize - размер контекста
 * @returns {number} - оценка стоимости в USD
 */
function estimateCost(pipeline, contextSize) {
  let totalCost = 0;

  for (const step of pipeline) {
    if (step.model === 'script') continue; // Программы бесплатны

    const model = MODEL_TIERS[step.model];
    if (!model) continue;

    // Оценка токенов для каждой роли
    let inputTokens = 0;
    let outputTokens = 0;

    if (step.role === 'classifier') {
      inputTokens = 200;
      outputTokens = 50;
    } else if (step.role === 'verifier' || step.role === 'reviewer') {
      inputTokens = Math.min(contextSize * 0.4, 50000);
      outputTokens = Math.min(contextSize * 0.1, 5000);
    } else if (step.role === 'executor') {
      // Для large context в hybrid (complex_large): executor получает summary, не весь контекст
      inputTokens = contextSize > 100000 ? Math.min(contextSize * 0.3, 100000) : contextSize;
      outputTokens = Math.min(contextSize * 0.3, 20000);
    } else if (step.role === 'designer') {
      // Designer получает summary от gatherer, не весь контекст
      inputTokens = contextSize > 100000 ? Math.min(contextSize * 0.1, 50000) : contextSize;
      outputTokens = Math.min(contextSize * 0.1, 5000);
    } else if (step.role === 'gatherer') {
      // Gatherer читает весь контекст, но output - summary
      inputTokens = contextSize;
      outputTokens = Math.min(contextSize * 0.02, 10000);
    } else if (step.role === 'applicator') {
      inputTokens = 3000;
      outputTokens = 500;
    } else if (step.role === 'direct') {
      inputTokens = contextSize;
      outputTokens = Math.min(contextSize * 0.4, 15000);
    }

    const cost = (inputTokens * model.cost.input + outputTokens * model.cost.output) / 1_000_000;
    totalCost += cost;
  }

  return totalCost;
}

/**
 * Классифицирует сложность задачи (эвристика без LLM-вызова)
 * @param {string} task — описание задачи
 * @returns {{ level: string, score: number, pipeline: Array, contextSize: number, criticality: string, estimatedCost: number, confidence: number, programSuggestion?: string }}
 */
function classifyComplexity(task) {
  const contextSize = estimateContextSize(task);
  const criticality = detectCriticality(task);

  // Проверка 0: Можно ли решить программой?
  for (const pattern of COMPLEXITY_INDICATORS.program) {
    if (pattern.test(task)) {
      // Определяем какая программа нужна
      let programSuggestion = '';
      if (/валидиру.*json|провер.*json/i.test(task)) {
        programSuggestion = 'scripts/validate_json_translations.py';
      } else if (/отчёт.*токен|статистика.*токен/i.test(task)) {
        programSuggestion = 'python3 -m src.reporting.token_tracker';
      } else if (/синхрониз|sync.*back/i.test(task)) {
        programSuggestion = 'scripts/sync_back.py';
      } else if (/lint|format|prettier/i.test(task)) {
        programSuggestion = 'npm run lint / prettier / black';
      } else if (/запуст.*pytest|run.*pytest|pytest/i.test(task)) {
        programSuggestion = 'pytest';
      } else if (/запуст.*npm.*test|npm.*test/i.test(task)) {
        programSuggestion = 'npm test';
      } else if (/тест.*запуст|run.*test/i.test(task)) {
        programSuggestion = 'pytest / npm test';
      }

      const pipeline = EXECUTION_PIPELINES.program;
      return {
        level: 'program',
        score: 0,
        pipeline,
        contextSize,
        criticality,
        estimatedCost: estimateCost(pipeline, contextSize),
        confidence: 0.98,
        programSuggestion
      };
    }
  }

  // Проверка 1: Тривиальная задача?
  let trivialScore = 0;
  for (const pattern of COMPLEXITY_INDICATORS.trivial) {
    if (pattern.test(task)) trivialScore++;
  }

  if (trivialScore > 0) {
    const pipeline = EXECUTION_PIPELINES.trivial;
    return {
      level: 'trivial',
      score: trivialScore,
      pipeline,
      contextSize,
      criticality,
      estimatedCost: estimateCost(pipeline, contextSize),
      confidence: 0.95
    };
  }

  // Проверка 2-5: LLM-based задачи (very_complex → complex → medium → simple)
  let score = 0;

  for (const pattern of COMPLEXITY_INDICATORS.very_complex) {
    if (pattern.test(task)) score += 5;
  }
  for (const pattern of COMPLEXITY_INDICATORS.complex) {
    if (pattern.test(task)) score += 3;
  }
  for (const pattern of COMPLEXITY_INDICATORS.medium) {
    if (pattern.test(task)) score += 1;
  }

  // Проверка на simple_repetitive: понижаем сложность если это простое повторяющееся действие
  let isSimpleRepetitive = false;
  for (const pattern of COMPLEXITY_INDICATORS.simple_repetitive) {
    if (pattern.test(task)) {
      isSimpleRepetitive = true;
      break;
    }
  }

  let level;
  let confidence;
  if (score >= 5) {
    level = 'very_complex';
    confidence = 0.90;
  } else if (score >= 3) {
    level = 'complex';
    confidence = 0.85;
  } else if (score >= 1) {
    // Если medium, но это simple repetitive → понижаем до simple
    if (isSimpleRepetitive && contextSize > 50000) {
      level = 'simple';  // simple large
      confidence = 0.82;
    } else {
      level = 'medium';
      confidence = 0.80;
    }
  } else {
    level = 'simple';
    confidence = 0.75;
  }

  const pipeline = generatePipeline(level, contextSize, criticality);
  const estimatedCost = estimateCost(pipeline, contextSize);

  return {
    level,
    score,
    pipeline,
    contextSize,
    criticality,
    estimatedCost,
    confidence
  };
}

const TASK_PATTERNS = {
  // Code patterns
  'implement|create|build|add|write code': 'coder',
  'test|spec|coverage|unit test|integration': 'tester',
  'review|audit|check|validate|security': 'reviewer',
  'research|find|search|documentation|explore': 'researcher',
  'design|architect|structure|plan': 'architect',

  // Domain patterns
  'api|endpoint|server|backend|database': 'backend-dev',
  'ui|frontend|component|react|css|style': 'frontend-dev',
  'deploy|docker|ci|cd|pipeline|infrastructure': 'devops',
};

// === ML ИНТЕГРАЦИЯ ===

/**
 * A/B testing конфигурация
 * mlRatio: доля запросов обрабатываемых ML (0.0 - 1.0)
 * mlConfidenceThreshold: минимальная уверенность ML для принятия решения
 * enabled: включен ли A/B testing
 */
const AB_CONFIG = {
  enabled: true,
  mlRatio: 0.7,          // 70% ML, 30% rules (повышен после калибровки — 88% задач >= порога)
  mlConfidenceThreshold: 0.7,
  logFile: '.claude/tracking/ab_test_log.jsonl'
};

/**
 * Вызов ML классификатора через Python subprocess
 * @param {string} task — описание задачи
 * @returns {Object|null} — результат ML или null при ошибке
 */
function callMLClassifier(task) {
  try {
    const { execSync } = require('child_process');
    const result = execSync(
      `python3 scripts/ml_classify.py "${task.replace(/"/g, '\\"')}"`,
      { encoding: 'utf-8', timeout: 5000, cwd: require('path').resolve(__dirname, '../..') }
    );
    return JSON.parse(result.trim());
  } catch (e) {
    return null;
  }
}

/**
 * Логирование результатов A/B теста
 * @param {Object} entry — запись для лога
 */
function logABResult(entry) {
  try {
    const fs = require('fs');
    const path = require('path');
    const logPath = path.resolve(__dirname, '..', '..', AB_CONFIG.logFile);
    const dir = path.dirname(logPath);
    if (!fs.existsSync(dir)) fs.mkdirSync(dir, { recursive: true });
    fs.appendFileSync(logPath, JSON.stringify(entry) + '\n');
  } catch (e) {
    // Логирование не должно блокировать основной workflow
  }
}

/**
 * Определяет группу A/B теста для текущего запроса
 * @returns {'ml'|'rules'} — группа
 */
function getABGroup() {
  if (!AB_CONFIG.enabled) return 'rules';
  return Math.random() < AB_CONFIG.mlRatio ? 'ml' : 'rules';
}

/**
 * Маппинг ML уровней на router.js уровни
 * ML возвращает: program, simple, medium, complex
 * Router.js использует: program, trivial, simple, medium, complex, very_complex
 */
function mapMLToRouter(mlComplexity) {
  const mapping = {
    'program': 'program',
    'simple': 'simple',
    'medium': 'medium',
    'complex': 'complex',
  };
  return mapping[mlComplexity] || 'simple';
}

/**
 * Вызов ML AgentSelector для ранжирования агентов
 * @param {string} task — описание задачи
 * @param {string} complexity — уровень сложности
 * @returns {Object|null} — результат ранжирования или null
 */
function callMLAgentSelector(task, complexity) {
  try {
    const { execSync } = require('child_process');
    const complexityNum = { 'program': 0, 'simple': 1, 'medium': 2, 'complex': 3 }[complexity] || 1;
    const hasSecurity = /безопасн|security|аудит|audit/i.test(task) ? 1 : 0;
    const hasPerformance = /производительн|performance|оптимиз/i.test(task) ? 1 : 0;

    const result = execSync(
      `python3 scripts/ml_agent_rank.py ${complexityNum} ${hasSecurity} ${hasPerformance}`,
      { encoding: 'utf-8', timeout: 5000, cwd: require('path').resolve(__dirname, '../..') }
    );
    const parsed = JSON.parse(result.trim());
    return parsed.length > 0 ? parsed : null;
  } catch (e) {
    return null;
  }
}

function routeTask(task) {
  const taskLower = task.toLowerCase();

  // 1. Определяем агента (паттерн-матчинг)
  let agent = 'coder';
  let confidence = 0.5;
  let reason = 'Маршрутизация по умолчанию';

  for (const [pattern, targetAgent] of Object.entries(TASK_PATTERNS)) {
    const regex = new RegExp(pattern, 'i');
    if (regex.test(taskLower)) {
      agent = targetAgent;
      confidence = 0.8;
      reason = `Совпадение с паттерном: ${pattern}`;
      break;
    }
  }

  // 2. Определяем сложность — rule-based (всегда как baseline)
  const rulesComplexity = classifyComplexity(task);

  // 3. A/B testing: ML vs rules
  const abGroup = getABGroup();
  let finalComplexity = rulesComplexity;
  let classificationMethod = 'rules';
  let mlResult = null;

  if (abGroup === 'ml' || rulesComplexity.confidence < 0.75) {
    // Вызываем ML если:
    // a) A/B тест назначил ML-группу, ИЛИ
    // b) Rule-based не уверен (confidence < 0.75) — ML fallback
    mlResult = callMLClassifier(task);

    if (mlResult && mlResult.method === 'ml' && mlResult.confidence >= AB_CONFIG.mlConfidenceThreshold) {
      // ML уверен — используем его результат
      const mlLevel = mapMLToRouter(mlResult.complexity);
      const contextSize = estimateContextSize(task);
      const criticality = detectCriticality(task);
      const pipeline = generatePipeline(mlLevel, contextSize, criticality);
      const estimatedCost = estimateCost(pipeline, contextSize);

      finalComplexity = {
        level: mlLevel,
        score: rulesComplexity.score,
        pipeline,
        contextSize,
        criticality,
        estimatedCost,
        confidence: mlResult.confidence,
        programSuggestion: rulesComplexity.programSuggestion
      };
      classificationMethod = 'ml';
    } else if (mlResult && rulesComplexity.confidence < 0.75) {
      // ML низкая уверенность + rules низкая уверенность
      // Берём consensus: если ML и rules согласны — используем, иначе rules
      classificationMethod = 'ml_fallback_to_rules';
    }
  }

  // 4. Рассчитываем экономию
  const baselineCost = estimateCost(
    [{ model: 'opus', role: 'direct' }],
    finalComplexity.contextSize
  );
  const savingsPercent = baselineCost > 0
    ? ((1 - finalComplexity.estimatedCost / baselineCost) * 100).toFixed(1)
    : '0.0';

  // 5. Логируем A/B результат
  logABResult({
    timestamp: new Date().toISOString(),
    task: task.substring(0, 100),
    abGroup,
    classificationMethod,
    rulesLevel: rulesComplexity.level,
    rulesConfidence: rulesComplexity.confidence,
    mlLevel: mlResult ? mlResult.complexity : null,
    mlConfidence: mlResult ? mlResult.confidence : null,
    mlMethod: mlResult ? mlResult.method : null,
    finalLevel: finalComplexity.level,
  });

  // 6. ML Agent Selector — ранжирование агентов
  let agentRanking = null;
  try {
    agentRanking = callMLAgentSelector(task, finalComplexity.level);
    if (agentRanking && agentRanking.length > 0) {
      agent = agentRanking[0].type;
      confidence = Math.min(0.95, agentRanking[0].score);
      reason = `ML AgentSelector: топ-${agentRanking.length} агентов`;
    }
  } catch (e) {
    // Fallback на pattern-matching агента
  }

  return {
    agent,
    confidence,
    reason,
    complexity: finalComplexity.level,
    complexityScore: finalComplexity.score,
    contextSize: finalComplexity.contextSize,
    criticality: finalComplexity.criticality,
    pipeline: finalComplexity.pipeline,
    estimatedCost: finalComplexity.estimatedCost,
    baselineCost,
    programSuggestion: finalComplexity.programSuggestion,
    estimatedCostReduction: `~${savingsPercent}%`,
    // ML метаинформация
    classificationMethod,
    abGroup,
    mlResult: mlResult ? {
      complexity: mlResult.complexity,
      confidence: mlResult.confidence,
      method: mlResult.method
    } : null,
    // ML AgentSelector результат
    agentRanking: agentRanking || []
  };
}

// CLI
const task = process.argv.slice(2).join(' ');

if (task) {
  const result = routeTask(task);
  console.log(JSON.stringify(result, null, 2));
} else {
  console.log('Usage: router.js <task description>');
  console.log('\nAvailable agents:', Object.keys(AGENT_CAPABILITIES).join(', '));
}

module.exports = { routeTask, classifyComplexity, callMLClassifier, callMLAgentSelector, getABGroup, AB_CONFIG, AGENT_CAPABILITIES, TASK_PATTERNS, MODEL_TIERS, EXECUTION_PIPELINES };
