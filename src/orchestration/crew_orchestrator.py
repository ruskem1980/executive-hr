"""
Оркестратор мульти-агентных workflows в стиле CrewAI.

Управляет созданием crew (команд агентов) и выполнением задач
в трёх топологиях: sequential, parallel, hierarchical.

Если библиотека crewai установлена -- оборачивает её API.
Если нет -- предоставляет собственную реализацию с тем же интерфейсом.

Готовые шаблоны:
- bug_fix: researcher -> coder -> tester
- feature: researcher -> architect -> coder -> tester -> reviewer
- refactor: architect -> coder -> reviewer
- security: security-architect -> security-auditor -> coder -> tester
- docs: researcher -> coder
"""

import time
import uuid
import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, List, Dict, Any

logger = logging.getLogger(__name__)


# ── Dataclasses ──

@dataclass
class Agent:
    """Агент в составе crew."""

    role: str                       # Роль: coder, tester, reviewer и т.д.
    goal: str                       # Цель агента
    backstory: str = ''             # Контекст/бэкграунд агента
    tools: List[str] = field(default_factory=list)   # Доступные инструменты
    model: str = 'flash'            # Модель LLM для агента


@dataclass
class Task:
    """Задача для выполнения агентом внутри crew."""

    description: str                # Описание задачи
    agent_role: str                 # Роль агента, выполняющего задачу
    expected_output: str = ''       # Ожидаемый формат результата
    dependencies: List[str] = field(default_factory=list)  # Зависимости (описания предыдущих задач)
    status: str = 'pending'         # pending / in_progress / completed / failed
    result: Optional[str] = None    # Результат выполнения


@dataclass
class Crew:
    """Команда агентов с набором задач."""

    name: str                       # Название crew
    agents: List[Agent]             # Агенты в составе
    tasks: List[Task]               # Задачи для выполнения
    topology: str = 'sequential'    # sequential / parallel / hierarchical
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


@dataclass
class CrewResult:
    """Результат выполнения crew."""

    crew_name: str                  # Название crew
    tasks_results: List[Dict[str, Any]]  # Результаты задач
    total_time_ms: float            # Общее время выполнения в мс
    success: bool                   # Успешно ли выполнены все задачи
    errors: List[str]               # Список ошибок (если есть)


# ── Шаблоны crew ──

_TEMPLATES: Dict[str, Dict[str, Any]] = {
    'bug_fix': {
        'name': 'Bug Fix Crew',
        'topology': 'sequential',
        'agents': [
            Agent(
                role='researcher',
                goal='Исследовать баг: воспроизвести, найти root cause',
                backstory='Опытный аналитик, умеет находить причины ошибок',
                tools=['grep', 'read', 'git_log'],
                model='flash',
            ),
            Agent(
                role='coder',
                goal='Исправить баг на основе анализа исследователя',
                backstory='Разработчик, пишет чистый и надёжный код',
                tools=['read', 'write', 'edit'],
                model='flash',
            ),
            Agent(
                role='tester',
                goal='Написать тесты, подтверждающие исправление бага',
                backstory='QA инженер, находит edge cases',
                tools=['read', 'write', 'bash'],
                model='flash',
            ),
        ],
        'tasks': [
            Task(
                description='Исследовать и воспроизвести баг, определить root cause',
                agent_role='researcher',
                expected_output='Описание root cause + стек вызовов + затронутые файлы',
            ),
            Task(
                description='Исправить баг на основе анализа исследователя',
                agent_role='coder',
                expected_output='Изменённые файлы с исправлением',
                dependencies=['Исследовать и воспроизвести баг, определить root cause'],
            ),
            Task(
                description='Написать тесты для подтверждения исправления',
                agent_role='tester',
                expected_output='Тестовые файлы + результат запуска pytest',
                dependencies=['Исправить баг на основе анализа исследователя'],
            ),
        ],
    },

    'feature': {
        'name': 'Feature Development Crew',
        'topology': 'sequential',
        'agents': [
            Agent(
                role='researcher',
                goal='Исследовать требования и существующий код',
                backstory='Аналитик требований, понимает бизнес-логику',
                tools=['grep', 'read', 'glob'],
                model='flash',
            ),
            Agent(
                role='architect',
                goal='Спроектировать архитектуру новой фичи',
                backstory='Системный архитектор с опытом проектирования',
                tools=['read', 'glob'],
                model='pro',
            ),
            Agent(
                role='coder',
                goal='Реализовать фичу по спроектированной архитектуре',
                backstory='Разработчик, следующий SOLID и clean code',
                tools=['read', 'write', 'edit', 'bash'],
                model='flash',
            ),
            Agent(
                role='tester',
                goal='Написать юнит и интеграционные тесты',
                backstory='QA инженер, обеспечивает покрытие > 80%',
                tools=['read', 'write', 'bash'],
                model='flash',
            ),
            Agent(
                role='reviewer',
                goal='Провести code review: качество, безопасность, best practices',
                backstory='Senior reviewer с фокусом на maintainability',
                tools=['read', 'grep'],
                model='pro',
            ),
        ],
        'tasks': [
            Task(
                description='Исследовать требования и проанализировать существующий код',
                agent_role='researcher',
                expected_output='Список требований + анализ затронутых модулей',
            ),
            Task(
                description='Спроектировать архитектуру новой фичи',
                agent_role='architect',
                expected_output='Диаграмма компонентов + API контракты + план файлов',
                dependencies=['Исследовать требования и проанализировать существующий код'],
            ),
            Task(
                description='Реализовать фичу по архитектуре',
                agent_role='coder',
                expected_output='Реализованные файлы с кодом',
                dependencies=['Спроектировать архитектуру новой фичи'],
            ),
            Task(
                description='Написать юнит и интеграционные тесты',
                agent_role='tester',
                expected_output='Тесты + отчёт о покрытии',
                dependencies=['Реализовать фичу по архитектуре'],
            ),
            Task(
                description='Code review: качество, безопасность, best practices',
                agent_role='reviewer',
                expected_output='APPROVED или CHANGES_REQUIRED с описанием',
                dependencies=['Написать юнит и интеграционные тесты'],
            ),
        ],
    },

    'refactor': {
        'name': 'Refactoring Crew',
        'topology': 'sequential',
        'agents': [
            Agent(
                role='architect',
                goal='Проанализировать текущую архитектуру и предложить план рефакторинга',
                backstory='Архитектор со знанием паттернов проектирования',
                tools=['read', 'grep', 'glob'],
                model='pro',
            ),
            Agent(
                role='coder',
                goal='Выполнить рефакторинг по плану архитектора',
                backstory='Разработчик, следующий DRY/SOLID/KISS',
                tools=['read', 'write', 'edit', 'bash'],
                model='flash',
            ),
            Agent(
                role='reviewer',
                goal='Убедиться что рефакторинг не сломал функциональность',
                backstory='Senior reviewer, проверяет backward compatibility',
                tools=['read', 'grep', 'bash'],
                model='pro',
            ),
        ],
        'tasks': [
            Task(
                description='Анализ текущей архитектуры и план рефакторинга',
                agent_role='architect',
                expected_output='Список проблем + план рефакторинга + порядок изменений',
            ),
            Task(
                description='Выполнить рефакторинг по плану',
                agent_role='coder',
                expected_output='Изменённые файлы',
                dependencies=['Анализ текущей архитектуры и план рефакторинга'],
            ),
            Task(
                description='Проверить рефакторинг: тесты, backward compatibility',
                agent_role='reviewer',
                expected_output='APPROVED или список проблем',
                dependencies=['Выполнить рефакторинг по плану'],
            ),
        ],
    },

    'security': {
        'name': 'Security Audit Crew',
        'topology': 'sequential',
        'agents': [
            Agent(
                role='security-architect',
                goal='Определить поверхность атаки и критические компоненты',
                backstory='Архитектор безопасности с опытом threat modeling',
                tools=['read', 'grep', 'glob'],
                model='opus',
            ),
            Agent(
                role='security-auditor',
                goal='Провести аудит безопасности кода',
                backstory='Пентестер, находит OWASP Top 10 уязвимости',
                tools=['read', 'grep', 'bash'],
                model='pro',
            ),
            Agent(
                role='coder',
                goal='Исправить найденные уязвимости',
                backstory='Разработчик с опытом secure coding',
                tools=['read', 'write', 'edit'],
                model='flash',
            ),
            Agent(
                role='tester',
                goal='Написать security-тесты для проверки исправлений',
                backstory='Security QA, пишет тесты на инъекции и XSS',
                tools=['read', 'write', 'bash'],
                model='flash',
            ),
        ],
        'tasks': [
            Task(
                description='Threat modeling: определить поверхность атаки',
                agent_role='security-architect',
                expected_output='Threat model + список критических компонентов',
            ),
            Task(
                description='Аудит безопасности кода по OWASP Top 10',
                agent_role='security-auditor',
                expected_output='Список уязвимостей с severity + рекомендации',
                dependencies=['Threat modeling: определить поверхность атаки'],
            ),
            Task(
                description='Исправить найденные уязвимости',
                agent_role='coder',
                expected_output='Исправленные файлы',
                dependencies=['Аудит безопасности кода по OWASP Top 10'],
            ),
            Task(
                description='Написать security-тесты',
                agent_role='tester',
                expected_output='Тесты на инъекции, XSS, CSRF + результаты',
                dependencies=['Исправить найденные уязвимости'],
            ),
        ],
    },

    'docs': {
        'name': 'Documentation Crew',
        'topology': 'sequential',
        'agents': [
            Agent(
                role='researcher',
                goal='Проанализировать код и собрать информацию для документации',
                backstory='Технический писатель, умеет читать код',
                tools=['read', 'grep', 'glob'],
                model='flash',
            ),
            Agent(
                role='coder',
                goal='Написать/обновить документацию по результатам анализа',
                backstory='Разработчик с навыками технического письма',
                tools=['read', 'write'],
                model='flash',
            ),
        ],
        'tasks': [
            Task(
                description='Проанализировать код и собрать информацию для документации',
                agent_role='researcher',
                expected_output='Структурированный анализ: модули, API, зависимости',
            ),
            Task(
                description='Написать/обновить документацию',
                agent_role='coder',
                expected_output='Файлы документации в формате Markdown',
                dependencies=['Проанализировать код и собрать информацию для документации'],
            ),
        ],
    },
}


class CrewOrchestrator:
    """
    Оркестратор мульти-агентных workflows.

    Поддерживает три топологии выполнения:
    - sequential: задачи последовательно, результат предыдущей в контекст следующей
    - parallel: независимые задачи одновременно (помечаются для внешнего orchestrator)
    - hierarchical: координатор (первая задача) распределяет остальные

    Если crewai установлен -- оборачивает его API для нативного выполнения.
    Если нет -- собственная реализация с идентичным интерфейсом.
    """

    def __init__(self):
        """Инициализация оркестратора."""
        self._crewai_available = self._check_crewai()
        self._execution_history: List[CrewResult] = []

    @staticmethod
    def _check_crewai() -> bool:
        """Проверка доступности библиотеки crewai."""
        try:
            import crewai  # noqa: F401
            return True
        except ImportError:
            return False

    # ── Создание агентов и задач ──

    def create_agent(
        self,
        role: str,
        goal: str,
        backstory: str = '',
        tools: Optional[List[str]] = None,
        model: str = 'flash',
    ) -> Agent:
        """
        Создание агента для включения в crew.

        Args:
            role: Роль агента (coder, tester, reviewer и т.д.)
            goal: Цель агента (что должен сделать)
            backstory: Контекст/бэкграунд агента для промпта
            tools: Список доступных инструментов
            model: LLM модель для агента (flash/pro/sonnet/opus)

        Returns:
            Объект Agent.
        """
        return Agent(
            role=role,
            goal=goal,
            backstory=backstory,
            tools=tools or [],
            model=model,
        )

    def create_task(
        self,
        description: str,
        agent_role: str,
        expected_output: str = '',
        dependencies: Optional[List[str]] = None,
    ) -> Task:
        """
        Создание задачи для crew.

        Args:
            description: Описание задачи.
            agent_role: Роль агента, выполняющего задачу.
            expected_output: Ожидаемый формат результата.
            dependencies: Список описаний задач, от которых зависит эта.

        Returns:
            Объект Task.
        """
        return Task(
            description=description,
            agent_role=agent_role,
            expected_output=expected_output,
            dependencies=dependencies or [],
        )

    # ── Создание crew ──

    def create_crew(
        self,
        name: str,
        agents: List[Agent],
        tasks: List[Task],
        topology: str = 'sequential',
    ) -> Crew:
        """
        Создание crew (команды агентов с задачами).

        Args:
            name: Название crew.
            agents: Список агентов.
            tasks: Список задач.
            topology: Топология выполнения: sequential / parallel / hierarchical.

        Returns:
            Объект Crew.

        Raises:
            ValueError: Если topology не поддерживается или агент для задачи не найден.
        """
        valid_topologies = ('sequential', 'parallel', 'hierarchical')
        if topology not in valid_topologies:
            raise ValueError(
                f"Неизвестная топология '{topology}'. "
                f"Доступны: {', '.join(valid_topologies)}"
            )

        # Валидация: все agent_role из задач должны быть в агентах
        agent_roles = {a.role for a in agents}
        for task in tasks:
            if task.agent_role not in agent_roles:
                raise ValueError(
                    f"Задача '{task.description[:50]}' требует роль '{task.agent_role}', "
                    f"но такой агент не добавлен. Доступные роли: {agent_roles}"
                )

        return Crew(
            name=name,
            agents=agents,
            tasks=tasks,
            topology=topology,
        )

    # ── Выполнение crew ──

    def execute(self, crew: Crew, context: Optional[Dict] = None) -> CrewResult:
        """
        Выполнение crew.

        Если crewai установлен -- делегирует ему. Иначе -- собственная реализация.

        Args:
            crew: Объект Crew для выполнения.
            context: Дополнительный контекст (передаётся первой задаче).

        Returns:
            CrewResult с результатами всех задач.
        """
        context = context or {}
        start_time = time.time()

        if self._crewai_available:
            try:
                result = self._execute_with_crewai(crew, context)
            except Exception as e:
                logger.warning("crewai выполнение не удалось, fallback: %s", e)
                result = self._execute_native(crew, context)
        else:
            result = self._execute_native(crew, context)

        # Замер времени
        elapsed_ms = (time.time() - start_time) * 1000
        result.total_time_ms = round(elapsed_ms, 1)

        # Сохраняем в историю
        self._execution_history.append(result)

        return result

    def _execute_native(self, crew: Crew, context: Dict) -> CrewResult:
        """
        Собственная реализация выполнения crew (без crewai).

        Поддерживает три топологии:
        - sequential: задачи по порядку, результат предыдущей в контекст следующей
        - parallel: независимые задачи помечаются для параллельного выполнения
        - hierarchical: первая задача -- координатор, остальные -- workers
        """
        if crew.topology == 'sequential':
            return self._execute_sequential(crew, context)
        elif crew.topology == 'parallel':
            return self._execute_parallel(crew, context)
        elif crew.topology == 'hierarchical':
            return self._execute_hierarchical(crew, context)
        else:
            return self._execute_sequential(crew, context)

    def _execute_sequential(self, crew: Crew, context: Dict) -> CrewResult:
        """
        Последовательное выполнение: каждая задача получает результат предыдущей.
        """
        tasks_results = []
        errors = []
        previous_result = context.get('initial_input', '')

        for task in crew.tasks:
            task.status = 'in_progress'
            agent = self._find_agent(crew, task.agent_role)

            task_context = {
                'previous_result': previous_result,
                'agent': {
                    'role': agent.role if agent else 'unknown',
                    'goal': agent.goal if agent else '',
                    'model': agent.model if agent else 'flash',
                    'tools': agent.tools if agent else [],
                },
                'task': {
                    'description': task.description,
                    'expected_output': task.expected_output,
                },
                'global_context': context,
            }

            try:
                # В нативной реализации -- формируем структурированный результат
                # Реальное выполнение делегируется внешнему orchestrator'у
                result_text = self._simulate_task_execution(task, task_context)
                task.status = 'completed'
                task.result = result_text
                previous_result = result_text
            except Exception as e:
                task.status = 'failed'
                error_msg = f"Задача '{task.description[:50]}' ({task.agent_role}): {e}"
                errors.append(error_msg)
                logger.error("Ошибка выполнения задачи: %s", error_msg)

            tasks_results.append({
                'description': task.description,
                'agent_role': task.agent_role,
                'status': task.status,
                'result': task.result,
                'model': agent.model if agent else 'flash',
            })

        success = all(t['status'] == 'completed' for t in tasks_results)
        return CrewResult(
            crew_name=crew.name,
            tasks_results=tasks_results,
            total_time_ms=0.0,  # Будет перезаписано в execute()
            success=success,
            errors=errors,
        )

    def _execute_parallel(self, crew: Crew, context: Dict) -> CrewResult:
        """
        Параллельное выполнение: группирует задачи без зависимостей.

        В нативной реализации выполняет последовательно, но помечает
        параллельные группы для внешнего orchestrator'а.
        """
        tasks_results = []
        errors = []
        completed_descriptions: set = set()

        # Группируем задачи по уровням зависимости
        levels = self._build_dependency_levels(crew.tasks)

        for level_idx, level_tasks in enumerate(levels):
            level_results = []
            for task in level_tasks:
                task.status = 'in_progress'
                agent = self._find_agent(crew, task.agent_role)

                # Собираем результаты зависимостей
                dep_results = [
                    tr['result']
                    for tr in tasks_results
                    if tr['description'] in task.dependencies and tr['result']
                ]

                task_context = {
                    'dependency_results': dep_results,
                    'parallel_level': level_idx,
                    'agent': {
                        'role': agent.role if agent else 'unknown',
                        'goal': agent.goal if agent else '',
                        'model': agent.model if agent else 'flash',
                    },
                    'task': {
                        'description': task.description,
                        'expected_output': task.expected_output,
                    },
                    'global_context': context,
                }

                try:
                    result_text = self._simulate_task_execution(task, task_context)
                    task.status = 'completed'
                    task.result = result_text
                    completed_descriptions.add(task.description)
                except Exception as e:
                    task.status = 'failed'
                    errors.append(f"Задача '{task.description[:50]}': {e}")

                level_results.append({
                    'description': task.description,
                    'agent_role': task.agent_role,
                    'status': task.status,
                    'result': task.result,
                    'model': agent.model if agent else 'flash',
                    'parallel_level': level_idx,
                })

            tasks_results.extend(level_results)

        success = all(t['status'] == 'completed' for t in tasks_results)
        return CrewResult(
            crew_name=crew.name,
            tasks_results=tasks_results,
            total_time_ms=0.0,
            success=success,
            errors=errors,
        )

    def _execute_hierarchical(self, crew: Crew, context: Dict) -> CrewResult:
        """
        Иерархическое выполнение: координатор (первая задача) управляет workers.
        """
        if not crew.tasks:
            return CrewResult(
                crew_name=crew.name,
                tasks_results=[],
                total_time_ms=0.0,
                success=True,
                errors=[],
            )

        tasks_results = []
        errors = []

        # Первая задача -- координатор
        coordinator_task = crew.tasks[0]
        coordinator_agent = self._find_agent(crew, coordinator_task.agent_role)

        coordinator_task.status = 'in_progress'
        coord_context = {
            'role': 'coordinator',
            'worker_tasks': [
                {'description': t.description, 'agent_role': t.agent_role}
                for t in crew.tasks[1:]
            ],
            'agent': {
                'role': coordinator_agent.role if coordinator_agent else 'coordinator',
                'goal': coordinator_agent.goal if coordinator_agent else '',
                'model': coordinator_agent.model if coordinator_agent else 'opus',
            },
            'task': {
                'description': coordinator_task.description,
                'expected_output': coordinator_task.expected_output,
            },
            'global_context': context,
        }

        try:
            coord_result = self._simulate_task_execution(coordinator_task, coord_context)
            coordinator_task.status = 'completed'
            coordinator_task.result = coord_result
        except Exception as e:
            coordinator_task.status = 'failed'
            errors.append(f"Координатор: {e}")
            coord_result = ''

        tasks_results.append({
            'description': coordinator_task.description,
            'agent_role': coordinator_task.agent_role,
            'status': coordinator_task.status,
            'result': coordinator_task.result,
            'model': coordinator_agent.model if coordinator_agent else 'opus',
            'is_coordinator': True,
        })

        # Workers -- выполняются с контекстом координатора
        for task in crew.tasks[1:]:
            task.status = 'in_progress'
            agent = self._find_agent(crew, task.agent_role)

            task_context = {
                'role': 'worker',
                'coordinator_result': coord_result,
                'agent': {
                    'role': agent.role if agent else 'unknown',
                    'goal': agent.goal if agent else '',
                    'model': agent.model if agent else 'flash',
                },
                'task': {
                    'description': task.description,
                    'expected_output': task.expected_output,
                },
                'global_context': context,
            }

            try:
                result_text = self._simulate_task_execution(task, task_context)
                task.status = 'completed'
                task.result = result_text
            except Exception as e:
                task.status = 'failed'
                errors.append(f"Worker '{task.agent_role}': {e}")

            tasks_results.append({
                'description': task.description,
                'agent_role': task.agent_role,
                'status': task.status,
                'result': task.result,
                'model': agent.model if agent else 'flash',
                'is_coordinator': False,
            })

        success = all(t['status'] == 'completed' for t in tasks_results)
        return CrewResult(
            crew_name=crew.name,
            tasks_results=tasks_results,
            total_time_ms=0.0,
            success=success,
            errors=errors,
        )

    def _execute_with_crewai(self, crew: Crew, context: Dict) -> CrewResult:
        """
        Выполнение через библиотеку crewai (если установлена).

        Оборачивает внутренние Agent/Task/Crew в объекты crewai.
        """
        import crewai as cr

        # Маппинг моделей
        model_map = {
            'flash': 'gemini/gemini-2.5-flash-preview',
            'pro': 'gemini/gemini-2.5-pro-preview',
            'sonnet': 'anthropic/claude-sonnet-4-5-20250929',
            'opus': 'anthropic/claude-opus-4-6',
        }

        # Конвертация агентов
        cr_agents = {}
        for agent in crew.agents:
            llm = model_map.get(agent.model, agent.model)
            cr_agent = cr.Agent(
                role=agent.role,
                goal=agent.goal,
                backstory=agent.backstory or f"Агент с ролью {agent.role}",
                llm=llm,
                verbose=False,
            )
            cr_agents[agent.role] = cr_agent

        # Конвертация задач
        cr_tasks = []
        for task in crew.tasks:
            cr_agent = cr_agents.get(task.agent_role)
            if not cr_agent:
                continue
            cr_task = cr.Task(
                description=task.description,
                expected_output=task.expected_output or "Результат выполнения задачи",
                agent=cr_agent,
            )
            cr_tasks.append(cr_task)

        # Маппинг топологии
        process_map = {
            'sequential': cr.Process.sequential,
            'hierarchical': cr.Process.hierarchical,
        }
        process = process_map.get(crew.topology, cr.Process.sequential)

        # Создание и запуск crewai Crew
        cr_crew = cr.Crew(
            agents=list(cr_agents.values()),
            tasks=cr_tasks,
            process=process,
            verbose=False,
        )

        result = cr_crew.kickoff(inputs=context)

        # Конвертация результата
        tasks_results = []
        for i, task in enumerate(crew.tasks):
            task.status = 'completed'
            task.result = str(result) if i == len(crew.tasks) - 1 else 'OK'
            tasks_results.append({
                'description': task.description,
                'agent_role': task.agent_role,
                'status': 'completed',
                'result': task.result,
                'model': self._find_agent(crew, task.agent_role).model
                if self._find_agent(crew, task.agent_role) else 'flash',
            })

        return CrewResult(
            crew_name=crew.name,
            tasks_results=tasks_results,
            total_time_ms=0.0,
            success=True,
            errors=[],
        )

    # ── Шаблоны ──

    def get_template(self, template_name: str) -> Crew:
        """
        Получение готового шаблона crew.

        Доступные шаблоны:
        - bug_fix: researcher -> coder -> tester
        - feature: researcher -> architect -> coder -> tester -> reviewer
        - refactor: architect -> coder -> reviewer
        - security: security-architect -> security-auditor -> coder -> tester
        - docs: researcher -> coder

        Args:
            template_name: Имя шаблона.

        Returns:
            Объект Crew, готовый к выполнению.

        Raises:
            ValueError: Если шаблон не найден.
        """
        if template_name not in _TEMPLATES:
            available = ', '.join(_TEMPLATES.keys())
            raise ValueError(
                f"Шаблон '{template_name}' не найден. "
                f"Доступные: {available}"
            )

        tmpl = _TEMPLATES[template_name]

        # Создаём глубокие копии агентов и задач
        agents = [
            Agent(
                role=a.role,
                goal=a.goal,
                backstory=a.backstory,
                tools=list(a.tools),
                model=a.model,
            )
            for a in tmpl['agents']
        ]

        tasks = [
            Task(
                description=t.description,
                agent_role=t.agent_role,
                expected_output=t.expected_output,
                dependencies=list(t.dependencies),
            )
            for t in tmpl['tasks']
        ]

        return Crew(
            name=tmpl['name'],
            agents=agents,
            tasks=tasks,
            topology=tmpl['topology'],
        )

    def list_templates(self) -> List[Dict[str, Any]]:
        """
        Список доступных шаблонов crew.

        Returns:
            Список словарей с информацией о каждом шаблоне.
        """
        result = []
        for name, tmpl in _TEMPLATES.items():
            result.append({
                'name': name,
                'display_name': tmpl['name'],
                'topology': tmpl['topology'],
                'agents_count': len(tmpl['agents']),
                'tasks_count': len(tmpl['tasks']),
                'agent_roles': [a.role for a in tmpl['agents']],
                'pipeline': ' -> '.join(a.role for a in tmpl['agents']),
            })
        return result

    # ── История выполнений ──

    def get_execution_history(self) -> List[Dict[str, Any]]:
        """
        История выполнений crew.

        Returns:
            Список словарей с результатами каждого выполнения.
        """
        return [
            {
                'crew_name': r.crew_name,
                'success': r.success,
                'total_time_ms': r.total_time_ms,
                'tasks_count': len(r.tasks_results),
                'completed': sum(1 for t in r.tasks_results if t['status'] == 'completed'),
                'failed': sum(1 for t in r.tasks_results if t['status'] == 'failed'),
                'errors': r.errors,
            }
            for r in self._execution_history
        ]

    # ── Вспомогательные методы ──

    @staticmethod
    def _find_agent(crew: Crew, role: str) -> Optional[Agent]:
        """Поиск агента по роли в crew."""
        for agent in crew.agents:
            if agent.role == role:
                return agent
        return None

    @staticmethod
    def _simulate_task_execution(task: Task, context: Dict) -> str:
        """
        Симуляция выполнения задачи.

        В нативной реализации (без crewai) формирует структурированный промпт,
        который может быть передан внешнему orchestrator'у или CLI для реального
        выполнения через LLM.

        Returns:
            Строка с промптом/контекстом для внешнего выполнения.
        """
        agent_info = context.get('agent', {})
        task_info = context.get('task', {})
        previous = context.get('previous_result', '')
        coordinator = context.get('coordinator_result', '')
        dep_results = context.get('dependency_results', [])

        # Формируем контекст для реального выполнения
        parts = [
            f"=== Задача: {task_info.get('description', task.description)} ===",
            f"Роль: {agent_info.get('role', 'unknown')}",
            f"Цель: {agent_info.get('goal', '')}",
            f"Модель: {agent_info.get('model', 'flash')}",
        ]

        if task_info.get('expected_output'):
            parts.append(f"Ожидаемый результат: {task_info['expected_output']}")

        if previous:
            parts.append(f"\n--- Результат предыдущей задачи ---\n{previous}")

        if coordinator:
            parts.append(f"\n--- Директива координатора ---\n{coordinator}")

        if dep_results:
            for i, dep in enumerate(dep_results, 1):
                parts.append(f"\n--- Зависимость {i} ---\n{dep}")

        return '\n'.join(parts)

    @staticmethod
    def _build_dependency_levels(tasks: List[Task]) -> List[List[Task]]:
        """
        Группировка задач по уровням зависимости для параллельного выполнения.

        Задачи без зависимостей -- уровень 0 (можно параллельно).
        Задачи, зависящие от уровня 0 -- уровень 1, и т.д.
        """
        if not tasks:
            return []

        # Индекс задач по описанию
        task_map = {t.description: t for t in tasks}
        assigned: set = set()
        levels: List[List[Task]] = []

        max_iterations = len(tasks) + 1
        iteration = 0

        while len(assigned) < len(tasks) and iteration < max_iterations:
            iteration += 1
            current_level = []

            for task in tasks:
                if task.description in assigned:
                    continue

                # Все зависимости уже назначены?
                deps_met = all(dep in assigned for dep in task.dependencies)
                if deps_met:
                    current_level.append(task)

            if not current_level:
                # Циклическая зависимость или недостижимые задачи
                remaining = [t for t in tasks if t.description not in assigned]
                levels.append(remaining)
                break

            for task in current_level:
                assigned.add(task.description)

            levels.append(current_level)

        return levels
