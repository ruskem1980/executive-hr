"""
LiteLLM Gateway — единый API-шлюз для вызова LLM разных провайдеров.

Обеспечивает унифицированный интерфейс для работы с моделями:
- Gemini Flash/Pro (через LiteLLM)
- Claude Sonnet/Opus (через LiteLLM)

Поддерживает retry с exponential backoff, fallback-цепочки,
параллельные запросы и автоматический трекинг токенов.

Если litellm не установлен — fallback на subprocess-вызов
gemini-bridge.sh / sonnet-bridge.sh.

Использование:
    gateway = LiteLLMGateway()
    result = gateway.completion('flash', 'Напиши функцию сортировки')
    print(result['content'])
"""

import logging
import os
import subprocess
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# Маппинг алиасов моделей на полные идентификаторы LiteLLM
MODEL_MAP: Dict[str, str] = {
    'flash': 'gemini/gemini-2.0-flash',
    'pro': 'gemini/gemini-2.0-pro',
    'sonnet': 'claude-sonnet-4-5-20250929',
    'opus': 'claude-opus-4-6',
}

# Стоимость за 1M токенов (USD)
MODEL_PRICING: Dict[str, Dict[str, float]] = {
    'flash': {'input': 0.50, 'output': 3.00},
    'pro': {'input': 2.00, 'output': 12.00},
    'sonnet': {'input': 3.00, 'output': 15.00},
    'opus': {'input': 15.00, 'output': 75.00},
}

# Цепочка fallback по умолчанию: от дешёвой к дорогой
DEFAULT_FALLBACK_CHAIN: List[str] = ['flash', 'pro', 'sonnet', 'opus']

# Параметры retry
MAX_RETRIES = 3
RETRY_DELAYS = [1.0, 2.0, 4.0]  # Exponential backoff (секунды)

# Путь к shell-мостам для fallback без litellm
_PROJECT_ROOT = Path(__file__).parent.parent.parent
_GEMINI_BRIDGE = _PROJECT_ROOT / '.claude' / 'helpers' / 'gemini-bridge.sh'
_SONNET_BRIDGE = _PROJECT_ROOT / '.claude' / 'helpers' / 'sonnet-bridge.sh'

# Проверяем доступность litellm при импорте
try:
    import litellm
    _HAS_LITELLM = True
except ImportError:
    _HAS_LITELLM = False
    logger.warning('litellm не установлен — будет использован fallback через shell-скрипты')


class LiteLLMGateway:
    """Единый шлюз для вызова LLM через LiteLLM с fallback на shell-мосты."""

    def __init__(self, config_path: str = 'config/integrations.yaml'):
        """
        Инициализация шлюза.

        Аргументы:
            config_path: путь к YAML-конфигу интеграций (относительно корня проекта).
                         Если файл не найден — используются значения по умолчанию.
        """
        self._config_path = _PROJECT_ROOT / config_path
        self._config: Dict[str, Any] = {}
        self._load_config()
        self._tracker = self._init_tracker()

    # ── Инициализация ──

    def _load_config(self) -> None:
        """Загружает конфигурацию из YAML, если файл существует."""
        if not self._config_path.exists():
            logger.debug('Конфиг %s не найден, используются значения по умолчанию', self._config_path)
            return

        try:
            import yaml
            with open(self._config_path, 'r', encoding='utf-8') as f:
                self._config = yaml.safe_load(f) or {}
            logger.info('Конфигурация загружена из %s', self._config_path)
        except ImportError:
            logger.debug('PyYAML не установлен, конфиг пропущен')
        except Exception as exc:
            logger.warning('Ошибка загрузки конфига: %s', exc)

    def _init_tracker(self) -> Optional[Any]:
        """Инициализирует TokenTracker если доступен."""
        try:
            from src.reporting.token_tracker import TokenTracker
            return TokenTracker()
        except Exception:
            logger.debug('TokenTracker недоступен — трекинг отключён')
            return None

    # ── Основные методы ──

    def completion(
        self,
        model_alias: str,
        prompt: str,
        system: Optional[str] = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
    ) -> Dict[str, Any]:
        """
        Единый метод вызова LLM.

        Аргументы:
            model_alias: алиас модели ('flash', 'pro', 'sonnet', 'opus').
            prompt: текст промпта (роль user).
            system: системный промпт (опционально).
            temperature: температура генерации (0.0-1.0).
            max_tokens: максимальное количество токенов ответа.

        Возвращает:
            dict с ключами: content, model, input_tokens, output_tokens, cost, latency_ms.

        Исключения:
            ValueError: если model_alias не распознан.
            RuntimeError: если все попытки исчерпаны.
        """
        if model_alias not in MODEL_MAP:
            raise ValueError(
                f'Неизвестная модель: {model_alias!r}. '
                f'Доступные: {", ".join(MODEL_MAP.keys())}'
            )

        last_error: Optional[Exception] = None

        for attempt in range(MAX_RETRIES):
            try:
                start_ms = time.monotonic() * 1000
                result = self._call_llm(model_alias, prompt, system, temperature, max_tokens)
                latency_ms = time.monotonic() * 1000 - start_ms
                result['latency_ms'] = round(latency_ms, 1)

                # Расчёт стоимости
                result['cost'] = self.get_cost(
                    model_alias, result['input_tokens'], result['output_tokens']
                )

                # Трекинг использования
                self._track_usage(
                    model_alias, result['input_tokens'], result['output_tokens'], result['latency_ms']
                )

                return result

            except Exception as exc:
                last_error = exc
                if attempt < MAX_RETRIES - 1:
                    delay = RETRY_DELAYS[attempt]
                    logger.warning(
                        'Попытка %d/%d для %s не удалась: %s. Повтор через %.1fс',
                        attempt + 1, MAX_RETRIES, model_alias, exc, delay,
                    )
                    time.sleep(delay)

        raise RuntimeError(
            f'Все {MAX_RETRIES} попытки для модели {model_alias!r} исчерпаны. '
            f'Последняя ошибка: {last_error}'
        )

    def completion_with_fallback(
        self,
        model_alias: str,
        prompt: str,
        fallback_chain: Optional[List[str]] = None,
        **kwargs: Any,
    ) -> Dict[str, Any]:
        """
        Вызов LLM с автоматическим fallback при ошибках.

        Если основная модель недоступна, пробует следующую из цепочки.
        По умолчанию цепочка: flash -> pro -> sonnet -> opus.

        Аргументы:
            model_alias: основная модель.
            prompt: текст промпта.
            fallback_chain: список алиасов для fallback (опционально).
            **kwargs: дополнительные аргументы для completion().

        Возвращает:
            dict — результат от первой успешной модели.

        Исключения:
            RuntimeError: если все модели в цепочке недоступны.
        """
        chain = fallback_chain or DEFAULT_FALLBACK_CHAIN

        # Ставим основную модель первой, затем остальные из цепочки
        models_to_try = [model_alias]
        for m in chain:
            if m != model_alias and m not in models_to_try:
                models_to_try.append(m)

        errors: List[str] = []

        for alias in models_to_try:
            try:
                result = self.completion(alias, prompt, **kwargs)
                if alias != model_alias:
                    logger.info(
                        'Fallback: вместо %s использована модель %s', model_alias, alias
                    )
                return result
            except Exception as exc:
                errors.append(f'{alias}: {exc}')
                logger.warning('Модель %s недоступна: %s', alias, exc)

        raise RuntimeError(
            f'Все модели недоступны. Ошибки:\n' + '\n'.join(f'  - {e}' for e in errors)
        )

    def batch_completion(self, requests: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Параллельный вызов нескольких запросов.

        Каждый элемент requests — dict с ключами:
            model_alias (str), prompt (str), и опциональные system, temperature, max_tokens.

        Аргументы:
            requests: список запросов.

        Возвращает:
            список результатов в том же порядке. При ошибке в элементе —
            dict с ключом 'error' вместо 'content'.
        """
        results: List[Optional[Dict[str, Any]]] = [None] * len(requests)

        def _call(index: int, req: Dict[str, Any]) -> tuple:
            try:
                res = self.completion(
                    model_alias=req['model_alias'],
                    prompt=req['prompt'],
                    system=req.get('system'),
                    temperature=req.get('temperature', 0.7),
                    max_tokens=req.get('max_tokens', 4096),
                )
                return index, res
            except Exception as exc:
                return index, {
                    'error': str(exc),
                    'model': req.get('model_alias', '?'),
                    'content': '',
                    'input_tokens': 0,
                    'output_tokens': 0,
                    'cost': 0.0,
                    'latency_ms': 0.0,
                }

        if not requests:
            return []

        max_workers = max(1, min(len(requests), 4))
        with ThreadPoolExecutor(max_workers=max_workers) as pool:
            futures = [pool.submit(_call, i, req) for i, req in enumerate(requests)]
            for future in as_completed(futures):
                idx, res = future.result()
                results[idx] = res

        return results  # type: ignore[return-value]

    def get_cost(self, model_alias: str, input_tokens: int, output_tokens: int) -> float:
        """
        Расчёт стоимости вызова в USD.

        Аргументы:
            model_alias: алиас модели.
            input_tokens: количество входных токенов.
            output_tokens: количество выходных токенов.

        Возвращает:
            стоимость в долларах.
        """
        pricing = MODEL_PRICING.get(model_alias)
        if not pricing:
            return 0.0
        return (input_tokens * pricing['input'] + output_tokens * pricing['output']) / 1_000_000

    def list_models(self) -> List[Dict[str, Any]]:
        """
        Список доступных моделей с метаданными.

        Возвращает:
            список словарей с ключами: alias, model_id, pricing, available.
        """
        models = []
        for alias, model_id in MODEL_MAP.items():
            models.append({
                'alias': alias,
                'model_id': model_id,
                'pricing': MODEL_PRICING.get(alias, {}),
                'available': self._check_model_available(alias),
            })
        return models

    # ── Внутренние методы ──

    def _call_llm(
        self,
        model_alias: str,
        prompt: str,
        system: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        """
        Фактический вызов LLM — через litellm или fallback на shell.

        Возвращает:
            dict с ключами: content, model, input_tokens, output_tokens.
        """
        if _HAS_LITELLM:
            return self._call_via_litellm(model_alias, prompt, system, temperature, max_tokens)
        return self._call_via_shell(model_alias, prompt, max_tokens)

    def _call_via_litellm(
        self,
        model_alias: str,
        prompt: str,
        system: Optional[str],
        temperature: float,
        max_tokens: int,
    ) -> Dict[str, Any]:
        """Вызов через библиотеку litellm."""
        model_id = MODEL_MAP[model_alias]

        messages = []
        if system:
            messages.append({'role': 'system', 'content': system})
        messages.append({'role': 'user', 'content': prompt})

        response = litellm.completion(
            model=model_id,
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens,
        )

        usage = response.usage
        content = response.choices[0].message.content or ''

        return {
            'content': content,
            'model': model_alias,
            'input_tokens': usage.prompt_tokens,
            'output_tokens': usage.completion_tokens,
        }

    def _call_via_shell(
        self,
        model_alias: str,
        prompt: str,
        max_tokens: int,
    ) -> Dict[str, Any]:
        """
        Fallback: вызов через shell-скрипты gemini-bridge.sh / sonnet-bridge.sh.

        Используется когда litellm не установлен.
        """
        if model_alias in ('flash', 'pro'):
            script = str(_GEMINI_BRIDGE)
            cmd = ['bash', script, model_alias, prompt]
        elif model_alias in ('sonnet', 'opus'):
            script = str(_SONNET_BRIDGE)
            cmd = ['bash', script, prompt, str(max_tokens)]
        else:
            raise ValueError(f'Нет shell-fallback для модели: {model_alias}')

        if not Path(script).exists():
            raise FileNotFoundError(f'Shell-мост не найден: {script}')

        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            cwd=str(_PROJECT_ROOT),
        )

        if result.returncode != 0:
            stderr = result.stderr.strip()
            raise RuntimeError(f'Shell-вызов завершился с ошибкой: {stderr or "код " + str(result.returncode)}')

        content = result.stdout.strip()

        # Оценка токенов (4 символа ~ 1 токен)
        input_tokens = max(len(prompt) // 4, 1)
        output_tokens = max(len(content) // 4, 1)

        return {
            'content': content,
            'model': model_alias,
            'input_tokens': input_tokens,
            'output_tokens': output_tokens,
        }

    def _track_usage(
        self,
        model: str,
        input_tokens: int,
        output_tokens: int,
        latency_ms: float,
    ) -> None:
        """
        Запись использования в TokenTracker если доступен.

        Аргументы:
            model: алиас модели.
            input_tokens: входные токены.
            output_tokens: выходные токены.
            latency_ms: задержка в миллисекундах.
        """
        if self._tracker is None:
            return

        try:
            # Ищем активную задачу в трекинг-директории
            tracking_dir = _PROJECT_ROOT / '.claude' / 'tracking'
            task_id = self._find_active_task_id(tracking_dir)
            if task_id:
                self._tracker.record_call(
                    task_id,
                    model=model,
                    role='gateway',
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                )
                logger.debug(
                    'Трекинг: %s in=%d out=%d latency=%.0fms',
                    model, input_tokens, output_tokens, latency_ms,
                )
        except Exception as exc:
            logger.debug('Ошибка трекинга: %s', exc)

    @staticmethod
    def _find_active_task_id(tracking_dir: Path) -> Optional[str]:
        """Ищет ID активной задачи в директории трекинга."""
        if not tracking_dir.exists():
            return None

        # Находим последний tracking-файл (формат: task_YYYYMMDD_HHMMSS_XXXXXX)
        task_files = sorted(tracking_dir.glob('task_*'), reverse=True)
        for f in task_files:
            name = f.name
            if name.startswith('task_'):
                return name[5:]  # Убираем префикс 'task_'
        return None

    def _check_model_available(self, model_alias: str) -> bool:
        """Проверяет доступность модели (наличие API-ключей)."""
        if model_alias in ('flash', 'pro'):
            return bool(os.environ.get('GOOGLE_API_KEY') or os.environ.get('GEMINI_API_KEY'))
        if model_alias in ('sonnet', 'opus'):
            return bool(os.environ.get('ANTHROPIC_API_KEY'))
        return False
