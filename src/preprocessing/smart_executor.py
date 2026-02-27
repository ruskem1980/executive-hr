"""
SmartExecutor - умное выполнение тестов и анализа с приоритизацией

Приоритеты:
1. Существующие pytest тесты (быстро, точно)
2. Статический анализ (средне, широкое покрытие)
3. Динамический анализ (медленно, глубокое понимание)
"""

from typing import Dict, List, Optional, Any
import subprocess
import json
import tempfile
from pathlib import Path
import logging


logger = logging.getLogger(__name__)


class SmartExecutor:
    """
    Умный исполнитель тестов и анализа.

    Выполняет тесты и анализ на основе классификации запроса,
    следуя стратегии приоритизации: pytest → static → dynamic.
    """

    def __init__(
        self,
        project_root: Optional[Path] = None,
        timeout_pytest: int = 120,
        timeout_static: int = 60,
        timeout_dynamic: int = 180
    ):
        """
        Args:
            project_root: Корень проекта (если None, используется текущая директория)
            timeout_pytest: Таймаут для pytest (секунды)
            timeout_static: Таймаут для статического анализа (секунды)
            timeout_dynamic: Таймаут для динамического анализа (секунды)
        """
        self.project_root = project_root or Path.cwd()
        self.timeout_pytest = timeout_pytest
        self.timeout_static = timeout_static
        self.timeout_dynamic = timeout_dynamic

    def execute(self, classification: Dict[str, Any]) -> Dict[str, Any]:
        """
        Выполняет тесты и анализ на основе классификации.

        Args:
            classification: Результат классификации запроса с полями:
                - tests_to_run: List[str] - пути к тестам для запуска
                - tools: List[str] - инструменты статического анализа
                - scope: str - область анализа (путь к файлам/директориям)
                - type: str - тип запроса (SECURITY, PERFORMANCE, etc.)

        Returns:
            Dict с результатами выполнения:
            {
                "pytest": {...},  # если были тесты
                "static_analysis": {...},  # всегда
                "dynamic_analysis": {...}  # только для PERFORMANCE
            }
        """
        results: Dict[str, Any] = {}

        # 1. Запускаем существующие pytest тесты (если есть)
        tests_to_run = classification.get("tests_to_run", [])
        if tests_to_run:
            logger.info(f"🧪 Running {len(tests_to_run)} existing tests...")
            print(f"🧪 Running {len(tests_to_run)} existing tests...")
            try:
                results["pytest"] = self._run_pytest_tests(tests_to_run)
            except Exception as e:
                logger.error(f"Pytest execution failed: {e}")
                results["pytest"] = {"error": str(e), "status": "failed"}

        # 2. Запускаем статический анализ
        tools = classification.get("tools", [])
        scope = classification.get("scope", ".")

        if tools:
            logger.info(f"🔍 Running static analysis: {', '.join(tools)}")
            print(f"🔍 Running static analysis: {', '.join(tools)}")
            try:
                results["static_analysis"] = self._run_static_analysis(tools, scope)
            except Exception as e:
                logger.error(f"Static analysis failed: {e}")
                results["static_analysis"] = {"error": str(e), "status": "failed"}

        # 3. Динамический анализ (опционально, только для performance)
        request_type = classification.get("type", "")
        if request_type == "PERFORMANCE":
            logger.info("⚡ Running dynamic profiling...")
            print("⚡ Running dynamic profiling...")
            try:
                results["dynamic_analysis"] = self._run_dynamic_analysis(scope)
            except Exception as e:
                logger.error(f"Dynamic analysis failed: {e}")
                results["dynamic_analysis"] = {"error": str(e), "status": "failed"}

        return results

    def _run_pytest_tests(self, test_paths: List[str]) -> Dict[str, Any]:
        """
        Запускает конкретные pytest тесты с JSON reporter.

        Args:
            test_paths: Список путей к тестовым файлам/директориям

        Returns:
            Dict с компактными результатами:
            {
                "passed": int,
                "failed": int,
                "skipped": int,
                "duration": float,
                "failures": [...],  # первые 5 ошибок
                "status": "passed" | "failed"
            }
        """
        # Создаем временный файл для JSON отчета
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json_report_path = f.name

        try:
            # Формируем команду pytest
            cmd = [
                "pytest",
                *test_paths,
                "-v",
                "--tb=short",
                "--json-report",
                f"--json-report-file={json_report_path}"
            ]

            logger.debug(f"Running command: {' '.join(cmd)}")

            # Запускаем pytest
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_pytest,
                cwd=self.project_root
            )

            # Читаем JSON отчет
            try:
                with open(json_report_path, 'r') as f:
                    data = json.load(f)
            except (FileNotFoundError, json.JSONDecodeError) as e:
                logger.error(f"Failed to read pytest JSON report: {e}")
                return {
                    "error": f"Failed to parse pytest output: {e}",
                    "status": "error",
                    "stdout": result.stdout[:500],
                    "stderr": result.stderr[:500]
                }

            # Извлекаем сводку
            summary = data.get("summary", {})
            tests = data.get("tests", [])

            # Компактное представление
            return {
                "passed": summary.get("passed", 0),
                "failed": summary.get("failed", 0),
                "skipped": summary.get("skipped", 0),
                "total": summary.get("total", 0),
                "duration": data.get("duration", 0.0),
                "failures": [
                    {
                        "test": t.get("nodeid", "unknown"),
                        "error": self._truncate_error(
                            t.get("call", {}).get("longrepr", "No error message"),
                            max_length=200
                        )
                    }
                    for t in tests if t.get("outcome") == "failed"
                ][:5],  # только первые 5 ошибок
                "status": "passed" if result.returncode == 0 else "failed",
                "exit_code": result.returncode
            }

        except subprocess.TimeoutExpired:
            logger.error(f"Pytest execution timed out after {self.timeout_pytest}s")
            return {
                "error": f"Pytest timed out after {self.timeout_pytest}s",
                "status": "timeout"
            }
        except Exception as e:
            logger.error(f"Unexpected error running pytest: {e}")
            return {
                "error": str(e),
                "status": "error"
            }
        finally:
            # Очищаем временный файл
            try:
                Path(json_report_path).unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to clean up temp file {json_report_path}: {e}")

    def _run_static_analysis(self, tools: List[str], scope: str) -> Dict[str, Any]:
        """
        Запускает статические анализаторы.

        Args:
            tools: Список инструментов для запуска (bandit, pylint, mypy, etc.)
            scope: Путь к анализируемым файлам/директориям

        Returns:
            Dict с результатами каждого инструмента:
            {
                "bandit": {...},
                "pylint": {...},
                ...
            }
        """
        results: Dict[str, Any] = {}

        for tool in tools:
            try:
                if tool == "bandit":
                    results["bandit"] = self._run_bandit(scope)
                elif tool == "pylint":
                    results["pylint"] = self._run_pylint(scope)
                elif tool == "mypy":
                    results["mypy"] = self._run_mypy(scope)
                elif tool == "safety":
                    results["safety"] = self._run_safety()
                elif tool == "ruff":
                    results["ruff"] = self._run_ruff(scope)
                else:
                    logger.warning(f"Unknown static analysis tool: {tool}")
                    results[tool] = {"error": f"Unknown tool: {tool}", "status": "skipped"}
            except Exception as e:
                logger.error(f"Error running {tool}: {e}")
                results[tool] = {"error": str(e), "status": "error"}

        return results

    def _run_bandit(self, scope: str) -> Dict[str, Any]:
        """Запускает Bandit для поиска уязвимостей безопасности."""
        cmd = ["bandit", "-r", scope, "-f", "json"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_static,
                cwd=self.project_root
            )

            # Bandit может вернуть ненулевой код, если найдены проблемы
            data = json.loads(result.stdout)

            issues = data.get("results", [])
            metrics = data.get("metrics", {})

            return {
                "issues_count": len(issues),
                "high_severity": len([i for i in issues if i.get("issue_severity") == "HIGH"]),
                "medium_severity": len([i for i in issues if i.get("issue_severity") == "MEDIUM"]),
                "low_severity": len([i for i in issues if i.get("issue_severity") == "LOW"]),
                "issues": [
                    {
                        "severity": i.get("issue_severity"),
                        "confidence": i.get("issue_confidence"),
                        "text": i.get("issue_text", "")[:100],
                        "file": i.get("filename"),
                        "line": i.get("line_number")
                    }
                    for i in issues[:10]  # первые 10 проблем
                ],
                "status": "completed"
            }

        except subprocess.TimeoutExpired:
            return {"error": f"Bandit timed out after {self.timeout_static}s", "status": "timeout"}
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse Bandit output: {e}", "status": "error"}
        except Exception as e:
            return {"error": str(e), "status": "error"}

    def _run_pylint(self, scope: str) -> Dict[str, Any]:
        """Запускает Pylint для анализа качества кода."""
        cmd = ["pylint", scope, "--output-format=json"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_static,
                cwd=self.project_root
            )

            # Pylint возвращает ненулевой код при наличии проблем
            issues = json.loads(result.stdout)

            return {
                "issues_count": len(issues),
                "errors": len([i for i in issues if i.get("type") == "error"]),
                "warnings": len([i for i in issues if i.get("type") == "warning"]),
                "refactors": len([i for i in issues if i.get("type") == "refactor"]),
                "conventions": len([i for i in issues if i.get("type") == "convention"]),
                "issues": [
                    {
                        "type": i.get("type"),
                        "message": i.get("message", "")[:100],
                        "file": i.get("path"),
                        "line": i.get("line"),
                        "symbol": i.get("symbol")
                    }
                    for i in issues[:10]  # первые 10 проблем
                ],
                "status": "completed"
            }

        except subprocess.TimeoutExpired:
            return {"error": f"Pylint timed out after {self.timeout_static}s", "status": "timeout"}
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse Pylint output: {e}", "status": "error"}
        except Exception as e:
            return {"error": str(e), "status": "error"}

    def _run_mypy(self, scope: str) -> Dict[str, Any]:
        """Запускает Mypy для проверки типов."""
        cmd = ["mypy", scope, "--no-error-summary", "--show-error-codes"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_static,
                cwd=self.project_root
            )

            # Парсим вывод mypy (построчно)
            lines = result.stdout.strip().split('\n') if result.stdout else []
            errors = [line for line in lines if ': error:' in line or ': note:' in line]

            return {
                "errors_count": len(errors),
                "errors": errors[:10],  # первые 10 ошибок
                "status": "completed" if result.returncode == 0 else "issues_found",
                "exit_code": result.returncode
            }

        except subprocess.TimeoutExpired:
            return {"error": f"Mypy timed out after {self.timeout_static}s", "status": "timeout"}
        except Exception as e:
            return {"error": str(e), "status": "error"}

    def _run_safety(self) -> Dict[str, Any]:
        """Запускает Safety для проверки известных уязвимостей в зависимостях."""
        cmd = ["safety", "check", "--json"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_static,
                cwd=self.project_root
            )

            # Safety может вернуть ненулевой код при наличии уязвимостей
            if result.stdout:
                data = json.loads(result.stdout)
                vulnerabilities = data if isinstance(data, list) else []

                return {
                    "vulnerabilities_count": len(vulnerabilities),
                    "vulnerabilities": [
                        {
                            "package": v.get("package"),
                            "version": v.get("installed_version"),
                            "vulnerability": v.get("vulnerability", "")[:100],
                            "severity": v.get("severity")
                        }
                        for v in vulnerabilities[:10]  # первые 10
                    ],
                    "status": "completed"
                }
            else:
                return {"vulnerabilities_count": 0, "status": "completed"}

        except subprocess.TimeoutExpired:
            return {"error": f"Safety timed out after {self.timeout_static}s", "status": "timeout"}
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse Safety output: {e}", "status": "error"}
        except Exception as e:
            return {"error": str(e), "status": "error"}

    def _run_ruff(self, scope: str) -> Dict[str, Any]:
        """Запускает Ruff для быстрого линтинга."""
        cmd = ["ruff", "check", scope, "--output-format=json"]

        try:
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_static,
                cwd=self.project_root
            )

            # Ruff возвращает JSON с проблемами
            issues = json.loads(result.stdout) if result.stdout else []

            return {
                "issues_count": len(issues),
                "issues": [
                    {
                        "code": i.get("code"),
                        "message": i.get("message", "")[:100],
                        "file": i.get("filename"),
                        "line": i.get("location", {}).get("row")
                    }
                    for i in issues[:10]  # первые 10
                ],
                "status": "completed"
            }

        except subprocess.TimeoutExpired:
            return {"error": f"Ruff timed out after {self.timeout_static}s", "status": "timeout"}
        except json.JSONDecodeError as e:
            return {"error": f"Failed to parse Ruff output: {e}", "status": "error"}
        except Exception as e:
            return {"error": str(e), "status": "error"}

    def _run_dynamic_analysis(self, scope: str) -> Dict[str, Any]:
        """
        Запускает динамическое профилирование (cProfile, memory_profiler).

        Args:
            scope: Путь к модулю/скрипту для профилирования

        Returns:
            Dict с результатами профилирования:
            {
                "cpu_profile": {...},
                "memory_profile": {...},
                "status": "completed" | "error"
            }
        """
        results: Dict[str, Any] = {}

        # 1. CPU профилирование через cProfile
        try:
            results["cpu_profile"] = self._run_cprofile(scope)
        except Exception as e:
            logger.error(f"cProfile failed: {e}")
            results["cpu_profile"] = {"error": str(e), "status": "error"}

        # 2. Memory профилирование через memory_profiler
        try:
            results["memory_profile"] = self._run_memory_profiler(scope)
        except Exception as e:
            logger.error(f"memory_profiler failed: {e}")
            results["memory_profile"] = {"error": str(e), "status": "error"}

        return results

    def _run_cprofile(self, scope: str) -> Dict[str, Any]:
        """Запускает cProfile для CPU профилирования."""
        # Создаем временный файл для профиля
        with tempfile.NamedTemporaryFile(mode='w', suffix='.prof', delete=False) as f:
            profile_path = f.name

        try:
            # Запускаем скрипт через cProfile
            cmd = ["python", "-m", "cProfile", "-o", profile_path, scope]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_dynamic,
                cwd=self.project_root
            )

            if result.returncode != 0:
                return {
                    "error": f"Script execution failed: {result.stderr[:200]}",
                    "status": "error"
                }

            # Анализируем профиль через pstats
            import pstats
            stats = pstats.Stats(profile_path)

            # Получаем топ функций по времени
            stats.sort_stats('cumulative')

            # Извлекаем статистику (в виде строки)
            import io
            stream = io.StringIO()
            stats.stream = stream
            stats.print_stats(10)  # топ 10

            return {
                "top_functions": stream.getvalue(),
                "total_calls": stats.total_calls,
                "status": "completed"
            }

        except subprocess.TimeoutExpired:
            return {"error": f"cProfile timed out after {self.timeout_dynamic}s", "status": "timeout"}
        except Exception as e:
            return {"error": str(e), "status": "error"}
        finally:
            # Очищаем временный файл
            try:
                Path(profile_path).unlink(missing_ok=True)
            except Exception as e:
                logger.warning(f"Failed to clean up profile file: {e}")

    def _run_memory_profiler(self, scope: str) -> Dict[str, Any]:
        """Запускает memory_profiler для профилирования памяти."""
        try:
            # Запускаем через memory_profiler
            cmd = ["python", "-m", "memory_profiler", scope]

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_dynamic,
                cwd=self.project_root
            )

            if result.returncode != 0:
                return {
                    "error": f"memory_profiler failed: {result.stderr[:200]}",
                    "status": "error"
                }

            # Парсим вывод memory_profiler
            output = result.stdout

            return {
                "profile_output": output[:1000],  # первые 1000 символов
                "status": "completed"
            }

        except subprocess.TimeoutExpired:
            return {"error": f"memory_profiler timed out after {self.timeout_dynamic}s", "status": "timeout"}
        except Exception as e:
            return {"error": str(e), "status": "error"}

    @staticmethod
    def _truncate_error(error_text: str, max_length: int = 200) -> str:
        """Обрезает текст ошибки до указанной длины."""
        if len(error_text) <= max_length:
            return error_text
        return error_text[:max_length] + "..."
