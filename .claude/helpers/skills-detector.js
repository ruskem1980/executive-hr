#!/usr/bin/env node
/**
 * Skills Detector - Автоматическое определение подходящих skills
 *
 * Упрощённая версия на keyword matching (для MVP)
 * В будущем можно добавить semantic embeddings через Gemini API
 */

const fs = require('fs');
const path = require('path');

// Keyword-based patterns для skills
const SKILL_PATTERNS = {
  'commit': {
    keywords: ['commit', 'коммит', 'save changes', 'git commit', 'push'],
    confidence_threshold: 0.8,
    description: 'Create git commit with changes'
  },
  'review-pr': {
    keywords: ['review', 'pr', 'pull request', 'code review', 'ревью'],
    confidence_threshold: 0.8,
    description: 'Review pull request code'
  },
  'github-release-management': {
    keywords: ['release', 'deploy', 'publish', 'version', 'релиз', 'публикация'],
    confidence_threshold: 0.7,
    description: 'GitHub release management'
  },
  'swarm-orchestration': {
    keywords: ['swarm', 'multi-agent', 'coordinate', 'orchestrate', 'рой агентов'],
    confidence_threshold: 0.7,
    description: 'Multi-agent swarm orchestration'
  },
  'github-workflow-automation': {
    keywords: ['workflow', 'ci/cd', 'github actions', 'automation', 'автоматизация'],
    confidence_threshold: 0.7,
    description: 'GitHub workflow automation'
  },
  'reasoningbank-intelligence': {
    keywords: ['learning', 'intelligence', 'adaptive', 'обучение', 'адаптив'],
    confidence_threshold: 0.6,
    description: 'Adaptive learning with ReasoningBank'
  },
  'verification-quality': {
    keywords: ['verify', 'validate', 'quality', 'проверка', 'валидация'],
    confidence_threshold: 0.7,
    description: 'Code quality verification'
  }
};

/**
 * Простое keyword matching для определения similarity
 */
function calculateKeywordSimilarity(prompt, keywords) {
  const lowerPrompt = prompt.toLowerCase();
  let matchCount = 0;

  for (const keyword of keywords) {
    if (lowerPrompt.includes(keyword.toLowerCase())) {
      matchCount++;
    }
  }

  // Similarity = процент совпавших keywords
  return keywords.length > 0 ? matchCount / keywords.length : 0;
}

/**
 * Находит лучшие skills для промпта
 */
function findBestSkills(userPrompt, topK = 3) {
  const results = [];

  for (const [skillName, skillData] of Object.entries(SKILL_PATTERNS)) {
    const similarity = calculateKeywordSimilarity(
      userPrompt,
      skillData.keywords
    );

    results.push({
      skill: skillName,
      similarity,
      confidence_threshold: skillData.confidence_threshold,
      description: skillData.description,
      autoApply: similarity >= skillData.confidence_threshold
    });
  }

  // Сортируем по similarity (убывание)
  results.sort((a, b) => b.similarity - a.similarity);

  // Возвращаем топ K
  return results.slice(0, topK);
}

/**
 * Определяет нужно ли auto-apply skill
 */
function shouldAutoApply(userPrompt) {
  const topSkill = findBestSkills(userPrompt, 1)[0];

  if (topSkill && topSkill.similarity >= topSkill.confidence_threshold) {
    return {
      autoApply: true,
      skill: topSkill.skill,
      similarity: topSkill.similarity,
      reasoning: `Высокая уверенность (${(topSkill.similarity * 100).toFixed(1)}%) для skill: ${topSkill.skill}`
    };
  }

  return {
    autoApply: false,
    skill: null,
    similarity: topSkill ? topSkill.similarity : 0,
    reasoning: 'Недостаточная уверенность для auto-apply'
  };
}

/**
 * Генерация индекса skills (для будущего использования с embeddings)
 */
function generateSkillsIndex(outputPath = null) {
  const indexPath = outputPath || path.join(__dirname, '..', 'skills-index.json');

  const index = {
    generated_at: new Date().toISOString(),
    version: '1.0.0-mvp',
    method: 'keyword_matching',
    skills: {}
  };

  for (const [skillName, skillData] of Object.entries(SKILL_PATTERNS)) {
    index.skills[skillName] = {
      keywords: skillData.keywords,
      confidence_threshold: skillData.confidence_threshold,
      description: skillData.description
    };
  }

  fs.writeFileSync(indexPath, JSON.stringify(index, null, 2));
  console.error(`Skills index сохранён: ${indexPath}`);

  return index;
}

/**
 * CLI entry point
 */
function main() {
  const args = process.argv.slice(2);

  if (args.length === 0) {
    console.error('Использование: node skills-detector.js "<user prompt>" [--top-k N]');
    console.error('             node skills-detector.js --generate-index [output.json]');
    console.error('');
    console.error('Примеры:');
    console.error('  node skills-detector.js "Commit my changes"');
    console.error('  node skills-detector.js "Review this pull request" --top-k 5');
    console.error('  node skills-detector.js --generate-index');
    process.exit(1);
  }

  // Команда генерации индекса
  if (args[0] === '--generate-index') {
    const outputPath = args[1] || null;
    generateSkillsIndex(outputPath);
    return;
  }

  // Парсинг аргументов
  const userPrompt = args[0];
  let topK = 3;

  for (let i = 1; i < args.length; i++) {
    if (args[i] === '--top-k' && args[i + 1]) {
      topK = parseInt(args[i + 1]);
      i++;
    }
  }

  // Находим лучшие skills
  const bestSkills = findBestSkills(userPrompt, topK);
  const autoApplyDecision = shouldAutoApply(userPrompt);

  const result = {
    userPrompt,
    autoApplyDecision,
    topSkills: bestSkills
  };

  console.log(JSON.stringify(result, null, 2));
}

// Если запущен напрямую
if (require.main === module) {
  main();
}

module.exports = {
  findBestSkills,
  shouldAutoApply,
  generateSkillsIndex,
  SKILL_PATTERNS
};
