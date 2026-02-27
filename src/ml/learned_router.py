"""
Адаптивный ML роутер задач, обучающийся на исторических данных маршрутизации.

Вдохновлён подходом Microsoft BEST-Route: выбор оптимальной модели и стратегии
выполнения на основе сложности запроса, исторических результатов и стоимости.

Стратегии:
- single_shot: один вызов оптимальной модели (простые задачи)
- multi_sample: N вызовов дешёвой модели + голосование (средние задачи)
- cascade: сначала дешёвая модель, при низкой уверенности — дороже (неопределённость)
"""

import os
import re
import uuid
import sqlite3
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Dict, List, Any

import numpy as np

logger = logging.getLogger(__name__)


# ── Стоимость моделей (USD за 1M токенов) ──

MODEL_PRICING = {
    'flash': {'input': 0.50, 'output': 3.00, 'name': 'Gemini Flash'},
    'pro': {'input': 2.00, 'output': 12.00, 'name': 'Gemini Pro'},
    'sonnet': {'input': 3.00, 'output': 15.00, 'name': 'Claude Sonnet 4.5'},
    'opus': {'input': 15.00, 'output': 75.00, 'name': 'Claude Opus 4.6'},
}

# Ранжирование моделей по стоимости (от дешёвой к дорогой)
MODEL_COST_ORDER = ['flash', 'pro', 'sonnet', 'opus']

# Средняя оценка качества по умолчанию (до обучения)
DEFAULT_MODEL_QUALITY = {
    'flash': 0.65,
    'pro': 0.80,
    'sonnet': 0.85,
    'opus': 0.95,
}


@dataclass
class RoutingDecision:
    """Решение маршрутизации — какую модель и стратегию использовать."""

    decision_id: str
    model: str                    # Рекомендуемая модель: flash / pro / sonnet / opus
    strategy: str                 # single_shot / multi_sample / cascade
    n_samples: int                # Количество попыток (для multi_sample)
    fallback_chain: List[str]     # Цепочка fallback моделей (для cascade)
    confidence: float             # Уверенность в решении (0-1)
    estimated_cost: float         # Оценка стоимости в USD
    reasoning: str                # Объяснение выбора на русском


class LearnedRouter:
    """
    Адаптивный роутер, обучающийся на исторических данных маршрутизации.

    При малом количестве данных (<50 решений) использует rule-based эвристику.
    После накопления достаточной статистики переключается на ML модель
    (RandomForest / GradientBoosting) для предсказания оптимальной модели.
    """

    # ── Ключевые слова для feature engineering ──

    PROGRAM_KEYWORDS = [
        'отчёт', 'отчет', 'статистик', 'покажи', 'список', 'показать',
        'валидац', 'провер', 'lint', 'format', 'pytest', 'тест запуст',
        'npm test', 'benchmark', 'синхрониз', 'coverage', 'расход',
    ]

    COMPLEX_KEYWORDS = [
        'архитектур', 'рефактор', 'миграц', 'безопасн', 'security',
        'производительн', 'оптимизац', 'переписать', 'distributed',
        'микросервис', 'cqrs', 'event-driven', 'шифрован', 'аудит',
    ]

    MEDIUM_KEYWORDS = [
        'api endpoint', 'endpoint', 'модуль', 'компонент', 'фич',
        'интеграц', 'middleware', 'crud', 'webhook', 'jwt', 'oauth',
        'pydantic', 'кеширован', 'redis', 'e2e тест',
    ]

    CODE_MARKERS = [
        'def ', 'class ', 'function ', 'import ', 'async ', 'await ',
        'const ', 'let ', 'var ', '=>', '{}', '[]', 'return ',
    ]

    def __init__(self, db_path: str = 'data/routing_history.db'):
        """
        Инициализация роутера с историей маршрутизации.

        Args:
            db_path: Путь к SQLite базе для хранения истории решений и результатов.
        """
        self.db_path = db_path
        self._model = None
        self._vectorizer = None
        self._is_trained = False

        # Создаём директорию для БД
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self._init_db()

    # ── Инициализация базы данных ──

    def _init_db(self):
        """Создание таблиц для хранения решений и результатов."""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS decisions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision_id TEXT UNIQUE NOT NULL,
                    task_description TEXT NOT NULL,
                    model TEXT NOT NULL,
                    strategy TEXT NOT NULL,
                    n_samples INTEGER DEFAULT 1,
                    confidence REAL DEFAULT 0.0,
                    estimated_cost REAL DEFAULT 0.0,
                    created_at TEXT NOT NULL
                );

                CREATE TABLE IF NOT EXISTS outcomes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    decision_id TEXT NOT NULL,
                    success INTEGER NOT NULL,
                    quality_score REAL NOT NULL,
                    actual_cost REAL NOT NULL,
                    actual_latency_ms REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (decision_id) REFERENCES decisions(decision_id)
                );

                CREATE INDEX IF NOT EXISTS idx_decisions_id ON decisions(decision_id);
                CREATE INDEX IF NOT EXISTS idx_outcomes_decision ON outcomes(decision_id);
                CREATE INDEX IF NOT EXISTS idx_decisions_model ON decisions(model);
            """)

    def _conn(self) -> sqlite3.Connection:
        """Создание подключения к SQLite с row_factory."""
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    # ── Feature engineering ──

    def _extract_features(self, task: str) -> np.ndarray:
        """
        Извлечение числовых признаков из описания задачи.

        Returns:
            Вектор признаков: [program_hits, complex_hits, medium_hits,
                              text_length, word_count, has_code_markers,
                              has_file_count, question_mark,
                              model_success_flash, model_success_pro,
                              model_success_sonnet, model_success_opus]
        """
        task_lower = task.lower()

        # Совпадения с ключевыми словами
        prog_hits = sum(1 for kw in self.PROGRAM_KEYWORDS if kw in task_lower)
        comp_hits = sum(1 for kw in self.COMPLEX_KEYWORDS if kw in task_lower)
        med_hits = sum(1 for kw in self.MEDIUM_KEYWORDS if kw in task_lower)

        # Длина и количество слов
        text_length = min(len(task) / 200.0, 1.0)
        word_count = min(len(task.split()) / 30.0, 1.0)

        # Наличие code-маркеров
        code_hits = sum(1 for marker in self.CODE_MARKERS if marker in task)
        has_code = min(code_hits / 3.0, 1.0)

        # Числовые паттерны файлов
        has_file_count = 1.0 if re.search(r'\d+\s*файл', task_lower) else 0.0

        # Вопросительный знак (вопрос vs императив)
        has_question = 1.0 if '?' in task else 0.0

        # Исторический success_rate каждой модели (для контекстуальности)
        model_stats = self._get_model_success_rates()
        flash_rate = model_stats.get('flash', {}).get('success_rate', 0.5)
        pro_rate = model_stats.get('pro', {}).get('success_rate', 0.5)
        sonnet_rate = model_stats.get('sonnet', {}).get('success_rate', 0.5)
        opus_rate = model_stats.get('opus', {}).get('success_rate', 0.5)

        return np.array([
            min(prog_hits / 3.0, 1.0),
            min(comp_hits / 3.0, 1.0),
            min(med_hits / 3.0, 1.0),
            text_length,
            word_count,
            has_code,
            has_file_count,
            has_question,
            flash_rate,
            pro_rate,
            sonnet_rate,
            opus_rate,
        ], dtype=np.float64)

    def _get_model_success_rates(self) -> Dict[str, Dict[str, float]]:
        """
        Исторический success_rate для каждой модели.

        Returns:
            Словарь {model: {success_rate, avg_quality, count}}.
        """
        stats = {}
        try:
            with self._conn() as conn:
                rows = conn.execute("""
                    SELECT d.model,
                           COUNT(*) as cnt,
                           AVG(o.success) as success_rate,
                           AVG(o.quality_score) as avg_quality
                    FROM decisions d
                    JOIN outcomes o ON d.decision_id = o.decision_id
                    GROUP BY d.model
                """).fetchall()
                for row in rows:
                    stats[row['model']] = {
                        'success_rate': row['success_rate'] or 0.5,
                        'avg_quality': row['avg_quality'] or 0.5,
                        'count': row['cnt'],
                    }
        except sqlite3.Error:
            pass
        return stats

    # ── Основной метод маршрутизации ──

    def route(self, task_description: str, context: Optional[Dict] = None) -> RoutingDecision:
        """
        Маршрутизация задачи к оптимальной модели и стратегии.

        Если ML модель обучена и данных достаточно -- использует ML предсказание.
        Иначе -- rule-based эвристика (аналог router.js).

        Args:
            task_description: Описание задачи на естественном языке.
            context: Дополнительный контекст (file_count, domain, criticality).

        Returns:
            RoutingDecision с рекомендуемой моделью, стратегией и оценками.
        """
        context = context or {}
        decision_id = uuid.uuid4().hex[:16]

        # Попытка ML предсказания
        if self._is_trained and self._model is not None:
            try:
                decision = self._ml_route(task_description, context, decision_id)
                self._save_decision(decision, task_description)
                return decision
            except Exception as e:
                logger.warning("ML маршрутизация не удалась, fallback на правила: %s", e)

        # Rule-based fallback
        decision = self._rule_based_route(task_description, context, decision_id)
        self._save_decision(decision, task_description)
        return decision

    def _ml_route(self, task: str, context: Dict, decision_id: str) -> RoutingDecision:
        """ML предсказание оптимальной модели."""
        features = self._extract_features(task).reshape(1, -1)
        predicted_model = self._model.predict(features)[0]

        # Вероятности для расчёта уверенности
        probabilities = self._model.predict_proba(features)[0]
        confidence = float(np.max(probabilities))

        # Определяем стратегию
        strategy = self.suggest_strategy(task)
        n_samples = self._calc_n_samples(strategy, predicted_model)
        fallback_chain = self._build_fallback_chain(predicted_model)
        estimated_cost = self._calc_estimated_cost(predicted_model, strategy, n_samples, task)

        return RoutingDecision(
            decision_id=decision_id,
            model=predicted_model,
            strategy=strategy,
            n_samples=n_samples,
            fallback_chain=fallback_chain,
            confidence=confidence,
            estimated_cost=estimated_cost,
            reasoning=f"ML предсказание: модель={predicted_model}, "
                      f"уверенность={confidence:.2f}, стратегия={strategy}",
        )

    def _rule_based_route(self, task: str, context: Dict, decision_id: str) -> RoutingDecision:
        """Rule-based маршрутизация (fallback при малом количестве данных)."""
        task_lower = task.lower()

        # Определяем уровень сложности
        prog_hits = sum(1 for kw in self.PROGRAM_KEYWORDS if kw in task_lower)
        comp_hits = sum(1 for kw in self.COMPLEX_KEYWORDS if kw in task_lower)
        med_hits = sum(1 for kw in self.MEDIUM_KEYWORDS if kw in task_lower)

        file_count = context.get('file_count', 1)

        # Логика выбора модели
        if prog_hits >= 2:
            model = 'flash'
            confidence = 0.90
            reasoning = "Задача решается программой/скриптом, Flash достаточен"
        elif comp_hits >= 2 or file_count >= 6:
            model = 'opus'
            confidence = 0.85
            reasoning = "Сложная задача: архитектура/безопасность/рефакторинг"
        elif med_hits >= 1 or file_count >= 3:
            model = 'pro'
            confidence = 0.80
            reasoning = "Средняя сложность: API/модуль/интеграция"
        elif len(task) < 80 and comp_hits == 0:
            model = 'flash'
            confidence = 0.85
            reasoning = "Короткая простая задача"
        else:
            model = 'sonnet'
            confidence = 0.75
            reasoning = "Стандартная задача средней сложности"

        strategy = self.suggest_strategy(task)
        n_samples = self._calc_n_samples(strategy, model)
        fallback_chain = self._build_fallback_chain(model)
        estimated_cost = self._calc_estimated_cost(model, strategy, n_samples, task)

        return RoutingDecision(
            decision_id=decision_id,
            model=model,
            strategy=strategy,
            n_samples=n_samples,
            fallback_chain=fallback_chain,
            confidence=confidence,
            estimated_cost=estimated_cost,
            reasoning=f"Rule-based: {reasoning}",
        )

    # ── Запись результатов ──

    def record_outcome(
        self,
        decision_id: str,
        success: bool,
        quality_score: float,
        actual_cost: float,
        actual_latency_ms: float,
    ):
        """
        Запись результата выполнения для обучения.

        Args:
            decision_id: Идентификатор решения маршрутизации.
            success: Успешно ли выполнена задача.
            quality_score: Качество результата (0-1).
            actual_cost: Фактическая стоимость в USD.
            actual_latency_ms: Фактическая задержка в миллисекундах.
        """
        try:
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO outcomes (decision_id, success, quality_score, "
                    "actual_cost, actual_latency_ms, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (
                        decision_id,
                        1 if success else 0,
                        quality_score,
                        actual_cost,
                        actual_latency_ms,
                        datetime.now().isoformat(),
                    ),
                )
        except sqlite3.Error as e:
            logger.error("Ошибка записи outcome: %s", e)

    def _save_decision(self, decision: RoutingDecision, task_description: str):
        """Сохранение решения маршрутизации в историю."""
        try:
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO decisions (decision_id, task_description, model, "
                    "strategy, n_samples, confidence, estimated_cost, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        decision.decision_id,
                        task_description,
                        decision.model,
                        decision.strategy,
                        decision.n_samples,
                        decision.confidence,
                        decision.estimated_cost,
                        datetime.now().isoformat(),
                    ),
                )
        except sqlite3.Error as e:
            logger.error("Ошибка сохранения decision: %s", e)

    # ── Обучение модели ──

    def train(self, min_samples: int = 50) -> Dict[str, Any]:
        """
        Переобучение ML модели на накопленных данных.

        Использует GradientBoosting для предсказания оптимальной модели
        на основе признаков задачи и исторической успешности.

        Args:
            min_samples: Минимальное количество записей с outcomes для обучения.

        Returns:
            Метрики обучения: accuracy, report, train_samples, test_samples.
        """
        # Загружаем данные с outcomes
        try:
            with self._conn() as conn:
                rows = conn.execute("""
                    SELECT d.task_description, d.model, o.success, o.quality_score
                    FROM decisions d
                    JOIN outcomes o ON d.decision_id = o.decision_id
                    WHERE o.success = 1 AND o.quality_score >= 0.5
                    ORDER BY o.created_at DESC
                    LIMIT 2000
                """).fetchall()
        except sqlite3.Error as e:
            return {'error': f'Ошибка чтения БД: {e}', 'trained': False}

        if len(rows) < min_samples:
            return {
                'error': f'Недостаточно данных: {len(rows)} < {min_samples}',
                'trained': False,
                'samples_available': len(rows),
            }

        # Формируем обучающую выборку
        tasks = [row['task_description'] for row in rows]
        labels = [row['model'] for row in rows]

        # Извлекаем признаки
        features = np.array([self._extract_features(t) for t in tasks])

        # Импортируем sklearn (отложенный импорт для быстрого старта)
        try:
            from sklearn.ensemble import GradientBoostingClassifier
            from sklearn.model_selection import train_test_split
            from sklearn.metrics import accuracy_score, classification_report
        except ImportError:
            return {'error': 'sklearn не установлен', 'trained': False}

        # Разделение на train/test
        from collections import Counter
        label_counts = Counter(labels)
        min_count = min(label_counts.values())
        use_stratify = min_count >= 2

        X_train, X_test, y_train, y_test = train_test_split(
            features, labels, test_size=0.2, random_state=42,
            stratify=labels if use_stratify else None,
        )

        # Обучение GradientBoosting
        clf = GradientBoostingClassifier(
            n_estimators=100,
            learning_rate=0.1,
            max_depth=5,
            min_samples_split=4,
            random_state=42,
        )
        clf.fit(X_train, y_train)

        # Оценка
        y_pred = clf.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        report = classification_report(y_test, y_pred, zero_division=0)

        # Сохраняем модель
        self._model = clf
        self._is_trained = True

        return {
            'trained': True,
            'accuracy': accuracy,
            'report': report,
            'train_samples': len(X_train),
            'test_samples': len(X_test),
            'label_distribution': dict(label_counts),
        }

    # ── Статистика ──

    def get_model_performance(self) -> Dict[str, Any]:
        """
        Статистика производительности по моделям.

        Returns:
            Словарь {model: {total, success_rate, avg_quality, avg_cost,
                            avg_latency_ms, cost_per_quality}} для каждой модели.
        """
        stats = {}
        try:
            with self._conn() as conn:
                rows = conn.execute("""
                    SELECT d.model,
                           COUNT(*) as total,
                           AVG(o.success) as success_rate,
                           AVG(o.quality_score) as avg_quality,
                           AVG(o.actual_cost) as avg_cost,
                           AVG(o.actual_latency_ms) as avg_latency
                    FROM decisions d
                    JOIN outcomes o ON d.decision_id = o.decision_id
                    GROUP BY d.model
                    ORDER BY avg_quality DESC
                """).fetchall()

                for row in rows:
                    model = row['model']
                    avg_quality = row['avg_quality'] or 0.0
                    avg_cost = row['avg_cost'] or 0.0
                    cost_per_quality = avg_cost / avg_quality if avg_quality > 0 else float('inf')

                    stats[model] = {
                        'total': row['total'],
                        'success_rate': round(row['success_rate'] or 0, 4),
                        'avg_quality': round(avg_quality, 4),
                        'avg_cost': round(avg_cost, 6),
                        'avg_latency_ms': round(row['avg_latency'] or 0, 1),
                        'cost_per_quality': round(cost_per_quality, 6),
                        'name': MODEL_PRICING.get(model, {}).get('name', model),
                    }
        except sqlite3.Error as e:
            logger.error("Ошибка получения статистики: %s", e)

        return stats

    # ── Стратегии (BEST-Route) ──

    def suggest_strategy(self, task_description: str) -> str:
        """
        Выбор стратегии выполнения на основе характеристик задачи.

        Стратегии (вдохновлено BEST-Route):
        - single_shot: один вызов оптимальной модели (простые, детерминированные задачи)
        - multi_sample: N вызовов дешёвой модели + majority voting (средние задачи,
          где 3 попытки Flash дешевле 1 Opus)
        - cascade: сначала дешёвая модель, если confidence < threshold -> дороже
          (задачи с неопределённой сложностью)

        Args:
            task_description: Описание задачи.

        Returns:
            Название стратегии: 'single_shot', 'multi_sample', 'cascade'.
        """
        task_lower = task_description.lower()

        # Индикаторы определённости
        prog_hits = sum(1 for kw in self.PROGRAM_KEYWORDS if kw in task_lower)
        comp_hits = sum(1 for kw in self.COMPLEX_KEYWORDS if kw in task_lower)

        # single_shot: задача явно простая ИЛИ явно сложная
        if prog_hits >= 2 or comp_hits >= 2:
            return 'single_shot'

        # single_shot: очень короткая задача — нет смысла делать несколько попыток
        if len(task_description) < 60:
            return 'single_shot'

        # multi_sample: задачи средней сложности с генерацией кода
        code_hits = sum(1 for m in self.CODE_MARKERS if m in task_description)
        med_hits = sum(1 for kw in self.MEDIUM_KEYWORDS if kw in task_lower)
        if med_hits >= 1 and code_hits == 0 and len(task_description) > 100:
            return 'multi_sample'

        # cascade: неопределённые задачи (нет явных индикаторов)
        total_hits = prog_hits + comp_hits + med_hits
        if total_hits == 0 and len(task_description) > 80:
            return 'cascade'

        return 'single_shot'

    # ── Оценка стоимости ──

    def estimate_cost(self, task_description: str) -> Dict[str, float]:
        """
        Оценка стоимости выполнения для каждой модели.

        Оценивает количество входных/выходных токенов на основе длины задачи
        и рассчитывает стоимость для каждой доступной модели.

        Args:
            task_description: Описание задачи.

        Returns:
            Словарь {model: estimated_cost_usd} для каждой модели.
        """
        # Оценка количества токенов
        input_tokens = max(len(task_description) // 4, 200) + 500  # промпт + контекст
        output_tokens = max(input_tokens // 3, 100)  # ответ примерно 30% от ввода

        costs = {}
        for model, pricing in MODEL_PRICING.items():
            cost = (
                input_tokens * pricing['input']
                + output_tokens * pricing['output']
            ) / 1_000_000
            costs[model] = round(cost, 6)

        return costs

    # ── Вспомогательные методы ──

    def _calc_n_samples(self, strategy: str, model: str) -> int:
        """Расчёт количества попыток для стратегии."""
        if strategy == 'multi_sample':
            # Дешёвые модели — больше попыток
            if model in ('flash',):
                return 5
            elif model in ('pro', 'sonnet'):
                return 3
            else:
                return 1
        return 1

    def _build_fallback_chain(self, primary_model: str) -> List[str]:
        """
        Построение цепочки fallback моделей от текущей к более дорогой.

        Например: flash -> [pro, sonnet, opus]
        """
        idx = MODEL_COST_ORDER.index(primary_model) if primary_model in MODEL_COST_ORDER else 0
        return MODEL_COST_ORDER[idx + 1:]

    def _calc_estimated_cost(
        self, model: str, strategy: str, n_samples: int, task: str
    ) -> float:
        """Расчёт ожидаемой стоимости выполнения."""
        base_costs = self.estimate_cost(task)
        base_cost = base_costs.get(model, 0.001)

        if strategy == 'multi_sample':
            return base_cost * n_samples
        elif strategy == 'cascade':
            # В среднем 70% решается первой моделью, 30% идёт в fallback
            chain = self._build_fallback_chain(model)
            cascade_cost = base_cost  # первая модель всегда вызывается
            if chain:
                fallback_cost = base_costs.get(chain[0], base_cost * 2)
                cascade_cost += fallback_cost * 0.3  # 30% вероятность fallback
            return cascade_cost
        else:
            return base_cost

    # ── Подсчёт данных ──

    def _count_decisions_with_outcomes(self) -> int:
        """Количество решений с записанными результатами."""
        try:
            with self._conn() as conn:
                row = conn.execute("""
                    SELECT COUNT(DISTINCT d.decision_id) as cnt
                    FROM decisions d
                    JOIN outcomes o ON d.decision_id = o.decision_id
                """).fetchone()
                return row['cnt'] if row else 0
        except sqlite3.Error:
            return 0
