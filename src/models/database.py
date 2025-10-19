"""Модели базы данных и операции с PostgreSQL."""
import os
import logging
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime
import uuid as uuid_lib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)
logger = logging.getLogger(__name__)

Base = declarative_base()


class RedditPost(Base):
    """Модель для постов Reddit."""
    __tablename__ = 'reddit_posts'
    __table_args__ = {'schema': 'parsers'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(String(50), unique=True, nullable=False, index=True)
    subreddit = Column(String(100), nullable=False, index=True)
    title = Column(Text, nullable=False)
    author = Column(String(100))
    url = Column(Text)
    selftext = Column(Text)
    score = Column(Integer, default=0)
    num_comments = Column(Integer, default=0)
    created_utc = Column(DateTime, index=True)
    is_self = Column(Boolean, default=False)
    link_flair_text = Column(String(100))
    scraped_at = Column(DateTime, default=datetime.utcnow, index=True)

    # Связь с Qdrant
    qdrant_id = Column(UUID(as_uuid=True), index=True)

    def __repr__(self):
        return f"<RedditPost {self.post_id}: {self.title[:50]}>"


class ProcessedRedditPost(Base):
    """Модель для обработанных постов Reddit (Editorial)."""
    __tablename__ = 'processed_reddit_posts'
    __table_args__ = {'schema': 'parsers'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    post_id = Column(String(50), unique=True, nullable=False, index=True)

    # Оригинальные данные
    original_title = Column(Text, nullable=False)
    original_text = Column(Text)
    subreddit = Column(String(100), index=True)
    author = Column(String(100))
    url = Column(Text)
    score = Column(Integer, default=0)

    # Результаты редакторской обработки
    is_news = Column(Boolean, default=False, index=True)
    original_summary = Column(Text)
    rewritten_post = Column(Text)
    editorial_title = Column(String(200))
    teaser = Column(Text)
    image_prompt = Column(Text)

    # Метаданные
    processed_at = Column(DateTime, default=datetime.utcnow, index=True)
    processing_time = Column(Integer)  # milliseconds
    model_used = Column(String(50))

    def __repr__(self):
        return f"<ProcessedRedditPost {self.post_id}: {self.editorial_title or self.original_title[:50]}>"


class TelegramMessage(Base):
    """Модель для сообщений Telegram."""
    __tablename__ = 'telegram_messages'
    __table_args__ = {'schema': 'parsers'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    message_id = Column(Integer, nullable=False)
    channel_username = Column(String(100), nullable=False, index=True)
    channel_title = Column(String(200))
    text = Column(Text)
    date = Column(DateTime, index=True)
    views = Column(Integer, default=0)
    forwards = Column(Integer, default=0)
    has_media = Column(Boolean, default=False)
    media_type = Column(String(50))
    scraped_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<TelegramMessage {self.message_id} from {self.channel_username}>"


class MediumArticle(Base):
    """Модель для статей Medium."""
    __tablename__ = 'medium_articles'
    __table_args__ = {'schema': 'parsers'}

    id = Column(Integer, primary_key=True, autoincrement=True)
    url = Column(Text, unique=True, nullable=False, index=True)
    title = Column(Text, nullable=False)
    author = Column(String(200))
    description = Column(Text)
    full_text = Column(Text)
    claps = Column(Integer, default=0)
    published_date = Column(DateTime, index=True)
    is_paywalled = Column(Boolean, default=False)
    source = Column(String(50))
    tags = Column(Text)
    scraped_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<MediumArticle {self.title[:50]}>"


def get_engine():
    """Создание и возврат engine для PostgreSQL."""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL не настроен в .env")
    return create_engine(db_url, echo=False)


def init_db():
    """Инициализация базы данных и создание таблиц."""
    engine = get_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS parsers"))
            conn.commit()
        logger.info("Схема parsers создана или существует")

        Base.metadata.create_all(engine)
        logger.info("Таблицы созданы")
    except Exception as e:
        logger.error(f"Ошибка инициализации БД: {e}")
        raise


def get_session():
    """Создание новой сессии для работы с БД."""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def get_stats_extended():
    """Получение расширенной статистики."""
    session = get_session()
    try:
        reddit_count = session.query(RedditPost).count()
        telegram_count = session.query(TelegramMessage).count()
        medium_count = session.query(MediumArticle).count()

        latest_reddit = session.query(RedditPost).order_by(
            RedditPost.scraped_at.desc()
        ).first()

        latest_telegram = session.query(TelegramMessage).order_by(
            TelegramMessage.scraped_at.desc()
        ).first()

        latest_medium = session.query(MediumArticle).order_by(
            MediumArticle.scraped_at.desc()
        ).first()

        return {
            'reddit_posts': reddit_count,
            'telegram_messages': telegram_count,
            'medium_articles': medium_count,
            'latest_reddit': latest_reddit.scraped_at if latest_reddit else None,
            'latest_telegram': latest_telegram.scraped_at if latest_telegram else None,
            'latest_medium': latest_medium.scraped_at if latest_medium else None
        }
    finally:
        session.close()


def get_posts_by_subreddit(subreddit: str, limit: int = 100):
    """Получение RAW постов из конкретного subreddit."""
    session = get_session()
    try:
        posts = session.query(RedditPost).filter_by(
            subreddit=subreddit
        ).order_by(RedditPost.created_utc.desc()).limit(limit).all()
        return posts
    finally:
        session.close()


def get_processed_posts(limit: int = 100, news_only: bool = False):
    """Получение обработанных постов."""
    session = get_session()
    try:
        query = session.query(ProcessedRedditPost)

        if news_only:
            query = query.filter(ProcessedRedditPost.is_news == True)

        posts = query.order_by(ProcessedRedditPost.processed_at.desc()).limit(limit).all()
        return posts
    finally:
        session.close()


def get_processed_by_subreddit(subreddit: str, limit: int = 100):
    """Получение обработанных постов из конкретного subreddit."""
    session = get_session()
    try:
        posts = session.query(ProcessedRedditPost).filter_by(
            subreddit=subreddit
        ).order_by(ProcessedRedditPost.processed_at.desc()).limit(limit).all()
        return posts
    finally:
        session.close()
    """Получение постов из конкретного subreddit."""
    session = get_session()
    try:
        posts = session.query(RedditPost).filter_by(
            subreddit=subreddit
        ).order_by(RedditPost.created_utc.desc()).limit(limit).all()
        return posts
    finally:
        session.close()


def get_medium_articles(limit: int = 100, author: str = None, tag: str = None):
    """Получение статей Medium с фильтрацией."""
    session = get_session()
    try:
        query = session.query(MediumArticle)

        if author:
            query = query.filter(MediumArticle.author.ilike(f'%{author}%'))

        if tag:
            query = query.filter(MediumArticle.tags.ilike(f'%{tag}%'))

        articles = query.order_by(MediumArticle.published_date.desc()).limit(limit).all()
        return articles
    finally:
        session.close()


def save_medium_article(article_data: dict):
    """Сохранение статьи Medium в БД."""
    session = get_session()
    try:
        existing = session.query(MediumArticle).filter_by(url=article_data['url']).first()
        if existing:
            return False

        if 'tags' in article_data and isinstance(article_data['tags'], list):
            import json
            article_data['tags'] = json.dumps(article_data['tags'])

        article = MediumArticle(**article_data)
        session.add(article)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка сохранения статьи: {e}")
        return False
    finally:
        session.close()


def save_telegram_message(msg_data: dict):
    """Сохранение сообщения Telegram в БД."""
    session = get_session()
    try:
        existing = session.query(TelegramMessage).filter_by(
            message_id=msg_data['message_id'],
            channel_username=msg_data['channel_username']
        ).first()
        if existing:
            return False

        message = TelegramMessage(**msg_data)
        session.add(message)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"Ошибка сохранения сообщения: {e}")
        return False
    finally:
        session.close()


def _check_services_health():
    """Проверка доступности Qdrant и Ollama."""
    logger.info("=" * 70)
    logger.info("ПРОВЕРКА ДОСТУПНОСТИ СЕРВИСОВ")
    logger.info("=" * 70)

    qdrant_ok = False
    ollama_ok = False

    try:
        logger.info("Проверка Qdrant...")
        from src.services.qdrant_service import get_qdrant_service
        qdrant = get_qdrant_service()
        qdrant_ok = qdrant.health_check()
        if qdrant_ok:
            logger.info("Qdrant доступен")
            info = qdrant.get_collection_info()
            logger.info(f"Векторов в коллекции: {info.get('vectors_count', 0)}")
        else:
            logger.warning("Qdrant недоступен")
    except Exception as e:
        logger.error(f"Ошибка подключения к Qdrant: {e}")

    try:
        logger.info("Проверка Ollama...")
        from src.services.ollama_service import get_ollama_service
        ollama = get_ollama_service()
        ollama_ok = ollama.health_check()
        if ollama_ok:
            logger.info("Ollama доступен")
        else:
            logger.warning("Ollama недоступен")
    except Exception as e:
        logger.error(f"Ошибка подключения к Ollama: {e}")

    logger.info("=" * 70)
    logger.info(f"ИТОГ: Qdrant={'OK' if qdrant_ok else 'FAIL'} | Ollama={'OK' if ollama_ok else 'FAIL'}")
    logger.info("=" * 70)

    return qdrant_ok, ollama_ok


def _process_editorial(post_id: str, text: str, title: str, post_data: dict):
    """Обработка через редакторский конвейер и сохранение в processed_reddit_posts."""
    logger.info("=" * 70)
    logger.info("РЕДАКТОРСКАЯ ОБРАБОТКА GPT-OSS")
    logger.info("=" * 70)

    import time
    start_time = time.time()

    try:
        from src.services.editorial_service import get_editorial_service
        editorial = get_editorial_service()

        result = editorial.process_post(
            title=title,
            content=text,
            source='reddit'
        )

        if result.get('error'):
            logger.error(f"Ошибка обработки: {result['error']}")
            return False

        processing_time_ms = int((time.time() - start_time) * 1000)

        logger.info("Сохранение в processed_reddit_posts...")
        session = get_session()
        try:
            # Проверка существования
            existing = session.query(ProcessedRedditPost).filter_by(post_id=post_id).first()
            if existing:
                logger.info("Обновление существующей записи")
                processed_post = existing
            else:
                processed_post = ProcessedRedditPost(post_id=post_id)
                session.add(processed_post)

            # Оригинальные данные
            processed_post.original_title = title
            processed_post.original_text = text
            processed_post.subreddit = post_data.get('subreddit')
            processed_post.author = post_data.get('author')
            processed_post.url = post_data.get('url')
            processed_post.score = post_data.get('score', 0)

            # Результаты обработки
            processed_post.is_news = result.get('is_news', False)

            if processed_post.is_news:
                processed_post.original_summary = result.get('original_summary')
                processed_post.rewritten_post = result.get('rewritten_post')
                processed_post.editorial_title = result.get('title')
                processed_post.teaser = result.get('teaser')
                processed_post.image_prompt = result.get('image_prompt')

                logger.info("Новость обработана")
                logger.info(f"Заголовок: {processed_post.editorial_title}")
            else:
                logger.info("Не новость, сохранено как non-news")

            # Метаданные
            processed_post.processed_at = datetime.utcnow()
            processed_post.processing_time = processing_time_ms
            processed_post.model_used = "gpt-oss:20b"

            session.commit()
            logger.info(f"Сохранено в processed_reddit_posts (ID: {processed_post.id})")
            logger.info("=" * 70)
            logger.info("РЕДАКТОРСКАЯ ОБРАБОТКА ЗАВЕРШЕНА")
            logger.info("=" * 70)
            return True

        except Exception as db_error:
            logger.error(f"Ошибка БД: {db_error}")
            session.rollback()
            return False
        finally:
            session.close()

    except Exception as e:
        logger.error(f"КРИТИЧЕСКАЯ ОШИБКА: {e}")
        logger.exception("Stack trace:")
        return False


def save_reddit_post(
    post_data: dict,
    check_semantic_duplicates: bool = True,
    process_with_editorial: bool = True
):
    """Сохранение поста Reddit с полным pipeline."""
    logger.info("=" * 70)
    logger.info(f"НАЧАЛО PIPELINE: {post_data['post_id']}")
    logger.info(f"Заголовок: {post_data['title'][:60]}...")
    logger.info(f"Subreddit: r/{post_data['subreddit']}")
    logger.info("=" * 70)

    session = get_session()
    editorial_processed = False

    try:
        # ШАГ 1: ПРОВЕРКА ТОЧНОГО ДУБЛИКАТА
        logger.info("ШАГ 1/7: Проверка точного дубликата по post_id")
        existing = session.query(RedditPost).filter_by(post_id=post_data['post_id']).first()
        if existing:
            logger.warning(f"Точный дубликат найден: {post_data['post_id']}")
            return {
                'saved': False,
                'reason': 'duplicate_id',
                'duplicate_of': post_data['post_id'],
                'similarity': None,
                'editorial_processed': False
            }
        logger.info("Точных дубликатов нет")

        # ШАГ 2: СОХРАНЕНИЕ В POSTGRESQL
        logger.info("ШАГ 2/7: Сохранение в PostgreSQL")
        post = RedditPost(**post_data)
        session.add(post)
        session.commit()
        session.refresh(post)
        logger.info(f"Сохранено в PostgreSQL: ID={post.id}, post_id={post.post_id}")

        # ШАГ 3: HEALTH-CHECK СЕРВИСОВ
        if not check_semantic_duplicates and not process_with_editorial:
            logger.info("Векторизация и Editorial отключены")
            logger.info("=" * 70)
            logger.info("PIPELINE ЗАВЕРШЕН (базовый режим)")
            logger.info("=" * 70)
            return {
                'saved': True,
                'reason': None,
                'duplicate_of': None,
                'similarity': None,
                'editorial_processed': False
            }

        logger.info("ШАГ 3/7: Проверка доступности сервисов")
        qdrant_ok, ollama_ok = _check_services_health()

        if not (qdrant_ok and ollama_ok):
            logger.warning("Сервисы недоступны")
            logger.info("=" * 70)
            logger.info("PIPELINE ЗАВЕРШЕН (сервисы недоступны)")
            logger.info("=" * 70)
            return {
                'saved': True,
                'reason': 'services_unavailable',
                'duplicate_of': None,
                'similarity': None,
                'editorial_processed': False
            }

        # ШАГ 4: ПОДГОТОВКА ТЕКСТА
        logger.info("ШАГ 4/7: Подготовка текста")
        text = f"{post.title}\n\n{post.selftext or ''}"
        text_len = len(text.strip())
        logger.info(f"Длина текста: {text_len} символов")

        if text_len < 50:
            logger.warning("Текст короткий, пропускаем векторизацию")
            logger.info("=" * 70)
            logger.info("PIPELINE ЗАВЕРШЕН (текст короткий)")
            logger.info("=" * 70)
            return {
                'saved': True,
                'reason': 'too_short',
                'duplicate_of': None,
                'similarity': None,
                'editorial_processed': False
            }
        logger.info("Текст готов")

        # ШАГ 5: СЕМАНТИЧЕСКАЯ ПРОВЕРКА
        if check_semantic_duplicates:
            logger.info("ШАГ 5/7: Проверка семантических дубликатов")
            try:
                from src.services.deduplication_service import get_deduplication_service
                dedup = get_deduplication_service()

                logger.info("Запрос к Ollama для генерации embedding...")
                is_duplicate, dup_post_id, similarity = dedup.check_duplicate(text)

                if is_duplicate:
                    logger.warning("=" * 70)
                    logger.warning("СЕМАНТИЧЕСКИЙ ДУБЛИКАТ ОБНАРУЖЕН")
                    logger.warning(f"Новый: {post.post_id}")
                    logger.warning(f"Дубликат: {dup_post_id}")
                    logger.warning(f"Схожесть: {similarity:.2%}")
                    logger.warning("=" * 70)

                    logger.info("Откат: удаление из PostgreSQL...")
                    session.delete(post)
                    session.commit()

                    logger.info("=" * 70)
                    logger.info("PIPELINE ЗАВЕРШЕН (дубликат)")
                    logger.info("=" * 70)

                    return {
                        'saved': False,
                        'reason': 'duplicate_semantic',
                        'duplicate_of': dup_post_id,
                        'similarity': similarity,
                        'editorial_processed': False
                    }

                logger.info("Семантических дубликатов нет")

            except Exception as e:
                logger.error(f"Ошибка проверки дубликатов: {e}")
                logger.warning("Продолжаем без проверки")
        else:
            logger.info("ШАГ 5/7: Пропущено (check_semantic_duplicates=False)")

        # ШАГ 6: СОХРАНЕНИЕ В QDRANT
        logger.info("ШАГ 6/7: Сохранение embedding в Qdrant")
        try:
            from src.services.deduplication_service import get_deduplication_service
            dedup = get_deduplication_service()

            metadata = {
                'subreddit': post.subreddit,
                'title': post.title,
                'author': post.author,
                'score': post.score
            }

            logger.info("Генерация и сохранение...")
            qdrant_id = dedup.save_to_qdrant(text, post.post_id, metadata)

            if not qdrant_id:
                logger.error("Не удалось сохранить в Qdrant")
            else:
                logger.info(f"Embedding в Qdrant: {qdrant_id}")

                logger.info("Связывание PostgreSQL <-> Qdrant...")
                if dedup.update_postgres_with_qdrant_id(post.post_id, qdrant_id):
                    logger.info("PostgreSQL обновлен")
                else:
                    logger.warning("Не удалось обновить qdrant_id")

        except Exception as e:
            logger.error(f"Ошибка Qdrant: {e}")

        # ШАГ 7: РЕДАКТОРСКАЯ ОБРАБОТКА
        if process_with_editorial and ollama_ok:
            logger.info("ШАГ 7/7: Редакторская обработка")
            editorial_processed = _process_editorial(post.post_id, text, post.title, post_data)
        else:
            logger.info("ШАГ 7/7: Пропущено")

        logger.info("=" * 70)
        logger.info("ПОЛНЫЙ PIPELINE ЗАВЕРШЕН")
        logger.info(f"PostgreSQL ID: {post.id}")
        if qdrant_id:
            logger.info(f"Qdrant UUID: {qdrant_id}")
        logger.info(f"Editorial: {'OK' if editorial_processed else 'SKIP'}")
        logger.info("=" * 70)

        return {
            'saved': True,
            'reason': None,
            'duplicate_of': None,
            'similarity': None,
            'editorial_processed': editorial_processed
        }

    except Exception as e:
        logger.error("=" * 70)
        logger.error(f"КРИТИЧЕСКАЯ ОШИБКА: {e}")
        logger.error("=" * 70)
        session.rollback()
        return {
            'saved': False,
            'reason': 'error',
            'duplicate_of': None,
            'similarity': None,
            'editorial_processed': False
        }
    finally:
        session.close()