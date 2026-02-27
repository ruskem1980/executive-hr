"""
TokenTracker - система учёта расхода токенов LLM моделей.

Хранит данные в SQLite, отображает таблицы после каждой задачи
и генерирует дневные отчёты.

Использование:
    # Трекинг внутри workflow
    tracker = TokenTracker()
    task_id = tracker.start_task("Проверь безопасность auth")
    tracker.record_call(task_id, model="opus", role="classifier", input_tokens=150, output_tokens=30)
    tracker.record_call(task_id, model="flash", role="executor", input_tokens=2400, output_tokens=800)
    tracker.finish_task(task_id)
    tracker.print_task_summary(task_id)

    # Дневной отчёт (CLI)
    python -m src.reporting.token_tracker
    python -m src.reporting.token_tracker --date 2026-02-10
"""

import sqlite3
import uuid
import time
from datetime import datetime, date
from pathlib import Path
from typing import Optional, List, Dict


# Стоимость за 1M токенов (USD)
MODEL_PRICING = {
    "opus": {"input": 15.00, "output": 75.00, "name": "Claude Opus 4.6"},
    "sonnet": {"input": 3.00, "output": 15.00, "name": "Claude Sonnet 4.5"},
    "flash": {"input": 0.50, "output": 3.00, "name": "Gemini Flash"},
    "pro": {"input": 2.00, "output": 12.00, "name": "Gemini Pro"},
}

DB_DIR = Path(__file__).parent.parent.parent / "data"
DB_PATH = DB_DIR / "token_usage.db"


class TokenTracker:
    """Система учёта токенов с SQLite хранением."""

    def __init__(self, db_path: Optional[Path] = None):
        # Поддержка и Path, и str
        self.db_path = Path(db_path) if db_path else DB_PATH
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _init_db(self):
        """Создаёт таблицы если не существуют."""
        with self._conn() as conn:
            conn.executescript("""
                CREATE TABLE IF NOT EXISTS tasks (
                    task_id TEXT PRIMARY KEY,
                    query TEXT NOT NULL,
                    complexity TEXT,
                    started_at TEXT NOT NULL,
                    finished_at TEXT,
                    total_input_tokens INTEGER DEFAULT 0,
                    total_output_tokens INTEGER DEFAULT 0,
                    total_cost_usd REAL DEFAULT 0.0,
                    opus_only_cost_usd REAL DEFAULT 0.0,
                    success INTEGER DEFAULT 1,
                    execution_time REAL DEFAULT 0.0,
                    retry_count INTEGER DEFAULT 0
                );

                CREATE TABLE IF NOT EXISTS calls (
                    call_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    task_id TEXT NOT NULL,
                    model TEXT NOT NULL,
                    role TEXT NOT NULL,
                    input_tokens INTEGER NOT NULL,
                    output_tokens INTEGER NOT NULL,
                    cost_usd REAL NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (task_id) REFERENCES tasks(task_id)
                );

                CREATE INDEX IF NOT EXISTS idx_calls_task ON calls(task_id);
                CREATE INDEX IF NOT EXISTS idx_tasks_date ON tasks(started_at);
            """)

            # Migration: добавить колонки если они отсутствуют (для существующих БД)
            cursor = conn.cursor()
            cursor.execute("PRAGMA table_info(tasks)")
            columns = [row[1] for row in cursor.fetchall()]

            if 'success' not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN success INTEGER DEFAULT 1")
            if 'execution_time' not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN execution_time REAL DEFAULT 0.0")
            if 'retry_count' not in columns:
                conn.execute("ALTER TABLE tasks ADD COLUMN retry_count INTEGER DEFAULT 0")

    def _conn(self) -> sqlite3.Connection:
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    @staticmethod
    def calc_cost(model: str, input_tokens: int, output_tokens: int) -> float:
        """Считает стоимость вызова в USD."""
        pricing = MODEL_PRICING.get(model)
        if not pricing:
            return 0.0
        return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000

    @staticmethod
    def calc_opus_equivalent(input_tokens: int, output_tokens: int) -> float:
        """Сколько бы стоило на чистом Opus."""
        p = MODEL_PRICING["opus"]
        return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000

    # ── Жизненный цикл задачи ──

    def start_task(self, query: str, complexity: str = "") -> str:
        """Начинает новую задачу, возвращает task_id."""
        task_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO tasks (task_id, query, complexity, started_at) VALUES (?, ?, ?, ?)",
                (task_id, query, complexity, datetime.now().isoformat()),
            )
        return task_id

    def record_call(
        self,
        task_id: str,
        model: str,
        role: str,
        input_tokens: int,
        output_tokens: int,
    ):
        """Записывает один вызов LLM."""
        cost = self.calc_cost(model, input_tokens, output_tokens)
        with self._conn() as conn:
            conn.execute(
                "INSERT INTO calls (task_id, model, role, input_tokens, output_tokens, cost_usd, timestamp) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (task_id, model, role, input_tokens, output_tokens, cost, datetime.now().isoformat()),
            )

    def finish_task(self, task_id: str, complexity: str = ""):
        """Завершает задачу, пересчитывает итоги."""
        with self._conn() as conn:
            row = conn.execute(
                "SELECT COALESCE(SUM(input_tokens),0) as inp, "
                "COALESCE(SUM(output_tokens),0) as out, "
                "COALESCE(SUM(cost_usd),0.0) as cost "
                "FROM calls WHERE task_id = ?",
                (task_id,),
            ).fetchone()

            total_in = row["inp"]
            total_out = row["out"]
            total_cost = row["cost"]
            opus_cost = self.calc_opus_equivalent(total_in, total_out)

            updates = {
                "finished_at": datetime.now().isoformat(),
                "total_input_tokens": total_in,
                "total_output_tokens": total_out,
                "total_cost_usd": total_cost,
                "opus_only_cost_usd": opus_cost,
            }
            if complexity:
                updates["complexity"] = complexity

            set_clause = ", ".join(f"{k} = ?" for k in updates)
            conn.execute(
                f"UPDATE tasks SET {set_clause} WHERE task_id = ?",
                (*updates.values(), task_id),
            )

    # ── Отображение после задачи ──

    def print_task_summary(self, task_id: str):
        """Печатает таблицу расхода по моделям после задачи."""
        with self._conn() as conn:
            task = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
            calls = conn.execute(
                "SELECT model, role, input_tokens, output_tokens, cost_usd FROM calls WHERE task_id = ? ORDER BY call_id",
                (task_id,),
            ).fetchall()

        if not task:
            print(f"Задача {task_id} не найдена")
            return

        query_short = task["query"][:60] + ("..." if len(task["query"]) > 60 else "")
        complexity = task["complexity"] or "?"

        print()
        print("=" * 72)
        print(f"  Задача: {query_short}")
        print(f"  Сложность: {complexity}")
        print("=" * 72)

        # Таблица вызовов
        print(f"{'Модель':<10} {'Роль':<14} {'Input':>8} {'Output':>8} {'Всего':>8} {'Стоимость':>11}")
        print("-" * 72)

        model_totals: Dict[str, Dict] = {}
        for c in calls:
            m = c["model"]
            total_tok = c["input_tokens"] + c["output_tokens"]
            print(
                f"{m:<10} {c['role']:<14} {c['input_tokens']:>8,} {c['output_tokens']:>8,} "
                f"{total_tok:>8,} ${c['cost_usd']:>9.4f}"
            )
            if m not in model_totals:
                model_totals[m] = {"input": 0, "output": 0, "cost": 0.0}
            model_totals[m]["input"] += c["input_tokens"]
            model_totals[m]["output"] += c["output_tokens"]
            model_totals[m]["cost"] += c["cost_usd"]

        # Итого по моделям
        print("-" * 72)
        grand_in = task["total_input_tokens"]
        grand_out = task["total_output_tokens"]
        grand_cost = task["total_cost_usd"]
        opus_cost = task["opus_only_cost_usd"]

        for m, t in model_totals.items():
            total_tok = t["input"] + t["output"]
            pct_tokens = (total_tok / (grand_in + grand_out) * 100) if (grand_in + grand_out) > 0 else 0
            pct_cost = (t["cost"] / grand_cost * 100) if grand_cost > 0 else 0
            name = MODEL_PRICING.get(m, {}).get("name", m)
            print(f"  {name:<20} {total_tok:>8,} ток ({pct_tokens:4.1f}%)   ${t['cost']:>8.4f} ({pct_cost:4.1f}%)")

        print("-" * 72)
        print(f"  {'ИТОГО':<20} {grand_in + grand_out:>8,} ток          ${grand_cost:>8.4f}")
        print(f"  {'Без маршрутизации':<20} {grand_in + grand_out:>8,} ток          ${opus_cost:>8.4f}")

        if opus_cost > 0:
            saving_pct = (1 - grand_cost / opus_cost) * 100
            saved_usd = opus_cost - grand_cost
            print(f"  {'ЭКОНОМИЯ':<20} {' ':>8}              ${saved_usd:>8.4f} ({saving_pct:.1f}%)")

        print("=" * 72)
        print()

    # ── Дневной отчёт ──

    def print_daily_report(self, target_date: Optional[date] = None):
        """Печатает сводный дневной отчёт по всем задачам."""
        if target_date is None:
            target_date = date.today()

        date_prefix = target_date.isoformat()

        with self._conn() as conn:
            tasks = conn.execute(
                "SELECT * FROM tasks WHERE started_at LIKE ? ORDER BY started_at",
                (f"{date_prefix}%",),
            ).fetchall()

            # Агрегация по моделям за день
            model_stats = conn.execute(
                "SELECT c.model, "
                "SUM(c.input_tokens) as total_input, "
                "SUM(c.output_tokens) as total_output, "
                "SUM(c.cost_usd) as total_cost, "
                "COUNT(*) as num_calls "
                "FROM calls c "
                "JOIN tasks t ON c.task_id = t.task_id "
                "WHERE t.started_at LIKE ? "
                "GROUP BY c.model "
                "ORDER BY total_cost DESC",
                (f"{date_prefix}%",),
            ).fetchall()

        if not tasks:
            print(f"\nНет данных за {target_date.isoformat()}")
            return

        print()
        print("=" * 80)
        print(f"  ДНЕВНОЙ ОТЧЁТ: {target_date.isoformat()}")
        print(f"  Задач выполнено: {len(tasks)}")
        print("=" * 80)

        # ── Таблица задач с разбивкой по моделям ──

        # Собираем вызовы по каждой задаче
        task_ids = [t["task_id"] for t in tasks]
        task_calls = {}
        with self._conn() as conn:
            for tid in task_ids:
                task_calls[tid] = conn.execute(
                    "SELECT model, SUM(input_tokens) as inp, SUM(output_tokens) as out, "
                    "SUM(cost_usd) as cost, COUNT(*) as cnt "
                    "FROM calls WHERE task_id = ? GROUP BY model ORDER BY cost DESC",
                    (tid,),
                ).fetchall()

        grand_tokens = 0
        grand_cost = 0.0
        grand_opus = 0.0

        for i, t in enumerate(tasks, 1):
            query_short = t["query"][:60] + (".." if len(t["query"]) > 60 else "")
            tokens = t["total_input_tokens"] + t["total_output_tokens"]
            cost = t["total_cost_usd"]
            opus = t["opus_only_cost_usd"]
            saving = f"{(1 - cost/opus)*100:.0f}%" if opus > 0 else "-"

            print()
            print(f"  {i}. {query_short}")
            print(f"     Сложность: {t['complexity'] or '?'}    Токены: {tokens:,}    Стоимость: ${cost:.4f}    Экономия: {saving}")

            # Модели этой задачи
            calls = task_calls.get(t["task_id"], [])
            if calls:
                print(f"     {'Модель':<22} {'Вызовов':>7} {'Input':>8} {'Output':>8} {'Всего':>8} {'Стоим.':>10} {'Доля':>6}")
                print(f"     {'-'*69}")
                for c in calls:
                    name = MODEL_PRICING.get(c["model"], {}).get("name", c["model"])
                    total = c["inp"] + c["out"]
                    pct = (c["cost"] / cost * 100) if cost > 0 else 0
                    print(
                        f"     {name:<22} {c['cnt']:>7} {c['inp']:>8,} {c['out']:>8,} "
                        f"{total:>8,} ${c['cost']:>8.4f} {pct:>5.1f}%"
                    )

            grand_tokens += tokens
            grand_cost += cost
            grand_opus += opus

        print()
        print("-" * 80)
        grand_saving = f"{(1 - grand_cost/grand_opus)*100:.1f}%" if grand_opus > 0 else "-"
        print(f"  ИТОГО ЗА ДЕНЬ: {len(tasks)} задач    {grand_tokens:,} ток    ${grand_cost:.4f}    Экономия: {grand_saving}")

        # ── Распределение по моделям ──
        print()
        print(f"{'Модель':<22} {'Вызовов':>8} {'Input':>10} {'Output':>10} {'Всего':>10} {'Стоимость':>12} {'Доля $':>8}")
        print("-" * 80)

        for ms in model_stats:
            name = MODEL_PRICING.get(ms["model"], {}).get("name", ms["model"])
            total = ms["total_input"] + ms["total_output"]
            pct = (ms["total_cost"] / grand_cost * 100) if grand_cost > 0 else 0
            print(
                f"{name:<22} {ms['num_calls']:>8} {ms['total_input']:>10,} "
                f"{ms['total_output']:>10,} {total:>10,} ${ms['total_cost']:>10.4f} {pct:>7.1f}%"
            )

        print("-" * 80)
        print(
            f"{'ИТОГО':<22} {sum(ms['num_calls'] for ms in model_stats):>8} "
            f"{'':>10} {'':>10} {grand_tokens:>10,} ${grand_cost:>10.4f} {'100.0%':>8}"
        )

        # ── Сравнение с Opus-only ──
        print()
        print(f"  Стоимость с маршрутизацией:  ${grand_cost:.4f}")
        print(f"  Стоимость без (чистый Opus): ${grand_opus:.4f}")
        if grand_opus > 0:
            print(f"  Экономия за день:            ${grand_opus - grand_cost:.4f} ({(1-grand_cost/grand_opus)*100:.1f}%)")
        print("=" * 80)
        print()

    # ── Общая статистика ──

    def print_total_stats(self):
        """Печатает общую статистику за всё время."""
        with self._conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) as tasks, "
                "COALESCE(SUM(total_input_tokens + total_output_tokens), 0) as tokens, "
                "COALESCE(SUM(total_cost_usd), 0) as cost, "
                "COALESCE(SUM(opus_only_cost_usd), 0) as opus_cost "
                "FROM tasks"
            ).fetchone()

            days = conn.execute(
                "SELECT COUNT(DISTINCT SUBSTR(started_at, 1, 10)) as days FROM tasks"
            ).fetchone()

        print(f"\n  Всего задач:   {total['tasks']}")
        print(f"  Всего токенов: {total['tokens']:,}")
        print(f"  Всего потрачено:      ${total['cost']:.4f}")
        print(f"  Без маршрутизации:    ${total['opus_cost']:.4f}")
        if total["opus_cost"] > 0:
            print(f"  Общая экономия:       ${total['opus_cost'] - total['cost']:.4f} ({(1-total['cost']/total['opus_cost'])*100:.1f}%)")
        print(f"  Рабочих дней:         {days['days']}")
        if days["days"] and days["days"] > 0:
            print(f"  Среднее за день:      ${total['cost']/days['days']:.4f}")
        print()


# ── CLI ──

def main():
    """CLI для просмотра отчётов по расходу токенов."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Отчёт по расходу токенов LLM моделей",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python -m src.reporting.token_tracker                   # отчёт за сегодня
  python -m src.reporting.token_tracker --date 2026-02-10 # за конкретный день
  python -m src.reporting.token_tracker --total            # общая статистика
  python -m src.reporting.token_tracker --last 5           # последние 5 задач
        """,
    )

    parser.add_argument("--date", type=str, default=None, help="Дата отчёта (YYYY-MM-DD), по умолчанию сегодня")
    parser.add_argument("--total", action="store_true", help="Показать общую статистику за всё время")
    parser.add_argument("--last", type=int, default=0, help="Показать последние N задач с деталями")
    parser.add_argument("--db", type=str, default=None, help="Путь к БД (по умолчанию data/token_usage.db)")

    args = parser.parse_args()

    db = Path(args.db) if args.db else None
    tracker = TokenTracker(db_path=db)

    if args.total:
        tracker.print_total_stats()
        return

    if args.last > 0:
        with tracker._conn() as conn:
            tasks = conn.execute(
                "SELECT task_id FROM tasks ORDER BY started_at DESC LIMIT ?",
                (args.last,),
            ).fetchall()
        for t in reversed(tasks):
            tracker.print_task_summary(t["task_id"])
        return

    target_date = date.fromisoformat(args.date) if args.date else date.today()
    tracker.print_daily_report(target_date)


if __name__ == "__main__":
    main()
