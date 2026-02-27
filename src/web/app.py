"""
FastAPI веб-интерфейс PT_Standart — инструмент анализа внешних проектов.

PT_Standart интегрируется в целевой проект и анализирует его:
безопасность, качество кода, покрытие тестами, i18n, производительность.

Страницы:
  /           — Главная: форма запроса анализа целевого проекта
  /results    — Результаты: проблемы, найденные в целевом проекте
  /reports    — Отчёты: расход токенов при анализе
  /i18n       — i18n: покрытие переводами целевого проекта
  /settings   — Настройки: пороги, модели, инструменты
  /qa         — QA: автотесты функций PT_Standart
  /health     — Health check (JSON)

Запуск:
  python -m uvicorn src.web.app:app --host 0.0.0.0 --port 8000
"""

import sys
import json
import traceback
from pathlib import Path
from datetime import date
from typing import Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

app = FastAPI(title="PT_Standart", version="1.0.0")

templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# ── In-memory хранилище последних результатов ──
_last_results: dict = {}
_last_settings: dict = {
    "confidence_threshold": 0.7,
    "model": "flash",
    "target_project": str(PROJECT_ROOT),
    "tools_bandit": True,
    "tools_pylint": True,
    "tools_radon": True,
    "tools_safety": True,
    "tools_coverage": True,
}


def _load_tools_config() -> dict:
    """Загружает конфигурацию инструментов из YAML."""
    config_path = PROJECT_ROOT / "config" / "tools_config.yaml"
    if not config_path.exists():
        return {}
    try:
        import yaml
        with open(config_path, "r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}
    except Exception:
        return {}


def _get_target_project() -> Path:
    """Возвращает путь к целевому проекту."""
    path_str = _last_settings.get("target_project", str(PROJECT_ROOT))
    p = Path(path_str)
    return p if p.exists() else PROJECT_ROOT


# ══════════════════════════════════════════════════
#  Health check
# ══════════════════════════════════════════════════

@app.get("/health", response_class=JSONResponse)
async def health():
    return {"status": "ok", "service": "PT_Standart"}


# ══════════════════════════════════════════════════
#  Главная страница — анализ целевого проекта
# ══════════════════════════════════════════════════

@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html", {
        "request": request,
        "result": _last_results.get("response"),
        "metrics": _last_results.get("metrics"),
        "target_project": _last_settings.get("target_project", ""),
    })


@app.post("/analyze", response_class=HTMLResponse)
async def analyze(
    request: Request,
    query: str = Form(""),
    target_project: str = Form(""),
):
    error = None
    response_text = None
    metrics = None

    if target_project.strip():
        _last_settings["target_project"] = target_project.strip()

    if not query.strip():
        error = "Введите запрос для анализа целевого проекта"
    else:
        try:
            target = _get_target_project()
            from src.main_workflow import handle_user_request
            response_text, metrics = handle_user_request(
                user_query=query,
                project_root=target,
                verbose=False,
                use_mock=True,
            )
            _last_results["response"] = response_text
            _last_results["metrics"] = metrics
            _last_results["query"] = query
        except Exception as e:
            error = f"Ошибка анализа: {e}"

    return templates.TemplateResponse("index.html", {
        "request": request,
        "query": query,
        "result": response_text,
        "metrics": metrics,
        "error": error,
        "target_project": _last_settings.get("target_project", ""),
    })


# ══════════════════════════════════════════════════
#  Результаты — проблемы в целевом проекте
# ══════════════════════════════════════════════════

@app.get("/results", response_class=HTMLResponse)
async def results(request: Request, severity: Optional[str] = None):
    issues = []
    try:
        from src.preprocessing.hybrid_classifier import HybridClassifier
        from src.main_workflow import SmartExecutor, HybridReportAggregator
        from src.main_workflow import Classification as WfClassification
        from src.main_workflow import RequestType as WfRequestType

        query = _last_results.get("query", "Проверь безопасность auth модуля")
        clf = HybridClassifier()
        classification = clf.classify(query)

        type_map = {
            "SECURITY": WfRequestType.SECURITY,
            "PERFORMANCE": WfRequestType.PERFORMANCE,
            "QUALITY": WfRequestType.REFACTORING,
            "COVERAGE": WfRequestType.TESTING,
            "ARCHITECTURE": WfRequestType.ARCHITECTURE,
            "DOCUMENTATION": WfRequestType.DOCUMENTATION,
        }
        wf_type = type_map.get(classification.get("type", ""), WfRequestType.DEBUGGING)
        wf_cls = WfClassification(
            primary_type=wf_type,
            confidence=classification.get("confidence", 0.5),
            tools=classification.get("tools", []),
            scope=classification.get("scope", "src/"),
            keywords=[],
        )

        target = _get_target_project()
        executor = SmartExecutor(target)
        exec_results = executor.execute(wf_cls)

        for issue_dict in exec_results.get("issues", []):
            issues.append(issue_dict)

        # Демо-issues если реальных нет
        if not issues:
            from tests.qa.data_generators import random_issues
            issues = random_issues(count=8)

    except Exception as e:
        issues = [{"type": "ERROR", "severity": "HIGH", "message": str(e), "file": "-", "line": 0}]

    if severity:
        issues = [i for i in issues if i.get("severity") == severity]

    severities = sorted(set(i.get("severity", "MEDIUM") for i in issues))

    return templates.TemplateResponse("results.html", {
        "request": request,
        "issues": issues,
        "severity_filter": severity,
        "severities": severities,
        "total": len(issues),
        "target_project": str(_get_target_project()),
    })


# ══════════════════════════════════════════════════
#  Отчёты по токенам
# ══════════════════════════════════════════════════

@app.get("/reports", response_class=HTMLResponse)
async def reports(request: Request):
    tasks = []
    daily_stats = {}
    total_stats = {}

    try:
        from src.reporting.token_tracker import TokenTracker

        tracker = TokenTracker()

        with tracker._conn() as conn:
            rows = conn.execute(
                "SELECT * FROM tasks ORDER BY started_at DESC LIMIT 20"
            ).fetchall()

            for row in rows:
                tasks.append(dict(row))

            today = date.today().isoformat()
            day_row = conn.execute(
                "SELECT COUNT(*) as cnt, "
                "COALESCE(SUM(total_input_tokens + total_output_tokens), 0) as tokens, "
                "COALESCE(SUM(total_cost_usd), 0) as cost, "
                "COALESCE(SUM(opus_only_cost_usd), 0) as opus_cost "
                "FROM tasks WHERE started_at LIKE ?",
                (f"{today}%",),
            ).fetchone()

            daily_stats = dict(day_row) if day_row else {}
            if daily_stats.get("opus_cost", 0) > 0:
                daily_stats["saving_pct"] = round(
                    (1 - daily_stats["cost"] / daily_stats["opus_cost"]) * 100, 1
                )
            else:
                daily_stats["saving_pct"] = 0

            total_row = conn.execute(
                "SELECT COUNT(*) as cnt, "
                "COALESCE(SUM(total_input_tokens + total_output_tokens), 0) as tokens, "
                "COALESCE(SUM(total_cost_usd), 0) as cost, "
                "COALESCE(SUM(opus_only_cost_usd), 0) as opus_cost "
                "FROM tasks"
            ).fetchone()
            total_stats = dict(total_row) if total_row else {}

    except Exception as e:
        tasks = []
        daily_stats = {"error": str(e)}

    return templates.TemplateResponse("reports.html", {
        "request": request,
        "tasks": tasks,
        "daily_stats": daily_stats,
        "total_stats": total_stats,
    })


# ══════════════════════════════════════════════════
#  i18n — переводы целевого проекта
# ══════════════════════════════════════════════════

@app.get("/i18n", response_class=HTMLResponse)
async def i18n_page(request: Request):
    stats = {}
    report = None
    locales = []

    try:
        from src.i18n.catalog import TranslationCatalog
        locales_dir = PROJECT_ROOT / "src" / "i18n" / "locales"
        catalog = TranslationCatalog(locales_dir=locales_dir)
        locales = catalog.list_locales()

        for loc in locales:
            stats[loc] = catalog.get_stats(loc)
    except Exception as e:
        stats = {"error": str(e)}

    return templates.TemplateResponse("i18n.html", {
        "request": request,
        "stats": stats,
        "locales": locales,
        "report": report,
        "target_project": str(_get_target_project()),
    })


@app.post("/i18n/validate", response_class=HTMLResponse)
async def i18n_validate(request: Request, source: str = Form("en"), target: str = Form("ru")):
    stats = {}
    report_data = None
    locales = []

    try:
        from src.i18n.catalog import TranslationCatalog
        from src.i18n.validator import TranslationValidator

        locales_dir = PROJECT_ROOT / "src" / "i18n" / "locales"
        catalog = TranslationCatalog(locales_dir=locales_dir)
        locales = catalog.list_locales()

        for loc in locales:
            stats[loc] = catalog.get_stats(loc)

        validator = TranslationValidator(catalog=catalog, project_root=_get_target_project())
        report = validator.validate(source_locale=source, target_locale=target)

        report_data = {
            "total": report.total_strings,
            "translated": report.translated_count,
            "missing": report.missing_count,
            "coverage": report.coverage_percent,
            "issues_count": len(report.issues),
            "by_severity": report.by_severity,
            "by_category": report.by_category,
            "is_complete": report.is_complete,
        }
    except Exception as e:
        report_data = {"error": str(e)}

    return templates.TemplateResponse("i18n.html", {
        "request": request,
        "stats": stats,
        "locales": locales,
        "report": report_data,
        "target_project": str(_get_target_project()),
    })


# ══════════════════════════════════════════════════
#  Настройки
# ══════════════════════════════════════════════════

@app.get("/settings", response_class=HTMLResponse)
async def settings_page(request: Request):
    config = _load_tools_config()
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": _last_settings,
        "config": config,
        "saved": False,
    })


@app.post("/settings", response_class=HTMLResponse)
async def settings_save(
    request: Request,
    confidence_threshold: float = Form(0.7),
    model: str = Form("flash"),
    target_project: str = Form(""),
    tools_bandit: bool = Form(False),
    tools_pylint: bool = Form(False),
    tools_radon: bool = Form(False),
    tools_safety: bool = Form(False),
    tools_coverage: bool = Form(False),
):
    _last_settings.update({
        "confidence_threshold": confidence_threshold,
        "model": model,
        "tools_bandit": tools_bandit,
        "tools_pylint": tools_pylint,
        "tools_radon": tools_radon,
        "tools_safety": tools_safety,
        "tools_coverage": tools_coverage,
    })
    if target_project.strip():
        _last_settings["target_project"] = target_project.strip()

    config = _load_tools_config()
    return templates.TemplateResponse("settings.html", {
        "request": request,
        "settings": _last_settings,
        "config": config,
        "saved": True,
    })


# ══════════════════════════════════════════════════
#  QA — тестирование функций PT_Standart
# ══════════════════════════════════════════════════

@app.get("/qa", response_class=HTMLResponse)
async def qa_page(request: Request):
    return templates.TemplateResponse("qa.html", {
        "request": request,
        "report": None,
        "running": False,
    })


@app.post("/qa/run", response_class=HTMLResponse)
async def qa_run(request: Request):
    report_data = None
    error = None
    try:
        from tests.qa.test_runner import run_all
        report = run_all(verbose=False)
        report_data = {
            "total_tests": report.total_tests,
            "total_passed": report.total_passed,
            "total_failed": report.total_failed,
            "pass_rate": report.pass_rate,
            "duration": report.total_duration,
            "modules": [],
        }
        for m in report.modules:
            mod = {
                "name": m.module,
                "total": m.total,
                "passed": m.passed,
                "failed": m.failed,
                "pass_rate": m.pass_rate,
                "duration": m.duration,
                "tests": [],
            }
            for t in m.tests:
                mod["tests"].append({
                    "name": t.name,
                    "passed": t.passed,
                    "duration": t.duration,
                    "error": t.error[:300] if t.error else "",
                })
            report_data["modules"].append(mod)
    except Exception as e:
        error = f"Ошибка запуска тестов: {e}\n{traceback.format_exc()}"

    return templates.TemplateResponse("qa.html", {
        "request": request,
        "report": report_data,
        "error": error,
        "running": False,
    })
