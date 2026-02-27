#!/usr/bin/env python3
"""
CLI Dashboard с Rich formatting для PT_Standart_Agents

Показывает:
- QCS Index (Quality-Cost-Speed composite metric)
- Breakdown по метрикам
- Топ-5 задач по экономии
- Success rate за период
- Alerts
"""

import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Rich library для красивого форматирования
try:
    from rich.console import Console
    from rich.table import Table
    from rich.panel import Panel
    from rich.progress import Progress, SpinnerColumn, TextColumn
    from rich.layout import Layout
    from rich.text import Text
    from rich import box
    HAS_RICH = True
except ImportError:
    HAS_RICH = False
    print("⚠️  Rich library не установлена. Установите: pip install rich")

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.reporting.token_tracker import TokenTracker
from src.monitoring.alerting import AlertingSystem


class DashboardCLI:
    """CLI Dashboard для метрик PT_Standart_Agents"""

    def __init__(
        self,
        db_path: Optional[str] = None,
        goal: Optional[str] = None
    ):
        """
        Args:
            db_path: Путь к БД token_usage.db
            goal: Приоритетная цель (cost/speed/quality) для адаптивного отображения
        """
        self.db_path = db_path or os.path.join(PROJECT_ROOT, "data", "token_usage.db")
        self.tracker = TokenTracker(db_path=self.db_path)
        self.alerting = AlertingSystem(db_path=self.db_path)
        self.console = Console() if HAS_RICH else None
        self.goal = goal  # cost, speed, quality

    def calculate_qcs_index(
        self,
        quality: float,
        cost_savings: float,
        speed: float,
        goal: Optional[str] = None
    ) -> float:
        """
        Расчёт QCS Index = Quality × w1 + Cost_Savings × w2 + Speed × w3

        Args:
            quality: Метрика качества (0-1)
            cost_savings: Экономия стоимости (0-1)
            speed: Улучшение скорости (0-1)
            goal: Приоритетная цель для адаптивных весов

        Returns:
            QCS Index (0-100)
        """
        # Дефолтные веса
        weights = {"quality": 0.4, "cost": 0.3, "speed": 0.3}

        # Адаптивные веса под цель
        if goal == "cost":
            weights = {"quality": 0.3, "cost": 0.5, "speed": 0.2}
        elif goal == "speed":
            weights = {"quality": 0.3, "cost": 0.2, "speed": 0.5}
        elif goal == "quality":
            weights = {"quality": 0.6, "cost": 0.2, "speed": 0.2}

        qcs = (
            quality * weights["quality"] +
            cost_savings * weights["cost"] +
            speed * weights["speed"]
        ) * 100

        return round(qcs, 1)

    def get_metrics_summary(self, days: int = 7) -> Dict:
        """Получение summary метрик за период"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        start_date = (datetime.now() - timedelta(days=days)).isoformat()

        # Success rate
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
            FROM tasks
            WHERE started_at >= ?
        """, (start_date,))
        total, successful = cursor.fetchone()
        success_rate = successful / total if total > 0 else 0

        # Cost savings (actual vs baseline)
        cursor.execute("""
            SELECT
                SUM(
                    (SELECT SUM(input_tokens *
                        CASE model
                            WHEN 'opus' THEN 0.000015
                            WHEN 'sonnet' THEN 0.000003
                            WHEN 'haiku' THEN 0.000001
                            WHEN 'flash' THEN 0.0000005
                            WHEN 'pro' THEN 0.000002
                            ELSE 0.000015
                        END
                        + output_tokens *
                        CASE model
                            WHEN 'opus' THEN 0.000075
                            WHEN 'sonnet' THEN 0.000015
                            WHEN 'haiku' THEN 0.000005
                            WHEN 'flash' THEN 0.000003
                            WHEN 'pro' THEN 0.000012
                            ELSE 0.000075
                        END
                    )
                    FROM calls
                    WHERE task_id = tasks.task_id)
                ) as actual_cost,
                SUM(
                    (SELECT SUM((input_tokens + output_tokens) * 0.000045)
                    FROM calls
                    WHERE task_id = tasks.task_id)
                ) as baseline_cost
            FROM tasks
            WHERE started_at >= ?
        """, (start_date,))
        actual_cost, baseline_cost = cursor.fetchone()
        actual_cost = actual_cost or 0
        baseline_cost = baseline_cost or 0
        cost_savings = (baseline_cost - actual_cost) / baseline_cost if baseline_cost > 0 else 0

        # Average time (simplified - just using task completion time)
        cursor.execute("""
            SELECT AVG(
                (julianday(finished_at) - julianday(started_at)) * 24 * 60
            ) as avg_minutes
            FROM tasks
            WHERE started_at >= ? AND finished_at IS NOT NULL
        """, (start_date,))
        avg_time = cursor.fetchone()[0] or 0

        # Speed improvement (assume baseline = 10 min, current = avg_time)
        baseline_time = 10.0  # минут
        speed_improvement = (baseline_time - avg_time) / baseline_time if baseline_time > 0 else 0
        speed_improvement = max(0, min(1, speed_improvement))  # Clamp 0-1

        conn.close()

        return {
            "quality": success_rate,
            "cost_savings": cost_savings,
            "speed": speed_improvement,
            "success_rate": success_rate,
            "actual_cost": actual_cost,
            "baseline_cost": baseline_cost,
            "avg_time": avg_time,
            "total_tasks": total
        }

    def get_top_savings_tasks(self, limit: int = 5) -> List[Tuple]:
        """Топ N задач по экономии стоимости"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
            SELECT
                tasks.task_id,
                tasks.query,
                tasks.complexity,
                (SELECT SUM(input_tokens *
                    CASE model
                        WHEN 'opus' THEN 0.000015
                        WHEN 'sonnet' THEN 0.000003
                        WHEN 'haiku' THEN 0.000001
                        WHEN 'flash' THEN 0.0000005
                        WHEN 'pro' THEN 0.000002
                        ELSE 0.000015
                    END
                    + output_tokens *
                    CASE model
                        WHEN 'opus' THEN 0.000075
                        WHEN 'sonnet' THEN 0.000015
                        WHEN 'haiku' THEN 0.000005
                        WHEN 'flash' THEN 0.000003
                        WHEN 'pro' THEN 0.000012
                        ELSE 0.000075
                    END
                )
                FROM calls
                WHERE task_id = tasks.task_id) as actual_cost,
                (SELECT SUM((input_tokens + output_tokens) * 0.000045)
                FROM calls
                WHERE task_id = tasks.task_id) as baseline_cost
            FROM tasks
            WHERE finished_at IS NOT NULL
            ORDER BY (baseline_cost - actual_cost) DESC
            LIMIT ?
        """, (limit,))

        return cursor.fetchall()

    def render_dashboard(self, days: int = 7) -> None:
        """Отрисовка dashboard в CLI"""
        if not HAS_RICH:
            self._render_simple_dashboard(days)
            return

        metrics = self.get_metrics_summary(days)
        qcs_index = self.calculate_qcs_index(
            quality=metrics["quality"],
            cost_savings=metrics["cost_savings"],
            speed=metrics["speed"],
            goal=self.goal
        )

        # Заголовок
        title_text = Text()
        title_text.append("📊 PT_Standart_Agents Dashboard\n", style="bold cyan")
        if self.goal:
            title_text.append(f"🎯 Цель: ", style="dim")
            title_text.append(self.goal.upper(), style="bold yellow")

        self.console.print(Panel(title_text, box=box.DOUBLE, expand=False))

        # QCS Index (большой, заметный)
        qcs_color = "green" if qcs_index >= 70 else "yellow" if qcs_index >= 50 else "red"
        qcs_panel = Panel(
            f"[bold {qcs_color}]{qcs_index:.1f}[/bold {qcs_color}] / 100",
            title="[bold]QCS Index[/bold]",
            border_style=qcs_color,
            expand=False
        )
        self.console.print(qcs_panel)

        # Breakdown метрик
        breakdown_table = Table(title="📈 Breakdown метрик", box=box.ROUNDED)
        breakdown_table.add_column("Метрика", style="cyan", no_wrap=True)
        breakdown_table.add_column("Значение", justify="right")
        breakdown_table.add_column("Статус", justify="center")

        def get_status_emoji(value: float, reverse: bool = False) -> str:
            if reverse:  # Для метрик где меньше = лучше
                if value < 0.3: return "✅"
                elif value < 0.7: return "⚠️"
                else: return "❌"
            else:
                if value >= 0.9: return "✅"
                elif value >= 0.7: return "⚠️"
                else: return "❌"

        breakdown_table.add_row(
            "Quality (Success Rate)",
            f"{metrics['quality']:.1%}",
            get_status_emoji(metrics['quality'])
        )
        breakdown_table.add_row(
            "Cost Savings",
            f"{metrics['cost_savings']:.1%}",
            get_status_emoji(metrics['cost_savings'])
        )
        breakdown_table.add_row(
            "Speed Improvement",
            f"{metrics['speed']:.1%}",
            get_status_emoji(metrics['speed'])
        )
        breakdown_table.add_row(
            "Avg Time",
            f"{metrics['avg_time']:.1f} мин",
            get_status_emoji(metrics['avg_time'] / 10, reverse=True)
        )

        self.console.print(breakdown_table)

        # Топ-5 задач по экономии
        top_tasks = self.get_top_savings_tasks(limit=5)
        if top_tasks:
            top_table = Table(title="💰 Топ-5 задач по экономии", box=box.ROUNDED)
            top_table.add_column("ID", style="dim")
            top_table.add_column("Описание", style="cyan")
            top_table.add_column("Сложность", justify="center")
            top_table.add_column("Экономия", justify="right", style="green")

            for task in top_tasks:
                task_id, desc, complexity, actual, baseline = task
                if baseline and actual is not None:
                    savings = baseline - actual
                    top_table.add_row(
                        task_id[:8],
                        desc[:40] + "..." if len(desc) > 40 else desc,
                        complexity or "N/A",
                        f"${savings:.4f}"
                    )

            self.console.print(top_table)

        # Alerts
        alerts = self.alerting.check_all_alerts(days=days)
        if alerts:
            alert_panel = Panel(
                "\n".join([str(alert) for alert in alerts[:3]]),  # Показываем топ-3
                title=f"[bold red]🚨 Alerts ({len(alerts)})[/bold red]",
                border_style="red",
                expand=False
            )
            self.console.print(alert_panel)

        # Footer
        footer_text = Text()
        footer_text.append(f"📅 Период: последние {days} дней | ", style="dim")
        footer_text.append(f"📋 Всего задач: {metrics['total_tasks']}", style="dim")
        self.console.print(Panel(footer_text, box=box.MINIMAL, expand=False))

    def _render_simple_dashboard(self, days: int = 7) -> None:
        """Простая версия dashboard без Rich"""
        metrics = self.get_metrics_summary(days)
        qcs_index = self.calculate_qcs_index(
            quality=metrics["quality"],
            cost_savings=metrics["cost_savings"],
            speed=metrics["speed"],
            goal=self.goal
        )

        print("\n" + "="*80)
        print("  📊 PT_Standart_Agents Dashboard")
        if self.goal:
            print(f"  🎯 Цель: {self.goal.upper()}")
        print("="*80 + "\n")

        print(f"QCS Index: {qcs_index:.1f} / 100")
        print("\nBreakdown метрик:")
        print(f"  Quality (Success Rate): {metrics['quality']:.1%}")
        print(f"  Cost Savings:           {metrics['cost_savings']:.1%}")
        print(f"  Speed Improvement:      {metrics['speed']:.1%}")
        print(f"  Avg Time:               {metrics['avg_time']:.1f} мин")

        # Топ задач
        top_tasks = self.get_top_savings_tasks(limit=5)
        if top_tasks:
            print("\n💰 Топ-5 задач по экономии:")
            for i, task in enumerate(top_tasks, 1):
                task_id, desc, complexity, actual, baseline = task
                if baseline and actual is not None:
                    savings = baseline - actual
                    print(f"  {i}. {task_id[:8]} - {desc[:40]} - ${savings:.4f}")

        print(f"\n📅 Период: последние {days} дней | 📋 Всего задач: {metrics['total_tasks']}")
        print("="*80 + "\n")


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="CLI Dashboard с метриками")
    parser.add_argument('--days', type=int, default=7, help='Период для анализа (дней)')
    parser.add_argument('--goal', choices=['cost', 'speed', 'quality'], help='Приоритетная цель')
    parser.add_argument('--db', type=str, help='Путь к базе данных')

    args = parser.parse_args()

    dashboard = DashboardCLI(db_path=args.db, goal=args.goal)
    dashboard.render_dashboard(days=args.days)


if __name__ == "__main__":
    main()
