#!/usr/bin/env python3
"""
Scanner - извлекает переводимые строки из исходного кода проекта.

Использует Python AST для анализа .py файлов и regex для .yaml/.json.
НЕ использует LLM - чисто алгоритмическая обработка.

Стратегия извлечения:
1. print() / logging.xxx() вызовы - пользовательские сообщения
2. f-строки с текстовым контентом
3. Enum значения с текстовыми метками
4. Строковые литералы в argparse (help, description)
5. Строки-шаблоны для отчётов (summary, recommendations)
6. YAML-конфиги: комментарии и текстовые значения
"""

import ast
import re
import json
import hashlib
from pathlib import Path
from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field, asdict
from enum import Enum


class StringCategory(Enum):
    """Категории извлечённых строк."""
    UI_MESSAGE = "ui_message"           # print(), user-facing
    LOG_MESSAGE = "log_message"         # logging.xxx()
    ERROR_MESSAGE = "error_message"     # raise, error strings
    ENUM_VALUE = "enum_value"           # Enum member values
    CLI_HELP = "cli_help"              # argparse help/description
    REPORT_TEMPLATE = "report_template" # summary, recommendations
    CONFIG_LABEL = "config_label"       # YAML/JSON labels
    DOCSTRING = "docstring"             # Module/class/function docstrings
    COMMENT = "comment"                 # Inline comments (Russian)
    KEYWORD = "keyword"                 # Classification keywords
    STATUS_TEXT = "status_text"         # Status indicators with text


@dataclass
class ExtractedString:
    """Извлечённая переводимая строка."""
    text: str
    category: str
    file: str
    line: int
    context: str = ""          # Окружающий код для контекста
    string_id: str = ""        # Уникальный хеш-ID
    has_placeholders: bool = False  # Содержит {}, %s и т.д.
    language_detected: str = ""     # 'ru', 'en', 'mixed', 'unknown'

    def __post_init__(self):
        if not self.string_id:
            raw = f"{self.file}:{self.line}:{self.text}"
            self.string_id = hashlib.md5(raw.encode()).hexdigest()[:12]
        if not self.language_detected:
            self.language_detected = detect_language(self.text)


def detect_language(text: str) -> str:
    """
    Определяет язык строки (ru/en/mixed/unknown).
    Без LLM - по наличию кириллицы/латиницы.
    """
    has_cyrillic = bool(re.search(r'[а-яА-ЯёЁ]', text))
    has_latin = bool(re.search(r'[a-zA-Z]', text))

    if has_cyrillic and has_latin:
        return "mixed"
    elif has_cyrillic:
        return "ru"
    elif has_latin:
        return "en"
    return "unknown"


def has_translatable_content(text: str) -> bool:
    """
    Проверяет, содержит ли строка переводимый текст.
    Фильтрует технические строки (пути, URL, regex, format-specifiers).
    """
    stripped = text.strip()

    # Слишком короткие
    if len(stripped) < 2:
        return False

    # Чисто технические паттерны - НЕ переводить
    skip_patterns = [
        r'^[\s\-=\*_\#\|]+$',           # Только спецсимволы (разделители)
        r'^[/\\][\w/\\.]+$',             # Пути к файлам
        r'^https?://',                    # URL
        r'^\w+\.\w+\.\w+',              # Dotted identifiers (a.b.c)
        r'^%[\(\w\)]*[sdif]',            # printf-style format only
        r'^\{[\w\.:!]*\}$',             # Только placeholder {name}
        r'^[\d\.\,\s\%\$]+$',           # Только цифры
        r'^[A-Z_]+$',                    # CONSTANT_NAMES
        r'^[\w\-]+\.(?:py|js|yaml|json|md|sh|log)$',  # Имена файлов
        r'^(?:src|tests|config|docs)/',  # Пути в проекте
        r'^--[\w\-]+=?',                 # CLI флаги
        r'^\w+://\w+',                   # Протоколы
        r'^[{}\[\]()]+$',               # Только скобки
        r'^\.+$',                        # Только точки
        r'^utf-?\d+$',                   # Кодировки
        r'^\d+\.\d+\.\d+',              # Версии
        r'^[A-Z][a-z]+(?:[A-Z][a-z]+)+$',  # CamelCase идентификаторы
    ]

    for pattern in skip_patterns:
        if re.match(pattern, stripped):
            return False

    # Должна содержать хотя бы одну букву (кириллица или латиница)
    if not re.search(r'[a-zA-Zа-яА-ЯёЁ]', stripped):
        return False

    # Должна содержать осмысленный текст (минимум 2 буквы подряд)
    if not re.search(r'[a-zA-Zа-яА-ЯёЁ]{2,}', stripped):
        return False

    return True


class PythonStringExtractor(ast.NodeVisitor):
    """AST-визитор для извлечения переводимых строк из Python кода."""

    def __init__(self, file_path: str, source_lines: List[str]):
        self.file_path = file_path
        self.source_lines = source_lines
        self.strings: List[ExtractedString] = []
        self._current_class = ""
        self._current_func = ""
        self._in_enum = False

    def visit_ClassDef(self, node: ast.ClassDef):
        """Отслеживает классы, особенно Enum."""
        old_class = self._current_class
        self._current_class = node.name

        # Определяем, является ли это Enum
        old_in_enum = self._in_enum
        for base in node.bases:
            if isinstance(base, ast.Name) and base.id == "Enum":
                self._in_enum = True
            elif isinstance(base, ast.Attribute) and base.attr == "Enum":
                self._in_enum = True

        self.generic_visit(node)
        self._current_class = old_class
        self._in_enum = old_in_enum

    def visit_FunctionDef(self, node: ast.FunctionDef):
        """Отслеживает функции и извлекает docstrings."""
        old_func = self._current_func
        self._current_func = node.name

        # Docstring
        if (node.body and isinstance(node.body[0], ast.Expr) and
                isinstance(node.body[0].value, (ast.Constant, ast.Constant))):
            docstring = self._get_str_value(node.body[0].value)
            if docstring and has_translatable_content(docstring):
                self._add_string(
                    docstring, StringCategory.DOCSTRING,
                    node.body[0].lineno,
                    context=f"def {node.name}()"
                )

        self.generic_visit(node)
        self._current_func = old_func

    visit_AsyncFunctionDef = visit_FunctionDef

    def visit_Assign(self, node: ast.Assign):
        """Извлекает строки из присваиваний (Enum members, constants)."""
        if self._in_enum:
            for target in node.targets:
                if isinstance(target, ast.Name) and isinstance(node.value, (ast.Constant, ast.Constant)):
                    val = self._get_str_value(node.value)
                    if val and has_translatable_content(val):
                        self._add_string(
                            val, StringCategory.ENUM_VALUE,
                            node.lineno,
                            context=f"{self._current_class}.{target.id}"
                        )
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call):
        """Извлекает строки из вызовов функций."""
        func_name = self._get_call_name(node)

        if func_name == "print":
            self._extract_call_strings(node, StringCategory.UI_MESSAGE)
        elif func_name in ("logger.info", "logger.warning", "logger.error",
                            "logger.debug", "logger.critical",
                            "logging.info", "logging.warning", "logging.error"):
            self._extract_call_strings(node, StringCategory.LOG_MESSAGE)
        elif func_name in ("parser.add_argument",):
            self._extract_argparse_strings(node)
        elif func_name in ("raise", "Exception", "ValueError",
                            "TypeError", "RuntimeError", "ImportError"):
            self._extract_call_strings(node, StringCategory.ERROR_MESSAGE)

        self.generic_visit(node)

    def visit_Raise(self, node: ast.Raise):
        """Извлекает строки из raise."""
        if node.exc and isinstance(node.exc, ast.Call):
            self._extract_call_strings(node.exc, StringCategory.ERROR_MESSAGE)
        self.generic_visit(node)

    def visit_JoinedStr(self, node: ast.JoinedStr):
        """Извлекает шаблоны f-строк."""
        # Собираем текстовые части f-строки
        text_parts = []
        has_expr = False
        for value in node.values:
            if isinstance(value, (ast.Constant, ast.Constant)):
                text_parts.append(self._get_str_value(value))
            elif isinstance(value, ast.FormattedValue):
                text_parts.append("{...}")
                has_expr = True

        combined = "".join(text_parts)
        if has_translatable_content(combined):
            self._add_string(
                combined, StringCategory.UI_MESSAGE,
                node.lineno,
                context=f"f-string in {self._current_func or self._current_class}",
                has_placeholders=has_expr
            )
        self.generic_visit(node)

    def visit_Constant(self, node: ast.Constant):
        """Извлекает строковые константы в определённых контекстах."""
        if isinstance(node.value, str) and has_translatable_content(node.value):
            # Пропускаем строки которые уже были обработаны в visit_Call, visit_Assign
            # Собираем только отдельно стоящие строки в списках / словарях
            pass

    def _extract_call_strings(self, node: ast.Call, category: StringCategory):
        """Извлекает строки из аргументов вызова функции."""
        for arg in node.args:
            if isinstance(arg, (ast.Constant, ast.Constant)):
                val = self._get_str_value(arg)
                if val and has_translatable_content(val):
                    self._add_string(val, category, arg.lineno,
                                     context=self._get_call_name(node))
            elif isinstance(arg, ast.JoinedStr):
                # f-строка - собираем шаблон
                text_parts = []
                has_expr = False
                for value in arg.values:
                    if isinstance(value, (ast.Constant, ast.Constant)):
                        text_parts.append(self._get_str_value(value))
                    elif isinstance(value, ast.FormattedValue):
                        text_parts.append("{...}")
                        has_expr = True
                combined = "".join(text_parts)
                if has_translatable_content(combined):
                    self._add_string(
                        combined, category, arg.lineno,
                        context=self._get_call_name(node),
                        has_placeholders=has_expr
                    )

        # keyword arguments (e.g. help="...")
        for kw in node.keywords:
            if kw.arg in ("help", "description", "epilog", "metavar"):
                if isinstance(kw.value, (ast.Constant, ast.Constant)):
                    val = self._get_str_value(kw.value)
                    if val and has_translatable_content(val):
                        self._add_string(
                            val, StringCategory.CLI_HELP, kw.value.lineno,
                            context=f"argparse {kw.arg}="
                        )

    def _extract_argparse_strings(self, node: ast.Call):
        """Извлекает строки из argparse вызовов."""
        for kw in node.keywords:
            if kw.arg in ("help", "description", "epilog", "metavar"):
                if isinstance(kw.value, (ast.Constant, ast.Constant)):
                    val = self._get_str_value(kw.value)
                    if val and has_translatable_content(val):
                        self._add_string(
                            val, StringCategory.CLI_HELP, kw.value.lineno,
                            context=f"argparse.{kw.arg}"
                        )

    def _extract_list_strings(self, node: ast.List, category: StringCategory):
        """Извлекает строки из списков (recommendations и т.п.)."""
        for elt in node.elts:
            if isinstance(elt, (ast.Constant, ast.Constant)):
                val = self._get_str_value(elt)
                if val and has_translatable_content(val):
                    self._add_string(val, category, elt.lineno)

    def _add_string(self, text: str, category: StringCategory, line: int,
                    context: str = "", has_placeholders: bool = False):
        """Добавляет строку в результат."""
        self.strings.append(ExtractedString(
            text=text,
            category=category.value,
            file=self.file_path,
            line=line,
            context=context,
            has_placeholders=has_placeholders
        ))

    def _get_call_name(self, node: ast.Call) -> str:
        """Получает имя вызываемой функции."""
        if isinstance(node.func, ast.Name):
            return node.func.id
        elif isinstance(node.func, ast.Attribute):
            if isinstance(node.func.value, ast.Name):
                return f"{node.func.value.id}.{node.func.attr}"
            return node.func.attr
        return ""

    @staticmethod
    def _get_str_value(node) -> str:
        """Извлекает строковое значение из AST-узла."""
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            return node.value
        return ""


class ProjectScanner:
    """
    Сканер проекта - обходит все файлы и извлекает переводимые строки.

    Поддерживает:
    - .py файлы (через AST)
    - .yaml файлы (через regex)
    - Строки в списках/словарях (recommendations, keywords, etc.)
    """

    def __init__(self, project_root: Path, exclude_dirs: Optional[List[str]] = None):
        self.project_root = Path(project_root)
        self.exclude_dirs = exclude_dirs or [
            "__pycache__", ".git", ".venv", "venv", "node_modules",
            ".swarm", ".claude", "locales", "i18n"
        ]

    def scan(self, extensions: Optional[List[str]] = None) -> List[ExtractedString]:
        """
        Сканирует проект и возвращает все извлечённые строки.

        Args:
            extensions: Расширения файлов для сканирования.
                По умолчанию: ['.py', '.yaml', '.yml']

        Returns:
            Список ExtractedString с уникальными строками
        """
        extensions = extensions or [".py", ".yaml", ".yml"]
        all_strings: List[ExtractedString] = []

        for ext in extensions:
            files = self._find_files(ext)
            for file_path in files:
                if ext == ".py":
                    strings = self._scan_python_file(file_path)
                elif ext in (".yaml", ".yml"):
                    strings = self._scan_yaml_file(file_path)
                else:
                    continue
                all_strings.extend(strings)

        # Постобработка: извлекаем строки из литералов в словарях/списках
        all_strings.extend(self._scan_inline_strings())

        # Дедупликация по тексту
        seen: Set[str] = set()
        unique: List[ExtractedString] = []
        for s in all_strings:
            if s.text not in seen:
                seen.add(s.text)
                unique.append(s)

        return unique

    def _find_files(self, extension: str) -> List[Path]:
        """Находит все файлы с указанным расширением."""
        files = []
        for path in self.project_root.rglob(f"*{extension}"):
            # Пропускаем исключённые директории
            parts = path.relative_to(self.project_root).parts
            if any(exc in parts for exc in self.exclude_dirs):
                continue
            files.append(path)
        return sorted(files)

    def _scan_python_file(self, file_path: Path) -> List[ExtractedString]:
        """Сканирует Python файл через AST."""
        try:
            source = file_path.read_text(encoding="utf-8")
            source_lines = source.splitlines()
            tree = ast.parse(source, filename=str(file_path))

            rel_path = str(file_path.relative_to(self.project_root))
            extractor = PythonStringExtractor(rel_path, source_lines)
            extractor.visit(tree)

            # Дополнительно: строки из recommendations и подобных списков
            extra = self._extract_list_literals(tree, rel_path)
            extractor.strings.extend(extra)

            return extractor.strings

        except SyntaxError as e:
            print(f"  [SKIP] Ошибка синтаксиса: {file_path}: {e}")
            return []
        except Exception as e:
            print(f"  [SKIP] Ошибка чтения: {file_path}: {e}")
            return []

    def _extract_list_literals(self, tree: ast.Module, file_path: str) -> List[ExtractedString]:
        """Извлекает строки из литералов списков (recommendations, keywords)."""
        strings = []

        for node in ast.walk(tree):
            # Ищем: "recommendations": [...]  или  recommendations.append("...")
            if isinstance(node, ast.List):
                for elt in node.elts:
                    if isinstance(elt, (ast.Constant, ast.Constant)):
                        val = elt.value if isinstance(elt, ast.Constant) else elt.s
                        if isinstance(val, str) and has_translatable_content(val):
                            strings.append(ExtractedString(
                                text=val,
                                category=StringCategory.REPORT_TEMPLATE.value,
                                file=file_path,
                                line=elt.lineno,
                                context="list literal"
                            ))

            # Ищем: dict values like {"msg": "Some message"}
            if isinstance(node, ast.Dict):
                for key, value in zip(node.keys, node.values):
                    if (isinstance(key, (ast.Constant, ast.Constant)) and
                            isinstance(value, (ast.Constant, ast.Constant))):
                        key_str = key.value if isinstance(key, ast.Constant) else key.s
                        val_str = value.value if isinstance(value, ast.Constant) else value.s
                        if (isinstance(key_str, str) and isinstance(val_str, str) and
                                key_str in ("msg", "message", "fix", "error",
                                           "summary", "description", "help") and
                                has_translatable_content(val_str)):
                            strings.append(ExtractedString(
                                text=val_str,
                                category=StringCategory.REPORT_TEMPLATE.value,
                                file=file_path,
                                line=value.lineno,
                                context=f"dict['{key_str}']"
                            ))

        return strings

    def _scan_yaml_file(self, file_path: Path) -> List[ExtractedString]:
        """Сканирует YAML файл через regex (без pyyaml зависимости)."""
        strings = []
        try:
            content = file_path.read_text(encoding="utf-8")
            rel_path = str(file_path.relative_to(self.project_root))

            for i, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()

                # Пропускаем пустые строки, чистые комментарии, ключи без значений
                if not stripped or stripped.startswith("#"):
                    # Русские комментарии - переводимые
                    if stripped.startswith("#") and re.search(r'[а-яА-ЯёЁ]', stripped):
                        comment_text = stripped.lstrip("# ").strip()
                        if has_translatable_content(comment_text):
                            strings.append(ExtractedString(
                                text=comment_text,
                                category=StringCategory.COMMENT.value,
                                file=rel_path,
                                line=i,
                                context="YAML comment"
                            ))
                    continue

                # Значения после ":"
                match = re.match(r'^[\w\-]+:\s*["\']?(.+?)["\']?\s*$', stripped)
                if match:
                    value = match.group(1).strip("'\"")
                    if has_translatable_content(value) and not re.match(r'^[\d\.\-]+$', value):
                        # Проверяем что это не техническое значение
                        if not re.match(r'^(true|false|null|none|\d+|[\w\-]+\.\w+)$', value, re.I):
                            strings.append(ExtractedString(
                                text=value,
                                category=StringCategory.CONFIG_LABEL.value,
                                file=rel_path,
                                line=i,
                                context="YAML value"
                            ))

        except Exception as e:
            print(f"  [SKIP] Ошибка YAML: {file_path}: {e}")

        return strings

    def _scan_inline_strings(self) -> List[ExtractedString]:
        """
        Дополнительный проход: ищет строки, которые AST мог пропустить.
        Regex-поиск по известным паттернам.
        """
        strings = []
        patterns = [
            # f"emoji text..."
            (r'(?:print|append)\s*\(\s*f?"([^"]*[а-яА-ЯёЁ][^"]*)"', StringCategory.UI_MESSAGE),
            # "emoji Status text"
            (r'(?:return|=)\s*f?"([^\n"]*(?:✅|❌|⚠️|🔴|🟡|🟢)[^\n"]*)"', StringCategory.STATUS_TEXT),
        ]

        for py_file in self._find_files(".py"):
            try:
                content = py_file.read_text(encoding="utf-8")
                rel_path = str(py_file.relative_to(self.project_root))

                for pattern, category in patterns:
                    for match in re.finditer(pattern, content):
                        text = match.group(1)
                        if has_translatable_content(text):
                            line_no = content[:match.start()].count('\n') + 1
                            strings.append(ExtractedString(
                                text=text,
                                category=category.value,
                                file=rel_path,
                                line=line_no,
                                context="regex extraction"
                            ))
            except Exception:
                continue

        return strings

    def generate_report(self, strings: List[ExtractedString]) -> Dict:
        """
        Генерирует отчёт о сканировании.

        Returns:
            Dict со статистикой и деталями
        """
        by_category: Dict[str, int] = {}
        by_language: Dict[str, int] = {}
        by_file: Dict[str, int] = {}

        for s in strings:
            by_category[s.category] = by_category.get(s.category, 0) + 1
            by_language[s.language_detected] = by_language.get(s.language_detected, 0) + 1
            by_file[s.file] = by_file.get(s.file, 0) + 1

        return {
            "total_strings": len(strings),
            "by_category": by_category,
            "by_language": by_language,
            "by_file": by_file,
            "with_placeholders": sum(1 for s in strings if s.has_placeholders),
        }

    def export_strings(self, strings: List[ExtractedString], output_path: Path):
        """Экспортирует извлечённые строки в JSON."""
        data = {
            "meta": {
                "project": str(self.project_root),
                "total": len(strings),
                "report": self.generate_report(strings),
            },
            "strings": [asdict(s) for s in strings]
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        print(f"  Экспортировано {len(strings)} строк -> {output_path}")


if __name__ == "__main__":
    import sys

    root = Path(sys.argv[1]) if len(sys.argv) > 1 else Path.cwd()
    scanner = ProjectScanner(root)

    print(f"\nСканирование проекта: {root}\n")
    strings = scanner.scan()

    report = scanner.generate_report(strings)

    print(f"\n{'='*60}")
    print(f"Найдено переводимых строк: {report['total_strings']}")
    print(f"{'='*60}")
    print(f"\nПо категориям:")
    for cat, count in sorted(report['by_category'].items()):
        print(f"  {cat}: {count}")
    print(f"\nПо языкам:")
    for lang, count in sorted(report['by_language'].items()):
        print(f"  {lang}: {count}")
    print(f"\nПо файлам:")
    for f, count in sorted(report['by_file'].items(), key=lambda x: -x[1]):
        print(f"  {f}: {count}")

    # Экспорт
    out = root / "src" / "i18n" / "extracted_strings.json"
    scanner.export_strings(strings, out)
