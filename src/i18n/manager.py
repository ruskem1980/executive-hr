#!/usr/bin/env python3
"""
Manager - CLI-оркестратор для pipeline перевода.

Команды:
  scan       Сканирует проект, извлекает строки
  translate  Переводит непереведённые строки через LLM
  validate   Валидирует полноту и качество переводов
  report     Генерирует отчёт о состоянии переводов
  pipeline   Запускает полный pipeline: scan -> translate -> validate
  export     Экспортирует строки для внешнего переводчика
  import     Импортирует переводы из внешнего файла
  stats      Показывает статистику каталога

Использование:
  python -m src.i18n.manager scan --project-root . --output src/i18n/locales/
  python -m src.i18n.manager translate --locale en --backend gemini
  python -m src.i18n.manager validate --source ru --target en
  python -m src.i18n.manager pipeline --source ru --target en
"""

import argparse
import json
import sys
import time
from pathlib import Path
from typing import Optional
from dataclasses import asdict


def get_project_root() -> Path:
    """Определяет корень проекта."""
    # Ищем CLAUDE.md или .git
    current = Path.cwd()
    for parent in [current] + list(current.parents):
        if (parent / "CLAUDE.md").exists() or (parent / ".git").exists():
            return parent
    return current


def cmd_scan(args):
    """Команда: сканирование проекта."""
    from .scanner import ProjectScanner

    project_root = Path(args.project_root)
    scanner = ProjectScanner(project_root)

    print(f"\n🔍 Сканирование проекта: {project_root}")
    print(f"   Расширения: {', '.join(args.extensions)}")

    strings = scanner.scan(extensions=args.extensions)
    report = scanner.generate_report(strings)

    print(f"\n{'='*60}")
    print(f"  Найдено переводимых строк: {report['total_strings']}")
    print(f"{'='*60}")

    print(f"\n  По категориям:")
    for cat, count in sorted(report['by_category'].items()):
        print(f"    {cat:<25} {count}")

    print(f"\n  По языкам:")
    for lang, count in sorted(report['by_language'].items()):
        print(f"    {lang:<10} {count}")

    print(f"\n  По файлам:")
    for f, count in sorted(report['by_file'].items(), key=lambda x: -x[1]):
        print(f"    {f:<40} {count}")

    print(f"\n  С плейсхолдерами: {report['with_placeholders']}")

    # Экспорт в JSON
    if args.output:
        output = Path(args.output) / "extracted_strings.json"
        scanner.export_strings(strings, output)

    # Merge с каталогами
    if args.merge_locale:
        from .catalog import TranslationCatalog
        locales_dir = Path(args.output) if args.output else project_root / "src" / "i18n" / "locales"
        catalog = TranslationCatalog(locales_dir)

        scanned_dicts = [asdict(s) for s in strings]
        new, existing, removed = catalog.merge_scanned_strings(
            args.merge_locale, scanned_dicts
        )
        print(f"\n  Merge с каталогом '{args.merge_locale}':")
        print(f"    Новых строк:      {new}")
        print(f"    Существующих:     {existing}")
        print(f"    Удалённых из кода: {removed}")

    return strings


def cmd_translate(args):
    """Команда: перевод через LLM."""
    from .catalog import TranslationCatalog
    from .translator import LLMTranslator, TranslationConfig

    locales_dir = Path(args.locales_dir)
    catalog = TranslationCatalog(locales_dir)

    config = TranslationConfig(
        backend=args.backend,
        model=args.model,
        batch_size=args.batch_size,
        rate_limit_delay=args.rate_delay,
    )

    if args.bridge_path:
        config.gemini_bridge_path = args.bridge_path
    if args.api_key:
        config.api_key = args.api_key

    translator = LLMTranslator(config)

    print(f"\n🌐 Перевод: {args.source_locale} -> {args.target_locale}")
    print(f"   Backend: {args.backend} ({args.model})")
    print(f"   Батч: {args.batch_size} строк")

    start = time.time()
    stats = translator.translate_catalog(
        catalog,
        source_locale=args.source_locale,
        target_locale=args.target_locale,
        force=args.force,
    )
    elapsed = time.time() - start

    print(f"\n{'='*60}")
    print(f"  Результат перевода ({elapsed:.1f}с):")
    print(f"    Всего строк:      {stats['total']}")
    print(f"    Тривиальных:      {stats['trivial']}")
    print(f"    Через LLM:        {stats['llm']}")
    print(f"    Пропущено:        {stats['skipped']}")
    print(f"    Ошибок:           {stats['errors']}")
    print(f"{'='*60}\n")


def cmd_validate(args):
    """Команда: валидация переводов."""
    from .catalog import TranslationCatalog
    from .validator import TranslationValidator

    locales_dir = Path(args.locales_dir)
    catalog = TranslationCatalog(locales_dir)
    project_root = Path(args.project_root)

    validator = TranslationValidator(catalog, project_root)

    print(f"\n✅ Валидация переводов: {args.source_locale} -> {args.target_locale}")

    # Фаза 1: Алгоритмическая
    report = validator.validate(
        source_locale=args.source_locale,
        target_locale=args.target_locale,
        sample_size=args.sample_size,
    )

    # Фаза 2: LLM проверка (если не отключена)
    if not args.no_llm and report.sample_for_review:
        print(f"\n  🤖 LLM-проверка ({len(report.sample_for_review)} строк)...")
        bridge_path = args.bridge_path or ""
        report = validator.llm_review(
            report,
            source_locale=args.source_locale,
            target_locale=args.target_locale,
            llm_backend=args.llm_backend,
            llm_model=args.llm_model,
            gemini_bridge_path=bridge_path,
        )

        # Применяем исправления
        if report.llm_corrections and args.auto_fix:
            applied = validator.apply_corrections(
                report, args.target_locale, auto_apply=True
            )
            print(f"  Применено исправлений: {applied}")

    # Вывод отчёта
    validator.print_report(report)

    # Сохранение отчёта
    if args.output:
        output_path = Path(args.output)
        validator.save_report(report, output_path)

    return report


def cmd_pipeline(args):
    """Команда: полный pipeline scan -> translate -> validate."""
    print(f"\n{'='*70}")
    print(f"  🚀 ПОЛНЫЙ PIPELINE ПЕРЕВОДА")
    print(f"  {args.source_locale} -> {args.target_locale}")
    print(f"{'='*70}")

    project_root = Path(args.project_root)
    locales_dir = project_root / "src" / "i18n" / "locales"

    # === ШАГ 1: Сканирование ===
    print(f"\n{'─'*40}")
    print(f"  ШАГ 1/3: Сканирование")
    print(f"{'─'*40}")

    from .scanner import ProjectScanner
    from .catalog import TranslationCatalog

    scanner = ProjectScanner(project_root)
    strings = scanner.scan()
    report = scanner.generate_report(strings)
    print(f"  Найдено строк: {report['total_strings']}")

    # Merge с обоими каталогами
    catalog = TranslationCatalog(locales_dir)
    scanned_dicts = [asdict(s) for s in strings]

    for locale in [args.source_locale, args.target_locale]:
        new, existing, removed = catalog.merge_scanned_strings(locale, scanned_dicts)
        print(f"  [{locale}] Новых: {new}, Существующих: {existing}, Удалённых: {removed}")

    # === ШАГ 2: Перевод ===
    print(f"\n{'─'*40}")
    print(f"  ШАГ 2/3: Перевод через LLM")
    print(f"{'─'*40}")

    from .translator import LLMTranslator, TranslationConfig

    config = TranslationConfig(
        backend=args.backend,
        model=args.model,
        batch_size=args.batch_size,
        rate_limit_delay=args.rate_delay,
    )
    if args.bridge_path:
        config.gemini_bridge_path = args.bridge_path

    translator = LLMTranslator(config)
    stats = translator.translate_catalog(
        catalog,
        source_locale=args.source_locale,
        target_locale=args.target_locale,
    )
    print(f"  LLM: {stats['llm']}, Тривиальных: {stats['trivial']}, "
          f"Ошибок: {stats['errors']}")

    # === ШАГ 3: Валидация ===
    print(f"\n{'─'*40}")
    print(f"  ШАГ 3/3: Валидация")
    print(f"{'─'*40}")

    from .validator import TranslationValidator

    validator = TranslationValidator(catalog, project_root)
    val_report = validator.validate(
        source_locale=args.source_locale,
        target_locale=args.target_locale,
        sample_size=args.sample_size,
    )

    # LLM-проверка
    if not args.no_llm and val_report.sample_for_review:
        print(f"  🤖 LLM-проверка качества...")
        bridge_path = args.bridge_path or ""
        val_report = validator.llm_review(
            val_report,
            source_locale=args.source_locale,
            target_locale=args.target_locale,
            llm_backend=args.backend,
            llm_model=args.model if args.model != "flash" else "pro",
            gemini_bridge_path=bridge_path,
        )

        if val_report.llm_corrections and args.auto_fix:
            applied = validator.apply_corrections(
                val_report, args.target_locale, auto_apply=True
            )
            print(f"  Применено LLM-исправлений: {applied}")

    # Вывод итогового отчёта
    validator.print_report(val_report)

    # Сохраняем отчёт
    report_path = project_root / "src" / "i18n" / "locales" / "validation_report.json"
    validator.save_report(val_report, report_path)

    # Итого
    print(f"\n{'='*70}")
    if val_report.is_complete:
        print(f"  ✅ Pipeline завершён успешно! Покрытие: {val_report.coverage_percent}%")
    else:
        print(f"  ⚠️  Pipeline завершён. Покрытие: {val_report.coverage_percent}%")
        print(f"     Не переведено: {val_report.missing_count} строк")
        if val_report.has_critical_issues:
            print(f"     Критических проблем: {val_report.by_severity.get('critical', 0)}")
    print(f"{'='*70}\n")


def cmd_stats(args):
    """Команда: статистика каталога."""
    from .catalog import TranslationCatalog

    locales_dir = Path(args.locales_dir)
    catalog = TranslationCatalog(locales_dir)

    locales = catalog.list_locales()
    if not locales:
        print("\n  Каталоги переводов не найдены.")
        print(f"  Директория: {locales_dir}")
        return

    print(f"\n📊 Статистика переводов")
    print(f"   Директория: {locales_dir}")
    print(f"   Локали: {', '.join(locales)}\n")

    for locale in locales:
        stats = catalog.get_stats(locale)
        print(f"  [{locale.upper()}]")
        print(f"    Всего: {stats['total']}, Переведено: {stats['translated']}, "
              f"Ожидают: {stats['pending']}")
        print(f"    Покрытие: {stats['coverage']}%")

        if stats.get('by_category'):
            print(f"    По категориям:")
            for cat, data in sorted(stats['by_category'].items()):
                print(f"      {cat:<20} {data.get('coverage', 0)}% "
                      f"({data.get('translated', 0)}/{data.get('total', 0)})")
        print()


def cmd_export(args):
    """Команда: экспорт для внешнего переводчика."""
    from .catalog import TranslationCatalog

    locales_dir = Path(args.locales_dir)
    catalog = TranslationCatalog(locales_dir)

    output = Path(args.output)
    catalog.export_for_translation(
        args.locale, output,
        only_pending=not args.all
    )


def cmd_import(args):
    """Команда: импорт переводов."""
    from .catalog import TranslationCatalog

    locales_dir = Path(args.locales_dir)
    catalog = TranslationCatalog(locales_dir)

    import_path = Path(args.input)
    count = catalog.import_translations(args.locale, import_path)
    print(f"\n  Импортировано {count} переводов для локали '{args.locale}'")


def build_parser() -> argparse.ArgumentParser:
    """Строит парсер аргументов."""
    parser = argparse.ArgumentParser(
        prog="i18n-manager",
        description="Управление переводами проекта PT_Standart",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Примеры:
  # Полный pipeline
  python -m src.i18n.manager pipeline --source ru --target en

  # Только сканирование
  python -m src.i18n.manager scan --merge-locale ru

  # Только перевод
  python -m src.i18n.manager translate --source ru --target en --backend gemini

  # Только валидация
  python -m src.i18n.manager validate --source ru --target en

  # Статистика
  python -m src.i18n.manager stats
        """
    )

    subparsers = parser.add_subparsers(dest="command", help="Команда")

    # === scan ===
    p_scan = subparsers.add_parser("scan", help="Сканировать проект")
    p_scan.add_argument("--project-root", default=".", help="Корень проекта")
    p_scan.add_argument("--output", default="", help="Директория для результатов")
    p_scan.add_argument("--extensions", nargs="+", default=[".py", ".yaml", ".yml"],
                        help="Расширения файлов")
    p_scan.add_argument("--merge-locale", default="",
                        help="Merge с каталогом указанной локали")

    # === translate ===
    p_trans = subparsers.add_parser("translate", help="Перевести строки через LLM")
    p_trans.add_argument("--source-locale", "--source", default="ru",
                         help="Исходный язык")
    p_trans.add_argument("--target-locale", "--target", default="en",
                         help="Целевой язык")
    p_trans.add_argument("--backend", default="gemini",
                         choices=["gemini", "openai", "anthropic", "ollama"],
                         help="LLM backend")
    p_trans.add_argument("--model", default="flash", help="Модель LLM")
    p_trans.add_argument("--batch-size", type=int, default=30,
                         help="Размер батча")
    p_trans.add_argument("--rate-delay", type=float, default=1.0,
                         help="Пауза между запросами (сек)")
    p_trans.add_argument("--force", action="store_true",
                         help="Перезаписать существующие переводы")
    p_trans.add_argument("--locales-dir",
                         default="src/i18n/locales",
                         help="Директория каталогов")
    p_trans.add_argument("--bridge-path", default="",
                         help="Путь к gemini-bridge.sh")
    p_trans.add_argument("--api-key", default="", help="API ключ (openai/anthropic)")

    # === validate ===
    p_val = subparsers.add_parser("validate", help="Валидировать переводы")
    p_val.add_argument("--source-locale", "--source", default="ru",
                       help="Исходный язык")
    p_val.add_argument("--target-locale", "--target", default="en",
                       help="Целевой язык")
    p_val.add_argument("--sample-size", type=int, default=20,
                       help="Размер выборки для LLM")
    p_val.add_argument("--no-llm", action="store_true",
                       help="Без LLM-проверки (только алгоритмическая)")
    p_val.add_argument("--auto-fix", action="store_true",
                       help="Автоприменение LLM-исправлений")
    p_val.add_argument("--output", default="",
                       help="Путь для сохранения отчёта")
    p_val.add_argument("--locales-dir",
                       default="src/i18n/locales",
                       help="Директория каталогов")
    p_val.add_argument("--project-root", default=".", help="Корень проекта")
    p_val.add_argument("--llm-backend", default="gemini", help="LLM backend для проверки")
    p_val.add_argument("--llm-model", default="pro", help="Модель для проверки")
    p_val.add_argument("--bridge-path", default="", help="Путь к gemini-bridge.sh")

    # === pipeline ===
    p_pipe = subparsers.add_parser("pipeline",
                                    help="Полный pipeline: scan -> translate -> validate")
    p_pipe.add_argument("--project-root", default=".", help="Корень проекта")
    p_pipe.add_argument("--source-locale", "--source", default="ru",
                        help="Исходный язык")
    p_pipe.add_argument("--target-locale", "--target", default="en",
                        help="Целевой язык")
    p_pipe.add_argument("--backend", default="gemini",
                        choices=["gemini", "openai", "anthropic", "ollama"],
                        help="LLM backend")
    p_pipe.add_argument("--model", default="flash", help="Модель для перевода")
    p_pipe.add_argument("--batch-size", type=int, default=30, help="Размер батча")
    p_pipe.add_argument("--rate-delay", type=float, default=1.0,
                        help="Пауза между запросами")
    p_pipe.add_argument("--sample-size", type=int, default=20,
                        help="Выборка для LLM-проверки")
    p_pipe.add_argument("--no-llm", action="store_true",
                        help="Без LLM-проверки качества")
    p_pipe.add_argument("--auto-fix", action="store_true",
                        help="Автоприменение LLM-исправлений")
    p_pipe.add_argument("--bridge-path", default="", help="Путь к gemini-bridge.sh")

    # === stats ===
    p_stats = subparsers.add_parser("stats", help="Статистика каталога")
    p_stats.add_argument("--locales-dir",
                         default="src/i18n/locales",
                         help="Директория каталогов")

    # === export ===
    p_export = subparsers.add_parser("export",
                                      help="Экспорт для внешнего переводчика")
    p_export.add_argument("--locale", required=True, help="Локаль для экспорта")
    p_export.add_argument("--output", required=True, help="Выходной файл")
    p_export.add_argument("--all", action="store_true",
                          help="Экспортировать все (не только ожидающие)")
    p_export.add_argument("--locales-dir",
                          default="src/i18n/locales",
                          help="Директория каталогов")

    # === import ===
    p_import = subparsers.add_parser("import",
                                      help="Импорт переводов из файла")
    p_import.add_argument("--locale", required=True, help="Целевая локаль")
    p_import.add_argument("--input", required=True, help="Входной файл")
    p_import.add_argument("--locales-dir",
                          default="src/i18n/locales",
                          help="Директория каталогов")

    return parser


def main():
    """Точка входа CLI."""
    parser = build_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    commands = {
        "scan": cmd_scan,
        "translate": cmd_translate,
        "validate": cmd_validate,
        "pipeline": cmd_pipeline,
        "stats": cmd_stats,
        "export": cmd_export,
        "import": cmd_import,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    main()
