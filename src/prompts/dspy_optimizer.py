#!/usr/bin/env python3
"""
DSPy Optimizer — оптимизация промптов через DSPy-подобную парадигму.

Предоставляет:
- Few-shot подбор примеров из базы для улучшения промптов
- Chain-of-Thought обёртка для структурированного рассуждения
- Teacher-Student дистилляция reasoning от мощной модели к лёгкой
- DSPy-подобные сигнатуры (input/output контракты)

Работает БЕЗ жёсткой зависимости от библиотеки dspy — если она
не установлена, используется встроенная реализация.

Использование:
    optimizer = DSPyOptimizer()
    optimizer.add_example('coder', 'Добавь валидацию email', 'def validate_email(...)', score=0.95)
    optimized = optimizer.optimize_prompt('Напиши функцию', task_type='coder')
"""

import os
import sqlite3
import json
import hashlib
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Callable, Any

# Попытка импортировать dspy для расширенной функциональности
_DSPY_AVAILABLE = False
try:
    import dspy
    _DSPY_AVAILABLE = True
except ImportError:
    pass

PROJECT_ROOT = Path(__file__).parent.parent.parent


class DSPyOptimizer:
    """
    Оптимизатор промптов через DSPy-подобную парадигму.

    Основные возможности:
    - Few-shot: автоподбор лучших примеров по score и task_type
    - Chain-of-Thought: структурирование рассуждения
    - Teacher-Student: дистилляция знаний в компактный промпт
    - Сигнатуры: формализация input/output контракта промпта
    """

    # Шаблоны Chain-of-Thought для разных типов задач
    COT_TEMPLATES = {
        'coder': (
            "Рассуждай шаг за шагом перед написанием кода:\n"
            "1. Определи входные данные и ожидаемый результат\n"
            "2. Продумай алгоритм решения\n"
            "3. Учти граничные случаи и обработку ошибок\n"
            "4. Напиши чистый, читаемый код\n"
        ),
        'reviewer': (
            "Рассуждай шаг за шагом при ревью кода:\n"
            "1. Проверь корректность логики\n"
            "2. Оцени безопасность и обработку ошибок\n"
            "3. Проверь производительность и масштабируемость\n"
            "4. Оцени читаемость и следование конвенциям\n"
        ),
        'tester': (
            "Рассуждай шаг за шагом при написании тестов:\n"
            "1. Определи основные сценарии использования\n"
            "2. Определи граничные случаи\n"
            "3. Определи негативные сценарии (невалидные входы)\n"
            "4. Напиши тесты от простых к сложным\n"
        ),
        'default': (
            "Рассуждай шаг за шагом:\n"
            "1. Проанализируй входные данные\n"
            "2. Определи план действий\n"
            "3. Выполни задачу последовательно\n"
            "4. Проверь результат\n"
        ),
    }

    def __init__(self, examples_db_path: str = 'data/prompt_examples.db'):
        """
        Инициализация оптимизатора с базой примеров.

        Args:
            examples_db_path: Путь к SQLite базе с примерами для few-shot.
                              Относительные пути разрешаются от корня проекта.
        """
        if os.path.isabs(examples_db_path):
            self.db_path = Path(examples_db_path)
        else:
            self.db_path = PROJECT_ROOT / examples_db_path

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

        # Счётчики для статистики
        self._stats = {
            'optimizations': 0,
            'examples_added': 0,
            'cot_applied': 0,
            'distillations': 0,
            'signatures_created': 0,
        }

    def _init_db(self) -> None:
        """Инициализация SQLite базы с таблицей примеров."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        cursor.execute("""
            CREATE TABLE IF NOT EXISTS examples (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                task_type TEXT NOT NULL,
                input_text TEXT NOT NULL,
                output_text TEXT NOT NULL,
                score REAL DEFAULT 1.0,
                embedding BLOB,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # Индекс для быстрого поиска по task_type + score
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_examples_type_score
            ON examples(task_type, score DESC)
        """)

        conn.commit()
        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """Создать соединение с БД."""
        return sqlite3.connect(str(self.db_path))

    def add_example(
        self,
        task_type: str,
        input_text: str,
        output_text: str,
        score: float = 1.0
    ) -> int:
        """
        Добавление примера в базу для few-shot обучения.

        Args:
            task_type: Тип задачи (coder, reviewer, tester и т.д.)
            input_text: Входной текст (промпт/задача)
            output_text: Ожидаемый выход (ответ/код)
            score: Оценка качества примера (0.0 - 1.0)

        Returns:
            ID добавленного примера
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO examples (task_type, input_text, output_text, score)
            VALUES (?, ?, ?, ?)
            """,
            (task_type, input_text, output_text, min(max(score, 0.0), 1.0))
        )

        example_id = cursor.lastrowid
        conn.commit()
        conn.close()

        self._stats['examples_added'] += 1
        return example_id

    def bootstrap_few_shot(
        self,
        task_type: str,
        n_examples: int = 3
    ) -> List[Dict[str, Any]]:
        """
        Автоматический подбор лучших примеров для указанного task_type.

        Выбирает top-N примеров с наивысшим score. Если примеров
        недостаточно, возвращает все доступные.

        Args:
            task_type: Тип задачи для подбора примеров
            n_examples: Количество примеров (по умолчанию 3)

        Returns:
            Список словарей с полями: input, output, score
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT input_text, output_text, score
            FROM examples
            WHERE task_type = ?
            ORDER BY score DESC, created_at DESC
            LIMIT ?
            """,
            (task_type, n_examples)
        )

        rows = cursor.fetchall()
        conn.close()

        return [
            {
                'input': row[0],
                'output': row[1],
                'score': row[2],
            }
            for row in rows
        ]

    def optimize_prompt(
        self,
        base_prompt: str,
        task_type: str,
        examples: Optional[List[Dict]] = None,
        metric_fn: Optional[Callable] = None
    ) -> str:
        """
        Оптимизация промпта: добавление few-shot примеров и CoT.

        Процесс:
        1. Подбор few-shot примеров из базы (или использование переданных)
        2. Структурирование через Chain-of-Thought
        3. Сборка финального оптимизированного промпта

        Args:
            base_prompt: Базовый промпт для оптимизации
            task_type: Тип задачи (coder, reviewer и т.д.)
            examples: Пользовательские примеры (если не указаны, берутся из БД)
            metric_fn: Функция метрики для оценки качества (опционально).
                       Принимает (prompt, examples) -> float

        Returns:
            Оптимизированный промпт
        """
        # Подбор примеров
        if examples is None:
            examples = self.bootstrap_few_shot(task_type)

        # Сборка блока few-shot примеров
        few_shot_block = self._build_few_shot_block(examples)

        # Chain-of-Thought обёртка
        cot_block = self._get_cot_template(task_type)

        # Сборка финального промпта
        parts = []

        # Системная инструкция CoT
        if cot_block:
            parts.append(cot_block)

        # Few-shot примеры
        if few_shot_block:
            parts.append(few_shot_block)

        # Основной промпт
        parts.append(base_prompt)

        optimized = "\n\n".join(parts)

        # Если передана функция метрики — оценить
        if metric_fn is not None:
            try:
                score = metric_fn(optimized, examples)
                # Можно использовать score для логирования или итеративной оптимизации
                self._stats['last_metric_score'] = score
            except Exception:
                pass

        self._stats['optimizations'] += 1
        return optimized

    def chain_of_thought(
        self,
        prompt: str,
        task_type: Optional[str] = None
    ) -> str:
        """
        Обёртка промпта в Chain-of-Thought паттерн.

        Добавляет инструкцию для пошагового рассуждения
        перед выполнением задачи.

        Args:
            prompt: Исходный промпт
            task_type: Тип задачи для выбора специфичного CoT шаблона

        Returns:
            Промпт с CoT обёрткой
        """
        cot_template = self._get_cot_template(task_type)

        result = f"{cot_template}\n\n{prompt}"
        self._stats['cot_applied'] += 1
        return result

    def teacher_student_distill(
        self,
        teacher_prompt: str,
        teacher_response: str,
        student_model: str = 'flash'
    ) -> str:
        """
        Дистилляция reasoning от мощной модели (Teacher) в промпт для лёгкой (Student).

        Извлекает цепочку рассуждений из ответа Teacher-модели и компрессирует
        в набор конкретных инструкций, которые Student-модель сможет выполнить.

        Args:
            teacher_prompt: Промпт, который был отправлен Teacher-модели
            teacher_response: Ответ Teacher-модели (с reasoning)
            student_model: Целевая Student-модель ('flash' или 'pro')

        Returns:
            Дистиллированный промпт для Student-модели
        """
        # Извлечение ключевых шагов рассуждения
        reasoning_steps = self._extract_reasoning_steps(teacher_response)

        # Формирование компактного промпта для Student
        parts = [
            f"# Инструкции (дистилляция от экспертной модели)\n",
        ]

        if reasoning_steps:
            parts.append("## Пошаговый план выполнения")
            for i, step in enumerate(reasoning_steps, 1):
                parts.append(f"{i}. {step}")
            parts.append("")

        # Добавляем исходную задачу
        parts.append("## Задача")
        parts.append(teacher_prompt)

        # Если student_model это flash — добавить ограничения для компактности
        if student_model == 'flash':
            parts.append("\n## Требования к ответу")
            parts.append("- Верни ТОЛЬКО результат без дополнительных рассуждений")
            parts.append("- Следуй пошаговому плану выше")
            parts.append("- Комментарии на русском языке")

        self._stats['distillations'] += 1
        return "\n".join(parts)

    def create_signature(
        self,
        input_fields: Dict[str, str],
        output_fields: Dict[str, str],
        instructions: str = ''
    ) -> Dict[str, Any]:
        """
        Создание DSPy-подобной сигнатуры (input/output контракт).

        Сигнатура определяет формальный контракт промпта: какие поля
        ожидаются на входе, какие на выходе, и какие инструкции применяются.

        Args:
            input_fields: Словарь {имя_поля: описание} для входных данных
            output_fields: Словарь {имя_поля: описание} для выходных данных
            instructions: Дополнительные инструкции для сигнатуры

        Returns:
            Словарь-сигнатура с полями: input_fields, output_fields,
            instructions, prompt_template, signature_id
        """
        # Генерация шаблона промпта из сигнатуры
        prompt_parts = []

        if instructions:
            prompt_parts.append(f"# Инструкции\n{instructions}")

        # Входные поля
        prompt_parts.append("# Входные данные")
        for field_name, field_desc in input_fields.items():
            prompt_parts.append(f"- **{field_name}**: {field_desc}")

        # Выходные поля
        prompt_parts.append("\n# Ожидаемый формат ответа")
        for field_name, field_desc in output_fields.items():
            prompt_parts.append(f"- **{field_name}**: {field_desc}")

        prompt_template = "\n".join(prompt_parts)

        # Создание уникального ID для сигнатуры
        sig_content = json.dumps(
            {'in': input_fields, 'out': output_fields, 'inst': instructions},
            sort_keys=True
        )
        signature_id = hashlib.sha256(sig_content.encode()).hexdigest()[:12]

        self._stats['signatures_created'] += 1

        return {
            'signature_id': signature_id,
            'input_fields': input_fields,
            'output_fields': output_fields,
            'instructions': instructions,
            'prompt_template': prompt_template,
        }

    def get_optimization_stats(self) -> Dict[str, Any]:
        """
        Статистика работы оптимизатора.

        Returns:
            Словарь с метриками:
            - optimizations: число оптимизаций
            - examples_added: число добавленных примеров
            - examples_in_db: общее число примеров в базе
            - cot_applied: число применений CoT
            - distillations: число дистилляций
            - signatures_created: число созданных сигнатур
            - task_types: список типов задач в базе примеров
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Общее количество примеров
        cursor.execute("SELECT COUNT(*) FROM examples")
        total_examples = cursor.fetchone()[0]

        # Типы задач
        cursor.execute("SELECT DISTINCT task_type FROM examples ORDER BY task_type")
        task_types = [row[0] for row in cursor.fetchall()]

        # Средний score по типам
        cursor.execute("""
            SELECT task_type, COUNT(*), ROUND(AVG(score), 3)
            FROM examples
            GROUP BY task_type
            ORDER BY task_type
        """)
        type_stats = {
            row[0]: {'count': row[1], 'avg_score': row[2]}
            for row in cursor.fetchall()
        }

        conn.close()

        return {
            **self._stats,
            'examples_in_db': total_examples,
            'task_types': task_types,
            'type_stats': type_stats,
            'dspy_available': _DSPY_AVAILABLE,
        }

    # ------------------------------------------------------------------
    # Внутренние методы
    # ------------------------------------------------------------------

    def _get_cot_template(self, task_type: Optional[str] = None) -> str:
        """Получить шаблон Chain-of-Thought для типа задачи."""
        if task_type and task_type in self.COT_TEMPLATES:
            return self.COT_TEMPLATES[task_type]
        return self.COT_TEMPLATES['default']

    def _build_few_shot_block(self, examples: List[Dict]) -> str:
        """
        Сборка блока few-shot примеров для вставки в промпт.

        Args:
            examples: Список примеров [{input, output, score}, ...]

        Returns:
            Форматированный блок примеров или пустая строка
        """
        if not examples:
            return ""

        parts = ["## Примеры выполнения"]

        for i, ex in enumerate(examples, 1):
            inp = ex.get('input', '')
            out = ex.get('output', '')
            parts.append(f"\n### Пример {i}")
            parts.append(f"**Задача:** {inp}")
            parts.append(f"**Результат:**\n{out}")

        return "\n".join(parts)

    def _extract_reasoning_steps(self, teacher_response: str) -> List[str]:
        """
        Извлечение шагов рассуждения из ответа Teacher-модели.

        Ищет пронумерованные шаги, маркеры «шаг», «step», а также
        структуру «сначала ... затем ... наконец».

        Args:
            teacher_response: Полный ответ Teacher-модели

        Returns:
            Список извлечённых шагов рассуждения
        """
        steps = []
        lines = teacher_response.strip().split('\n')

        for line in lines:
            stripped = line.strip()
            if not stripped:
                continue

            # Пронумерованные шаги: "1.", "2)", "1:"
            if (
                len(stripped) > 2
                and stripped[0].isdigit()
                and stripped[1] in '.):'
            ):
                # Убираем номер и разделитель
                step_text = stripped[2:].strip()
                if step_text:
                    steps.append(step_text)
                continue

            # Маркеры с тире или звёздочкой
            if stripped.startswith(('- ', '* ', '• ')):
                step_text = stripped[2:].strip()
                if step_text and len(step_text) > 10:
                    steps.append(step_text)
                continue

            # Ключевые слова рассуждения
            lower = stripped.lower()
            reasoning_markers = [
                'сначала', 'затем', 'далее', 'потом', 'наконец',
                'во-первых', 'во-вторых', 'в-третьих',
                'first', 'then', 'next', 'finally',
                'шаг ', 'step ',
            ]
            if any(lower.startswith(marker) for marker in reasoning_markers):
                steps.append(stripped)

        # Если не нашли структурированных шагов — берём первые содержательные строки
        if not steps:
            for line in lines:
                stripped = line.strip()
                if stripped and len(stripped) > 20 and not stripped.startswith('#'):
                    steps.append(stripped)
                    if len(steps) >= 5:
                        break

        return steps
