#!/usr/bin/env python3
"""
Система мониторинга и алертов для PT_Standart_Agents

Реализует:
- Threshold-based alerts (критичные метрики)
- Trend-based alerts (падение метрик несколько дней подряд)
- Alert delivery (вывод в CLI + запись в log)
"""

import os
import sys
import sqlite3
import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Tuple
import logging

# Добавляем корневую директорию в путь
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.reporting.token_tracker import TokenTracker


class AlertLevel:
    """Уровни алертов"""
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


class Alert:
    """Класс для представления алерта"""
    def __init__(
        self,
        level: str,
        metric: str,
        current_value: float,
        threshold: Optional[float],
        message: str,
        timestamp: Optional[datetime] = None
    ):
        self.level = level
        self.metric = metric
        self.current_value = current_value
        self.threshold = threshold
        self.message = message
        self.timestamp = timestamp or datetime.now()

    def __str__(self) -> str:
        icon = {
            AlertLevel.INFO: "ℹ️",
            AlertLevel.WARNING: "⚠️",
            AlertLevel.CRITICAL: "🚨"
        }.get(self.level, "•")

        ts = self.timestamp.strftime("%H:%M:%S")
        return f"{icon} [{self.level}] {ts} - {self.metric}: {self.message}"

    def to_dict(self) -> Dict:
        return {
            "level": self.level,
            "metric": self.metric,
            "current_value": self.current_value,
            "threshold": self.threshold,
            "message": self.message,
            "timestamp": self.timestamp.isoformat()
        }


class AlertingSystem:
    """
    Система мониторинга метрик и генерации алертов

    Поддерживает:
    - Threshold alerts: метрика вышла за пределы
    - Trend alerts: метрика падает/растёт несколько дней подряд
    - Configurable thresholds
    """

    # Дефолтные пороги для алертов
    DEFAULT_THRESHOLDS = {
        "success_rate": {
            "critical": 0.85,  # < 85% = CRITICAL
            "warning": 0.90    # < 90% = WARNING
        },
        "cost_per_task": {
            "critical": 20.0,  # > $20 = CRITICAL
            "warning": 15.0    # > $15 = WARNING
        },
        "avg_time": {
            "critical": 900,   # > 15 min = CRITICAL
            "warning": 600     # > 10 min = WARNING
        },
        "cost_growth": {
            "critical": 0.20,  # рост > 20% за неделю = CRITICAL
            "warning": 0.10    # рост > 10% за неделю = WARNING
        }
    }

    def __init__(
        self,
        db_path: Optional[str] = None,
        log_path: Optional[str] = None,
        thresholds: Optional[Dict] = None
    ):
        """
        Инициализация системы алертов

        Args:
            db_path: Путь к БД с метриками (по умолчанию token_usage.db)
            log_path: Путь к лог-файлу для алертов
            thresholds: Кастомные пороги (override defaults)
        """
        self.db_path = db_path or os.path.join(PROJECT_ROOT, "data", "token_usage.db")
        self.log_path = log_path or os.path.join(PROJECT_ROOT, "logs", "alerts.log")
        self.thresholds = {**self.DEFAULT_THRESHOLDS, **(thresholds or {})}

        # Создаём директорию для логов если нужно
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)

        # Настройка логирования
        logging.basicConfig(
            filename=self.log_path,
            level=logging.INFO,
            format='%(asctime)s - %(levelname)s - %(message)s'
        )

        self.tracker = TokenTracker(db_path=self.db_path)

    def check_all_alerts(self, days: int = 7) -> List[Alert]:
        """
        Проверка всех алертов за последние N дней

        Returns:
            Список активных алертов
        """
        alerts = []

        # Threshold-based alerts
        alerts.extend(self._check_success_rate())
        alerts.extend(self._check_cost_per_task())
        alerts.extend(self._check_avg_time())

        # Trend-based alerts
        alerts.extend(self._check_success_rate_trend(days=days))
        alerts.extend(self._check_cost_growth(days=days))

        # Сортируем по уровню (CRITICAL первым) и времени
        level_order = {AlertLevel.CRITICAL: 0, AlertLevel.WARNING: 1, AlertLevel.INFO: 2}
        alerts.sort(key=lambda a: (level_order.get(a.level, 3), a.timestamp), reverse=True)

        return alerts

    def _check_success_rate(self) -> List[Alert]:
        """Проверка success rate за последние 24 часа"""
        alerts = []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Считаем success rate за последние 24 часа
        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        cursor.execute("""
            SELECT
                COUNT(*) as total,
                SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful
            FROM tasks
            WHERE started_at >= ?
        """, (yesterday,))

        row = cursor.fetchone()
        conn.close()

        if row and row[0] > 0:  # Если есть задачи
            total, successful = row
            success_rate = successful / total if total > 0 else 1.0

            thresholds = self.thresholds.get("success_rate", {})

            if success_rate < thresholds.get("critical", 0.85):
                alerts.append(Alert(
                    level=AlertLevel.CRITICAL,
                    metric="success_rate",
                    current_value=success_rate,
                    threshold=thresholds.get("critical"),
                    message=f"Success rate критично низкий: {success_rate:.1%} (порог: {thresholds.get('critical'):.1%})"
                ))
            elif success_rate < thresholds.get("warning", 0.90):
                alerts.append(Alert(
                    level=AlertLevel.WARNING,
                    metric="success_rate",
                    current_value=success_rate,
                    threshold=thresholds.get("warning"),
                    message=f"Success rate низкий: {success_rate:.1%} (порог: {thresholds.get('warning'):.1%})"
                ))

        return alerts

    def _check_cost_per_task(self) -> List[Alert]:
        """Проверка средней стоимости за задачу (последние 24 часа)"""
        alerts = []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        cursor.execute("""
            SELECT AVG(
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
            ) as avg_cost
            FROM tasks
            WHERE started_at >= ?
        """, (yesterday,))

        row = cursor.fetchone()
        conn.close()

        if row and row[0] is not None:
            avg_cost = row[0]
            thresholds = self.thresholds.get("cost_per_task", {})

            if avg_cost > thresholds.get("critical", 20.0):
                alerts.append(Alert(
                    level=AlertLevel.CRITICAL,
                    metric="cost_per_task",
                    current_value=avg_cost,
                    threshold=thresholds.get("critical"),
                    message=f"Стоимость задачи критично высокая: ${avg_cost:.2f} (порог: ${thresholds.get('critical'):.2f})"
                ))
            elif avg_cost > thresholds.get("warning", 15.0):
                alerts.append(Alert(
                    level=AlertLevel.WARNING,
                    metric="cost_per_task",
                    current_value=avg_cost,
                    threshold=thresholds.get("warning"),
                    message=f"Стоимость задачи высокая: ${avg_cost:.2f} (порог: ${thresholds.get('warning'):.2f})"
                ))

        return alerts

    def _check_avg_time(self) -> List[Alert]:
        """Проверка среднего времени выполнения (последние 24 часа)"""
        alerts = []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        yesterday = (datetime.now() - timedelta(days=1)).isoformat()
        cursor.execute("""
            SELECT AVG(
                (julianday(finished_at) - julianday(started_at)) * 24 * 60
            ) as avg_minutes
            FROM tasks
            WHERE started_at >= ? AND finished_at IS NOT NULL
        """, (yesterday,))

        row = cursor.fetchone()
        conn.close()

        if row and row[0] is not None:
            avg_minutes = row[0]
            thresholds = self.thresholds.get("avg_time", {})

            if avg_minutes > thresholds.get("critical", 900) / 60:  # 15 мин
                alerts.append(Alert(
                    level=AlertLevel.CRITICAL,
                    metric="avg_time",
                    current_value=avg_minutes,
                    threshold=thresholds.get("critical") / 60,
                    message=f"Среднее время выполнения критично высокое: {avg_minutes:.1f} мин (порог: {thresholds.get('critical')/60:.1f} мин)"
                ))
            elif avg_minutes > thresholds.get("warning", 600) / 60:  # 10 мин
                alerts.append(Alert(
                    level=AlertLevel.WARNING,
                    metric="avg_time",
                    current_value=avg_minutes,
                    threshold=thresholds.get("warning") / 60,
                    message=f"Среднее время выполнения высокое: {avg_minutes:.1f} мин (порог: {thresholds.get('warning')/60:.1f} мин)"
                ))

        return alerts

    def _check_success_rate_trend(self, days: int = 7) -> List[Alert]:
        """Проверка тренда success rate за последние N дней"""
        alerts = []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Получаем success rate по дням
        start_date = (datetime.now() - timedelta(days=days)).date()
        cursor.execute("""
            SELECT
                DATE(started_at) as day,
                CAST(SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*) as success_rate
            FROM tasks
            WHERE DATE(started_at) >= ?
            GROUP BY DATE(started_at)
            ORDER BY DATE(started_at)
        """, (start_date.isoformat(),))

        rows = cursor.fetchall()
        conn.close()

        if len(rows) >= 3:  # Нужно минимум 3 дня для тренда
            rates = [row[1] for row in rows]

            # Проверяем падает ли success rate 3 дня подряд
            declining_days = 0
            for i in range(1, len(rates)):
                if rates[i] < rates[i-1]:
                    declining_days += 1
                else:
                    declining_days = 0

            if declining_days >= 2:  # 3 дня подряд падает
                alerts.append(Alert(
                    level=AlertLevel.WARNING,
                    metric="success_rate_trend",
                    current_value=rates[-1],
                    threshold=None,
                    message=f"Success rate падает {declining_days+1} дней подряд (текущий: {rates[-1]:.1%})"
                ))

        return alerts

    def _check_cost_growth(self, days: int = 7) -> List[Alert]:
        """Проверка роста стоимости за последнюю неделю"""
        alerts = []

        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Средняя стоимость первых 3 дней vs последних 3 дней
        start_date = (datetime.now() - timedelta(days=days)).date()
        mid_date = (datetime.now() - timedelta(days=days//2)).date()

        cursor.execute("""
            SELECT AVG(
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
            ) as avg_cost
            FROM tasks
            WHERE DATE(started_at) >= ? AND DATE(started_at) < ?
        """, (start_date.isoformat(), mid_date.isoformat()))

        early_cost = cursor.fetchone()[0] or 0

        cursor.execute("""
            SELECT AVG(
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
            ) as avg_cost
            FROM tasks
            WHERE DATE(started_at) >= ?
        """, (mid_date.isoformat(),))

        recent_cost = cursor.fetchone()[0] or 0
        conn.close()

        if early_cost > 0:
            growth = (recent_cost - early_cost) / early_cost
            thresholds = self.thresholds.get("cost_growth", {})

            if growth > thresholds.get("critical", 0.20):
                alerts.append(Alert(
                    level=AlertLevel.CRITICAL,
                    metric="cost_growth",
                    current_value=growth,
                    threshold=thresholds.get("critical"),
                    message=f"Стоимость задач выросла на {growth:.1%} за {days} дней (порог: {thresholds.get('critical'):.1%})"
                ))
            elif growth > thresholds.get("warning", 0.10):
                alerts.append(Alert(
                    level=AlertLevel.WARNING,
                    metric="cost_growth",
                    current_value=growth,
                    threshold=thresholds.get("warning"),
                    message=f"Стоимость задач выросла на {growth:.1%} за {days} дней (порог: {thresholds.get('warning'):.1%})"
                ))

        return alerts

    def print_alerts(self, alerts: List[Alert]) -> None:
        """Вывод алертов в CLI"""
        if not alerts:
            print("✅ Все метрики в норме. Алертов нет.")
            return

        print(f"\n{'='*80}")
        print(f"  СИСТЕМА АЛЕРТОВ - Обнаружено {len(alerts)} алерт(ов)")
        print(f"{'='*80}\n")

        for alert in alerts:
            print(alert)
            # Также записываем в лог
            log_level = {
                AlertLevel.INFO: logging.INFO,
                AlertLevel.WARNING: logging.WARNING,
                AlertLevel.CRITICAL: logging.CRITICAL
            }.get(alert.level, logging.INFO)

            logging.log(log_level, alert.message)

        print(f"\n{'='*80}\n")

    def export_alerts_json(self, alerts: List[Alert], output_path: str) -> None:
        """Экспорт алертов в JSON"""
        data = {
            "timestamp": datetime.now().isoformat(),
            "total_alerts": len(alerts),
            "alerts": [alert.to_dict() for alert in alerts]
        }

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        print(f"Алерты экспортированы в {output_path}")


def main():
    """CLI entry point"""
    import argparse

    parser = argparse.ArgumentParser(description="Система мониторинга и алертов")
    parser.add_argument('--check', action='store_true', help='Проверить все алерты')
    parser.add_argument('--days', type=int, default=7, help='Период для трендов (дней)')
    parser.add_argument('--export', type=str, help='Экспортировать алерты в JSON')
    parser.add_argument('--db', type=str, help='Путь к базе данных')

    args = parser.parse_args()

    system = AlertingSystem(db_path=args.db)

    if args.check or not any([args.export]):
        alerts = system.check_all_alerts(days=args.days)
        system.print_alerts(alerts)

        if args.export:
            system.export_alerts_json(alerts, args.export)


if __name__ == "__main__":
    main()
