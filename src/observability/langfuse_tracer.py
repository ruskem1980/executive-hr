"""
LangfuseTracer — трейсинг и мониторинг LLM-вызовов.

Интегрируется с Langfuse для production-мониторинга.
Если Langfuse недоступен (нет пакета или ключей) — автоматически
переключается на локальное хранение в SQLite (data/traces.db).

Использование:
    tracer = LangfuseTracer()

    # Ручной трейсинг
    trace_id = tracer.start_trace("classify_task", {"user": "admin"})
    span_id = tracer.start_span(trace_id, "call_llm", {"prompt": "..."})
    tracer.log_llm_call(trace_id, model="opus", input_text="...", output_text="...",
                        input_tokens=200, output_tokens=50, cost=0.02, latency_ms=1200)
    tracer.end_span(span_id, {"result": "ok"})
    tracer.score(trace_id, "quality", 0.95, "Высокое качество ответа")
    tracer.end_trace(trace_id)

    # Декоратор
    @traced("my_function")
    def my_function(x):
        return x * 2

    # Context manager
    with tracer.span(trace_id, "preprocessing"):
        data = preprocess(raw)
"""

import os
import uuid
import time
import json
import sqlite3
import functools
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List
from contextlib import contextmanager

logger = logging.getLogger(__name__)

# Путь к локальной БД для fallback
_DB_DIR = Path(__file__).parent.parent.parent / "data"
_DB_PATH = _DB_DIR / "traces.db"


class LangfuseTracer:
    """
    Трейсер LLM-вызовов с интеграцией Langfuse и SQLite fallback.

    Проверяет наличие пакета langfuse и environment-переменных:
    - LANGFUSE_PUBLIC_KEY
    - LANGFUSE_SECRET_KEY
    - LANGFUSE_HOST (опционально, по умолчанию https://cloud.langfuse.com)

    Если что-то отсутствует — всё сохраняется локально в SQLite.
    """

    def __init__(
        self,
        project_name: str = "pt_standart_agents",
        enabled: bool = True,
        db_path: Optional[Path] = None,
    ):
        """
        Инициализация трейсера.

        Аргументы:
            project_name: имя проекта для Langfuse
            enabled: включить/выключить трейсинг (False = полностью выключен)
            db_path: путь к SQLite для fallback (по умолчанию data/traces.db)
        """
        self._project_name = project_name
        self._enabled = enabled
        self._db_path = Path(db_path) if db_path else _DB_PATH

        # Langfuse клиент (если доступен)
        self._langfuse = None
        self._langfuse_available = False

        # Локальные объекты для хранения активных трейсов/спанов (Langfuse API)
        self._active_traces: Dict[str, Any] = {}
        self._active_spans: Dict[str, Any] = {}

        if enabled:
            self._try_init_langfuse()
            self._init_local_db()

    def _try_init_langfuse(self) -> None:
        """Попытка инициализировать Langfuse клиент."""
        public_key = os.environ.get("LANGFUSE_PUBLIC_KEY")
        secret_key = os.environ.get("LANGFUSE_SECRET_KEY")
        host = os.environ.get("LANGFUSE_HOST", "https://cloud.langfuse.com")

        if not public_key or not secret_key:
            logger.info(
                "Langfuse ключи не настроены (LANGFUSE_PUBLIC_KEY, LANGFUSE_SECRET_KEY). "
                "Используется локальный SQLite fallback."
            )
            return

        try:
            from langfuse import Langfuse

            self._langfuse = Langfuse(
                public_key=public_key,
                secret_key=secret_key,
                host=host,
            )
            self._langfuse_available = True
            logger.info("Langfuse инициализирован: %s", host)
        except ImportError:
            logger.info(
                "Пакет langfuse не установлен. Используется SQLite fallback. "
                "Установите: pip install langfuse"
            )
        except Exception as e:
            logger.warning("Ошибка инициализации Langfuse: %s. Используется SQLite fallback.", e)

    def _init_local_db(self) -> None:
        """Инициализация локальной SQLite БД для fallback."""
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS traces (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    status TEXT DEFAULT 'running',
                    metadata_json TEXT,
                    output_json TEXT
                );

                CREATE TABLE IF NOT EXISTS spans (
                    id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    start_time TEXT NOT NULL,
                    end_time TEXT,
                    input_json TEXT,
                    output_json TEXT,
                    status TEXT DEFAULT 'running',
                    FOREIGN KEY (trace_id) REFERENCES traces(id)
                );

                CREATE TABLE IF NOT EXISTS generations (
                    id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    input_text TEXT,
                    output_text TEXT,
                    input_tokens INTEGER DEFAULT 0,
                    output_tokens INTEGER DEFAULT 0,
                    cost REAL DEFAULT 0.0,
                    latency_ms REAL DEFAULT 0.0,
                    metadata_json TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (trace_id) REFERENCES traces(id)
                );

                CREATE TABLE IF NOT EXISTS scores (
                    id TEXT PRIMARY KEY,
                    trace_id TEXT NOT NULL,
                    name TEXT NOT NULL,
                    value REAL NOT NULL,
                    comment TEXT,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (trace_id) REFERENCES traces(id)
                );

                CREATE INDEX IF NOT EXISTS idx_spans_trace ON spans(trace_id);
                CREATE INDEX IF NOT EXISTS idx_generations_trace ON generations(trace_id);
                CREATE INDEX IF NOT EXISTS idx_scores_trace ON scores(trace_id);
                CREATE INDEX IF NOT EXISTS idx_traces_start ON traces(start_time);
            """)

    def _conn(self) -> sqlite3.Connection:
        """Создаёт подключение к SQLite."""
        conn = sqlite3.connect(str(self._db_path))
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def _gen_id() -> str:
        """Генерация уникального идентификатора."""
        return uuid.uuid4().hex[:16]

    @staticmethod
    def _now_iso() -> str:
        """Текущее время в ISO формате."""
        return datetime.now().isoformat()

    # ── Публичные методы ──

    def start_trace(self, name: str, metadata: Optional[Dict] = None) -> str:
        """
        Начало нового трейса.

        Аргументы:
            name: имя трейса (например, "classify_task", "generate_code")
            metadata: дополнительные метаданные

        Возвращает:
            trace_id — идентификатор трейса
        """
        if not self._enabled:
            return self._gen_id()

        trace_id = self._gen_id()
        now = self._now_iso()

        # Langfuse
        if self._langfuse_available and self._langfuse:
            try:
                trace = self._langfuse.trace(
                    id=trace_id,
                    name=name,
                    metadata=metadata or {},
                )
                self._active_traces[trace_id] = trace
            except Exception as e:
                logger.warning("Langfuse start_trace ошибка: %s", e)

        # Локальная БД (всегда сохраняем)
        try:
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO traces (id, name, start_time, metadata_json) VALUES (?, ?, ?, ?)",
                    (trace_id, name, now, json.dumps(metadata or {}, ensure_ascii=False)),
                )
        except Exception as e:
            logger.warning("Локальная запись trace ошибка: %s", e)

        return trace_id

    def start_span(
        self,
        trace_id: str,
        name: str,
        input_data: Optional[Dict] = None,
    ) -> str:
        """
        Начало span внутри трейса.

        Аргументы:
            trace_id: идентификатор родительского трейса
            name: имя span (например, "call_llm", "parse_response")
            input_data: входные данные span

        Возвращает:
            span_id — идентификатор span
        """
        if not self._enabled:
            return self._gen_id()

        span_id = self._gen_id()
        now = self._now_iso()

        # Langfuse
        if self._langfuse_available and self._langfuse:
            try:
                trace = self._active_traces.get(trace_id)
                if trace:
                    span = trace.span(
                        id=span_id,
                        name=name,
                        input=input_data,
                    )
                    self._active_spans[span_id] = span
            except Exception as e:
                logger.warning("Langfuse start_span ошибка: %s", e)

        # Локальная БД
        try:
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO spans (id, trace_id, name, start_time, input_json) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (
                        span_id,
                        trace_id,
                        name,
                        now,
                        json.dumps(input_data or {}, ensure_ascii=False),
                    ),
                )
        except Exception as e:
            logger.warning("Локальная запись span ошибка: %s", e)

        return span_id

    def end_span(
        self,
        span_id: str,
        output_data: Optional[Dict] = None,
        status: str = "ok",
    ) -> None:
        """
        Завершение span.

        Аргументы:
            span_id: идентификатор span
            output_data: результат span
            status: статус завершения ('ok', 'error')
        """
        if not self._enabled:
            return

        now = self._now_iso()

        # Langfuse
        if self._langfuse_available:
            try:
                span = self._active_spans.pop(span_id, None)
                if span:
                    span.end(output=output_data, level="ERROR" if status == "error" else "DEFAULT")
            except Exception as e:
                logger.warning("Langfuse end_span ошибка: %s", e)

        # Локальная БД
        try:
            with self._conn() as conn:
                conn.execute(
                    "UPDATE spans SET end_time = ?, output_json = ?, status = ? WHERE id = ?",
                    (now, json.dumps(output_data or {}, ensure_ascii=False), status, span_id),
                )
        except Exception as e:
            logger.warning("Локальная запись end_span ошибка: %s", e)

    def log_llm_call(
        self,
        trace_id: str,
        model: str,
        input_text: str,
        output_text: str,
        input_tokens: int,
        output_tokens: int,
        cost: float,
        latency_ms: float,
        metadata: Optional[Dict] = None,
    ) -> None:
        """
        Логирование вызова LLM (generation).

        Аргументы:
            trace_id: идентификатор трейса
            model: название модели ('opus', 'flash', 'pro', 'gpt-4', ...)
            input_text: входной текст (промпт)
            output_text: выходной текст (ответ)
            input_tokens: количество входных токенов
            output_tokens: количество выходных токенов
            cost: стоимость вызова в USD
            latency_ms: задержка в миллисекундах
            metadata: дополнительные метаданные
        """
        if not self._enabled:
            return

        gen_id = self._gen_id()
        now = self._now_iso()

        # Langfuse
        if self._langfuse_available and self._langfuse:
            try:
                trace = self._active_traces.get(trace_id)
                if trace:
                    trace.generation(
                        id=gen_id,
                        name=f"llm-{model}",
                        model=model,
                        input=input_text,
                        output=output_text,
                        usage={
                            "input": input_tokens,
                            "output": output_tokens,
                            "total": input_tokens + output_tokens,
                        },
                        metadata={
                            **(metadata or {}),
                            "cost_usd": cost,
                            "latency_ms": latency_ms,
                        },
                    )
            except Exception as e:
                logger.warning("Langfuse log_llm_call ошибка: %s", e)

        # Локальная БД
        try:
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO generations "
                    "(id, trace_id, model, input_text, output_text, "
                    "input_tokens, output_tokens, cost, latency_ms, metadata_json, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
                    (
                        gen_id,
                        trace_id,
                        model,
                        input_text,
                        output_text,
                        input_tokens,
                        output_tokens,
                        cost,
                        latency_ms,
                        json.dumps(metadata or {}, ensure_ascii=False),
                        now,
                    ),
                )
        except Exception as e:
            logger.warning("Локальная запись generation ошибка: %s", e)

    def end_trace(
        self,
        trace_id: str,
        output: Optional[Dict] = None,
        status: str = "ok",
    ) -> None:
        """
        Завершение трейса.

        Аргументы:
            trace_id: идентификатор трейса
            output: финальный результат трейса
            status: статус завершения ('ok', 'error')
        """
        if not self._enabled:
            return

        now = self._now_iso()

        # Langfuse
        if self._langfuse_available:
            try:
                trace = self._active_traces.pop(trace_id, None)
                if trace:
                    trace.update(output=output, metadata={"status": status})
            except Exception as e:
                logger.warning("Langfuse end_trace ошибка: %s", e)

        # Локальная БД
        try:
            with self._conn() as conn:
                conn.execute(
                    "UPDATE traces SET end_time = ?, status = ?, output_json = ? WHERE id = ?",
                    (now, status, json.dumps(output or {}, ensure_ascii=False), trace_id),
                )
        except Exception as e:
            logger.warning("Локальная запись end_trace ошибка: %s", e)

    def score(
        self,
        trace_id: str,
        name: str,
        value: float,
        comment: Optional[str] = None,
    ) -> None:
        """
        Оценка качества для трейса.

        Аргументы:
            trace_id: идентификатор трейса
            name: название метрики ('quality', 'relevance', 'accuracy')
            value: значение оценки (0.0 - 1.0)
            comment: комментарий к оценке
        """
        if not self._enabled:
            return

        score_id = self._gen_id()
        now = self._now_iso()

        # Langfuse
        if self._langfuse_available and self._langfuse:
            try:
                self._langfuse.score(
                    trace_id=trace_id,
                    name=name,
                    value=value,
                    comment=comment,
                )
            except Exception as e:
                logger.warning("Langfuse score ошибка: %s", e)

        # Локальная БД
        try:
            with self._conn() as conn:
                conn.execute(
                    "INSERT INTO scores (id, trace_id, name, value, comment, created_at) "
                    "VALUES (?, ?, ?, ?, ?, ?)",
                    (score_id, trace_id, name, value, comment, now),
                )
        except Exception as e:
            logger.warning("Локальная запись score ошибка: %s", e)

    def flush(self) -> None:
        """
        Отправка буфера в Langfuse.

        Langfuse буферизирует события и отправляет пакетами.
        Вызовите flush() чтобы отправить всё немедленно.
        """
        if self._langfuse_available and self._langfuse:
            try:
                self._langfuse.flush()
            except Exception as e:
                logger.warning("Langfuse flush ошибка: %s", e)

    def get_local_traces(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Получение локальных трейсов из SQLite.

        Аргументы:
            limit: максимальное количество трейсов

        Возвращает:
            Список словарей с данными трейсов (включая spans, generations, scores)
        """
        try:
            with self._conn() as conn:
                traces = conn.execute(
                    "SELECT * FROM traces ORDER BY start_time DESC LIMIT ?",
                    (limit,),
                ).fetchall()

                result = []
                for t in traces:
                    trace_data = {
                        "id": t["id"],
                        "name": t["name"],
                        "start_time": t["start_time"],
                        "end_time": t["end_time"],
                        "status": t["status"],
                        "metadata": json.loads(t["metadata_json"] or "{}"),
                        "output": json.loads(t["output_json"] or "{}"),
                    }

                    # Span'ы
                    spans = conn.execute(
                        "SELECT * FROM spans WHERE trace_id = ? ORDER BY start_time",
                        (t["id"],),
                    ).fetchall()
                    trace_data["spans"] = [
                        {
                            "id": s["id"],
                            "name": s["name"],
                            "start_time": s["start_time"],
                            "end_time": s["end_time"],
                            "status": s["status"],
                            "input": json.loads(s["input_json"] or "{}"),
                            "output": json.loads(s["output_json"] or "{}"),
                        }
                        for s in spans
                    ]

                    # Генерации (LLM вызовы)
                    gens = conn.execute(
                        "SELECT * FROM generations WHERE trace_id = ? ORDER BY created_at",
                        (t["id"],),
                    ).fetchall()
                    trace_data["generations"] = [
                        {
                            "id": g["id"],
                            "model": g["model"],
                            "input_text": g["input_text"],
                            "output_text": g["output_text"],
                            "input_tokens": g["input_tokens"],
                            "output_tokens": g["output_tokens"],
                            "cost": g["cost"],
                            "latency_ms": g["latency_ms"],
                            "metadata": json.loads(g["metadata_json"] or "{}"),
                            "created_at": g["created_at"],
                        }
                        for g in gens
                    ]

                    # Оценки
                    scores = conn.execute(
                        "SELECT * FROM scores WHERE trace_id = ? ORDER BY created_at",
                        (t["id"],),
                    ).fetchall()
                    trace_data["scores"] = [
                        {
                            "id": sc["id"],
                            "name": sc["name"],
                            "value": sc["value"],
                            "comment": sc["comment"],
                            "created_at": sc["created_at"],
                        }
                        for sc in scores
                    ]

                    result.append(trace_data)

                return result

        except Exception as e:
            logger.warning("Ошибка чтения локальных трейсов: %s", e)
            return []

    # ── Context Manager для span ──

    @contextmanager
    def span(self, trace_id: str, name: str, input_data: Optional[Dict] = None):
        """
        Context manager для автоматического трейсинга блока кода.

        Использование:
            with tracer.span(trace_id, "preprocessing", {"raw": data}):
                result = preprocess(data)

        Аргументы:
            trace_id: идентификатор трейса
            name: имя span
            input_data: входные данные
        """
        span_id = self.start_span(trace_id, name, input_data)
        status = "ok"
        output = {}
        try:
            yield span_id
        except Exception as e:
            status = "error"
            output = {"error": str(e), "error_type": type(e).__name__}
            raise
        finally:
            self.end_span(span_id, output_data=output, status=status)

    # ── Свойства ──

    @property
    def is_langfuse_active(self) -> bool:
        """Активен ли Langfuse (пакет + ключи)."""
        return self._langfuse_available

    @property
    def is_enabled(self) -> bool:
        """Включён ли трейсинг."""
        return self._enabled


# ── Глобальный трейсер (синглтон) ──

_global_tracer: Optional[LangfuseTracer] = None


def _get_global_tracer() -> LangfuseTracer:
    """Получение или создание глобального трейсера."""
    global _global_tracer
    if _global_tracer is None:
        _global_tracer = LangfuseTracer()
    return _global_tracer


# ── Декоратор @traced ──


def traced(name: Optional[str] = None):
    """
    Декоратор для автоматического трейсинга функций.

    Создаёт трейс с именем функции (или указанным name),
    логирует входные аргументы и результат.

    Использование:
        @traced("classify_task")
        def classify_task(description: str) -> str:
            return "simple"

        @traced()  # имя = "my_function"
        def my_function(x: int) -> int:
            return x * 2

    Аргументы:
        name: имя трейса (по умолчанию — имя функции)
    """

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            tracer = _get_global_tracer()
            trace_name = name or func.__name__

            # Подготовка входных данных (безопасная сериализация)
            input_data = {}
            try:
                if args:
                    input_data["args"] = [_safe_serialize(a) for a in args]
                if kwargs:
                    input_data["kwargs"] = {
                        k: _safe_serialize(v) for k, v in kwargs.items()
                    }
            except Exception:
                input_data["args"] = "<не сериализуемые>"

            trace_id = tracer.start_trace(trace_name, {"function": func.__qualname__})
            span_id = tracer.start_span(trace_id, f"{trace_name}_exec", input_data)

            start_time = time.time()
            status = "ok"
            output = {}

            try:
                result = func(*args, **kwargs)
                try:
                    output["result"] = _safe_serialize(result)
                except Exception:
                    output["result"] = "<не сериализуемый>"
                return result
            except Exception as e:
                status = "error"
                output = {"error": str(e), "error_type": type(e).__name__}
                raise
            finally:
                elapsed_ms = (time.time() - start_time) * 1000
                output["latency_ms"] = round(elapsed_ms, 2)
                tracer.end_span(span_id, output_data=output, status=status)
                tracer.end_trace(trace_id, output=output, status=status)

        return wrapper

    # Поддержка вызова без скобок: @traced вместо @traced()
    if callable(name):
        func = name
        name = None
        return traced(None)(func)

    return decorator


def _safe_serialize(obj: Any) -> Any:
    """Безопасная сериализация объекта для JSON."""
    if obj is None or isinstance(obj, (str, int, float, bool)):
        return obj
    if isinstance(obj, (list, tuple)):
        return [_safe_serialize(item) for item in obj[:10]]  # Лимит 10 элементов
    if isinstance(obj, dict):
        return {
            str(k): _safe_serialize(v)
            for k, v in list(obj.items())[:20]  # Лимит 20 ключей
        }
    # Для остальных типов — строковое представление
    try:
        s = str(obj)
        return s[:500] if len(s) > 500 else s  # Лимит 500 символов
    except Exception:
        return f"<{type(obj).__name__}>"
