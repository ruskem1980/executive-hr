#!/usr/bin/env python3
"""
Исправляет функцию t() на странице /services чтобы она делала двойную трансляцию.

Проблема: локальная функция t() возвращает значение из labels[key][language],
но это значение само является ключом перевода (например '(main).page.сервисы').

Решение: если значение похоже на ключ перевода, передать его в глобальный t().
"""

from pathlib import Path

def fix_services_t_function():
    """Исправляет локальную функцию t() для двойной трансляции."""
    file_path = Path('apps/frontend/src/app/(main)/services/page.tsx')
    content = file_path.read_text(encoding='utf-8')

    # Находим и заменяем локальную функцию t()
    old_function = """  const t = (key: string): string => {
    return labels[key]?.[language] || labels[key]?.ru || key;
  };"""

    new_function = """  // Глобальный t из useTranslation
  const { t: globalT } = useTranslation();

  // Локальная функция с двойной трансляцией
  const t = (key: string): string => {
    const value = labels[key]?.[language] || labels[key]?.ru || key;

    // Если значение похоже на ключ перевода - передаём в глобальный t()
    if (value.includes('.') || value.startsWith('(')) {
      return globalT(value);
    }

    return value;
  };"""

    if old_function in content:
        content = content.replace(old_function, new_function)
        file_path.write_text(content, encoding='utf-8')
        print(f"✅ Исправлено: {file_path}")
        return True
    else:
        print(f"⚠️  Функция t() не найдена или уже изменена в {file_path}")
        return False

def main():
    print("🔧 ИСПРАВЛЕНИЕ ДВОЙНОЙ ТРАНСЛЯЦИИ НА /services")
    print("=" * 60)

    if fix_services_t_function():
        print("\n✅ Готово! Перезагрузите страницу в браузере.")
    else:
        print("\n⚠️  Не удалось применить исправление")

if __name__ == '__main__':
    main()
