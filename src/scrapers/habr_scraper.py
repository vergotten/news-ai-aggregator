"""
HABR SCRAPER (SAFE MODE + RSS FALLBACK)
========================================

Цель:
    Стабильный и безопасный сбор статей с Хабра.

Стратегия:
    1. Основной метод: HTML парсинг через селекторы
    2. Fallback метод: RSS парсинг (последние ~20 статей)

Принципы:
    • Обход хабов через /hub/ и /hubs/ (автоматический fallback)
    • Ротация User-Agent и Referer
    • Плавная пагинация (DOWNLOAD_DELAY + AUTOTHROTTLE)
    • RSS как запасной вариант при проблемах с HTML
    • Совместимость с deduplication_service и editorial_service

Результат:
    Статьи извлекаются корректно, при блокировке HTML - переключение на RSS.
"""

import os
import logging
import scrapy
from scrapy.http import Response, Request
from datetime import datetime
from urllib.parse import urljoin
import html
import sys
import random
import xml.etree.ElementTree as ET
from typing import Optional, List, Dict, Callable
from scrapy.crawler import CrawlerProcess

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models.database import save_habr_article, HabrArticle
from src.utils.log_manager import get_log_manager

logger = logging.getLogger(__name__)

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 12_2) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64; rv:122.0) Gecko/20100101 Firefox/122.0",
]


class HabrArticleSpider(scrapy.Spider):
    """
    Главный spider для обхода крупнейших технологических хабов.
    Поддерживает HTML парсинг + RSS fallback.
    """

    name = "habr_articles"
    allowed_domains = ["habr.com"]

    # Релевантные хабы для парсинга
    RELEVANT_HUBS = [
        "artificial_intelligence", "machine_learning", "neural_networks",
        "deep_learning", "data_mining", "natural_language_processing",
        "computer_vision", "python", "programming", "backend",
        "devops", "docker", "kubernetes", "cloud_services",
    ]

    custom_settings = {
        "CONCURRENT_REQUESTS": 1,
        "DOWNLOAD_DELAY": 8,
        "RANDOMIZE_DOWNLOAD_DELAY": 4,
        "AUTOTHROTTLE_ENABLED": True,
        "AUTOTHROTTLE_START_DELAY": 8,
        "AUTOTHROTTLE_MAX_DELAY": 20,
        "COOKIES_ENABLED": True,
        "RETRY_TIMES": 4,
        "RETRY_HTTP_CODES": [429, 403, 500, 502, 503, 504],
        "LOG_LEVEL": "INFO",
    }

    def __init__(
        self,
        max_articles: int = 10,
        hubs: Optional[List[str]] = None,
        enable_llm: bool = True,
        enable_deduplication: bool = True,
        log_callback: Optional[Callable] = None,
        stats_dict: Optional[Dict] = None,
        use_rss_fallback: bool = True,
        *args,
        **kwargs
    ):
        super().__init__(*args, **kwargs)

        self.max_articles = max_articles
        self.hubs = hubs or self.RELEVANT_HUBS
        self.enable_llm = enable_llm
        self.enable_deduplication = enable_deduplication
        self.log_callback = log_callback
        self.use_rss_fallback = use_rss_fallback

        self.stats_dict = stats_dict or {
            "saved": 0,
            "skipped": 0,
            "semantic_duplicates": 0,
            "errors": 0,
            "blocked": 0,
            "rss_used": 0,
        }

        self.collected = 0
        self.html_failed_hubs = []  # Хабы где HTML парсинг не сработал

        # Инициализация дедупликатора (если включён)
        if enable_deduplication:
            try:
                from src.services.deduplication_service import get_deduplication_service
                self.dedup = get_deduplication_service()
                self.log_message("Дедупликатор инициализирован", "INFO")
            except Exception as e:
                self.log_message(f"Ошибка инициализации дедупликатора: {e}", "WARNING")
                self.dedup = None
                self.enable_deduplication = False
        else:
            self.dedup = None

        self.log_message(f"Spider инициализирован: max_articles={max_articles}, hubs={len(self.hubs)}", "INFO")
        self.log_message(f"LLM обработка: {'ВКЛЮЧЕНА' if enable_llm else 'ВЫКЛЮЧЕНА'}", "INFO")

    def start(self):
        """
        Переопределенный метод start() для Scrapy 2.13+
        """
        logger.info(f"Запуск паука {self.name}")
        return super().start()

    # -----------------------------------------------------
    # Вспомогательные методы
    # -----------------------------------------------------
    def log_message(self, text: str, level="INFO"):
        """Логирование сообщения с использованием callback или стандартного логгера."""
        if self.log_callback:
            try:
                self.log_callback(text, level)
            except:
                pass

        # Также используем стандартный логгер Scrapy
        log_level = getattr(logging, level.upper(), logging.INFO)
        self.logger.log(log_level, text)

    def headers(self, referer: Optional[str] = None):
        h = {"User-Agent": random.choice(USER_AGENTS)}
        if referer:
            h["Referer"] = referer
        return h

    # -----------------------------------------------------
    # Стартовый обход — HTML парсинг, затем RSS fallback
    # -----------------------------------------------------
    def start_requests(self):
        self.log_message(f"Начало обхода {len(self.hubs)} хабов", "INFO")

        for hub in self.hubs:
            url = f"https://habr.com/ru/hub/{hub}/articles/"
            self.log_message(f"📡 Обход хаба (HTML): {hub}", "INFO")
            yield Request(
                url,
                callback=self.parse_list,
                meta={"hub": hub, "path": "hub"},
                headers=self.headers(),
                errback=self.handle_error
            )

    def handle_error(self, failure):
        """Обработка ошибок запросов."""
        hub = failure.request.meta.get("hub")
        if hub:
            self.log_message(f"⚠ Ошибка запроса для хаба {hub}: {failure}", "WARNING")
            self.html_failed_hubs.append(hub)

    # -----------------------------------------------------
    # Список статей на странице хаба (HTML)
    # -----------------------------------------------------
    def parse_list(self, response: Response):
        """Парсинг списка статей с проверкой лимита."""
        hub = response.meta["hub"]
        path = response.meta["path"]

        # ПРОВЕРКА ЛИМИТА В НАЧАЛЕ
        if self.collected >= self.max_articles:
            self.log_message(f"✓ Достигнут лимит статей: {self.max_articles}", "INFO")
            return

        self.log_message(f"Парсинг списка статей для хаба: {hub}, статус: {response.status}", "INFO")

        if response.status == 404 and path == "hub":
            alt = f"https://habr.com/ru/hubs/{hub}/articles/"
            self.log_message(f"Fallback /hubs/ для хаба: {hub}", "INFO")
            yield Request(alt, callback=self.parse_list, meta={"hub": hub, "path": "hubs"}, headers=self.headers())
            return

        link_selectors = [
            "article a[href*='/articles/']::attr(href)",
            "h2 a[href*='/articles/']::attr(href)",
            "a[href*='/articles/'][class*='title']::attr(href)",
            "a.tm-title__link::attr(href)",
            "a.tm-article-snippet__title-link::attr(href)",
            "h2.tm-title a::attr(href)",
        ]

        links = []
        for sel in link_selectors:
            found = response.css(sel).getall()
            if found:
                links.extend(found)

        article_links = []
        for link in links:
            if '/articles/' not in link and '/post/' not in link:
                continue
            if '/comments/' in link:
                continue
            if '#' in link:
                link = link.split('#')[0]
            if '/companies/' in link and link.endswith('/articles/'):
                continue
            import re
            if not re.search(r'/(?:articles|post)/\d+', link):
                continue

            full_url = response.urljoin(link)
            article_links.append(full_url)

        article_links = list(dict.fromkeys(article_links))

        # ОГРАНИЧИВАЕМ КОЛИЧЕСТВО ССЫЛОК
        remaining = self.max_articles - self.collected
        if remaining > 0:
            article_links = article_links[:remaining]

        self.log_message(f"📊 Найдено {len(article_links)} статей (осталось собрать: {remaining})", "INFO")

        if not article_links:
            self.log_message(f"⚠ HTML парсинг не нашел статей для хаба {hub}", "WARNING")

            if self.use_rss_fallback and hub not in self.html_failed_hubs:
                self.html_failed_hubs.append(hub)
                self.log_message(f"→ Переключение на RSS для хаба: {hub}", "INFO")
                rss_url = f"https://habr.com/ru/rss/hub/{hub}/articles/"
                yield Request(rss_url, callback=self.parse_rss, meta={"hub": hub}, headers=self.headers())
            return

        # Обход статей
        for idx, url in enumerate(article_links, 1):
            if self.collected >= self.max_articles:
                self.log_message(f"✓ Достигнут лимит: {self.max_articles} статей", "INFO")
                return

            self.log_message(f"→ [{idx}/{len(article_links)}] {url}", "INFO")
            yield Request(url, callback=self.parse_article, headers=self.headers(response.url), meta={"retry": 0})

        # Пагинация ТОЛЬКО если не достигли лимита
        if self.collected < self.max_articles:
            next_selectors = [
                "a.tm-pagination__page--next::attr(href)",
                "a[rel='next']::attr(href)",
                "a[class*='next']::attr(href)",
            ]

            next_page = None
            for sel in next_selectors:
                next_page = response.css(sel).get()
                if next_page:
                    break

            if next_page:
                next_url = response.urljoin(next_page)
                self.log_message(f"→ Пагинация: {next_url} (осталось: {self.max_articles - self.collected})", "INFO")
                yield Request(next_url, callback=self.parse_list, meta={"hub": hub, "path": path},
                              headers=self.headers(response.url))

    # -----------------------------------------------------
    # RSS парсинг (fallback метод)
    # -----------------------------------------------------
    def parse_rss(self, response: Response):
        """Парсинг RSS с проверкой лимита."""
        hub = response.meta["hub"]
        self.log_message(f"📡 RSS парсинг для хаба: {hub}", "INFO")

        # ПРОВЕРКА ЛИМИТА
        if self.collected >= self.max_articles:
            self.log_message(f"✓ Достигнут лимит статей: {self.max_articles}", "INFO")
            return

        try:
            root = ET.fromstring(response.text)
            items = root.findall('.//item')

            # ОГРАНИЧИВАЕМ КОЛИЧЕСТВО ЭЛЕМЕНТОВ ИЗ RSS
            remaining = self.max_articles - self.collected
            if remaining > 0:
                items = items[:remaining]

            self.log_message(f"📊 Найдено {len(items)} статей в RSS (осталось: {remaining})", "INFO")

            for idx, item in enumerate(items, 1):
                if self.collected >= self.max_articles:
                    self.log_message(f"✓ Достигнут лимит: {self.max_articles} статей", "INFO")
                    break

                title = item.find('title').text if item.find('title') is not None else "Без заголовка"
                link = item.find('link').text if item.find('link') is not None else None
                description = item.find('description').text if item.find('description') is not None else ""
                pub_date_str = item.find('pubDate').text if item.find('pubDate') is not None else None
                author_elem = item.find('.//{http://purl.org/dc/elements/1.1/}creator')
                author = author_elem.text if author_elem is not None else None

                if not link:
                    continue

                pub_date = None
                if pub_date_str:
                    try:
                        from email.utils import parsedate_to_datetime
                        pub_date = parsedate_to_datetime(pub_date_str)
                    except:
                        pub_date = datetime.utcnow()
                else:
                    pub_date = datetime.utcnow()

                self.log_message(f"→ RSS [{idx}/{len(items)}] {title[:50]}...", "INFO")

                yield Request(
                    link,
                    callback=self.parse_article,
                    headers=self.headers(),
                    meta={
                        "retry": 0,
                        "from_rss": True,
                        "rss_title": title,
                        "rss_description": description,
                        "rss_author": author,
                        "rss_pub_date": pub_date,
                    }
                )

                self.stats_dict["rss_used"] += 1

        except ET.ParseError as e:
            self.log_message(f"✗ Ошибка парсинга RSS XML: {e}", "ERROR")
        except Exception as e:
            self.log_message(f"✗ Ошибка RSS парсинга: {e}", "ERROR")
            logger.exception("RSS parsing error:")

    # -----------------------------------------------------
    # Проверка блокировки
    # -----------------------------------------------------
    def blocked(self, response: Response) -> bool:
        """
        Проверка блокировки - только длина страницы.
        """
        page_size = len(response.text)

        # Нормальная статья Хабра > 10KB
        if page_size < 10000:
            self.log_message(f"[BLOCKED] Короткая страница: {page_size} байт", "DEBUG")
            return True

        self.log_message(f"[OK] {page_size} байт", "DEBUG")
        return False

    # -----------------------------------------------------
    # Парсинг статьи
    # -----------------------------------------------------
    def parse_article(self, response: Response):
        """Парсинг отдельной статьи с проверкой лимита."""
        from_rss = response.meta.get("from_rss", False)

        # ПРОВЕРКА ЛИМИТА В НАЧАЛЕ
        if self.collected >= self.max_articles:
            self.log_message(f"✓ Достигнут лимит статей: {self.max_articles}", "INFO")
            return

        self.log_message(f"━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━", "INFO")
        self.log_message(f"[ПАРСИНГ] {response.url}", "INFO")
        self.log_message(f"[РАЗМЕР] {len(response.text)} символов", "INFO")
        self.log_message(f"[RSS?] {from_rss}", "DEBUG")
        self.log_message(f"[COLLECTED] {self.collected}/{self.max_articles}", "DEBUG")

        # Проверка на блокировку
        if self.blocked(response):
            retry = response.meta.get("retry", 0)
            if retry >= 3:
                self.log_message(f"✗ Заблокирован после {retry} попыток", "WARNING")
                self.stats_dict["blocked"] += 1
                if from_rss:
                    self.save_from_rss_metadata(response)
                return

            self.log_message(f"⚠ Возможная блокировка, повтор {retry + 1}/3", "WARNING")
            yield Request(
                response.url,
                callback=self.parse_article,
                headers=self.headers(),
                meta={**response.meta, "retry": retry + 1},
                dont_filter=True,
            )
            return

        # Извлечение данных
        try:
            title = self.extract_title(response) or response.meta.get("rss_title", "Без заголовка")
            self.log_message(f"[TITLE] {title[:60]}...", "INFO")

            content = self.extract_content(response)
            self.log_message(f"[CONTENT] {len(content)} символов", "INFO")

            if (not content or len(content) < 150) and from_rss:
                content = response.meta.get("rss_description", "")
                self.log_message("→ Используем описание из RSS как контент", "INFO")

            author = self.extract_author(response) or response.meta.get("rss_author")
            self.log_message(f"[AUTHOR] {author}", "DEBUG")

            published = self.extract_pub_date(response) or response.meta.get("rss_pub_date", datetime.utcnow())
            self.log_message(f"[DATE] {published}", "DEBUG")

            images = self.extract_images(response)
            self.log_message(f"[IMAGES] {len(images)} изображений", "DEBUG")

            url = response.url

            # Валидация минимальной длины контента
            if not content or len(content) < 100:
                self.log_message(f"✗ Контент слишком короткий ({len(content)} символов)", "WARNING")
                self.stats_dict["skipped"] += 1
                return

            # Дедупликация
            if self.enable_deduplication and self.dedup:
                try:
                    self.log_message(f"[DEDUP] Проверка дедупликации...", "DEBUG")
                    is_dup, dup_id, score = self.dedup.check_duplicate(
                        text=f"{title}\n\n{content}",
                        source="habr"
                    )

                    if is_dup:
                        self.log_message(
                            f"✗ Семантический дубликат: {dup_id} (схожесть: {score:.2%})",
                            "INFO"
                        )
                        self.stats_dict["semantic_duplicates"] += 1
                        return
                    else:
                        self.log_message(f"[✓] Не дубликат", "DEBUG")

                except Exception as e:
                    self.log_message(f"⚠ Ошибка дедупликации: {e}", "WARNING")

            # LLM обработка (если включена)
            processed_title = title
            processed_content = content
            teaser = None
            image_prompt = None
            relevance_score = None

            if self.enable_llm:
                try:
                    self.log_message(f"[LLM] Редакторская обработка...", "INFO")
                    from src.services.editorial_service import get_editorial_service

                    editorial = get_editorial_service()
                    result = editorial.process_post(
                        title=title,
                        content=content,
                        source="habr",
                        default_relevant=True  # Habr всегда релевантен по умолчанию
                    )

                    # Логирование полного результата LLM
                    self.log_message(f"[LLM] Полный результат: {result}", "DEBUG")

                    # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Проверка наличия ошибок
                    if result.get('error'):
                        self.log_message(
                            f"✗ Ошибка LLM: {result['error']}\n"
                            f"   Продолжаем сохранение без LLM обработки",
                            "WARNING"
                        )
                        # Fallback: сохраняем как есть, но продолжаем
                        self.stats_dict["errors"] += 1
                        # НЕ возвращаемся - продолжаем сохранение без LLM данных

                    elif not result.get('is_news'):
                        # Статья не прошла фильтр релевантности
                        self.log_message(
                            f"⏭ ПРОПУСК: Статья не подходит\n"
                            f"   Причина: {result.get('relevance_reason', 'N/A')}\n"
                            f"   Релевантность: {result.get('relevance_score', 0):.2f}",
                            "INFO"
                        )
                        self.stats_dict["skipped"] += 1
                        return  # Только здесь прерываем обработку

                    else:
                        # Статья прошла - используем обработанные данные
                        processed_title = result.get('title') or title
                        processed_content = result.get('rewritten_post') or content
                        teaser = result.get('teaser')
                        image_prompt = result.get('image_prompt')
                        relevance_score = result.get('relevance_score', 0.0)

                        # Проверка, что обработанный контент отличается от оригинала
                        if processed_content != content:
                            self.log_message(f"[LLM] ✓ Обработанный контент отличается от оригинала", "INFO")
                            self.log_message(f"[LLM] Оригинал (начало): {content[:200]}...", "DEBUG")
                            self.log_message(f"[LLM] Обработанный (начало): {processed_content[:200]}...", "DEBUG")
                        else:
                            self.log_message(f"[LLM] ⚠️ Обработанный контент идентичен оригиналу!", "WARNING")

                        # Инициализация счетчика если его нет
                        if "editorial_processed" not in self.stats_dict:
                            self.stats_dict["editorial_processed"] = 0

                        self.stats_dict["editorial_processed"] += 1

                        self.log_message(f"[✓] LLM обработка успешна", "INFO")
                        self.log_message(f"   Новый заголовок: {processed_title[:60]}...", "DEBUG")
                        self.log_message(f"   Релевантность: {relevance_score:.2f}", "DEBUG")

                except ImportError as e:
                    self.log_message(f"✗ Editorial service недоступен: {e}", "WARNING")
                    # Продолжаем без LLM
                except Exception as e:
                    self.log_message(f"✗ Ошибка LLM обработки: {e}", "ERROR")
                    logger.exception("LLM processing error:")
                    self.stats_dict["errors"] += 1
                    # НЕ прерываем - продолжаем сохранение без LLM

            # Сохранение статьи
            try:
                self.log_message(f"[DB] Сохранение в PostgreSQL...", "INFO")

                # ДИАГНОСТИКА: Логируем данные перед сохранением
                self.log_message("=" * 80, "INFO")
                self.log_message("ДИАГНОСТИКА ПЕРЕД save_habr_article:", "INFO")
                self.log_message(f"  original_title: {title[:100]}", "INFO")
                self.log_message(f"  processed_title: {processed_title[:100] if processed_title else 'NONE'}", "INFO")
                self.log_message(f"  original_content: {len(content)} символов", "INFO")
                self.log_message(f"  processed_content: {len(processed_content) if processed_content else 0} символов", "INFO")
                self.log_message(f"  teaser: {'ДА (' + str(len(teaser)) + ' сим.)' if teaser else 'NONE'}", "INFO")
                self.log_message(f"  image_prompt: {'ДА (' + str(len(image_prompt)) + ' сим.)' if image_prompt else 'NONE'}", "INFO")
                self.log_message(f"  relevance_score: {relevance_score}", "INFO")
                self.log_message(f"  title_changed: {processed_title != title}", "INFO")
                self.log_message(f"  content_changed: {processed_content != content}", "INFO")

                # Сравнение контента
                if processed_content != content:
                    self.log_message("  ✓ Оригинальный и обработанный контент РАЗЛИЧАЮТСЯ", "INFO")
                    self.log_message(f"  Оригинал (начало): {content[:200]}...", "DEBUG")
                    self.log_message(f"  Обработанный (начало): {processed_content[:200]}...", "DEBUG")
                else:
                    self.log_message("  ⚠️ Оригинальный и обработанный контент ИДЕНТИЧНЫ!", "WARNING")

                self.log_message("=" * 80, "INFO")

                # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Правильная подготовка данных для сохранения
                save_kwargs = {
                    'is_news': True,  # Явно указываем, что это новость
                    'relevance_score': relevance_score,
                    'enable_llm': False,  # LLM уже обработали выше
                }

                # Добавляем обработанные поля если они есть
                if processed_title != title:
                    save_kwargs['title'] = processed_title
                    self.log_message(f"[SCRAPER] Добавлен title: {processed_title[:50]}")

                if processed_content != content:
                    save_kwargs['rewritten_post'] = processed_content
                    self.log_message(f"[SCRAPER] Добавлен rewritten_post: {len(processed_content)} символов")

                if teaser:
                    save_kwargs['teaser'] = teaser
                    self.log_message(f"[SCRAPER] Добавлен teaser: {teaser[:50]}")

                if image_prompt:
                    save_kwargs['image_prompt'] = image_prompt
                    self.log_message(f"[SCRAPER] Добавлен image_prompt: {image_prompt[:50]}")

                # Логируем итоговые данные для сохранения
                self.log_message(f"[SCRAPER] Итого save_kwargs: {list(save_kwargs.keys())}")

                saved = save_habr_article(
                    url=url,
                    title=processed_title,
                    content=processed_content,
                    author=author,
                    published_at=published,
                    images=images,
                    tags=self.hubs,
                    **save_kwargs
                )

                if saved:
                    self.stats_dict["saved"] += 1
                    self.collected += 1
                    source_type = "RSS" if from_rss else "HTML"
                    self.log_message(
                        f"✓✓✓ СОХРАНЕНО [{self.collected}/{self.max_articles}] ({source_type}): {processed_title[:50]}...",
                        "INFO"
                    )

                    # Сохранение в Qdrant (если дедупликация включена)
                    if self.enable_deduplication and self.dedup:
                        try:
                            self.log_message(f"[QDRANT] Сохранение embedding...", "DEBUG")
                            qdrant_text = f"{processed_title}\n\n{processed_content}"

                            # Извлекаем article_id из URL
                            import re
                            match = re.search(r'/(?:articles|post)/(\d+)', url)
                            article_id = match.group(1) if match else url

                            qdrant_id = self.dedup.save_to_qdrant(
                                text=qdrant_text,
                                record_id=article_id,
                                metadata={
                                    'title': processed_title,
                                    'url': url,
                                    'teaser': teaser or '',
                                    'author': author or '',
                                    'hubs': self.hubs,
                                    'relevance_score': relevance_score or 0.0
                                },
                                source="habr"
                            )

                            if qdrant_id:
                                self.log_message(f"[✓] Сохранено в Qdrant: {qdrant_id[:8]}...", "DEBUG")
                        except Exception as e:
                            self.log_message(f"⚠ Ошибка сохранения в Qdrant: {e}", "WARNING")
                else:
                    self.log_message(f"⊘ Статья уже существует в БД: {processed_title[:50]}...", "INFO")
                    self.stats_dict["skipped"] += 1

            except Exception as e:
                self.log_message(f"✗ Ошибка сохранения: {e}", "ERROR")
                self.stats_dict["errors"] += 1
                logger.exception(f"Детали ошибки для {url}:")

        except Exception as e:
            self.log_message(f"✗ Ошибка парсинга: {e}", "ERROR")
            self.stats_dict["errors"] += 1
            logger.exception(f"Детали ошибки для {response.url}:")

    def save_from_rss_metadata(self, response: Response):
        """Сохранение статьи используя только метаданные из RSS."""
        try:
            title = response.meta.get("rss_title", "Без заголовка")
            content = response.meta.get("rss_description", "Контент недоступен")
            author = response.meta.get("rss_author")
            published = response.meta.get("rss_pub_date", datetime.utcnow())
            url = response.url

            self.log_message(f"[RSS] Сохранение из RSS метаданных: {title[:50]}...", "INFO")

            # LLM обработка (если включена)
            processed_title = title
            processed_content = content
            teaser = None
            image_prompt = None
            relevance_score = None

            if self.enable_llm:
                try:
                    self.log_message(f"[LLM] Редакторская обработка RSS...", "INFO")
                    from src.services.editorial_service import get_editorial_service

                    editorial = get_editorial_service()
                    result = editorial.process_post(
                        title=title,
                        content=content,
                        source="habr",
                        default_relevant=True
                    )

                    if result.get('error'):
                        self.log_message(f"✗ Ошибка LLM (RSS): {result['error']}", "ERROR")
                        self.stats_dict["errors"] += 1
                        return

                    if not result.get('is_news'):
                        self.log_message(f"⏭ RSS статья не подходит: {result.get('relevance_reason', 'N/A')}", "INFO")
                        self.stats_dict["skipped"] += 1
                        return

                    processed_title = result.get('title', title)
                    processed_content = result.get('rewritten_post', content)
                    teaser = result.get('teaser')
                    image_prompt = result.get('image_prompt')
                    relevance_score = result.get('relevance_score', 0.0)

                    self.stats_dict["editorial_processed"] += 1
                    self.log_message(f"[✓] LLM обработка RSS успешна", "INFO")

                except Exception as e:
                    self.log_message(f"✗ Ошибка LLM обработки RSS: {e}", "ERROR")
                    self.stats_dict["errors"] += 1
                    return

            # КРИТИЧЕСКОЕ ИСПРАВЛЕНИЕ: Правильная подготовка данных для сохранения
            save_kwargs = {
                'is_news': True,  # Явно указываем, что это новость
                'relevance_score': relevance_score,
                'enable_llm': False,  # LLM уже обработали выше
            }

            # Добавляем обработанные поля если они есть
            if processed_title != title:
                save_kwargs['title'] = processed_title

            if processed_content != content:
                save_kwargs['rewritten_post'] = processed_content

            if teaser:
                save_kwargs['teaser'] = teaser

            if image_prompt:
                save_kwargs['image_prompt'] = image_prompt

            saved = save_habr_article(
                url=url,
                title=processed_title,
                content=processed_content,
                author=author,
                published_at=published,
                images=[],
                tags=self.hubs,
                **save_kwargs
            )

            if saved:
                self.stats_dict["saved"] += 1
                self.stats_dict["rss_used"] += 1
                self.collected += 1
                self.log_message(f"✓ RSS данные сохранены", "INFO")

        except Exception as e:
            self.log_message(f"✗ Ошибка сохранения RSS метаданных: {e}", "ERROR")
            self.stats_dict["errors"] += 1
            logger.exception("RSS save error:")

    # -----------------------------------------------------
    # Извлечение полей
    # -----------------------------------------------------
    def extract_title(self, response: Response):
        """Универсальное извлечение заголовка."""
        selectors = [
            "h1 span[class*='title']::text",
            "h1[class*='title']::text",
            "h1 span::text",
            "h1::text",
            "meta[property='og:title']::attr(content)",
            "title::text",
        ]

        for sel in selectors:
            title = response.css(sel).get()
            if title:
                return title.strip()

        return None

    def extract_author(self, response: Response):
        """Универсальное извлечение автора."""
        selectors = [
            "a[class*='user'] span::text",
            "a[class*='author']::text",
            "[class*='author'] a::text",
            "meta[name='author']::attr(content)",
        ]

        for sel in selectors:
            author = response.css(sel).get()
            if author:
                return author.strip()

        return None

    def extract_pub_date(self, response: Response):
        """Универсальное извлечение даты."""
        dt = response.css("time::attr(datetime)").get()
        if dt:
            try:
                return datetime.fromisoformat(dt.replace("Z", "+00:00"))
            except:
                pass

        dt = response.css("meta[property='article:published_time']::attr(content)").get()
        if dt:
            try:
                return datetime.fromisoformat(dt.replace("Z", "+00:00"))
            except:
                pass

        return None

    def extract_content(self, response: Response):
        """Универсальное извлечение контента для любой версии Хабра."""
        content_selectors = [
            "article[id*='post']",
            "div[class*='article-formatted']",
            "div[id*='post-content']",
            "div.tm-article-body",
            "article.tm-article-presenter__body",
            "div.post__text",
            "div.content",
        ]

        blocks = None
        used_selector = None

        for sel in content_selectors:
            container = response.css(sel).get()
            if container:
                blocks = response.css(f"{sel} > *")
                used_selector = sel
                break

        if not blocks:
            blocks = response.css("article *")
            used_selector = "article *"

        if not blocks:
            return ""

        self.log_message(f"✓ Контент извлечён селектором: {used_selector}", "DEBUG")

        result = []
        for block in blocks:
            if block.css("pre, code"):
                code_text = "".join(block.css("::text").getall())
                if code_text.strip():
                    result.append(f"<code>{html.escape(code_text.strip())}</code>")
            elif block.css("h1, h2, h3, h4, h5, h6"):
                header_text = "".join(block.css("::text").getall()).strip()
                if header_text:
                    result.append(f"\n{header_text}\n")
            else:
                text = "".join(block.css("::text").getall()).strip()
                if text and len(text) > 5:
                    result.append(text)

        content = "\n\n".join(result).strip()
        self.log_message(f"✓ Извлечено {len(result)} блоков, {len(content)} символов", "DEBUG")

        return content

    def extract_images(self, response: Response):
        """Универсальное извлечение изображений."""
        img_selectors = [
            "article img::attr(src)",
            "div[class*='article'] img::attr(src)",
            "img[class*='article']::attr(src)",
        ]

        images = []
        for sel in img_selectors:
            imgs = response.css(sel).getall()
            images.extend(imgs)

        result = []
        for img in images:
            if any(skip in img.lower() for skip in ["icon", "avatar", "emoji", "logo"]):
                continue

            if img.startswith("//"):
                img = "https:" + img
            elif img.startswith("/"):
                img = "https://habr.com" + img

            result.append(img)

        return list(dict.fromkeys(result))


def scrape_habr(
    max_articles: int = 10,
    hubs=None,
    enable_llm: bool = True,
    enable_deduplication: bool = True,
    debug: bool = False,
    log_callback=None,
    save_html: bool = False
):
    """
    Главная точка запуска парсера, вызываемая run_habr_scraper.py
    Возвращает статистику.
    """

    stats = {
        "success": False,
        "saved": 0,
        "skipped": 0,
        "semantic_duplicates": 0,
        "editorial_processed": 0,
        "errors": 0,
        "blocked": 0,
        "rss_used": 0,
        "total_attempts": 0,
    }

    scrapy_settings = {
        'ROBOTSTXT_OBEY': False,
        'LOG_ENABLED': debug,
        'LOG_LEVEL': 'DEBUG' if debug else 'INFO',
        'COOKIES_ENABLED': True,
        'REDIRECT_ENABLED': True,

        'CONCURRENT_REQUESTS': 1,
        'DOWNLOAD_DELAY': 8,
        'RANDOMIZE_DOWNLOAD_DELAY': 4,
        'RETRY_TIMES': 5,
        'RETRY_HTTP_CODES': [403, 429, 500, 502, 503, 504],

        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': 8,
        'AUTOTHROTTLE_MAX_DELAY': 20,
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1,

        'USER_AGENT': random.choice(USER_AGENTS),
    }

    try:
        process = CrawlerProcess(settings=scrapy_settings)

        process.crawl(
            HabrArticleSpider,
            max_articles=max_articles,
            hubs=hubs,
            enable_llm=enable_llm,
            enable_deduplication=enable_deduplication,
            log_callback=log_callback,
            stats_dict=stats,
            debug=debug,
            save_html=save_html,
            use_rss_fallback=True,  # Включен RSS fallback
        )

        process.start()
        stats["success"] = True
        return stats

    except Exception as e:
        logger.exception("Критическая ошибка парсера:")
        stats["success"] = False
        stats["error"] = str(e)
        return stats