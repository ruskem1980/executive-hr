"""
Библиотека обучения с векторным поиском паттернов.

Использует ChromaDB для хранения и поиска успешных паттернов решения задач
с помощью семантического векторного поиска.
"""

import chromadb
from chromadb.config import Settings
from sentence_transformers import SentenceTransformer
from typing import List, Dict, Optional
import os
import json


class LearningLibrary:
    """Векторная библиотека успешных паттернов решения задач."""

    def __init__(self, persist_directory: str = 'data/chroma_db'):
        """
        Инициализация библиотеки обучения.

        Args:
            persist_directory: Директория для хранения базы данных
        """
        # Создание директории если не существует
        os.makedirs(persist_directory, exist_ok=True)

        # Инициализация ChromaDB клиента с персистентностью
        self.client = chromadb.PersistentClient(
            path=persist_directory,
            settings=Settings(
                anonymized_telemetry=False,
                allow_reset=True
            )
        )

        # Создание или получение коллекции
        try:
            self.collection = self.client.get_or_create_collection(
                name="task_patterns",
                metadata={"description": "Успешные паттерны решения задач"}
            )
        except Exception:
            # Если коллекция повреждена, пересоздаём
            try:
                self.client.delete_collection("task_patterns")
            except Exception:
                pass
            self.collection = self.client.create_collection(
                name="task_patterns",
                metadata={"description": "Успешные паттерны решения задач"}
            )

        # Sentence Transformer для embeddings
        # Используем лёгкую модель all-MiniLM-L6-v2 (384 dimensions)
        self.encoder = SentenceTransformer('all-MiniLM-L6-v2')

    def add_pattern(self, task_id: str, description: str, solution: str,
                   metadata: Optional[Dict] = None):
        """
        Добавить успешный паттерн в библиотеку.

        Args:
            task_id: Уникальный ID задачи
            description: Описание задачи
            solution: Описание решения/подхода
            metadata: Дополнительные метаданные (complexity, success_score, etc.)
        """
        # Генерация embedding для описания задачи
        embedding = self.encoder.encode(description)

        # Подготовка метаданных
        meta = metadata or {}
        meta['solution'] = solution  # Решение в метаданных

        # Добавление в коллекцию
        self.collection.add(
            ids=[task_id],
            embeddings=[embedding.tolist()],
            documents=[description],  # Текст описания
            metadatas=[meta]
        )

    def search_similar(self, query: str, top_k: int = 3,
                      filter_metadata: Optional[Dict] = None) -> List[Dict]:
        """
        Найти похожие задачи через семантический поиск.

        Args:
            query: Описание новой задачи
            top_k: Количество результатов
            filter_metadata: Фильтр по метаданным (например, {'complexity': 'simple'})

        Returns:
            Список найденных паттернов с решениями
        """
        # Генерация embedding для запроса
        query_embedding = self.encoder.encode(query)

        # Поиск похожих
        results = self.collection.query(
            query_embeddings=[query_embedding.tolist()],
            n_results=top_k,
            where=filter_metadata  # Опциональный фильтр
        )

        # Форматирование результатов
        patterns = []
        if results['ids'] and results['ids'][0]:
            for i in range(len(results['ids'][0])):
                pattern = {
                    'task_id': results['ids'][0][i],
                    'description': results['documents'][0][i],
                    'solution': results['metadatas'][0][i].get('solution', ''),
                    'similarity': 1.0 - results['distances'][0][i],  # Косинусное расстояние -> сходство
                    'metadata': results['metadatas'][0][i]
                }
                patterns.append(pattern)

        return patterns

    def get_pattern(self, task_id: str) -> Optional[Dict]:
        """
        Получить конкретный паттерн по ID.

        Args:
            task_id: ID задачи

        Returns:
            Информация о паттерне или None если не найден
        """
        try:
            results = self.collection.get(ids=[task_id])

            if results['ids']:
                return {
                    'task_id': results['ids'][0],
                    'description': results['documents'][0],
                    'solution': results['metadatas'][0].get('solution', ''),
                    'metadata': results['metadatas'][0]
                }
        except Exception:
            pass

        return None

    def update_pattern(self, task_id: str, solution: str = None,
                      metadata: Optional[Dict] = None):
        """
        Обновить существующий паттерн.

        Args:
            task_id: ID задачи
            solution: Новое решение (опционально)
            metadata: Новые метаданные (опционально)
        """
        # Получить текущий паттерн
        current = self.get_pattern(task_id)
        if not current:
            raise ValueError(f"Паттерн {task_id} не найден")

        # Обновление метаданных
        new_meta = current['metadata'].copy()
        if solution:
            new_meta['solution'] = solution
        if metadata:
            new_meta.update(metadata)

        # Обновление в ChromaDB
        self.collection.update(
            ids=[task_id],
            metadatas=[new_meta]
        )

    def delete_pattern(self, task_id: str):
        """
        Удалить паттерн из библиотеки.

        Args:
            task_id: ID задачи для удаления
        """
        self.collection.delete(ids=[task_id])

    def get_all_patterns(self, limit: int = 100) -> List[Dict]:
        """
        Получить все паттерны из библиотеки.

        Args:
            limit: Максимум паттернов для возврата

        Returns:
            Список всех паттернов
        """
        results = self.collection.get(limit=limit)

        patterns = []
        if results['ids']:
            for i in range(len(results['ids'])):
                pattern = {
                    'task_id': results['ids'][i],
                    'description': results['documents'][i],
                    'solution': results['metadatas'][i].get('solution', ''),
                    'metadata': results['metadatas'][i]
                }
                patterns.append(pattern)

        return patterns

    def search_by_complexity(self, complexity: str, limit: int = 10) -> List[Dict]:
        """
        Поиск паттернов по уровню сложности.

        Args:
            complexity: Уровень сложности (program, simple, medium, complex)
            limit: Максимум результатов

        Returns:
            Список паттернов заданной сложности
        """
        results = self.collection.get(
            where={"complexity": complexity},
            limit=limit
        )

        patterns = []
        if results['ids']:
            for i in range(len(results['ids'])):
                pattern = {
                    'task_id': results['ids'][i],
                    'description': results['documents'][i],
                    'solution': results['metadatas'][i].get('solution', ''),
                    'metadata': results['metadatas'][i]
                }
                patterns.append(pattern)

        return patterns

    def get_statistics(self) -> Dict:
        """
        Получить статистику библиотеки.

        Returns:
            Словарь со статистикой
        """
        all_patterns = self.get_all_patterns(limit=10000)

        # Подсчёт по сложности
        complexity_counts = {}
        success_scores = []

        for pattern in all_patterns:
            complexity = pattern['metadata'].get('complexity', 'unknown')
            complexity_counts[complexity] = complexity_counts.get(complexity, 0) + 1

            score = pattern['metadata'].get('success_score')
            if score is not None:
                success_scores.append(float(score))

        avg_success = sum(success_scores) / len(success_scores) if success_scores else 0.0

        return {
            'total_patterns': len(all_patterns),
            'by_complexity': complexity_counts,
            'average_success_score': avg_success
        }

    def reset(self):
        """Очистить всю библиотеку (осторожно!)."""
        self.client.delete_collection("task_patterns")
        self.collection = self.client.create_collection(
            name="task_patterns",
            metadata={"description": "Успешные паттерны решения задач"}
        )

    def export_to_json(self, output_path: str):
        """
        Экспорт всех паттернов в JSON файл.

        Args:
            output_path: Путь к выходному файлу
        """
        patterns = self.get_all_patterns(limit=10000)

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(patterns, f, ensure_ascii=False, indent=2)

    def import_from_json(self, input_path: str):
        """
        Импорт паттернов из JSON файла.

        Args:
            input_path: Путь к входному файлу
        """
        with open(input_path, 'r', encoding='utf-8') as f:
            patterns = json.load(f)

        for pattern in patterns:
            self.add_pattern(
                task_id=pattern['task_id'],
                description=pattern['description'],
                solution=pattern['solution'],
                metadata=pattern.get('metadata', {})
            )
