"""Reddit scraper с поддержкой семантической дедупликации и редакторской обработки."""
import os
import praw
import time
import logging
from datetime import datetime
from src.models.database import save_reddit_post

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s'
)
logger = logging.getLogger(__name__)


def get_reddit_client():
    """
    Создание клиента PRAW для Reddit API.

    Returns:
        Экземпляр praw.Reddit

    Raises:
        ValueError: Если credentials не настроены в .env
    """
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "NewsAggregator/1.0")

    if not client_id or not client_secret:
        raise ValueError("Reddit API не настроен в .env")

    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent
    )


def scrape_subreddit(
    subreddit_name: str,
    max_posts: int = 50,
    sort_by: str = 'hot',
    enable_llm: bool = True
):
    """
    Парсинг постов из одного subreddit.

    Args:
        subreddit_name: Название subreddit без префикса r/
        max_posts: Максимальное количество постов для загрузки
        sort_by: Тип сортировки ('hot', 'new', 'top')
        enable_llm: Включить редакторскую обработку через GPT-OSS

    Returns:
        Словарь с результатами парсинга:
        {
            'success': bool,
            'subreddit': str,
            'saved': int,              # новых постов сохранено
            'skipped': int,            # пропущено (точные дубликаты по ID)
            'semantic_duplicates': int, # пропущено (семантические дубликаты)
            'editorial_processed': int, # обработано редактором
            'errors': int              # ошибок при обработке
        }
    """
    logger.info(f"Парсинг r/{subreddit_name} (Editorial: {'ON' if enable_llm else 'OFF'})")

    try:
        reddit = get_reddit_client()
        subreddit = reddit.subreddit(subreddit_name)

        # Выбор метода получения постов
        if sort_by == 'hot':
            posts = subreddit.hot(limit=max_posts)
        elif sort_by == 'new':
            posts = subreddit.new(limit=max_posts)
        elif sort_by == 'top':
            posts = subreddit.top(limit=max_posts)
        else:
            logger.warning(f"Неизвестная сортировка '{sort_by}', использую 'hot'")
            posts = subreddit.hot(limit=max_posts)

        # Счетчики для статистики
        saved_count = 0
        skipped_count = 0
        semantic_duplicates = 0
        editorial_processed_count = 0
        error_count = 0

        for submission in posts:
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

                # Сохранение с полным pipeline
                result = save_reddit_post(
                    post_data,
                    check_semantic_duplicates=True,
                    process_with_editorial=enable_llm
                )

                # Обработка результата
                if result['saved']:
                    saved_count += 1
                    logger.info(f"  Сохранено [{saved_count}]: {post_data['title'][:60]}...")

                    if result.get('editorial_processed'):
                        editorial_processed_count += 1
                        logger.info(f"    Editorial обработан")
                else:
                    reason = result.get('reason', 'unknown')

                    if reason == 'duplicate_id':
                        skipped_count += 1
                        logger.debug(f"  Пропущен: точный дубликат")

                    elif reason == 'duplicate_semantic':
                        semantic_duplicates += 1
                        dup_id = result.get('duplicate_of', 'unknown')
                        similarity = result.get('similarity', 0)
                        logger.info(f"  Пропущен: семантический дубликат")
                        logger.info(f"    Похож на: {dup_id} (схожесть: {similarity:.2%})")

                    elif reason == 'too_short':
                        skipped_count += 1
                        logger.debug(f"  Пропущен: текст слишком короткий")

                    else:
                        error_count += 1
                        logger.warning(f"  Пропущен: {reason}")

                # Задержка для соблюдения rate limit Reddit API
                time.sleep(0.5)

            except Exception as e:
                error_count += 1
                logger.error(f"  Ошибка обработки поста: {e}")
                continue

        # Итоговая статистика
        logger.info(f"Завершено r/{subreddit_name}:")
        logger.info(f"  Сохранено: {saved_count}")
        logger.info(f"  ID дубликатов: {skipped_count}")
        logger.info(f"  Семантических дубликатов: {semantic_duplicates}")
        logger.info(f"  Editorial обработано: {editorial_processed_count}")
        logger.info(f"  Ошибок: {error_count}")

        return {
            'success': True,
            'subreddit': subreddit_name,
            'saved': saved_count,
            'skipped': skipped_count,
            'semantic_duplicates': semantic_duplicates,
            'editorial_processed': editorial_processed_count,
            'errors': error_count
        }

    except Exception as e:
        logger.error(f"Критическая ошибка при парсинге r/{subreddit_name}: {e}")
        return {
            'success': False,
            'subreddit': subreddit_name,
            'error': str(e)
        }


def scrape_multiple_subreddits(
    subreddits: list,
    max_posts: int = 50,
    sort_by: str = 'hot',
    delay: int = 5,
    enable_llm: bool = True
):
    """
    Парсинг нескольких subreddits последовательно.

    Args:
        subreddits: Список названий subreddits
        max_posts: Максимум постов на каждый subreddit
        sort_by: Тип сортировки
        delay: Задержка между subreddits в секундах (для rate limiting)
        enable_llm: Включить редакторскую обработку через GPT-OSS

    Returns:
        Список словарей с результатами для каждого subreddit
    """
    results = []

    logger.info(f"Начало массового парсинга: {len(subreddits)} subreddits")
    logger.info(f"Editorial обработка: {'Включена' if enable_llm else 'Отключена'}")

    for i, sub in enumerate(subreddits, 1):
        logger.info(f"[{i}/{len(subreddits)}] Обработка r/{sub}")

        try:
            result = scrape_subreddit(
                sub,
                max_posts,
                sort_by,
                enable_llm=enable_llm
            )
            results.append(result)

            # Задержка между subreddits (кроме последнего)
            if i < len(subreddits):
                time.sleep(delay)

        except Exception as e:
            logger.error(f"Ошибка r/{sub}: {e}")
            results.append({
                'success': False,
                'subreddit': sub,
                'error': str(e)
            })

    # Агрегированная статистика
    total_saved = sum(r.get('saved', 0) for r in results if r.get('success'))
    total_semantic = sum(r.get('semantic_duplicates', 0) for r in results if r.get('success'))
    total_editorial = sum(r.get('editorial_processed', 0) for r in results if r.get('success'))
    success_count = sum(1 for r in results if r.get('success'))

    logger.info("Массовый парсинг завершен:")
    logger.info(f"  Успешно: {success_count}/{len(results)} subreddits")
    logger.info(f"  Всего сохранено: {total_saved}")
    logger.info(f"  Семантических дубликатов: {total_semantic}")
    logger.info(f"  Editorial обработано: {total_editorial}")
    
    return results