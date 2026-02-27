"""
i18n - Система интернационализации и проверки переводов.

Модули:
- scanner: AST-сканер для извлечения строк из исходного кода
- catalog: Управление каталогами переводов (JSON per locale)
- translator: Профессиональный перевод через LLM
- validator: Проверка полноты покрытия переводами
- manager: CLI-оркестратор pipeline сканирование -> перевод -> валидация
"""

from pathlib import Path
from typing import Optional

_LOCALES_DIR = Path(__file__).parent / "locales"
_current_locale = "ru"
_catalog_cache: dict = {}


def set_locale(locale: str) -> None:
    """Устанавливает текущую локаль."""
    global _current_locale, _catalog_cache
    _current_locale = locale
    _catalog_cache = {}


def get_locale() -> str:
    """Возвращает текущую локаль."""
    return _current_locale


def t(key: str, **kwargs) -> str:
    """
    Переводит строку по ключу.

    Args:
        key: Ключ перевода (обычно оригинальная строка)
        **kwargs: Параметры для форматирования

    Returns:
        Переведённая строка или оригинальный ключ если перевод не найден
    """
    global _catalog_cache

    if _current_locale not in _catalog_cache:
        from .catalog import TranslationCatalog
        catalog = TranslationCatalog(_LOCALES_DIR)
        _catalog_cache[_current_locale] = catalog.load(_current_locale)

    translations = _catalog_cache.get(_current_locale, {})
    result = translations.get(key, key)

    if kwargs:
        try:
            result = result.format(**kwargs)
        except (KeyError, IndexError):
            pass

    return result
