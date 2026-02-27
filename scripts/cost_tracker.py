#!/usr/bin/env python3
"""
Cost Tracker — анализатор экономии маршрутизации моделей.

Читает данные из data/token_usage.db и показывает:
- Реальную стоимость по ценам моделей
- Гипотетическую стоимость (если бы всё делал Opus)
- Экономию за разные периоды (день/неделя/месяц/всё время)

Использование:
    python3 scripts/cost_tracker.py              # Отчёт за сегодня
    python3 scripts/cost_tracker.py --week       # За неделю
    python3 scripts/cost_tracker.py --month      # За месяц
    python3 scripts/cost_tracker.py --all        # За всё время
    python3 scripts/cost_tracker.py --json       # JSON формат
    python3 scripts/cost_tracker.py --csv        # CSV экспорт в data/cost_report.csv
"""

import os
import sys
import sqlite3
import argparse
import json
import csv
from datetime import datetime, timedelta
from typing import Optional, Dict, Any

# Настройка пути для импорта из корня проекта
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

# Пути к файлам данных
DB_PATH = os.path.join(ROOT, "data", "token_usage.db")
CSV_PATH = os.path.join(ROOT, "data", "cost_report.csv")

# Цены моделей за 1 000 000 токенов (USD)
PRICES = {
    "opus": {"input": 15.00, "output": 75.00},
    "sonnet": {"input": 3.00, "output": 15.00},
    "flash": {"input": 0.50, "output": 3.00},
    "pro": {"input": 2.00, "output": 12.00},
}

# Порядок отображения моделей в отчёте
DISPLAY_ORDER = ["opus", "flash", "pro", "sonnet"]


def get_stats(period: str = "today") -> Optional[Dict[str, Any]]:
    """Извлекает статистику из базы данных за указанный период.

    Args:
        period: 'today', 'week', 'month' или 'all'

    Returns:
        Словарь со статистикой или None при ошибке
    """
    if not os.path.exists(DB_PATH):
        return None

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    now = datetime.now()
    days_count = 1
    period_name = ""

    # Определение фильтра по времени
    if period == "today":
        today_str = now.strftime("%Y-%m-%d")
        where_clause = f"started_at LIKE '{today_str}%'"
        period_name = f"{today_str} (сегодня)"
        days_count = 1
    elif period == "week":
        date_limit = (now - timedelta(days=7)).isoformat()
        where_clause = f"started_at >= '{date_limit}'"
        period_name = "последние 7 дней"
        days_count = 7
    elif period == "month":
        date_limit = (now - timedelta(days=30)).isoformat()
        where_clause = f"started_at >= '{date_limit}'"
        period_name = "последние 30 дней"
        days_count = 30
    elif period == "all":
        where_clause = "1=1"
        period_name = "за всё время"
        # Расчёт количества дней с момента первой записи
        cursor.execute("SELECT MIN(started_at) FROM tasks")
        first_row = cursor.fetchone()
        if first_row and first_row[0]:
            try:
                first_date = datetime.fromisoformat(first_row[0])
                days_count = max((now - first_date).days, 1)
            except (ValueError, TypeError):
                days_count = 1
        else:
            days_count = 1
    else:
        conn.close()
        return None

    # Количество задач за период
    cursor.execute(f"SELECT COUNT(*) FROM tasks WHERE {where_clause}")
    tasks_count = cursor.fetchone()[0]

    if tasks_count == 0:
        conn.close()
        return {"period_name": period_name, "tasks_count": 0, "days_count": days_count}

    # Все вызовы за период
    cursor.execute(
        f"""
        SELECT c.model, c.input_tokens, c.output_tokens, c.cost_usd
        FROM calls c
        JOIN tasks t ON c.task_id = t.task_id
        WHERE {where_clause}
        """
    )
    calls = cursor.fetchall()
    conn.close()

    total_tokens = 0
    actual_cost = 0.0
    baseline_cost = 0.0

    # Инициализация статистики по каждой модели
    model_stats = {m: {"tokens": 0, "cost": 0.0} for m in DISPLAY_ORDER}

    for model_name, input_tokens, output_tokens, cost_usd in calls:
        # Нормализация названия модели
        m_key = model_name.lower().strip()
        target_model = m_key if m_key in PRICES else None
        if target_model is None:
            # Попытка частичного совпадения
            for key in PRICES:
                if key in m_key:
                    target_model = key
                    break

        tokens = input_tokens + output_tokens
        total_tokens += tokens
        actual_cost += cost_usd

        if target_model and target_model in model_stats:
            model_stats[target_model]["tokens"] += tokens
            model_stats[target_model]["cost"] += cost_usd

        # Базовая стоимость (как если бы всё делал Opus)
        baseline_cost += (
            input_tokens * PRICES["opus"]["input"] / 1_000_000
            + output_tokens * PRICES["opus"]["output"] / 1_000_000
        )

    # Итоговые показатели экономии
    savings = baseline_cost - actual_cost
    savings_pct = (savings / baseline_cost * 100) if baseline_cost > 0 else 0.0
    avg_savings_per_task = savings / tasks_count if tasks_count > 0 else 0.0
    monthly_forecast = (savings / days_count) * 30

    return {
        "period_name": period_name,
        "tasks_count": tasks_count,
        "total_tokens": total_tokens,
        "model_stats": model_stats,
        "actual_cost": actual_cost,
        "baseline_cost": baseline_cost,
        "savings": savings,
        "savings_pct": savings_pct,
        "avg_savings_per_task": avg_savings_per_task,
        "monthly_forecast": monthly_forecast,
        "days_count": days_count,
    }


def print_report(stats: Optional[Dict[str, Any]]) -> None:
    """Выводит красиво оформленный отчёт в консоль."""
    if not stats or stats.get("tasks_count", 0) == 0:
        period = stats["period_name"] if stats else "неизвестно"
        print(f"\n  Нет данных за период: {period}\n")
        return

    w = 50  # Ширина отчёта

    print()
    print("═" * w)
    print("  COST TRACKING — Экономия маршрутизации моделей")
    print("═" * w)
    print(f"  Период: {stats['period_name']}")
    print("─" * w)
    print(f"  Задач выполнено:           {stats['tasks_count']}")
    print(f"  Токенов использовано:      {stats['total_tokens']:,}")
    print("─" * w)
    print("  Модель        Токены     Стоимость   Доля")

    for m in DISPLAY_ORDER:
        m_data = stats["model_stats"][m]
        share = (
            (m_data["cost"] / stats["actual_cost"] * 100)
            if stats["actual_cost"] > 0
            else 0.0
        )
        print(
            f"  {m:<12} {m_data['tokens']:>10,}     "
            f"${m_data['cost']:<9.4f} {share:>5.1f}%"
        )

    print("─" * w)
    print(f"  Фактическая стоимость:    ${stats['actual_cost']:.4f}")
    print(f"  Если бы только Opus:      ${stats['baseline_cost']:.4f}")
    print(
        f"  ЭКОНОМИЯ:                 "
        f"${stats['savings']:.4f} ({stats['savings_pct']:.1f}%)"
    )
    print("─" * w)
    print(f"  Средняя экономия на задачу: ${stats['avg_savings_per_task']:.4f}")
    print(f"  Прогноз за месяц (30д):     ${stats['monthly_forecast']:.2f}")
    print("═" * w)
    print()


def export_json(stats: Optional[Dict[str, Any]]) -> None:
    """Выводит статистику в формате JSON."""
    if not stats:
        print(json.dumps({"error": "Нет данных"}, ensure_ascii=False, indent=2))
        return

    # Подготовка JSON-совместимого словаря
    output = {
        "period": stats["period_name"],
        "tasks_count": stats["tasks_count"],
        "total_tokens": stats.get("total_tokens", 0),
        "actual_cost_usd": round(stats.get("actual_cost", 0.0), 6),
        "baseline_cost_usd": round(stats.get("baseline_cost", 0.0), 6),
        "savings_usd": round(stats.get("savings", 0.0), 6),
        "savings_pct": round(stats.get("savings_pct", 0.0), 2),
        "avg_savings_per_task_usd": round(stats.get("avg_savings_per_task", 0.0), 6),
        "monthly_forecast_usd": round(stats.get("monthly_forecast", 0.0), 2),
        "models": {},
    }

    model_stats = stats.get("model_stats", {})
    for m in DISPLAY_ORDER:
        m_data = model_stats.get(m, {"tokens": 0, "cost": 0.0})
        output["models"][m] = {
            "tokens": m_data["tokens"],
            "cost_usd": round(m_data["cost"], 6),
        }

    print(json.dumps(output, ensure_ascii=False, indent=2))


def export_csv(stats: Optional[Dict[str, Any]]) -> None:
    """Экспортирует статистику в CSV файл data/cost_report.csv."""
    if not stats or stats.get("tasks_count", 0) == 0:
        print("Нет данных для экспорта в CSV.")
        return

    # Убеждаемся что директория data/ существует
    os.makedirs(os.path.dirname(CSV_PATH), exist_ok=True)

    with open(CSV_PATH, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)

        # Заголовок с общей информацией
        writer.writerow(["Период", stats["period_name"]])
        writer.writerow(["Задач", stats["tasks_count"]])
        writer.writerow(["Токенов", stats.get("total_tokens", 0)])
        writer.writerow(["Фактическая стоимость USD", f"{stats.get('actual_cost', 0):.6f}"])
        writer.writerow(["Базовая стоимость (Opus) USD", f"{stats.get('baseline_cost', 0):.6f}"])
        writer.writerow(["Экономия USD", f"{stats.get('savings', 0):.6f}"])
        writer.writerow(["Экономия %", f"{stats.get('savings_pct', 0):.2f}"])
        writer.writerow(["Средняя экономия на задачу USD", f"{stats.get('avg_savings_per_task', 0):.6f}"])
        writer.writerow(["Прогноз за месяц USD", f"{stats.get('monthly_forecast', 0):.2f}"])
        writer.writerow([])

        # Таблица по моделям
        writer.writerow(["Модель", "Токены", "Стоимость USD", "Доля %"])
        model_stats = stats.get("model_stats", {})
        actual = stats.get("actual_cost", 0)
        for m in DISPLAY_ORDER:
            m_data = model_stats.get(m, {"tokens": 0, "cost": 0.0})
            share = (m_data["cost"] / actual * 100) if actual > 0 else 0.0
            writer.writerow([m, m_data["tokens"], f"{m_data['cost']:.6f}", f"{share:.1f}"])

    print(f"CSV экспортирован: {CSV_PATH}")


def main():
    """Точка входа CLI."""
    parser = argparse.ArgumentParser(
        description="Cost Tracker — анализатор экономии маршрутизации моделей",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python3 scripts/cost_tracker.py              # Отчёт за сегодня
  python3 scripts/cost_tracker.py --week       # За неделю
  python3 scripts/cost_tracker.py --month      # За месяц
  python3 scripts/cost_tracker.py --all        # За всё время
  python3 scripts/cost_tracker.py --json       # JSON формат
  python3 scripts/cost_tracker.py --csv        # CSV экспорт
        """,
    )

    # Периоды — взаимоисключающие
    period_group = parser.add_mutually_exclusive_group()
    period_group.add_argument("--week", action="store_true", help="Отчёт за последние 7 дней")
    period_group.add_argument("--month", action="store_true", help="Отчёт за последние 30 дней")
    period_group.add_argument("--all", action="store_true", help="Отчёт за всё время")

    # Формат вывода
    format_group = parser.add_mutually_exclusive_group()
    format_group.add_argument("--json", action="store_true", help="Вывод в формате JSON")
    format_group.add_argument("--csv", action="store_true", help="Экспорт в CSV (data/cost_report.csv)")

    args = parser.parse_args()

    # Определяем период
    if args.week:
        period = "week"
    elif args.month:
        period = "month"
    elif args.all:
        period = "all"
    else:
        period = "today"

    # Получаем статистику
    stats = get_stats(period)

    # Вывод в нужном формате
    if args.json:
        export_json(stats)
    elif args.csv:
        export_csv(stats)
    else:
        print_report(stats)


if __name__ == "__main__":
    main()
