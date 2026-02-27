#!/usr/bin/env python3
"""
Prompt Builder - Сборка промптов из templates с учетом сложности и контекста

Процесс сборки:
1. Загрузить base template (base_coder.md)
2. Добавить complexity additions из complexity_additions.json
3. Добавить context additions из context_additions.json
4. Вернуть финальный промпт

Пример использования:
    prompt = build_prompt(
        agent_type='coder',
        complexity='medium',
        context={'task_description': 'Реализовать API endpoint', 'context_type': 'api'}
    )
"""

import os
import json
from pathlib import Path
from typing import Dict, List, Optional

PROJECT_ROOT = Path(__file__).parent.parent.parent
TEMPLATES_DIR = PROJECT_ROOT / "prompts" / "templates"


def load_base_template(agent_type: str) -> str:
    """
    Загружает базовый template для агента

    Args:
        agent_type: Тип агента (coder, reviewer, tester, etc.)

    Returns:
        Содержимое базового template

    Raises:
        FileNotFoundError: Если template не найден
    """
    template_path = TEMPLATES_DIR / f"base_{agent_type}.md"

    if not template_path.exists():
        raise FileNotFoundError(
            f"Template для агента '{agent_type}' не найден: {template_path}"
        )

    with open(template_path, 'r', encoding='utf-8') as f:
        return f.read()


def load_complexity_additions(complexity: str) -> List[str]:
    """
    Загружает дополнения для заданной сложности

    Args:
        complexity: Уровень сложности (simple, medium, complex, very_complex)

    Returns:
        Список строк-дополнений для промпта
    """
    additions_path = TEMPLATES_DIR / "complexity_additions.json"

    if not additions_path.exists():
        return []

    with open(additions_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get(complexity, {}).get("additions", [])


def load_context_additions(context_type: Optional[str]) -> List[str]:
    """
    Загружает дополнения для заданного контекста

    Args:
        context_type: Тип контекста (security, performance, api, testing, etc.)

    Returns:
        Список строк-дополнений для промпта
    """
    if not context_type:
        return []

    additions_path = TEMPLATES_DIR / "context_additions.json"

    if not additions_path.exists():
        return []

    with open(additions_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    return data.get(context_type, {}).get("additions", [])


def build_prompt(
    agent_type: str,
    complexity: str,
    context: Optional[Dict] = None
) -> str:
    """
    Собирает финальный промпт из базового template и additions

    Args:
        agent_type: Тип агента (coder, reviewer, tester)
        complexity: Уровень сложности (simple, medium, complex, very_complex)
        context: Словарь с контекстом:
            - task_description: Описание задачи
            - context_type: Тип контекста (security, performance, api, etc.)
            - additional_instructions: Дополнительные инструкции

    Returns:
        Финальный промпт готовый для отправки LLM

    Example:
        >>> prompt = build_prompt(
        ...     agent_type='coder',
        ...     complexity='medium',
        ...     context={
        ...         'task_description': 'Создать REST API endpoint для users',
        ...         'context_type': 'api'
        ...     }
        ... )
    """
    context = context or {}

    # ШАГ 1: Загрузить базовый template
    base_prompt = load_base_template(agent_type)

    # ШАГ 2: Добавить complexity additions
    complexity_additions = load_complexity_additions(complexity)

    # ШАГ 3: Добавить context additions
    context_type = context.get('context_type')
    context_additions = load_context_additions(context_type)

    # ШАГ 4: Собрать финальный промпт
    parts = [base_prompt]

    # Добавляем complexity additions
    if complexity_additions:
        parts.append("\n## Сложность задачи: " + complexity)
        parts.append("\n".join(complexity_additions))

    # Добавляем context additions
    if context_additions:
        parts.append("\n## Контекст задачи")
        parts.append("\n".join(context_additions))

    # Добавляем саму задачу
    task_description = context.get('task_description', '')
    if task_description:
        parts.append(f"\n## Задача\n\n{task_description}")

    # Добавляем дополнительный контекст если есть
    additional_context = context.get('additional_context', '')
    if additional_context:
        parts.append(f"\n## Дополнительный контекст\n\n{additional_context}")

    # Дополнительные инструкции
    additional_instructions = context.get('additional_instructions', '')
    if additional_instructions:
        parts.append(f"\n## Дополнительные требования\n\n{additional_instructions}")

    return "\n\n".join(parts)


def estimate_prompt_tokens(prompt: str) -> int:
    """
    Оценка количества токенов в промпте

    Приблизительная формула: 1 токен ≈ 4 символа

    Args:
        prompt: Текст промпта

    Returns:
        Оценка количества токенов
    """
    return len(prompt) // 4


def validate_prompt(prompt: str, max_tokens: int = 4000) -> Dict:
    """
    Валидация промпта перед отправкой

    Args:
        prompt: Текст промпта
        max_tokens: Максимально допустимое количество токенов

    Returns:
        Словарь с результатом валидации:
        {
            'valid': bool,
            'estimated_tokens': int,
            'warnings': List[str]
        }
    """
    estimated_tokens = estimate_prompt_tokens(prompt)
    warnings = []

    # Проверка длины
    if estimated_tokens > max_tokens:
        warnings.append(
            f"Промпт слишком длинный: {estimated_tokens} токенов (макс {max_tokens})"
        )

    # Проверка на пустоту
    if not prompt.strip():
        warnings.append("Промпт пустой")

    # Проверка на наличие задачи
    if "## Задача" not in prompt:
        warnings.append("Промпт не содержит описание задачи")

    return {
        'valid': len(warnings) == 0,
        'estimated_tokens': estimated_tokens,
        'warnings': warnings
    }


def main():
    """CLI для тестирования prompt builder"""
    import argparse

    parser = argparse.ArgumentParser(description="Prompt Builder - сборка промптов из templates")
    parser.add_argument('--agent-type', type=str, default='coder', help='Тип агента')
    parser.add_argument('--complexity', type=str, default='medium',
                       choices=['simple', 'medium', 'complex', 'very_complex'],
                       help='Уровень сложности')
    parser.add_argument('--context-type', type=str,
                       choices=['security', 'performance', 'database', 'api', 'testing', 'frontend', 'refactoring'],
                       help='Тип контекста')
    parser.add_argument('--task', type=str, help='Описание задачи')
    parser.add_argument('--output', type=str, help='Путь для сохранения промпта')
    parser.add_argument('--validate', action='store_true', help='Валидировать промпт')

    args = parser.parse_args()

    context = {}
    if args.context_type:
        context['context_type'] = args.context_type
    if args.task:
        context['task_description'] = args.task

    # Собрать промпт
    prompt = build_prompt(
        agent_type=args.agent_type,
        complexity=args.complexity,
        context=context
    )

    # Валидация
    if args.validate:
        validation = validate_prompt(prompt)
        print(f"\n{'✅' if validation['valid'] else '❌'} Валидация:")
        print(f"  Токенов: ~{validation['estimated_tokens']}")
        if validation['warnings']:
            print("  Предупреждения:")
            for warning in validation['warnings']:
                print(f"    - {warning}")
        print()

    # Вывод/сохранение
    if args.output:
        with open(args.output, 'w', encoding='utf-8') as f:
            f.write(prompt)
        print(f"Промпт сохранён в {args.output}")
    else:
        print("="*80)
        print("СГЕНЕРИРОВАННЫЙ ПРОМПТ:")
        print("="*80)
        print(prompt)
        print("="*80)


if __name__ == "__main__":
    main()
