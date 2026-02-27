#!/usr/bin/env node
/**
 * Skill Parameter Inference - Автоматическое извлечение параметров для скиллов
 *
 * Функциональность:
 * 1. Context-based inference - извлечение из промпта и контекста
 * 2. Pattern matching - использование regex для common patterns
 * 3. Learning library - сохранение успешных inferences
 * 4. LLM fallback - вызов Opus для сложных случаев (TODO: Week 2)
 */

const fs = require('fs');
const path = require('path');

// Путь к learning library
const LEARNING_LIB_PATH = path.join(__dirname, '..', 'data', 'skill-params-learned.json');

// Pattern-based extractors для разных типов параметров
const PARAM_EXTRACTORS = {
  // Commit message inference
  'commit_message': {
    patterns: [
      // "commit this as 'feat: add feature'"
      /commit.*['"]([^'"]+)['"]/i,
      // "save changes: fixed bug"
      /save changes:?\s*(.+)/i,
      // "коммит с сообщением 'fix: исправление'"
      /коммит.*['"]([^'"]+)['"]/i,
    ],
    contextAnalysis: (context) => {
      // Анализируем git diff если есть в контексте
      if (context.gitDiff) {
        const files = extractFilesFromDiff(context.gitDiff);
        if (files.length === 1) {
          return `update ${path.basename(files[0])}`;
        }
        return `update ${files.length} files`;
      }
      return null;
    }
  },

  // Pull request title/body
  'pr_title': {
    patterns: [
      /create pr ['"]([^'"]+)['"]/i,
      /pull request:?\s*(.+)/i,
    ],
    contextAnalysis: (context) => {
      if (context.branchName) {
        // Преобразуем branch name в PR title
        return context.branchName.replace(/[-_]/g, ' ');
      }
      return null;
    }
  },

  // File path inference
  'file_path': {
    patterns: [
      /in file ['"]([^'"]+)['"]/i,
      /файл ['"]([^'"]+)['"]/i,
      /path:?\s*([^\s]+)/i,
    ],
    contextAnalysis: (context) => {
      // Последний упомянутый файл в контексте
      if (context.lastMentionedFile) {
        return context.lastMentionedFile;
      }
      return null;
    }
  },

  // Agent type inference
  'agent_type': {
    patterns: [
      /spawn (\w+) agent/i,
      /use (\w+) to/i,
    ],
    contextAnalysis: (context) => {
      // На основе типа задачи выбираем агента
      const taskKeywords = context.prompt?.toLowerCase() || '';
      if (taskKeywords.includes('bug') || taskKeywords.includes('fix')) {
        return 'coder';
      }
      if (taskKeywords.includes('test')) {
        return 'tester';
      }
      if (taskKeywords.includes('review')) {
        return 'reviewer';
      }
      return null;
    }
  }
};

/**
 * Главная функция inference параметров
 * @param {string} skillName - Имя скилла (напр. 'commit', 'review-pr')
 * @param {string} userPrompt - Промпт пользователя
 * @param {Object} context - Контекст (gitDiff, branchName, lastMentionedFile, etc.)
 * @returns {Object} - Объект с извлечёнными параметрами
 */
function inferParameters(skillName, userPrompt, context = {}) {
  const result = {
    inferred: {},
    confidence: {},
    source: {}
  };

  // Определяем какие параметры нужны для этого скилла
  const requiredParams = getRequiredParams(skillName);

  // Пытаемся извлечь каждый параметр
  for (const param of requiredParams) {
    const extractor = PARAM_EXTRACTORS[param];
    if (!extractor) {
      continue; // Нет extractor для этого параметра
    }

    let value = null;
    let confidence = 0;
    let source = 'unknown';

    // 1. Pattern matching в промпте
    for (const pattern of extractor.patterns) {
      const match = userPrompt.match(pattern);
      if (match && match[1]) {
        value = match[1].trim();
        confidence = 0.9;
        source = 'pattern';
        break;
      }
    }

    // 2. Context analysis (если pattern не сработал)
    if (!value && extractor.contextAnalysis) {
      const contextValue = extractor.contextAnalysis(context);
      if (contextValue) {
        value = contextValue;
        confidence = 0.7;
        source = 'context';
      }
    }

    // 3. Learning library (проверяем прошлые успешные inferences)
    if (!value) {
      const learnedValue = lookupLearningLibrary(skillName, param, userPrompt);
      if (learnedValue) {
        value = learnedValue;
        confidence = 0.6;
        source = 'learned';
      }
    }

    // Сохраняем результат
    if (value) {
      result.inferred[param] = value;
      result.confidence[param] = confidence;
      result.source[param] = source;
    }
  }

  return result;
}

/**
 * Получить список обязательных параметров для скилла
 */
function getRequiredParams(skillName) {
  const SKILL_PARAMS = {
    'commit': ['commit_message'],
    'review-pr': ['pr_number'],
    'github-release-management': ['version', 'release_notes'],
    'swarm-orchestration': ['agent_type', 'task_description'],
  };

  return SKILL_PARAMS[skillName] || [];
}

/**
 * Поиск в learning library
 */
function lookupLearningLibrary(skillName, param, userPrompt) {
  try {
    if (!fs.existsSync(LEARNING_LIB_PATH)) {
      return null;
    }

    const library = JSON.parse(fs.readFileSync(LEARNING_LIB_PATH, 'utf8'));
    const key = `${skillName}:${param}`;

    if (!library[key]) {
      return null;
    }

    // Ищем похожий промпт в прошлых успешных inferences
    const entries = library[key];
    for (const entry of entries) {
      if (similarity(entry.prompt, userPrompt) > 0.8) {
        return entry.value;
      }
    }
  } catch (error) {
    // Ошибка чтения library - не критично
    return null;
  }

  return null;
}

/**
 * Сохранить успешный inference в learning library
 */
function saveToLearningLibrary(skillName, param, userPrompt, value) {
  try {
    // Создаём директорию если нужно
    const dir = path.dirname(LEARNING_LIB_PATH);
    if (!fs.existsSync(dir)) {
      fs.mkdirSync(dir, { recursive: true });
    }

    // Читаем или создаём library
    let library = {};
    if (fs.existsSync(LEARNING_LIB_PATH)) {
      library = JSON.parse(fs.readFileSync(LEARNING_LIB_PATH, 'utf8'));
    }

    const key = `${skillName}:${param}`;
    if (!library[key]) {
      library[key] = [];
    }

    // Добавляем новую запись
    library[key].push({
      prompt: userPrompt,
      value: value,
      timestamp: new Date().toISOString(),
      success: true
    });

    // Ограничиваем размер library (максимум 50 записей на параметр)
    if (library[key].length > 50) {
      library[key] = library[key].slice(-50);
    }

    fs.writeFileSync(LEARNING_LIB_PATH, JSON.stringify(library, null, 2));
  } catch (error) {
    console.error('Ошибка сохранения в learning library:', error.message);
  }
}

// === ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ===

/**
 * Извлечь список файлов из git diff
 */
function extractFilesFromDiff(diff) {
  const lines = diff.split('\n');
  const files = [];

  for (const line of lines) {
    if (line.startsWith('diff --git')) {
      const match = line.match(/b\/(.+)$/);
      if (match) {
        files.push(match[1]);
      }
    }
  }

  return files;
}

/**
 * Простая cosine similarity для строк (упрощённая версия)
 */
function similarity(str1, str2) {
  const words1 = str1.toLowerCase().split(/\s+/);
  const words2 = str2.toLowerCase().split(/\s+/);

  const set1 = new Set(words1);
  const set2 = new Set(words2);

  const intersection = new Set([...set1].filter(x => set2.has(x)));
  const union = new Set([...set1, ...set2]);

  return intersection.size / union.size;
}

// === CLI INTERFACE ===

if (require.main === module) {
  const args = process.argv.slice(2);

  if (args.length < 2) {
    console.log('Usage: skill-param-inference.js <skill-name> "<user-prompt>" [context-json]');
    console.log('');
    console.log('Examples:');
    console.log('  skill-param-inference.js commit "commit this as \'feat: add feature\'"');
    console.log('  skill-param-inference.js review-pr "review pr 123"');
    process.exit(1);
  }

  const skillName = args[0];
  const userPrompt = args[1];
  const context = args[2] ? JSON.parse(args[2]) : {};

  const result = inferParameters(skillName, userPrompt, context);
  console.log(JSON.stringify(result, null, 2));
}

// === EXPORTS ===

module.exports = {
  inferParameters,
  saveToLearningLibrary,
  PARAM_EXTRACTORS
};
