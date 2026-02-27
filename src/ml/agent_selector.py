"""
ML селектор агентов для задач.

Использует Gradient Boosting для ранжирования агентов по пригодности
для конкретной задачи на основе исторических данных о производительности.
"""

from sklearn.ensemble import GradientBoostingRegressor
from sklearn.preprocessing import StandardScaler
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error, r2_score
import pickle
import os
from typing import List, Dict, Tuple, Optional
import numpy as np


class AgentSelector:
    """Селектор оптимального агента для задачи на основе ML."""

    def __init__(self):
        """Инициализация селектора."""
        # Gradient Boosting регрессор для предсказания успешности
        self.model = GradientBoostingRegressor(
            n_estimators=100,      # 100 деревьев
            learning_rate=0.1,     # Скорость обучения
            max_depth=5,           # Максимальная глубина
            min_samples_split=4,   # Минимум для разделения
            random_state=42        # Воспроизводимость
        )

        # Нормализация признаков
        self.scaler = StandardScaler()

        self.is_trained = False

        # Список типов агентов (для consistency)
        self.agent_types = [
            'coder', 'reviewer', 'tester', 'researcher', 'architect',
            'security-architect', 'performance-engineer', 'coordinator'
        ]

    def train(self, features: List[List[float]], scores: List[float],
              test_size: float = 0.2) -> dict:
        """
        Обучение модели ранжирования агентов.

        Args:
            features: Список векторов признаков
                      [task_similarity, agent_past_performance, agent_load,
                       task_complexity_num, agent_specialization_match]
            scores: Список оценок успеха (0-1)
            test_size: Доля тестовой выборки

        Returns:
            Метрики обучения (mse, r2)
        """
        if len(features) < 20:
            raise ValueError("Недостаточно данных для обучения (минимум 20 примеров)")

        # Нормализация признаков
        X = self.scaler.fit_transform(features)
        y = np.array(scores)

        # Разделение на train/test
        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=42
        )

        # Обучение модели
        self.model.fit(X_train, y_train)
        self.is_trained = True

        # Оценка качества
        y_pred = self.model.predict(X_test)
        mse = mean_squared_error(y_test, y_pred)
        r2 = r2_score(y_test, y_pred)

        return {
            'mse': mse,
            'r2': r2,
            'train_samples': len(X_train),
            'test_samples': len(X_test)
        }

    def rank_agents(self, task_features: Dict[str, float],
                   available_agents: List[Dict]) -> List[Dict]:
        """
        Ранжирование агентов по пригодности для задачи.

        Args:
            task_features: Признаки задачи
                - complexity_num: Числовая сложность (0=program, 1=simple, 2=medium, 3=complex)
                - requires_security: Требуется security (0/1)
                - requires_performance: Требуется performance (0/1)
                - file_count: Количество файлов
            available_agents: Список доступных агентов
                [{
                    'type': 'coder',
                    'past_performance': 0.85,
                    'current_load': 0.3,
                    'specialization': ['backend', 'api']
                }, ...]

        Returns:
            Список агентов, отсортированных по пригодности (топ-3)
        """
        if not self.is_trained:
            # Fallback на rule-based если модель не обучена
            return self._rule_based_ranking(task_features, available_agents)

        # Формирование признаков для каждого агента
        agent_features = []
        for agent in available_agents:
            feature_vector = self._create_feature_vector(task_features, agent)
            agent_features.append(feature_vector)

        # Нормализация и предсказание
        X = self.scaler.transform(agent_features)
        scores = self.model.predict(X)

        # Добавление оценок к агентам
        ranked_agents = []
        for i, agent in enumerate(available_agents):
            agent_copy = agent.copy()
            agent_copy['ml_score'] = float(scores[i])
            ranked_agents.append(agent_copy)

        # Сортировка по убыванию оценки
        ranked_agents.sort(key=lambda x: x['ml_score'], reverse=True)

        # Возврат топ-3
        return ranked_agents[:3]

    def _create_feature_vector(self, task_features: Dict[str, float],
                              agent: Dict) -> List[float]:
        """
        Создание вектора признаков для пары (задача, агент).

        Returns:
            Вектор [task_similarity, agent_performance, agent_load,
                    task_complexity, specialization_match]
        """
        # 1. Task similarity (на основе специализации агента)
        specialization_match = 0.0
        if 'specialization' in agent and task_features.get('domain'):
            if task_features['domain'] in agent['specialization']:
                specialization_match = 1.0

        # 2. Agent past performance
        agent_performance = agent.get('past_performance', 0.5)

        # 3. Agent current load (инвертируем: меньше нагрузка = лучше)
        agent_load = 1.0 - agent.get('current_load', 0.5)

        # 4. Task complexity
        task_complexity = task_features.get('complexity_num', 1.0)

        # 5. Specialization match bonus
        spec_bonus = 0.0
        agent_type = agent.get('type', '')
        if task_features.get('requires_security', 0) and 'security' in agent_type:
            spec_bonus = 1.0
        elif task_features.get('requires_performance', 0) and 'performance' in agent_type:
            spec_bonus = 1.0

        return [
            specialization_match,
            agent_performance,
            agent_load,
            task_complexity,
            spec_bonus
        ]

    def _rule_based_ranking(self, task_features: Dict[str, float],
                           available_agents: List[Dict]) -> List[Dict]:
        """
        Rule-based fallback для ранжирования агентов.

        Args:
            task_features: Признаки задачи
            available_agents: Доступные агенты

        Returns:
            Топ-3 агента
        """
        ranked = []

        for agent in available_agents:
            score = 0.0
            agent_type = agent.get('type', '')

            # Базовая оценка: past_performance
            score += agent.get('past_performance', 0.5) * 0.5

            # Штраф за нагрузку
            score -= agent.get('current_load', 0.0) * 0.3

            # Бонус за специализацию
            if task_features.get('requires_security', 0) and 'security' in agent_type:
                score += 0.3
            if task_features.get('requires_performance', 0) and 'performance' in agent_type:
                score += 0.3
            if task_features.get('complexity_num', 1) >= 2:  # medium/complex
                if agent_type in ['architect', 'coordinator']:
                    score += 0.2

            agent_copy = agent.copy()
            agent_copy['rule_score'] = score
            ranked.append(agent_copy)

        # Сортировка
        ranked.sort(key=lambda x: x['rule_score'], reverse=True)
        return ranked[:3]

    def predict_success(self, task_features: Dict[str, float],
                       agent: Dict) -> float:
        """
        Предсказание вероятности успеха для пары (задача, агент).

        Args:
            task_features: Признаки задачи
            agent: Информация об агенте

        Returns:
            Вероятность успеха (0-1)
        """
        if not self.is_trained:
            # Fallback: простая эвристика
            base_score = agent.get('past_performance', 0.5)
            load_penalty = agent.get('current_load', 0.0) * 0.2
            return max(0.0, min(1.0, base_score - load_penalty))

        # ML предсказание
        feature_vector = self._create_feature_vector(task_features, agent)
        X = self.scaler.transform([feature_vector])
        prediction = self.model.predict(X)[0]

        # Клиппинг в [0, 1]
        return max(0.0, min(1.0, prediction))

    def save(self, path: str = 'data/models/agent_selector.pkl'):
        """
        Сохранение модели на диск.

        Args:
            path: Путь к файлу модели
        """
        if not self.is_trained:
            raise RuntimeError("Модель не обучена. Нечего сохранять.")

        os.makedirs(os.path.dirname(path), exist_ok=True)

        with open(path, 'wb') as f:
            pickle.dump({
                'model': self.model,
                'scaler': self.scaler,
                'agent_types': self.agent_types,
                'is_trained': self.is_trained
            }, f)

    def load(self, path: str = 'data/models/agent_selector.pkl'):
        """
        Загрузка модели с диска.

        Args:
            path: Путь к файлу модели
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Модель не найдена: {path}")

        with open(path, 'rb') as f:
            data = pickle.load(f)
            self.model = data['model']
            self.scaler = data['scaler']
            self.agent_types = data.get('agent_types', self.agent_types)
            self.is_trained = data.get('is_trained', True)
