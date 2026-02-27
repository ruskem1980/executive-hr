#!/usr/bin/env python3
"""
git_auto_save.py - Автоматический коммит и пуш в GitHub.

Генерирует осмысленные commit-сообщения БЕЗ LLM,
анализируя git diff (типы файлов, директории, статистику изменений).

Использование:
    python3 scripts/git_auto_save.py                    # коммит + пуш всех изменений
    python3 scripts/git_auto_save.py --file path/to/f   # коммит конкретного файла
    python3 scripts/git_auto_save.py --check             # проверить есть ли изменения
    python3 scripts/git_auto_save.py --no-push           # коммит без пуша
"""

import subprocess
import sys
import os
from pathlib import Path
from datetime import datetime, timezone
from collections import defaultdict
from typing import Optional


# Маппинг директорий -> семантические префиксы
DIR_PREFIXES = {
    "src/": "feat",
    "tests/": "test",
    "docs/": "docs",
    "config/": "config",
    "scripts/": "chore",
    ".claude/": "infra",
    ".github/": "ci",
    "examples/": "docs",
}

# Маппинг расширений -> типы файлов
EXT_LABELS = {
    ".py": "Python",
    ".js": "JavaScript",
    ".mjs": "JavaScript",
    ".cjs": "JavaScript",
    ".ts": "TypeScript",
    ".sh": "shell",
    ".json": "config",
    ".yaml": "config",
    ".yml": "config",
    ".md": "docs",
    ".toml": "config",
    ".cfg": "config",
    ".sql": "SQL",
    ".html": "HTML",
    ".css": "CSS",
}

# Ключевые слова в путях -> подсказки
PATH_HINTS = {
    "test": "tests",
    "spec": "tests",
    "fix": "fix",
    "bug": "fix",
    "auth": "auth",
    "security": "security",
    "hook": "hooks",
    "report": "reporting",
    "token": "tokens",
    "agent": "agents",
    "monitor": "monitoring",
    "track": "tracking",
    "config": "config",
    "migration": "migration",
    "perf": "performance",
}


def run_git(*args: str, check: bool = True) -> subprocess.CompletedProcess:
    """Запуск git команды."""
    result = subprocess.run(
        ["git"] + list(args),
        capture_output=True,
        text=True,
        cwd=os.environ.get("PROJECT_DIR", "."),
    )
    if check and result.returncode != 0:
        raise RuntimeError(f"git {' '.join(args)} failed: {result.stderr.strip()}")
    return result


def has_changes() -> bool:
    """Есть ли незакоммиченные изменения."""
    r1 = run_git("diff", "--quiet", "HEAD", check=False)
    r2 = run_git("diff", "--cached", "--quiet", check=False)
    r3 = run_git("ls-files", "--others", "--exclude-standard", check=False)
    return r1.returncode != 0 or r2.returncode != 0 or bool(r3.stdout.strip())


def get_changed_files() -> list[dict]:
    """Список изменённых файлов с метаданными."""
    files = []

    # Staged
    result = run_git("diff", "--cached", "--name-status", check=False)
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            files.append({"status": parts[0][0], "path": parts[1]})

    # Unstaged
    result = run_git("diff", "--name-status", check=False)
    for line in result.stdout.strip().splitlines():
        if not line.strip():
            continue
        parts = line.split("\t", 1)
        if len(parts) == 2:
            path = parts[1]
            if not any(f["path"] == path for f in files):
                files.append({"status": parts[0][0], "path": path})

    # Untracked
    result = run_git("ls-files", "--others", "--exclude-standard", check=False)
    for line in result.stdout.strip().splitlines():
        if line.strip():
            if not any(f["path"] == line.strip() for f in files):
                files.append({"status": "A", "path": line.strip()})

    return files


def get_diff_stats() -> dict:
    """Статистика diff: добавлено/удалено строк."""
    result = run_git("diff", "--stat", "--cached", check=False)
    stats_staged = result.stdout.strip()
    result = run_git("diff", "--stat", check=False)
    stats_unstaged = result.stdout.strip()

    # Парсим итоговую строку типа "3 files changed, 45 insertions(+), 12 deletions(-)"
    insertions = 0
    deletions = 0
    for stats in [stats_staged, stats_unstaged]:
        for line in stats.splitlines():
            if "insertion" in line or "deletion" in line:
                parts = line.split(",")
                for part in parts:
                    part = part.strip()
                    if "insertion" in part:
                        insertions += int(part.split()[0])
                    elif "deletion" in part:
                        deletions += int(part.split()[0])

    return {"insertions": insertions, "deletions": deletions}


def detect_prefix(files: list[dict]) -> str:
    """Определяет семантический префикс по типу изменений."""
    paths = [f["path"] for f in files]

    # По директориям
    prefix_counts = defaultdict(int)
    for path in paths:
        for dir_prefix, prefix in DIR_PREFIXES.items():
            if path.startswith(dir_prefix):
                prefix_counts[prefix] += 1
                break
        else:
            prefix_counts["chore"] += 1

    # По ключевым словам в путях
    hint_counts = defaultdict(int)
    for path in paths:
        path_lower = path.lower()
        for keyword, hint in PATH_HINTS.items():
            if keyword in path_lower:
                hint_counts[hint] += 1

    # Приоритет: test > fix > feat > docs > config > chore
    if prefix_counts.get("test", 0) > len(files) * 0.5:
        return "test"
    if hint_counts.get("fix", 0) > 0:
        return "fix"
    if prefix_counts.get("feat", 0) > 0:
        return "feat"
    if prefix_counts.get("docs", 0) > len(files) * 0.5:
        return "docs"
    if prefix_counts.get("config", 0) > len(files) * 0.5:
        return "config"
    if prefix_counts.get("ci", 0) > 0:
        return "ci"
    if prefix_counts.get("infra", 0) > 0:
        return "infra"

    # Самый частый
    return max(prefix_counts, key=prefix_counts.get, default="chore")


def detect_scope(files: list[dict]) -> str:
    """Определяет scope (область) изменений."""
    paths = [f["path"] for f in files]

    # Общая директория
    dirs = set()
    for path in paths:
        parts = Path(path).parts
        if len(parts) > 1:
            dirs.add(parts[1] if parts[0] in ("src", "tests", ".claude") else parts[0])
        else:
            dirs.add(Path(path).stem)

    if len(dirs) == 1:
        return dirs.pop()
    if len(dirs) <= 3:
        return ",".join(sorted(dirs))

    # Слишком много — обобщаем
    top_dirs = set()
    for path in paths:
        parts = Path(path).parts
        if parts:
            top_dirs.add(parts[0])

    if len(top_dirs) == 1:
        return top_dirs.pop()
    return "multiple"


def generate_description(files: list[dict], stats: dict) -> str:
    """Генерирует описание изменений."""
    status_map = {"A": "add", "M": "update", "D": "delete", "R": "rename"}
    actions = defaultdict(list)

    for f in files:
        action = status_map.get(f["status"], "change")
        name = Path(f["path"]).name
        actions[action].append(name)

    parts = []
    for action in ["add", "update", "delete", "rename", "change"]:
        names = actions.get(action, [])
        if not names:
            continue
        if len(names) <= 3:
            parts.append(f"{action} {', '.join(names)}")
        else:
            parts.append(f"{action} {len(names)} files")

    description = "; ".join(parts) if parts else "update files"

    # Усечение до 72 символов (стандарт git)
    if len(description) > 68:
        description = description[:65] + "..."

    return description


def generate_commit_message(
    files: list[dict],
    stats: dict,
    specific_file: Optional[str] = None,
) -> str:
    """Генерирует commit-сообщение без LLM."""
    if specific_file:
        # Для одного файла — короткое сообщение
        name = Path(specific_file).name
        action = "add" if any(
            f["path"] == specific_file and f["status"] == "A" for f in files
        ) else "update"
        prefix = detect_prefix([{"path": specific_file, "status": "M"}])
        return f"{prefix}: {action} {name}"

    prefix = detect_prefix(files)
    scope = detect_scope(files)
    description = generate_description(files, stats)

    # Conventional commits: type(scope): description
    subject = f"{prefix}({scope}): {description}"

    # Усечение subject до 72 символов
    if len(subject) > 72:
        subject = subject[:69] + "..."

    # Body
    branch = run_git("branch", "--show-current", check=False).stdout.strip()
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")

    body_lines = [
        "",
        f"Files: {len(files)} | +{stats['insertions']} -{stats['deletions']}",
        f"Branch: {branch} | {timestamp}",
        "",
        "Auto-save by Claude Code",
    ]

    return subject + "\n".join(body_lines)


def auto_save(
    specific_file: Optional[str] = None,
    push: bool = True,
) -> bool:
    """Основная процедура: stage + commit + push."""
    if not has_changes():
        print("[auto-save] Нет изменений для коммита")
        return True

    files = get_changed_files()
    if not files:
        print("[auto-save] Нет изменений для коммита")
        return True

    stats = get_diff_stats()

    # Stage
    if specific_file:
        run_git("add", specific_file)
        print(f"[auto-save] Staged: {specific_file}")
    else:
        # Stage все, кроме чувствительных файлов
        sensitive = {".env", "credentials.json", ".secrets", "id_rsa"}
        for f in files:
            name = Path(f["path"]).name
            if name in sensitive or name.startswith(".env"):
                print(f"[auto-save] SKIP sensitive: {f['path']}")
                continue
            run_git("add", f["path"], check=False)
        print(f"[auto-save] Staged {len(files)} файлов (+{stats['insertions']} -{stats['deletions']})")

    # Генерируем сообщение
    message = generate_commit_message(files, stats, specific_file)

    # Commit
    result = run_git("commit", "-m", message, check=False)
    if result.returncode != 0:
        combined = result.stdout + result.stderr
        no_commit_phrases = [
            "nothing to commit",
            "nothing added to commit",
            "no changes added to commit",
            "working tree clean",
        ]
        if any(p in combined for p in no_commit_phrases):
            print("[auto-save] Нечего коммитить (уже закоммичено)")
            return True
        # Показываем только реальные git ошибки, фильтруя вывод pre-commit хуков
        git_error_lines = [
            l for l in combined.splitlines()
            if any(kw in l.lower() for kw in ["error:", "fatal:", "rejected"])
            and not l.startswith("\x1b")
        ]
        error_msg = "\n".join(git_error_lines) if git_error_lines else combined.strip()[:300]
        print(f"[auto-save] Ошибка коммита: {error_msg}")
        return False

    short_msg = message.split("\n")[0]
    print(f"[auto-save] Commit: {short_msg}")

    # Push
    if push:
        branch = run_git("branch", "--show-current", check=False).stdout.strip()
        result = run_git("push", "origin", branch, check=False)
        if result.returncode == 0:
            print(f"[auto-save] Push -> origin/{branch}")
        else:
            print(f"[auto-save] Push не удался: {result.stderr.strip()}")
            # Не критично — можно пушнуть позже
            return True

    return True


def main():
    """CLI entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Auto-save to GitHub (no LLM)")
    parser.add_argument("--file", type=str, help="Конкретный файл для коммита")
    parser.add_argument("--check", action="store_true", help="Только проверить наличие изменений")
    parser.add_argument("--no-push", action="store_true", help="Коммит без пуша")
    args = parser.parse_args()

    if args.check:
        if has_changes():
            files = get_changed_files()
            print(f"Есть изменения: {len(files)} файлов")
            sys.exit(0)
        else:
            print("Нет изменений")
            sys.exit(1)

    success = auto_save(
        specific_file=args.file,
        push=not args.no_push,
    )
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
