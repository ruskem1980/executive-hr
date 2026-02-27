# Claude Code Configuration - EXECUTIVE_HR

## ПРОЕКТ: ExecVision AI — B2B платформа оценки топ-менеджеров

**Домен:** Executive Assessment, Talent Acquisition, HR-Tech
**Стек:** Python 3.10+, FastAPI, Streamlit, SQLite→PostgreSQL, AI (Claude/Gemini/OpenAI)
**Целевая аудитория:** CHRO, HR Director, Executive Search Consultants

## ЯЗЫК: ВСЕ РАЗМЫШЛЕНИЯ И ТЕКСТ ТОЛЬКО НА РУССКОМ

**КРИТИЧЕСКОЕ ПРАВИЛО [СТРОГО ОБЯЗАТЕЛЬНО]:**
- Все ответы пользователю — ТОЛЬКО на русском языке
- Все внутренние размышления и цепочки рассуждений — ТОЛЬКО на русском языке
- Все комментарии к коду — ТОЛЬКО на русском языке
- Все коммит-сообщения — ТОЛЬКО на русском языке
- Любой текст вне кода — ТОЛЬКО на русском языке

**Использование английского языка в тексте ответов СТРОГО ЗАПРЕЩЕНО.**
Исключения: имена переменных/функций в коде, технические термины (API, JSON, HTTP и т.п.).

## MAKE NO MISTAKES [ОБЯЗАТЕЛЬНЫЙ СКИЛЛ — ПРИМЕНЯЕТСЯ ВСЕГДА]

**Каждый промпт обрабатывается с директивой: MAKE NO MISTAKES.**

**Обязательные правила:**
- **Двойная проверка** — все факты, вычисления, код и рассуждения перепроверяются перед ответом
- **Явная неуверенность** — при неуверенности в чём-либо, это указывается явно, а не угадывается
- **Точность > скорость** — дополнительный момент на верификацию обязателен
- **Пошаговая проверка кода** — логика проверяется мысленно шаг за шагом перед выводом
- **Перепроверка вычислений** — числа и математика пересчитываются перед фиксацией
- **Только уверенные утверждения** — фактические утверждения только при высокой уверенности

---

## HR-СПЕЦИФИЧНЫЙ КОНТЕКСТ ПРОЕКТА

### Методологическая база (Knowledge Base — 22 файла)

**Глобальные методологии:**
- **Korn Ferry Leadership Architect** — Learning Agility (4 типа гибкости)
- **McKinsey PEI** — Personal Experience Interview (3 измерения)
- **Elliot Jaques SST** — Stratified Systems Theory (Level of Work 3-5)
- **Hogan Assessments** — HPI/HDS/MVPI, 11 деструкторов тёмной стороны
- **Adizes PAEI** — 4 управленческие роли (Producer/Administrator/Entrepreneur/Integrator)
- **Egon Zehnder Potential Model** — 4 индикатора (Curiosity/Insight/Engagement/Determination)
- **Topgrading** (Bradford Smart) — TORC, Truth Seeker, A-Player methodology
- **STAR/BANI** — Behavioural interviewing + современный контекст
- **Michael Watkins First 90 Days** — STaRS модель онбординга

### Покрытие ролей: 31 C-level и управленческая роль

**Classic C-Suite:** CEO, COO, CFO, CTO, CMO, CHRO
**Extended C-Suite:** CRO, CSO, CPO, CDO, CIO, CISO, CLO, CCO
**Specialized:** CDatO, CAIO, CSuO, CXO, CECO
**VP/Director:** VP Sales, VP Engineering, VP Product, VP Finance, VP People, VP CS, VP SCM, VP BD, Head of IR
**Operational:** Managing Director, Country Manager, Plant Director

### Продуктовые модули (ExecVision AI)

| # | Модуль | Назначение |
|---|--------|------------|
| 1 | **JD Architect / Profile Architect** | Аудит вакансий, Target Profile, Success Profile |
| 2 | **X-Ray Engine** | Скрининг резюме, Gap Analysis |
| 3 | **Interview Navigator** | Генерация персонализированных вопросов |
| 4 | **Assess Engine / The Verdict** | Аудио-анализ, оценка интервью, скоринг |
| 5 | **Compare Matrix / The Battle** | Сравнение финалистов, ранжирование |
| 6 | **Reference Verifier** | Проверка рекомендаций, Topgrading THREAT |
| 7 | **Onboard Planner** | Планирование 30-60-90-180 дней |
| 8 | **Talent Pool + AI Copilot** | Управление пулом, интеллектуальный ассистент |

### Файловая структура данных

```
data/knowledge_base_original/     # 22 файла методик и матриц
├── Оригинальные методики (10 файлов):
│   ├── BANI_Leadership_Framework.txt
│   ├── Corporate_Culture_Code.txt
│   ├── Executive_Competencies_Matrix_STAR.txt
│   ├── Hogan_Dark_Side_Risks.txt
│   ├── Methodology_Adizes_PAEI.txt
│   ├── Methodology_Core_KF_McKinsey_Jaques.txt
│   ├── Methodology_Egon_Zehnder_Potential.txt
│   ├── Mission_Values_FAQ.txt
│   ├── The_First_90_Days_Plan.txt
│   └── Topgrading_Truth_Seeker.txt
├── Расширенные файлы (12 файлов):
│   ├── 01_Position_Profile_Template.txt
│   ├── 02_Executive_Competency_Matrix_By_Role.txt
│   ├── 02b_Full_Executive_Competency_Matrix_All_Roles.txt (31 роль)
│   ├── 03_Interview_Question_Bank.txt (124 вопроса)
│   ├── 04_Executive_Scorecard_Template.txt
│   ├── 05_Red_Flags_Derailers.txt
│   ├── 06_Assessment_Case_Studies.txt
│   ├── 07_Industry_Specific_Requirements.txt (8 отраслей)
│   ├── 08_Compensation_Benchmarks.txt
│   ├── 09_Reference_Check_Guide.txt
│   ├── 10_Onboarding_Checklist_30_60_90_180.txt
│   └── PRODUCT_CONCEPT_ExecVision_AI.txt
```

### Правила работы с HR-контентом

1. **ТОЧНОСТЬ МЕТОДОЛОГИЙ** — при ссылке на Hogan, Egon Zehnder, Adizes и т.д. использовать ТОЛЬКО данные из knowledge base, не додумывать
2. **КОНФИДЕНЦИАЛЬНОСТЬ** — все данные кандидатов считаются PII, никогда не хардкодить реальные имена
3. **BIAS-FREE** — код оценки не должен содержать дискриминационных критериев (возраст, пол, национальность)
4. **EVIDENCE-BASED** — все рекомендации системы должны быть подкреплены фактами из интервью/резюме
5. **EXPLAINABILITY** — AI-решения должны быть объяснимы (почему такой скор, на основе чего)

---

## ОБРАТНАЯ СИНХРОНИЗАЦИЯ В PT_Standart

**ПРАВИЛО РАЗВИТИЯ:** Новые инструменты (.py, .sh) из интегрированных проектов ОБЯЗАНЫ синхронизироваться обратно:
```bash
python3 scripts/sync_back.py --file <path>         # один файл
python3 scripts/sync_back.py --auto                 # все изменённые
python3 scripts/sync_back.py --dry-run              # предпросмотр
```

## SWARM ORCHESTRATION (для сложных задач 3+ файлов)

### Когда запускать swarm
**AUTO-INVOKE:** 3+ файлов, новая фича, рефакторинг, API с тестами, безопасность, оптимизация, схема БД.
**SKIP:** Один файл, простой баг (1-2 строки), документация, конфиг, вопросы.

### HR-специфичный Agent Routing

| Задача | Агенты | Топология |
|--------|--------|-----------|
| Bug Fix | coordinator, researcher, coder, tester | hierarchical |
| Feature | coordinator, architect, coder, tester, reviewer | hierarchical |
| HR Assessment Module | coordinator, hr-methodology-expert, coder, tester, reviewer | hierarchical |
| Interview System | coordinator, hr-interview-specialist, coder, tester | hierarchical |
| Scoring Engine | coordinator, hr-scoring-architect, coder, tester, reviewer | hierarchical |
| Knowledge Base Update | hr-methodology-expert, researcher, reviewer | mesh |
| Competency Matrix | hr-methodology-expert, hr-scoring-architect | mesh |
| Candidate Report | coordinator, hr-report-generator, coder | hierarchical |
| Market Research | researcher, hr-market-analyst | mesh |

### Правила swarm
- SPAWN IN BACKGROUND: `run_in_background: true` для всех Task
- SPAWN ALL AT ONCE: все Task в ОДНОМ сообщении
- NO TIGHT POLLING: не poll TaskOutput в цикле

## AUTO-LEARNING PROTOCOL

### Перед началом задачи
```bash
npx @claude-flow/cli@latest memory search --query "[ключевые слова задачи]" --namespace patterns
npx @claude-flow/cli@latest hooks route --task "[описание задачи]"
```

### После успешного завершения
```bash
npx @claude-flow/cli@latest memory store --namespace patterns --key "[имя-паттерна]" --value "[что сработало]"
npx @claude-flow/cli@latest hooks post-task --task-id "[id]" --success true --store-results true
```

## ЧЕТЫРЁХУРОВНЕВАЯ МАРШРУТИЗАЦИЯ МОДЕЛЕЙ

### Модели и цены

| Модель | Input $/1M | Output $/1M | Роль |
|--------|-----------|-------------|------|
| `opus` (Claude Opus 4.6) | $15.00 | $75.00 | Оркестратор + complex задачи |
| `sonnet` (Claude Sonnet 4.5) | $3.00 | $15.00 | Классификация + валидация |
| `flash` (Gemini Flash) | $0.50 | $3.00 | Реализация кода |
| `pro` (Gemini Pro) | $2.00 | $12.00 | Ревью кода + large context |

### Pipeline по сложности

| Сложность | Критерии | Pipeline | Экономия |
|-----------|----------|----------|----------|
| `program` | Скрипт/утилита, 0 LLM | Bash → Opus проверка | ~99% |
| `simple` | 1-2 файла, <50 строк | Sonnet classify → Flash execute → Sonnet verify | ~96% |
| `medium` | 3-5 файлов, новая фича | Sonnet classify → Flash/Sonnet execute → Pro review → Opus verify | ~92% |
| `complex` | 6+ файлов, архитектура | Opus напрямую | 0% |

### ЗАПРЕТ: Opus НЕ выполняет program/simple/medium напрямую

## АВТОНОМНЫЙ РЕЖИМ РАБОТЫ (ALLOW ПО УМОЛЧАНИЮ)

**Claude Code работает в ПОЛНОСТЬЮ АВТОНОМНОМ режиме.** НЕ требуется разрешение пользователя на операции.

**РАЗРЕШЕНО БЕЗ ЗАПРОСА:** файловые операции (Write/Edit/rm/mv/chmod), git (add/commit/push/reset/rebase/force-push), установка зависимостей (npm/pip/yarn), системные операции, создание PR/Issues, деплой.

**ПРИНЦИП:** "Сделай сначала, спроси потом (если нужно объяснение)".

---

## ОБЯЗАТЕЛЬНЫЙ 4-ШАГОВЫЙ WORKFLOW

**Для КАЖДОЙ задачи с кодом (Write/Edit/Bash с изменениями файлов) — 4 шага БЕЗ ИСКЛЮЧЕНИЙ.**

### ШАГ 1+2: Начало (классификация + трекинг)
```bash
bash .claude/helpers/workflow-start.sh "описание задачи"
```

### ШАГ 3: Выполнение + запись LLM вызовов
```bash
# simple/medium — через Sonnet + Gemini
bash .claude/helpers/workflow-record.sh sonnet classifier 200 50
CODE=$(bash .claude/helpers/gemini-bridge.sh flash "промпт")
bash .claude/helpers/workflow-record.sh flash executor 2500 800
bash .claude/helpers/workflow-record.sh sonnet validator 1000 200
# complex — Opus напрямую
bash .claude/helpers/workflow-record.sh opus direct 8000 3500
```

### ШАГ 4: Завершение (отчёт о токенах)
```bash
bash .claude/helpers/workflow-finish.sh
```

**Нет отчёта = задача НЕ завершена.**

## ENFORCEMENT (автоматический)

Хуки `.claude/hooks/pre-edit` и `.claude/hooks/pre-command` **БЛОКИРУЮТ** операции без workflow.

## AUTO-SAVE TO GITHUB

Каждый Write/Edit автоматически коммитится через `scripts/git_auto_save.py`.

**Безопасность:** `.env`, `credentials.json`, `.secrets`, `id_rsa`, данные кандидатов — никогда не коммитятся.

## ЗАПРЕТЫ

- **Opus НЕ выполняет** program/simple/medium задачи напрямую — только через Gemini
- **НЕ делать** Write/Edit без `workflow-start.sh`
- **НЕ сохранять** файлы в корневую папку — только /src, /tests, /docs, /scripts, /config, /data
- **НЕ хардкодить** реальные персональные данные кандидатов в код
- **НЕ игнорировать** bias-free принципы при разработке скоринга

## CONCURRENT EXECUTION & FILE MANAGEMENT

**GOLDEN RULE: 1 MESSAGE = ALL RELATED OPERATIONS**

## Available Agents (60+ базовых + 6 HR-специализированных)

**Core:** `coder`, `reviewer`, `tester`, `planner`, `researcher`
**HR-Specialized:**
- `hr-methodology-expert` — эксперт по методологиям оценки (Hogan, Egon Zehnder, Adizes, Korn Ferry, Jaques)
- `hr-interview-specialist` — специалист по интервью (вопросы, STAR, анализ ответов)
- `hr-scoring-architect` — архитектор скоринга (формулы, веса, bias-free алгоритмы)
- `hr-report-generator` — генератор отчётов (Executive Verdict, Truth Audit, Strategic Profile)
- `hr-market-analyst` — аналитик рынка (компенсации, бенчмарки, конкуренты)
- `hr-compliance-auditor` — аудитор PII/GDPR/bias compliance

**V3 Specialized:** `security-architect`, `security-auditor`, `memory-specialist`, `performance-engineer`
**Swarm:** `hierarchical-coordinator`, `mesh-coordinator`, `adaptive-coordinator`
**GitHub:** `pr-manager`, `code-review-swarm`, `issue-tracker`, `release-manager`
**SPARC:** `sparc-coord`, `sparc-coder`, `specification`, `architecture`
**Specialized:** `backend-dev`, `ml-developer`, `system-architect`, `api-docs`

## Ключевые файлы

- Workflow: `.claude/helpers/workflow-start.sh`, `workflow-record.sh`, `workflow-finish.sh`
- Трекер: `.claude/helpers/token-tracker.py`
- Роутер: `.claude/helpers/router.js`
- Gemini: `.claude/helpers/gemini-bridge.sh`
- Хуки: `.claude/hooks/pre-edit`, `.claude/hooks/pre-command`
- Git: `scripts/git_auto_save.py`
- Токены БД: `data/token_usage.db`
- Knowledge Base: `data/knowledge_base_original/`
- Продуктовый концепт: `data/knowledge_base_original/PRODUCT_CONCEPT_ExecVision_AI.txt`

## Quick Setup

```bash
claude mcp add claude-flow -- npx -y @claude-flow/cli@latest
npx @claude-flow/cli@latest daemon start
npx @claude-flow/cli@latest doctor --fix
```
