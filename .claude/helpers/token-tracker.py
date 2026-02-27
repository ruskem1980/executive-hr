#!/usr/bin/env python3
"""
Standalone Token Tracker — работает БЕЗ зависимости от src/reporting/.

Автоматически находит или создаёт БД в PROJECT_ROOT/data/token_usage.db.
Можно использовать из любого проекта после копирования .claude/helpers/.

Использование:
    python3 .claude/helpers/token-tracker.py start "Описание задачи" "simple"
    python3 .claude/helpers/token-tracker.py record TASK_ID opus classifier 200 50
    python3 .claude/helpers/token-tracker.py finish TASK_ID
    python3 .claude/helpers/token-tracker.py report --last 5
    python3 .claude/helpers/token-tracker.py report --date 2026-02-13
    python3 .claude/helpers/token-tracker.py report --total
"""

import sqlite3
import uuid
import sys
import os
from datetime import datetime, date
from pathlib import Path

# Стоимость за 1M токенов (USD)
MODEL_PRICING = {
    "opus": {"input": 15.00, "output": 75.00, "name": "Claude Opus 4.6"},
    "sonnet": {"input": 3.00, "output": 15.00, "name": "Claude Sonnet 4.5"},
    "flash": {"input": 0.50, "output": 3.00, "name": "Gemini Flash"},
    "pro": {"input": 2.00, "output": 12.00, "name": "Gemini Pro"},
}


def find_project_root():
    """Находит корень проекта (где .claude/ или .git/)."""
    p = Path(__file__).resolve().parent
    while p != p.parent:
        if (p / ".claude").is_dir() or (p / ".git").is_dir():
            return p
        p = p.parent
    return Path.cwd()


PROJECT_ROOT = find_project_root()
DB_DIR = PROJECT_ROOT / "data"
DB_PATH = DB_DIR / "token_usage.db"


def get_conn():
    DB_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
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
            baseline_opus_cost_usd REAL DEFAULT 0.0
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
    # Миграция: добавляем колонку если отсутствует (для старых БД)
    try:
        conn.execute("ALTER TABLE tasks ADD COLUMN baseline_opus_cost_usd REAL DEFAULT 0.0")
        conn.commit()
    except Exception:
        pass
    return conn


def calc_cost(model, input_tokens, output_tokens):
    p = MODEL_PRICING.get(model)
    if not p:
        return 0.0
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


def calc_opus_equivalent(input_tokens, output_tokens):
    p = MODEL_PRICING["opus"]
    return (input_tokens * p["input"] + output_tokens * p["output"]) / 1_000_000


def cmd_start(args):
    """start "описание" "complexity" [baseline_input] [baseline_output]
    baseline_input/output — оценочные токены если бы задачу выполнял Opus напрямую.
    Используется для расчёта экономии от скриптов (program tasks).
    """
    query = args[0] if args else "Без описания"
    complexity = args[1] if len(args) > 1 else ""
    baseline_input = int(args[2]) if len(args) > 2 else 0
    baseline_output = int(args[3]) if len(args) > 3 else 0
    baseline_opus_cost = calc_opus_equivalent(baseline_input, baseline_output)
    task_id = datetime.now().strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:6]
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO tasks (task_id, query, complexity, started_at, baseline_opus_cost_usd) VALUES (?, ?, ?, ?, ?)",
            (task_id, query, complexity, datetime.now().isoformat(), baseline_opus_cost),
        )
    print(task_id)


def cmd_record(args):
    """record TASK_ID model role input_tokens output_tokens"""
    if len(args) < 5:
        print("Использование: record TASK_ID model role input_tokens output_tokens", file=sys.stderr)
        sys.exit(1)
    task_id, model, role = args[0], args[1], args[2]
    inp, out = int(args[3]), int(args[4])
    cost = calc_cost(model, inp, out)
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO calls (task_id, model, role, input_tokens, output_tokens, cost_usd, timestamp) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (task_id, model, role, inp, out, cost, datetime.now().isoformat()),
        )


def cmd_finish(args):
    """finish TASK_ID"""
    task_id = args[0] if args else ""
    if not task_id:
        print("Использование: finish TASK_ID", file=sys.stderr)
        sys.exit(1)
    with get_conn() as conn:
        row = conn.execute(
            "SELECT COALESCE(SUM(input_tokens),0) as inp, "
            "COALESCE(SUM(output_tokens),0) as out, "
            "COALESCE(SUM(cost_usd),0.0) as cost "
            "FROM calls WHERE task_id = ?",
            (task_id,),
        ).fetchone()
        total_in, total_out, total_cost = row["inp"], row["out"], row["cost"]
        opus_cost = calc_opus_equivalent(total_in, total_out)
        conn.execute(
            "UPDATE tasks SET finished_at=?, total_input_tokens=?, total_output_tokens=?, "
            "total_cost_usd=?, opus_only_cost_usd=? WHERE task_id=?",
            (datetime.now().isoformat(), total_in, total_out, total_cost, opus_cost, task_id),
        )
    # Автоматически выводим отчёт
    print_task_summary(task_id)


def _safe(row, key, default=0.0):
    """Безопасное чтение поля из sqlite3.Row (поддержка старых БД)."""
    try:
        return row[key]
    except (IndexError, KeyError):
        return default


def print_task_summary(task_id):
    with get_conn() as conn:
        task = conn.execute("SELECT * FROM tasks WHERE task_id = ?", (task_id,)).fetchone()
        calls = conn.execute(
            "SELECT model, role, input_tokens, output_tokens, cost_usd FROM calls WHERE task_id = ? ORDER BY call_id",
            (task_id,),
        ).fetchall()
    if not task:
        print(f"Задача {task_id} не найдена")
        return

    W = 74  # ширина отчёта
    SEP = "=" * W
    LINE = "  " + "─" * (W - 2)

    query_short = task["query"][:62] + ("..." if len(task["query"]) > 62 else "")
    complexity = task["complexity"] or "?"
    grand_in = task["total_input_tokens"]
    grand_out = task["total_output_tokens"]
    grand_cost = task["total_cost_usd"]
    grand_tok = grand_in + grand_out
    opus_cost = task["opus_only_cost_usd"]          # Opus-цена для фактических LLM-вызовов
    baseline_cost = _safe(task, "baseline_opus_cost_usd", 0.0)  # Opus-цена для всей задачи (baseline)

    # ── Заголовок ──────────────────────────────────────────────────────────
    print()
    print(SEP)
    print(f"  Задача:    {query_short}")
    print(f"  Сложность: {complexity}")
    print(SEP)

    # ── БЛОК 1: Применённые модели (каждый вызов) ──────────────────────────
    print(f"\n  ПРИМЕНЁННЫЕ МОДЕЛИ:")
    if calls:
        print(f"  {'Модель':<24} {'Роль':<13} {'Input':>8} {'Output':>8} {'Стоимость':>11}")
        print(LINE)
        model_totals = {}
        for c in calls:
            m = c["model"]
            full_name = MODEL_PRICING.get(m, {}).get("name", m)
            print(f"  {full_name:<24} {c['role']:<13} {c['input_tokens']:>8,} {c['output_tokens']:>8,} ${c['cost_usd']:>9.4f}")
            if m not in model_totals:
                model_totals[m] = {"input": 0, "output": 0, "cost": 0.0}
            model_totals[m]["input"] += c["input_tokens"]
            model_totals[m]["output"] += c["output_tokens"]
            model_totals[m]["cost"] += c["cost_usd"]
    else:
        print(f"  — (задача выполнена скриптами, LLM не вызывался)")
        model_totals = {}

    # ── БЛОК 2: Итого по каждой модели ─────────────────────────────────────
    if model_totals:
        print(f"\n  ИТОГО ПО МОДЕЛЯМ:")
        print(f"  {'Модель':<24} {'Токены':>10}          {'Стоимость':>11}")
        print(LINE)
        for m, t in model_totals.items():
            mtok = t["input"] + t["output"]
            pct_tok = (mtok / grand_tok * 100) if grand_tok > 0 else 0
            pct_cost = (t["cost"] / grand_cost * 100) if grand_cost > 0 else 0
            name = MODEL_PRICING.get(m, {}).get("name", m)
            print(f"  {name:<24} {mtok:>8,} ({pct_tok:4.1f}%)   ${t['cost']:>8.4f} ({pct_cost:4.1f}%)")

    print(LINE)
    print(f"  {'Всего токенов:':<24} {grand_tok:>8,}            Реальная стоимость: ${grand_cost:.4f}")

    # ── БЛОК 3: Экономия (три источника) ───────────────────────────────────
    #   script_savings   = baseline_cost - opus_cost
    #                      (сколько сэкономили, переложив работу на скрипты)
    #   routing_savings  = opus_cost - grand_cost
    #                      (сколько сэкономили, используя дешёвые модели вместо Opus)
    #   total_savings    = script_savings + routing_savings

    script_savings = max(0.0, baseline_cost - opus_cost) if baseline_cost > 0 else 0.0
    routing_savings = max(0.0, opus_cost - grand_cost)
    total_savings = script_savings + routing_savings

    # Базовая стоимость для расчёта % итого
    full_baseline = baseline_cost if baseline_cost > 0 else opus_cost

    print(f"\n  ЭКОНОМИЯ:")
    print(LINE)

    # Строка 1: от скриптов
    if script_savings > 0:
        s_pct = (script_savings / full_baseline * 100) if full_baseline > 0 else 0
        print(f"  {'От скриптов (py/sh):':<35} ${script_savings:>8.4f}   ({s_pct:.1f}% — основная работа скрипты)")
    else:
        if complexity == "program" and baseline_cost > 0:
            print(f"  {'От скриптов (py/sh):':<35} ${'0.0000':>8}   (LLM-вызовы превысили baseline-оценку)")
        elif complexity == "program":
            print(f"  {'От скриптов (py/sh):':<35} {'—':>10}   (program-задача, baseline не задан)")
        else:
            print(f"  {'От скриптов (py/sh):':<35} ${'0.0000':>8}   (задача — LLM pipeline)")

    # Строка 2: от маршрутизации
    if routing_savings > 0:
        r_pct = (routing_savings / opus_cost * 100) if opus_cost > 0 else 0
        print(f"  {'От маршрутизации (vs Opus):':<35} ${routing_savings:>8.4f}   ({r_pct:.1f}% — дешёвые модели вместо Opus)")
    elif opus_cost > 0:
        print(f"  {'От маршрутизации (vs Opus):':<35} ${'0.0000':>8}   (использован Opus напрямую)")
    else:
        print(f"  {'От маршрутизации (vs Opus):':<35} ${'0.0000':>8}   (LLM не вызывался)")

    # Строка 3: итого
    print(LINE)
    if full_baseline > 0:
        t_pct = (total_savings / full_baseline * 100)
        print(f"  {'ИТОГО ЭКОНОМИЯ:':<35} ${total_savings:>8.4f}   ({t_pct:.1f}% от ${full_baseline:.4f})")
    else:
        print(f"  {'ИТОГО ЭКОНОМИЯ:':<35} ${'0.0000':>8}   (нет данных для сравнения)")

    print(SEP)
    print()


def cmd_report(args):
    """report [--last N | --date YYYY-MM-DD | --total]"""
    if "--total" in args:
        with get_conn() as conn:
            total = conn.execute(
                "SELECT COUNT(*) as tasks, COALESCE(SUM(total_input_tokens + total_output_tokens), 0) as tokens, "
                "COALESCE(SUM(total_cost_usd), 0) as cost, COALESCE(SUM(opus_only_cost_usd), 0) as opus_cost FROM tasks"
            ).fetchone()
            days = conn.execute("SELECT COUNT(DISTINCT SUBSTR(started_at, 1, 10)) as days FROM tasks").fetchone()
        print(f"\n  Всего задач:   {total['tasks']}")
        print(f"  Всего токенов: {total['tokens']:,}")
        print(f"  Потрачено:     ${total['cost']:.4f}")
        print(f"  Без маршрут.:  ${total['opus_cost']:.4f}")
        if total["opus_cost"] > 0:
            print(f"  Экономия:      ${total['opus_cost'] - total['cost']:.4f} ({(1-total['cost']/total['opus_cost'])*100:.1f}%)")
        print(f"  Рабочих дней:  {days['days']}\n")
        return

    if "--last" in args:
        idx = args.index("--last")
        n = int(args[idx + 1]) if idx + 1 < len(args) else 5
        with get_conn() as conn:
            tasks = conn.execute("SELECT task_id FROM tasks ORDER BY started_at DESC LIMIT ?", (n,)).fetchall()
        for t in reversed(tasks):
            print_task_summary(t["task_id"])
        return

    if "--date" in args:
        idx = args.index("--date")
        d = args[idx + 1] if idx + 1 < len(args) else date.today().isoformat()
    else:
        d = date.today().isoformat()

    with get_conn() as conn:
        tasks = conn.execute("SELECT task_id FROM tasks WHERE started_at LIKE ? ORDER BY started_at", (f"{d}%",)).fetchall()
    if not tasks:
        print(f"\nНет данных за {d}")
        return
    print(f"\nОтчёт за {d}: {len(tasks)} задач")
    for t in tasks:
        print_task_summary(t["task_id"])


def cmd_summary(args):
    """summary TASK_ID — показать отчёт без завершения задачи"""
    task_id = args[0] if args else ""
    if not task_id:
        print("Использование: summary TASK_ID", file=sys.stderr)
        sys.exit(1)
    print_task_summary(task_id)


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Использование: python3 token-tracker.py <start|record|finish|summary|report> [args...]")
        sys.exit(1)
    cmd = sys.argv[1]
    rest = sys.argv[2:]
    if cmd == "start":
        cmd_start(rest)
    elif cmd == "record":
        cmd_record(rest)
    elif cmd == "finish":
        cmd_finish(rest)
    elif cmd == "summary":
        cmd_summary(rest)
    elif cmd == "report":
        cmd_report(rest)
    else:
        print(f"Неизвестная команда: {cmd}", file=sys.stderr)
        sys.exit(1)
