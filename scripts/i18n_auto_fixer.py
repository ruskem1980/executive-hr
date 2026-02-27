#!/usr/bin/env python3
import os
import json
import argparse
import logging
import shutil
from typing import Dict, Any
from datetime import datetime

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class I18nAutoFixer:
    """
    Автоматический исправитель проблем i18n.
    """

    def __init__(self, locales_path: str, base_lang: str = 'ru'):
        self.locales_path = locales_path
        self.base_lang = base_lang
        self.base_translations = {}

    def load_base(self):
        base_path = os.path.join(self.locales_path, f"{self.base_lang}.json")
        with open(base_path, 'r', encoding='utf-8') as f:
            self.base_translations = json.load(f)

    def deep_merge(self, base: Dict, target: Dict, lang: str, fix_missing: bool, mark_untranslated: bool) -> Dict:
        """Рекурсивное слияние словарей с применением исправлений."""
        result = target.copy()
        
        for key, value in base.items():
            if key not in result:
                if fix_missing:
                    if isinstance(value, dict):
                        result[key] = self.deep_merge(value, {}, lang, fix_missing, mark_untranslated)
                    else:
                        result[key] = f"[MISSING_{lang.upper()}] {value}"
                        logger.info(f"Добавлен недостающий ключ: {key}")
            else:
                if isinstance(value, dict) and isinstance(result[key], dict):
                    result[key] = self.deep_merge(value, result[key], lang, fix_missing, mark_untranslated)
                elif not isinstance(value, dict) and not isinstance(result[key], dict):
                    # Если значение совпадает с базовым и не является пустым/коротким
                    if mark_untranslated and result[key] == value and len(value) > 3 and lang != self.base_lang:
                        if not result[key].startswith("[FIXME]"):
                            result[key] = f"[FIXME] {result[key]}"
                            logger.info(f"Помечен непереведенный ключ: {key}")
        
        return result

    def sort_dict(self, d: Dict) -> Dict:
        """Рекурсивная сортировка словаря по ключам."""
        sorted_dict = {}
        for key in sorted(d.keys()):
            if isinstance(d[key], dict):
                sorted_dict[key] = self.sort_dict(d[key])
            else:
                sorted_dict[key] = d[key]
        return sorted_dict

    def fix_all(self, fix_missing: bool, mark_untranslated: bool, sort: bool):
        self.load_base()
        
        files = [f for f in os.listdir(self.locales_path) if f.endswith('.json')]
        
        for file in files:
            lang = file.replace('.json', '')
            path = os.path.join(self.locales_path, file)
            
            # Создание бэкапа
            backup_path = f"{path}.bak_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            shutil.copy2(path, backup_path)
            
            with open(path, 'r', encoding='utf-8') as f:
                content = json.load(f)
            
            fixed_content = content
            if lang != self.base_lang:
                fixed_content = self.deep_merge(self.base_translations, content, lang, fix_missing, mark_untranslated)
            
            if sort:
                fixed_content = self.sort_dict(fixed_content)
                
            with open(path, 'w', encoding='utf-8') as f:
                json.dump(fixed_content, f, ensure_ascii=False, indent=2)
            
            logger.info(f"Файл {file} обработан и сохранен.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Автоматический исправитель i18n")
    parser.add_argument("--locales", default="apps/frontend/src/locales", help="Путь к файлам локализации")
    parser.add_argument("--fix-missing", action="store_true", help="Добавить отсутствующие ключи")
    parser.add_argument("--mark-untranslated", action="store_true", help="Пометить непереведенные значения")
    parser.add_argument("--sort", action="store_true", help="Сортировать ключи в алфавитном порядке")
    
    args = parser.parse_args()
    
    if not (args.fix_missing or args.mark_untranslated or args.sort):
        parser.print_help()
    else:
        fixer = I18nAutoFixer(args.locales)
        fixer.fix_all(args.fix_missing, args.mark_untranslated, args.sort)
