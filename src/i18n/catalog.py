#!/usr/bin/env python3
"""
Catalog - управление каталогами переводов.

Хранит переводы в JSON-файлах: locales/{locale}.json
Формат: {"original_string": "translated_string", ...}

Поддерживает:
- Загрузка/сохранение каталогов
- Merge новых строк с существующими
- Статистика покрытия переводами
- Экспорт/импорт для внешних переводчиков
"""

import json
import shutil
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Set
from dataclasses import dataclass, asdict


@dataclass
class TranslationEntry:
    """Запись перевода."""
    original: str
    translated: str
    category: str = ""
    source_file: str = ""
    source_line: int = 0
    status: str = "pending"     # pending | translated | reviewed | approved
    translator: str = ""        # llm | human | auto
    updated_at: str = ""
    context: str = ""
    has_placeholders: bool = False


class TranslationCatalog:
    """
    Управление каталогом переводов для одной или нескольких локалей.

    Структура файлов:
        locales/
            ru.json    - Русский каталог
            en.json    - Английский каталог
            _meta.json - Метаданные (даты, версии)
    """

    def __init__(self, locales_dir: Path):
        self.locales_dir = Path(locales_dir)
        self.locales_dir.mkdir(parents=True, exist_ok=True)

    def load(self, locale: str) -> Dict[str, str]:
        """
        Загружает каталог переводов для локали.

        Args:
            locale: Код языка (ru, en, de, etc.)

        Returns:
            Dict[original, translated]
        """
        catalog_path = self.locales_dir / f"{locale}.json"
        if not catalog_path.exists():
            return {}

        with open(catalog_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Поддерживаем оба формата: простой {"key": "value"} и расширенный
        if data and isinstance(next(iter(data.values()), None), dict):
            # Расширенный формат: {"key": {"translated": "...", "status": "..."}}
            return {k: v.get("translated", k) for k, v in data.items()
                    if v.get("translated")}
        return data

    def load_full(self, locale: str) -> Dict[str, TranslationEntry]:
        """
        Загружает полный каталог с метаданными.

        Returns:
            Dict[original, TranslationEntry]
        """
        catalog_path = self.locales_dir / f"{locale}.json"
        if not catalog_path.exists():
            return {}

        with open(catalog_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        entries = {}
        for key, value in data.items():
            if isinstance(value, dict):
                entries[key] = TranslationEntry(
                    original=key,
                    translated=value.get("translated", ""),
                    category=value.get("category", ""),
                    source_file=value.get("source_file", ""),
                    source_line=value.get("source_line", 0),
                    status=value.get("status", "pending"),
                    translator=value.get("translator", ""),
                    updated_at=value.get("updated_at", ""),
                    context=value.get("context", ""),
                    has_placeholders=value.get("has_placeholders", False),
                )
            else:
                entries[key] = TranslationEntry(
                    original=key,
                    translated=value,
                    status="translated" if value else "pending"
                )

        return entries

    def save(self, locale: str, entries: Dict[str, TranslationEntry]):
        """
        Сохраняет каталог переводов.

        Args:
            locale: Код языка
            entries: Словарь записей
        """
        # Бэкап
        catalog_path = self.locales_dir / f"{locale}.json"
        if catalog_path.exists():
            backup_path = self.locales_dir / f"{locale}.backup.json"
            shutil.copy2(catalog_path, backup_path)

        # Сохраняем в расширенном формате
        data = {}
        for key, entry in sorted(entries.items()):
            data[key] = {
                "translated": entry.translated,
                "category": entry.category,
                "source_file": entry.source_file,
                "source_line": entry.source_line,
                "status": entry.status,
                "translator": entry.translator,
                "updated_at": entry.updated_at or datetime.now().isoformat(),
                "context": entry.context,
                "has_placeholders": entry.has_placeholders,
            }

        with open(catalog_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Обновляем метаданные
        self._update_meta(locale, len(entries))

    def merge_scanned_strings(self, locale: str,
                               scanned: List[dict]) -> Tuple[int, int, int]:
        """
        Мержит отсканированные строки с существующим каталогом.

        Args:
            locale: Код языка
            scanned: Список словарей из scanner.ExtractedString

        Returns:
            (new_count, existing_count, removed_count)
        """
        existing = self.load_full(locale)
        new_count = 0
        existing_count = 0

        scanned_keys: Set[str] = set()

        for item in scanned:
            text = item.get("text", "")
            scanned_keys.add(text)

            if text in existing:
                # Обновляем метаданные, сохраняем перевод
                entry = existing[text]
                entry.source_file = item.get("file", entry.source_file)
                entry.source_line = item.get("line", entry.source_line)
                entry.category = item.get("category", entry.category)
                entry.context = item.get("context", entry.context)
                entry.has_placeholders = item.get("has_placeholders", False)
                existing_count += 1
            else:
                # Новая строка - добавляем
                existing[text] = TranslationEntry(
                    original=text,
                    translated="",
                    category=item.get("category", ""),
                    source_file=item.get("file", ""),
                    source_line=item.get("line", 0),
                    status="pending",
                    context=item.get("context", ""),
                    has_placeholders=item.get("has_placeholders", False),
                )
                new_count += 1

        # Помечаем удалённые строки (больше нет в коде)
        removed_count = 0
        for key in list(existing.keys()):
            if key not in scanned_keys:
                existing[key].status = "orphaned"
                removed_count += 1

        self.save(locale, existing)
        return new_count, existing_count, removed_count

    def get_untranslated(self, locale: str) -> List[TranslationEntry]:
        """Возвращает строки без перевода."""
        entries = self.load_full(locale)
        return [e for e in entries.values()
                if not e.translated or e.status == "pending"]

    def get_stats(self, locale: str) -> Dict:
        """
        Возвращает статистику покрытия переводами.

        Returns:
            Dict со статистикой по категориям и статусам
        """
        entries = self.load_full(locale)
        if not entries:
            return {"total": 0, "translated": 0, "pending": 0, "coverage": 0.0}

        total = len(entries)
        by_status = {}
        by_category = {}

        for entry in entries.values():
            by_status[entry.status] = by_status.get(entry.status, 0) + 1
            cat = entry.category or "unknown"
            if cat not in by_category:
                by_category[cat] = {"total": 0, "translated": 0}
            by_category[cat]["total"] += 1
            if entry.translated:
                by_category[cat]["translated"] += 1

        translated = sum(1 for e in entries.values() if e.translated)

        return {
            "total": total,
            "translated": translated,
            "pending": total - translated,
            "coverage": round(translated / total * 100, 1) if total else 0.0,
            "by_status": by_status,
            "by_category": {
                cat: {
                    **data,
                    "coverage": round(data["translated"] / data["total"] * 100, 1)
                    if data["total"] else 0.0
                }
                for cat, data in by_category.items()
            },
        }

    def export_for_translation(self, locale: str, output_path: Path,
                                only_pending: bool = True):
        """
        Экспортирует строки для внешнего переводчика.

        Формат: простой JSON {"original": "translated"} для удобства.
        """
        entries = self.load_full(locale)
        export_data = {}

        for key, entry in entries.items():
            if only_pending and entry.translated:
                continue
            export_data[key] = {
                "translation": entry.translated or "",
                "category": entry.category,
                "context": entry.context,
                "file": entry.source_file,
            }

        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(export_data, f, ensure_ascii=False, indent=2)

        print(f"  Экспортировано {len(export_data)} строк для перевода -> {output_path}")

    def import_translations(self, locale: str, import_path: Path) -> int:
        """
        Импортирует переводы из внешнего файла.

        Returns:
            Количество импортированных переводов
        """
        with open(import_path, "r", encoding="utf-8") as f:
            imported = json.load(f)

        entries = self.load_full(locale)
        count = 0

        for key, value in imported.items():
            if key in entries:
                if isinstance(value, dict):
                    translation = value.get("translation", "")
                else:
                    translation = value

                if translation:
                    entries[key].translated = translation
                    entries[key].status = "translated"
                    entries[key].translator = "imported"
                    entries[key].updated_at = datetime.now().isoformat()
                    count += 1

        self.save(locale, entries)
        return count

    def list_locales(self) -> List[str]:
        """Возвращает список доступных локалей."""
        locales = []
        for path in self.locales_dir.glob("*.json"):
            name = path.stem
            if not name.startswith("_") and name != "extracted_strings":
                locales.append(name)
        return sorted(locales)

    def _update_meta(self, locale: str, count: int):
        """Обновляет метаданные."""
        meta_path = self.locales_dir / "_meta.json"
        meta = {}
        if meta_path.exists():
            with open(meta_path, "r", encoding="utf-8") as f:
                meta = json.load(f)

        meta[locale] = {
            "entries": count,
            "updated_at": datetime.now().isoformat(),
        }

        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)
