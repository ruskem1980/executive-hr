#!/usr/bin/env python3
import os
import json
import re
import argparse
import logging
from typing import Dict, List, Any, Set, Tuple
from collections import Counter
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Цвета для терминала
class Colors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

class I18nAnalyzer:
    """
    Комплексный анализатор системы интернационализации.
    """

    def __init__(self, base_dir: str, locales_path: str, base_lang: str = 'ru'):
        self.base_dir = base_dir
        self.locales_path = locales_path
        self.base_lang = base_lang
        self.languages = []
        self.translations = {}
        self.report_data = {
            "timestamp": datetime.now().isoformat(),
            "summary": {},
            "statistics": {},
            "issues": [],
            "component_coverage": {}
        }

    def load_locales(self):
        """Загрузка всех файлов локализации."""
        if not os.path.exists(self.locales_path):
            logger.error(f"Путь к локалям не найден: {self.locales_path}")
            return

        files = [f for f in os.listdir(self.locales_path) if f.endswith('.json') and not f.endswith('.before_common_translate')]
        for file in files:
            lang = file.replace('.json', '')
            self.languages.append(lang)
            path = os.path.join(self.locales_path, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    self.translations[lang] = json.load(f)
                logger.info(f"Загружен язык: {lang}")
            except Exception as e:
                logger.error(f"Ошибка загрузки {lang}: {e}")

    def flatten_dict(self, d: Dict, parent_key: str = '', sep: str = '.') -> Dict[str, str]:
        """Превращает вложенный словарь в плоский."""
        items = []
        for k, v in d.items():
            new_key = f"{parent_key}{sep}{k}" if parent_key else k
            if isinstance(v, dict):
                items.extend(self.flatten_dict(v, new_key, sep=sep).items())
            else:
                items.append((new_key, str(v)))
        return dict(items)

    def analyze_statistics(self):
        """Статистический анализ переводов."""
        logger.info("Запуск статистического анализа...")
        base_flat = self.flatten_dict(self.translations.get(self.base_lang, {}))
        
        for lang, trans in self.translations.items():
            flat = self.flatten_dict(trans)
            word_count = sum(len(v.split()) for v in flat.values())
            char_count = sum(len(v) for v in flat.values())
            
            self.report_data["statistics"][lang] = {
                "keys_count": len(flat),
                "word_count": word_count,
                "char_count": char_count,
                "coverage_percent": (len(flat) / len(base_flat) * 100) if len(base_flat) > 0 else 0
            }

    def find_issues(self):
        """Поиск проблем в переводах."""
        logger.info("Поиск проблем и несоответствий...")
        base_flat = self.flatten_dict(self.translations.get(self.base_lang, {}))
        
        for lang, trans in self.translations.items():
            if lang == self.base_lang:
                continue
                
            flat = self.flatten_dict(trans)
            
            # 1. Проверка отсутствующих ключей
            for key in base_flat:
                if key not in flat:
                    self.add_issue("missing_key", "error", lang, key, "Ключ отсутствует в файле перевода")
            
            # 2. Проверка непереведенных значений (копия оригинала)
            for key, val in flat.items():
                if key in base_flat and val == base_flat[key] and len(val) > 3:
                    self.add_issue("untranslated", "warning", lang, key, "Значение совпадает с базовым языком")

                # 3. Проверка placeholder'ов {param}
                base_params = set(re.findall(r'\{([^}]+)\}', base_flat.get(key, "")))
                lang_params = set(re.findall(r'\{([^}]+)\}', val))
                if base_params != lang_params:
                    self.add_issue("placeholder_mismatch", "error", lang, key, 
                                 f"Несоответствие параметров: ожидается {base_params}, найдено {lang_params}")

                # 4. Проверка на латиницу в RU и кириллицу в EN (базовая)
                if lang == 'en' and re.search('[а-яА-Я]', val):
                    self.add_issue("invalid_chars", "warning", lang, key, "Кириллица в английском переводе")

    def add_issue(self, type: str, severity: str, lang: str, key: str, description: str):
        self.report_data["issues"].append({
            "type": type,
            "severity": severity,
            "lang": lang,
            "key": key,
            "description": description
        })

    def scan_components(self):
        """Сканирование компонентов на использование переводов и хардкод."""
        logger.info("Сканирование компонентов (это может занять время)...")
        used_keys = set()
        hardcoded = []
        
        # Регулярки для поиска t('key') и хардкода
        t_pattern = re.compile(r"""t\(['"]([^'"]+)['"]\)""")
        # Очень упрощенный поиск хардкода: кириллица в кавычках внутри TSX
        hardcode_pattern = re.compile(r""">\s*([А-Яа-я][^<>{}\n]+)\s*<""")

        for root, _, files in os.walk(os.path.join(self.base_dir, 'apps/frontend/src')):
            if 'locales' in root or 'node_modules' in root:
                continue
                
            for file in files:
                if file.endswith(('.tsx', '.ts')):
                    path = os.path.join(root, file)
                    try:
                        with open(path, 'r', encoding='utf-8') as f:
                            content = f.read()
                            # Поиск используемых ключей
                            matches = t_pattern.findall(content)
                            used_keys.update(matches)
                            
                            # Поиск хардкода
                            hc_matches = hardcode_pattern.findall(content)
                            for match in hc_matches:
                                if match.strip():
                                    hardcoded.append({
                                        "file": os.path.relpath(path, self.base_dir),
                                        "text": match.strip()
                                    })
                    except Exception as e:
                        logger.error(f"Ошибка чтения файла {path}: {e}")

        base_flat = self.flatten_dict(self.translations.get(self.base_lang, {}))
        unused_keys = [k for k in base_flat if k not in used_keys]
        missing_keys_in_code = [k for k in used_keys if k not in base_flat]

        self.report_data["component_coverage"] = {
            "used_keys_count": len(used_keys),
            "unused_keys_count": len(unused_keys),
            "missing_keys_in_code_count": len(missing_keys_in_code),
            "hardcoded_strings_count": len(hardcoded),
            "hardcoded_samples": hardcoded[:20],  # Только первые 20 для отчета
            "missing_keys_samples": missing_keys_in_code[:20]
        }

    def run(self, output_dir: str):
        self.load_locales()
        self.analyze_statistics()
        self.find_issues()
        self.scan_components()
        
        self.report_data["summary"] = {
            "total_keys_base": len(self.flatten_dict(self.translations.get(self.base_lang, {}))),
            "languages": self.languages,
            "total_issues": len(self.report_data["issues"]),
            "critical_issues": len([i for i in self.report_data["issues"] if i["severity"] == "error"])
        }

        # Сохранение JSON отчета
        os.makedirs(output_dir, exist_ok=True)
        report_path = os.path.join(output_dir, f"i18n_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json")
        with open(report_path, 'w', encoding='utf-8') as f:
            json.dump(self.report_data, f, ensure_ascii=False, indent=2)
            
        logger.info(f"{Colors.OKGREEN}Анализ завершен. Отчет сохранен в {report_path}{Colors.ENDC}")
        self.print_summary()

    def print_summary(self):
        summary = self.report_data["summary"]
        print(f"\n{Colors.BOLD}--- ИТОГИ АНАЛИЗА I18N ---{Colors.ENDC}")
        print(f"Базовый язык: {self.base_lang} ({summary['total_keys_base']} ключей)")
        print(f"Всего языков: {', '.join(summary['languages'])}")
        print(f"Всего проблем: {summary['total_issues']} (Критических: {summary['critical_issues']})")
        
        print(f"\n{Colors.BOLD}Покрытие компонентов:{Colors.ENDC}")
        cov = self.report_data["component_coverage"]
        print(f"- Используется ключей: {cov['used_keys_count']}")
        print(f"- Неиспользуемых ключей: {cov['unused_keys_count']}")
        print(f"- Ключей в коде, но нет в JSON: {cov['missing_keys_in_code_count']}")
        print(f"- Хардкодных строк найдено: {cov['hardcoded_strings_count']}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Комплексный анализатор i18n")
    parser.add_argument("--analyze", action="store_true", help="Запустить анализ")
    parser.add_argument("--dir", default=".", help="Корневая директория проекта")
    parser.add_argument("--locales", default="apps/frontend/src/locales", help="Путь к файлам локализации")
    parser.add_argument("--output", default="reports/i18n", help="Директория для отчетов")
    
    args = parser.parse_args()
    
    analyzer = I18nAnalyzer(args.dir, args.locales)
    analyzer.run(args.output)
