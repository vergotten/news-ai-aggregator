"""
Reddit scraper с поддержкой семантической дедупликации, редакторской обработки и DEBUG режима.
"""
import os
import praw
import time
import logging
import requests  # Добавлено для создания session
from datetime import datetime
from typing import Optional, Callable, Dict, Any
from prawcore.exceptions import ResponseException, RequestException
from src.models.database import save_reddit_post

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


class RedditScraperError(Exception):
    """Базовый класс для ошибок Reddit scraper."""
    pass


class RedditAuthError(RedditScraperError):
    """Ошибка авторизации Reddit API."""
    pass


def mask_credential(cred: str) -> str:
    """Маскирует учетные данные для безопасного логирования (показывает первые 4 и последние 4 символа)."""
    if len(cred) < 8:
        return "****"
    return f"{cred[:4]}...{cred[-4:]}"


def log_request(response, *args, **kwargs):
    """Hook для логирования HTTP-запросов в requests (используется PRAW)."""
    request = response.request
    logger.debug(f"HTTP Request: {request.method} {request.url}")
    logger.debug(f"Headers: {request.headers}")
    if response.status_code >= 400:
        logger.error(f"HTTP Error: Status {response.status_code}")
        logger.error(f"Response Body: {response.text[:500]}...")  # Ограничиваем тело для безопасности
    else:
        logger.debug(f"HTTP Success: Status {response.status_code}")
    return response


def get_reddit_client(debug: bool = False) -> praw.Reddit:
    """
    Создание клиента PRAW для Reddit API.

    Args:
        debug: Включить детальное логирование

    Returns:
        Экземпляр praw.Reddit

    Raises:
        RedditAuthError: Если credentials не настроены в .env
    """
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("user_agent", "NewsAggregator/1.0")

    if not client_id or not client_secret:
        error_msg = "Reddit API credentials не настроены в .env"
        logger.error(f"❌ {error_msg}")
        logger.info("📋 Добавьте в .env:")
        logger.info("   REDDIT_CLIENT_ID=ваш_client_id")
        logger.info("   REDDIT_CLIENT_SECRET=ваш_client_secret")
        raise RedditAuthError(error_msg)

    if debug:
        logger.debug(f"CLIENT_ID: {mask_credential(client_id)} (length: {len(client_id)})")
        logger.debug(f"CLIENT_SECRET: {mask_credential(client_secret)} (length: {len(client_secret)})")
        logger.debug(f"USER_AGENT: {user_agent}")

    if len(client_id) < 10 or len(client_secret) < 20:
        error_msg = "Reddit credentials выглядят некорректно"
        logger.error(f"❌ {error_msg}")
        logger.error(f"   CLIENT_ID длина: {len(client_id)} (ожидается 14-22)")
        logger.error(f"   SECRET длина: {len(client_secret)} (ожидается 27-32)")
        raise RedditAuthError(error_msg)

    try:
        if debug:
            logger.debug("Создание PRAW клиента...")

        # Создаем кастомную session для добавления hook
        session = requests.Session()
        session.hooks["response"].append(log_request)

        reddit = praw.Reddit(
            client_id=client_id,
            client_secret=client_secret,
            user_agent=user_agent,
            check_for_async=False,
            requestor_kwargs={"session": session}  # Передаем session для hooks
        )

        # Тестовый запрос для проверки авторизации
        if debug:
            logger.debug("Тестовый запрос для проверки авторизации (subreddit 'python', hot limit=1)...")

        test_sub = reddit.subreddit("python")
        list(test_sub.hot(limit=1))

        logger.info("✅ Reddit API подключен")
        return reddit

    except ResponseException as e:
        if e.response.status_code == 401:
            error_msg = "401 Unauthorized - неверные Reddit credentials"
            logger.error(f"❌ {error_msg}")
            logger.error("🔧 Решение:")
            logger.error("   1. Откройте https://www.reddit.com/prefs/apps")
            logger.error("   2. Пересоздайте приложение (type: script)")
            logger.error("   3. Обновите .env с новыми credentials")

            if debug:
                logger.debug(f"Response status: {e.response.status_code}")
                logger.debug(f"Response text: {e.response.text[:200]}")

            raise RedditAuthError(error_msg) from e
        raise

    except Exception as e:
        logger.error(f"❌ Ошибка подключения к Reddit: {e}")
        raise


def scrape_subreddit(
    subreddit_name: str,
    max_posts: int = 1,
    sort_by: str = 'hot',
    enable_llm: bool = True,
    log_callback: Optional[Callable[[str, str], None]] = None,
    retry_on_error: bool = True,
    max_retries: int = 3,
    debug: bool = False
) -> Dict[str, Any]:
    """
    Парсинг постов из одного subreddit.

    Args:
        subreddit_name: Название subreddit без префикса r/
        max_posts: Максимальное количество постов (дефолт: 1 для безопасности)
        sort_by: Тип сортировки ('hot', 'new', 'top')
        enable_llm: Включить редакторскую обработку через GPT-OSS
        log_callback: Callback функция для логирования в UI (message, level)
        retry_on_error: Повторять попытки при ошибках
        max_retries: Максимальное количество попыток
        debug: Включить детальное логирование

    Returns:
        Словарь с результатами парсинга:
        {
            'success': bool,
            'subreddit': str,
            'saved': int,
            'skipped': int,
            'semantic_duplicates': int,
            'editorial_processed': int,
            'errors': int,
            'retries': int
        }
    """
    def log(message: str, level: str = "INFO"):
        """Универсальная функция логирования."""
        logger_func = getattr(logger, level.lower(), logger.info)
        logger_func(message)

        # Вызываем callback если он есть
        if log_callback:
            try:
                log_callback(message, level)
            except Exception as e:
                logger.warning(f"Ошибка в log_callback: {e}")

    log(f"Парсинг r/{subreddit_name} (Editorial: {'ON' if enable_llm else 'OFF'})")

    if debug:
        log(f"DEBUG режим включён", "DEBUG")
        log(f"Параметры: max_posts={max_posts}, sort={sort_by}", "DEBUG")

    retry_count = 0
    last_error = None

    while retry_count <= max_retries:
        try:
            # Получение Reddit клиента
            reddit = get_reddit_client(debug=debug)
            subreddit = reddit.subreddit(subreddit_name)

            # Выбор метода получения постов
            if sort_by == 'hot':
                posts = subreddit.hot(limit=max_posts)
            elif sort_by == 'new':
                posts = subreddit.new(limit=max_posts)
            elif sort_by == 'top':
                posts = subreddit.top(limit=max_posts)
            else:
                log(f"Неизвестная сортировка '{sort_by}', использую 'hot'", "WARNING")
                posts = subreddit.hot(limit=max_posts)

            # Счетчики для статистики
            saved_count = 0
            skipped_count = 0
            semantic_duplicates = 0
            editorial_processed_count = 0
            error_count = 0

            for idx, submission in enumerate(posts, 1):
                try:
                    # Парсинг данных поста
                    post_data = {
                        'post_id': submission.id,
                        'subreddit': submission.subreddit.display_name,
                        'title': submission.title,
                        'author': str(submission.author) if submission.author else '[deleted]',
                        'url': submission.url,
                        'selftext': submission.selftext if submission.is_self else '',
                        'score': submission.score,
                        'num_comments': submission.num_comments,
                        'created_utc': datetime.fromtimestamp(submission.created_utc),
                        'is_self': submission.is_self,
                        'link_flair_text': submission.link_flair_text
                    }

                    if debug:
                        log(f"  [{idx}/{max_posts}] Post ID: {submission.id}", "DEBUG")
                        log(f"  Title: {post_data['title'][:50]}...", "DEBUG")

                    # Сохранение с полным pipeline
                    result = save_reddit_post(
                        post_data,
                        check_semantic_duplicates=True,
                        process_with_editorial=enable_llm
                    )

                    # Обработка результата
                    if result['saved']:
                        saved_count += 1
                        log(f"  ✓ Сохранено [{saved_count}]: {post_data['title'][:60]}...")

                        if result.get('editorial_processed'):
                            editorial_processed_count += 1
                            log(f"    → Editorial обработан")
                    else:
                        reason = result.get('reason', 'unknown')

                        if reason == 'duplicate_id':
                            skipped_count += 1
                            if debug:
                                log(f"  ⊗ Пропущен: точный дубликат", "DEBUG")

                        elif reason == 'duplicate_semantic':
                            semantic_duplicates += 1
                            dup_id = result.get('duplicate_of', 'unknown')
                            similarity = result.get('similarity', 0)
                            log(f"  ≈ Пропущен: семантический дубликат")
                            log(f"    Похож на: {dup_id} (схожесть: {similarity:.2%})")

                        elif reason == 'too_short':
                            skipped_count += 1
                            if debug:
                                log(f"  ⊘ Пропущен: текст слишком короткий", "DEBUG")

                        else:
                            error_count += 1
                            log(f"  ✗ Ошибка: {reason}", "WARNING")

                    # Rate limiting
                    if idx < max_posts:
                        time.sleep(0.5)

                except Exception as e:
                    error_count += 1
                    log(f"  ✗ Ошибка обработки поста: {e}", "ERROR")
                    if debug:
                        import traceback
                        log(f"  Traceback: {traceback.format_exc()}", "DEBUG")
                    continue

            # Итоговая статистика
            log(f"Завершено r/{subreddit_name}:")
            log(f"  • Сохранено: {saved_count}")
            log(f"  • ID дубликатов: {skipped_count}")
            log(f"  • Семантических дубликатов: {semantic_duplicates}")
            log(f"  • Editorial обработано: {editorial_processed_count}")
            if error_count > 0:
                log(f"  • Ошибок: {error_count}", "WARNING")

            return {
                'success': True,
                'subreddit': subreddit_name,
                'saved': saved_count,
                'skipped': skipped_count,
                'semantic_duplicates': semantic_duplicates,
                'editorial_processed': editorial_processed_count,
                'errors': error_count,
                'retries': retry_count
            }

        except RedditAuthError as e:
            # Auth ошибки не retry
            log(f"❌ Ошибка авторизации: {e}", "ERROR")
            return {
                'success': False,
                'subreddit': subreddit_name,
                'error': str(e),
                'error_type': 'auth',
                'retries': retry_count
            }

        except ResponseException as e:
            if e.response.status_code == 429:
                # Rate limit - exponential backoff
                retry_count += 1
                if retry_count <= max_retries and retry_on_error:
                    wait_time = 2 ** retry_count
                    log(f"⚠️ Rate limit (429). Retry {retry_count}/{max_retries} через {wait_time}s", "WARNING")
                    time.sleep(wait_time)
                    continue
                else:
                    log(f"❌ Rate limit exceeded после {retry_count} попыток", "ERROR")
                    return {
                        'success': False,
                        'subreddit': subreddit_name,
                        'error': 'Rate limit exceeded',
                        'error_type': 'rate_limit',
                        'retries': retry_count
                    }
            else:
                last_error = e
                retry_count += 1
                if retry_count <= max_retries and retry_on_error:
                    log(f"⚠️ HTTP {e.response.status_code}. Retry {retry_count}/{max_retries}", "WARNING")
                    time.sleep(2)
                    continue
                else:
                    log(f"❌ HTTP ошибка после {retry_count} попыток: {e}", "ERROR")
                    return {
                        'success': False,
                        'subreddit': subreddit_name,
                        'error': str(e),
                        'error_type': 'http',
                        'retries': retry_count
                    }

        except Exception as e:
            last_error = e
            retry_count += 1
            if retry_count <= max_retries and retry_on_error:
                log(f"⚠️ Ошибка: {e}. Retry {retry_count}/{max_retries}", "WARNING")
                time.sleep(2)
                continue
            else:
                log(f"❌ Критическая ошибка после {retry_count} попыток: {e}", "ERROR")
                if debug:
                    import traceback
                    log(f"Traceback: {traceback.format_exc()}", "DEBUG")
                return {
                    'success': False,
                    'subreddit': subreddit_name,
                    'error': str(e),
                    'error_type': 'unknown',
                    'retries': retry_count
                }

    # Если дошли сюда - все retry исчерпаны
    return {
        'success': False,
        'subreddit': subreddit_name,
        'error': str(last_error),
        'error_type': 'max_retries_exceeded',
        'retries': retry_count
    }


def scrape_multiple_subreddits(
    subreddits: list,
    max_posts: int = 1,  # 🎯 ИЗМЕНЕНО: дефолт 1 вместо 50
    sort_by: str = 'hot',
    delay: int = 5,
    enable_llm: bool = True,
    log_callback: Optional[Callable[[str, str], None]] = None,  # 🆕 ДОБАВЛЕНО
    stop_on_auth_error: bool = True,  # 🆕 ДОБАВЛЕНО
    debug: bool = False  # 🆕 ДОБАВЛЕНО
) -> list:
    """
    Парсинг нескольких subreddits последовательно.

    Args:
        subreddits: Список названий subreddits
        max_posts: Максимум постов на каждый subreddit (дефолт: 1)
        sort_by: Тип сортировки
        delay: Задержка между subreddits в секундах
        enable_llm: Включить редакторскую обработку
        log_callback: Callback функция для логирования
        stop_on_auth_error: Остановить парсинг при ошибке авторизации
        debug: Включить детальное логирование

    Returns:
        Список словарей с результатами для каждого subreddit
    """
    def log(message: str, level: str = "INFO"):
        """Универсальная функция логирования."""
        logger_func = getattr(logger, level.lower(), logger.info)
        logger_func(message)

        if log_callback:
            try:
                log_callback(message, level)
            except Exception as e:
                logger.warning(f"Ошибка в log_callback: {e}")

    results = []

    log(f"Начало массового парсинга: {len(subreddits)} subreddits")
    log(f"Editorial обработка: {'Включена' if enable_llm else 'Отключена'}")

    if debug:
        log(f"DEBUG режим включён", "DEBUG")
        log(f"Параметры: max_posts={max_posts}, sort={sort_by}, delay={delay}s", "DEBUG")

    # Проверка авторизации перед стартом
    try:
        get_reddit_client(debug=debug)
        log("✅ Предварительная проверка авторизации успешна")
    except RedditAuthError as e:
        log(f"❌ Ошибка авторизации перед стартом: {e}", "ERROR")
        log("⚠️ Парсинг прерван. Исправьте credentials и попробуйте снова.", "ERROR")
        return [{
            'success': False,
            'error': str(e),
            'error_type': 'auth_pre_check'
        }]

    for i, sub in enumerate(subreddits, 1):
        log(f"[{i}/{len(subreddits)}] Обработка r/{sub}")

        try:
            result = scrape_subreddit(
                sub,
                max_posts,
                sort_by,
                enable_llm=enable_llm,
                log_callback=log_callback,
                debug=debug
            )
            results.append(result)

            # Проверка на auth ошибку
            if not result['success'] and result.get('error_type') == 'auth':
                if stop_on_auth_error:
                    log("⚠️ Обнаружена ошибка авторизации. Парсинг остановлен.", "ERROR")
                    log("   Исправьте credentials и запустите снова.", "ERROR")
                    break

            # Задержка между subreddits (кроме последнего)
            if i < len(subreddits):
                time.sleep(delay)

        except Exception as e:
            log(f"❌ Критическая ошибка r/{sub}: {e}", "ERROR")
            results.append({
                'success': False,
                'subreddit': sub,
                'error': str(e),
                'error_type': 'critical'
            })

    # Агрегированная статистика
    successful = [r for r in results if r.get('success')]
    failed = [r for r in results if not r.get('success')]

    total_saved = sum(r.get('saved', 0) for r in successful)
    total_semantic = sum(r.get('semantic_duplicates', 0) for r in successful)
    total_editorial = sum(r.get('editorial_processed', 0) for r in successful)

    log("Массовый парсинг завершен:")
    log(f"  • Успешно: {len(successful)}/{len(results)} subreddits")
    if failed:
        log(f"  • Ошибок: {len(failed)}", "WARNING")
    log(f"  • Всего сохранено: {total_saved}")
    log(f"  • Семантических дубликатов: {total_semantic}")
    log(f"  • Editorial обработано: {total_editorial}")

    return results


# ============================================================================
# CLI для тестирования
# ============================================================================

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Reddit Scraper с DEBUG режимом")
    parser.add_argument(
        "subreddit",
        nargs="?",
        default="python",
        help="Subreddit для парсинга (по умолчанию: python)"
    )
    parser.add_argument(
        "--max-posts",
        type=int,
        default=1,
        help="Количество постов (по умолчанию: 1)"
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Включить DEBUG режим"
    )
    parser.add_argument(
        "--no-llm",
        action="store_true",
        help="Отключить Editorial обработку"
    )

    args = parser.parse_args()

    print("=" * 70)
    print("REDDIT SCRAPER - Тестовый запуск")
    print("=" * 70)
    print(f"Subreddit: r/{args.subreddit}")
    print(f"Max posts: {args.max_posts}")
    print(f"Debug: {args.debug}")
    print(f"Editorial: {not args.no_llm}")
    print("=" * 70 + "\n")

    result = scrape_subreddit(
        subreddit_name=args.subreddit,
        max_posts=args.max_posts,
        enable_llm=not args.no_llm,
        debug=args.debug
    )

    print("\n" + "=" * 70)
    print("РЕЗУЛЬТАТ")
    print("=" * 70)
    print(f"Success: {result['success']}")
    if result['success']:
        print(f"Saved: {result.get('saved', 0)}")
        print(f"Skipped: {result.get('skipped', 0)}")
        print(f"Semantic duplicates: {result.get('semantic_duplicates', 0)}")
        print(f"Editorial: {result.get('editorial_processed', 0)}")
    else:
        print(f"Error: {result.get('error')}")
        print(f"Error type: {result.get('error_type')}")