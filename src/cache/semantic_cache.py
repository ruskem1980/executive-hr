"""
Семантический кеш LLM-ответов.

Кеширует ответы моделей по семантическому сходству промптов.
Использует sentence-transformers (all-MiniLM-L6-v2) для эмбеддингов
и cosine similarity для поиска похожих запросов.

Если sentence-transformers недоступен — fallback на точный хеш-поиск.

Хранение: SQLite (data/semantic_cache/cache.db).
Thread-safe, поддерживает TTL, автоматическое удаление устаревших записей.

Использование:
    cache = SemanticCache(similarity_threshold=0.85)

    # Прямое использование
    cached = cache.get('Напиши сортировку пузырьком')
    if cached is None:
        result = gateway.completion('flash', 'Напиши сортировку пузырьком')
        cache.put('Напиши сортировку пузырьком', result)

    # Кеш-прокси (автоматически)
    result = cache.get_or_call('Напиши сортировку', 'flash', gateway=gw)
"""

import hashlib
import json
import logging
import sqlite3
import time
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional

import numpy as np

if TYPE_CHECKING:
    from src.gateway.litellm_gateway import LiteLLMGateway

logger = logging.getLogger(__name__)

# Путь к директории кеша по умолчанию
_DEFAULT_CACHE_DIR = Path(__file__).parent.parent.parent / 'data' / 'semantic_cache'

# Модель для эмбеддингов
_EMBEDDING_MODEL_NAME = 'all-MiniLM-L6-v2'

# Проверяем доступность sentence-transformers при импорте
try:
    from sentence_transformers import SentenceTransformer
    _HAS_SENTENCE_TRANSFORMERS = True
except ImportError:
    _HAS_SENTENCE_TRANSFORMERS = False
    logger.info(
        'sentence-transformers не установлен — семантический поиск недоступен, '
        'будет использован exact-match кеш (по хешу)'
    )


class SemanticCache:
    """Семантический кеш LLM-ответов с cosine similarity поиском."""

    def __init__(
        self,
        similarity_threshold: float = 0.85,
        cache_dir: str = '',
        max_size: int = 10000,
    ):
        """
        Инициализация кеша.

        Аргументы:
            similarity_threshold: порог cosine similarity для считания
                                  промптов семантически идентичными (0.0-1.0).
            cache_dir: директория для хранения кеша. По умолчанию data/semantic_cache.
            max_size: максимальное количество записей в кеше.
        """
        self._threshold = similarity_threshold
        self._max_size = max_size
        self._cache_dir = Path(cache_dir) if cache_dir else _DEFAULT_CACHE_DIR
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._db_path = self._cache_dir / 'cache.db'

        # Статистика
        self._hits = 0
        self._misses = 0

        # Инициализация БД
        self._init_db()

        # Инициализация модели эмбеддингов (ленивая загрузка)
        self._model: Optional[Any] = None
        self._embedding_dim: Optional[int] = None

    # ── Инициализация ──

    def _init_db(self) -> None:
        """Создаёт таблицу кеша если не существует."""
        with self._conn() as conn:
            conn.execute('''
                CREATE TABLE IF NOT EXISTS cache (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    prompt_hash TEXT NOT NULL,
                    prompt_text TEXT NOT NULL,
                    embedding BLOB,
                    response TEXT NOT NULL,
                    model TEXT,
                    created_at REAL NOT NULL,
                    expires_at REAL NOT NULL,
                    hit_count INTEGER DEFAULT 0
                )
            ''')
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_cache_hash ON cache(prompt_hash)'
            )
            conn.execute(
                'CREATE INDEX IF NOT EXISTS idx_cache_expires ON cache(expires_at)'
            )

    def _conn(self) -> sqlite3.Connection:
        """Создаёт подключение к SQLite (thread-safe)."""
        conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn

    def _get_model(self) -> Optional[Any]:
        """Ленивая загрузка модели sentence-transformers."""
        if not _HAS_SENTENCE_TRANSFORMERS:
            return None

        if self._model is None:
            try:
                self._model = SentenceTransformer(_EMBEDDING_MODEL_NAME)
                # Определяем размерность эмбеддинга
                test_emb = self._model.encode(['test'], convert_to_numpy=True)
                self._embedding_dim = test_emb.shape[1]
                logger.info(
                    'Загружена модель %s (dim=%d)',
                    _EMBEDDING_MODEL_NAME, self._embedding_dim,
                )
            except Exception as exc:
                logger.warning('Не удалось загрузить модель эмбеддингов: %s', exc)
                return None

        return self._model

    # ── Публичные методы ──

    def get(self, prompt: str, model: Optional[str] = None) -> Optional[Dict[str, Any]]:
        """
        Поиск в кеше по семантическому сходству (или по хешу как fallback).

        Аргументы:
            prompt: текст промпта для поиска.
            model: фильтр по модели (опционально).

        Возвращает:
            закешированный ответ (dict) или None если не найден.
        """
        # Удаляем устаревшие записи
        self._evict_expired()

        prompt_hash = self._hash(prompt)
        now = time.time()

        # Попытка 1: Точное совпадение по хешу (быстрый путь)
        exact = self._find_by_hash(prompt_hash, model, now)
        if exact is not None:
            self._hits += 1
            return exact

        # Попытка 2: Семантический поиск (если доступен)
        sem_model = self._get_model()
        if sem_model is not None:
            semantic = self._find_by_similarity(prompt, model, now)
            if semantic is not None:
                self._hits += 1
                return semantic

        self._misses += 1
        return None

    def put(
        self,
        prompt: str,
        response: Dict[str, Any],
        model: Optional[str] = None,
        ttl: int = 3600,
    ) -> None:
        """
        Сохранение ответа в кеш.

        Аргументы:
            prompt: текст промпта (ключ).
            response: ответ LLM для кеширования (dict).
            model: алиас модели (опционально).
            ttl: время жизни записи в секундах (по умолчанию 1 час).
        """
        # Проверяем лимит размера кеша
        self._ensure_size_limit()

        prompt_hash = self._hash(prompt)
        now = time.time()
        expires_at = now + ttl

        # Генерируем эмбеддинг
        embedding_blob = self._encode_prompt(prompt)

        # Сериализуем ответ
        response_json = json.dumps(response, ensure_ascii=False, default=str)

        with self._conn() as conn:
            # Удаляем старую запись с таким же хешем (обновление)
            if model:
                conn.execute(
                    'DELETE FROM cache WHERE prompt_hash = ? AND model = ?',
                    (prompt_hash, model),
                )
            else:
                conn.execute(
                    'DELETE FROM cache WHERE prompt_hash = ? AND model IS NULL',
                    (prompt_hash,),
                )

            conn.execute(
                '''INSERT INTO cache
                   (prompt_hash, prompt_text, embedding, response, model, created_at, expires_at, hit_count)
                   VALUES (?, ?, ?, ?, ?, ?, ?, 0)''',
                (prompt_hash, prompt, embedding_blob, response_json, model, now, expires_at),
            )

        logger.debug('Кеш: сохранён ответ для модели %s (TTL=%ds)', model, ttl)

    def get_or_call(
        self,
        prompt: str,
        model_alias: str,
        gateway: Optional['LiteLLMGateway'] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Кеш-прокси: возвращает из кеша или вызывает gateway и кеширует результат.

        Аргументы:
            prompt: текст промпта.
            model_alias: алиас модели.
            gateway: экземпляр LiteLLMGateway (обязателен при отсутствии кеша).
            **kwargs: дополнительные аргументы для gateway.completion().

        Возвращает:
            dict — результат из кеша или от LLM.

        Исключения:
            ValueError: если кеш пуст и gateway не предоставлен.
        """
        # Пробуем кеш
        cached = self.get(prompt, model=model_alias)
        if cached is not None:
            cached['cached'] = True
            return cached

        # Вызываем LLM
        if gateway is None:
            raise ValueError(
                'Ответ не найден в кеше, а gateway не предоставлен для вызова LLM'
            )

        result = gateway.completion(model_alias, prompt, **kwargs)
        result['cached'] = False

        # Кешируем
        ttl = kwargs.pop('ttl', 3600)
        self.put(prompt, result, model=model_alias, ttl=ttl)

        return result

    def invalidate(
        self,
        prompt: Optional[str] = None,
        model: Optional[str] = None,
    ) -> int:
        """
        Инвалидация записей кеша.

        Аргументы:
            prompt: текст промпта для удаления (опционально).
            model: фильтр по модели (опционально).

        Возвращает:
            количество удалённых записей.
        """
        with self._conn() as conn:
            if prompt and model:
                prompt_hash = self._hash(prompt)
                cursor = conn.execute(
                    'DELETE FROM cache WHERE prompt_hash = ? AND model = ?',
                    (prompt_hash, model),
                )
            elif prompt:
                prompt_hash = self._hash(prompt)
                cursor = conn.execute(
                    'DELETE FROM cache WHERE prompt_hash = ?', (prompt_hash,)
                )
            elif model:
                cursor = conn.execute(
                    'DELETE FROM cache WHERE model = ?', (model,)
                )
            else:
                # Без аргументов — ничего не удаляем (защита от случайной очистки)
                return 0

            deleted = cursor.rowcount
            logger.info('Кеш: инвалидировано %d записей', deleted)
            return deleted

    def stats(self) -> Dict[str, Any]:
        """
        Статистика кеша.

        Возвращает:
            dict с ключами: hits, misses, hit_rate, cache_size, db_size_bytes.
        """
        with self._conn() as conn:
            row = conn.execute('SELECT COUNT(*) as cnt FROM cache').fetchone()
            cache_size = row['cnt']

        total = self._hits + self._misses
        hit_rate = (self._hits / total * 100) if total > 0 else 0.0

        db_size = self._db_path.stat().st_size if self._db_path.exists() else 0

        return {
            'hits': self._hits,
            'misses': self._misses,
            'hit_rate': round(hit_rate, 2),
            'cache_size': cache_size,
            'max_size': self._max_size,
            'db_size_bytes': db_size,
            'similarity_threshold': self._threshold,
            'semantic_search_available': _HAS_SENTENCE_TRANSFORMERS and self._get_model() is not None,
        }

    def clear(self) -> int:
        """
        Полная очистка кеша.

        Возвращает:
            количество удалённых записей.
        """
        with self._conn() as conn:
            row = conn.execute('SELECT COUNT(*) as cnt FROM cache').fetchone()
            count = row['cnt']
            conn.execute('DELETE FROM cache')

        self._hits = 0
        self._misses = 0
        logger.info('Кеш полностью очищен (%d записей удалено)', count)
        return count

    # ── Внутренние методы ──

    @staticmethod
    def _hash(prompt: str) -> str:
        """SHA-256 хеш промпта для быстрого exact-match поиска."""
        return hashlib.sha256(prompt.encode('utf-8')).hexdigest()

    def _encode_prompt(self, prompt: str) -> Optional[bytes]:
        """
        Генерирует эмбеддинг промпта и возвращает как bytes (BLOB).

        Возвращает None если модель эмбеддингов недоступна.
        """
        model = self._get_model()
        if model is None:
            return None

        try:
            embedding = model.encode([prompt], convert_to_numpy=True)[0]
            return embedding.astype(np.float32).tobytes()
        except Exception as exc:
            logger.warning('Ошибка генерации эмбеддинга: %s', exc)
            return None

    def _bytes_to_embedding(self, blob: bytes) -> np.ndarray:
        """Десериализует BLOB обратно в numpy-вектор."""
        return np.frombuffer(blob, dtype=np.float32)

    def _cosine_similarity(self, a: np.ndarray, b: np.ndarray) -> float:
        """Вычисляет cosine similarity между двумя векторами."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _find_by_hash(
        self,
        prompt_hash: str,
        model: Optional[str],
        now: float,
    ) -> Optional[Dict[str, Any]]:
        """Точный поиск по хешу промпта."""
        with self._conn() as conn:
            if model:
                row = conn.execute(
                    '''SELECT id, response FROM cache
                       WHERE prompt_hash = ? AND model = ? AND expires_at > ?
                       ORDER BY created_at DESC LIMIT 1''',
                    (prompt_hash, model, now),
                ).fetchone()
            else:
                row = conn.execute(
                    '''SELECT id, response FROM cache
                       WHERE prompt_hash = ? AND expires_at > ?
                       ORDER BY created_at DESC LIMIT 1''',
                    (prompt_hash, now),
                ).fetchone()

            if row is None:
                return None

            # Увеличиваем счётчик попаданий
            conn.execute(
                'UPDATE cache SET hit_count = hit_count + 1 WHERE id = ?',
                (row['id'],),
            )

            return json.loads(row['response'])

    def _find_by_similarity(
        self,
        prompt: str,
        model: Optional[str],
        now: float,
    ) -> Optional[Dict[str, Any]]:
        """Семантический поиск по cosine similarity."""
        query_embedding = self._encode_prompt(prompt)
        if query_embedding is None:
            return None

        query_vec = self._bytes_to_embedding(query_embedding)

        with self._conn() as conn:
            if model:
                rows = conn.execute(
                    '''SELECT id, embedding, response FROM cache
                       WHERE embedding IS NOT NULL AND model = ? AND expires_at > ?''',
                    (model, now),
                ).fetchall()
            else:
                rows = conn.execute(
                    '''SELECT id, embedding, response FROM cache
                       WHERE embedding IS NOT NULL AND expires_at > ?''',
                    (now,),
                ).fetchall()

        best_score = 0.0
        best_row = None

        for row in rows:
            stored_vec = self._bytes_to_embedding(row['embedding'])
            score = self._cosine_similarity(query_vec, stored_vec)
            if score > best_score:
                best_score = score
                best_row = row

        if best_row is not None and best_score >= self._threshold:
            # Увеличиваем счётчик попаданий
            with self._conn() as conn:
                conn.execute(
                    'UPDATE cache SET hit_count = hit_count + 1 WHERE id = ?',
                    (best_row['id'],),
                )

            logger.debug(
                'Кеш: семантическое совпадение с similarity=%.3f (порог=%.2f)',
                best_score, self._threshold,
            )
            return json.loads(best_row['response'])

        return None

    def _evict_expired(self) -> None:
        """Удаляет записи с истёкшим TTL."""
        now = time.time()
        with self._conn() as conn:
            cursor = conn.execute(
                'DELETE FROM cache WHERE expires_at <= ?', (now,)
            )
            if cursor.rowcount > 0:
                logger.debug('Кеш: удалено %d устаревших записей', cursor.rowcount)

    def _ensure_size_limit(self) -> None:
        """Удаляет самые старые записи при превышении max_size."""
        with self._conn() as conn:
            row = conn.execute('SELECT COUNT(*) as cnt FROM cache').fetchone()
            current_size = row['cnt']

            if current_size >= self._max_size:
                # Удаляем 10% самых старых и наименее используемых записей
                to_delete = max(self._max_size // 10, 1)
                conn.execute(
                    '''DELETE FROM cache WHERE id IN (
                         SELECT id FROM cache ORDER BY hit_count ASC, created_at ASC LIMIT ?
                       )''',
                    (to_delete,),
                )
                logger.info(
                    'Кеш: удалено %d записей (лимит %d)',
                    to_delete, self._max_size,
                )
