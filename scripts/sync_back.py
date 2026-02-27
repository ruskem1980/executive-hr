#!/usr/bin/env python3
"""
sync_back.py — Обратная синхронизация инструментов в PT_Standart.

Когда в интегрированном проекте создаётся новый Python-инструмент
для повышения эффективности, этот скрипт отправляет его обратно
в репозиторий PT_Standart.

Все комментарии на русском.

Использование:
    # Синхронизировать конкретный файл
    python3 scripts/sync_back.py --file src/reporting/new_tool.py

    # Синхронизировать все новые/изменённые инструменты
    python3 scripts/sync_back.py --auto

    # Проверить что изменилось (dry run)
    python3 scripts/sync_back.py --dry-run

    # Указать другой remote для PT_Standart
    python3 scripts/sync_back.py --auto --remote https://github.com/ruskem1980/PT_Standart.git
"""

import subprocess
import sys
import os
import json
import shutil
import tempfile
from pathlib import Path
from datetime import datetime, timezone
from typing import List, Optional, Tuple

# Репозиторий-источник (PT_Standart)
DEFAULT_UPSTREAM = "https://github.com/ruskem1980/PT_Standart.git"

# Директории, которые синхронизируются обратно
SYNC_DIRS = [
    "src/reporting/",       # Инструменты отчётности
    "src/preprocessing/",   # Инструменты предобработки
    "scripts/",             # Утилиты
    ".claude/helpers/",     # Хелперы координации
]

# Файлы, которые НИКОГДА не синхронизируются обратно
EXCLUDE_PATTERNS = [
    "__pycache__",
    ".pyc",
    ".DS_Store",
    "memory.db",
    "token_usage.db",
    ".env",
    "credentials",
    "secrets",
    "node_modules",
]

# Расширения инструментов для автоопределения
TOOL_EXTENSIONS = {".py", ".sh", ".js", ".mjs", ".cjs"}


def run(cmd: str, cwd: Optional[str] = None) -> Tuple[int, str]:
    """Выполнить команду, вернуть (код, вывод)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True, cwd=cwd
    )
    return result.returncode, (result.stdout + result.stderr).strip()


def is_excluded(path: str) -> bool:
    """Проверить, исключён ли файл из синхронизации."""
    for pattern in EXCLUDE_PATTERNS:
        if pattern in path:
            return True
    return False


def is_tool_file(path: str) -> bool:
    """Проверить, является ли файл инструментом."""
    ext = Path(path).suffix
    return ext in TOOL_EXTENSIONS


def get_project_root() -> Path:
    """Найти корень текущего проекта."""
    code, root = run("git rev-parse --show-toplevel")
    if code != 0:
        return Path.cwd()
    return Path(root.strip())


def find_changed_tools(project_root: Path) -> List[str]:
    """Найти новые/изменённые инструменты в директориях синхронизации."""
    changed = []

    for sync_dir in SYNC_DIRS:
        full_dir = project_root / sync_dir
        if not full_dir.exists():
            continue

        # Находим все файлы-инструменты
        for filepath in full_dir.rglob("*"):
            if not filepath.is_file():
                continue
            rel = str(filepath.relative_to(project_root))
            if is_excluded(rel):
                continue
            if not is_tool_file(rel):
                continue
            changed.append(rel)

    return changed


def get_git_diff_files(project_root: Path) -> List[str]:
    """Получить файлы, изменённые с последнего коммита."""
    code, output = run("git diff --name-only HEAD", cwd=str(project_root))
    if code != 0:
        return []

    # Также новые untracked файлы
    code2, untracked = run(
        "git ls-files --others --exclude-standard", cwd=str(project_root)
    )

    all_files = set()
    for line in (output + "\n" + untracked).strip().split("\n"):
        line = line.strip()
        if line:
            all_files.add(line)

    return [f for f in all_files if not is_excluded(f) and is_tool_file(f)]


def sync_to_upstream(
    files: List[str],
    project_root: Path,
    upstream_url: str,
    dry_run: bool = False,
    branch: str = "contrib/auto-sync",
) -> bool:
    """Синхронизировать файлы обратно в PT_Standart."""

    if not files:
        print("Нет файлов для синхронизации.")
        return True

    print(f"\nФайлы для синхронизации в PT_Standart ({len(files)}):")
    for f in files:
        print(f"  + {f}")

    if dry_run:
        print("\n[DRY RUN] Файлы НЕ отправлены.")
        return True

    # Клонируем PT_Standart во временную папку
    tmp_dir = tempfile.mkdtemp(prefix="pt_sync_")
    try:
        print(f"\nКлонирую PT_Standart...")
        code, out = run(f"git clone --depth 5 {upstream_url} {tmp_dir}/repo")
        if code != 0:
            print(f"Ошибка клонирования: {out}")
            return False

        repo_dir = Path(tmp_dir) / "repo"

        # Создаём ветку
        run(f"git checkout -b {branch}", cwd=str(repo_dir))

        # Копируем файлы
        copied = 0
        for rel_path in files:
            src_file = project_root / rel_path
            dst_file = repo_dir / rel_path

            if not src_file.exists():
                print(f"  Пропускаю {rel_path} — файл не найден")
                continue

            # Создаём директорию если нет
            dst_file.parent.mkdir(parents=True, exist_ok=True)

            # Копируем
            shutil.copy2(str(src_file), str(dst_file))
            copied += 1
            print(f"  Скопирован: {rel_path}")

        if copied == 0:
            print("Нет файлов для коммита.")
            return True

        # Определяем имя текущего проекта
        current_project = project_root.name

        # Коммитим
        run("git add -A", cwd=str(repo_dir))
        timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M")
        commit_msg = (
            f"feat(sync): инструменты из {current_project} ({copied} файлов)\n\n"
            f"Автоматическая синхронизация из проекта {current_project}\n"
            f"Дата: {timestamp}\n"
            f"Файлы:\n"
            + "\n".join(f"  - {f}" for f in files[:20])
        )

        code, out = run(
            f'git commit -m "{commit_msg}"',
            cwd=str(repo_dir),
        )
        if code != 0 and "nothing to commit" in out:
            print("Нет изменений для коммита — файлы идентичны.")
            return True

        # Пушим
        print(f"\nПушу в ветку {branch}...")
        code, out = run(f"git push origin {branch} --force", cwd=str(repo_dir))
        if code != 0:
            print(f"Ошибка пуша: {out}")
            print("\nПопробуйте:")
            print(f"  1. Проверить доступ к {upstream_url}")
            print(f"  2. Настроить SSH ключ или токен")
            return False

        print(f"\nУспешно запушено в {branch}!")
        print(f"Создайте PR: {upstream_url.replace('.git', '')}/compare/{branch}")
        return True

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def sync_specific_file(
    filepath: str,
    project_root: Path,
    upstream_url: str,
    dry_run: bool = False,
) -> bool:
    """Синхронизировать один конкретный файл."""
    full_path = project_root / filepath
    if not full_path.exists():
        print(f"Файл не найден: {filepath}")
        return False

    if is_excluded(filepath):
        print(f"Файл исключён из синхронизации: {filepath}")
        return False

    return sync_to_upstream([filepath], project_root, upstream_url, dry_run)


def main():
    """Главная функция CLI."""
    import argparse

    parser = argparse.ArgumentParser(
        description="Обратная синхронизация инструментов в PT_Standart",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  python3 scripts/sync_back.py --dry-run          # Показать что синхронизируется
  python3 scripts/sync_back.py --auto              # Синхронизировать все изменённые инструменты
  python3 scripts/sync_back.py --file src/new.py   # Синхронизировать один файл
        """,
    )

    parser.add_argument(
        "--file", type=str, help="Конкретный файл для синхронизации"
    )
    parser.add_argument(
        "--auto",
        action="store_true",
        help="Автоматически найти и синхронизировать все изменённые инструменты",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Только показать что будет синхронизировано (без пуша)",
    )
    parser.add_argument(
        "--remote",
        type=str,
        default=DEFAULT_UPSTREAM,
        help=f"URL репозитория PT_Standart (по умолчанию: {DEFAULT_UPSTREAM})",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Синхронизировать ВСЕ инструменты (не только изменённые)",
    )

    args = parser.parse_args()
    project_root = get_project_root()

    print("═══════════════════════════════════════════════════")
    print("  Обратная синхронизация → PT_Standart")
    print(f"  Проект: {project_root.name}")
    print(f"  Upstream: {args.remote}")
    print("═══════════════════════════════════════════════════")

    if args.file:
        success = sync_specific_file(
            args.file, project_root, args.remote, args.dry_run
        )
    elif args.auto:
        # Только изменённые файлы
        files = get_git_diff_files(project_root)
        # Фильтруем по директориям синхронизации
        sync_files = [
            f for f in files if any(f.startswith(d) for d in SYNC_DIRS)
        ]
        success = sync_to_upstream(
            sync_files, project_root, args.remote, args.dry_run
        )
    elif args.all:
        # Все инструменты
        files = find_changed_tools(project_root)
        success = sync_to_upstream(
            files, project_root, args.remote, args.dry_run
        )
    elif args.dry_run:
        # Dry run показывает всё
        files = find_changed_tools(project_root)
        sync_to_upstream(files, project_root, args.remote, dry_run=True)
        success = True
    else:
        parser.print_help()
        success = True

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
