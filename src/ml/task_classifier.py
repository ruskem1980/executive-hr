"""
ML классификатор сложности задач.

Использует TF-IDF векторизацию + Random Forest для предсказания
уровня сложности задачи: program, simple, medium, complex.
"""

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.ensemble import RandomForestClassifier
from sklearn.calibration import CalibratedClassifierCV
from sklearn.model_selection import train_test_split
from sklearn.metrics import classification_report, accuracy_score
from scipy.sparse import hstack, csr_matrix
import pickle
import os
import re
from typing import List, Tuple, Optional, Union
import numpy as np


class TaskClassifier:
    """Классификатор сложности задач на основе ML."""

    # Индикаторы для feature engineering
    PROGRAM_KEYWORDS = [
        'отчёт', 'отчет', 'статистик', 'покажи', 'список', 'показать',
        'валидац', 'провер', 'lint', 'format', 'flake8', 'black', 'pylint',
        'eslint', 'prettier', 'pytest', 'тест запуст', 'запусти тест',
        'запустить тест', 'npm test', 'benchmark', 'синхрониз', 'git log',
        'git status', 'дерево директор', 'размер проект', 'зависимост',
        'прогони', 'coverage', 'сколько токен', 'расход', 'экономи',
    ]

    COMPLEX_KEYWORDS = [
        'архитектур', 'рефактор', 'миграц', 'безопасн', 'security',
        'производительн', 'оптимизац', 'переписать', 'distributed',
        'микросервис', 'монолит', 'переработ', 'весь проект', 'все файлы',
        'всё приложен', 'мультитенант', 'cqrs', 'event-driven',
        'двухфактор', 'шифрован', 'аудит', 'sso', 'graphql',
        '6+ файлов', '10+ файлов', 'полн переработк', 'полное покрыт',
    ]

    MEDIUM_KEYWORDS = [
        'api endpoint', 'endpoint', 'модуль', 'компонент', 'фич',
        'интеграц', 'middleware', 'crud', 'миграц табл', 'репозитор',
        'webhook', 'rate limit', 'pagination', 'кеширован', 'redis',
        'jwt', 'oauth', 'pydantic', 'stripe', 'twilio',
        'e2e тест', 'интеграцион тест', 'нагрузоч тест',
    ]

    def __init__(self):
        """Инициализация классификатора."""
        # TF-IDF векторизатор для преобразования текста в числовые признаки
        self.vectorizer = TfidfVectorizer(
            max_features=300,      # Больше признаков для лучшей дискриминации
            ngram_range=(1, 3),    # Униграммы, биграммы и триграммы
            min_df=1,              # Учитываем редкие слова (важно для program)
            max_df=0.9,            # Игнорируем слишком частые слова
            sublinear_tf=True,     # Логарифмическое масштабирование TF
            analyzer='word',
        )

        # Random Forest классификатор (базовая модель)
        self.model = RandomForestClassifier(
            n_estimators=200,      # Больше деревьев для стабильности
            max_depth=15,          # Глубже для сложных паттернов
            min_samples_split=3,   # Меньший порог для разделения
            min_samples_leaf=1,    # Листья могут быть маленькими
            class_weight='balanced',  # Автобалансировка классов
            random_state=42        # Воспроизводимость
        )

        # Калиброванная модель — корректирует вероятности predict_proba
        # для более точных значений confidence (sigmoid/Platt scaling)
        self._calibrated_model = None

        self.is_trained = False

    def _extract_keyword_features(self, tasks: List[str]) -> np.ndarray:
        """
        Извлечение keyword-based признаков для каждой задачи.

        Дополняет TF-IDF явными индикаторами сложности.
        """
        features = []
        for task in tasks:
            task_lower = task.lower()
            row = []
            # Количество совпадений с program-индикаторами
            prog_hits = sum(1 for kw in self.PROGRAM_KEYWORDS if kw in task_lower)
            row.append(min(prog_hits / 3.0, 1.0))  # Нормализация

            # Количество совпадений с complex-индикаторами
            comp_hits = sum(1 for kw in self.COMPLEX_KEYWORDS if kw in task_lower)
            row.append(min(comp_hits / 3.0, 1.0))

            # Количество совпадений с medium-индикаторами
            med_hits = sum(1 for kw in self.MEDIUM_KEYWORDS if kw in task_lower)
            row.append(min(med_hits / 3.0, 1.0))

            # Длина описания (longer = more complex)
            row.append(min(len(task) / 100.0, 1.0))

            # Количество слов
            word_count = len(task.split())
            row.append(min(word_count / 15.0, 1.0))

            # Наличие числовых упоминаний файлов (6+ файлов и т.д.)
            has_file_count = 1.0 if re.search(r'\d+\s*файл', task_lower) else 0.0
            row.append(has_file_count)

            features.append(row)
        return np.array(features)

    def _combine_features(self, tasks: List[str], fit: bool = False):
        """Комбинация TF-IDF и keyword-based признаков."""
        if fit:
            tfidf = self.vectorizer.fit_transform(tasks)
        else:
            tfidf = self.vectorizer.transform(tasks)
        keyword_feats = csr_matrix(self._extract_keyword_features(tasks))
        return hstack([tfidf, keyword_feats])

    def train(self, tasks: List[str], labels: List[str],
              test_size: float = 0.2, calibrate: bool = True) -> dict:
        """
        Обучение классификатора с калибровкой вероятностей.

        Args:
            tasks: Список описаний задач
            labels: Список меток сложности ("program", "simple", "medium", "complex")
            test_size: Доля тестовой выборки
            calibrate: Применить CalibratedClassifierCV для калибровки confidence

        Returns:
            Метрики обучения (accuracy, report, calibrated)
        """
        if len(tasks) < 10:
            raise ValueError("Недостаточно данных для обучения (минимум 10 примеров)")

        # Комбинированная векторизация (TF-IDF + keyword features)
        X = self._combine_features(tasks, fit=True)

        # Разделение на train/test (stratify если достаточно данных в каждом классе)
        from collections import Counter
        label_counts = Counter(labels)
        min_count = min(label_counts.values())
        use_stratify = min_count >= 2

        X_train, X_test, y_train, y_test = train_test_split(
            X, labels, test_size=test_size, random_state=42,
            stratify=labels if use_stratify else None
        )

        # Обучение базовой модели
        self.model.fit(X_train, y_train)
        self.is_trained = True

        # Калибровка вероятностей через CalibratedClassifierCV
        # Решает проблему: RandomForest даёт размазанные вероятности (max ~0.6)
        # после калибровки: уверенные предсказания получают confidence > 0.8
        self._calibrated_model = None
        is_calibrated = False
        if calibrate and X_train.shape[0] >= 20:
            try:
                # cv=3 для калибровки (нужно минимум 3 примера на класс)
                cv_folds = min(5, min_count) if min_count >= 3 else 3
                cal_model = CalibratedClassifierCV(
                    self.model,
                    method='sigmoid',  # Platt scaling — хорош для многоклассовой
                    cv=cv_folds,
                    ensemble=True      # Ансамбль калиброванных моделей
                )
                cal_model.fit(X_train, y_train)
                self._calibrated_model = cal_model
                is_calibrated = True
            except Exception:
                # Калибровка не удалась — используем некалиброванную модель
                self._calibrated_model = None

        # Оценка качества (используем калиброванную если есть)
        pred_model = self._calibrated_model if self._calibrated_model else self.model
        y_pred = pred_model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)
        report = classification_report(y_test, y_pred, zero_division=0)

        return {
            'accuracy': accuracy,
            'report': report,
            'train_samples': X_train.shape[0],
            'test_samples': X_test.shape[0],
            'calibrated': is_calibrated
        }

    def predict(self, task: str, return_confidence: bool = False) -> Union[str, Tuple[str, float]]:
        """
        Предсказание сложности задачи.

        Использует калиброванную модель (если доступна) для точных вероятностей.

        Args:
            task: Описание задачи
            return_confidence: Вернуть также уровень уверенности

        Returns:
            Метка сложности или (метка, уверенность) если return_confidence=True
        """
        if not self.is_trained:
            raise RuntimeError("Модель не обучена. Вызовите train() сначала.")

        # Комбинированная векторизация
        X = self._combine_features([task])

        # Используем калиброванную модель для лучшего confidence
        pred_model = self._calibrated_model if self._calibrated_model else self.model

        # Предсказание
        prediction = pred_model.predict(X)[0]

        if return_confidence:
            # Вероятности (калиброванные если доступны)
            probabilities = pred_model.predict_proba(X)[0]
            confidence = float(np.max(probabilities))
            return prediction, confidence

        return prediction

    def predict_batch(self, tasks: List[str]) -> List[str]:
        """
        Пакетное предсказание для списка задач.

        Args:
            tasks: Список описаний задач

        Returns:
            Список меток сложности
        """
        if not self.is_trained:
            raise RuntimeError("Модель не обучена. Вызовите train() сначала.")

        X = self._combine_features(tasks)
        pred_model = self._calibrated_model if self._calibrated_model else self.model
        return pred_model.predict(X).tolist()

    def get_feature_importance(self, top_n: int = 20) -> List[Tuple[str, float]]:
        """
        Получить топ-N важных признаков (слов).

        Args:
            top_n: Количество топовых признаков

        Returns:
            Список пар (слово, важность)
        """
        if not self.is_trained:
            raise RuntimeError("Модель не обучена.")

        # Важность признаков из базовой модели (Random Forest)
        # CalibratedClassifierCV не имеет feature_importances_
        importances = self.model.feature_importances_  # Всегда базовая модель

        # Имена признаков: TF-IDF + keyword features
        tfidf_names = list(self.vectorizer.get_feature_names_out())
        keyword_names = [
            'kw:program_hits', 'kw:complex_hits', 'kw:medium_hits',
            'kw:text_length', 'kw:word_count', 'kw:has_file_count'
        ]
        feature_names = tfidf_names + keyword_names

        # Сортировка по важности
        indices = np.argsort(importances)[::-1][:top_n]

        return [(feature_names[i], importances[i]) for i in indices
                if i < len(feature_names)]

    def save(self, path: str = 'data/models/task_classifier.pkl'):
        """
        Сохранение модели на диск.

        Args:
            path: Путь к файлу модели
        """
        if not self.is_trained:
            raise RuntimeError("Модель не обучена. Нечего сохранять.")

        # Создание директории если не существует
        os.makedirs(os.path.dirname(path), exist_ok=True)

        # Сохранение векторизатора, базовой и калиброванной модели
        with open(path, 'wb') as f:
            pickle.dump({
                'vectorizer': self.vectorizer,
                'model': self.model,
                'calibrated_model': self._calibrated_model,
                'is_trained': self.is_trained
            }, f)

    def load(self, path: str = 'data/models/task_classifier.pkl'):
        """
        Загрузка модели с диска.

        Args:
            path: Путь к файлу модели
        """
        if not os.path.exists(path):
            raise FileNotFoundError(f"Модель не найдена: {path}")

        with open(path, 'rb') as f:
            data = pickle.load(f)
            self.vectorizer = data['vectorizer']
            self.model = data['model']
            self._calibrated_model = data.get('calibrated_model', None)
            self.is_trained = data.get('is_trained', True)

    @staticmethod
    def rule_based_fallback(task: str) -> str:
        """
        Rule-based fallback для случаев низкой уверенности ML.

        Args:
            task: Описание задачи

        Returns:
            Метка сложности
        """
        task_lower = task.lower()

        # Индикаторы программных задач (решаются скриптом)
        program_indicators = [
            'отчёт', 'статистика', 'покажи', 'список', 'просмотр',
            'валидация json', 'lint', 'format', 'тесты запустить'
        ]

        # Индикаторы сложных задач
        complex_indicators = [
            'архитектура', 'рефактор', 'миграция', 'безопасность',
            'производительность', 'оптимизация', 'переписать',
            'многомодульный', 'distributed'
        ]

        # Индикаторы средних задач
        medium_indicators = [
            'новая фича', 'api endpoint', 'модуль', 'интеграция',
            'несколько файлов', 'база данных'
        ]

        # Проверка индикаторов
        if any(ind in task_lower for ind in program_indicators):
            return 'program'
        elif any(ind in task_lower for ind in complex_indicators):
            return 'complex'
        elif any(ind in task_lower for ind in medium_indicators):
            return 'medium'
        else:
            return 'simple'
