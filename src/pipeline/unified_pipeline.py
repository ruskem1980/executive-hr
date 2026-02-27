"""
Unified Pipeline — главный orchestrator, объединяющий все интеграции.

Pipeline обработки задачи:
    Task -> classify (LearnedRouter/TaskClassifier)
         -> check cache (SemanticCache)
         -> optimize prompt (DSPyOptimizer)
         -> validate input (GuardrailsValidator)
         -> execute (LiteLLMGateway)
         -> validate output (GuardrailsValidator)
         -> cache result (SemanticCache)
         -> trace (LangfuseTracer)
         -> track tokens (TokenTracker)
         -> result

Каждый компонент опционален — если модуль не установлен,
pipeline работает без него (graceful degradation).
"""

import logging
import time
import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Корень проекта
_PROJECT_ROOT = Path(__file__).parent.parent.parent

# ── Ленивые импорты компонентов (каждый в try/except) ──

try:
    from src.gateway.litellm_gateway import LiteLLMGateway
    _HAS_GATEWAY = True
except ImportError:
    _HAS_GATEWAY = False

try:
    from src.cache.semantic_cache import SemanticCache
    _HAS_CACHE = True
except ImportError:
    _HAS_CACHE = False

try:
    from src.validation.guardrails_validator import GuardrailsValidator
    _HAS_VALIDATION = True
except ImportError:
    _HAS_VALIDATION = False

try:
    from src.observability.langfuse_tracer import LangfuseTracer
    _HAS_OBSERVABILITY = True
except ImportError:
    _HAS_OBSERVABILITY = False

try:
    from src.ml.task_classifier import TaskClassifier
    _HAS_CLASSIFIER = True
except ImportError:
    _HAS_CLASSIFIER = False

try:
    from src.reporting.token_tracker import TokenTracker
    _HAS_TRACKER = True
except ImportError:
    _HAS_TRACKER = False

try:
    from src.prompts.prompt_analyzer import PromptAnalyzer
    _HAS_PROMPT_ANALYZER = True
except ImportError:
    _HAS_PROMPT_ANALYZER = False

# Загрузка YAML конфига
try:
    import yaml
    _HAS_YAML = True
except ImportError:
    _HAS_YAML = False


@dataclass
class PipelineResult:
    """Результат обработки задачи через pipeline."""

    # Основной результат
    content: str = ''
    # Какая модель использовалась
    model_used: str = ''
    # Получен ли результат из кеша
    cached: bool = False
    # Токены
    input_tokens: int = 0
    output_tokens: int = 0
    # Стоимость в USD
    cost: float = 0.0
    # Задержка в миллисекундах
    latency_ms: float = 0.0
    # Результат валидации входа/выхода
    validation: Dict[str, Any] = field(default_factory=dict)
    # ID трейса для observability
    trace_id: str = ''
    # Решение маршрутизатора: модель + обоснование
    routing_decision: Dict[str, Any] = field(default_factory=dict)


class UnifiedPipeline:
    """
    Главный orchestrator, объединяющий все компоненты системы.

    Принцип: graceful degradation — если компонент недоступен,
    pipeline работает без него. Каждый компонент создаётся
    лениво при первом обращении и кешируется.
    """

    def __init__(self, config_path: str = 'config/integrations.yaml'):
        """
        Инициализация pipeline.

        Аргументы:
            config_path: путь к YAML-конфигурации интеграций
                         (относительно корня проекта).
        """
        self._config_path = _PROJECT_ROOT / config_path
        self._config: Dict[str, Any] = {}
        self._load_config()

        # Кеш ленивых экземпляров компонентов
        self._gateway: Optional[Any] = None
        self._cache: Optional[Any] = None
        self._validator: Optional[Any] = None
        self._tracer: Optional[Any] = None
        self._classifier: Optional[Any] = None
        self._tracker: Optional[Any] = None
        self._prompt_analyzer: Optional[Any] = None

        # TTL для кеша (используется при put())
        self._cache_ttl: int = self._config.get('cache', {}).get('ttl', 3600)

        # Статистика pipeline
        self._stats = {
            'total_requests': 0,
            'cache_hits': 0,
            'cache_misses': 0,
            'total_input_tokens': 0,
            'total_output_tokens': 0,
            'total_cost': 0.0,
            'total_latency_ms': 0.0,
            'successes': 0,
            'failures': 0,
            'validation_blocks': 0,
        }

    # ── Загрузка конфига ──

    def _load_config(self) -> None:
        """Загружает конфигурацию из YAML-файла."""
        if not self._config_path.exists():
            logger.info(
                'Конфиг %s не найден, используются значения по умолчанию',
                self._config_path,
            )
            return

        if not _HAS_YAML:
            logger.warning('PyYAML не установлен — конфиг не загружен')
            return

        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
            logger.info('Конфигурация pipeline загружена из %s', self._config_path)
        except Exception as exc:
            logger.warning('Ошибка загрузки конфига: %s', exc)

    def _is_enabled(self, component: str) -> bool:
        """Проверяет, включён ли компонент в конфиге."""
        section = self._config.get(component, {})
        # По умолчанию включён, если секция существует
        if isinstance(section, dict):
            return section.get('enabled', True)
        return True

    # ── Ленивая инициализация компонентов ──

    @property
    def gateway(self) -> Optional[Any]:
        """LiteLLM Gateway — единый API для вызовов LLM."""
        if self._gateway is None and _HAS_GATEWAY and self._is_enabled('gateway'):
            try:
                self._gateway = LiteLLMGateway(
                    config_path=str(self._config_path.relative_to(_PROJECT_ROOT))
                )
                logger.debug('Gateway инициализирован')
            except Exception as exc:
                logger.warning('Ошибка инициализации Gateway: %s', exc)
        return self._gateway

    @property
    def cache(self) -> Optional[Any]:
        """SemanticCache — семантическое кеширование ответов."""
        if self._cache is None and _HAS_CACHE and self._is_enabled('cache'):
            try:
                cache_config = self._config.get('cache', {})
                self._cache = SemanticCache(
                    similarity_threshold=cache_config.get('similarity_threshold', 0.85),
                    cache_dir=str(_PROJECT_ROOT / cache_config.get('cache_dir', 'data/semantic_cache')),
                    max_size=cache_config.get('max_size', 10000),
                )
                # TTL хранится отдельно для передачи в put()
                self._cache_ttl = cache_config.get('ttl', 3600)
                logger.debug('SemanticCache инициализирован')
            except Exception as exc:
                logger.warning('Ошибка инициализации SemanticCache: %s', exc)
        return self._cache

    @property
    def validator(self) -> Optional[Any]:
        """GuardrailsValidator — валидация входов и выходов."""
        if self._validator is None and _HAS_VALIDATION and self._is_enabled('validation'):
            try:
                val_config = self._config.get('validation', {})
                rules_config = val_config.get('rules', {})
                # Преобразуем конфиг в формат GuardrailsValidator:
                # max_length, disabled_rules
                validator_config = {}
                if 'max_length' in rules_config:
                    validator_config['max_length'] = rules_config['max_length']
                # Собираем отключённые правила из конфига
                disabled = []
                for rule_name, enabled in rules_config.items():
                    if rule_name != 'max_length' and enabled is False:
                        disabled.append(rule_name)
                if disabled:
                    validator_config['disabled_rules'] = disabled
                self._validator = GuardrailsValidator(
                    rules_config=validator_config,
                )
                logger.debug('GuardrailsValidator инициализирован')
            except Exception as exc:
                logger.warning('Ошибка инициализации Validator: %s', exc)
        return self._validator

    @property
    def tracer(self) -> Optional[Any]:
        """LangfuseTracer — трейсинг и мониторинг."""
        if self._tracer is None and _HAS_OBSERVABILITY and self._is_enabled('observability'):
            try:
                obs_config = self._config.get('observability', {})
                self._tracer = LangfuseTracer(
                    project_name=obs_config.get('project_name', 'pt_standart_agents'),
                    db_path=_PROJECT_ROOT / obs_config.get('db_path', 'data/traces.db'),
                )
                logger.debug('LangfuseTracer инициализирован')
            except Exception as exc:
                logger.warning('Ошибка инициализации Tracer: %s', exc)
        return self._tracer

    @property
    def classifier(self) -> Optional[Any]:
        """TaskClassifier — ML-классификатор сложности задач."""
        if self._classifier is None and _HAS_CLASSIFIER:
            try:
                cls = TaskClassifier()
                # Попытка загрузить обученную модель
                model_path = _PROJECT_ROOT / 'data' / 'models' / 'task_classifier.pkl'
                if model_path.exists():
                    cls.load(str(model_path))
                    logger.debug('TaskClassifier загружен из %s', model_path)
                else:
                    logger.debug(
                        'Обученная модель TaskClassifier не найдена, '
                        'будет использован rule-based fallback'
                    )
                self._classifier = cls
            except Exception as exc:
                logger.warning('Ошибка инициализации TaskClassifier: %s', exc)
        return self._classifier

    @property
    def tracker(self) -> Optional[Any]:
        """TokenTracker — учёт расхода токенов."""
        if self._tracker is None and _HAS_TRACKER:
            try:
                self._tracker = TokenTracker()
                logger.debug('TokenTracker инициализирован')
            except Exception as exc:
                logger.warning('Ошибка инициализации TokenTracker: %s', exc)
        return self._tracker

    @property
    def prompt_analyzer(self) -> Optional[Any]:
        """PromptAnalyzer — анализ промптов и рекомендации."""
        if self._prompt_analyzer is None and _HAS_PROMPT_ANALYZER:
            try:
                self._prompt_analyzer = PromptAnalyzer()
                logger.debug('PromptAnalyzer инициализирован')
            except Exception as exc:
                logger.warning('Ошибка инициализации PromptAnalyzer: %s', exc)
        return self._prompt_analyzer

    # ── Основной pipeline ──

    def process(
        self,
        task_description: str,
        context: Optional[Dict[str, Any]] = None,
    ) -> PipelineResult:
        """
        Обработка задачи через полный pipeline.

        Последовательность:
            1. Классификация сложности
            2. Проверка кеша
            3. Валидация входа
            4. Выбор модели (routing)
            5. Выполнение LLM-вызова
            6. Валидация выхода
            7. Кеширование результата
            8. Трейсинг
            9. Трекинг токенов

        Аргументы:
            task_description: текстовое описание задачи.
            context: дополнительный контекст (файлы, настройки и т.д.).

        Возвращает:
            PipelineResult с результатом и метаданными.
        """
        context = context or {}
        start_time = time.monotonic()
        trace_id = str(uuid.uuid4())[:12]

        result = PipelineResult(trace_id=trace_id)
        self._stats['total_requests'] += 1

        try:
            # ── ШАГ 1: Классификация сложности ──
            complexity = self._classify_task(task_description)
            result.routing_decision['complexity'] = complexity

            # ── ШАГ 2: Проверка кеша ──
            cached_content = self._check_cache(task_description)
            if cached_content is not None:
                result.content = cached_content
                result.cached = True
                result.model_used = 'cache'
                self._stats['cache_hits'] += 1
                logger.info('Результат получен из кеша (trace=%s)', trace_id)
                # Трейсинг даже для кешированных результатов
                self._trace(trace_id, task_description, result)
                result.latency_ms = (time.monotonic() - start_time) * 1000
                self._stats['successes'] += 1
                return result

            self._stats['cache_misses'] += 1

            # ── ШАГ 3: Валидация входа ──
            input_validation = self._validate_input(task_description, context)
            result.validation['input'] = input_validation
            if input_validation.get('blocked', False):
                result.content = f"Вход заблокирован валидацией: {input_validation.get('reason', 'неизвестная причина')}"
                result.latency_ms = (time.monotonic() - start_time) * 1000
                self._stats['validation_blocks'] += 1
                self._stats['failures'] += 1
                return result

            # ── ШАГ 4: Выбор модели ──
            model_alias = self._select_model(complexity, context)
            result.routing_decision['model'] = model_alias
            result.routing_decision['reason'] = self._routing_reason(complexity, model_alias)
            result.model_used = model_alias

            # ── ШАГ 5: Выполнение LLM-вызова ──
            llm_result = self._execute_llm(
                model_alias=model_alias,
                prompt=task_description,
                system=context.get('system_prompt'),
                temperature=context.get('temperature', 0.7),
                max_tokens=context.get('max_tokens', 4096),
            )
            result.content = llm_result.get('content', '')
            result.input_tokens = llm_result.get('input_tokens', 0)
            result.output_tokens = llm_result.get('output_tokens', 0)
            result.cost = llm_result.get('cost', 0.0)

            # ── ШАГ 6: Валидация выхода ──
            output_validation = self._validate_output(result.content)
            result.validation['output'] = output_validation

            # ── ШАГ 7: Кеширование результата ──
            if not result.cached and result.content:
                self._store_cache(task_description, result.content)

            # ── ШАГ 8: Трейсинг ──
            self._trace(trace_id, task_description, result)

            # ── ШАГ 9: Трекинг токенов ──
            self._track_tokens(result)

            # Обновление статистики
            self._stats['total_input_tokens'] += result.input_tokens
            self._stats['total_output_tokens'] += result.output_tokens
            self._stats['total_cost'] += result.cost
            self._stats['successes'] += 1

        except Exception as exc:
            logger.error('Ошибка в pipeline (trace=%s): %s', trace_id, exc)
            result.content = f'Ошибка pipeline: {exc}'
            self._stats['failures'] += 1

        result.latency_ms = (time.monotonic() - start_time) * 1000
        self._stats['total_latency_ms'] += result.latency_ms

        return result

    def process_simple(self, prompt: str, model: str = 'flash') -> str:
        """
        Упрощённый вызов: кеш -> LLM -> результат.

        Без классификации, валидации и трейсинга.
        Подходит для быстрых запросов без полного pipeline.

        Аргументы:
            prompt: текст промпта.
            model: алиас модели ('flash', 'pro', 'sonnet', 'opus').

        Возвращает:
            Текст ответа от LLM (или из кеша).
        """
        # Проверка кеша
        cached = self._check_cache(prompt)
        if cached is not None:
            self._stats['cache_hits'] += 1
            return cached

        self._stats['cache_misses'] += 1

        # LLM-вызов
        llm_result = self._execute_llm(
            model_alias=model,
            prompt=prompt,
        )
        content = llm_result.get('content', '')

        # Кеширование
        if content:
            self._store_cache(prompt, content)

        # Обновление статистики
        self._stats['total_requests'] += 1
        self._stats['total_input_tokens'] += llm_result.get('input_tokens', 0)
        self._stats['total_output_tokens'] += llm_result.get('output_tokens', 0)
        self._stats['total_cost'] += llm_result.get('cost', 0.0)
        self._stats['successes'] += 1

        return content

    # ── Публичные методы статистики ──

    def get_status(self) -> Dict[str, Any]:
        """
        Статус всех компонентов pipeline.

        Возвращает:
            Словарь с информацией о каждом компоненте:
            initialized, available, конфиг включения.
        """
        return {
            'gateway': {
                'available': _HAS_GATEWAY,
                'enabled': self._is_enabled('gateway'),
                'initialized': self._gateway is not None,
            },
            'cache': {
                'available': _HAS_CACHE,
                'enabled': self._is_enabled('cache'),
                'initialized': self._cache is not None,
            },
            'validation': {
                'available': _HAS_VALIDATION,
                'enabled': self._is_enabled('validation'),
                'initialized': self._validator is not None,
            },
            'observability': {
                'available': _HAS_OBSERVABILITY,
                'enabled': self._is_enabled('observability'),
                'initialized': self._tracer is not None,
            },
            'classifier': {
                'available': _HAS_CLASSIFIER,
                'enabled': True,  # Классификатор всегда используется если доступен
                'initialized': self._classifier is not None,
                'trained': (
                    self._classifier.is_trained
                    if self._classifier is not None
                    else False
                ),
            },
            'token_tracker': {
                'available': _HAS_TRACKER,
                'enabled': True,
                'initialized': self._tracker is not None,
            },
            'prompt_analyzer': {
                'available': _HAS_PROMPT_ANALYZER,
                'enabled': True,
                'initialized': self._prompt_analyzer is not None,
            },
            'config_loaded': bool(self._config),
            'config_path': str(self._config_path),
        }

    def get_stats(self) -> Dict[str, Any]:
        """
        Агрегированная статистика работы pipeline.

        Возвращает:
            Словарь со статистикой: запросы, кеш, токены,
            стоимость, latency, success rate.
        """
        total = self._stats['total_requests']
        hits = self._stats['cache_hits']
        successes = self._stats['successes']

        return {
            'total_requests': total,
            'cache_hits': hits,
            'cache_misses': self._stats['cache_misses'],
            'cache_hit_rate': (hits / total * 100) if total > 0 else 0.0,
            'total_input_tokens': self._stats['total_input_tokens'],
            'total_output_tokens': self._stats['total_output_tokens'],
            'total_tokens': (
                self._stats['total_input_tokens']
                + self._stats['total_output_tokens']
            ),
            'total_cost_usd': self._stats['total_cost'],
            'avg_latency_ms': (
                self._stats['total_latency_ms'] / total
                if total > 0
                else 0.0
            ),
            'success_rate': (successes / total * 100) if total > 0 else 0.0,
            'successes': successes,
            'failures': self._stats['failures'],
            'validation_blocks': self._stats['validation_blocks'],
        }

    def health_check(self) -> Dict[str, Any]:
        """
        Проверка здоровья всех компонентов.

        Возвращает:
            Словарь с результатами проверки:
            healthy (bool), компоненты и их статус.
        """
        checks: Dict[str, Dict[str, Any]] = {}
        all_healthy = True

        # Gateway
        if _HAS_GATEWAY and self._is_enabled('gateway'):
            try:
                gw = self.gateway
                checks['gateway'] = {
                    'healthy': gw is not None,
                    'detail': 'Инициализирован' if gw else 'Ошибка инициализации',
                }
            except Exception as exc:
                checks['gateway'] = {'healthy': False, 'detail': str(exc)}
                all_healthy = False
        else:
            checks['gateway'] = {
                'healthy': True,
                'detail': 'Не установлен' if not _HAS_GATEWAY else 'Отключён в конфиге',
                'optional': True,
            }

        # Cache
        if _HAS_CACHE and self._is_enabled('cache'):
            try:
                c = self.cache
                checks['cache'] = {
                    'healthy': c is not None,
                    'detail': 'Инициализирован' if c else 'Ошибка инициализации',
                }
            except Exception as exc:
                checks['cache'] = {'healthy': False, 'detail': str(exc)}
                all_healthy = False
        else:
            checks['cache'] = {
                'healthy': True,
                'detail': 'Не установлен' if not _HAS_CACHE else 'Отключён в конфиге',
                'optional': True,
            }

        # Validator
        if _HAS_VALIDATION and self._is_enabled('validation'):
            try:
                v = self.validator
                checks['validation'] = {
                    'healthy': v is not None,
                    'detail': 'Инициализирован' if v else 'Ошибка инициализации',
                }
            except Exception as exc:
                checks['validation'] = {'healthy': False, 'detail': str(exc)}
                all_healthy = False
        else:
            checks['validation'] = {
                'healthy': True,
                'detail': 'Не установлен' if not _HAS_VALIDATION else 'Отключён в конфиге',
                'optional': True,
            }

        # Tracer
        if _HAS_OBSERVABILITY and self._is_enabled('observability'):
            try:
                t = self.tracer
                checks['observability'] = {
                    'healthy': t is not None,
                    'detail': 'Инициализирован' if t else 'Ошибка инициализации',
                }
            except Exception as exc:
                checks['observability'] = {'healthy': False, 'detail': str(exc)}
                all_healthy = False
        else:
            checks['observability'] = {
                'healthy': True,
                'detail': 'Не установлен' if not _HAS_OBSERVABILITY else 'Отключён в конфиге',
                'optional': True,
            }

        # Classifier
        if _HAS_CLASSIFIER:
            try:
                cls = self.classifier
                checks['classifier'] = {
                    'healthy': cls is not None,
                    'detail': (
                        'Обучен' if cls and cls.is_trained
                        else 'Rule-based fallback' if cls
                        else 'Ошибка инициализации'
                    ),
                }
            except Exception as exc:
                checks['classifier'] = {'healthy': False, 'detail': str(exc)}
                all_healthy = False
        else:
            checks['classifier'] = {
                'healthy': True,
                'detail': 'sklearn не установлен, используется rule-based',
                'optional': True,
            }

        # TokenTracker
        if _HAS_TRACKER:
            try:
                tr = self.tracker
                checks['token_tracker'] = {
                    'healthy': tr is not None,
                    'detail': 'Инициализирован' if tr else 'Ошибка',
                }
            except Exception as exc:
                checks['token_tracker'] = {'healthy': False, 'detail': str(exc)}
                all_healthy = False
        else:
            checks['token_tracker'] = {
                'healthy': True,
                'detail': 'Недоступен',
                'optional': True,
            }

        return {
            'healthy': all_healthy,
            'components': checks,
            'graceful_degradation': self._config.get('general', {}).get(
                'graceful_degradation', True
            ),
        }

    # ── Внутренние методы pipeline ──

    def _classify_task(self, task_description: str) -> str:
        """
        Классификация сложности задачи.

        Использует ML-модель если обучена, иначе rule-based fallback.

        Возвращает:
            Метка сложности: 'program', 'simple', 'medium', 'complex'.
        """
        cls = self.classifier
        if cls is not None:
            try:
                if cls.is_trained:
                    prediction, confidence = cls.predict(
                        task_description, return_confidence=True
                    )
                    logger.debug(
                        'ML классификация: %s (confidence=%.2f)',
                        prediction, confidence,
                    )
                    # При низкой уверенности — fallback на правила
                    if confidence < 0.5:
                        return TaskClassifier.rule_based_fallback(task_description)
                    return prediction
                else:
                    return TaskClassifier.rule_based_fallback(task_description)
            except Exception as exc:
                logger.warning('Ошибка ML-классификации: %s', exc)

        # Fallback без sklearn
        return self._simple_classify(task_description)

    @staticmethod
    def _simple_classify(task_description: str) -> str:
        """
        Простейшая rule-based классификация (без sklearn).

        Используется когда TaskClassifier полностью недоступен.
        """
        task_lower = task_description.lower()

        program_hints = [
            'отчёт', 'отчет', 'статистик', 'покажи', 'список',
            'валидац', 'lint', 'format', 'тест запуст', 'pytest',
        ]
        complex_hints = [
            'архитектур', 'рефактор', 'миграц', 'безопасн',
            'производительн', 'оптимизац', 'переписать',
        ]
        medium_hints = [
            'api endpoint', 'модуль', 'компонент', 'фич',
            'интеграц', 'crud', 'middleware',
        ]

        if any(h in task_lower for h in program_hints):
            return 'program'
        if any(h in task_lower for h in complex_hints):
            return 'complex'
        if any(h in task_lower for h in medium_hints):
            return 'medium'
        return 'simple'

    def _check_cache(self, prompt: str) -> Optional[str]:
        """
        Проверка семантического кеша.

        SemanticCache.get() возвращает Dict (кешированный ответ) или None.
        Извлекаем 'content' из словаря для возврата текста.

        Возвращает:
            Кешированный текст ответа или None.
        """
        c = self.cache
        if c is None:
            return None

        try:
            hit = c.get(prompt)
            if hit is not None:
                logger.debug('Cache hit для промпта (%.40s...)', prompt)
                # hit — это Dict от SemanticCache, извлекаем content
                if isinstance(hit, dict):
                    return hit.get('content', str(hit))
                return str(hit)
        except Exception as exc:
            logger.warning('Ошибка проверки кеша: %s', exc)

        return None

    def _store_cache(self, prompt: str, response: str) -> None:
        """Сохранение результата в семантический кеш."""
        c = self.cache
        if c is None:
            return

        try:
            # SemanticCache.put() принимает Dict как response
            response_dict = {'content': response}
            ttl = getattr(self, '_cache_ttl', 3600)
            c.put(prompt, response_dict, ttl=ttl)
            logger.debug('Результат сохранён в кеш')
        except Exception as exc:
            logger.warning('Ошибка записи в кеш: %s', exc)

    def _validate_input(
        self,
        prompt: str,
        context: Dict[str, Any],
    ) -> Dict[str, Any]:
        """
        Валидация входных данных через GuardrailsValidator.

        GuardrailsValidator.validate_input(prompt) возвращает ValidationResult
        (dataclass с is_valid, errors, warnings, score, details).

        Возвращает:
            Словарь с результатами валидации:
            valid (bool), blocked (bool), errors ([]), warnings ([]).
        """
        val_config = self._config.get('validation', {})
        if not val_config.get('validate_input', True):
            return {'valid': True, 'blocked': False, 'errors': [], 'warnings': []}

        v = self.validator
        if v is None:
            return {'valid': True, 'blocked': False, 'errors': [], 'warnings': []}

        try:
            vr = v.validate_input(prompt)
            return {
                'valid': vr.is_valid,
                'blocked': not vr.is_valid,
                'errors': vr.errors,
                'warnings': vr.warnings,
                'score': vr.score,
                'details': vr.details,
                'reason': vr.errors[0] if vr.errors else '',
            }
        except Exception as exc:
            logger.warning('Ошибка валидации входа: %s', exc)
            # При ошибке валидации — пропускаем (graceful degradation)
            return {'valid': True, 'blocked': False, 'error': str(exc)}

    def _validate_output(self, content: str) -> Dict[str, Any]:
        """
        Валидация выходных данных LLM через GuardrailsValidator.

        GuardrailsValidator.validate_output(output) возвращает ValidationResult.

        Возвращает:
            Словарь с результатами: valid, errors, warnings, score.
        """
        val_config = self._config.get('validation', {})
        if not val_config.get('validate_output', True):
            return {'valid': True, 'errors': [], 'warnings': []}

        v = self.validator
        if v is None:
            return {'valid': True, 'errors': [], 'warnings': []}

        try:
            vr = v.validate_output(content)
            return {
                'valid': vr.is_valid,
                'errors': vr.errors,
                'warnings': vr.warnings,
                'score': vr.score,
                'details': vr.details,
            }
        except Exception as exc:
            logger.warning('Ошибка валидации выхода: %s', exc)
            return {'valid': True, 'error': str(exc)}

    def _select_model(
        self,
        complexity: str,
        context: Dict[str, Any],
    ) -> str:
        """
        Выбор оптимальной модели на основе сложности задачи.

        Аргументы:
            complexity: уровень сложности ('program', 'simple', 'medium', 'complex').
            context: контекст задачи (может содержать явный выбор модели).

        Возвращает:
            Алиас модели.
        """
        # Явный выбор модели из контекста
        if context.get('model'):
            return context['model']

        # Конфиг маршрутизации
        routing_config = self._config.get('routing', {})
        gateway_config = self._config.get('gateway', {})
        default_model = gateway_config.get('default_model', 'flash')

        # Маршрутизация по сложности
        model_map = {
            'program': default_model,   # Простые утилитарные задачи
            'simple': 'flash',          # Flash для простых задач
            'medium': 'pro',            # Pro для средних
            'complex': 'opus',          # Opus для сложных
        }

        return model_map.get(complexity, default_model)

    @staticmethod
    def _routing_reason(complexity: str, model: str) -> str:
        """Текстовое обоснование выбора модели."""
        reasons = {
            'program': f'Утилитарная задача -> {model} (минимальная стоимость)',
            'simple': f'Простая задача -> {model} (баланс стоимость/качество)',
            'medium': f'Средняя задача -> {model} (качественный ревью)',
            'complex': f'Сложная задача -> {model} (максимальное качество)',
        }
        return reasons.get(complexity, f'Выбрана модель {model}')

    def _execute_llm(
        self,
        model_alias: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """
        Выполнение LLM-вызова через Gateway.

        Если Gateway недоступен — возвращает заглушку с ошибкой.

        Возвращает:
            dict с ключами: content, model, input_tokens, output_tokens, cost.
        """
        gw = self.gateway
        if gw is None:
            logger.error(
                'Gateway недоступен — невозможно выполнить LLM-вызов (модель=%s)',
                model_alias,
            )
            return {
                'content': '',
                'model': model_alias,
                'input_tokens': 0,
                'output_tokens': 0,
                'cost': 0.0,
                'error': 'Gateway недоступен',
            }

        try:
            return gw.completion_with_fallback(
                model_alias=model_alias,
                prompt=prompt,
                system=system,
                temperature=temperature,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            logger.error('Ошибка LLM-вызова: %s', exc)
            return {
                'content': '',
                'model': model_alias,
                'input_tokens': 0,
                'output_tokens': 0,
                'cost': 0.0,
                'error': str(exc),
            }

    def _trace(
        self,
        trace_id: str,
        task_description: str,
        result: PipelineResult,
    ) -> None:
        """
        Запись трейса в observability-систему.

        Использует LangfuseTracer API:
            start_trace() -> log_llm_call() -> end_trace()
        """
        t = self.tracer
        if t is None:
            return

        try:
            # Создаём трейс
            t_id = t.start_trace(
                name='pipeline_process',
                metadata={
                    'pipeline_trace_id': trace_id,
                    'cached': result.cached,
                    **result.routing_decision,
                },
            )

            # Логируем LLM-вызов (если был)
            if result.model_used and result.model_used != 'cache':
                t.log_llm_call(
                    trace_id=t_id,
                    model=result.model_used,
                    input_text=task_description[:2000],  # Лимит для БД
                    output_text=result.content[:2000],
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                    cost=result.cost,
                    latency_ms=result.latency_ms,
                    metadata=result.routing_decision,
                )

            # Завершаем трейс
            t.end_trace(
                trace_id=t_id,
                output={'content_length': len(result.content), 'cached': result.cached},
                status='ok',
            )
        except Exception as exc:
            logger.warning('Ошибка трейсинга: %s', exc)

    def _track_tokens(self, result: PipelineResult) -> None:
        """Запись расхода токенов в TokenTracker."""
        tr = self.tracker
        if tr is None:
            return

        if result.input_tokens == 0 and result.output_tokens == 0:
            return

        try:
            # Ищем активную задачу
            tracking_dir = _PROJECT_ROOT / '.claude' / 'tracking'
            task_id = self._find_active_task_id(tracking_dir)
            if task_id:
                tr.record_call(
                    task_id,
                    model=result.model_used,
                    role='pipeline',
                    input_tokens=result.input_tokens,
                    output_tokens=result.output_tokens,
                )
        except Exception as exc:
            logger.debug('Ошибка записи токенов: %s', exc)

    @staticmethod
    def _find_active_task_id(tracking_dir: Path) -> Optional[str]:
        """Ищет ID активной задачи в директории трекинга."""
        if not tracking_dir.exists():
            return None

        task_files = sorted(tracking_dir.glob('task_*'), reverse=True)
        for f in task_files:
            name = f.name
            if name.startswith('task_'):
                return name[5:]
        return None
