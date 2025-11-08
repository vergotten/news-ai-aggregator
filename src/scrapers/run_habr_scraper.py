#!/usr/bin/env python3
"""
Улучшенный скрипт для запуска Habr scraper.

Поддерживает:
- Гибкую настройку параметров
- Красивую отчетность
- Обработку ошибок
- Export результатов
"""

import argparse
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
import json

# Добавляем корневую директорию в sys.path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from src.scrapers.habr_scraper import scrape_habr


def setup_logging(debug: bool = False):
    """Настройка логирования."""
    level = logging.DEBUG if debug else logging.INFO

    # Форматтер с цветами
    class ColoredFormatter(logging.Formatter):
        """Форматтер с цветовой поддержкой."""

        COLORS = {
            'DEBUG': '\033[36m',  # Cyan
            'INFO': '\033[32m',  # Green
            'WARNING': '\033[33m',  # Yellow
            'ERROR': '\033[31m',  # Red
            'CRITICAL': '\033[35m',  # Magenta
            'RESET': '\033[0m'  # Reset
        }

        def format(self, record):
            levelname = record.levelname
            if levelname in self.COLORS:
                record.levelname = f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
            return super().format(record)

    handler = logging.StreamHandler()
    handler.setFormatter(ColoredFormatter(
        fmt='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
        datefmt='%H:%M:%S'
    ))

    logging.basicConfig(
        level=level,
        handlers=[handler]
    )


def print_banner():
    """Красивый баннер."""
    banner = """
╔══════════════════════════════════════════════════════════════════╗
║                     HABR SCRAPER v2.0                            ║
║                   AI-Powered News Aggregator                     ║
╚══════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def print_config(args):
    """Печать конфигурации запуска."""
    print("\n" + "=" * 70)
    print("⚙️  КОНФИГУРАЦИЯ")
    print("=" * 70)
    print(f"📊 Max articles:      {args.max_articles}")
    print(f"📁 Hubs:              {args.hubs if args.hubs else 'All'}")
    print(f"🤖 LLM processing:    {'✅ ON' if not args.no_llm else '❌ OFF'}")
    print(f"🔍 Deduplication:     {'✅ ON' if not args.no_dedup else '❌ OFF'}")
    print(f"🐛 Debug mode:        {'✅ ON' if args.debug else '❌ OFF'}")
    if args.output:
        print(f"💾 Output file:       {args.output}")
    print("=" * 70 + "\n")


def print_results(result: dict):
    """Красивая печать результатов."""
    print("\n" + "=" * 70)
    print("📊 РЕЗУЛЬТАТЫ ПАРСИНГА")
    print("=" * 70)

    if result['success']:
        print(f"✅ Status:            SUCCESS")
        print(f"💾 Saved:             {result.get('saved', 0)} articles")
        print(f"⏭️  Skipped:           {result.get('skipped', 0)} articles")
        print(f"🔄 Duplicates:        {result.get('semantic_duplicates', 0)} articles")
        print(f"📝 LLM processed:     {result.get('editorial_processed', 0)} articles")

        errors = result.get('errors', 0)
        if errors > 0:
            print(f"⚠️  Errors:            {errors} errors")

        # Вычисляем статистику
        total = result.get('saved', 0) + result.get('skipped', 0)
        if total > 0:
            save_rate = (result.get('saved', 0) / total) * 100
            print(f"📈 Save rate:         {save_rate:.1f}%")

            if result.get('editorial_processed', 0) > 0 and result.get('saved', 0) > 0:
                llm_rate = (result.get('editorial_processed', 0) / result.get('saved', 0)) * 100
                print(f"🤖 LLM success rate:  {llm_rate:.1f}%")
    else:
        print(f"❌ Status:            FAILED")
        print(f"💥 Error:             {result.get('error', 'Unknown error')}")

    print("=" * 70)


def save_results(result: dict, output_path: str):
    """Сохранение результатов в JSON."""
    try:
        # Добавляем timestamp
        result['timestamp'] = datetime.now().isoformat()

        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

        print(f"\n💾 Результаты сохранены в: {output_path}")
    except Exception as e:
        print(f"\n❌ Ошибка сохранения результатов: {e}")


def main():
    parser = argparse.ArgumentParser(description="Habr Scraper")

    # Основные параметры
    parser.add_argument("--max-articles", type=int, default=10)  # ← По умолчанию 10
    parser.add_argument("--hubs", type=str)

    # Флаги LLM - по умолчанию ВКЛЮЧЕНА
    parser.add_argument("--enable-llm", action="store_true", help="Включить LLM обработку")
    parser.add_argument("--no-llm", action="store_true", help="Отключить LLM обработку")

    # Флаги дедупликации - по умолчанию ВКЛЮЧЕНА
    parser.add_argument("--enable-dedup", action="store_true", help="Включить дедупликацию")
    parser.add_argument("--no-dedup", action="store_true", help="Отключить дедупликацию")

    parser.add_argument("--debug", action="store_true")
    parser.add_argument("--output", type=str)
    parser.add_argument("--quiet", action="store_true")

    args = parser.parse_args()

    # LLM по умолчанию ВКЛЮЧЕНА
    enable_llm = not args.no_llm  # ← ИЗМЕНЕНО: включена по умолчанию

    # Дедупликация по умолчанию ВКЛЮЧЕНА
    enable_dedup = not args.no_dedup  # ← ИЗМЕНЕНО: включена по умолчанию

    hubs_list = args.hubs.split(',') if args.hubs else None

    if not args.quiet:
        setup_logging(args.debug)
        print_banner()
        print_config(args)
        print(f"Итоговые настройки: LLM={enable_llm}, Дедупликация={enable_dedup}")

    try:
        result = scrape_habr(
            max_articles=args.max_articles,
            hubs=hubs_list,
            enable_llm=enable_llm,
            enable_deduplication=enable_dedup,
            debug=args.debug,
            log_callback=None if args.quiet else lambda msg, lvl: print(f"[{lvl}] {msg}")
        )

        if not args.quiet:
            print_results(result)

        if args.output:
            save_results(result, args.output)

        sys.exit(0 if result['success'] else 1)

    except KeyboardInterrupt:
        print("\n\n⚠️ Парсинг прерван")
        sys.exit(130)
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")
        logging.exception("Stack trace:")
        sys.exit(1)


if __name__ == "__main__":
    main()