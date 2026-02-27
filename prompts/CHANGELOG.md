# Prompt Templates Changelog

Версионирование изменений в prompt templates для отслеживания эволюции промптов.

## Version 1.0.0 - MVP (2026-02-13)

### Добавлено
- `base_coder.md` - Базовый промпт для coder агента
- `complexity_additions.json` - Дополнения под complexity (simple/medium/complex/very_complex)
- `context_additions.json` - Дополнения под контекст (security/performance/api/testing/frontend/refactoring)
- Система layered prompts (базовый + complexity + context)

### Метрики (baseline)
- Success rate: N/A (первая версия)
- Quality score: N/A
- User satisfaction: N/A

### Reasoning
Первая версия prompt templates для MVP. Фокус на:
1. Чистый код и best practices
2. Адаптивность под complexity
3. Context-aware instructions
4. Безопасность и производительность

---

## Формат для будущих версий

### Version X.Y.Z - Description (YYYY-MM-DD)

#### Изменения
- Что изменилось в промптах
- Какие additions добавлены/убраны
- Почему сделаны изменения

#### Метрики после изменений
- Success rate: X%
- Quality score: Y/10
- User satisfaction: Z/10
- A/B test results: победа/поражение

#### Reasoning
Объяснение почему изменения улучшают качество результатов.

---

## Guidelines для изменений промптов

1. **A/B Testing**: Всегда тестируй новые промпты против старых
2. **Incremental**: Меняй по одному аспекту за раз
3. **Measurable**: Определяй метрики ДО внесения изменений
4. **Rollback-ready**: Храни предыдущие версии для возможного отката
5. **Document**: Записывай reasoning для каждого изменения
