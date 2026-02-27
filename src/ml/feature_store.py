"""
Хранилище признаков (Feature Store) для ML классификатора задач.

Сохраняет вычисленные keyword-features каждой классифицированной задачи
в SQLite для последующего переобучения модели и анализа качества.
"""

import sqlite3
import os
import csv
from typing import List, Tuple, Optional, Dict, Any


class FeatureStore:
    """
    Хранилище признаков классификации задач.

    Сохраняет keyword-features, результат классификации и обратную связь
    в SQLite (data/feature_store.db). Используется для:
    - Накопления обучающих данных из реальных классификаций
    - Выгрузки данных для переобучения модели
    - Анализа качества классификации через feedback
    """

    def __init__(self, db_path: str = 'data/feature_store.db'):
        """
        Инициализация хранилища. Создаёт БД и таблицу, если не существуют.

        Args:
            db_path: Путь к файлу SQLite базы данных.
        """
        self.db_path = db_path
        # Создаём директорию для БД
        db_dir = os.path.dirname(self.db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        self.conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._create_table()

    def _create_table(self):
        """Создание таблицы features, если отсутствует."""
        query = """
        CREATE TABLE IF NOT EXISTS features (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            task_description TEXT NOT NULL,
            complexity_label TEXT NOT NULL,
            confidence REAL,
            method TEXT,
            -- Keyword features (из TaskClassifier._extract_keyword_features)
            program_hits REAL,
            complex_hits REAL,
            medium_hits REAL,
            text_length REAL,
            word_count REAL,
            has_file_count REAL,
            -- Feedback (опционально, заполняется позже)
            was_correct INTEGER DEFAULT NULL,  -- 1=верно, 0=неверно, NULL=нет feedback
            actual_label TEXT DEFAULT NULL,
            -- Метаданные
            timestamp TEXT DEFAULT CURRENT_TIMESTAMP
        );
        """
        with self.conn:
            self.conn.execute(query)

    def record(
        self,
        task_description: str,
        complexity_label: str,
        confidence: float,
        method: str,
        keyword_features: Optional[Dict[str, float]] = None,
    ) -> Optional[int]:
        """
        Записать результат классификации задачи.

        Args:
            task_description: Описание задачи.
            complexity_label: Предсказанная метка сложности (program/simple/medium/complex).
            confidence: Уровень уверенности (0.0 — 1.0).
            method: Метод классификации ('ml', 'rules', 'fallback' и т.д.).
            keyword_features: Словарь keyword-признаков. Ожидаемые ключи:
                program_hits, complex_hits, medium_hits, text_length,
                word_count, has_file_count.

        Returns:
            ID записи в БД или None при ошибке.
        """
        kf = keyword_features or {}
        query = """
        INSERT INTO features (
            task_description, complexity_label, confidence, method,
            program_hits, complex_hits, medium_hits, text_length,
            word_count, has_file_count
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """
        params = (
            task_description,
            complexity_label,
            confidence,
            method,
            kf.get('program_hits'),
            kf.get('complex_hits'),
            kf.get('medium_hits'),
            kf.get('text_length'),
            kf.get('word_count'),
            kf.get('has_file_count'),
        )
        try:
            with self.conn:
                cursor = self.conn.execute(query, params)
                return cursor.lastrowid
        except sqlite3.Error:
            return None

    def get_training_data(
        self,
        min_confidence: float = 0.5,
        limit: int = 1000,
    ) -> Tuple[List[str], List[str]]:
        """
        Выгрузить данные для переобучения модели.

        Логика выборки:
        - Записи с actual_label: используем actual_label как ground truth
        - Записи с was_correct=1: используем complexity_label (подтверждено)
        - Записи без feedback: используем complexity_label если confidence >= порога
        - Исключаем записи с was_correct=0 без actual_label

        Args:
            min_confidence: Минимальная уверенность для записей без feedback.
            limit: Максимальное количество записей.

        Returns:
            Кортеж (descriptions, labels) — списки описаний и меток.
        """
        query = """
        SELECT task_description,
               COALESCE(actual_label, complexity_label) AS final_label
        FROM features
        WHERE (actual_label IS NOT NULL)
           OR (confidence >= ? AND (was_correct IS NULL OR was_correct = 1))
        ORDER BY timestamp DESC
        LIMIT ?
        """
        tasks: List[str] = []
        labels: List[str] = []
        try:
            cursor = self.conn.cursor()
            cursor.execute(query, (min_confidence, limit))
            for row in cursor.fetchall():
                tasks.append(row[0])
                labels.append(row[1])
        except sqlite3.Error:
            pass

        return tasks, labels

    def add_feedback(
        self,
        feature_id: int,
        was_correct: bool,
        actual_label: Optional[str] = None,
    ):
        """
        Добавить обратную связь для записи классификации.

        Args:
            feature_id: ID записи в таблице features.
            was_correct: Верно ли была классифицирована задача.
            actual_label: Правильная метка (если классификация была неверной).
        """
        query = """
        UPDATE features
        SET was_correct = ?, actual_label = ?
        WHERE id = ?
        """
        try:
            with self.conn:
                self.conn.execute(query, (
                    1 if was_correct else 0,
                    actual_label,
                    feature_id,
                ))
        except sqlite3.Error:
            pass

    def get_statistics(self) -> Dict[str, Any]:
        """
        Статистика feature store.

        Returns:
            Словарь с метриками:
                total — общее количество записей
                by_label — распределение по меткам сложности
                by_method — распределение по методам классификации
                avg_confidence — средняя уверенность
                with_feedback — количество записей с feedback
                accuracy — точность (из записей с feedback)
        """
        stats: Dict[str, Any] = {
            'total': 0,
            'by_label': {},
            'by_method': {},
            'avg_confidence': 0.0,
            'with_feedback': 0,
            'accuracy': 0.0,
        }
        try:
            cursor = self.conn.cursor()

            # Общее количество записей
            cursor.execute("SELECT COUNT(*) FROM features")
            stats['total'] = cursor.fetchone()[0]

            # Распределение по меткам сложности
            cursor.execute(
                "SELECT complexity_label, COUNT(*) FROM features GROUP BY complexity_label"
            )
            stats['by_label'] = dict(cursor.fetchall())

            # Распределение по методам классификации
            cursor.execute(
                "SELECT method, COUNT(*) FROM features GROUP BY method"
            )
            stats['by_method'] = dict(cursor.fetchall())

            # Средняя уверенность
            cursor.execute(
                "SELECT AVG(confidence) FROM features WHERE confidence IS NOT NULL"
            )
            avg = cursor.fetchone()[0]
            stats['avg_confidence'] = round(avg, 4) if avg is not None else 0.0

            # Количество записей с обратной связью
            cursor.execute(
                "SELECT COUNT(*) FROM features WHERE was_correct IS NOT NULL"
            )
            stats['with_feedback'] = cursor.fetchone()[0]

            # Точность классификации (из записей с feedback)
            cursor.execute(
                "SELECT AVG(CAST(was_correct AS REAL)) FROM features "
                "WHERE was_correct IS NOT NULL"
            )
            acc = cursor.fetchone()[0]
            stats['accuracy'] = round(acc, 4) if acc is not None else 0.0

        except sqlite3.Error:
            pass

        return stats

    def export_csv(self, output_path: str):
        """
        Экспорт всех данных feature store в CSV файл.

        Args:
            output_path: Путь для сохранения CSV.
        """
        out_dir = os.path.dirname(output_path)
        if out_dir:
            os.makedirs(out_dir, exist_ok=True)
        try:
            cursor = self.conn.cursor()
            cursor.execute("SELECT * FROM features ORDER BY timestamp DESC")
            columns = [desc[0] for desc in cursor.description]

            with open(output_path, 'w', newline='', encoding='utf-8') as f:
                writer = csv.writer(f)
                writer.writerow(columns)
                writer.writerows(cursor.fetchall())
        except (sqlite3.Error, IOError):
            pass

    def __del__(self):
        """Закрытие соединения при удалении объекта."""
        try:
            if hasattr(self, 'conn'):
                self.conn.close()
        except Exception:
            pass
