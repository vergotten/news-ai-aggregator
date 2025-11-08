"""
Веб-интерфейс Streamlit для News Aggregator с живыми логами.

Этот модуль предоставляет панель управления для парсинга данных из различных источников
(Reddit, Habr, Telegram, Medium), их обработки с помощью LLM, просмотра результатов
и мониторинга статистики.
"""

import streamlit as st
import sys
import os
from pathlib import Path
import pandas as pd
import time
import uuid
from collections import deque
import json
import multiprocessing
from queue import Empty
import requests
from datetime import datetime, timezone, timedelta

from src.scrapers.telegram_scraper import scrape_telegram_channels

# Добавляем корневую директорию в sys.path для импортов
sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(
    page_title="News Aggregator",
    page_icon="📰",
    layout="wide"
)

try:
    from src.config.config import get_config
    config = get_config()
    st.success("✅ Конфигурация загружена успешно")
except FileNotFoundError as e:
    st.error("❌ Файл .env не найден!")
    st.error(str(e))
    st.stop()
except ValueError as e:
    st.error("❌ Невалидная конфигурация!")
    st.error(str(e))
    st.stop()
except Exception as e:
    st.error(f"❌ Ошибка загрузки конфигурации: {e}")
    st.stop()

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

try:
    from src.models.database import (
        init_db,
        get_stats_extended,
        # get_posts_by_subreddit,
        # get_processed_posts,
        # get_processed_by_subreddit,
        # get_medium_articles,
        # get_habr_articles,
        # get_session,
        # get_processing_statistics,
        # is_post_processed,
        # get_unprocessed_posts,
        RedditPost,
        ProcessedRedditPost,
        MediumArticle,
        TelegramMessage,
        HabrArticle,
        TelegramPost,
        TelegramPostRepository, # Импортируем репозиторий
    )
    from src.config_loader import get_config as get_sources_config
    from src.services.editorial_service import EditorialService
    from src.scrapers.reddit_scraper import get_reddit_client, scrape_subreddit

    init_db()
    sources_config = get_sources_config()
except Exception as e:
    st.error(f"Ошибка инициализации: {e}")
    st.stop()

# ============================================================================
# НАСТРОЙКИ ИЗ ЦЕНТРАЛИЗОВАННОЙ КОНФИГУРАЦИИ
# ============================================================================
# Создаём SETTINGS из config для обратной совместимости
SETTINGS = {
    # PostgreSQL
    'postgres_user': config.POSTGRES_USER,
    'postgres_password': config.POSTGRES_PASSWORD,
    'postgres_db': config.POSTGRES_DB,
    'postgres_port': config.POSTGRES_PORT,

    # Reddit API
    'reddit_client_id': config.REDDIT_CLIENT_ID,
    'reddit_client_secret': config.REDDIT_CLIENT_SECRET,
    'reddit_user_agent': config.REDDIT_USER_AGENT,

    # Telegram API
    'telegram_api_id': config.TELEGRAM_API_ID,
    'telegram_api_hash': config.TELEGRAM_API_HASH,
    'telegram_phone': config.TELEGRAM_PHONE,

    # Qdrant
    'qdrant_port': config.QDRANT_PORT,
    'qdrant_grpc_port': config.QDRANT_GRPC_PORT,
    'qdrant_url': config.QDRANT_URL,

    # Ollama
    'ollama_port': config.OLLAMA_PORT,
    'ollama_base_url': config.OLLAMA_BASE_URL,

    # Приложение
    'app_port': config.APP_PORT,
    'tz': config.TZ,
    'adminer_port': config.ADMINER_PORT,

    # LLM Processing
    'max_parallel_tasks': config.MAX_PARALLEL_TASKS,

    # N8N
    'n8n_port': config.N8N_PORT,
    'n8n_db': config.N8N_DB,
    'n8n_basic_auth_active': config.N8N_BASIC_AUTH_ACTIVE,
    'n8n_basic_auth_user': config.N8N_BASIC_AUTH_USER,
    'n8n_basic_auth_password': config.N8N_BASIC_AUTH_PASSWORD,

    # LLM
    'llm_provider': config.LLM_PROVIDER,
    'llm_model': config.LLM_MODEL,
    'llm_temperature': config.LLM_TEMPERATURE,
    'llm_max_tokens': config.LLM_MAX_TOKENS,
    'llm_top_p': config.LLM_TOP_P,
    'llm_base_url': config.LLM_BASE_URL,

    # Парсинг
    'default_max_posts': config.DEFAULT_MAX_POSTS,
    'default_delay': config.DEFAULT_DELAY,
    'default_sort': config.DEFAULT_SORT,
    'default_enable_llm': config.DEFAULT_ENABLE_LLM,
    'batch_size': config.BATCH_SIZE,

    # Качество
    'min_text_length': config.MIN_TEXT_LENGTH,
    'enable_semantic_dedup': config.ENABLE_SEMANTIC_DEDUP,
    'enable_vectorization': config.ENABLE_VECTORIZATION,

    # UI
    'logs_max_length': config.LOGS_MAX_LENGTH,
    'viewer_default_limit': config.VIEWER_DEFAULT_LIMIT,
    'show_debug_info': config.SHOW_DEBUG_INFO
}

# ============================================================================
# ИНИЦИАЛИЗАЦИЯ SESSION STATE
# ============================================================================
# Инициализация базовых настроек
if 'settings' not in st.session_state:
    st.session_state.settings = SETTINGS

# Инициализация лог менеджера
if 'log_manager' not in st.session_state:
    try:
        from src.utils.log_manager import get_log_manager
        st.session_state.log_manager = get_log_manager()
    except Exception as e:
        st.error(f"Ошибка инициализации лог менеджера: {e}")
        st.session_state.log_manager = None

# Инициализация состояния парсинга
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

if 'current_session_id' not in st.session_state:
    st.session_state.current_session_id = None

if 'logs_restored' not in st.session_state:
    st.session_state.logs_restored = False

# ============================================================================
# ФУНКЦИИ ВОССТАНОВЛЕНИЯ И ПРОВЕРКИ
# ============================================================================

def restore_logs():
    """Восстановить логи из Redis при загрузке страницы."""
    if not st.session_state.logs_restored and st.session_state.get('log_manager'):
        try:
            log_manager = st.session_state.log_manager
            logs = log_manager.get_logs(limit=100)

            if logs:
                # Конвертируем логи из Redis в формат Streamlit
                formatted_logs = []
                for log in logs:
                    icon = {"INFO": "ℹ️", "SUCCESS": "✅", "WARNING": "⚠️", "ERROR": "❌", "DEBUG": "🔍"}.get(log.get('level', 'INFO'), "📝")
                    timestamp = log.get('timestamp', '')[:8]  # Только время
                    formatted_logs.append(f"{icon} `{timestamp}` {log.get('message', '')}")

                st.session_state.parsing_logs = deque(
                    formatted_logs,
                    maxlen=st.session_state.settings['logs_max_length']
                )

            st.session_state.logs_restored = True
        # ИСПРАВЛЕНО: Заменен голый except на конкретный тип для лучшей отладки
        except Exception as e:
            st.error(f"Ошибка восстановления логов: {e}")

def check_active_sessions():
    """Проверить наличие активных сессий парсинга."""
    if st.session_state.get('log_manager'):
        try:
            log_manager = st.session_state.log_manager
            active_sessions = log_manager.get_active_sessions()

            if active_sessions:
                st.session_state.current_session_id = active_sessions[0]['id']
                st.session_state.parsing_active = True
                return True
        # ИСПРАВЛЕНО: Заменен голый except на конкретный тип для лучшей отладки
        except Exception as e:
            st.warning(f"Ошибка проверки активных сессий: {e}")

    return False

# Вызываем восстановление и проверку при загрузке
restore_logs()
check_active_sessions()

# ============================================================================
# КЛАССЫ И ФУНКЦИИ
# ============================================================================

class StreamlitLogger:
    """Логгер, записывающий сообщения в session_state для отображения в UI."""

    @staticmethod
    def log(message: str, level: str = "INFO") -> None:
        """Добавить лог-сообщение."""
        from datetime import datetime, timezone, timedelta
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Moscow time (UTC+3)
        moscow_tz = timezone(timedelta(hours=3))
        timestamp = datetime.now(moscow_tz).strftime("%H:%M:%S")

        icon = {"INFO": "ℹ️", "SUCCESS": "✅", "WARNING": "⚠️", "ERROR": "❌", "DEBUG": "🔍"}.get(level, "📝")
        log_entry = f"{icon} `{timestamp}` {message}"
        st.session_state.parsing_logs.append(log_entry)

        # Также отправляем в лог менеджер
        if st.session_state.get('log_manager'):
            try:
                st.session_state.log_manager.add_log(message, level, st.session_state.get('current_session_id'))
            except Exception as e:
                st.warning(f"Ошибка сохранения лога: {e}")

    @staticmethod
    def add_separator(session_number: int) -> None:
        """Добавить разделитель между сессиями парсинга."""
        from datetime import datetime, timezone, timedelta

        moscow_tz = timezone(timedelta(hours=3))
        separator = (
            f"\n{'=' * 80}\n"
            f"🆕 **НОВАЯ СЕССИЯ #{session_number}** - "
            f"{datetime.now(moscow_tz).strftime('%Y-%m-%d %H:%M:%S')}\n"
            f"{'=' * 80}\n"
        )
        st.session_state.parsing_logs.append(separator)

    @staticmethod
    def clear() -> None:
        """Очистить логи."""
        st.session_state.parsing_logs.clear()
        st.session_state.log_session_counter = 0

        # Очищаем также в Redis
        if st.session_state.get('log_manager'):
            try:
                st.session_state.log_manager.clear_logs()
            except Exception as e:
                st.warning(f"Ошибка очистки логов: {e}")

# ============================================================================
# HABR SCRAPER - MULTIPROCESSING WRAPPER
# ============================================================================

def habr_scraper_worker(
        hubs: list,
        tags: list,
        max_articles: int,
        enable_llm: bool,
        enable_dedup: bool,
        log_queue: multiprocessing.Queue,
        result_queue: multiprocessing.Queue
):
    """Worker процесс для запуска скрипта-раннера Habr."""
    import sys
    import subprocess
    import traceback
    from pathlib import Path

    project_root = Path(__file__).parent.parent
    runner_script = project_root / "src" / "scrapers" / "run_habr_scraper.py"

    def process_log_callback(message: str, level: str):
        try:
            log_queue.put({'message': message, 'level': level})
        except Exception as e:
            print(f"Error in log callback: {e}")

    # Настройка переменных окружения для предотвращения проблем с Scrapy
    env = os.environ.copy()
    env['PYTHONPATH'] = str(project_root)
    env['SCRAPY_SETTINGS_MODULE'] = 'src.scrapers.settings'

    try:
        # Формирование команды с правильными аргументами
        cmd = [
            sys.executable, str(runner_script),
            '--max-articles', str(max_articles)  # ✓ hyphen, не underscore
        ]

        # Добавляем хабы через запятую
        if hubs:
            cmd.extend(['--hubs', ','.join(hubs)])

        # Флаги - БЕЗ явных значений True/False
        if enable_llm:
            cmd.append('--enable-llm')
        else:
            cmd.append('--no-llm')

        if enable_dedup:
            cmd.append('--enable-dedup')
        else:
            cmd.append('--no-dedup')

        process_log_callback(f"Executing command: {' '.join(cmd)}", "INFO")
        process_log_callback(f"Working directory: {project_root}", "DEBUG")

        # Запуск процесса с улучшенной обработкой вывода
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            bufsize=1,
            cwd=str(project_root),
            env=env
        )

        # Чтение вывода в реальном времени
        output_lines = []
        while True:
            output = process.stdout.readline()
            if output == '' and process.poll() is not None:
                break
            if output:
                output_lines.append(output.strip())

                # Определение уровня логирования
                if "INFO" in output:
                    level = "INFO"
                elif "WARNING" in output or "WARN" in output:
                    level = "WARNING"
                elif "ERROR" in output or "CRITICAL" in output:
                    level = "ERROR"
                elif "SUCCESS" in output:
                    level = "SUCCESS"
                else:
                    level = "INFO"

                process_log_callback(output.strip(), level)

        # Получение кода возврата
        return_code = process.poll()

        # Анализ результатов
        if return_code == 0:
            process_log_callback("Habr scraping completed successfully.", "SUCCESS")

            # Попытка извлечь статистику из вывода
            saved = 0
            skipped = 0
            errors = 0

            for line in output_lines:
                if "Сохранено:" in line:
                    try:
                        saved = int(line.split("Сохранено:")[1].strip())
                    except (ValueError, IndexError):
                        pass
                elif "Пропущено:" in line:
                    try:
                        skipped = int(line.split("Пропущено:")[1].strip())
                    except (ValueError, IndexError):
                        pass
                elif "Ошибок:" in line:
                    try:
                        errors = int(line.split("Ошибок:")[1].strip())
                    except (ValueError, IndexError):
                        pass

            result = {
                'success': True,
                'saved': saved,
                'skipped': skipped,
                'semantic_duplicates': 0,
                'editorial_processed': 0,
                'errors': errors
            }
            result_queue.put(result)
        else:
            process_log_callback(f"Habr scraping failed with return code {return_code}.", "ERROR")
            result_queue.put({
                'success': False,
                'error': f'Process failed with code {return_code}',
                'saved': 0,
                'skipped': 0,
                'semantic_duplicates': 0,
                'editorial_processed': 0,
                'errors': 1
            })

    except Exception as e:
        error_msg = f"Critical error in habr_scraper_worker: {str(e)}"
        process_log_callback(error_msg, "ERROR")
        traceback.print_exc()
        result_queue.put({
            'success': False,
            'error': str(e),
            'saved': 0,
            'skipped': 0,
            'semantic_duplicates': 0,
            'editorial_processed': 0,
            'errors': 1
        })

def scrape_habr_with_live_logs(
    hubs: list,
    tags: list,
    max_articles: int,
    enable_llm: bool = True,
    enable_dedup: bool = True,
) -> dict:
    """
    Синхронная обертка для запуска Habr парсинга с живыми логами.
    """
    logger = StreamlitLogger()

    # Создаем новую сессию
    if st.session_state.get('log_manager'):
        session_id = st.session_state.log_manager.create_session()
        st.session_state.current_session_id = session_id
    else:
        # ИСПРАВЛЕНИЕ: `uuid` теперь импортирован, ошибки не будет
        session_id = str(uuid.uuid4())

    st.session_state.log_session_counter += 1
    logger.add_separator(st.session_state.log_session_counter)

    # Устанавливаем флаг активного парсинга
    st.session_state.parsing_active = True
    st.session_state.parsing_in_progress = True

    progress_bar = st.progress(0)
    status_text = st.empty()
    log_container = st.expander("📋 **Логи парсинга Habr**", expanded=True)
    log_placeholder = log_container.empty()

    logger.log(f"🚀 Начало парсинга Habr", "INFO")
    logger.log(f"Сессия: {session_id[:8]}...", "DEBUG")
    logger.log(f"Хабы: {', '.join(hubs) if hubs else 'По умолчанию'}", "INFO")
    logger.log(f"Теги: {', '.join(tags) if tags else 'По умолчанию'}", "INFO")
    logger.log(f"Max статей: {max_articles}, LLM: {'ON' if enable_llm else 'OFF'}, Dedup: {'ON' if enable_dedup else 'OFF'}", "INFO")

    # Создаем очереди для межпроцессного обмена
    log_queue = multiprocessing.Queue()
    result_queue = multiprocessing.Queue()

    # Запускаем worker процесс
    process = multiprocessing.Process(
        target=habr_scraper_worker,
        args=(hubs, tags, max_articles, enable_llm, enable_dedup, log_queue, result_queue)
    )

    try:
        process.start()

        # Индикатор прогресса (неопределенный)
        progress = 0.0
        progress_direction = 0.01

        # Читаем логи в реальном времени
        while process.is_alive() or not log_queue.empty():
            try:
                # Получаем лог с таймаутом
                log_entry = log_queue.get(timeout=0.1)
                logger.log(log_entry['message'], log_entry['level'])
                log_placeholder.markdown("\n".join(st.session_state.parsing_logs))
            except Empty:
                pass

            # Обновляем прогресс-бар (пульсирующий эффект)
            progress += progress_direction
            if progress >= 1.0 or progress <= 0.0:
                progress_direction *= -1
            progress_bar.progress(min(max(progress, 0.0), 1.0))
            status_text.info("🔄 Парсинг Habr в процессе...")

            time.sleep(0.1)

        # Ждем завершения процесса
        process.join(timeout=5)

        # Получаем результат
        try:
            result = result_queue.get(timeout=1)
        except Empty:
            result = {
                'success': False,
                'error': 'Timeout: результат не получен',
                'saved': 0,
                'skipped': 0,
                'semantic_duplicates': 0,
                'editorial_processed': 0,
                'errors': 1
            }

        # Финальное обновление логов
        logger.log("="*60, "DEBUG")

        if result.get('success'):
            saved = result.get('saved', 0)
            skipped = result.get('skipped', 0)
            semantic_dups = result.get('semantic_duplicates', 0)
            editorial = result.get('editorial_processed', 0)
            errors = result.get('errors', 0)

            logger.log(f"🎉 Парсинг завершён!", "SUCCESS")
            logger.log(f"Сохранено: {saved}", "SUCCESS")
            logger.log(f"Пропущено: {skipped}", "INFO")
            if semantic_dups > 0:
                logger.log(f"Дубликатов: {semantic_dups}", "INFO")
            if enable_llm and editorial > 0:
                logger.log(f"Обработано LLM: {editorial}", "SUCCESS")
            if errors > 0:
                logger.log(f"Ошибок: {errors}", "WARNING")

            progress_bar.progress(1.0)
            status_text.success(f"✅ Завершено! Сохранено {saved} статей")
        else:
            error = result.get('error', 'Unknown error')
            logger.log(f"❌ Ошибка: {error}", "ERROR")
            progress_bar.progress(0.0)
            status_text.error(f"❌ Ошибка парсинга")

        log_placeholder.markdown("\n".join(st.session_state.parsing_logs))

        # Сохраняем результат
        st.session_state.habr_parsing_results = result

        return result

    # ИСПРАВЛЕНО: Заменен голый except на конкретный тип для лучшей отладки
    except Exception as e:
        logger.log(f"КРИТИЧЕСКАЯ ОШИБКА: {str(e)}", "ERROR")
        status_text.error(f"❌ Ошибка: {str(e)}")
        log_placeholder.markdown("\n".join(st.session_state.parsing_logs))

        if process.is_alive():
            process.terminate()
            process.join()

        return {
            'success': False,
            'error': str(e),
            'saved': 0,
            'skipped': 0,
            'semantic_duplicates': 0,
            'editorial_processed': 0,
            'errors': 1
        }
    finally:
        # Сбрасываем флаги
        st.session_state.parsing_active = False
        st.session_state.parsing_in_progress = False

        # Закрываем сессию
        if st.session_state.get('log_manager') and session_id:
            try:
                st.session_state.log_manager.close_session(session_id)
            except Exception as e:
                logger.log(f"Ошибка закрытия сессии: {e}", "WARNING")


def scrape_with_live_logs(subreddits: list[str], max_posts: int, sort_by: str, delay: int, enable_llm: bool) -> list[dict]:
    """Синхронный парсинг с логами в реальном времени."""
    logger = StreamlitLogger()

    # Создаем новую сессию
    if st.session_state.get('log_manager'):
        session_id = st.session_state.log_manager.create_session()
        st.session_state.current_session_id = session_id
    else:
        # ИСПРАВЛЕНИЕ: `uuid` теперь импортирован, ошибки не будет
        session_id = str(uuid.uuid4())

    st.session_state.log_session_counter += 1
    logger.add_separator(st.session_state.log_session_counter)

    # Устанавливаем флаг активного парсинга
    st.session_state.parsing_active = True
    st.session_state.parsing_in_progress = True

    progress_bar = st.progress(0)
    status_text = st.empty()
    log_container = st.expander("📋 **Логи парсинга**", expanded=True)
    log_placeholder = log_container.empty()

    results = []
    total_subs = len(subreddits)
    settings = st.session_state.settings
    logger.log(f"🚀 Начало парсинга: {total_subs} subreddits", "INFO")
    logger.log(f"Сессия: {session_id[:8]}...", "DEBUG")
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

        # Сохраняем результат
        st.session_state.parsing_results = results

        return results

    # ИСПРАВЛЕНО: Заменен голый except на конкретный тип для лучшей отладки
    except Exception as e:
        logger.log(f"КРИТИЧЕСКАЯ ОШИБКА: {str(e)}", "ERROR")
        status_text.error(f"❌ Ошибка: {str(e)}")
        log_placeholder.markdown("\n".join(st.session_state.parsing_logs))
        return []
    finally:
        # Сбрасываем флаги
        st.session_state.parsing_active = False
        st.session_state.parsing_in_progress = False

        # Закрываем сессию
        if st.session_state.get('log_manager') and session_id:
            try:
                st.session_state.log_manager.close_session(session_id)
            except Exception as e:
                logger.log(f"Ошибка закрытия сессии: {e}", "WARNING")

# ИСПРАВЛЕНО: Функция не используется в UI, закомментирована для чистоты кода.
# Если в будущем потребуется её интегрировать, можно будет создать кнопку и вызвать её.
# def process_posts_with_live_logs(unprocessed_posts: list) -> dict:
#     """Параллельная обработка постов через LLM с живыми логами."""
#     # ... (код функции) ...
#     pass

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

# ============================================================================
# ФУНКЦИИ КОНВЕРТАЦИИ ОБЪЕКТОВ В СЛОВАРЬ
# ============================================================================
# Эти функции решают проблему DetachedInstanceError, преобразуя ORM-объекты
# в обычные словари Python, которые можно безопасно использовать вне сессии.

def _reddit_post_to_dict(post: RedditPost) -> dict:
    """Конвертирует RedditPost в словарь."""
    return {
        'id': post.id,
        'post_id': post.post_id,
        'title': post.title,
        'selftext': post.selftext,
        'url': post.url,
        'author': post.author,
        'subreddit': post.subreddit,
        'score': post.score,
        'num_comments': post.num_comments,
        'created_utc': post.created_utc.isoformat() if post.created_utc else None,
        'scraped_at': post.scraped_at.isoformat() if post.scraped_at else None,
        'qdrant_id': str(post.qdrant_id) if post.qdrant_id else None,
    }

def _processed_reddit_post_to_dict(post: ProcessedRedditPost, raw_post_data: dict = None) -> dict:
    """Конвертирует ProcessedRedditPost в словарь."""
    return {
        'id': post.id,
        'post_id': post.post_id,
        'original_title': post.original_title,
        'original_text': post.original_text,
        'subreddit': post.subreddit,
        'author': post.author,
        'url': post.url,
        'score': post.score,
        'is_news': post.is_news,
        'original_summary': post.original_summary,
        'rewritten_post': post.rewritten_post,
        'title': post.title,
        'teaser': post.teaser,
        'image_prompt': post.image_prompt,
        'processed_at': post.processed_at.isoformat() if post.processed_at else None,
        'processing_time': post.processing_time,
        'model_used': post.model_used,
        'raw_post': raw_post_data # Включаем данные оригинального поста
    }

def _habr_article_to_dict(article: HabrArticle) -> dict:
    """Конвертирует HabrArticle в словарь."""
    return {
        'id': article.id,
        'article_id': article.article_id,
        'title': article.title,
        'content': article.content,
        'url': article.url,
        'author': article.author,
        'description': article.description,
        'categories': article.categories,
        'pub_date': article.pub_date.isoformat() if article.pub_date else None,
        'scraped_at': article.scraped_at.isoformat() if article.scraped_at else None,
        'reading_time': article.reading_time,
        'views': article.views,
        'rating': article.rating,
        'original_title': article.original_title,
        'original_content': article.original_content,
        'rewritten_post': article.rewritten_post,
        'teaser': article.teaser,
        'image_prompt': article.image_prompt,
        'is_news': article.is_news,
        'editorial_processed': article.editorial_processed,
        'telegram_title': article.telegram_title,
        'telegram_content': article.telegram_content,
        'telegram_hashtags': article.telegram_hashtags,
        'telegram_formatted': article.telegram_formatted,
        'telegram_character_count': article.telegram_character_count,
        'telegram_processed': article.telegram_processed,
        'language': article.language,
        'word_count': article.word_count,
        'reading_time_calculated': article.reading_time_calculated,
        'sentiment': article.sentiment,
        'keywords': article.keywords,
        'summary': article.summary,
        'difficulty_level': article.difficulty_level,
        'relevance_score': article.relevance_score,
        'processing_version': article.processing_version,
        'last_updated': article.last_updated.isoformat() if article.last_updated else None,
        'qdrant_id': str(article.qdrant_id) if article.qdrant_id else None,
        'images': article.images,
    }

def _telegram_post_to_dict(post: TelegramPost) -> dict:
    """Конвертирует TelegramPost в словарь."""
    return {
        'id': post.id,
        'article_id': post.article_id,
        'content': post.content,
        'title': post.title,
        'hashtags': post.hashtags,
        'formatted_content': post.formatted_content,
        'character_count': post.character_count,
        'created_at': post.created_at.isoformat() if post.created_at else None,
        'published_at': post.published_at.isoformat() if post.published_at else None,
        'telegram_message_id': post.telegram_message_id,
        'is_published': post.is_published,
    }

# ============================================================================
# ФУНКЦИИ-ХЕЛПЕРЫ ДЛЯ РАБОТЫ С ДАТАМИ
# ============================================================================

def _parse_iso_to_utc(dt_str: str | None) -> datetime | None:
    """
    Безопасно парсит ISO-строку в UTC-aware datetime-объект.
    Если строка не содержит timezone, предполагается московское время (UTC+3).
    """
    if not dt_str:
        return None
    dt = datetime.fromisoformat(dt_str)
    if dt.tzinfo is None:
        # Если datetime наивный, предполагаем московское время
        moscow_tz = timezone(timedelta(hours=3))
        dt = dt.replace(tzinfo=moscow_tz)
    # Конвертируем в UTC для консистентности
    return dt.astimezone(timezone.utc)


# ============================================================================
# ФУНКЦИИ РЕНДЕРИНГА (ИСПРАВЛЕНЫ ДЛЯ РАБОТЫ СО СЛОВАРЯМИ)
# ============================================================================

def render_raw_post_viewer(post_data: dict, lang='ru') -> None:
    """Рендеринг сырого Reddit поста с векторной информацией."""
    has_vector = post_data.get('qdrant_id') is not None
    vector_badge = t('vectorized') if has_vector else t('no_vector')

    now = datetime.now(timezone.utc)
    created_utc_str = post_data.get('created_utc')
    scraped_at_str = post_data.get('scraped_at')

    created_time = datetime.fromisoformat(created_utc_str) if created_utc_str else now
    scraped_time = datetime.fromisoformat(scraped_at_str) if scraped_at_str else now

    time_since_created = now - created_time
    time_since_scraped = now - scraped_time

    with st.expander(f"r/{post_data.get('subreddit')} • {post_data.get('title', '')[:80]}"):
        col_badge1, col_badge2 = st.columns([1, 1], gap="small")
        with col_badge1:
            st.caption(vector_badge)
        with col_badge2:
            if has_vector:
                st.caption(f"`{post_data.get('qdrant_id', '')[:8]}...`")

        st.markdown("---")

        col_time1, col_time2 = st.columns(2, gap="small")
        with col_time1:
            st.markdown(f"**{t('published_reddit')}**")
            st.info(f"{created_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            st.caption(format_timedelta(time_since_created, lang))
        with col_time2:
            st.markdown(f"**{t('received_db')}**")
            st.success(f"{scraped_time.strftime('%Y-%m-%d %H:%M:%S UTC')}")
            st.caption(format_timedelta(time_since_scraped, lang))

        st.markdown("---")

        col_a, col_b = st.columns([2, 1], gap="small")

        with col_a:
            st.markdown(f"**{t('original_title')}**")
            st.write(post_data.get('title', ''))

            st.markdown(f"**{t('original_text')}**")
            selftext = post_data.get('selftext', '')
            if selftext:
                st.text_area(
                    t('post_text'),
                    selftext,
                    height=200,
                    key=f"raw_{post_data.get('id')}",
                    label_visibility="collapsed"
                )
            else:
                st.caption(f"_{t('text_missing')}_")

        with col_b:
            st.metric(t('score'), post_data.get('score', 0))
            st.metric(t('comments'), post_data.get('num_comments', 0))
            st.caption(f"**{t('author')}** u/{post_data.get('author', '')}")

            if has_vector:
                st.success(t('in_qdrant'))
                with st.expander(t('qdrant_uuid')):
                    st.code(post_data.get('qdrant_id', ''))
            else:
                st.warning(t('no_vector'))

            if post_data.get('url'):
                st.link_button(t('open_original'), post_data.get('url'))


def render_processed_post_viewer(post_data: dict, lang='ru') -> None:
    """Рендеринг обработанного поста с вкладками."""
    status_icon = "📰" if post_data.get('is_news') else "❌"
    raw_post_data = post_data.get('raw_post', {})

    # Используем teaser как основной заголовок, если есть
    if post_data.get('is_news') and post_data.get('teaser'):
        title_display = post_data.get('teaser', '')[:80]
    elif post_data.get('title'):
        title_display = post_data.get('title', '')[:80]
    else:
        title_display = post_data.get('original_title', '')[:80]

    has_vector = raw_post_data.get('qdrant_id') is not None

    now = datetime.now(timezone.utc)

    with st.expander(f"{status_icon} r/{post_data.get('subreddit')} • {title_display}"):
        # Badges - компактнее
        col_badge1, col_badge2, col_badge3, col_badge4 = st.columns([1, 1, 1, 1], gap="small")
        with col_badge1:
            if post_data.get('is_news'):
                st.success("✅ News")
            else:
                st.error("❌ Not News")
        with col_badge2:
            if has_vector:
                st.info("🤖 Vector")
            else:
                st.warning("⚠️ No Vec")
        with col_badge3:
            st.caption(f"⚡ {post_data.get('processing_time', 0)}ms")
        with col_badge4:
            st.caption(f"🤖 {post_data.get('model_used', 'gpt-oss')}")

        st.markdown("---")

        # Timeline - компактнее
        if raw_post_data:
            col_timeline1, col_timeline2, col_timeline3 = st.columns(3, gap="small")

            # ИСПОЛЬЗУЕМ ХЕЛПЕР ДЛЯ БЕЗОПАСНОГО ПАРСИНГА ДАТ
            created_time = _parse_iso_to_utc(raw_post_data.get('created_utc')) or now
            scraped_time = _parse_iso_to_utc(raw_post_data.get('scraped_at')) or now
            processed_time = _parse_iso_to_utc(post_data.get('processed_at')) or now

            with col_timeline1:
                st.markdown("**📅 Опубликовано**")
                st.info(f"{created_time.strftime('%Y-%m-%d %H:%M')}")
                st.caption(format_timedelta(now - created_time, lang))
            with col_timeline2:
                st.markdown("**💾 Получено**")
                st.success(f"{scraped_time.strftime('%Y-%m-%d %H:%M')}")
                st.caption(format_timedelta(now - scraped_time, lang))
            with col_timeline3:
                st.markdown("**🤖 Обработано**")
                st.warning(f"{processed_time.strftime('%Y-%m-%d %H:%M')}")
                st.caption(format_timedelta(now - processed_time, lang))

        st.markdown("---")

        if post_data.get('is_news'):
            tab_original, tab_llm, tab_meta = st.tabs(["📄 Оригинал", "🤖 LLM Output", "📊 Метаданные"])

            with tab_original:
                st.markdown("### 📌 Оригинальный заголовок")
                st.info(post_data.get('original_title', ''))

                st.markdown("### 📝 Оригинальный текст")
                original_text = post_data.get('original_text', '')
                if original_text:
                    full_original = f"{post_data.get('original_title', '')}\n\n{original_text}"
                    st.text_area(
                        "Полный оригинальный текст",
                        full_original,
                        height=400,
                        key=f"orig_full_{post_data.get('id')}",
                        label_visibility="collapsed"
                    )
                    st.caption(f"📏 Длина: {len(full_original)} символов | Слов: {count_words(full_original)}")
                else:
                    st.caption("_Текст отсутствует_")

            with tab_llm:
                # Teaser как основной заголовок
                st.markdown("### ✨ Заголовок (Teaser)")
                if post_data.get('teaser'):
                    st.success(f"**{post_data.get('teaser')}**")
                else:
                    st.caption("_Не создан_")

                st.markdown("### 📰 Редакторский заголовок")
                if post_data.get('title'):
                    st.info(post_data.get('title'))
                else:
                    st.caption("_Не создан_")

                st.markdown("### ✏️ Переписанный текст (LLM Output)")
                rewritten_post = post_data.get('rewritten_post', '')
                if rewritten_post:
                    st.text_area(
                        "Полный переписанный текст от LLM",
                        rewritten_post,
                        height=400,
                        key=f"llm_full_{post_data.get('id')}",
                        label_visibility="collapsed"
                    )

                    # Добавлена статистика по словам
                    original_text = f"{post_data.get('original_title', '')}\n\n{post_data.get('original_text', '')}"
                    original_len = len(original_text)
                    original_words = count_words(original_text)
                    llm_len = len(rewritten_post)
                    llm_words = count_words(rewritten_post)

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
                if post_data.get('image_prompt'):
                    st.code(post_data.get('image_prompt'), language="text")
                else:
                    st.caption("_Не создан_")

                st.markdown("### 📋 Краткое содержание (Summary)")
                if post_data.get('original_summary'):
                    with st.expander("Показать summary"):
                        st.write(post_data.get('original_summary'))
                else:
                    st.caption("_Не создано_")

            with tab_meta:
                st.markdown("### 📊 Метаданные обработки")

                # Уменьшен gap
                col_m1, col_m2 = st.columns(2, gap="small")

                with col_m1:
                    st.markdown("**🤖 Модель**")
                    st.info(post_data.get('model_used', 'gpt-oss'))

                    st.markdown("**⚡ Время обработки**")
                    processing_time = post_data.get('processing_time', 0)
                    st.info(f"{processing_time}ms ({processing_time / 1000:.2f}s)")

                    processed_at_str = post_data.get('processed_at')
                    st.markdown("**📅 Дата обработки**")
                    st.info(datetime.fromisoformat(processed_at_str).strftime('%Y-%m-%d %H:%M:%S UTC') if processed_at_str else 'N/A')

                with col_m2:
                    st.markdown("**📰 Классификация**")
                    if post_data.get('is_news'):
                        st.success("✅ Новость")
                    else:
                        st.error("❌ Не новость")

                    st.markdown("**🎯 Векторизация**")
                    if has_vector:
                        st.success("✅ В Qdrant")
                        if raw_post_data.get('qdrant_id'):
                            st.code(raw_post_data.get('qdrant_id'), language="text")
                    else:
                        st.warning("⚠️ Не векторизован")

                    st.markdown("**⬆️ Score**")
                    st.info(f"{post_data.get('score', 0)} upvotes")

            st.markdown("---")
            if post_data.get('url'):
                st.link_button("🔗 Открыть оригинал на Reddit", post_data.get('url'))
        else:
            st.warning("**❌ Не является новостью**")
            st.caption(f"**Оригинальный заголовок:** {post_data.get('original_title', '')}")
            st.caption(f"**Subreddit:** r/{post_data.get('subreddit', '')}")
            st.caption(f"**Автор:** u/{post_data.get('author', '')}")

            if post_data.get('original_text'):
                with st.expander("📄 Показать оригинальный текст"):
                    st.text_area(
                        "Оригинальный текст",
                        post_data.get('original_text', ''),
                        height=200,
                        key=f"not_news_{post_data.get('id')}",
                        label_visibility="collapsed"
                    )


def render_habr_article_viewer(article_data: dict, lang='ru') -> None:
    """Рендеринг статьи с Habr."""
    has_vector = article_data.get('qdrant_id') is not None
    is_processed = article_data.get('editorial_processed')
    is_news = article_data.get('is_news')

    # Иконка статуса
    if is_news:
        status_icon = "📰"
    elif is_processed:
        status_icon = "🤖"
    else:
        status_icon = "📄"

    # Заголовок для отображения
    if is_news and article_data.get('teaser'):
        title_display = article_data.get('teaser', '')[:80]
    elif article_data.get('title'):
        title_display = article_data.get('title', '')[:80]
    else:
        title_display = article_data.get('title', '')[:80]

    now = datetime.now(timezone.utc)

    with st.expander(f"{status_icon} Habr • {title_display}"):
        # Badges
        col_badge1, col_badge2, col_badge3 = st.columns([1, 1, 1], gap="small")
        with col_badge1:
            if is_news:
                st.success("✅ News")
            elif is_processed:
                st.info("🤖 Processed")
            else:
                st.warning("📄 Raw")
        with col_badge2:
            if has_vector:
                st.info("🤖 Vector")
            else:
                st.warning("⚠️ No Vec")
        with col_badge3:
            if article_data.get('rating') is not None:
                st.caption(f"⭐ {article_data.get('rating')}")
            else:
                st.caption("⭐ N/A")

        st.markdown("---")

        # Timeline
        col_time1, col_time2 = st.columns(2, gap="small")
        with col_time1:
            st.markdown("**📅 Опубликовано на Habr**")

            # ИСПОЛЬЗУЕМ ХЕЛПЕР ДЛЯ БЕЗОПАСНОГО ПАРСИНГА ДАТ
            pub_time = _parse_iso_to_utc(article_data.get('pub_date'))
            if pub_time:
                st.info(f"{pub_time.strftime('%Y-%m-%d %H:%M')}")
                st.caption(format_timedelta(now - pub_time, lang))
            else:
                st.caption("_Дата неизвестна_")

        with col_time2:
            st.markdown("**💾 Получено в БД**")

            # ИСПОЛЬЗУЕМ ХЕЛПЕР ДЛЯ БЕЗОПАСНОГО ПАРСИНГА ДАТ
            scraped_time = _parse_iso_to_utc(article_data.get('scraped_at')) or now
            st.success(f"{scraped_time.strftime('%Y-%m-%d %H:%M')}")
            st.caption(format_timedelta(now - scraped_time, lang))

        st.markdown("---")

        # Контент
        if is_news:
            tab_original, tab_llm, tab_meta = st.tabs(["📄 Оригинал", "🤖 LLM Output", "📊 Метаданные"])

            with tab_original:
                st.markdown("### 📌 Оригинальный заголовок")
                st.info(article_data.get('title', ''))

                st.markdown("### 📝 Оригинальный текст")
                content = article_data.get('content', '')
                if content:
                    st.text_area(
                        "Полный оригинальный текст",
                        content,
                        height=400,
                        key=f"habr_orig_{article_data.get('id')}",
                        label_visibility="collapsed"
                    )
                    st.caption(f"📏 Длина: {len(content)} символов | Слов: {count_words(content)}")
                else:
                    st.caption("_Текст отсутствует_")

            with tab_llm:
                st.markdown("### ✨ Заголовок (Teaser)")
                if article_data.get('teaser'):
                    st.success(f"**{article_data.get('teaser')}**")
                else:
                    st.caption("_Не создан_")

                st.markdown("### 📰 Редакторский заголовок")
                if article_data.get('title'):
                    st.info(article_data.get('title'))
                else:
                    st.caption("_Не создан_")

                st.markdown("### ✏️ Переписанный текст (LLM Output)")
                rewritten_post = article_data.get('rewritten_post', '')
                if rewritten_post:
                    st.text_area(
                        "Полный переписанный текст от LLM",
                        rewritten_post,
                        height=400,
                        key=f"habr_llm_{article_data.get('id')}",
                        label_visibility="collapsed"
                    )

                    # Статистика
                    original_len = len(article_data.get('content', ''))
                    original_words = count_words(article_data.get('content', ''))
                    llm_len = len(rewritten_post)
                    llm_words = count_words(rewritten_post)

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

                st.markdown("### 🎨 Промпт для генерации изображения")
                if article_data.get('image_prompt'):
                    st.code(article_data.get('image_prompt'), language="text")
                else:
                    st.caption("_Не создан_")

            with tab_meta:
                st.markdown("### 📊 Метаданные статьи")

                col_m1, col_m2 = st.columns(2, gap="small")

                with col_m1:
                    st.markdown("**✍️ Автор**")
                    st.info(article_data.get('author', 'Unknown'))

                    st.markdown("**📚 Категории**")
                    if article_data.get('categories'):
                        st.info(article_data.get('categories'))
                    else:
                        st.caption("_Нет категорий_")

                    st.markdown("**⏱️ Время чтения**")
                    if article_data.get('reading_time'):
                        st.info(f"{article_data.get('reading_time')} мин")
                    else:
                        st.caption("_Неизвестно_")

                with col_m2:
                    st.markdown("**👁️ Просмотры**")
                    if article_data.get('views') is not None:
                        st.info(f"{article_data.get('views'):,}")
                    else:
                        st.caption("_Неизвестно_")

                    st.markdown("**⭐ Рейтинг**")
                    if article_data.get('rating') is not None:
                        st.info(f"{article_data.get('rating')}")
                    else:
                        st.caption("_Неизвестно_")

                    st.markdown("**🎯 Векторизация**")
                    if has_vector:
                        st.success("✅ В Qdrant")
                        st.code(article_data.get('qdrant_id'), language="text")
                    else:
                        st.warning("⚠️ Не векторизован")

            st.markdown("---")
            if article_data.get('url'):
                st.link_button("🔗 Открыть оригинал на Habr", article_data.get('url'))
        else:
            # Для необработанных/не-новостных статей
            col_a, col_b = st.columns([2, 1], gap="small")

            with col_a:
                st.markdown("### 📌 Заголовок")
                st.info(article_data.get('title', ''))

                st.markdown("### 📝 Контент")
                content = article_data.get('content', '')
                if content:
                    st.text_area(
                        "Полный текст",
                        content,
                        height=300,
                        key=f"habr_raw_{article_data.get('id')}",
                        label_visibility="collapsed"
                    )
                    st.caption(f"📏 Длина: {len(content)} символов")
                else:
                    st.caption("_Текст отсутствует_")

            with col_b:
                st.markdown("**✍️ Автор**")
                st.caption(article_data.get('author', 'Unknown'))

                if article_data.get('rating') is not None:
                    st.metric("⭐ Рейтинг", article_data.get('rating'))

                if article_data.get('views') is not None:
                    st.metric("👁️ Просмотры", f"{article_data.get('views'):,}")

                if article_data.get('reading_time'):
                    st.metric("⏱️ Чтение", f"{article_data.get('reading_time')} мин")

                if has_vector:
                    st.success("✅ Векторизовано")
                else:
                    st.warning("⚠️ Не векторизовано")

                if article_data.get('url'):
                    st.link_button("🔗 Открыть", article_data.get('url'))

def render_telegram_post_viewer(post_data: dict, lang='ru') -> None:
    """
    Рендеринг Telegram поста.
    Теперь принимает словарь post_data, что безопасно и предотвращает DetachedInstanceError.
    """
    if not post_data:
        st.warning("Данные поста отсутствуют.")
        return

    now = datetime.now(timezone.utc)

    # ИСПОЛЬЗУЕМ ХЕЛПЕР ДЛЯ БЕЗОПАСНОГО ПАРСИНГА ДАТ
    created_time = _parse_iso_to_utc(post_data.get('created_at')) or now
    published_time = _parse_iso_to_utc(post_data.get('published_at'))

    status_icon = "✅" if post_data.get('is_published') else "📝"
    title_display = post_data.get('title', 'Без заголовка')[:80]

    with st.expander(f"{status_icon} Telegram • {title_display}"):
        # Badges
        col_badge1, col_badge2, col_badge3 = st.columns([1, 1, 1], gap="small")
        with col_badge1:
            st.success("Опубликовано" if post_data.get('is_published') else "Черновик")
        with col_badge2:
            st.caption(f"📏 {post_data.get('character_count', 0)} символов")
        with col_badge3:
            if post_data.get('telegram_message_id'):
                st.caption(f"ID: {post_data.get('telegram_message_id')}")

        st.markdown("---")

        # Timeline
        col_time1, col_time2 = st.columns(2, gap="small")
        with col_time1:
            st.markdown("**📅 Создан**")
            st.info(f"{created_time.strftime('%Y-%m-%d %H:%M')}")
            st.caption(format_timedelta(now - created_time, lang))
        with col_time2:
            st.markdown("**📤 Опубликован**")
            if published_time:
                st.success(f"{published_time.strftime('%Y-%m-%d %H:%M')}")
                st.caption(format_timedelta(now - published_time, lang))
            else:
                st.caption("Не опубликован")

        st.markdown("---")

        # Content
        col_a, col_b = st.columns([2, 1], gap="small")

        with col_a:
            st.markdown("### 📌 Заголовок")
            st.info(post_data.get('title', 'Нет заголовка'))

            st.markdown("### 📝 Контент")
            st.text_area(
                "Содержимое поста",
                post_data.get('content', 'Нет содержимого'),
                height=200,
                key=f"telegram_content_{post_data.get('id')}", # Используем ID для уникальности ключа
                label_visibility="collapsed"
            )

            if post_data.get('formatted_content'):
                with st.expander("Форматированный контент"):
                    st.markdown(post_data.get('formatted_content'))

            if post_data.get('hashtags'):
                st.markdown("### 🏷️ Хештеги")
                st.info(post_data.get('hashtags'))

        with col_b:
            st.markdown("**📊 Статистика**")
            st.metric("Символы", post_data.get('character_count', 0))

            if post_data.get('article_id'):
                st.caption(f"ID Статьи: {post_data.get('article_id')}")
                if st.button("Открыть статью", key=f"open_article_{post_data.get('id')}"):
                    # Здесь можно добавить переход к статье
                    pass

            if post_data.get('is_published') and post_data.get('telegram_message_id'):
                st.markdown("**📱 В Telegram**")
                st.success(f"Сообщение ID: {post_data.get('telegram_message_id')}")
                # Здесь можно добавить кнопку для перехода к сообщению
                if st.button("Открыть в Telegram", key=f"open_telegram_{post_data.get('id')}"):
                    # Здесь можно добавить переход к сообщению в Telegram
                    pass

        st.markdown("---")

def get_telegram_posts(limit=50, include_published=True, include_drafts=True):
    """Получение Telegram постов с фильтрацией."""
    from src.models.database import get_db_session

    with get_db_session() as session:
        query = session.query(TelegramPost)

        if not include_published:
            query = query.filter_by(is_published=False)
        if not include_drafts:
            query = query.filter_by(is_published=True)

        posts = query.order_by(TelegramPost.created_at.desc()).limit(limit).all()
        # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Конвертируем объекты в словари перед возвратом
        return [_telegram_post_to_dict(p) for p in posts]

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

# ============================================================================
# ОСНОВНОЙ ИНТЕРФЕЙС
# ============================================================================

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

# Индикатор активного процесса
if st.session_state.get('parsing_active', False):
    session_id = st.session_state.get('current_session_id', 'Unknown')
    st.warning(f"🔄 Активен процесс парсинга (сессия: {session_id[:8] if session_id != 'Unknown' else session_id}...)")

# === API STATUS ===
col1, col2, col3, col4 = st.columns(4)
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
with col4:
    # Habr не требует API ключей, всегда доступен
    st.success("🟢 Habr")

st.markdown("---")

try:
    stats = get_stats_extended()
# ИСПРАВЛЕНО: Заменен голый except на конкретный тип для лучшей отладки
except Exception as e:
    st.error(f"Не удалось загрузить статистику: {e}")
    stats = {
        'reddit_posts': 0,
        'telegram_messages': 0,
        'medium_articles': 0,
        'habr_articles': 0,
        'telegram_posts': 0,
        'latest_reddit': None,
        'latest_telegram': None,
        'latest_medium': None,
        'latest_habr': None
    }

# === TABS ===
tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs([
    t('reddit_tab'),
    t('telegram_tab'),
    t('medium_tab'),
    "🇷🇺 Habr",
    "📱 Telegram Посты",
    f"📊 {t('data_viewer_tab')}",
    f"⚙️ {t('settings_tab')}",
    "🔌 API"
])

# === TAB 1: REDDIT PARSER ===
with tab1:
    st.markdown('<div class="reddit-section">', unsafe_allow_html=True)
    st.header(f"{t('reddit_tab')} Parser")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader(t('settings'))

        all_subreddits = sources_config.get_reddit_subreddits()
        categories = sources_config.get_reddit_categories()

        category_filter = st.selectbox(
            t('filter_category'),
            [t('all_categories')] + categories,
            index=0,
            key="reddit_category"
        )

        if category_filter == t('all_categories'):
            filtered_subs = all_subreddits
        else:
            filtered_subs = sources_config.get_reddit_subreddits(category=category_filter)

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
        if st.session_state.parsing_logs:
            with st.expander("📜 Все логи сессии", expanded=False):
                st.markdown("\n".join(list(st.session_state.parsing_logs)))

    with col2:
        st.subheader(t('statistics'))

        # FIXED: Safe statistics retrieval with defaults
        reddit_count = stats.get('reddit_posts', 0)
        st.metric(t('posts'), f"{reddit_count:,}")

        # Статистика обработки
        try:
            from src.models.database import get_db_session, ProcessedRedditPost, HabrArticle, get_session

            with get_db_session() as session:
                # Reddit статистика
                reddit_processed_count = session.query(ProcessedRedditPost).count()
                reddit_news_count = session.query(ProcessedRedditPost).filter_by(is_news=True).count()

                # Habr статистика
                habr_processed_count = session.query(HabrArticle).filter_by(editorial_processed=True).count()
                habr_news_count = session.query(HabrArticle).filter_by(is_news=True).count()

                # Общая статистика
                processed_count = reddit_processed_count + habr_processed_count
                news_count = reddit_news_count + habr_news_count

                # Процент обработки
                processing_rate = (processed_count / reddit_count * 100) if reddit_count > 0 else 0

                st.metric("Обработано", f"{processed_count:,}")
                st.metric("Новостей", f"{news_count:,}")

                if reddit_count > 0:
                    st.progress(
                        processing_rate / 100,
                        text=f"Обработка: {processing_rate:.1f}%"
                    )
        # `logger` не определен, заменен на `st.error`
        except Exception as e:
            st.caption(f"⚠️ Статистика недоступна")
            st.error(f"Ошибка получения статистики обработки: {e}")

    st.markdown('</div>', unsafe_allow_html=True)

# === TAB 2: TELEGRAM PARSER ===
with tab2:
    st.markdown('<div class="telegram-section">', unsafe_allow_html=True)
    st.header(f"{t('telegram_tab')} Parser")

    # Уведомление о разработке
    st.warning("⚠️ **В разработке** - Требует настройки Telegram API")

    col_info, col_settings = st.columns([2, 1])

    with col_info:
        st.markdown("""
        ### Что нужно для работы:

        1. **Получить Telegram API**
           - Зайти на https://my.telegram.org/apps
           - Создать приложение и получить `api_id` и `api_hash`

        2. **Настроить переменные окружения**:
           ```bash
           TELEGRAM_API_ID=ваш_api_id
           TELEGRAM_API_HASH=ваш_api_hash
           TELEGRAM_PHONE=+7xxxxxxxxxx
           ```

        3. **Права доступа**
           - Бот должен быть администратором каналов
           - Убедитесь что бот имеет права на чтение сообщений

        ### Текущий статус:
        """)

        # Проверяем настройки
        config_status = []
        if os.getenv("TELEGRAM_API_ID"):
            config_status.append("✅ TELEGRAM_API_ID настроен")
        else:
            config_status.append("❌ TELEGRAM_API_ID не настроен")

        if os.getenv("TELEGRAM_API_HASH"):
            config_status.append("✅ TELEGRAM_API_HASH настроен")
        else:
            config_status.append("❌ TELEGRAM_API_HASH не настроен")

        if os.getenv("TELEGRAM_PHONE"):
            config_status.append("✅ TELEGRAM_PHONE настроен")
        else:
            config_status.append("❌ TELEGRAM_PHONE не настроен")

        for status in config_status:
            st.markdown(f"- {status}")

        if all("✅" in status for status in config_status):
            st.success("🎉 Все настройки в порядке! Можете использовать парсер.")
        else:
            st.error("⚠️ Настройте отсутствующие параметры для использования парсера.")

    with col_settings:
        st.subheader("Тестовые настройки")

        # Демо-каналы (можно изменить)
        demo_channels = [
            "@telegram",  # Официальный канал Telegram
            "@durov",  # Канал Павла Дурова
            "@python_news",  # Новости Python (если доступен)
        ]

        selected_channels = st.multiselect(
            "Выберите каналы для теста:",
            demo_channels,
            default=[],
            key="telegram_demo_channels",
            help="Выберите каналы из списка или введите свои"
        )

        # Настройки парсинга
        col_a, col_b, col_c = st.columns(3)
        with col_a:
            tg_max_msgs = st.slider(
                "Сообщений с канала:",
                10, 500,
                100,
                key="tg_max_msgs"
            )
        with col_b:
            tg_delay = st.slider(
                "Задержка (сек):",
                3, 30,
                5,
                key="tg_delay"
            )
        with col_c:
            tg_enable_llm = st.checkbox(
                "LLM Preprocessing",
                value=False,
                key="tg_llm",
                disabled=True
            )
            st.caption("Пока не доступно")

        st.markdown("---")

        # Кнопка запуска
        button_disabled = (
                not selected_channels or
                not all([os.getenv("TELEGRAM_API_ID"), os.getenv("TELEGRAM_API_HASH"), os.getenv("TELEGRAM_PHONE")])
        )

        if button_disabled:
            st.warning("⚠️ Настройте Telegram API для использования парсера")

        if st.button(
                "🚀 Запустить парсинг Telegram",
                type="primary",
                use_container_width=True,
                key="telegram_parse_btn",
                disabled=button_disabled
        ):
            if not selected_channels:
                st.error("Выберите хотя бы один канал")
            else:
                st.markdown("---")

                # Вызов scraper с live logs
                results = scrape_telegram_channels(
                    channels=selected_channels,
                    limit=tg_max_msgs,
                    delay=tg_delay,
                    enable_llm=tg_enable_llm,
                    log_callback=lambda msg, lvl: StreamlitLogger.log(msg, lvl)
                )

                # Отображение результатов
                st.markdown("### Результаты парсинга:")
                for result in results:
                    if result.get('success'):
                        st.success(f"✅ {result.get('channel', 'Unknown')}: {result.get('messages_saved', 0)} сообщений")
                    else:
                        st.error(f"❌ {result.get('channel', 'Unknown')}: {result.get('error', 'Unknown error')}")

                st.session_state.parsing_results = results
                st.rerun()

    # Статистика
    st.markdown("---")
    st.subheader("Статистика")
    # st.metric("Сообщений", f"{stats['telegram_messages']:,}")

    # if stats['latest_telegram']:
    #     st.caption(f"Последнее: {stats['latest_telegram']}")

    # Информация о разработке
    with st.expander("ℹ️ Информация о разработке"):
        st.markdown("""
        ### Текущий статус:
        - **Версия**: 0.1 (в разработке)
        - **Стабильность**: Альфа
        - **Поддержка**: Базовая

        ### Планируемые улучшения:
        - [ ] LLM обработка сообщений
        - [ ] Фильтрация по типам контента
        - [ ] Поддержка медиа-вложений
        - [ ] Автоматическое определение языка
        - [ ] Интеграция с векторизацией

        ### Известные ограничения:
        - Требуются права администратора на каналах
        - Rate limiting от Telegram API
        - Нет поддержки приватных каналов

        ### Для разработчиков:
        ```python
        # Пример использования
        from src.scrapers.telegram_scraper import scrape_telegram_channels

        results = await scrape_telegram_channels(
            channels=['@channel1', '@channel2'],
            limit=100
        )
        ```
        """)

    st.markdown('</div>', unsafe_allow_html=True)

# === TAB 3: MEDIUM ===
with tab3:
    st.markdown('<div class="medium-section">', unsafe_allow_html=True)
    st.header(f"{t('medium_tab')} Parser")
    st.info(t('in_development'))
    st.markdown('</div>', unsafe_allow_html=True)

# === TAB 4: HABR PARSER ===
with tab4:
    st.markdown('<div class="habr-section">', unsafe_allow_html=True)
    st.header("🇷🇺 Habr Parser (Enhanced)")

    # Проверка доступности сервисов
    qdrant_available = False
    ollama_available = False

    try:
        import requests

        qdrant_url = os.getenv("QDRANT_URL", "http://qdrant:6333")
        resp = requests.get(f"{qdrant_url}/collections", timeout=2)
        qdrant_available = resp.status_code == 200
    except:
        pass

    try:
        ollama_url = os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        resp = requests.get(f"{ollama_url}/api/tags", timeout=2)
        ollama_available = resp.status_code == 200
    except:
        pass

    # Статус сервисов
    col_status1, col_status2 = st.columns(2)
    with col_status1:
        if qdrant_available:
            st.success("✅ Qdrant доступен (дедупликация включена)")
        else:
            st.warning("⚠️ Qdrant недоступен (дедупликация отключена)")

    with col_status2:
        if ollama_available:
            st.success("✅ Ollama доступен (LLM обработка доступна)")
        else:
            st.warning("⚠️ Ollama недоступен (LLM обработка недоступна)")

    st.markdown("---")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("⚙️ Настройки парсинга")

        # Получаем хабы и теги из конфига
        try:
            all_hubs = sources_config.get_habr_hubs()
            all_tags = sources_config.get_habr_tags()
            categories = sources_config.get_habr_categories()
        except Exception as e:
            st.error(f"❌ Ошибка загрузки конфигурации: {e}")
            all_hubs = []
            all_tags = []
            categories = []

        # Фильтр по категориям
        habr_category_filter = st.selectbox(
            "📁 Фильтр по категории:",
            ["Все"] + categories,
            index=0,
            key="habr_category",
            help="Фильтровать хабы и теги по категории"
        )

        # Фильтрация хабов и тегов
        if habr_category_filter == "Все":
            filtered_hubs = all_hubs
            filtered_tags = all_tags
        else:
            filtered_hubs = sources_config.get_habr_hubs(category=habr_category_filter)
            filtered_tags = sources_config.get_habr_tags(category=habr_category_filter)

        # Session state для выбора
        if 'habr_selected_hubs' not in st.session_state:
            st.session_state.habr_selected_hubs = []
        if 'habr_selected_tags' not in st.session_state:
            st.session_state.habr_selected_tags = []
        if 'habr_widget_key' not in st.session_state:
            st.session_state.habr_widget_key = 0

        # Выбор хабов
        with st.expander("🏷️ Выбор хабов", expanded=True):
            col_hub1, col_hub2 = st.columns([3, 1])
            with col_hub2:
                st.write("")
                st.write("")
                if st.button("Выбрать все", key="select_all_habr_hubs", use_container_width=True):
                    st.session_state.habr_selected_hubs = filtered_hubs.copy()
                    st.session_state.habr_widget_key += 1
                    st.rerun()

                if st.button("Очистить", key="clear_habr_hubs", use_container_width=True):
                    st.session_state.habr_selected_hubs = []
                    st.session_state.habr_widget_key += 1
                    st.rerun()

            with col_hub1:
                selected_hubs = st.multiselect(
                    f"Хабы ({len(filtered_hubs)} доступно):",
                    filtered_hubs,
                    default=[h for h in st.session_state.habr_selected_hubs if h in filtered_hubs],
                    key=f"habr_hubs_multiselect_{st.session_state.habr_widget_key}",
                    help="Выберите хабы для парсинга. Если не выбрано - используются все хабы"
                )
                st.session_state.habr_selected_hubs = selected_hubs

                if not selected_hubs:
                    st.info(f"💡 Будут использованы все хабы ({len(filtered_hubs)})")

        # Выбор тегов
        with st.expander("🔖 Дополнительные теги (опционально)", expanded=False):
            col_tag1, col_tag2 = st.columns([3, 1])
            with col_tag2:
                st.write("")
                st.write("")
                if st.button("Выбрать все", key="select_all_habr_tags", use_container_width=True):
                    st.session_state.habr_selected_tags = filtered_tags.copy()
                    st.session_state.habr_widget_key += 1
                    st.rerun()

                if st.button("Очистить", key="clear_habr_tags", use_container_width=True):
                    st.session_state.habr_selected_tags = []
                    st.session_state.habr_widget_key += 1
                    st.rerun()

            with col_tag1:
                selected_tags = st.multiselect(
                    f"Теги ({len(filtered_tags)} доступно):",
                    filtered_tags,
                    default=[t for t in st.session_state.habr_selected_tags if t in filtered_tags],
                    key=f"habr_tags_multiselect_{st.session_state.habr_widget_key}",
                    help="Дополнительные теги для фильтрации контента"
                )
                st.session_state.habr_selected_tags = selected_tags

        st.markdown("---")

        # Настройки парсинга
        st.subheader("🎛️ Параметры")

        col_a, col_b, col_c = st.columns(3)

        with col_a:
            habr_max_articles = st.number_input(
                "Max статей:",
                min_value=1,
                max_value=200,
                value=10,
                step=5,
                key="habr_max_articles",
                help="Максимальное количество статей для парсинга"
            )

        with col_b:
            habr_enable_llm = st.checkbox(
                "🤖 LLM Обработка",
                value=ollama_available,
                key="habr_llm",
                disabled=not ollama_available,
                help="Включить редакторскую обработку через LLM (требует Ollama)"
            )

        with col_c:
            habr_enable_dedup = st.checkbox(
                "🔍 Дедупликация",
                value=qdrant_available,
                key="habr_dedup",
                disabled=not qdrant_available,
                help="Включить семантическую дедупликацию через Qdrant"
            )

        st.markdown("---")

        # Статус последнего парсинга
        if 'habr_parsing_results' in st.session_state and st.session_state.habr_parsing_results:
            result = st.session_state.habr_parsing_results

            if result.get('success'):
                saved = result.get('saved', 0)
                skipped = result.get('skipped', 0)
                semantic_dups = result.get('semantic_duplicates', 0)
                editorial = result.get('editorial_processed', 0)
                errors = result.get('errors', 0)

                col_res1, col_res2, col_res3, col_res4 = st.columns(4)
                with col_res1:
                    st.metric("✅ Сохранено", saved)
                with col_res2:
                    st.metric("⏭️ Пропущено", skipped)
                with col_res3:
                    st.metric("🔄 Дубликатов", semantic_dups)
                with col_res4:
                    st.metric("📝 LLM", editorial)

                if errors > 0:
                    st.warning(f"⚠️ Ошибок: {errors}")
            else:
                st.error(f"❌ Ошибка: {result.get('error', 'Unknown')}")

        # Кнопки управления
        col_btn1, col_btn2, col_btn3, col_btn4 = st.columns([2, 1, 1, 1])

        with col_btn1:
            if st.button(
                    "🚀 Запустить парсинг",
                    type="primary",
                    use_container_width=True,
                    key="habr_parse_btn",
                    disabled=st.session_state.parsing_in_progress
            ):
                st.markdown("---")

                # Clear logs before starting
                StreamlitLogger.clear()

                # Запуск парсинга с live logs
                result = scrape_habr_with_live_logs(
                    hubs=selected_hubs if selected_hubs else [],
                    tags=selected_tags if selected_tags else [],
                    max_articles=habr_max_articles,
                    enable_llm=habr_enable_llm,
                    enable_dedup=habr_enable_dedup  # ← НОВЫЙ ПАРАМЕТР
                )

                st.session_state.habr_parsing_results = result
                st.rerun()

        with col_btn2:
            if st.button(
                    "📥 Export",
                    type="secondary",
                    use_container_width=True,
                    key="habr_export_btn",
                    disabled=not ('habr_parsing_results' in st.session_state)
            ):
                if 'habr_parsing_results' in st.session_state:
                    result = st.session_state.habr_parsing_results
                    json_str = json.dumps(result, indent=2, ensure_ascii=False)
                    st.download_button(
                        label="⬇️ Скачать JSON",
                        data=json_str,
                        file_name=f"habr_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json",
                        mime="application/json"
                    )

        with col_btn3:
            if st.button(
                    "🗑️ Очистить логи",
                    type="secondary",
                    use_container_width=True,
                    key="habr_clear_logs_btn",
                    disabled=st.session_state.parsing_in_progress
            ):
                StreamlitLogger.clear()
                if 'habr_parsing_results' in st.session_state:
                    del st.session_state.habr_parsing_results
                st.success("Логи очищены!")
                time.sleep(0.5)
                st.rerun()

        with col_btn4:
            if st.button(
                    "🔄 Обновить",
                    type="secondary",
                    use_container_width=True,
                    key="habr_refresh_btn"
            ):
                st.rerun()

        # Отображение логов
        if st.session_state.parsing_logs:
            with st.expander("📜 Логи парсинга", expanded=False):
                st.markdown("\n".join(list(st.session_state.parsing_logs)))

    with col2:
        st.subheader("📊 Статистика")

        try:
            # Базовая статистика
            total_articles = stats.get('habr_articles', 0)
            st.metric("📚 Всего статей", f"{total_articles:,}")

            if stats.get('latest_habr'):
                st.caption(f"🕐 Последняя: {stats['latest_habr']}")

            st.markdown("---")

            # Детальная статистика
            session = get_session()

            # Обработанные статьи
            processed = session.query(HabrArticle).filter(
                HabrArticle.editorial_processed == True
            ).count()

            # Новости
            news = session.query(HabrArticle).filter(
                HabrArticle.is_news == True
            ).count()

            # Векторизованные
            vectorized = session.query(HabrArticle).filter(
                HabrArticle.qdrant_id.isnot(None)
            ).count()

            st.metric("🤖 Обработано LLM", f"{processed:,}")
            st.metric("📰 Новостей", f"{news:,}")
            st.metric("🔍 В Qdrant", f"{vectorized:,}")

            # Прогресс обработки
            if total_articles > 0:
                processing_rate = (processed / total_articles) * 100
                st.progress(
                    processing_rate / 100,
                    text=f"Обработка: {processing_rate:.1f}%"
                )

                news_rate = (news / total_articles) * 100
                st.progress(
                    news_rate / 100,
                    text=f"Новости: {news_rate:.1f}%"
                )

            # Топ категорий
            st.markdown("---")
            st.caption("📁 Топ категорий")

            from sqlalchemy import func

            top_categories = session.query(
                HabrArticle.categories,
                func.count(HabrArticle.id)
            ).group_by(
                HabrArticle.categories
            ).order_by(
                func.count(HabrArticle.id).desc()
            ).limit(5).all()

            for cat, count in top_categories:
                if cat:
                    st.caption(f"• {cat.split(',')[0]}: {count}")

            session.close()

        except Exception as e:
            st.error(f"❌ Ошибка статистики: {e}")

    st.markdown('</div>', unsafe_allow_html=True)

# === TAB 5: TELEGRAM POSTS ===
with tab5:
    st.header("📱 Telegram Посты")

    # Фильтры
    col1, col2, col3 = st.columns(3)
    with col1:
        include_published = st.checkbox("Опубликовано", value=True)
    with col2:
        include_drafts = st.checkbox("Черновики", value=True)
    with col3:
        limit = st.number_input("Лимит", min_value=10, max_value=100, value=20)

    # Получение постов
    posts_data = get_telegram_posts(limit=limit, include_published=include_published, include_drafts=include_drafts)

    if not posts_data:
        st.info("Нет постов для отображения")
    else:
        # Отображение постов
        for post_data in posts_data:
            render_telegram_post_viewer(post_data, st.session_state.language)

        # Статистика
        st.subheader("📊 Статистика")
        col1, col2, col3 = st.columns(3)
        with col1:
            st.metric("Всего постов", len(posts_data))
        with col2:
            published_count = sum(1 for p in posts_data if p.get('is_published'))
            st.metric("Опубликовано", published_count)
        with col3:
            draft_count = sum(1 for p in posts_data if not p.get('is_published'))
            st.metric("Черновики", draft_count)

# === TAB 6: DATA VIEWER ===
with tab6:
    st.header("📊 Просмотр данных")

    # Выбор источника данных
    data_source = st.radio(
        "Источник данных:",
        ["Reddit (сырые)", "Reddit (обработанные)", "Telegram", "Medium", "Habr", "Telegram Посты"],
        horizontal=True,
        key="data_source_radio"
    )

    st.markdown("---")

    # Настройки отображения
    col_filter, col_sort, col_limit = st.columns([2, 2, 1])

    with col_limit:
        limit = st.slider(
            "Записей",
            10, 500,
            st.session_state.settings['viewer_default_limit'],
            key="unified_limit"
        )

    # Специфичные настройки для каждого источника
    if "Reddit" in data_source:
        with col_filter:
            if "обработанные" in data_source:
                news_only = st.checkbox("Только новости", value=False, key="news_filter")
            else:
                news_only = False

        with col_sort:
            if "сырые" in data_source:
                sort_options = {
                    "Получены (новые)": "scraped_at_desc",
                    "Опубликованы (новые)": "created_utc_desc",
                    "Рейтинг ⬆": "score_desc"
                }
            else:
                sort_options = {
                    "Обработаны (новые)": "processed_at_desc",
                    "Рейтинг ⬆": "score_desc"
                }

            sort_by = st.selectbox("Сортировка", list(sort_options.keys()), key="reddit_sort_viewer")
            sort_value = sort_options[sort_by]

    elif data_source == "Habr":
        with col_filter:
            habr_filter = st.selectbox(
                "Фильтр:",
                ["Все", "Только новости", "Только обработанные"],
                key="habr_filter"
            )

        with col_sort:
            habr_sort_options = {
                "Получены (новые)": "scraped_at_desc",
                "Опубликованы (новые)": "pub_date_desc",
                "Рейтинг ⬆": "rating_desc"
            }
            habr_sort_by = st.selectbox("Сортировка", list(habr_sort_options.keys()), key="habr_sort_viewer")
            habr_sort_value = habr_sort_options[habr_sort_by]

    elif data_source == "Telegram Посты":
        with col_filter:
            tg_filter = st.selectbox(
                "Фильтр:",
                ["Все", "Только опубликованные", "Только черновики"],
                key="tg_filter"
            )

        with col_sort:
            tg_sort_options = {
                "Созданы (новые)": "created_at_desc",
                "Опубликованы (новые)": "published_at_desc",
                "Символов ⬆": "character_count_desc"
            }
            tg_sort_by = st.selectbox("Сортировка", list(tg_sort_options.keys()), key="tg_sort_viewer")
            tg_sort_value = tg_sort_options[tg_sort_by]

    st.markdown("---")

    # Загрузка и отображение данных
    try:
        session = get_session()

        if data_source == "Reddit (сырые)":
            query = session.query(RedditPost)

            if sort_value == "scraped_at_desc":
                query = query.order_by(RedditPost.scraped_at.desc())
            elif sort_value == "created_utc_desc":
                query = query.order_by(RedditPost.created_utc.desc())
            elif sort_value == "score_desc":
                query = query.order_by(RedditPost.score.desc())

            posts = query.limit(limit).all()
            posts_data = [_reddit_post_to_dict(p) for p in posts]

            if posts_data:
                st.caption(f"🔴 Найдено: {len(posts_data)} сырых постов")
                for post_data in posts_data:
                    render_raw_post_viewer(post_data, st.session_state.language)
            else:
                st.info("Нет сырых постов")

        elif data_source == "Reddit (обработанные)":
            query = session.query(ProcessedRedditPost)

            if news_only:
                query = query.filter(ProcessedRedditPost.is_news == True)

            if sort_value == "processed_at_desc":
                query = query.order_by(ProcessedRedditPost.processed_at.desc())
            elif sort_value == "score_desc":
                query = query.order_by(ProcessedRedditPost.score.desc())

            processed_posts = query.limit(limit).all()

            # Получаем ID сырых постов для одного запроса
            post_ids = [p.post_id for p in processed_posts]
            raw_posts_map = {p.post_id: _reddit_post_to_dict(p) for p in session.query(RedditPost).filter(RedditPost.post_id.in_(post_ids)).all()}

            processed_posts_data = []
            for proc_post in processed_posts:
                raw_post_data = raw_posts_map.get(proc_post.post_id)
                processed_posts_data.append(_processed_reddit_post_to_dict(proc_post, raw_post_data))

            if processed_posts_data:
                filter_text = " (только новости)" if news_only else ""
                st.caption(f"🤖 Найдено: {len(processed_posts_data)} обработанных постов{filter_text}")

                for post_data in processed_posts_data:
                    render_processed_post_viewer(post_data, st.session_state.language)
            else:
                st.info("Нет обработанных постов" + (" (новостей)" if news_only else ""))

        elif data_source == "Habr":
            query = session.query(HabrArticle)

            # Применяем фильтры
            if habr_filter == "Только новости":
                query = query.filter(HabrArticle.is_news == True)
            elif habr_filter == "Только обработанные":
                query = query.filter(HabrArticle.editorial_processed == True)

            # Применяем сортировку
            if habr_sort_value == "scraped_at_desc":
                query = query.order_by(HabrArticle.scraped_at.desc())
            elif habr_sort_value == "pub_date_desc":
                query = query.order_by(HabrArticle.pub_date.desc().nullslast())
            elif habr_sort_value == "rating_desc":
                query = query.order_by(HabrArticle.rating.desc().nullslast())

            articles = query.limit(limit).all()
            articles_data = [_habr_article_to_dict(a) for a in articles]

            if articles_data:
                filter_text = ""
                if habr_filter != "Все":
                    filter_text = f" ({habr_filter.lower()})"
                st.caption(f"🇷🇺 Найдено: {len(articles_data)} статей Habr{filter_text}")

                for article_data in articles_data:
                    render_habr_article_viewer(article_data, st.session_state.language)
            else:
                st.info(f"Нет статей Habr{' (' + habr_filter.lower() + ')' if habr_filter != 'Все' else ''}")

        elif data_source == "Telegram":
            messages = session.query(TelegramMessage).order_by(
                TelegramMessage.date.desc()
            ).limit(limit).all()

            if messages:
                st.caption(f"💬 Найдено: {len(messages)} сообщений")
                for msg in messages:
                    with st.expander(f"@{msg.channel_username} • {msg.text[:80] if msg.text else '[Media]'}"):
                        st.markdown(f"**Канал:** {msg.channel_title}")
                        st.markdown(f"**Дата:** {msg.date}")
                        if msg.text:
                            st.text_area("Текст", msg.text, height=200, key=f"tg_{msg.id}")
                        if msg.has_media:
                            st.caption(f"📎 Медиа: {msg.media_type}")
                        st.caption(f"👁️ Просмотры: {msg.views} | Пересылок: {msg.forwards}")
            else:
                st.info("Нет сообщений Telegram")

        elif data_source == "Medium":
            articles = session.query(MediumArticle).order_by(
                MediumArticle.published_date.desc()
            ).limit(limit).all()

            if articles:
                st.caption(f"📝 Найдено: {len(articles)} статей")
                for art in articles:
                    with st.expander(f"Medium • {art.title[:80]}"):
                        st.markdown(f"**Автор:** {art.author}")
                        st.markdown(f"**Дата:** {art.published_date}")
                        if art.description:
                            st.write(art.description)
                        if art.full_text:
                            st.text_area("Полный текст", art.full_text, height=300, key=f"med_{art.id}")
                        st.link_button("Открыть на Medium", art.url)
            else:
                st.info("Нет статей Medium")

        elif data_source == "Telegram Посты":
            query = session.query(TelegramPost)

            # Применяем фильтры
            if tg_filter == "Только опубликованные":
                query = query.filter(TelegramPost.is_published == True)
            elif tg_filter == "Только черновики":
                query = query.filter(TelegramPost.is_published == False)

            # Применяем сортировку
            if tg_sort_value == "created_at_desc":
                query = query.order_by(TelegramPost.created_at.desc())
            elif tg_sort_value == "published_at_desc":
                query = query.order_by(TelegramPost.published_at.desc().nullslast())
            elif tg_sort_value == "character_count_desc":
                query = query.order_by(TelegramPost.character_count.desc())

            posts = query.limit(limit).all()
            posts_data = [_telegram_post_to_dict(p) for p in posts]

            if posts_data:
                filter_text = ""
                if tg_filter != "Все":
                    filter_text = f" ({tg_filter.lower()})"
                st.caption(f"📱 Найдено: {len(posts_data)} постов{filter_text}")

                for post_data in posts_data:
                    render_telegram_post_viewer(post_data, st.session_state.language)
            else:
                st.info(f"Нет постов{' (' + tg_filter.lower() + ')' if tg_filter != 'Все' else ''}")

        session.close()

    except Exception as e:
        st.error(f"Ошибка загрузки данных: {e}")
        import traceback
        st.code(traceback.format_exc())

# === TAB 7: SETTINGS ===
with tab7:
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

    # Структурированное отображение настроек по категориям
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
    render_settings_section("Параметры парсинга", parsing_settings, "🔥")
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

# === TAB 8: API ===
with tab8:
    st.header("🔌 API Доступ")

    col_api1, col_api2 = st.columns([2, 1])

    with col_api1:
        st.subheader("Эндпоинты API")

        st.code("""
Базовый URL: http://localhost:8000

GET /stats - Статистика
GET /habr/articles - Статьи Habr
GET /habr/articles/{id} - Конкретная статья
GET /reddit/posts - Посты Reddit
GET /telegram/posts - Telegram посты
GET /logs - Логи парсинга
DELETE /logs - Очистить логи
GET /health - Проверка здоровья
GET /sessions - Активные сессии
        """, language="bash")

        st.markdown("#### Примеры запросов:")

        col_ex1, col_ex2 = st.columns(2)

        with col_ex1:
            st.code("""
# Получить статистику
curl http://localhost:8000/stats

# Получить 10 статей Habr
curl "http://localhost:8000/habr/articles?limit=10"

# Получить только новости
curl "http://localhost:8000/habr/articles?is_news=true"
            """, language="bash")

        with col_ex2:
            st.code("""
# Получить логи
curl http://localhost:8000/logs

# Очистить логи
curl -X DELETE http://localhost:8000/logs

# Проверить здоровье
curl http://localhost:8000/health
            """, language="bash")

    with col_api2:
        st.subheader("Тестирование API")

        if st.button("📊 Получить статистику", use_container_width=True):
            try:
                response = requests.get("http://api:8000/stats", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    st.success("✅ Успешный ответ")
                    st.json(data)
                else:
                    st.error(f"❌ Ошибка: {response.status_code}")
                    st.text(response.text)
            except Exception as e:
                st.error(f"❌ Ошибка подключения: {e}")

        if st.button("📋 Получить логи", use_container_width=True):
            try:
                response = requests.get("http://api:8000/logs?limit=20", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    st.success(f"✅ Получено {len(data)} записей")

                    # Отображаем последние 5 записей
                    for log in data[-5:]:
                        level = log.get('level', 'INFO')
                        icon = {"INFO": "ℹ️", "SUCCESS": "✅", "WARNING": "⚠️", "ERROR": "❌"}.get(level, "📝")
                        st.caption(f"{icon} {log.get('timestamp', '')[:8]} {log.get('message', '')}")
                else:
                    st.error(f"❌ Ошибка: {response.status_code}")
                    st.text(response.text)
            except Exception as e:
                st.error(f"❌ Ошибка подключения: {e}")

        if st.button("🏥 Проверить здоровье", use_container_width=True):
            try:
                response = requests.get("http://api:8000/health", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    st.success("✅ API здоров")
                    st.json(data)
                else:
                    st.error(f"❌ Ошибка: {response.status_code}")
            except Exception as e:
                st.error(f"❌ Ошибка подключения: {e}")

        if st.button("🔄 Получить активные сессии", use_container_width=True):
            try:
                response = requests.get("http://api:8000/sessions", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    sessions = data.get('sessions', [])
                    st.success(f"✅ Активных сессий: {len(sessions)}")

                    for session in sessions:
                        with st.expander(f"Сессия: {session.get('id', '')[:8]}..."):
                            st.json(session)
                else:
                    st.error(f"❌ Ошибка: {response.status_code}")
            except Exception as e:
                st.error(f"❌ Ошибка подключения: {e}")

# === FOOTER ===
st.markdown("---")
col_f1, col_f2, col_f3 = st.columns([2, 1, 1])
with col_f1:
    st.caption("PostgreSQL • Docker • N8N • Ollama • GPT-OSS • Scrapy")
with col_f2:
    current_model = st.session_state.settings['llm_model']
    st.caption(f"🤖 Model: {current_model}")
with col_f3:
    if st.button("🔄 Обновить", key="refresh_btn"):
        st.rerun()