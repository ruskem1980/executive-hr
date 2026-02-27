#!/usr/bin/env python3
"""
Auto Prompt Tuner — автоматическая калибровка промптов на основе feedback.

Предоставляет:
- Запись результатов использования промптов (success/failure/score)
- Анализ причин неудач с группировкой по паттернам
- A/B тестирование вариантов промптов
- Автоматическая генерация улучшенных промптов
- Выбор лучшего промпта для типа задачи по истории

Использование:
    tuner = AutoPromptTuner()

    # Запись результатов
    tuner.record_result('p1', 'Напиши код...', 'coder', result='def foo()...', success=True, score=0.9)
    tuner.record_result('p2', 'Код для...', 'coder', result='', success=False, error='Пустой ответ')

    # Анализ
    analysis = tuner.analyze_failures(task_type='coder')
    improved = tuner.suggest_improvement('Напиши код...', 'coder')

    # A/B тесты
    test_id = tuner.ab_test('Вариант A', 'Вариант B', 'coder')
    results = tuner.get_ab_results(test_id)
"""

import os
import re
import sqlite3
import uuid
import math
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Any
from collections import Counter, defaultdict

PROJECT_ROOT = Path(__file__).parent.parent.parent


class AutoPromptTuner:
    """
    Автоматическая калибровка промптов на основе обратной связи.

    Собирает статистику по каждому промпту, выявляет паттерны
    неудач и предлагает улучшения на основе исторических данных.
    """

    # Известные паттерны ошибок и рекомендации по исправлению
    FAILURE_PATTERNS = {
        'empty_response': {
            'regex': r'(пуст|empty|no output|нет ответа|none)',
            'suggestion': 'Добавь явное требование: "Ты ОБЯЗАН вернуть ответ. Пустой ответ недопустим."',
        },
        'wrong_format': {
            'regex': r'(формат|format|json|markdown|структур)',
            'suggestion': 'Добавь чёткий пример ожидаемого формата ответа с шаблоном.',
        },
        'off_topic': {
            'regex': r'(не по теме|irrelevant|off.?topic|не связан)',
            'suggestion': 'Добавь ограничение: "Отвечай ТОЛЬКО на поставленную задачу. Не отклоняйся."',
        },
        'too_verbose': {
            'regex': r'(многослов|verbose|слишком длин|too long)',
            'suggestion': 'Добавь: "Ответ должен быть кратким и по существу. Макс N строк."',
        },
        'code_error': {
            'regex': r'(syntax|синтакс|ошибка.?компиляц|runtime|traceback|exception)',
            'suggestion': 'Добавь: "Проверь код на синтаксические ошибки перед ответом. '
                          'Верни ТОЛЬКО рабочий код."',
        },
        'missing_context': {
            'regex': r'(контекст|context|не хватает|missing|insufficient)',
            'suggestion': 'Предоставь больше контекста: описание файлов, зависимости, примеры.',
        },
        'hallucination': {
            'regex': r'(галлюцин|hallucin|выдум|несуществующ|invented)',
            'suggestion': 'Добавь: "Используй ТОЛЬКО предоставленную информацию. '
                          'Если не знаешь — скажи об этом."',
        },
        'incomplete': {
            'regex': r'(неполн|incomplete|не завершён|partial|обрезан|truncat)',
            'suggestion': 'Добавь: "Верни ПОЛНОЕ решение. Не сокращай и не обрезай ответ."',
        },
    }

    def __init__(self, db_path: str = 'data/prompt_tuning.db'):
        """
        Инициализация тюнера с базой результатов.

        Args:
            db_path: Путь к SQLite базе. Относительные пути
                     разрешаются от корня проекта.
        """
        if os.path.isabs(db_path):
            self.db_path = Path(db_path)
        else:
            self.db_path = PROJECT_ROOT / db_path

        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self) -> None:
        """Инициализация таблиц SQLite."""
        conn = sqlite3.connect(str(self.db_path))
        cursor = conn.cursor()

        # Результаты использования промптов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS prompt_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                prompt_id TEXT NOT NULL,
                prompt_text TEXT NOT NULL,
                task_type TEXT NOT NULL,
                result_text TEXT,
                success INTEGER NOT NULL DEFAULT 0,
                score REAL,
                error TEXT,
                created_at TEXT DEFAULT (datetime('now'))
            )
        """)

        # A/B тесты
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ab_tests (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id TEXT NOT NULL UNIQUE,
                task_type TEXT NOT NULL,
                prompt_a TEXT NOT NULL,
                prompt_b TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now')),
                status TEXT DEFAULT 'active'
            )
        """)

        # Результаты A/B тестов
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ab_results (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                test_id TEXT NOT NULL,
                variant TEXT NOT NULL,
                prompt_text TEXT NOT NULL,
                success INTEGER NOT NULL DEFAULT 0,
                score REAL,
                created_at TEXT DEFAULT (datetime('now')),
                FOREIGN KEY (test_id) REFERENCES ab_tests(test_id)
            )
        """)

        # Индексы для производительности
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_type
            ON prompt_results(task_type, success)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_results_prompt_id
            ON prompt_results(prompt_id)
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_ab_results_test
            ON ab_results(test_id, variant)
        """)

        conn.commit()
        conn.close()

    def _get_connection(self) -> sqlite3.Connection:
        """Создать соединение с БД."""
        return sqlite3.connect(str(self.db_path))

    def record_result(
        self,
        prompt_id: str,
        prompt_text: str,
        task_type: str,
        result: str,
        success: bool,
        score: Optional[float] = None,
        error: Optional[str] = None
    ) -> int:
        """
        Запись результата использования промпта.

        Args:
            prompt_id: Уникальный идентификатор промпта
            prompt_text: Текст промпта
            task_type: Тип задачи (coder, reviewer и т.д.)
            result: Текст результата (ответ модели)
            success: Успешно ли выполнена задача
            score: Оценка качества (0.0 - 1.0), опционально
            error: Текст ошибки при неудаче, опционально

        Returns:
            ID записи в базе
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO prompt_results
                (prompt_id, prompt_text, task_type, result_text, success, score, error)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                prompt_id,
                prompt_text,
                task_type,
                result,
                1 if success else 0,
                score,
                error,
            )
        )

        record_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return record_id

    def analyze_failures(
        self,
        task_type: Optional[str] = None,
        limit: int = 50
    ) -> Dict[str, Any]:
        """
        Анализ причин неудач промптов.

        Группирует ошибки по паттернам, считает failure rate
        и формирует рекомендации по улучшению.

        Args:
            task_type: Фильтр по типу задачи (None — все типы)
            limit: Максимальное количество записей для анализа

        Returns:
            Словарь:
            - common_patterns: найденные паттерны ошибок с частотой
            - failure_rate: процент неудач
            - total_records: общее число записей
            - failed_records: число неудачных записей
            - suggestions: список рекомендаций по улучшению
            - failure_rate_by_type: breakdown по типам задач
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Запрос неудачных записей
        if task_type:
            cursor.execute(
                """
                SELECT prompt_text, error, result_text, task_type
                FROM prompt_results
                WHERE success = 0 AND task_type = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (task_type, limit)
            )
        else:
            cursor.execute(
                """
                SELECT prompt_text, error, result_text, task_type
                FROM prompt_results
                WHERE success = 0
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (limit,)
            )

        failed_rows = cursor.fetchall()

        # Общая статистика
        if task_type:
            cursor.execute(
                "SELECT COUNT(*) FROM prompt_results WHERE task_type = ?",
                (task_type,)
            )
        else:
            cursor.execute("SELECT COUNT(*) FROM prompt_results")
        total = cursor.fetchone()[0]

        if task_type:
            cursor.execute(
                "SELECT COUNT(*) FROM prompt_results WHERE success = 0 AND task_type = ?",
                (task_type,)
            )
        else:
            cursor.execute(
                "SELECT COUNT(*) FROM prompt_results WHERE success = 0"
            )
        failed_total = cursor.fetchone()[0]

        # Failure rate по типам задач
        cursor.execute("""
            SELECT
                task_type,
                COUNT(*) as total,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failures
            FROM prompt_results
            GROUP BY task_type
        """)
        rate_by_type = {}
        for row in cursor.fetchall():
            t_type, t_total, t_failures = row
            rate_by_type[t_type] = {
                'total': t_total,
                'failures': t_failures,
                'failure_rate': round(t_failures / t_total, 4) if t_total else 0.0,
            }

        conn.close()

        # Анализ паттернов в ошибках
        pattern_counts = Counter()
        matched_suggestions = []

        for prompt_text, error_text, result_text, _ in failed_rows:
            combined = " ".join(filter(None, [error_text, result_text, prompt_text]))
            combined_lower = combined.lower()

            for pattern_name, pattern_info in self.FAILURE_PATTERNS.items():
                if re.search(pattern_info['regex'], combined_lower):
                    pattern_counts[pattern_name] += 1
                    if pattern_info['suggestion'] not in matched_suggestions:
                        matched_suggestions.append(pattern_info['suggestion'])

        # Анализ частых слов в неудачных промптах
        word_freq = self._analyze_word_frequency(
            [row[0] for row in failed_rows]
        )

        failure_rate = round(failed_total / total, 4) if total else 0.0

        return {
            'common_patterns': dict(pattern_counts.most_common()),
            'failure_rate': failure_rate,
            'total_records': total,
            'failed_records': failed_total,
            'suggestions': matched_suggestions,
            'failure_rate_by_type': rate_by_type,
            'frequent_words_in_failures': word_freq[:10],
        }

    def suggest_improvement(
        self,
        prompt_text: str,
        task_type: str,
        failure_patterns: Optional[List[str]] = None
    ) -> str:
        """
        Генерация улучшенного промпта на основе анализа неудач.

        Добавляет защитные инструкции, уточнения формата вывода
        и другие улучшения на основе выявленных паттернов ошибок.

        Args:
            prompt_text: Текущий текст промпта
            task_type: Тип задачи
            failure_patterns: Список конкретных паттернов ошибок (если известны).
                              Если не указаны — анализируются из БД.

        Returns:
            Улучшенный промпт
        """
        # Получить паттерны из анализа если не переданы
        if failure_patterns is None:
            analysis = self.analyze_failures(task_type=task_type)
            failure_patterns = list(analysis.get('common_patterns', {}).keys())

        # Собрать рекомендации для найденных паттернов
        improvements = []
        for pattern_name in failure_patterns:
            if pattern_name in self.FAILURE_PATTERNS:
                improvements.append(
                    self.FAILURE_PATTERNS[pattern_name]['suggestion']
                )

        # Сформировать улучшенный промпт
        parts = [prompt_text]

        if improvements:
            parts.append("\n## Дополнительные требования (автокалибровка)")
            for imp in improvements:
                parts.append(f"- {imp}")

        # Добавить общие улучшения для типа задачи
        type_improvements = self._get_type_specific_improvements(task_type)
        if type_improvements:
            parts.append("\n## Специфичные требования")
            for imp in type_improvements:
                parts.append(f"- {imp}")

        return "\n".join(parts)

    def ab_test(
        self,
        prompt_a: str,
        prompt_b: str,
        task_type: str
    ) -> str:
        """
        Создание A/B теста для двух вариантов промпта.

        Args:
            prompt_a: Текст варианта A
            prompt_b: Текст варианта B
            task_type: Тип задачи

        Returns:
            test_id — идентификатор для отслеживания результатов
        """
        test_id = f"ab_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{uuid.uuid4().hex[:6]}"

        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            INSERT INTO ab_tests (test_id, task_type, prompt_a, prompt_b)
            VALUES (?, ?, ?, ?)
            """,
            (test_id, task_type, prompt_a, prompt_b)
        )

        conn.commit()
        conn.close()
        return test_id

    def record_ab_result(
        self,
        test_id: str,
        variant: str,
        success: bool,
        score: Optional[float] = None
    ) -> None:
        """
        Запись результата A/B теста для конкретного варианта.

        Args:
            test_id: Идентификатор теста
            variant: Вариант ('A' или 'B')
            success: Успешность
            score: Оценка качества (0.0 - 1.0)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Получить текст промпта для варианта
        cursor.execute(
            "SELECT prompt_a, prompt_b FROM ab_tests WHERE test_id = ?",
            (test_id,)
        )
        row = cursor.fetchone()
        if not row:
            conn.close()
            return

        prompt_text = row[0] if variant.upper() == 'A' else row[1]

        cursor.execute(
            """
            INSERT INTO ab_results (test_id, variant, prompt_text, success, score)
            VALUES (?, ?, ?, ?, ?)
            """,
            (test_id, variant.upper(), prompt_text, 1 if success else 0, score)
        )

        conn.commit()
        conn.close()

    def get_ab_results(self, test_id: str) -> Dict[str, Any]:
        """
        Результаты A/B теста с определением победителя.

        Используется статистика: средний score, success rate,
        и доверительная оценка (confidence) на основе объёма данных.

        Args:
            test_id: Идентификатор теста

        Returns:
            Словарь:
            - variant_a_score: средний score варианта A
            - variant_b_score: средний score варианта B
            - variant_a_success_rate: success rate варианта A
            - variant_b_success_rate: success rate варианта B
            - winner: 'A', 'B' или 'inconclusive'
            - confidence: уровень уверенности (0.0 - 1.0)
            - total_samples_a: число замеров для A
            - total_samples_b: число замеров для B
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Проверить существование теста
        cursor.execute(
            "SELECT task_type, status FROM ab_tests WHERE test_id = ?",
            (test_id,)
        )
        test_row = cursor.fetchone()
        if not test_row:
            conn.close()
            return {
                'error': f'Тест {test_id} не найден',
                'winner': 'inconclusive',
                'confidence': 0.0,
            }

        # Собрать статистику по вариантам
        results = {}
        for variant in ('A', 'B'):
            cursor.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(success) as successes,
                    AVG(score) as avg_score
                FROM ab_results
                WHERE test_id = ? AND variant = ?
                """,
                (test_id, variant)
            )
            row = cursor.fetchone()
            total, successes, avg_score = row

            results[variant] = {
                'total': total or 0,
                'successes': successes or 0,
                'avg_score': round(avg_score, 4) if avg_score else 0.0,
                'success_rate': round((successes or 0) / total, 4) if total else 0.0,
            }

        conn.close()

        # Определение победителя
        winner, confidence = self._determine_winner(results)

        return {
            'test_id': test_id,
            'task_type': test_row[0],
            'status': test_row[1],
            'variant_a_score': results['A']['avg_score'],
            'variant_b_score': results['B']['avg_score'],
            'variant_a_success_rate': results['A']['success_rate'],
            'variant_b_success_rate': results['B']['success_rate'],
            'total_samples_a': results['A']['total'],
            'total_samples_b': results['B']['total'],
            'winner': winner,
            'confidence': confidence,
        }

    def get_best_prompt(self, task_type: str) -> Optional[str]:
        """
        Лучший промпт для типа задачи по историческим данным.

        Выбирает промпт с наивысшим средним score среди
        успешных результатов (минимум 2 использования).

        Args:
            task_type: Тип задачи

        Returns:
            Текст лучшего промпта или None если данных нет
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute(
            """
            SELECT prompt_text, AVG(score) as avg_score, COUNT(*) as uses
            FROM prompt_results
            WHERE task_type = ? AND success = 1 AND score IS NOT NULL
            GROUP BY prompt_text
            HAVING COUNT(*) >= 2
            ORDER BY avg_score DESC
            LIMIT 1
            """,
            (task_type,)
        )

        row = cursor.fetchone()
        conn.close()

        if row:
            return row[0]

        # Fallback: если нет промптов с 2+ использованиями, берём лучший единичный
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT prompt_text
            FROM prompt_results
            WHERE task_type = ? AND success = 1
            ORDER BY score DESC
            LIMIT 1
            """,
            (task_type,)
        )
        row = cursor.fetchone()
        conn.close()

        return row[0] if row else None

    def calibration_report(self) -> Dict[str, Any]:
        """
        Общий отчёт по калибровке всех типов задач.

        Returns:
            Словарь:
            - total_records: общее число записей
            - overall_success_rate: общий success rate
            - by_task_type: статистика по каждому типу задачи
            - active_ab_tests: число активных A/B тестов
            - top_failure_patterns: самые частые паттерны ошибок
            - improvement_potential: потенциал улучшения (%)
        """
        conn = self._get_connection()
        cursor = conn.cursor()

        # Общая статистика
        cursor.execute("SELECT COUNT(*) FROM prompt_results")
        total = cursor.fetchone()[0]

        cursor.execute(
            "SELECT COUNT(*) FROM prompt_results WHERE success = 1"
        )
        successes = cursor.fetchone()[0]

        # По типам задач
        cursor.execute("""
            SELECT
                task_type,
                COUNT(*) as total,
                SUM(success) as successes,
                ROUND(AVG(score), 4) as avg_score,
                ROUND(AVG(CASE WHEN success = 1 THEN score END), 4) as avg_success_score
            FROM prompt_results
            GROUP BY task_type
            ORDER BY task_type
        """)

        by_type = {}
        for row in cursor.fetchall():
            t_type, t_total, t_successes, t_avg_score, t_avg_success_score = row
            by_type[t_type] = {
                'total': t_total,
                'successes': t_successes or 0,
                'success_rate': round((t_successes or 0) / t_total, 4) if t_total else 0.0,
                'avg_score': t_avg_score or 0.0,
                'avg_success_score': t_avg_success_score or 0.0,
            }

        # Активные A/B тесты
        cursor.execute(
            "SELECT COUNT(*) FROM ab_tests WHERE status = 'active'"
        )
        active_tests = cursor.fetchone()[0]

        conn.close()

        # Анализ паттернов ошибок
        failure_analysis = self.analyze_failures()
        top_patterns = failure_analysis.get('common_patterns', {})

        # Потенциал улучшения: разница между лучшим и средним success rate
        if by_type:
            rates = [v['success_rate'] for v in by_type.values() if v['total'] >= 3]
            if rates:
                best = max(rates)
                avg = sum(rates) / len(rates)
                improvement_potential = round((best - avg) * 100, 1)
            else:
                improvement_potential = 0.0
        else:
            improvement_potential = 0.0

        return {
            'total_records': total,
            'overall_success_rate': round(successes / total, 4) if total else 0.0,
            'by_task_type': by_type,
            'active_ab_tests': active_tests,
            'top_failure_patterns': top_patterns,
            'improvement_potential': improvement_potential,
        }

    # ------------------------------------------------------------------
    # Внутренние методы
    # ------------------------------------------------------------------

    def _analyze_word_frequency(
        self,
        texts: List[str]
    ) -> List[tuple]:
        """
        Анализ частотности слов в текстах.

        Исключает стоп-слова и короткие слова.

        Args:
            texts: Список текстов для анализа

        Returns:
            Список кортежей (слово, частота) по убыванию
        """
        stop_words = {
            'в', 'на', 'и', 'или', 'для', 'из', 'по', 'от', 'не', 'это',
            'что', 'как', 'все', 'при', 'так', 'то', 'но', 'уже', 'бы',
            'если', 'же', 'ли', 'к', 'до', 'за', 'без', 'под', 'над',
            'the', 'a', 'an', 'is', 'are', 'was', 'were', 'be', 'to',
            'of', 'and', 'in', 'that', 'for', 'it', 'with', 'as', 'on',
        }

        word_counter = Counter()
        for text in texts:
            if not text:
                continue
            words = re.findall(r'[a-zA-Zа-яА-ЯёЁ]{4,}', text.lower())
            for word in words:
                if word not in stop_words:
                    word_counter[word] += 1

        return word_counter.most_common(20)

    def _get_type_specific_improvements(
        self,
        task_type: str
    ) -> List[str]:
        """
        Специфичные улучшения для конкретного типа задачи.

        Args:
            task_type: Тип задачи

        Returns:
            Список строк-рекомендаций
        """
        improvements_map = {
            'coder': [
                'Верни ТОЛЬКО код без пояснений, если не просят иначе.',
                'Комментарии в коде на русском языке.',
                'Обработай граничные случаи и невалидные входы.',
            ],
            'reviewer': [
                'Структурируй ответ: проблемы, рекомендации, итог.',
                'Укажи конкретные строки кода, которые нужно изменить.',
                'Оцени серьёзность каждой найденной проблемы.',
            ],
            'tester': [
                'Используй pytest как фреймворк тестирования.',
                'Включи тесты для граничных случаев и ошибок.',
                'Каждый тест должен проверять ОДНУ вещь.',
            ],
            'architect': [
                'Используй диаграммы или структурированные списки.',
                'Обоснуй каждое архитектурное решение.',
                'Укажи потенциальные риски и ограничения.',
            ],
        }

        return improvements_map.get(task_type, [])

    def _determine_winner(
        self,
        results: Dict[str, Dict]
    ) -> tuple:
        """
        Определение победителя A/B теста.

        Использует комбинацию success rate и avg score.
        Confidence рассчитывается на основе объёма данных.

        Args:
            results: Словарь {'A': {...}, 'B': {...}} со статистикой

        Returns:
            Кортеж (winner: str, confidence: float)
        """
        a = results['A']
        b = results['B']

        # Минимальный объём данных для вывода
        min_samples = 5
        if a['total'] < min_samples or b['total'] < min_samples:
            # Недостаточно данных — если совсем мало, inconclusive
            if a['total'] < 2 and b['total'] < 2:
                return 'inconclusive', 0.0

            # Предварительный результат с низкой уверенностью
            total = a['total'] + b['total']
            confidence = min(total / (min_samples * 2), 0.5)
        else:
            # Достаточно данных — считаем confidence
            total = a['total'] + b['total']
            confidence = min(total / 30, 1.0)  # 30 замеров = 100% confidence

        # Комбинированный скор: 60% success rate + 40% avg score
        score_a = a['success_rate'] * 0.6 + a['avg_score'] * 0.4
        score_b = b['success_rate'] * 0.6 + b['avg_score'] * 0.4

        # Минимальная разница для определения победителя
        min_diff = 0.05
        diff = abs(score_a - score_b)

        if diff < min_diff:
            return 'inconclusive', confidence * 0.5

        winner = 'A' if score_a > score_b else 'B'

        # Скорректировать confidence на основе величины разницы
        confidence = confidence * min(diff / 0.2, 1.0)

        return winner, round(confidence, 4)
