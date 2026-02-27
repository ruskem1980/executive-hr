"""
ToolOrchestrator - оркестратор инструментов анализа кода

Параллельный запуск инструментов статического анализа:
- bandit (безопасность)
- safety (уязвимости зависимостей)
- pylint (качество кода)
- radon (сложность)
- coverage (покрытие тестами)
- semgrep (SAST)

Компактные отчеты: 150-500 токенов вместо 10,000+
"""

import subprocess
import json
import logging
from pathlib import Path
from typing import Dict, List, Any, Optional
from concurrent.futures import ThreadPoolExecutor, as_completed, TimeoutError
from enum import Enum

logger = logging.getLogger(__name__)


class RequestType(Enum):
    """Типы запросов для агрегации"""
    SECURITY = "security"
    PERFORMANCE = "performance"
    QUALITY = "quality"
    COVERAGE = "coverage"
    GENERAL = "general"


class ToolOrchestrator:
    """Запускает инструменты анализа и агрегирует результаты"""

    def __init__(self, project_root: Path, timeout: int = 300):
        """
        Инициализация оркестратора

        Args:
            project_root: корневая директория проекта
            timeout: таймаут для каждого инструмента (секунды)
        """
        self.project_root = Path(project_root)
        self.results_dir = self.project_root / "analysis_results"
        self.results_dir.mkdir(exist_ok=True)
        self.timeout = timeout

        logger.info(f"ToolOrchestrator initialized: {self.project_root}")

    def run_analysis(self, classification: Dict) -> Dict:
        """
        Запускает все необходимые инструменты и возвращает агрегированный отчет

        Args:
            classification: результат из RequestClassifier
                {
                    "primary_type": "security",
                    "tools": ["bandit", "safety"],
                    "scope": "src/auth"
                }

        Returns:
            Компактный структурированный отчет для LLM (150-500 токенов)
        """
        req_type_str = classification.get("primary_type", "general")
        try:
            req_type = RequestType(req_type_str)
        except ValueError:
            req_type = RequestType.GENERAL

        tools = classification.get("tools", [])
        scope = classification.get("scope", ".")

        logger.info(f"Starting analysis: type={req_type.value}, tools={tools}, scope={scope}")

        # Запускаем инструменты параллельно
        results = self._run_tools_parallel(tools, scope)

        # Агрегируем результаты в компактный отчет
        report = self._aggregate_results(req_type, results, scope)

        # Сохраняем детальные результаты для человека (опционально)
        self._save_detailed_results(results)

        logger.info(f"Analysis completed: {len(results)} tools executed")
        return report

    def _run_tools_parallel(self, tools: List[str], scope: str) -> Dict[str, Any]:
        """
        Запускает инструменты параллельно

        Args:
            tools: список инструментов для запуска
            scope: область анализа (путь к файлу/директории)

        Returns:
            Словарь {tool_name: result}
        """
        results = {}
        max_workers = min(len(tools), 6)  # ограничиваем до 6 параллельных задач

        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(self._run_tool, tool, scope): tool
                for tool in tools
            }

            for future in as_completed(futures):
                tool = futures[future]
                try:
                    results[tool] = future.result(timeout=self.timeout)
                    logger.info(f"Tool '{tool}' completed successfully")
                except TimeoutError:
                    results[tool] = {"error": f"Timeout after {self.timeout}s"}
                    logger.error(f"Tool '{tool}' timed out")
                except Exception as e:
                    results[tool] = {"error": str(e)}
                    logger.error(f"Tool '{tool}' failed: {e}")

        return results

    def _run_tool(self, tool: str, scope: str) -> Dict:
        """
        Запускает отдельный инструмент

        Args:
            tool: имя инструмента
            scope: область анализа

        Returns:
            Результат работы инструмента
        """
        tool_map = {
            "bandit": self._run_bandit,
            "safety": self._run_safety,
            "pylint": self._run_pylint,
            "radon": self._run_radon,
            "coverage": self._run_coverage,
            "semgrep": self._run_semgrep,
        }

        runner = tool_map.get(tool)
        if runner:
            return runner(scope)
        else:
            logger.warning(f"Unknown tool: {tool}")
            return {"error": f"Unknown tool: {tool}"}

    def _run_bandit(self, scope: str) -> Dict:
        """
        Запускает bandit security scanner

        Args:
            scope: путь для анализа

        Returns:
            Словарь с найденными уязвимостями
        """
        cmd = [
            "bandit",
            "-r", scope,
            "-f", "json",
            "-ll"  # только medium/high severity
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.project_root,
            timeout=self.timeout
        )

        if result.returncode in [0, 1]:  # 0=no issues, 1=issues found
            try:
                data = json.loads(result.stdout)

                # Преобразуем в компактный формат
                issues = []
                for item in data.get("results", []):
                    issues.append({
                        "sev": item["issue_severity"],
                        "file": f"{Path(item['filename']).name}:{item['line_number']}",
                        "rule": item["test_id"],
                        "cwe": item.get("issue_cwe", {}).get("id", "") if isinstance(item.get("issue_cwe"), dict) else "",
                        "msg": item["issue_text"][:60],
                        "code": item["code"][:40].strip(),
                        "fix": self._suggest_fix(item["test_id"])
                    })

                return {
                    "issues": issues,
                    "stats": {
                        "high": sum(1 for i in issues if i["sev"] == "HIGH"),
                        "medium": sum(1 for i in issues if i["sev"] == "MEDIUM")
                    }
                }
            except json.JSONDecodeError as e:
                logger.error(f"Bandit JSON parsing failed: {e}")
                return {"error": f"JSON parsing failed: {e}"}

        return {"error": result.stderr or "Bandit execution failed"}

    def _run_safety(self, scope: str) -> Dict:
        """
        Запускает safety для проверки уязвимостей зависимостей

        Args:
            scope: путь к requirements.txt или Pipfile

        Returns:
            Словарь с найденными CVE
        """
        # Ищем requirements.txt
        req_file = self.project_root / "requirements.txt"
        if not req_file.exists():
            return {"error": "requirements.txt not found"}

        cmd = [
            "safety",
            "check",
            "--json",
            "--file", str(req_file)
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.project_root,
            timeout=self.timeout
        )

        try:
            data = json.loads(result.stdout)

            vulnerabilities = []
            for vuln in data:
                vulnerabilities.append({
                    "pkg": vuln[0],
                    "version": vuln[2],
                    "cve": vuln[4] if len(vuln) > 4 else "N/A",
                    "severity": "HIGH" if "critical" in str(vuln).lower() else "MEDIUM",
                    "fix": f"upgrade to {vuln[3]}" if len(vuln) > 3 else "review"
                })

            return {
                "vulnerabilities": vulnerabilities,
                "count": len(vulnerabilities)
            }
        except (json.JSONDecodeError, IndexError) as e:
            logger.error(f"Safety parsing failed: {e}")
            return {"vulnerabilities": [], "count": 0}

    def _run_pylint(self, scope: str) -> Dict:
        """
        Запускает pylint для проверки качества кода

        Args:
            scope: путь для анализа

        Returns:
            Словарь с нарушениями стиля и ошибками
        """
        cmd = ["pylint", scope, "--output-format=json"]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.project_root,
            timeout=self.timeout
        )

        try:
            data = json.loads(result.stdout)

            # Группируем по severity
            issues_by_severity = {
                "error": [],
                "warning": [],
                "refactor": [],
                "convention": []
            }

            for item in data:
                severity = item.get("type", "convention")
                if severity in issues_by_severity:
                    issues_by_severity[severity].append({
                        "file": f"{Path(item['path']).name}:{item['line']}",
                        "rule": item["message-id"],
                        "msg": item["message"][:60]
                    })

            # Вычисляем score (обычно в stderr или отдельной команде)
            score = 0.0
            if result.stderr:
                import re
                score_match = re.search(r"Your code has been rated at ([\d.]+)/10", result.stderr)
                if score_match:
                    score = float(score_match.group(1))

            return {
                "issues": issues_by_severity,
                "score": score
            }
        except json.JSONDecodeError as e:
            logger.error(f"Pylint parsing failed: {e}")
            return {"issues": {}, "score": 0.0, "error": str(e)}

    def _run_radon(self, scope: str) -> Dict:
        """
        Запускает radon для анализа сложности кода

        Args:
            scope: путь для анализа

        Returns:
            Словарь со сложностью функций и maintainability index
        """
        results = {}

        # Cyclomatic complexity
        cmd_cc = ["radon", "cc", scope, "-j", "-n", "C"]  # только C и выше
        result_cc = subprocess.run(
            cmd_cc,
            capture_output=True,
            text=True,
            cwd=self.project_root,
            timeout=self.timeout
        )

        try:
            data_cc = json.loads(result_cc.stdout)

            complex_functions = []
            for file_path, functions in data_cc.items():
                for func in functions:
                    if func["complexity"] >= 10:  # высокая сложность
                        complex_functions.append({
                            "func": func["name"],
                            "file": f"{Path(file_path).name}:{func['lineno']}",
                            "complexity": func["complexity"],
                            "rank": func["rank"]
                        })

            results["complex_functions"] = sorted(
                complex_functions,
                key=lambda x: x["complexity"],
                reverse=True
            )[:10]
        except json.JSONDecodeError:
            results["complex_functions"] = []

        # Maintainability index
        cmd_mi = ["radon", "mi", scope, "-j"]
        result_mi = subprocess.run(
            cmd_mi,
            capture_output=True,
            text=True,
            cwd=self.project_root,
            timeout=self.timeout
        )

        try:
            data_mi = json.loads(result_mi.stdout)

            low_maintainability = [
                {"file": Path(k).name, "mi": v["mi"], "rank": v["rank"]}
                for k, v in data_mi.items()
                if v["mi"] < 65  # плохая maintainability
            ]

            results["low_maintainability"] = low_maintainability
        except json.JSONDecodeError:
            results["low_maintainability"] = []

        return results

    def _run_coverage(self, scope: str) -> Dict:
        """
        Анализирует test coverage

        Args:
            scope: путь для анализа

        Returns:
            Словарь с покрытием и пробелами
        """
        # Предполагаем, что coverage уже запущен и есть .coverage файл
        cmd = ["coverage", "json", "-o", "-"]
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.project_root,
            timeout=self.timeout
        )

        if result.returncode == 0:
            try:
                data = json.loads(result.stdout)

                # Находим критичные непокрытые участки
                critical_gaps = []
                for file_path, file_data in data.get("files", {}).items():
                    if scope in file_path:
                        summary = file_data.get("summary", {})
                        coverage_pct = summary.get("percent_covered", 0)

                        if coverage_pct < 80:  # низкое покрытие
                            missing_lines = file_data.get("missing_lines", [])
                            # Группируем в диапазоны
                            ranges = self._group_line_ranges(missing_lines)

                            critical_gaps.append({
                                "file": Path(file_path).name,
                                "coverage": f"{coverage_pct:.1f}%",
                                "missing_lines": ranges[:3],  # только первые 3 диапазона
                                "priority": self._determine_priority(file_path, coverage_pct)
                            })

                totals = data.get("totals", {})
                overall_pct = totals.get("percent_covered", 0)

                return {
                    "overall": f"{overall_pct:.1f}%",
                    "critical_gaps": sorted(
                        critical_gaps,
                        key=lambda x: {"CRITICAL": 4, "HIGH": 3, "MEDIUM": 2, "LOW": 1}.get(x["priority"], 0),
                        reverse=True
                    )[:5]
                }
            except json.JSONDecodeError as e:
                logger.error(f"Coverage JSON parsing failed: {e}")
                return {"error": "Coverage JSON parsing failed"}

        return {"error": "Coverage data not found. Run 'coverage run' first."}

    def _run_semgrep(self, scope: str) -> Dict:
        """
        Запускает semgrep SAST

        Args:
            scope: путь для анализа

        Returns:
            Словарь с найденными паттернами
        """
        cmd = [
            "semgrep",
            "--config=auto",
            "--json",
            scope
        ]

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=self.project_root,
            timeout=self.timeout
        )

        try:
            data = json.loads(result.stdout)

            findings = []
            for finding in data.get("results", []):
                findings.append({
                    "severity": finding.get("extra", {}).get("severity", "INFO"),
                    "file": f"{Path(finding['path']).name}:{finding['start']['line']}",
                    "rule": finding["check_id"],
                    "msg": finding.get("extra", {}).get("message", "")[:60]
                })

            return {
                "findings": findings,
                "count": len(findings)
            }
        except json.JSONDecodeError as e:
            logger.error(f"Semgrep parsing failed: {e}")
            return {"findings": [], "count": 0}

    def _aggregate_results(self, req_type: RequestType, results: Dict, scope: str) -> Dict:
        """
        Агрегирует результаты всех инструментов в компактный отчет

        Args:
            req_type: тип запроса
            results: результаты всех инструментов
            scope: область анализа

        Returns:
            Компактный отчет (150-500 токенов)
        """
        if req_type == RequestType.SECURITY:
            return self._aggregate_security_report(results, scope)
        elif req_type == RequestType.PERFORMANCE:
            return self._aggregate_performance_report(results, scope)
        elif req_type == RequestType.QUALITY:
            return self._aggregate_quality_report(results, scope)
        elif req_type == RequestType.COVERAGE:
            return self._aggregate_coverage_report(results, scope)

        # Generic aggregation
        return {
            "type": req_type.value,
            "scope": scope,
            "results": results
        }

    def _aggregate_security_report(self, results: Dict, scope: str) -> Dict:
        """
        Агрегирует security отчет (150-300 токенов)

        Args:
            results: результаты инструментов
            scope: область анализа

        Returns:
            Компактный security отчет
        """
        bandit_results = results.get("bandit", {})
        safety_results = results.get("safety", {})
        semgrep_results = results.get("semgrep", {})

        return {
            "type": "security",
            "scope": scope,
            "code_issues": bandit_results.get("issues", [])[:10],  # топ 10
            "dependency_vulns": safety_results.get("vulnerabilities", [])[:5],
            "sast_findings": semgrep_results.get("findings", [])[:5],
            "stats": bandit_results.get("stats", {}),
            "score": self._calculate_security_score(bandit_results, safety_results)
        }

    def _aggregate_quality_report(self, results: Dict, scope: str) -> Dict:
        """
        Агрегирует quality отчет (250-500 токенов)

        Args:
            results: результаты инструментов
            scope: область анализа

        Returns:
            Компактный quality отчет
        """
        radon_results = results.get("radon", {})
        pylint_results = results.get("pylint", {})

        return {
            "type": "quality",
            "scope": scope,
            "complexity": {
                "high": radon_results.get("complex_functions", [])[:5]
            },
            "maintainability": radon_results.get("low_maintainability", [])[:5],
            "violations": {
                "errors": pylint_results.get("issues", {}).get("error", [])[:5],
                "warnings": pylint_results.get("issues", {}).get("warning", [])[:3]
            },
            "score": {
                "pylint": pylint_results.get("score", 0),
                "maintainability": self._calc_avg_mi(radon_results)
            }
        }

    def _aggregate_performance_report(self, results: Dict, scope: str) -> Dict:
        """
        Агрегирует performance отчет

        Args:
            results: результаты инструментов
            scope: область анализа

        Returns:
            Компактный performance отчет
        """
        radon_results = results.get("radon", {})

        return {
            "type": "performance",
            "scope": scope,
            "complexity_hotspots": radon_results.get("complex_functions", [])[:5],
            "recommendations": [
                "Reduce cyclomatic complexity in identified functions",
                "Consider caching expensive operations",
                "Profile runtime with py-spy or cProfile"
            ]
        }

    def _aggregate_coverage_report(self, results: Dict, scope: str) -> Dict:
        """
        Агрегирует coverage отчет

        Args:
            results: результаты инструментов
            scope: область анализа

        Returns:
            Компактный coverage отчет
        """
        coverage_results = results.get("coverage", {})

        return {
            "type": "coverage",
            "scope": scope,
            "overall": coverage_results.get("overall", "N/A"),
            "gaps": coverage_results.get("critical_gaps", []),
            "recommendations": [
                "Focus on CRITICAL priority files first",
                "Add unit tests for uncovered code paths",
                "Review integration test coverage"
            ]
        }

    def _suggest_fix(self, rule_id: str) -> str:
        """
        Предлагает фикс для security issue

        Args:
            rule_id: идентификатор правила bandit

        Returns:
            Краткая рекомендация по исправлению
        """
        FIXES = {
            "B201": "use env vars",
            "B105": "use secrets module",
            "B324": "upgrade to SHA256+",
            "B501": "validate SSL certificates",
            "B601": "parameterize queries",
            "B602": "disable shell=True",
            "B608": "validate SQL input",
            "B703": "use hmac.compare_digest"
        }
        return FIXES.get(rule_id, "review code")

    def _group_line_ranges(self, lines: List[int]) -> List[str]:
        """
        Группирует линии в диапазоны

        Args:
            lines: список номеров строк

        Returns:
            Список строк вида "10-15", "20-25"
        """
        if not lines:
            return []

        lines = sorted(lines)
        ranges = []
        start = lines[0]
        end = lines[0]

        for line in lines[1:]:
            if line == end + 1:
                end = line
            else:
                ranges.append(f"{start}-{end}" if start != end else str(start))
                start = end = line

        ranges.append(f"{start}-{end}" if start != end else str(start))
        return ranges

    def _determine_priority(self, file_path: str, coverage: float) -> str:
        """
        Определяет приоритет для coverage gap

        Args:
            file_path: путь к файлу
            coverage: процент покрытия

        Returns:
            Приоритет: CRITICAL, HIGH, MEDIUM, LOW
        """
        # Критичные файлы
        critical_patterns = ["auth", "payment", "security", "admin", "login", "crypto"]

        file_lower = file_path.lower()
        is_critical = any(pattern in file_lower for pattern in critical_patterns)

        if is_critical:
            if coverage < 50:
                return "CRITICAL"
            elif coverage < 70:
                return "HIGH"

        if coverage < 60:
            return "MEDIUM"

        return "LOW"

    def _calculate_security_score(self, bandit_results: Dict, safety_results: Dict) -> float:
        """
        Вычисляет общий security score (0-10)

        Args:
            bandit_results: результаты bandit
            safety_results: результаты safety

        Returns:
            Оценка безопасности от 0 до 10
        """
        stats = bandit_results.get("stats", {})
        high = stats.get("high", 0)
        medium = stats.get("medium", 0)
        cves = safety_results.get("count", 0)

        # Формула: 10 - (high*2 + medium + cves*1.5)
        deductions = high * 2 + medium + cves * 1.5
        score = max(0.0, 10.0 - deductions)

        return round(score, 1)

    def _calc_avg_mi(self, radon_results: Dict) -> str:
        """
        Вычисляет средний maintainability index

        Args:
            radon_results: результаты radon

        Returns:
            Ранг: A, B, C, D, F
        """
        files = radon_results.get("low_maintainability", [])
        if not files:
            return "A"

        avg_mi = sum(f["mi"] for f in files) / len(files)

        if avg_mi >= 85:
            return "A"
        elif avg_mi >= 65:
            return "B"
        elif avg_mi >= 50:
            return "C"
        elif avg_mi >= 25:
            return "D"
        else:
            return "F"

    def _save_detailed_results(self, results: Dict):
        """
        Сохраняет детальные результаты для человека

        Args:
            results: полные результаты всех инструментов
        """
        try:
            output_file = self.results_dir / "detailed_analysis.json"
            with open(output_file, "w", encoding="utf-8") as f:
                json.dump(results, f, indent=2, ensure_ascii=False)
            logger.info(f"Detailed results saved to {output_file}")
        except Exception as e:
            logger.error(f"Failed to save detailed results: {e}")


# Пример использования
if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)

    orchestrator = ToolOrchestrator(
        project_root=Path.cwd(),
        timeout=300
    )

    # Пример классификации запроса
    classification = {
        "primary_type": "security",
        "tools": ["bandit", "safety"],
        "scope": "src"
    }

    report = orchestrator.run_analysis(classification)
    print(json.dumps(report, indent=2))
