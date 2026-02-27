"""
GuardrailsValidator — валидация входов и выходов LLM.

Работает на встроенных правилах (regex, compile, эвристики).
Если установлен guardrails-ai — подключает дополнительные валидаторы из Hub.

Использование:
    validator = GuardrailsValidator()
    result = validator.validate_output("print('hello')", task_type="code")
    print(result.is_valid, result.score, result.errors)

    # Кастомное правило
    validator.add_rule("no_swear", lambda text: "damn" not in text.lower(), "Без ругательств")
    result = validator.validate_output("This is damn bad")
"""

import re
import json
from dataclasses import dataclass, field
from typing import List, Dict, Callable, Optional, Any


@dataclass
class ValidationResult:
    """Результат валидации текста или кода."""

    is_valid: bool
    errors: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    score: float = 1.0
    details: Dict[str, bool] = field(default_factory=dict)

    def __repr__(self) -> str:
        status = "PASSED" if self.is_valid else "FAILED"
        return (
            f"ValidationResult({status}, score={self.score:.2f}, "
            f"errors={len(self.errors)}, warnings={len(self.warnings)})"
        )


# ── Паттерны для встроенных правил ──

# Персональные данные (PII)
_PII_PATTERNS = {
    "email": re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b'),
    "phone_ru": re.compile(r'(?:\+7|8)[\s\-]?\(?\d{3}\)?[\s\-]?\d{3}[\s\-]?\d{2}[\s\-]?\d{2}'),
    "phone_intl": re.compile(r'\+\d{1,3}[\s\-]?\(?\d{2,4}\)?[\s\-]?\d{3,4}[\s\-]?\d{2,4}'),
    "ipv4": re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b'),
    "ssn": re.compile(r'\b\d{3}[\s\-]?\d{2}[\s\-]?\d{4}\b'),
    "passport_ru": re.compile(r'\b\d{4}[\s\-]?\d{6}\b'),
}

# Инъекции (SQL, XSS, команды)
_INJECTION_PATTERNS = {
    "sql_union": re.compile(r'\bUNION\s+(ALL\s+)?SELECT\b', re.IGNORECASE),
    "sql_drop": re.compile(r'\bDROP\s+(TABLE|DATABASE|INDEX)\b', re.IGNORECASE),
    "sql_insert": re.compile(r'\bINSERT\s+INTO\b.*\bVALUES\b', re.IGNORECASE | re.DOTALL),
    "sql_delete": re.compile(r'\bDELETE\s+FROM\b', re.IGNORECASE),
    "sql_comment": re.compile(r'(--|/\*|\*/)'),
    "sql_or_true": re.compile(r"'\s*OR\s+'?\d*'?\s*=\s*'?\d*", re.IGNORECASE),
    "xss_script": re.compile(r'<\s*script\b[^>]*>.*?</\s*script\s*>', re.IGNORECASE | re.DOTALL),
    "xss_event": re.compile(r'\bon\w+\s*=\s*["\']', re.IGNORECASE),
    "xss_javascript": re.compile(r'javascript\s*:', re.IGNORECASE),
    "cmd_pipe": re.compile(r';\s*(rm|cat|wget|curl|bash|sh|python|perl|nc)\s', re.IGNORECASE),
    "cmd_backtick": re.compile(r'`[^`]+`'),
    "cmd_subshell": re.compile(r'\$\([^)]+\)'),
}

# Секреты (API-ключи, токены, пароли)
_SECRET_PATTERNS = {
    "aws_key": re.compile(r'AKIA[0-9A-Z]{16}'),
    "aws_secret": re.compile(r'(?:aws_secret|secret_key)\s*[=:]\s*["\']?[A-Za-z0-9/+=]{40}', re.IGNORECASE),
    "github_token": re.compile(r'gh[ps]_[A-Za-z0-9_]{36,}'),
    "generic_api_key": re.compile(
        r'(?:api[_\-]?key|apikey|api[_\-]?secret|api[_\-]?token)\s*[=:]\s*["\']?[A-Za-z0-9\-_]{20,}',
        re.IGNORECASE,
    ),
    "bearer_token": re.compile(r'Bearer\s+[A-Za-z0-9\-_\.]{20,}', re.IGNORECASE),
    "private_key": re.compile(r'-----BEGIN\s+(RSA\s+)?PRIVATE\s+KEY-----'),
    "password_assign": re.compile(
        r'(?:password|passwd|pwd)\s*[=:]\s*["\'][^"\']{4,}["\']',
        re.IGNORECASE,
    ),
    "slack_token": re.compile(r'xox[bprs]-[A-Za-z0-9\-]{10,}'),
    "openai_key": re.compile(r'sk-[A-Za-z0-9]{20,}'),
}

# Плейсхолдеры
_PLACEHOLDER_PATTERNS = {
    "todo": re.compile(r'\bTODO\b', re.IGNORECASE),
    "fixme": re.compile(r'\bFIXME\b', re.IGNORECASE),
    "hack": re.compile(r'\bHACK\b', re.IGNORECASE),
    "xxx": re.compile(r'\bXXX\b'),
    "placeholder": re.compile(r'\bplaceholder\b', re.IGNORECASE),
    "lorem_ipsum": re.compile(r'\blorem\s+ipsum\b', re.IGNORECASE),
    "pass_only": re.compile(r'^\s*pass\s*$', re.MULTILINE),
    "ellipsis_body": re.compile(r'^\s*\.\.\.\s*$', re.MULTILINE),
}

# Максимальная длина по умолчанию (символов)
_DEFAULT_MAX_LENGTH = 100_000


class GuardrailsValidator:
    """
    Валидатор входов и выходов LLM.

    Работает на встроенных regex-правилах. Если установлен пакет guardrails-ai,
    подключает дополнительные валидаторы из Guardrails Hub.
    """

    def __init__(self, rules_config: Optional[Dict[str, Any]] = None):
        """
        Инициализация валидатора.

        Аргументы:
            rules_config: Конфигурация правил. Ключи:
                - max_length (int): макс. длина текста (по умолчанию 100_000)
                - enabled_rules (list): список включённых правил (по умолчанию все)
                - disabled_rules (list): список отключённых правил
                - custom_pii_patterns (dict): дополнительные PII паттерны
        """
        self._config = rules_config or {}
        self._max_length = self._config.get("max_length", _DEFAULT_MAX_LENGTH)

        # Кастомные правила: имя -> (функция, описание)
        self._custom_rules: Dict[str, tuple] = {}

        # Статистика валидаций
        self._stats = {
            "total": 0,
            "passed": 0,
            "failed": 0,
            "by_rule": {},
        }

        # Определяем включённые/выключенные правила
        self._enabled_rules = set(self._config.get("enabled_rules", []))
        self._disabled_rules = set(self._config.get("disabled_rules", []))

        # Проверяем доступность guardrails-ai
        self._guardrails_available = False
        try:
            import guardrails  # noqa: F401
            self._guardrails_available = True
        except ImportError:
            pass

    def _is_rule_enabled(self, rule_name: str) -> bool:
        """Проверяет, включено ли правило."""
        if self._disabled_rules and rule_name in self._disabled_rules:
            return False
        if self._enabled_rules:
            return rule_name in self._enabled_rules
        return True

    def _update_stats(self, result: ValidationResult) -> None:
        """Обновляет внутреннюю статистику валидаций."""
        self._stats["total"] += 1
        if result.is_valid:
            self._stats["passed"] += 1
        else:
            self._stats["failed"] += 1

        for rule_name, passed in result.details.items():
            if rule_name not in self._stats["by_rule"]:
                self._stats["by_rule"][rule_name] = {"passed": 0, "failed": 0}
            if passed:
                self._stats["by_rule"][rule_name]["passed"] += 1
            else:
                self._stats["by_rule"][rule_name]["failed"] += 1

    # ── Встроенные правила ──

    @staticmethod
    def _check_no_pii(text: str) -> tuple:
        """Проверка на утечку персональных данных (PII)."""
        found = []
        for pii_type, pattern in _PII_PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                found.append(f"Обнаружены PII ({pii_type}): {len(matches)} совпадений")
        return len(found) == 0, found

    @staticmethod
    def _check_no_injection(text: str) -> tuple:
        """Проверка на SQL/XSS/command injection паттерны."""
        found = []
        for inj_type, pattern in _INJECTION_PATTERNS.items():
            if pattern.search(text):
                found.append(f"Обнаружен паттерн инъекции ({inj_type})")
        return len(found) == 0, found

    @staticmethod
    def _check_valid_python(code: str) -> tuple:
        """Проверка синтаксиса Python через compile()."""
        try:
            compile(code, "<validation>", "exec")
            return True, []
        except SyntaxError as e:
            return False, [f"Синтаксическая ошибка Python: {e.msg} (строка {e.lineno})"]

    @staticmethod
    def _check_no_secrets(text: str) -> tuple:
        """Проверка на утечку секретов (API-ключи, токены, пароли)."""
        found = []
        for secret_type, pattern in _SECRET_PATTERNS.items():
            if pattern.search(text):
                found.append(f"Обнаружен секрет ({secret_type})")
        return len(found) == 0, found

    def _check_max_length(self, text: str) -> tuple:
        """Проверка максимальной длины текста."""
        if len(text) > self._max_length:
            return False, [
                f"Текст превышает лимит: {len(text)} > {self._max_length} символов"
            ]
        return True, []

    @staticmethod
    def _check_has_structure(code: str) -> tuple:
        """Проверка наличия структуры (функции, классы) в коде."""
        has_func = bool(re.search(r'^\s*def\s+\w+', code, re.MULTILINE))
        has_class = bool(re.search(r'^\s*class\s+\w+', code, re.MULTILINE))
        has_import = bool(re.search(r'^\s*(import|from)\s+', code, re.MULTILINE))

        if has_func or has_class:
            return True, []
        elif has_import:
            # Есть импорты, но нет функций/классов — предупреждение
            return True, []

        return False, ["Код не содержит функций или классов"]

    @staticmethod
    def _check_no_placeholder(text: str) -> tuple:
        """Проверка на TODO, FIXME, placeholder текст."""
        found = []
        for ph_type, pattern in _PLACEHOLDER_PATTERNS.items():
            matches = pattern.findall(text)
            if matches:
                found.append(f"Обнаружен placeholder ({ph_type}): {len(matches)} шт.")
        return len(found) == 0, found

    # ── Публичные методы ──

    def validate_output(
        self,
        output: str,
        expected_format: Optional[str] = None,
        task_type: Optional[str] = None,
    ) -> ValidationResult:
        """
        Валидация выхода LLM.

        Аргументы:
            output: текст выхода LLM
            expected_format: ожидаемый формат ('json', 'python', 'markdown', None)
            task_type: тип задачи ('code', 'text', 'review', None)

        Возвращает:
            ValidationResult с детальным отчётом
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, bool] = {}

        # Набор правил зависит от типа задачи
        rules_to_run = []

        # Всегда проверяем
        rules_to_run.append(("max_length", self._check_max_length))
        rules_to_run.append(("no_pii", self._check_no_pii))
        rules_to_run.append(("no_secrets", self._check_no_secrets))

        # Для кода — дополнительные проверки
        if task_type == "code" or expected_format == "python":
            rules_to_run.append(("valid_python", self._check_valid_python))
            rules_to_run.append(("has_structure", self._check_has_structure))
            rules_to_run.append(("no_placeholder", self._check_no_placeholder))

        # Для JSON
        if expected_format == "json":
            rules_to_run.append(("valid_json", lambda t: self._check_json(t)))

        # Для текста — проверяем инъекции
        if task_type in ("text", "review", None):
            rules_to_run.append(("no_injection", self._check_no_injection))

        # Плейсхолдеры для текста
        if task_type in ("text", "review"):
            rules_to_run.append(("no_placeholder", self._check_no_placeholder))

        # Применяем правила
        for rule_name, rule_fn in rules_to_run:
            if not self._is_rule_enabled(rule_name):
                continue
            passed, issues = rule_fn(output)
            details[rule_name] = passed
            if not passed:
                errors.extend(issues)

        # Кастомные правила
        for rule_name, (rule_fn, description) in self._custom_rules.items():
            if not self._is_rule_enabled(rule_name):
                continue
            try:
                passed = rule_fn(output)
                details[rule_name] = passed
                if not passed:
                    errors.append(f"Правило '{rule_name}' не пройдено: {description}")
            except Exception as e:
                details[rule_name] = False
                warnings.append(f"Ошибка в правиле '{rule_name}': {e}")

        # Guardrails AI (если доступен)
        if self._guardrails_available:
            hub_warnings = self._run_guardrails_hub(output, task_type)
            warnings.extend(hub_warnings)

        # Подсчёт score
        total_rules = len(details)
        passed_rules = sum(1 for v in details.values() if v)
        score = passed_rules / total_rules if total_rules > 0 else 1.0

        is_valid = len(errors) == 0

        result = ValidationResult(
            is_valid=is_valid,
            errors=errors,
            warnings=warnings,
            score=score,
            details=details,
        )
        self._update_stats(result)
        return result

    def validate_input(self, prompt: str) -> ValidationResult:
        """
        Валидация входного промпта.

        Проверяет промпт на инъекции, PII и длину.

        Аргументы:
            prompt: входной промпт для LLM

        Возвращает:
            ValidationResult
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, bool] = {}

        # Базовая проверка
        if not prompt or not prompt.strip():
            result = ValidationResult(
                is_valid=False,
                errors=["Пустой промпт"],
                score=0.0,
                details={"non_empty": False},
            )
            self._update_stats(result)
            return result

        details["non_empty"] = True

        # Проверка длины
        if self._is_rule_enabled("max_length"):
            passed, issues = self._check_max_length(prompt)
            details["max_length"] = passed
            if not passed:
                errors.extend(issues)

        # Проверка на инъекции
        if self._is_rule_enabled("no_injection"):
            passed, issues = self._check_no_injection(prompt)
            details["no_injection"] = passed
            if not passed:
                # Для промптов инъекции — предупреждения, не ошибки
                warnings.extend(issues)
                details["no_injection"] = True  # Не блокируем, но предупреждаем

        # Проверка PII
        if self._is_rule_enabled("no_pii"):
            passed, issues = self._check_no_pii(prompt)
            details["no_pii"] = passed
            if not passed:
                warnings.extend(issues)

        # Кастомные правила
        for rule_name, (rule_fn, description) in self._custom_rules.items():
            if not self._is_rule_enabled(rule_name):
                continue
            try:
                passed = rule_fn(prompt)
                details[rule_name] = passed
                if not passed:
                    errors.append(f"Правило '{rule_name}' не пройдено: {description}")
            except Exception as e:
                details[rule_name] = False
                warnings.append(f"Ошибка в правиле '{rule_name}': {e}")

        total_rules = len(details)
        passed_rules = sum(1 for v in details.values() if v)
        score = passed_rules / total_rules if total_rules > 0 else 1.0

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            score=score,
            details=details,
        )
        self._update_stats(result)
        return result

    def validate_code(self, code: str, language: str = "python") -> ValidationResult:
        """
        Валидация сгенерированного кода.

        Аргументы:
            code: исходный код
            language: язык программирования ('python', 'javascript', 'generic')

        Возвращает:
            ValidationResult
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, bool] = {}

        # Проверка на пустоту
        if not code or not code.strip():
            result = ValidationResult(
                is_valid=False,
                errors=["Пустой код"],
                score=0.0,
                details={"non_empty": False},
            )
            self._update_stats(result)
            return result

        details["non_empty"] = True

        # Длина
        if self._is_rule_enabled("max_length"):
            passed, issues = self._check_max_length(code)
            details["max_length"] = passed
            if not passed:
                errors.extend(issues)

        # Синтаксис Python
        if language == "python" and self._is_rule_enabled("valid_python"):
            passed, issues = self._check_valid_python(code)
            details["valid_python"] = passed
            if not passed:
                errors.extend(issues)

        # Структура
        if self._is_rule_enabled("has_structure"):
            passed, issues = self._check_has_structure(code)
            details["has_structure"] = passed
            if not passed:
                warnings.extend(issues)
                # Структура — предупреждение, не ошибка (может быть скрипт)
                details["has_structure"] = True

        # Секреты
        if self._is_rule_enabled("no_secrets"):
            passed, issues = self._check_no_secrets(code)
            details["no_secrets"] = passed
            if not passed:
                errors.extend(issues)

        # Плейсхолдеры
        if self._is_rule_enabled("no_placeholder"):
            passed, issues = self._check_no_placeholder(code)
            details["no_placeholder"] = passed
            if not passed:
                warnings.extend(issues)
                # Плейсхолдеры — предупреждения для кода
                details["no_placeholder"] = True

        # PII в коде
        if self._is_rule_enabled("no_pii"):
            passed, issues = self._check_no_pii(code)
            details["no_pii"] = passed
            if not passed:
                warnings.extend(issues)

        # Кастомные правила
        for rule_name, (rule_fn, description) in self._custom_rules.items():
            if not self._is_rule_enabled(rule_name):
                continue
            try:
                passed = rule_fn(code)
                details[rule_name] = passed
                if not passed:
                    errors.append(f"Правило '{rule_name}' не пройдено: {description}")
            except Exception as e:
                details[rule_name] = False
                warnings.append(f"Ошибка в правиле '{rule_name}': {e}")

        total_rules = len(details)
        passed_rules = sum(1 for v in details.values() if v)
        score = passed_rules / total_rules if total_rules > 0 else 1.0

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            score=score,
            details=details,
        )
        self._update_stats(result)
        return result

    def validate_json(
        self, text: str, schema: Optional[Dict[str, Any]] = None
    ) -> ValidationResult:
        """
        Проверка JSON-формата и опциональная валидация по схеме.

        Аргументы:
            text: текст, который должен быть валидным JSON
            schema: JSON Schema для валидации структуры (опционально)

        Возвращает:
            ValidationResult
        """
        errors: List[str] = []
        warnings: List[str] = []
        details: Dict[str, bool] = {}

        passed, issues = self._check_json(text)
        details["valid_json"] = passed
        if not passed:
            errors.extend(issues)
            result = ValidationResult(
                is_valid=False,
                errors=errors,
                score=0.0,
                details=details,
            )
            self._update_stats(result)
            return result

        # Если есть схема — валидируем по ней
        if schema:
            parsed = json.loads(text)
            schema_passed, schema_issues = self._validate_json_schema(parsed, schema)
            details["schema_valid"] = schema_passed
            if not schema_passed:
                errors.extend(schema_issues)

        # Проверка на секреты в JSON
        if self._is_rule_enabled("no_secrets"):
            passed, issues = self._check_no_secrets(text)
            details["no_secrets"] = passed
            if not passed:
                warnings.extend(issues)

        total_rules = len(details)
        passed_rules = sum(1 for v in details.values() if v)
        score = passed_rules / total_rules if total_rules > 0 else 1.0

        result = ValidationResult(
            is_valid=len(errors) == 0,
            errors=errors,
            warnings=warnings,
            score=score,
            details=details,
        )
        self._update_stats(result)
        return result

    def add_rule(
        self, name: str, rule_fn: Callable[[str], bool], description: str = ""
    ) -> None:
        """
        Добавление кастомного правила валидации.

        Аргументы:
            name: уникальное имя правила
            rule_fn: функция (text) -> bool, True если правило пройдено
            description: описание правила для отчётов об ошибках
        """
        if not callable(rule_fn):
            raise TypeError(f"rule_fn должен быть callable, получен {type(rule_fn)}")
        self._custom_rules[name] = (rule_fn, description)

    def get_stats(self) -> Dict[str, Any]:
        """
        Статистика валидаций.

        Возвращает:
            dict с ключами: total, passed, failed, by_rule, pass_rate
        """
        total = self._stats["total"]
        return {
            "total": total,
            "passed": self._stats["passed"],
            "failed": self._stats["failed"],
            "pass_rate": self._stats["passed"] / total if total > 0 else 0.0,
            "by_rule": dict(self._stats["by_rule"]),
        }

    # ── Вспомогательные методы ──

    @staticmethod
    def _check_json(text: str) -> tuple:
        """Проверка валидности JSON."""
        try:
            json.loads(text)
            return True, []
        except json.JSONDecodeError as e:
            return False, [f"Невалидный JSON: {e.msg} (позиция {e.pos})"]

    @staticmethod
    def _validate_json_schema(data: Any, schema: Dict[str, Any]) -> tuple:
        """
        Простая валидация JSON по схеме (без jsonschema).

        Поддерживает базовые проверки: required, type, properties.
        Для полной валидации рекомендуется установить jsonschema.
        """
        errors = []

        # Попытка использовать jsonschema если установлен
        try:
            import jsonschema
            try:
                jsonschema.validate(data, schema)
                return True, []
            except jsonschema.ValidationError as e:
                return False, [f"Ошибка схемы: {e.message}"]
        except ImportError:
            pass

        # Fallback: базовая валидация
        expected_type = schema.get("type")
        if expected_type:
            type_map = {
                "object": dict,
                "array": list,
                "string": str,
                "number": (int, float),
                "integer": int,
                "boolean": bool,
                "null": type(None),
            }
            expected_py_type = type_map.get(expected_type)
            if expected_py_type and not isinstance(data, expected_py_type):
                errors.append(
                    f"Ожидался тип '{expected_type}', получен '{type(data).__name__}'"
                )
                return False, errors

        # Проверка required полей для объектов
        if isinstance(data, dict):
            required = schema.get("required", [])
            for field_name in required:
                if field_name not in data:
                    errors.append(f"Отсутствует обязательное поле: '{field_name}'")

            # Проверка типов свойств
            properties = schema.get("properties", {})
            for prop_name, prop_schema in properties.items():
                if prop_name in data:
                    prop_type = prop_schema.get("type")
                    if prop_type:
                        type_map = {
                            "string": str,
                            "number": (int, float),
                            "integer": int,
                            "boolean": bool,
                            "array": list,
                            "object": dict,
                        }
                        expected = type_map.get(prop_type)
                        if expected and not isinstance(data[prop_name], expected):
                            errors.append(
                                f"Поле '{prop_name}': ожидался тип '{prop_type}', "
                                f"получен '{type(data[prop_name]).__name__}'"
                            )

        return len(errors) == 0, errors

    def _run_guardrails_hub(self, text: str, task_type: Optional[str]) -> List[str]:
        """
        Запуск валидаторов из Guardrails Hub (если доступны).

        Возвращает список предупреждений (не блокирует, только информирует).
        """
        warnings = []
        try:
            from guardrails.hub import ToxicLanguage, DetectPII

            # Проверка токсичности
            try:
                toxic_validator = ToxicLanguage(on_fail="noop")
                result = toxic_validator.validate(text, {})
                if hasattr(result, 'outcome') and result.outcome == 'fail':
                    warnings.append("Guardrails Hub: обнаружен токсичный контент")
            except Exception:
                pass

            # Проверка PII через Hub
            try:
                pii_validator = DetectPII(on_fail="noop")
                result = pii_validator.validate(text, {})
                if hasattr(result, 'outcome') and result.outcome == 'fail':
                    warnings.append("Guardrails Hub: обнаружены персональные данные (PII)")
            except Exception:
                pass

        except ImportError:
            # Guardrails Hub не установлен — пропускаем тихо
            pass
        except Exception:
            # Любая другая ошибка — не блокируем
            pass

        return warnings
