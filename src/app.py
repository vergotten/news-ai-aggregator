"""Веб-интерфейс Streamlit для News Aggregator с живыми логами."""

import streamlit as st
import os
import sys
from pathlib import Path
import pandas as pd
import time
from datetime import datetime, timezone
from collections import deque
import json

# Добавляем корневую директорию в sys.path для импортов
sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(
    page_title="News Aggregator",
    page_icon="📰",
    layout="wide"
)

from src.utils.translations import TRANSLATIONS

def t(key: str, **kwargs) -> str:
    """Перевод ключа на текущий язык."""
    lang = st.session_state.get('language', 'ru')
    text = TRANSLATIONS.get(lang, TRANSLATIONS['ru']).get(key, key)
    if kwargs:
        return text.format(**kwargs)
    return text

# Загрузка CSS стилей
css_path = Path(__file__).parent / "static" / "style.css"
if css_path.exists():
    with open(css_path) as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    st.error("DATABASE_URL не настроен")
    st.stop()

try:
    from src.models.database import (
        init_db,
        get_stats_extended,
        get_posts_by_subreddit,
        get_processed_posts,
        get_processed_by_subreddit,
        get_medium_articles,
        get_session,
        RedditPost,
        ProcessedRedditPost,
        MediumArticle,
        TelegramMessage
    )
    from src.config_loader import get_config
    from src.services.editorial_service import EditorialService
    from src.scrapers.reddit_scraper import get_reddit_client, scrape_subreddit

    init_db()
    config = get_config()
except Exception as e:
    st.error(f"Ошибка инициализации: {e}")
    st.stop()

# ============================================================================
# НАСТРОЙКИ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
# ============================================================================
SETTINGS = {
    # PostgreSQL
    'postgres_user': os.getenv("POSTGRES_USER", "newsaggregator"),
    'postgres_password': os.getenv("POSTGRES_PASSWORD", "changeme123"),
    'postgres_db': os.getenv("POSTGRES_DB", "news_aggregator"),
    'postgres_port': int(os.getenv("POSTGRES_PORT", 5433)),

    # Reddit API
    'reddit_client_id': os.getenv("REDDIT_CLIENT_ID", "qpyZocAcLob0M8zbug8lrg"),
    'reddit_client_secret': os.getenv("REDDIT_CLIENT_SECRET", "wafZuaOqufek2lpBEaKlG3emDB1bkA"),
    'reddit_user_agent': os.getenv("REDDIT_USER_AGENT", "NewsAggregator/1.0"),

    # Telegram API
    'telegram_api_id': os.getenv("TELEGRAM_API_ID", "your_api_id"),
    'telegram_api_hash': os.getenv("TELEGRAM_API_HASH", "your_api_hash"),
    'telegram_phone': os.getenv("TELEGRAM_PHONE", "+1234567890"),

    # Qdrant
    'qdrant_port': int(os.getenv("QDRANT_PORT", 6333)),
    'qdrant_grpc_port': int(os.getenv("QDRANT_GRPC_PORT", 6334)),
    'qdrant_url': os.getenv("QDRANT_URL", "http://qdrant:6333"),

    # Ollama
    'ollama_port': int(os.getenv("OLLAMA_PORT", 11434)),
    'ollama_base_url': os.getenv("OLLAMA_BASE_URL", "http://ollama:11434"),

    # Приложение
    'app_port': int(os.getenv("APP_PORT", 8501)),
    'tz': os.getenv("TZ", "UTC"),
    'adminer_port': int(os.getenv("ADMINER_PORT", 8080)),

    # LLM Processing
    'max_parallel_tasks': int(os.getenv("MAX_PARALLEL_TASKS", 1)),

    # N8N
    'n8n_port': int(os.getenv("N8N_PORT", 5678)),
    'n8n_db': os.getenv("N8N_DB", "n8n"),
    'n8n_basic_auth_active': os.getenv("N8N_BASIC_AUTH_ACTIVE", "true").lower() == 'true',
    'n8n_basic_auth_user': os.getenv("N8N_BASIC_AUTH_USER", "admin"),
    'n8n_basic_auth_password': os.getenv("N8N_BASIC_AUTH_PASSWORD", "admin123"),

    # LLM
    'llm_provider': os.getenv("LLM_PROVIDER", "gpt-oss"),
    'llm_model': os.getenv("LLM_MODEL", "gpt-oss:20b"),
    'llm_temperature': float(os.getenv("LLM_TEMPERATURE", 0.7)),
    'llm_max_tokens': int(os.getenv("LLM_MAX_TOKENS", 8000)),
    'llm_top_p': float(os.getenv("LLM_TOP_P", 0.9)),
    'llm_base_url': os.getenv("LLM_BASE_URL", "http://localhost:5000"),

    # Парсинг
    'default_max_posts': int(os.getenv("DEFAULT_MAX_POSTS", 1)),
    'default_delay': int(os.getenv("DEFAULT_DELAY", 5)),
    'default_sort': os.getenv("DEFAULT_SORT", "hot"),
    'default_enable_llm': os.getenv("DEFAULT_ENABLE_LLM", "true").lower() == 'true',
    'batch_size': int(os.getenv("BATCH_SIZE", 10)),

    # Качество
    'min_text_length': int(os.getenv("MIN_TEXT_LENGTH", 50)),
    'enable_semantic_dedup': os.getenv("ENABLE_SEMANTIC_DEDUP", "true").lower() == 'true',
    'enable_vectorization': os.getenv("ENABLE_VECTORIZATION", "true").lower() == 'true',

    # UI
    'logs_max_length': int(os.getenv("LOGS_MAX_LENGTH", 500)),
    'viewer_default_limit': int(os.getenv("VIEWER_DEFAULT_LIMIT", 100)),
    'show_debug_info': os.getenv("SHOW_DEBUG_INFO", "false").lower() == 'true'
}

# Инициализация session_state
if 'settings' not in st.session_state:
    st.session_state.settings = SETTINGS

if 'parsing_logs' not in st.session_state:
    st.session_state.parsing_logs = deque(maxlen=st.session_state.settings['logs_max_length'])

if 'parsing_active' not in st.session_state:
    st.session_state.parsing_active = False

if 'parsing_in_progress' not in st.session_state:
    st.session_state.parsing_in_progress = False

if 'parsing_results' not in st.session_state:
    st.session_state.parsing_results = None

if 'parsing_progress' not in st.session_state:
    st.session_state.parsing_progress = {'current': 0, 'total': 0, 'status': ''}

if 'language' not in st.session_state:
    st.session_state.language = 'ru'

if 'log_session_counter' not in st.session_state:
    st.session_state.log_session_counter = 0

if 'log_storage' not in st.session_state:
    st.session_state.log_storage = None

# ============================================================================
# КЛАССЫ И ФУНКЦИИ
# ============================================================================

class StreamlitLogger:
    """Логгер, записывающий сообщения в session_state для отображения в UI."""

    @staticmethod
    def log(message: str, level: str = "INFO") -> None:
        """Добавить лог-сообщение."""
        timestamp = datetime.now().strftime("%H:%M:%S")
        icon = {"INFO": "ℹ️", "SUCCESS": "✅", "WARNING": "⚠️", "ERROR": "❌", "DEBUG": "🔍"}.get(level, "📝")
        log_entry = f"{icon} `{timestamp}` {message}"
        st.session_state.parsing_logs.append(log_entry)

    @staticmethod
    def add_separator(session_number: int) -> None:
        """Добавить разделитель между сессиями парсинга."""
        separator = f"\n{'='*80}\n🆕 **НОВАЯ СЕССИЯ #{session_number}** - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n{'='*80}\n"
        st.session_state.parsing_logs.append(separator)

    @staticmethod
    def clear() -> None:
        """Очистить логи."""
        st.session_state.parsing_logs.clear()
        st.session_state.log_session_counter = 0

def scrape_with_live_logs(subreddits: list[str], max_posts: int, sort_by: str, delay: int, enable_llm: bool) -> list[dict]:
    """Синхронный парсинг с логами в реальном времени."""
    logger = StreamlitLogger()
    st.session_state.log_session_counter += 1
    logger.add_separator(st.session_state.log_session_counter)

    progress_bar = st.progress(0)
    status_text = st.empty()
    log_container = st.expander("📋 **Логи парсинга**", expanded=True)
    log_placeholder = log_container.empty()

    results = []
    total_subs = len(subreddits)
    settings = st.session_state.settings
    logger.log(f"🚀 Начало парсинга: {total_subs} subreddits", "INFO")
    logger.log(f"Настройки: max_posts={max_posts}, sort={sort_by}, LLM={'ON' if enable_llm else 'OFF'}", "DEBUG")
    logger.log(f"LLM: {settings['llm_model']}, temp={settings['llm_temperature']}", "DEBUG")

    try:
        logger.log("Подключение к Reddit API...", "INFO")
        reddit = get_reddit_client()
        logger.log("✓ Reddit API подключен", "SUCCESS")

        for idx, sub in enumerate(subreddits, 1):
            progress = idx / total_subs
            progress_bar.progress(progress)
            status_text.info(f"🔥 Парсинг **r/{sub}** ({idx}/{total_subs})")

            logger.log(f"{'='*60}", "DEBUG")
            logger.log(f"Обработка r/{sub} [{idx}/{total_subs}]", "INFO")
            log_placeholder.markdown("\n".join(st.session_state.parsing_logs))

            try:
                result = scrape_subreddit(
                    subreddit_name=sub,
                    max_posts=max_posts,
                    sort_by=sort_by,
                    enable_llm=enable_llm,
                    log_callback=lambda msg, lvl: logger.log(msg, lvl)
                )
                results.append(result)

                if result.get('success'):
                    saved = result.get('saved', 0)
                    skipped = result.get('skipped', 0)
                    semantic_dups = result.get('semantic_duplicates', 0)
                    editorial = result.get('editorial_processed', 0)
                    msg = f"r/{sub}: сохранено {saved}, пропущено {skipped}"
                    if semantic_dups > 0:
                        msg += f", дубликатов {semantic_dups}"
                    if enable_llm and editorial > 0:
                        msg += f", обработано LLM {editorial}"
                    logger.log(msg, "SUCCESS")
                else:
                    error = result.get('error', 'Unknown error')
                    logger.log(f"r/{sub}: ошибка - {error}", "ERROR")
            except Exception as e:
                logger.log(f"r/{sub}: критическая ошибка - {str(e)}", "ERROR")
                results.append({'success': False, 'subreddit': sub, 'error': str(e)})

            log_placeholder.markdown("\n".join(st.session_state.parsing_logs))

            if idx < total_subs:
                logger.log(f"⏳ Ожидание {delay} сек...", "DEBUG")
                time.sleep(delay)

        logger.log(f"{'='*60}", "DEBUG")
        total_saved = sum(r.get('saved', 0) for r in results if r.get('success'))
        total_semantic = sum(r.get('semantic_duplicates', 0) for r in results if r.get('success'))
        total_editorial = sum(r.get('editorial_processed', 0) for r in results if r.get('success'))
        success_count = sum(1 for r in results if r.get('success'))

        logger.log(f"🎉 Парсинг завершён!", "SUCCESS")
        logger.log(f"Успешно: {success_count}/{total_subs} subreddits", "INFO")
        logger.log(f"Всего сохранено: {total_saved} постов", "SUCCESS")
        if total_semantic > 0:
            logger.log(f"Дубликатов отфильтровано: {total_semantic}", "INFO")
        if enable_llm and total_editorial > 0:
            logger.log(f"Обработано LLM: {total_editorial}", "SUCCESS")

        progress_bar.progress(1.0)
        status_text.success(f"✅ Завершено! Сохранено {total_saved} постов")
        log_placeholder.markdown("\n".join(st.session_state.parsing_logs))

        return results

    except Exception as e:
        logger.log(f"КРИТИЧЕСКАЯ ОШИБКА: {str(e)}", "ERROR")
        status_text.error(f"❌ Ошибка: {str(e)}")
        log_placeholder.markdown("\n".join(st.session_state.parsing_logs))
        return []


def process_posts_with_live_logs(unprocessed_posts: list) -> dict:
    """Параллельная обработка постов через LLM с живыми логами."""
    import concurrent.futures
    import threading
    from src.utils.thread_safe_logger import get_thread_safe_logger
    from src.models.database import is_post_processed

    # КРИТИЧНО: Копируем settings ДО создания потоков
    settings = dict(st.session_state.settings)

    # Используем thread-safe logger
    logger = get_thread_safe_logger()

    progress_bar = st.progress(0)
    status_text = st.empty()
    log_container = st.expander("📋 **Логи обработки LLM**", expanded=True)
    log_placeholder = log_container.empty()

    # Храним все логи для финального отображения
    all_logs = []

    processed_count = 0
    news_count = 0
    error_count = 0
    skipped_count = 0
    total = len(unprocessed_posts)

    # Thread-safe counters
    lock = threading.Lock()
    completed = [0]

    max_workers = settings['max_parallel_tasks']

    def add_log(message: str, level: str = "INFO"):
        """Добавить лог и обновить UI."""
        logger.log(message, level)
        timestamp = datetime.now().strftime("%H:%M:%S")
        icons = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "DEBUG": "🔍"
        }
        icon = icons.get(level, "📝")
        formatted = f"{icon} `{timestamp}` {message}"

        with lock:
            all_logs.append(formatted)
            log_placeholder.markdown("\n".join(all_logs[-100:]))

    add_log(f"🤖 Начало параллельной обработки: {total} постов", "INFO")
    add_log(f"Параллельных потоков: {max_workers}", "INFO")
    add_log(f"Модель: {settings['llm_model']}, temp={settings['llm_temperature']}", "INFO")

    def process_single_post(post, idx, settings_copy):
        """Обработка одного поста в отдельном потоке."""
        nonlocal processed_count, news_count, error_count, skipped_count

        try:
            # Проверка дедупликации
            if is_post_processed(post.post_id):
                with lock:
                    skipped_count += 1
                add_log(f"[{idx}/{total}] ⭕️ Пропущен (уже обработан): {post.post_id}", "WARNING")
                return True

            full_text = f"{post.title}\n\n{post.selftext or ''}"
            text_length = len(full_text.strip())

            if text_length < settings_copy['min_text_length']:
                add_log(
                    f"[{idx}/{total}] ⭕️ Пропущен (текст короче {settings_copy['min_text_length']} символов)",
                    "WARNING"
                )
                with lock:
                    skipped_count += 1
                return True

            add_log(f"[{idx}/{total}] 🤖 Отправка в LLM: {post.title[:60]}...", "DEBUG")

            # Создаем editorial service с настройками из параметра
            from src.services.editorial_service import EditorialService
            editorial = EditorialService(model=settings_copy['llm_model'])

            result = editorial.process_post(
                title=post.title,
                content=full_text,
                source='reddit'
            )

            if result.get('error'):
                with lock:
                    error_count += 1
                error_msg = result['error']
                add_log(f"[{idx}/{total}] ❌ Ошибка LLM: {error_msg}", "ERROR")
                add_log(f"   └─ Пост: {post.title[:50]}...", "ERROR")
                return False

            # Сохранение в БД
            session = get_session()
            try:
                # Двойная проверка перед записью
                existing = session.query(ProcessedRedditPost).filter_by(post_id=post.post_id).first()
                if existing:
                    add_log(f"[{idx}/{total}] ⭕️ Пропущен (уже обработан другим потоком)", "WARNING")
                    with lock:
                        skipped_count += 1
                    return True

                processed_post = ProcessedRedditPost(
                    post_id=post.post_id,
                    original_title=post.title,
                    original_text=post.selftext or '',
                    subreddit=post.subreddit,
                    author=post.author,
                    url=post.url,
                    score=post.score,
                    is_news=result.get('is_news', False),
                    original_summary=result.get('original_summary'),
                    rewritten_post=result.get('rewritten_post'),
                    editorial_title=result.get('title'),
                    teaser=result.get('teaser'),
                    image_prompt=result.get('image_prompt'),
                    processed_at=datetime.utcnow(),
                    processing_time=int(result.get('processing_time', 0) * 1000),
                    model_used=editorial.model
                )

                session.add(processed_post)
                session.commit()

                with lock:
                    processed_count += 1
                    if result.get('is_news'):
                        news_count += 1
                        add_log(f"[{idx}/{total}] 📰 НОВОСТЬ: {result.get('title', 'N/A')[:60]}...", "SUCCESS")
                    else:
                        add_log(f"[{idx}/{total}] 📄 Не новость", "INFO")

                return True

            except Exception as db_error:
                error_msg = str(db_error)
                add_log(f"[{idx}/{total}] ❌ Ошибка БД: {error_msg}", "ERROR")
                add_log(f"   └─ Пост ID: {post.post_id}", "ERROR")
                session.rollback()
                with lock:
                    error_count += 1
                return False
            finally:
                session.close()

        except Exception as e:
            with lock:
                error_count += 1

            error_msg = str(e)
            error_type = type(e).__name__

            # Основная ошибка
            add_log(f"[{idx}/{total}] ❌ Критическая ошибка: {error_type}", "ERROR")
            add_log(f"   └─ Сообщение: {error_msg}", "ERROR")

            # Информация о посте
            try:
                post_title = post.title[:50] if hasattr(post, 'title') else 'Unknown'
                add_log(f"   └─ Пост: {post_title}...", "ERROR")
            except:
                add_log(f"   └─ Пост: [Не удалось получить]", "ERROR")

            # Traceback - построчно
            import traceback
            tb_lines = traceback.format_exc().split('\n')
            add_log(f"   └─ Traceback:", "ERROR")
            for line in tb_lines:
                if line.strip():
                    add_log(f"      {line}", "ERROR")

            return False

    # Параллельное выполнение
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {
                executor.submit(process_single_post, post, idx, settings): idx
                for idx, post in enumerate(unprocessed_posts, 1)
            }

            for future in concurrent.futures.as_completed(futures):
                idx = futures[future]

                with lock:
                    completed[0] += 1
                    progress = completed[0] / total

                progress_bar.progress(progress)
                status_text.info(f"📄 Обработано {completed[0]}/{total} постов")

                try:
                    future.result()
                except Exception as e:
                    add_log(f"❌ Необработанная ошибка в потоке #{idx}: {str(e)}", "ERROR")

        add_log(f"{'=' * 60}", "DEBUG")
        add_log(f"🎉 Обработка завершена!", "SUCCESS")
        add_log(f"Обработано: {processed_count}", "SUCCESS")
        add_log(f"Новостей: {news_count}", "INFO")
        add_log(f"Пропущено: {skipped_count}", "WARNING")
        add_log(f"Ошибок: {error_count}", "ERROR" if error_count > 0 else "INFO")

        progress_bar.progress(1.0)
        status_text.success(
            f"✅ Завершено! Обработано: {processed_count}, Новостей: {news_count}, Пропущено: {skipped_count}")

        return {
            'processed': processed_count,
            'news': news_count,
            'skipped': skipped_count,
            'errors': error_count
        }

    except Exception as e:
        add_log(f"КРИТИЧЕСКАЯ ОШИБКА EXECUTOR: {str(e)}", "ERROR")

        import traceback
        tb_lines = traceback.format_exc().split('\n')
        add_log(f"Полный traceback:", "ERROR")
        for line in tb_lines:
            if line.strip():
                add_log(f"  {line}", "ERROR")

        status_text.error(f"❌ Ошибка: {str(e)}")

        return {
            'processed': processed_count,
            'news': news_count,
            'skipped': skipped_count,
            'errors': error_count
        }

def format_timedelta(td, lang='ru') -> str:
    """Форматирование временного интервала."""
    total_seconds = int(td.total_seconds())
    if total_seconds < 60:
        return f"{total_seconds} {t('sec')} {t('ago')}"
    elif total_seconds < 3600:
        return f"{total_seconds // 60} {t('min')} {t('ago')}"
    elif total_seconds < 86400:
        return f"{total_seconds // 3600} {t('hour')} {t('ago')}"
    else:
        days = total_seconds // 86400
        return f"{days} {t('days')} {t('ago')}"

def count_words(text: str) -> int:
    """Подсчет количества слов в тексте."""
    if not text:
        return 0
    return len(text.split())

def render_raw_post_viewer(post, lang='ru') -> None:
    """Рендеринг сырого Reddit поста с векторной информацией."""
    has_vector = post.qdrant_id is not None
    vector_badge = t('vectorized') if has_vector else t('no_vector')

    now = datetime.now(timezone.utc)
    created_time = post.created_utc.replace(tzinfo=timezone.utc) if post.created_utc.tzinfo is None else post.created_utc
    scraped_time = post.scraped_at.replace(tzinfo=timezone.utc) if post.scraped_at.tzinfo is None else post.scraped_at

    time_since_created = now - created_time
    time_since_scraped = now - scraped_time

    with st.expander(f"r/{post.subreddit} • {post.title[:80]}"):
        col_badge1, col_badge2 = st.columns([1, 1], gap="small")
        with col_badge1:
            st.caption(vector_badge)
        with col_badge2:
            if has_vector:
                st.caption(f"`{str(post.qdrant_id)[:8]}...`")

        st.markdown("---")

        col_time1, col_time2 = st.columns(2, gap="small")
        with col_time1:
            st.markdown(f"**{t('published_reddit')}**")
            st.info(f"{post.created_utc.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            st.caption(format_timedelta(time_since_created, lang))
        with col_time2:
            st.markdown(f"**{t('received_db')}**")
            st.success(f"{post.scraped_at.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            st.caption(format_timedelta(time_since_scraped, lang))

        st.markdown("---")

        col_a, col_b = st.columns([2, 1], gap="small")

        with col_a:
            st.markdown(f"**{t('original_title')}**")
            st.write(post.title)

            st.markdown(f"**{t('original_text')}**")
            if post.selftext:
                st.text_area(
                    t('post_text'),
                    post.selftext,
                    height=200,
                    key=f"raw_{post.id}",
                    label_visibility="collapsed"
                )
            else:
                st.caption(f"_{t('text_missing')}_")

        with col_b:
            st.metric(t('score'), post.score)
            st.metric(t('comments'), post.num_comments)
            st.caption(f"**{t('author')}** u/{post.author}")

            if has_vector:
                st.success(t('in_qdrant'))
                with st.expander(t('qdrant_uuid')):
                    st.code(str(post.qdrant_id))
            else:
                st.warning(t('no_vector'))

            if post.url:
                st.link_button(t('open_original'), post.url)


def render_processed_post_viewer(post, raw_post, lang='ru') -> None:
    """Рендеринг обработанного поста с вкладками."""
    status_icon = "📰" if post.is_news else "❌"

    # Используем teaser как основной заголовок, если есть
    if post.is_news and post.teaser:
        title_display = post.teaser[:80]
    elif post.editorial_title:
        title_display = post.editorial_title[:80]
    else:
        title_display = post.original_title[:80]

    has_vector = raw_post and raw_post.qdrant_id is not None

    now = datetime.now(timezone.utc)

    with st.expander(f"{status_icon} r/{post.subreddit} • {title_display}"):
        # Badges - компактнее
        col_badge1, col_badge2, col_badge3, col_badge4 = st.columns([1, 1, 1, 1], gap="small")
        with col_badge1:
            if post.is_news:
                st.success("✅ News")
            else:
                st.error("❌ Not News")
        with col_badge2:
            if has_vector:
                st.info("🤖 Vector")
            else:
                st.warning("⚠️ No Vec")
        with col_badge3:
            st.caption(f"⚡ {post.processing_time}ms")
        with col_badge4:
            st.caption(f"🤖 {post.model_used or 'gpt-oss'}")

        st.markdown("---")

        # Timeline - компактнее
        if raw_post:
            col_timeline1, col_timeline2, col_timeline3 = st.columns(3, gap="small")
            created_time = raw_post.created_utc.replace(
                tzinfo=timezone.utc) if raw_post.created_utc.tzinfo is None else raw_post.created_utc
            scraped_time = raw_post.scraped_at.replace(
                tzinfo=timezone.utc) if raw_post.scraped_at.tzinfo is None else raw_post.scraped_at
            processed_time = post.processed_at.replace(
                tzinfo=timezone.utc) if post.processed_at.tzinfo is None else post.processed_at

            with col_timeline1:
                st.markdown("**📅 Опубликовано**")
                st.info(f"{raw_post.created_utc.strftime('%Y-%m-%d %H:%M')}")
                st.caption(format_timedelta(now - created_time, lang))
            with col_timeline2:
                st.markdown("**💾 Получено**")
                st.success(f"{raw_post.scraped_at.strftime('%Y-%m-%d %H:%M')}")
                st.caption(format_timedelta(now - scraped_time, lang))
            with col_timeline3:
                st.markdown("**🤖 Обработано**")
                st.warning(f"{post.processed_at.strftime('%Y-%m-%d %H:%M')}")
                st.caption(format_timedelta(now - processed_time, lang))

        st.markdown("---")

        if post.is_news:
            tab_original, tab_llm, tab_meta = st.tabs(["📄 Оригинал", "🤖 LLM Output", "📊 Метаданные"])

            with tab_original:
                st.markdown("### 📌 Оригинальный заголовок")
                st.info(post.original_title)

                st.markdown("### 📝 Оригинальный текст")
                if post.original_text:
                    full_original = f"{post.original_title}\n\n{post.original_text}"
                    st.text_area(
                        "Полный оригинальный текст",
                        full_original,
                        height=400,
                        key=f"orig_full_{post.id}",
                        label_visibility="collapsed"
                    )
                    st.caption(f"📏 Длина: {len(full_original)} символов | Слов: {count_words(full_original)}")
                else:
                    st.caption("_Текст отсутствует_")

            with tab_llm:
                # Teaser как основной заголовок
                st.markdown("### ✨ Заголовок (Teaser)")
                if post.teaser:
                    st.success(f"**{post.teaser}**")
                else:
                    st.caption("_Не создан_")

                st.markdown("### 📰 Редакторский заголовок")
                if post.editorial_title:
                    st.info(post.editorial_title)
                else:
                    st.caption("_Не создан_")

                st.markdown("### ✍️ Переписанный текст (LLM Output)")
                if post.rewritten_post:
                    st.text_area(
                        "Полный переписанный текст от LLM",
                        post.rewritten_post,
                        height=400,
                        key=f"llm_full_{post.id}",
                        label_visibility="collapsed"
                    )

                    # Добавлена статистика по словам
                    original_text = f"{post.original_title}\n\n{post.original_text or ''}"
                    original_len = len(original_text)
                    original_words = count_words(original_text)
                    llm_len = len(post.rewritten_post)
                    llm_words = count_words(post.rewritten_post)

                    diff_chars = llm_len - original_len
                    diff_words = llm_words - original_words
                    diff_pct = (diff_chars / original_len * 100) if original_len > 0 else 0

                    col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4, gap="small")
                    with col_stat1:
                        st.metric("Оригинал", f"{original_words} слов")
                        st.caption(f"{original_len} символов")
                    with col_stat2:
                        st.metric("LLM Output", f"{llm_words} слов")
                        st.caption(f"{llm_len} символов")
                    with col_stat3:
                        st.metric("Δ Слов", f"{diff_words:+d}")
                    with col_stat4:
                        st.metric("Δ Символов", f"{diff_chars:+d} ({diff_pct:+.1f}%)")
                else:
                    st.warning("_Переписанный текст не создан_")

                # Переименован промпт
                st.markdown("### 🎨 Промпт для генерации изображения")
                if post.image_prompt:
                    st.code(post.image_prompt, language="text")
                else:
                    st.caption("_Не создан_")

                st.markdown("### 📋 Краткое содержание (Summary)")
                if post.original_summary:
                    with st.expander("Показать summary"):
                        st.write(post.original_summary)
                else:
                    st.caption("_Не создано_")

            with tab_meta:
                st.markdown("### 📊 Метаданные обработки")

                # Уменьшен gap
                col_m1, col_m2 = st.columns(2, gap="small")

                with col_m1:
                    st.markdown("**🤖 Модель**")
                    st.info(post.model_used or 'gpt-oss')

                    st.markdown("**⚡ Время обработки**")
                    st.info(f"{post.processing_time}ms ({post.processing_time / 1000:.2f}s)")

                    st.markdown("**📅 Дата обработки**")
                    st.info(post.processed_at.strftime('%Y-%m-%d %H:%M:%S UTC'))

                with col_m2:
                    st.markdown("**📰 Классификация**")
                    if post.is_news:
                        st.success("✅ Новость")
                    else:
                        st.error("❌ Не новость")

                    st.markdown("**🎯 Векторизация**")
                    if has_vector:
                        st.success("✅ В Qdrant")
                        if raw_post:
                            st.code(str(raw_post.qdrant_id), language="text")
                    else:
                        st.warning("⚠️ Не векторизован")

                    st.markdown("**⬆️ Score**")
                    st.info(f"{post.score} upvotes")

            st.markdown("---")
            if post.url:
                st.link_button("🔗 Открыть оригинал на Reddit", post.url)
        else:
            st.warning("**❌ Не является новостью**")
            st.caption(f"**Оригинальный заголовок:** {post.original_title}")
            st.caption(f"**Subreddit:** r/{post.subreddit}")
            st.caption(f"**Автор:** u/{post.author}")

            if post.original_text:
                with st.expander("📄 Показать оригинальный текст"):
                    st.text_area(
                        "Оригинальный текст",
                        post.original_text,
                        height=200,
                        key=f"not_news_{post.id}",
                        label_visibility="collapsed"
                    )


def render_settings_section(title: str, settings_dict: dict, icon: str = "⚙️"):
    """
    Рендеринг секции настроек с метриками.

    Args:
        title: Заголовок секции
        settings_dict: Словарь настроек для отображения
        icon: Эмодзи иконка
    """
    with st.expander(f"{icon} {title}", expanded=False):
        # Разбиваем на колонки по 2
        items = list(settings_dict.items())
        cols_per_row = 2

        for i in range(0, len(items), cols_per_row):
            cols = st.columns(cols_per_row)
            for j, col in enumerate(cols):
                if i + j < len(items):
                    key, value = items[i + j]
                    with col:
                        # Форматирование ключа (человекочитаемо)
                        display_key = key.replace('_', ' ').title()

                        # Маскирование паролей и секретов
                        if 'password' in key.lower() or 'secret' in key.lower():
                            display_value = "***" if value else "Not set"
                        else:
                            display_value = str(value)

                        st.metric(display_key, display_value)


# === HEADER ===
col_title, col_spacer, col_lang = st.columns([3, 0.5, 1])

with col_title:
    st.title(t('title'))
    st.caption(t('subtitle'))

with col_lang:
    col_ru, col_en = st.columns(2)
    with col_ru:
        if st.button("🇷🇺 RU", key="lang_ru", use_container_width=True,
                     type="primary" if st.session_state.language == 'ru' else "secondary"):
            st.session_state.language = 'ru'
            st.rerun()
    with col_en:
        if st.button("🇬🇧 EN", key="lang_en", use_container_width=True,
                     type="primary" if st.session_state.language == 'en' else "secondary"):
            st.session_state.language = 'en'
            st.rerun()

# === API STATUS ===
col1, col2, col3 = st.columns(3)
with col1:
    if os.getenv("REDDIT_CLIENT_ID"):
        st.success(t('reddit_api'))
    else:
        st.warning(t('reddit_api'))
with col2:
    if os.getenv("TELEGRAM_API_ID"):
        st.success(t('telegram_api'))
    else:
        st.warning(t('telegram_api'))
with col3:
    st.success(t('database'))

st.markdown("---")

try:
    stats = get_stats_extended()
except:
    stats = {
        'reddit_posts': 0,
        'telegram_messages': 0,
        'medium_articles': 0,
        'latest_reddit': None,
        'latest_telegram': None,
        'latest_medium': None
    }

# === TABS ===
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    t('reddit_tab'),
    t('telegram_tab'),
    t('medium_tab'),
    f"📊 {t('data_viewer_tab')}",
    t('analytics_tab'),
    f"⚙️ {t('settings_tab')}"
])

# === TAB 1: REDDIT PARSER ===
with tab1:
    st.markdown('<div class="reddit-section">', unsafe_allow_html=True)
    st.header(f"{t('reddit_tab')} Parser")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader(t('settings'))

        all_subreddits = config.get_reddit_subreddits()
        categories = config.get_reddit_categories()

        category_filter = st.selectbox(
            t('filter_category'),
            [t('all_categories')] + categories,
            index=0,
            key="reddit_category"
        )

        if category_filter == t('all_categories'):
            filtered_subs = all_subreddits
        else:
            filtered_subs = config.get_reddit_subreddits(category=category_filter)

        if 'reddit_selected' not in st.session_state:
            st.session_state.reddit_selected = []
        if 'reddit_widget_key' not in st.session_state:
            st.session_state.reddit_widget_key = 0

        col_sel1, col_sel2 = st.columns([3, 1])

        with col_sel2:
            st.write("")
            st.write("")
            if st.button(t('select_all'), key="select_all_reddit"):
                st.session_state.reddit_selected = filtered_subs.copy()
                st.session_state.reddit_widget_key += 1
                st.rerun()

        with col_sel1:
            selected_subs = st.multiselect(
                t('subreddits'),
                filtered_subs,
                default=[s for s in st.session_state.reddit_selected if s in filtered_subs],
                key=f"reddit_multiselect_{st.session_state.reddit_widget_key}"
            )
            st.session_state.reddit_selected = selected_subs

        settings = st.session_state.settings

        col_a, col_b, col_c, col_d = st.columns(4)
        with col_a:
            max_posts = st.slider(
                t('max_posts'),
                min_value=1,
                max_value=200,
                value=max(1, settings['default_max_posts']),
                key="reddit_max_posts",
                help="Количество постов для загрузки из каждого subreddit (1-200)",
                disabled=st.session_state.parsing_in_progress
            )
        with col_b:
            delay = st.slider(
                t('delay_sec'),
                3, 30,
                settings['default_delay'],
                key="reddit_delay",
                disabled=st.session_state.parsing_in_progress
            )
        with col_c:
            sort_by = st.selectbox(
                t('sort'),
                ["hot", "new", "top"],
                index=["hot", "new", "top"].index(settings['default_sort']),
                key="reddit_sort",
                disabled=st.session_state.parsing_in_progress
            )
        with col_d:
            enable_llm = st.checkbox(
                t('editorial'),
                value=settings['default_enable_llm'],
                key="reddit_llm",
                disabled=st.session_state.parsing_in_progress
            )

        st.markdown("---")

        # Статус и результаты
        if st.session_state.parsing_results:
            total_saved = sum(r.get('saved', 0) for r in st.session_state.parsing_results if r.get('success'))
            success_count = sum(1 for r in st.session_state.parsing_results if r.get('success'))
            total_count = len(st.session_state.parsing_results)

            st.success(f"✅ Последний парсинг: {total_saved} постов из {success_count}/{total_count} subreddits")

        # Кнопки управления
        col_btn1, col_btn2, col_btn3 = st.columns([2, 1, 1])

        with col_btn1:
            start_button_disabled = (
                    not selected_subs or
                    not os.getenv("REDDIT_CLIENT_ID") or
                    st.session_state.parsing_in_progress
            )

            if st.button(
                    "🚀 " + t('start_parsing') if not st.session_state.parsing_in_progress else "⏸️ Парсинг активен...",
                    type="primary",
                    use_container_width=True,
                    key="reddit_parse_btn",
                    disabled=start_button_disabled
            ):
                if not selected_subs:
                    st.error(t('select_subreddits'))
                elif not os.getenv("REDDIT_CLIENT_ID"):
                    st.error(t('api_not_configured'))
                else:
                    st.markdown("---")
                    results = scrape_with_live_logs(
                        subreddits=selected_subs,
                        max_posts=max_posts,
                        sort_by=sort_by,
                        delay=delay,
                        enable_llm=enable_llm
                    )
                    st.rerun()

        with col_btn2:
            if st.button(
                    "🔄 Обновить",
                    type="secondary",
                    use_container_width=True,
                    key="refresh_page_btn"
            ):
                # Восстанавливаем логи при обновлении
                if st.session_state.log_storage:
                    StreamlitLogger.restore_logs()
                st.rerun()

        with col_btn3:
            if st.button(
                    "🗑️ Очистить",
                    type="secondary",
                    use_container_width=True,
                    key="clear_logs_btn",
                    disabled=st.session_state.parsing_in_progress
            ):
                StreamlitLogger.clear()
                st.session_state.parsing_results = None
                st.success("Логи очищены!")
                time.sleep(0.5)
                st.rerun()

        # Отображение логов
        if st.session_state.parsing_logs or (
                st.session_state.log_storage and st.session_state.log_storage.log_file.exists()):
            with st.expander("📜 Все логи сессии", expanded=False):
                # Если логи есть в памяти
                if st.session_state.parsing_logs:
                    st.markdown("\n".join(list(st.session_state.parsing_logs)))
                # Если нет - попробуем восстановить
                elif st.session_state.log_storage:
                    if st.button("🔄 Загрузить логи из файла"):
                        StreamlitLogger.restore_logs()
                        st.rerun()

    with col2:
        st.subheader(t('statistics'))
        st.metric(t('posts'), f"{stats['reddit_posts']:,}")

        # Статистика обработки
        try:
            from src.models.database import get_processing_statistics

            proc_stats = get_processing_statistics()

            st.metric("Обработано", f"{proc_stats['total_processed']:,}")
            st.metric("Новостей", f"{proc_stats['total_news']:,}")

            if proc_stats['total_raw'] > 0:
                st.progress(
                    proc_stats['processing_rate'] / 100,
                    text=f"Обработка: {proc_stats['processing_rate']}%"
                )
        except Exception as e:
            st.caption(f"Ошибка статистики: {e}")

    st.markdown('</div>', unsafe_allow_html=True)

# === TAB 2: TELEGRAM ===
with tab2:
    st.markdown('<div class="telegram-section">', unsafe_allow_html=True)
    st.header(f"{t('telegram_tab')} Parser")
    st.info(t('in_development'))
    st.markdown('</div>', unsafe_allow_html=True)

# === TAB 3: MEDIUM ===
with tab3:
    st.markdown('<div class="medium-section">', unsafe_allow_html=True)
    st.header(f"{t('medium_tab')} Parser")
    st.info(t('in_development'))
    st.markdown('</div>', unsafe_allow_html=True)

# === TAB 4: UNIFIED DATA VIEWER ===
with tab4:
    st.header("📊 Просмотр данных Reddit")

    # Управление предобработкой
    with st.expander("🔧 Управление предобработкой", expanded=False):
        st.markdown(f"### {t('sync_processing')}")
        st.caption(t('process_raw_posts'))

        col_sync1, col_sync2 = st.columns([2, 1])

        with col_sync1:
            st.markdown(f"**{t('statistics')}:**")
            try:
                session = get_session()
                total_raw = session.query(RedditPost).count()
                total_processed = session.query(ProcessedRedditPost).count()

                from sqlalchemy import exists

                unprocessed_count = session.query(RedditPost).filter(
                    ~exists().where(ProcessedRedditPost.post_id == RedditPost.post_id)
                ).count()

                session.close()

                col_a, col_b, col_c = st.columns(3)
                with col_a:
                    st.metric(t('raw_posts'), total_raw)
                with col_b:
                    st.metric(t('processed'), total_processed)
                with col_c:
                    st.metric(t('unprocessed'), unprocessed_count)

            except Exception as e:
                st.error(t('statistics_error', error=str(e)))
                unprocessed_count = 0

        with col_sync2:
            st.markdown(f"**{t('settings')}:**")
            batch_size = st.number_input(
                t('batch_size'),
                min_value=1,
                max_value=100,
                value=st.session_state.settings['batch_size'],
                help=t('batch_size_help'),
                key="batch_size_input"
            )

        st.markdown("---")

        if st.button(
                t('start_processing'),
                type="primary",
                use_container_width=True,
                key="start_processing_btn"
        ):
            if unprocessed_count == 0:
                st.info(t('no_unprocessed'))
            else:
                try:
                    from src.models.database import get_unprocessed_posts

                    unprocessed_posts = get_unprocessed_posts(limit=batch_size)

                    if not unprocessed_posts:
                        st.warning(t('no_posts_process'))
                    else:
                        st.markdown("---")
                        st.subheader("🤖 Обработка LLM в процессе...")

                        results = process_posts_with_live_logs(unprocessed_posts)

                        st.markdown("---")
                        st.success(f"✅ Обработка завершена!")

                        col_r1, col_r2, col_r3, col_r4 = st.columns(4)
                        with col_r1:
                            st.metric("Обработано", results['processed'])
                        with col_r2:
                            st.metric("Новостей", results['news'])
                        with col_r3:
                            st.metric("Пропущено", results['skipped'])
                        with col_r4:
                            st.metric("Ошибок", results['errors'])

                        if results['errors'] > 0:
                            st.error(f"⚠️ Обнаружено {results['errors']} ошибок. Проверьте логи выше для деталей.")
                            st.info(
                                "💡 Совет: Прокрутите логи вверх и найдите сообщения с ❌ для просмотра деталей ошибок.")

                        if st.button("🔄 Обновить страницу", key="refresh_after_processing"):
                            st.rerun()

                except Exception as e:
                    st.error(f"❌ Критическая ошибка: {e}")

                    with st.expander("🔍 Детальная информация об ошибке"):
                        import traceback

                        st.code(traceback.format_exc(), language="python")

    st.markdown("---")

    # Настройки отображения
    col_filter, col_sort, col_limit = st.columns([2, 2, 1])

    with col_filter:
        # ИЗМЕНЕНИЕ: index=2 для выбора "Все посты" по умолчанию
        view_mode = st.radio(
            "Режим просмотра",
            ["🔴 Только сырые", "🤖 Только обработанные", "📋 Все посты"],
            index=2,  # <-- По умолчанию "Все посты"
            horizontal=True,
            key="view_mode_radio"
        )

        # Дополнительный фильтр для обработанных
        news_only = False
        if "обработанные" in view_mode.lower():
            news_only = st.checkbox("Только новости", value=False, key="news_filter")

    with col_sort:
        # Динамическая сортировка в зависимости от режима
        if "сырые" in view_mode.lower():
            sort_options = {
                "Получены (новые)": "scraped_at_desc",
                "Получены (старые)": "scraped_at_asc",
                "Опубликованы (новые)": "created_utc_desc",
                "Опубликованы (старые)": "created_utc_asc",
                "Рейтинг ⬆": "score_desc",
                "Рейтинг ⬇": "score_asc"
            }
        elif "обработанные" in view_mode.lower():
            sort_options = {
                "Обработаны (новые)": "processed_at_desc",
                "Обработаны (старые)": "processed_at_asc",
                "Рейтинг ⬆": "score_desc",
                "Рейтинг ⬇": "score_asc"
            }
        else:  # Все посты
            sort_options = {
                "Обработаны (новые)": "processed_at_desc",
                "Получены (новые)": "scraped_at_desc",
                "Рейтинг ⬆": "score_desc"
            }

        sort_by = st.selectbox(
            "Сортировка",
            list(sort_options.keys()),
            key="unified_sort"
        )
        sort_value = sort_options[sort_by]

    with col_limit:
        limit = st.slider(
            "Записей",
            10, 500,
            st.session_state.settings['viewer_default_limit'],
            key="unified_limit"
        )

    st.markdown("---")

    # Загрузка и отображение данных
    try:
        session = get_session()

        if view_mode == "🔴 Только сырые":
            # Показываем только сырые посты
            query = session.query(RedditPost)

            if sort_value == "scraped_at_desc":
                query = query.order_by(RedditPost.scraped_at.desc())
            elif sort_value == "scraped_at_asc":
                query = query.order_by(RedditPost.scraped_at.asc())
            elif sort_value == "created_utc_desc":
                query = query.order_by(RedditPost.created_utc.desc())
            elif sort_value == "created_utc_asc":
                query = query.order_by(RedditPost.created_utc.asc())
            elif sort_value == "score_desc":
                query = query.order_by(RedditPost.score.desc())
            elif sort_value == "score_asc":
                query = query.order_by(RedditPost.score.asc())

            posts = query.limit(limit).all()

            if posts:
                st.caption(f"🔴 Найдено: {len(posts)} сырых постов")
                for post in posts:
                    render_raw_post_viewer(post, st.session_state.language)
            else:
                st.info("Нет сырых постов")

        elif view_mode == "🤖 Только обработанные":
            # Показываем только обработанные посты
            query = session.query(ProcessedRedditPost)

            if news_only:
                query = query.filter(ProcessedRedditPost.is_news == True)

            if sort_value == "processed_at_desc":
                query = query.order_by(ProcessedRedditPost.processed_at.desc())
            elif sort_value == "processed_at_asc":
                query = query.order_by(ProcessedRedditPost.processed_at.asc())
            elif sort_value == "score_desc":
                query = query.order_by(ProcessedRedditPost.score.desc())
            elif sort_value == "score_asc":
                query = query.order_by(ProcessedRedditPost.score.asc())

            processed_posts = query.limit(limit).all()

            if processed_posts:
                filter_text = " (только новости)" if news_only else ""
                st.caption(f"🤖 Найдено: {len(processed_posts)} обработанных постов{filter_text}")

                for proc_post in processed_posts:
                    raw_post = session.query(RedditPost).filter_by(post_id=proc_post.post_id).first()
                    render_processed_post_viewer(proc_post, raw_post, st.session_state.language)
            else:
                st.info("Нет обработанных постов" + (" (новостей)" if news_only else ""))

        else:  # 📋 Все посты
            # Показываем обработанные посты с возможностью развернуть сырые
            query = session.query(ProcessedRedditPost)

            if news_only:
                query = query.filter(ProcessedRedditPost.is_news == True)

            if sort_value == "processed_at_desc":
                query = query.order_by(ProcessedRedditPost.processed_at.desc())
            elif sort_value == "scraped_at_desc":
                # Присоединяем RedditPost для сортировки по scraped_at
                query = query.join(RedditPost, ProcessedRedditPost.post_id == RedditPost.post_id)
                query = query.order_by(RedditPost.scraped_at.desc())
            elif sort_value == "score_desc":
                query = query.order_by(ProcessedRedditPost.score.desc())

            processed_posts = query.limit(limit).all()

            if processed_posts:
                filter_text = " (только новости)" if news_only else ""
                st.caption(f"📋 Найдено: {len(processed_posts)} постов{filter_text}")

                for proc_post in processed_posts:
                    raw_post = session.query(RedditPost).filter_by(post_id=proc_post.post_id).first()
                    render_processed_post_viewer(proc_post, raw_post, st.session_state.language)
            else:
                st.info("Нет данных" + (" (новостей)" if news_only else ""))

        session.close()

        # Статистика векторизации
        st.markdown("---")
        st.subheader("📊 Статистика векторизации")

        col_stat1, col_stat2, col_stat3, col_stat4 = st.columns(4, gap="small")

        session = get_session()
        total_posts = session.query(RedditPost).count()
        vectorized_posts = session.query(RedditPost).filter(RedditPost.qdrant_id.isnot(None)).count()
        total_processed = session.query(ProcessedRedditPost).count()
        news_count = session.query(ProcessedRedditPost).filter(ProcessedRedditPost.is_news == True).count()
        session.close()

        with col_stat1:
            st.metric("Всего постов", total_posts)
        with col_stat2:
            st.metric("Векторизовано", vectorized_posts)
        with col_stat3:
            st.metric("Обработано", total_processed)
        with col_stat4:
            st.metric("Новостей", news_count)

        # Прогресс-бары
        col_prog1, col_prog2 = st.columns(2)
        with col_prog1:
            if total_posts > 0:
                vec_pct = vectorized_posts / total_posts
                st.progress(vec_pct, text=f"Векторизация: {vec_pct:.1%}")
            else:
                st.progress(0.0, text="Векторизация: 0%")

        with col_prog2:
            if total_posts > 0:
                proc_pct = total_processed / total_posts
                st.progress(proc_pct, text=f"Обработка: {proc_pct:.1%}")
            else:
                st.progress(0.0, text="Обработка: 0%")

    except Exception as e:
        st.error(f"Ошибка загрузки данных: {e}")
        import traceback

        st.code(traceback.format_exc())

# === TAB 5: ANALYTICS ===
with tab5:
    st.header(t('analytics_tab'))

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Reddit", f"{stats['reddit_posts']:,}")
    with col2:
        st.metric("Telegram", f"{stats['telegram_messages']:,}")
    with col3:
        st.metric("Medium", f"{stats['medium_articles']:,}")
    with col4:
        total = stats['reddit_posts'] + stats['telegram_messages'] + stats['medium_articles']
        st.metric(t('total'), f"{total:,}")

    st.markdown("---")

    if total > 0:
        st.subheader(t('activity'))

        chart_data = pd.DataFrame({
            t('platform'): ['Reddit', 'Telegram', 'Medium'],
            t('records_count'): [
                stats['reddit_posts'],
                stats['telegram_messages'],
                stats['medium_articles']
            ]
        })
        st.bar_chart(chart_data.set_index(t('platform')))
    else:
        st.info(t('no_data'))

# === TAB 6: SETTINGS ===
with tab6:
    st.header("⚙️ Настройки")

    st.subheader("🤖 LLM Обработка")
    col_llm1, col_llm2 = st.columns(2)
    with col_llm1:
        st.metric("Модель", st.session_state.settings['llm_model'])
        st.metric("Temperature", st.session_state.settings['llm_temperature'])
    with col_llm2:
        st.metric("Max Tokens", st.session_state.settings['llm_max_tokens'])
        st.metric("Параллельных потоков", st.session_state.settings['max_parallel_tasks'])

    st.markdown("---")

    # ИЗМЕНЕНИЕ: Структурированное отображение настроек по категориям
    st.subheader("📋 Конфигурация приложения")

    settings = st.session_state.settings

    # Группировка настроек по категориям
    database_settings = {
        'postgres_user': settings['postgres_user'],
        'postgres_db': settings['postgres_db'],
        'postgres_port': settings['postgres_port']
    }

    reddit_settings = {
        'reddit_client_id': settings['reddit_client_id'],
        'reddit_client_secret': settings['reddit_client_secret'],
        'reddit_user_agent': settings['reddit_user_agent']
    }

    telegram_settings = {
        'telegram_api_id': settings['telegram_api_id'],
        'telegram_api_hash': settings['telegram_api_hash'],
        'telegram_phone': settings['telegram_phone']
    }

    llm_settings = {
        'llm_provider': settings['llm_provider'],
        'llm_model': settings['llm_model'],
        'llm_temperature': settings['llm_temperature'],
        'llm_max_tokens': settings['llm_max_tokens'],
        'llm_top_p': settings['llm_top_p'],
        'max_parallel_tasks': settings['max_parallel_tasks']
    }

    services_settings = {
        'qdrant_url': settings['qdrant_url'],
        'qdrant_port': settings['qdrant_port'],
        'ollama_base_url': settings['ollama_base_url'],
        'ollama_port': settings['ollama_port']
    }

    parsing_settings = {
        'default_max_posts': settings['default_max_posts'],
        'default_delay': settings['default_delay'],
        'default_sort': settings['default_sort'],
        'default_enable_llm': settings['default_enable_llm'],
        'batch_size': settings['batch_size'],
        'min_text_length': settings['min_text_length']
    }

    quality_settings = {
        'enable_semantic_dedup': settings['enable_semantic_dedup'],
        'enable_vectorization': settings['enable_vectorization']
    }

    ui_settings = {
        'logs_max_length': settings['logs_max_length'],
        'viewer_default_limit': settings['viewer_default_limit'],
        'show_debug_info': settings['show_debug_info'],
        'app_port': settings['app_port']
    }

    # Рендеринг категорий
    render_settings_section("База данных (PostgreSQL)", database_settings, "🗄️")
    render_settings_section("Reddit API", reddit_settings, "🔴")
    render_settings_section("Telegram API", telegram_settings, "💬")
    render_settings_section("LLM & AI", llm_settings, "🤖")
    render_settings_section("Сервисы (Qdrant, Ollama)", services_settings, "🔧")
    render_settings_section("Параметры парсинга", parsing_settings, "📥")
    render_settings_section("Качество и дедупликация", quality_settings, "✨")
    render_settings_section("Пользовательский интерфейс", ui_settings, "🎨")

    # Экспорт в JSON/YAML
    st.markdown("---")
    st.subheader("💾 Экспорт настроек")

    col_export1, col_export2 = st.columns(2)

    with col_export1:
        if st.button("📄 Скачать JSON", use_container_width=True):
            json_str = json.dumps(settings, indent=2, ensure_ascii=False)
            st.download_button(
                label="⬇️ Сохранить settings.json",
                data=json_str,
                file_name="settings.json",
                mime="application/json"
            )

    with col_export2:
        if st.button("📋 Показать raw JSON", use_container_width=True):
            with st.expander("Raw JSON", expanded=True):
                st.json(settings)

# === FOOTER ===
st.markdown("---")
col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
with col_f1:
    st.caption("PostgreSQL • Docker • N8N • Ollama • GPT-OSS")
with col_f2:
    current_model = st.session_state.settings['llm_model']
    st.caption(f"🤖 Model: {current_model}")
with col_f3:
    if st.button("🔄 Обновить", key="refresh_btn"):
        st.rerun()