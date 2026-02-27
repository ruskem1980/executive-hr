#!/usr/bin/env python3
"""
Translator - профессиональный перевод строк через LLM.

Использует LLM ТОЛЬКО для обеспечения качественного перевода.
Оптимизирует расход токенов через:
- Батчинг строк (до 50 за запрос)
- Кеширование уже переведённых
- Автоматический перевод тривиальных строк без LLM
- Контекстные подсказки для LLM (категория, файл, плейсхолдеры)

Поддерживаемые backend'ы:
- Gemini (через gemini-bridge.sh) - дешёвый
- OpenAI API (через requests)
- Anthropic API (через requests)
- Ollama (локальный)
"""

import json
import re
import subprocess
import time
import os
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass

from .catalog import TranslationCatalog, TranslationEntry
from .scanner import detect_language


# Словарь тривиальных переводов (без LLM)
TRIVIAL_TRANSLATIONS = {
    "ru_to_en": {
        # Уровни критичности
        "CRITICAL": "CRITICAL", "HIGH": "HIGH", "MEDIUM": "MEDIUM", "LOW": "LOW",
        # Статусы
        "completed": "completed", "failed": "failed", "error": "error",
        "passed": "passed", "skipped": "skipped", "timeout": "timeout",
        # Технические
        "unknown": "unknown", "none": "none", "N/A": "N/A",
    },
    "en_to_ru": {
        "CRITICAL": "КРИТИЧЕСКИЙ",
        "HIGH": "ВЫСОКИЙ",
        "MEDIUM": "СРЕДНИЙ",
        "LOW": "НИЗКИЙ",
        "completed": "завершено",
        "failed": "провалено",
        "error": "ошибка",
        "passed": "пройдено",
        "skipped": "пропущено",
        "timeout": "тайм-аут",
        "unknown": "неизвестно",
        "Found": "Найдено",
        "issues": "проблем",
        "including": "включая",
        "Address CRITICAL issues immediately": "Немедленно устраните КРИТИЧЕСКИЕ проблемы",
        "Consider incremental refactoring": "Рекомендуется постепенный рефакторинг",
        "Run security audit before deployment": "Проведите аудит безопасности перед развёртыванием",
        "review code": "проверьте код",
        "use env vars": "используйте переменные окружения",
        "use secrets module": "используйте модуль secrets",
        "validate SSL certificates": "проверяйте SSL сертификаты",
        "parameterize queries": "параметризуйте запросы",
        "Reduce cyclomatic complexity in identified functions":
            "Снизьте цикломатическую сложность в указанных функциях",
        "Consider caching expensive operations":
            "Рассмотрите кеширование ресурсоёмких операций",
        "Profile runtime with py-spy or cProfile":
            "Профилируйте время выполнения с помощью py-spy или cProfile",
        "Focus on CRITICAL priority files first":
            "Сначала обратите внимание на файлы с приоритетом CRITICAL",
        "Add unit tests for uncovered code paths":
            "Добавьте юнит-тесты для непокрытых путей кода",
        "Review integration test coverage":
            "Проверьте покрытие интеграционными тестами",
    }
}


@dataclass
class TranslationConfig:
    """Конфигурация переводчика."""
    backend: str = "gemini"         # gemini | openai | anthropic | ollama
    model: str = "flash"            # flash | pro | gpt-4o-mini | etc.
    batch_size: int = 30            # Строк за один запрос к LLM
    rate_limit_delay: float = 1.0   # Пауза между запросами (секунды)
    max_retries: int = 3            # Макс. попыток при ошибке
    temperature: float = 0.3        # Низкая = более точный перевод
    gemini_bridge_path: str = ""    # Путь к gemini-bridge.sh
    api_key: str = ""               # API ключ (для openai/anthropic)
    ollama_url: str = "http://localhost:11434"  # URL Ollama


class LLMTranslator:
    """
    Переводчик строк через LLM.

    Использует LLM только для непереведённых строк,
    оптимизируя расход токенов через батчинг и тривиальные словари.
    """

    def __init__(self, config: Optional[TranslationConfig] = None):
        self.config = config or TranslationConfig()
        self._setup_backend()

    def _setup_backend(self):
        """Настраивает backend для LLM вызовов."""
        if self.config.backend == "gemini":
            if not self.config.gemini_bridge_path:
                self.config.gemini_bridge_path = str(
                    Path(__file__).parent.parent.parent / ".claude" / "helpers" / "gemini-bridge.sh"
                )
        elif self.config.backend == "openai":
            if not self.config.api_key:
                self.config.api_key = os.environ.get("OPENAI_API_KEY", "")
        elif self.config.backend == "anthropic":
            if not self.config.api_key:
                self.config.api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    def translate_catalog(self, catalog: TranslationCatalog,
                          source_locale: str, target_locale: str,
                          force: bool = False) -> Dict[str, int]:
        """
        Переводит все непереведённые строки каталога.

        Args:
            catalog: Каталог переводов
            source_locale: Исходный язык (ru, en)
            target_locale: Целевой язык (en, ru, de, etc.)
            force: Перезаписать существующие переводы

        Returns:
            Dict со статистикой: trivial, llm, errors, skipped
        """
        entries = catalog.load_full(target_locale)
        if not entries:
            # Если каталог целевого языка пуст, копируем из исходного
            source_entries = catalog.load_full(source_locale)
            entries = {
                k: TranslationEntry(
                    original=v.original,
                    translated="",
                    category=v.category,
                    source_file=v.source_file,
                    source_line=v.source_line,
                    status="pending",
                    context=v.context,
                    has_placeholders=v.has_placeholders,
                )
                for k, v in source_entries.items()
            }

        stats = {"trivial": 0, "llm": 0, "errors": 0, "skipped": 0, "total": len(entries)}

        # Разделяем на тривиальные и требующие LLM
        trivial_entries = []
        llm_entries = []

        direction = f"{source_locale}_to_{target_locale}"
        trivial_dict = TRIVIAL_TRANSLATIONS.get(direction, {})

        for key, entry in entries.items():
            if entry.translated and not force:
                stats["skipped"] += 1
                continue

            if key in trivial_dict:
                entry.translated = trivial_dict[key]
                entry.status = "translated"
                entry.translator = "trivial_dict"
                trivial_entries.append(entry)
                stats["trivial"] += 1
            else:
                llm_entries.append(entry)

        # Батчим LLM переводы
        if llm_entries:
            print(f"\n  Перевод {len(llm_entries)} строк через LLM ({self.config.backend})...")
            batches = self._create_batches(llm_entries, self.config.batch_size)

            for i, batch in enumerate(batches):
                print(f"    Батч {i+1}/{len(batches)} ({len(batch)} строк)...")
                try:
                    translations = self._translate_batch(
                        batch, source_locale, target_locale
                    )
                    for entry, translation in zip(batch, translations):
                        if translation:
                            entry.translated = translation
                            entry.status = "translated"
                            entry.translator = f"llm:{self.config.backend}"
                            stats["llm"] += 1
                        else:
                            stats["errors"] += 1

                    # Rate limiting
                    if i < len(batches) - 1:
                        time.sleep(self.config.rate_limit_delay)

                except Exception as e:
                    print(f"    Ошибка батча {i+1}: {e}")
                    stats["errors"] += len(batch)

        # Сохраняем
        catalog.save(target_locale, entries)

        return stats

    def translate_single(self, text: str, source_locale: str,
                         target_locale: str, context: str = "") -> str:
        """
        Переводит одну строку через LLM.

        Args:
            text: Исходный текст
            source_locale: Язык оригинала
            target_locale: Целевой язык
            context: Контекст для переводчика

        Returns:
            Переведённая строка
        """
        # Проверяем тривиальный словарь
        direction = f"{source_locale}_to_{target_locale}"
        trivial = TRIVIAL_TRANSLATIONS.get(direction, {})
        if text in trivial:
            return trivial[text]

        # LLM перевод
        prompt = self._build_single_prompt(text, source_locale, target_locale, context)
        response = self._call_llm(prompt)
        return self._extract_translation(response, text)

    def _translate_batch(self, entries: List[TranslationEntry],
                         source_locale: str, target_locale: str) -> List[str]:
        """Переводит батч строк через один вызов LLM."""
        prompt = self._build_batch_prompt(entries, source_locale, target_locale)
        response = self._call_llm(prompt)
        return self._parse_batch_response(response, len(entries))

    def _build_batch_prompt(self, entries: List[TranslationEntry],
                            source_locale: str, target_locale: str) -> str:
        """Строит промпт для батчевого перевода."""
        locale_names = {
            "ru": "русский", "en": "английский", "de": "немецкий",
            "fr": "французский", "es": "испанский", "zh": "китайский",
            "ja": "японский", "ko": "корейский", "pt": "португальский",
            "it": "итальянский", "ar": "арабский", "hi": "хинди",
        }

        source_name = locale_names.get(source_locale, source_locale)
        target_name = locale_names.get(target_locale, target_locale)

        lines = []
        for i, entry in enumerate(entries, 1):
            ctx = ""
            if entry.context:
                ctx = f" [контекст: {entry.context}]"
            if entry.has_placeholders:
                ctx += " [СОХРАНИ плейсхолдеры {{...}} как есть!]"
            lines.append(f"{i}. {entry.original}{ctx}")

        strings_block = "\n".join(lines)

        prompt = f"""Ты профессиональный переводчик IT-документации и интерфейсов.
Переведи строки с {source_name} на {target_name}.

ПРАВИЛА:
1. Сохраняй технические термины как есть (API, SQL, JSON, pytest, bandit и т.д.)
2. Сохраняй плейсхолдеры {{...}}, %s, {{name}} без изменений
3. Сохраняй эмодзи и спецсимволы (✅ ❌ ⚠️ 🔴 🟡 🟢)
4. Сохраняй форматирование (переносы строк, отступы)
5. Переводи естественно и профессионально, не дословно
6. Для IT-терминов используй принятые в отрасли переводы

СТРОКИ ДЛЯ ПЕРЕВОДА:
{strings_block}

ФОРМАТ ОТВЕТА: ТОЛЬКО JSON массив строк, без объяснений.
Пример: ["перевод 1", "перевод 2", "перевод 3"]

Верни РОВНО {len(entries)} переводов в том же порядке."""

        return prompt

    def _build_single_prompt(self, text: str, source_locale: str,
                             target_locale: str, context: str = "") -> str:
        """Строит промпт для перевода одной строки."""
        locale_names = {
            "ru": "русский", "en": "английский", "de": "немецкий",
            "fr": "французский", "es": "испанский",
        }
        source_name = locale_names.get(source_locale, source_locale)
        target_name = locale_names.get(target_locale, target_locale)

        ctx_note = f"\nКонтекст: {context}" if context else ""

        return f"""Переведи с {source_name} на {target_name}.
Сохраняй технические термины, плейсхолдеры и эмодзи.{ctx_note}

Текст: {text}

Верни ТОЛЬКО перевод, без пояснений."""

    def _call_llm(self, prompt: str) -> str:
        """Вызывает LLM backend."""
        for attempt in range(self.config.max_retries):
            try:
                if self.config.backend == "gemini":
                    return self._call_gemini(prompt)
                elif self.config.backend == "openai":
                    return self._call_openai(prompt)
                elif self.config.backend == "anthropic":
                    return self._call_anthropic(prompt)
                elif self.config.backend == "ollama":
                    return self._call_ollama(prompt)
                else:
                    raise ValueError(f"Неизвестный backend: {self.config.backend}")
            except Exception as e:
                if attempt < self.config.max_retries - 1:
                    wait = (attempt + 1) * 2
                    print(f"    Ошибка LLM (попытка {attempt+1}): {e}. Повтор через {wait}с...")
                    time.sleep(wait)
                else:
                    raise

    def _call_gemini(self, prompt: str) -> str:
        """Вызывает Gemini через bridge скрипт."""
        bridge_path = self.config.gemini_bridge_path

        if not Path(bridge_path).exists():
            # Fallback на прямой вызов gemini CLI
            try:
                result = subprocess.run(
                    ["gemini", "-m", f"gemini-2.5-{self.config.model}", "-p", prompt],
                    capture_output=True, text=True, timeout=120
                )
                if result.returncode == 0:
                    return result.stdout.strip()
                raise Exception(f"Gemini CLI error: {result.stderr}")
            except FileNotFoundError:
                raise Exception(
                    "Gemini CLI не найден. Установите: pip install google-genai"
                )

        result = subprocess.run(
            ["bash", bridge_path, self.config.model, prompt],
            capture_output=True, text=True, timeout=120
        )
        if result.returncode == 0:
            return result.stdout.strip()
        raise Exception(f"Gemini bridge error: {result.stderr}")

    def _call_openai(self, prompt: str) -> str:
        """Вызывает OpenAI API."""
        import urllib.request

        model = self.config.model or "gpt-4o-mini"
        data = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.config.temperature,
        }).encode()

        req = urllib.request.Request(
            "https://api.openai.com/v1/chat/completions",
            data=data,
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.config.api_key}",
            }
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result["choices"][0]["message"]["content"].strip()

    def _call_anthropic(self, prompt: str) -> str:
        """Вызывает Anthropic API."""
        import urllib.request

        model = self.config.model or "claude-haiku-4-5-20251001"
        data = json.dumps({
            "model": model,
            "max_tokens": 4096,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": self.config.temperature,
        }).encode()

        req = urllib.request.Request(
            "https://api.anthropic.com/v1/messages",
            data=data,
            headers={
                "Content-Type": "application/json",
                "x-api-key": self.config.api_key,
                "anthropic-version": "2023-06-01",
            }
        )

        with urllib.request.urlopen(req, timeout=120) as resp:
            result = json.loads(resp.read())
            return result["content"][0]["text"].strip()

    def _call_ollama(self, prompt: str) -> str:
        """Вызывает Ollama (локальный LLM)."""
        import urllib.request

        model = self.config.model or "llama3"
        data = json.dumps({
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": self.config.temperature},
        }).encode()

        req = urllib.request.Request(
            f"{self.config.ollama_url}/api/generate",
            data=data,
            headers={"Content-Type": "application/json"},
        )

        with urllib.request.urlopen(req, timeout=300) as resp:
            result = json.loads(resp.read())
            return result["response"].strip()

    def _parse_batch_response(self, response: str, expected_count: int) -> List[str]:
        """Парсит ответ батчевого перевода."""
        # Убираем markdown блоки
        cleaned = response.strip()
        if cleaned.startswith("```"):
            cleaned = re.sub(r'```(?:json)?\n?', '', cleaned).strip()

        try:
            translations = json.loads(cleaned)
            if isinstance(translations, list):
                # Добиваем до нужной длины пустыми строками
                while len(translations) < expected_count:
                    translations.append("")
                return translations[:expected_count]
        except json.JSONDecodeError:
            pass

        # Fallback: парсим построчно (если LLM вернул не JSON)
        lines = []
        for line in cleaned.splitlines():
            line = line.strip()
            # Убираем нумерацию "1. " или "1) "
            line = re.sub(r'^\d+[\.\)]\s*', '', line)
            # Убираем кавычки
            line = line.strip('"\'')
            if line:
                lines.append(line)

        while len(lines) < expected_count:
            lines.append("")
        return lines[:expected_count]

    def _extract_translation(self, response: str, original: str) -> str:
        """Извлекает перевод из ответа на одиночный запрос."""
        cleaned = response.strip()
        # Убираем кавычки если обёрнут
        if (cleaned.startswith('"') and cleaned.endswith('"')) or \
           (cleaned.startswith("'") and cleaned.endswith("'")):
            cleaned = cleaned[1:-1]
        return cleaned or original

    @staticmethod
    def _create_batches(items: List, batch_size: int) -> List[List]:
        """Разбивает список на батчи."""
        return [items[i:i + batch_size] for i in range(0, len(items), batch_size)]
