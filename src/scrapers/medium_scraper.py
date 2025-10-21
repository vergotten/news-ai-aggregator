"""Medium scraper для парсинга статей по тегам через RSS."""
import logging
import time
from typing import Optional, Callable
from datetime import datetime
import requests
import feedparser
from src.models.database import save_medium_article
from src.utils.translations import t

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def scrape_medium_articles(
        tags: list,
        max_articles: int = 30,
        delay: int = 3,
        enable_llm: bool = False,
        log_callback: Optional[Callable[[str, str], None]] = None
):
    """
    Парсинг статей Medium по указанным тегам через RSS-ленты.

    Args:
        tags: Список тегов (e.g., ['tech', 'news'])
        max_articles: Максимум статей для парсинга на тег
        delay: Задержка между тегами в секундах
        enable_llm: Включить редакторскую обработку через GPT-OSS
        log_callback: Callback для логирования (message, level)

    Returns:
        Список словарей с результатами для каждого тега
    """

    def log(message: str, level: str = "INFO"):
        """Универсальная функция логирования."""
        logger_func = getattr(logger, level.lower(), logger.info)
        logger_func(message)
        if log_callback:
            log_callback(message, level)

    results = []
    log(f"Начало парсинга Medium: {len(tags)} тегов", "INFO")
    log(f"Editorial обработка: {'Включена' if enable_llm else 'Отключена'}", "INFO")

    for i, tag in enumerate(tags, 1):
        log(f"[{i}/{len(tags)}] Обработка тега {tag}", "INFO")
        saved_count = 0
        skipped_count = 0
        error_count = 0
        editorial_processed_count = 0

        try:
            # Формируем URL для RSS-ленты тега
            rss_url = f"https://medium.com/feed/tag/{tag.lower().replace(' ', '-')}"
            response = requests.get(rss_url, timeout=10)
            response.raise_for_status()
            feed = feedparser.parse(response.content)

            # Ограничение количества статей
            entries = feed.entries[:max_articles]
            log(f"Найдено {len(entries)} статей для тега {tag}", "INFO")

            for entry in entries:
                try:
                    # Формирование данных статьи
                    article_data = {
                        'title': entry.get('title', ''),
                        'url': entry.get('link', ''),
                        'summary': entry.get('summary', '')[:500],
                        'published_at': datetime.strptime(
                            entry.get('published', datetime.utcnow().isoformat()),
                            '%a, %d %b %Y %H:%M:%S %z'
                        ).replace(tzinfo=None) if entry.get('published') else datetime.utcnow(),
                        'author': entry.get('author', 'Unknown'),
                        'tag': tag,
                        'scraped_at': datetime.utcnow()
                    }

                    # Сохранение в БД
                    saved = save_medium_article(article_data)
                    if saved:
                        saved_count += 1
                        log(f"  ✓ Сохранено [{saved_count}]: {article_data['title'][:60] or 'No title'}...", "INFO")

                        # Редакторская обработка
                        if enable_llm:
                            from src.services.editorial_service import get_editorial_service
                            editorial = get_editorial_service()
                            text = f"{article_data['title']}\n\n{article_data['summary']}".strip()
                            result = editorial.process_post(article_data['title'], text, source="medium")

                            if result.get('is_news') and not result.get('error'):
                                editorial_processed_count += 1
                                log(f"    → Editorial обработан", "INFO")
                            elif result.get('error'):
                                log(f"    → Editorial ошибка: {result['error']}", "WARNING")
                    else:
                        skipped_count += 1
                        log(f"  ⊗ Пропущен: дубликат или ошибка", "DEBUG")

                    # Задержка для соблюдения лимитов
                    time.sleep(0.5)

                except Exception as e:
                    error_count += 1
                    log(f"  ✗ Ошибка обработки статьи: {e}", "ERROR")
                    continue

            # Итоговая статистика по тегу
            log(f"Завершено {tag}:", "INFO")
            log(f"  • Сохранено: {saved_count}", "INFO")
            log(f"  • Пропущено: {skipped_count}", "INFO")
            log(f"  • Editorial обработано: {editorial_processed_count}", "INFO")
            log(f"  • Ошибок: {error_count}", "WARNING" if error_count > 0 else "INFO")

            results.append({
                'success': True,
                'tag': tag,
                'saved': saved_count,
                'skipped': skipped_count,
                'editorial_processed': editorial_processed_count,
                'errors': error_count
            })

        except Exception as e:
            log(f"Ошибка парсинга тега {tag}: {e}", "ERROR")
            results.append({
                'success': False,
                'tag': tag,
                'error': str(e),
                'saved': 0,
                'skipped': 0,
                'editorial_processed': 0,
                'errors': 1
            })

        if i < len(tags):
            time.sleep(delay)

    log("Массовый парсинг Medium завершен", "INFO")
    return results
