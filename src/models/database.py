"""
Слой базы данных с моделями SQLAlchemy и паттерном репозитория.

Реализует:
- Паттерн репозитория для абстракции доступа к данным
- Паттерн Unit of Work через управление сессиями
- Пул соединений
- Правильную обработку исключений с декораторами
- Валидацию данных перед сохранением
"""

import os
from pathlib import Path
import json
import re

# Загружаем .env перед импортом других модулей
try:
    from dotenv import load_dotenv

    PROJECT_ROOT = Path(__file__).parent.parent.parent
    ENV_FILE = PROJECT_ROOT / ".env"

    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=True)
except ImportError:
    pass
except Exception:
    pass

import logging
from contextlib import contextmanager
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, TypeVar, Generic
from uuid import UUID

from sqlalchemy import (
    create_engine, Column, Integer, String, Text, DateTime,
    Boolean, Float, Index, ForeignKey, event,
    text  # ← ДОБАВЛЕНО: для SQL запросов
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship, Session, scoped_session
from sqlalchemy.pool import QueuePool
from sqlalchemy.exc import (
    SQLAlchemyError,
    OperationalError,  # ← ДОБАВЛЕНО: для обработки ошибок подключения
    IntegrityError     # ← ДОБАВЛЕНО: для обработки нарушений уникальности
)
from sqlalchemy.dialects.postgresql import UUID as PG_UUID, ARRAY

from src.config.config import get_config
from src.core.exceptions import (
    handle_database_errors,
    DatabaseException,
    DatabaseConnectionError
)

logger = logging.getLogger(__name__)

Base = declarative_base()
T = TypeVar('T')

def moscow_now():
    """Возвращает текущее время в московском часовом поясе (UTC+3).

    Важно: Эта функция вызывается на стороне Python при создании объекта.
    Она отличается от server_default=func.now(), которая выполняется на стороне БД.
    """
    moscow_tz = timezone(timedelta(hours=3))
    return datetime.now(moscow_tz)

# ============================================================================
# ВАЛИДАТОРЫ ДАННЫХ
# ============================================================================

def validate_habr_article_data(title: str, content: str, url: str) -> bool:
    """
    Валидация основных полей статьи Habr.

    Args:
        title: Заголовок статьи
        content: Содержание статьи
        url: URL статьи

    Returns:
        bool: True если данные валидны, False в противном случае
    """
    if not title or not isinstance(title, str) or len(title.strip()) < 5:
        logger.error(f"[VALIDATION] Неверный заголовок: {title}")
        return False

    if not content or not isinstance(content, str) or len(content.strip()) < 50:
        logger.error(f"[VALIDATION] Неверное содержимое: {len(content) if content else 0} символов")
        return False

    if not url or not isinstance(url, str) or not url.startswith('http'):
        logger.error(f"[VALIDATION] Неверный URL: {url}")
        return False

    return True

def validate_llm_result(llm_result: Optional[Dict[str, Any]]) -> bool:
    """
    Валидация результата LLM обработки.

    Args:
        llm_result: Результат обработки от LLM

    Returns:
        bool: True если результат валиден, False в противном случае
    """
    if not llm_result:
        return True

    required_fields = ['is_news', 'relevance_score']
    for field in required_fields:
        if field not in llm_result:
            logger.error(f"[VALIDATION] Отсутствует обязательное поле в LLM результате: {field}")
            return False

    if not isinstance(llm_result['is_news'], bool):
        logger.error(f"[VALIDATION] Поле is_news должно быть bool, получено: {type(llm_result['is_news'])}")
        return False

    if not isinstance(llm_result['relevance_score'], (int, float)):
        logger.error(f"[VALIDATION] Поле relevance_score должно быть числом, получено: {type(llm_result['relevance_score'])}")
        return False

    return True

# ============================================================================
# МОДЕЛИ
# ============================================================================

class RedditPost(Base):
    """Модель поста Reddit."""
    __tablename__ = 'reddit_posts'

    id = Column(Integer, primary_key=True)
    post_id = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(Text, nullable=False)
    selftext = Column(Text)
    url = Column(String(2048))
    author = Column(String(255))
    subreddit = Column(String(255), nullable=False, index=True)
    score = Column(Integer, default=0)
    num_comments = Column(Integer, default=0)
    created_utc = Column(DateTime, nullable=False)
    scraped_at = Column(DateTime, default=moscow_now)
    qdrant_id = Column(PG_UUID(as_uuid=True), nullable=True)

    processed_post = relationship(
        "ProcessedRedditPost",
        back_populates="original_post",
        uselist=False,
        cascade="all, delete-orphan"
    )

    __table_args__ = (
        Index('idx_reddit_post_id', 'post_id'),
        Index('idx_reddit_subreddit', 'subreddit'),
        Index('idx_reddit_created', 'created_utc'),
        Index('idx_reddit_scraped', 'scraped_at'),
    )

    def __repr__(self) -> str:
        return f"<RedditPost(post_id='{self.post_id}', subreddit='{self.subreddit}')>"


class ProcessedRedditPost(Base):
    """Модель обработанного поста Reddit."""
    __tablename__ = 'processed_reddit_posts'

    id = Column(Integer, primary_key=True)
    post_id = Column(
        String(50),
        ForeignKey('reddit_posts.post_id', ondelete='CASCADE'),
        unique=True,
        nullable=False
    )
    original_title = Column(Text, nullable=False)
    original_text = Column(Text)
    subreddit = Column(String(255), nullable=False)
    author = Column(String(255))
    url = Column(String(2048))
    score = Column(Integer, default=0)
    is_news = Column(Boolean, default=False, index=True)
    original_summary = Column(Text)
    rewritten_post = Column(Text)
    title = Column(Text)
    teaser = Column(Text)
    image_prompt = Column(Text)
    processed_at = Column(DateTime, default=moscow_now)
    processing_time = Column(Integer)
    model_used = Column(String(100))

    original_post = relationship("RedditPost", back_populates="processed_post")

    __table_args__ = (
        Index('idx_processed_post_id', 'post_id'),
        Index('idx_processed_is_news', 'is_news'),
        Index('idx_processed_processed_at', 'processed_at'),
    )

    def __repr__(self) -> str:
        return f"<ProcessedRedditPost(post_id='{self.post_id}', is_news={self.is_news})>"


class TelegramMessage(Base):
    """Модель сообщения Telegram."""
    __tablename__ = 'telegram_messages'

    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, nullable=False)
    text = Column(Text)
    sender = Column(String(255))
    channel = Column(String(255), nullable=False, index=True)
    channel_username = Column(String(255))
    channel_title = Column(String(255))
    date = Column(DateTime, nullable=False)
    scraped_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    has_media = Column(Boolean, default=False)
    media_type = Column(String(100))
    views = Column(Integer, default=0)
    forwards = Column(Integer, default=0)
    replies = Column(Integer, default=0)
    qdrant_id = Column(PG_UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index('idx_telegram_message_id', 'message_id'),
        Index('idx_telegram_channel', 'channel'),
        Index('idx_telegram_date', 'date'),
    )

    def __repr__(self) -> str:
        return f"<TelegramMessage(channel='{self.channel}', message_id={self.message_id})>"


class MediumArticle(Base):
    """Модель статьи Medium."""
    __tablename__ = 'medium_articles'

    id = Column(Integer, primary_key=True)
    article_id = Column(String(100), unique=True, nullable=False, index=True)
    title = Column(Text, nullable=False)
    content = Column(Text)
    summary = Column(Text)
    author = Column(String(255))
    url = Column(String(2048))
    tag = Column(String(255))
    publication = Column(String(255))
    claps = Column(Integer, default=0)
    responses = Column(Integer, default=0)
    published_at = Column(DateTime)
    scraped_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    qdrant_id = Column(PG_UUID(as_uuid=True), nullable=True)

    __table_args__ = (
        Index('idx_medium_article_id', 'article_id'),
        Index('idx_medium_publication', 'publication'),
        Index('idx_medium_published_at', 'published_at'),
    )

    def __repr__(self) -> str:
        return f"<MediumArticle(article_id='{self.article_id}', title='{self.title[:50]}')>"


class HabrArticle(Base):
    """Модель статьи Habr."""
    __tablename__ = 'habr_articles'

    id = Column(Integer, primary_key=True)
    article_id = Column(String(50), unique=True, nullable=False, index=True)
    title = Column(Text, nullable=False)
    content = Column(Text)
    url = Column(String(2048), nullable=False)
    author = Column(String(255))
    description = Column(Text)
    categories = Column(Text)
    pub_date = Column(DateTime)
    scraped_at = Column(DateTime, default=moscow_now)
    reading_time = Column(Integer)
    views = Column(Integer)
    rating = Column(Integer)

    # Оригинальные данные
    original_title = Column(Text)
    original_content = Column(Text)

    # Обработанные данные (прямые поля без префикса)
    rewritten_post = Column(Text)
    teaser = Column(Text)
    image_prompt = Column(Text)
    is_news = Column(Boolean, default=False, index=True)
    editorial_processed = Column(Boolean, default=False)

    # Поля для короткой версии (Telegram)
    telegram_title = Column(Text)
    telegram_content = Column(Text)
    telegram_hashtags = Column(Text)
    telegram_formatted = Column(Text)
    telegram_character_count = Column(Integer)
    telegram_processed = Column(Boolean, default=False)

    # Метаданные
    language = Column(String(10), default='ru')
    word_count = Column(Integer)
    reading_time_calculated = Column(Integer)
    sentiment = Column(String(20))
    keywords = Column(Text)
    summary = Column(Text)
    difficulty_level = Column(String(20))
    relevance_score = Column(Float)
    processing_version = Column(String(20))
    last_updated = Column(
        DateTime,
        default=moscow_now,
        onupdate=moscow_now
    )

    # ID вектора
    qdrant_id = Column(PG_UUID(as_uuid=True), nullable=True)

    # Изображения в виде массива
    images = Column(ARRAY(String))

    __table_args__ = (
        Index('idx_habr_article_id', 'article_id'),
        Index('idx_habr_is_news', 'is_news'),
        Index('idx_habr_pub_date', 'pub_date'),
        Index('idx_habr_scraped_at', 'scraped_at'),
        Index('idx_habr_relevance', 'relevance_score'),
        Index('idx_habr_language', 'language'),
        Index('idx_habr_processed', 'editorial_processed'),
        Index('idx_habr_telegram_processed', 'telegram_processed'),
    )

    def __repr__(self) -> str:
        return f"<HabrArticle(article_id='{self.article_id}', title='{self.title[:50]}')>"


class TelegramPost(Base):
    """Модель готового поста для Telegram."""
    __tablename__ = 'telegram_posts'

    id = Column(Integer, primary_key=True)
    article_id = Column(
        String(50),
        ForeignKey('habr_articles.article_id', ondelete='CASCADE'),
        unique=True,
        nullable=False
    )
    content = Column(Text, nullable=False)  # Короткий контент для Telegram
    title = Column(Text, nullable=False)    # Заголовок для Telegram
    hashtags = Column(Text)                  # Хештеги через запятую
    formatted_content = Column(Text)         # Отформатированный контент с markdown
    character_count = Column(Integer)        # Количество символов
    created_at = Column(DateTime, default=moscow_now)
    published_at = Column(DateTime)          # Когда опубликован в Telegram
    telegram_message_id = Column(Integer)    # ID сообщения в Telegram
    is_published = Column(Boolean, default=False)

    # Связь с оригинальной статьей
    article = relationship("HabrArticle", backref="telegram_posts")

    __table_args__ = (
        Index('idx_telegram_post_article_id', 'article_id'),
        Index('idx_telegram_post_published', 'published_at'),
        Index('idx_telegram_post_is_published', 'is_published'),
    )

    def __repr__(self) -> str:
        return f"<TelegramPost(article_id='{self.article_id}', published={self.is_published})>"


# ============================================================================
# ДВИЖОК БАЗЫ ДАННЫХ И СЕССИЯ
# ============================================================================

_engine = None
_session_factory = None


@handle_database_errors
def get_engine():
    """Получить или создать движок SQLAlchemy с пулом соединений."""
    global _engine

    if _engine is None:
        config = get_config()

        # Приоритет: используем DATABASE_URL из окружения, если есть
        db_url = os.getenv('DATABASE_URL')

        if not db_url:
            # Fallback: собираем из компонентов
            db_url = (
                f"postgresql://{config.POSTGRES_USER}:{config.POSTGRES_PASSWORD}"
                f"@{config.POSTGRES_HOST}:{config.POSTGRES_PORT}/{config.POSTGRES_DB}"
            )

        logger.info(f"Connecting to database: {db_url.split('@')[1]}")  # Логируем без пароля

        try:
            _engine = create_engine(
                db_url,
                poolclass=QueuePool,
                pool_size=10,
                max_overflow=20,
                pool_pre_ping=True,
                pool_recycle=3600,
                echo=config.DEBUG,
                connect_args={
                    "connect_timeout": 10,
                    "options": "-c timezone=utc"
                }
            )

            # Проверка подключения
            with _engine.connect() as conn:
                conn.execute(text("SELECT 1"))

            logger.info(
                f"Database engine created successfully: {config.POSTGRES_HOST}:{config.POSTGRES_PORT}/{config.POSTGRES_DB}")

        except OperationalError as e:
            logger.error(f"Database connection failed: {e}")
            raise DatabaseConnectionError(
                f"Cannot connect to PostgreSQL at {config.POSTGRES_HOST}:{config.POSTGRES_PORT}") from e

    return _engine


@handle_database_errors
def get_session_factory():
    """Получить или создать фабрику сессий."""
    global _session_factory

    if _session_factory is None:
        engine = get_engine()
        _session_factory = scoped_session(
            sessionmaker(
                autocommit=False,
                autoflush=False,
                bind=engine
            )
        )
        logger.info("Фабрика сессий создана")

    return _session_factory


def get_session() -> Session:
    """Получить сессию базы данных."""
    factory = get_session_factory()
    return factory()


@contextmanager
def get_db_session():
    """Контекстный менеджер для сессий базы данных."""
    session = get_session()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


@handle_database_errors
def init_db():
    """Инициализировать базу данных (создать таблицы)."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    logger.info("Таблицы базы данных созданы")


# ============================================================================
# ПАТТЕРН РЕПОЗИТОРИЯ
# ============================================================================

class BaseRepository(Generic[T]):
    """
    Базовый репозиторий с общими CRUD операциями.

    ВАЖНО: Методы этого репозитория возвращают ORM-объекты, которые привязаны
    к сессии. Если сессия закрывается, доступ к "лениво" загруженным атрибутам
    вызовет DetachedInstanceError.

    Чтобы избежать этого:
    1. Используйте контекстный менеджер `with repository as repo:`.
    2. Выполняйте все операции с объектами внутри блока `with`.
    3. Или используйте методы, возвращающие словари (например, get_as_dict()),
       если они доступны в дочерних репозиториях.
    """

    def __init__(self, model_class: type, session: Optional[Session] = None):
        self.model_class = model_class
        self._session = session
        self._owns_session = session is None

    @property
    def session(self) -> Session:
        """Получить сессию (создать при необходимости)."""
        if self._session is None:
            self._session = get_session()
        return self._session

    def __enter__(self):
        """Вход в контекстный менеджер."""
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Выход из контекстного менеджера."""
        if self._owns_session and self._session:
            if exc_type is None:
                self.commit()
            else:
                self.rollback()
            self._session.close()

    @handle_database_errors
    def add(self, entity: T) -> T:
        """Добавить сущность в сессию."""
        self.session.add(entity)
        return entity

    @handle_database_errors
    def add_all(self, entities: List[T]) -> None:
        """Добавить несколько сущностей."""
        self.session.add_all(entities)

    @handle_database_errors
    def commit(self) -> None:
        """Подтвердить транзакцию."""
        self.session.commit()

    @handle_database_errors
    def rollback(self) -> None:
        """Откатить транзакцию."""
        self.session.rollback()

    @handle_database_errors
    def get_by_id(self, entity_id: int) -> Optional[T]:
        """Получить сущность по ID."""
        return self.session.query(self.model_class).get(entity_id)

    @handle_database_errors
    def get_all(self, limit: int = 100, offset: int = 0) -> List[T]:
        """Получить все сущности с пагинацией."""
        return (
            self.session.query(self.model_class)
            .limit(limit)
            .offset(offset)
            .all()
        )

    @handle_database_errors
    def count(self) -> int:
        """Подсчитать все сущности."""
        return self.session.query(self.model_class).count()

    @handle_database_errors
    def delete(self, entity: T) -> None:
        """Удалить сущность."""
        self.session.delete(entity)


class RedditPostRepository(BaseRepository[RedditPost]):
    """Репозиторий для постов Reddit."""

    def __init__(self, session: Optional[Session] = None):
        super().__init__(RedditPost, session)

    @handle_database_errors
    def get_by_post_id(self, post_id: str) -> Optional[RedditPost]:
        """Получить пост по post_id."""
        return self.session.query(RedditPost).filter_by(post_id=post_id).first()

    @handle_database_errors
    def exists(self, post_id: str) -> bool:
        """Проверить существование поста."""
        return self.session.query(
            self.session.query(RedditPost).filter_by(post_id=post_id).exists()
        ).scalar()

    @handle_database_errors
    def get_by_subreddit(
        self,
        subreddit: str,
        limit: int = 50,
        offset: int = 0
    ) -> List[RedditPost]:
        """Получить посты по сабреддиту."""
        return (
            self.session.query(RedditPost)
            .filter_by(subreddit=subreddit)
            .order_by(RedditPost.scraped_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )


class ProcessedRedditPostRepository(BaseRepository[ProcessedRedditPost]):
    """Репозиторий для обработанных постов Reddit."""

    def __init__(self, session: Optional[Session] = None):
        super().__init__(ProcessedRedditPost, session)

    @handle_database_errors
    def get_news_only(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[ProcessedRedditPost]:
        """Получить только новостные посты."""
        return (
            self.session.query(ProcessedRedditPost)
            .filter_by(is_news=True)
            .order_by(ProcessedRedditPost.processed_at.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )

    @handle_database_errors
    def is_processed(self, post_id: str) -> bool:
        """Проверить, обработан ли пост."""
        return self.session.query(
            self.session.query(ProcessedRedditPost)
            .filter_by(post_id=post_id)
            .exists()
        ).scalar()


class HabrArticleRepository(BaseRepository[HabrArticle]):
    """Репозиторий для статей Habr."""

    def __init__(self, session: Optional[Session] = None):
        super().__init__(HabrArticle, session)

    @handle_database_errors
    def get_by_article_id(self, article_id: str) -> Optional[HabrArticle]:
        """Получить статью по article_id."""
        return self.session.query(HabrArticle).filter_by(article_id=article_id).first()

    @handle_database_errors
    def get_by_article_id_as_dict(self, article_id: str) -> Optional[Dict[str, Any]]:
        """Получить статью по article_id в виде словаря (безопасно для использования вне сессии)."""
        article = self.get_by_article_id(article_id)
        if article:
            return {
                'id': article.id,
                'article_id': article.article_id,
                'title': article.title,
                'content': article.content,
                'url': article.url,
                'author': article.author,
                'pub_date': article.pub_date.isoformat() if article.pub_date else None,
                'scraped_at': article.scraped_at.isoformat() if article.scraped_at else None,
                'is_news': article.is_news,
                'editorial_processed': article.editorial_processed,
                'rewritten_post': article.rewritten_post,
                'teaser': article.teaser,
                'image_prompt': article.image_prompt,
                'telegram_title': article.telegram_title,
                'telegram_content': article.telegram_content,
                'telegram_hashtags': article.telegram_hashtags,
                'telegram_formatted': article.telegram_formatted,
                'telegram_character_count': article.telegram_character_count,
                'telegram_processed': article.telegram_processed,
                'qdrant_id': str(article.qdrant_id) if article.qdrant_id else None,
            }
        return None

    @handle_database_errors
    def exists(self, article_id: str) -> bool:
        """Проверить существование статьи."""
        return self.session.query(
            self.session.query(HabrArticle).filter_by(article_id=article_id).exists()
        ).scalar()

    @handle_database_errors
    def get_news_articles(
        self,
        limit: int = 50,
        offset: int = 0
    ) -> List[HabrArticle]:
        """Получить новостные статьи."""
        return (
            self.session.query(HabrArticle)
            .filter_by(is_news=True)
            .order_by(HabrArticle.pub_date.desc())
            .limit(limit)
            .offset(offset)
            .all()
        )


class TelegramPostRepository(BaseRepository[TelegramPost]):
    """Репозиторий для постов Telegram."""

    def __init__(self, session: Optional[Session] = None):
        super().__init__(TelegramPost, session)

    @handle_database_errors
    def get_by_article_id(self, article_id: str) -> Optional[TelegramPost]:
        """Получить пост по article_id."""
        return self.session.query(TelegramPost).filter_by(article_id=article_id).first()

    @handle_database_errors
    def get_by_article_id_as_dict(self, article_id: str) -> Optional[Dict[str, Any]]:
        """
        Получить пост по article_id в виде словаря.
        Этот метод безопасен для использования вне сессии и предотвращает DetachedInstanceError.
        """
        post = self.get_by_article_id(article_id)
        if post:
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
        return None

    @handle_database_errors
    def exists(self, article_id: str) -> bool:
        """Проверить существование поста."""
        return self.session.query(
            self.session.query(TelegramPost).filter_by(article_id=article_id).exists()
        ).scalar()

    @handle_database_errors
    def get_unpublished_posts(self, limit: int = 50) -> List[TelegramPost]:
        """Получить неопубликованные посты."""
        return (
            self.session.query(TelegramPost)
            .filter_by(is_published=False)
            .order_by(TelegramPost.created_at.desc())
            .limit(limit)
            .all()
        )

    @handle_database_errors
    def get_unpublished_posts_as_dict(self, limit: int = 50) -> List[Dict[str, Any]]:
        """
        Получить неопубликованные посты в виде списка словарей.
        Безопасно для использования вне сессии.
        """
        posts = self.get_unpublished_posts(limit)
        return [
            {
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
            } for post in posts
        ]

    @handle_database_errors
    def mark_as_published(self, post_id: int, message_id: int) -> bool:
        """Отметить пост как опубликованный."""
        post = self.get_by_id(post_id)
        if post:
            post.is_published = True
            post.published_at = moscow_now()
            post.telegram_message_id = message_id
            self.commit()
            return True
        return False


# ============================================================================
# ФУНКЦИИ ДЛЯ ОБРАТНОЙ СОВМЕСТИМОСТИ
# ============================================================================

@handle_database_errors
def save_reddit_post(post_data: Dict[str, Any]) -> bool:
    """Сохранить пост Reddit (устаревшая функция)."""
    with RedditPostRepository() as repo:
        if repo.exists(post_data['post_id']):
            logger.debug(f"Пост Reddit уже существует: {post_data['post_id']}")
            return False

        post = RedditPost(**post_data)
        repo.add(post)
        repo.commit()
        logger.debug(f"Пост Reddit сохранен: {post.post_id}")
        return True


@handle_database_errors
def save_habr_article(
        url: str,
        title: str,
        content: str,
        author: Optional[str] = None,
        published_at: Optional[datetime] = None,
        images: Optional[List[str]] = None,
        tags: Optional[List[str]] = None,
        enable_llm: bool = True,
        **kwargs
) -> bool:
    """
    Сохранить статью Habr с опциональной LLM обработкой.

    Args:
        url: URL статьи
        title: Заголовок статьи
        content: Содержание статьи
        author: Автор статьи
        published_at: Дата публикации
        images: Список изображений
        tags: Теги статьи
        enable_llm: Включить LLM обработку
        **kwargs: Дополнительные поля для сохранения:
            - is_news: bool - является ли статья новостью
            - relevance_score: float - оценка релевантности
            - rewritten_post: str - переписанный текст
            - teaser: str - краткая аннотация
            - image_prompt: str - промпт для генерации изображения
            - original_summary: str - оригинальное резюме
            - content_type: str - тип контента
            - editorial_processed: bool - флаг обработки
            - telegram_title: str - заголовок для Telegram
            - telegram_content: str - контент для Telegram
            - telegram_hashtags: str - хештеги для Telegram
            - telegram_formatted: str - отформатированный контент для Telegram
            - telegram_character_count: int - количество символов для Telegram
            - telegram_processed: bool - флаг обработки для Telegram
            - language: str - язык статьи
            - word_count: int - количество слов
            - reading_time_calculated: int - расчетное время чтения
            - sentiment: str - тональность
            - keywords: str - ключевые слова
            - summary: str - краткое содержание
            - difficulty_level: str - уровень сложности
            - processing_version: str - версия обработки
            - qdrant_id: UUID - ID вектора в Qdrant

    Returns:
        bool: True если статья успешно сохранена, False в противном случае
    """
    import re
    import json

    # Валидация входных данных
    if not validate_habr_article_data(title, content, url):
        logger.error("[DB] Валидация входных данных не пройдена")
        return False

    # FORCE LLM PROCESSING FOR HABR - ALWAYS ENABLED
    enable_llm = True

    logger.info(f"[DB] Начало сохранения статьи Habr: {title[:50]}...")
    logger.debug(f"[DB] URL: {url}")
    logger.debug(f"[DB] Автор: {author}")
    logger.debug(f"[DB] Дата публикации: {published_at}")
    logger.debug(f"[DB] Длина контента: {len(content)} символов")
    logger.info(f"[DB] LLM обработка: {'ВКЛЮЧЕНА' if enable_llm else 'ВЫКЛЮЧЕНА'}")

    # Извлечение article_id из URL
    match = re.search(r'/(?:articles|post)/(\d+)', url)
    if not match:
        logger.error(f"[DB] Не удалось извлечь article_id из URL: {url}")
        return False

    article_id = match.group(1)
    logger.debug(f"[DB] Извлечен article_id: {article_id}")

    # ПРОВЕРКА НАЛИЧИЯ ДАННЫХ LLM В KWARGS
    llm_result = None
    if any(key in kwargs for key in ['title', 'teaser', 'rewritten_post', 'image_prompt']):
        logger.info("[DB] Обнаружены обработанные данные в kwargs")
        llm_result = {
            'is_news': kwargs.get('is_news', True),
            'title': kwargs.get('title'),
            'teaser': kwargs.get('teaser'),
            'rewritten_post': kwargs.get('rewritten_post'),
            'image_prompt': kwargs.get('image_prompt'),
            'relevance_score': kwargs.get('relevance_score', 0.8),
            'original_summary': kwargs.get('original_summary'),
            'content_type': kwargs.get('content_type'),
            'editorial_processed': True
        }
        logger.debug(f"[DB] Данные LLM из kwargs: {llm_result}")

    # LLM обработка если включена и нет данных в kwargs
    if enable_llm and not llm_result:
        logger.info(f"[DB] Запуск LLM обработки для статьи: {article_id}")
        try:
            from src.services.editorial_service import get_editorial_service
            editorial = get_editorial_service()

            llm_result = editorial.process_post(
                title=title,
                content=content,
                source="habr",
                default_relevant=True  # ← КРИТИЧНО для Habr!
            )

            logger.debug(f"[DB] Результат LLM обработки: {llm_result}")

            # Проверка, что rewritten_post отличается от оригинала
            if llm_result.get('rewritten_post'):
                original_len = len(content)
                rewritten_len = len(llm_result['rewritten_post'])
                similarity = 1.0 - abs(original_len - rewritten_len) / max(original_len, rewritten_len, 1)

                logger.info(f"[DB] Длина оригинала: {original_len} символов")
                logger.info(f"[DB] Длина обработанного: {rewritten_len} символов")
                logger.info(f"[DB] Сходство по длине: {similarity:.2f}")

                if similarity > 0.9:  # Если тексты очень похожи по длине
                    logger.warning("[DB] Обработанный текст слишком похож на оригинал!")

                # Логирование начала обработанного текста
                logger.info(f"[DB] Начало обработанного текста: {llm_result['rewritten_post'][:500]}...")

            if llm_result.get('error'):
                logger.error(f"[DB] Ошибка LLM: {llm_result['error']}")
                # Продолжаем сохранение даже при ошибке LLM
                llm_result = {
                    'is_news': False,
                    'relevance_score': 0.0,
                    'editorial_processed': True,  # ← Mark as processed even with error
                    'telegram_processed': True
                }
        except ImportError:
            logger.warning("[DB] Editorial service недоступен")
        except Exception as e:
            logger.error(f"[DB] Ошибка LLM обработки: {e}")
            logger.exception("[DB] Stack trace:")
            # Продолжаем сохранение без LLM обработки
            llm_result = {
                'is_news': False,
                'relevance_score': 0.0,
                'editorial_processed': False,  # ← Not processed if exception
                'telegram_processed': False
            }
    else:
        logger.info("[DB] LLM обработка отключена или данные уже обработаны")

    # Валидация LLM результата
    if not validate_llm_result(llm_result):
        logger.error("[DB] Валидация LLM результата не пройдена")
        return False

    # Основная транзакция базы данных
    session = get_session()
    article = None
    try:
        # Проверка существования
        repo = HabrArticleRepository(session)
        if repo.exists(article_id):
            logger.info(f"[DB] Статья Habr уже существует: {article_id}")
            return False

        # Базовые данные статьи
        article_data = {
            'article_id': article_id,
            'url': url,
            'title': title,
            'content': content,
            'author': author,
            'pub_date': published_at,
            'original_title': title,
            'original_content': content,
            'categories': ','.join(tags) if tags else None,
            'images': images,  # ИСПРАВЛЕНО: сохраняем изображения как массив
            'word_count': len(content.split()),
            'reading_time_calculated': max(1, len(content.split()) // 200),
            'language': 'ru',
            'editorial_processed': False,  # ← Default to False, will be updated if LLM succeeds
            'telegram_processed': False,
        }

        # Добавление полей из kwargs
        allowed_fields = {
            'description', 'pub_date', 'scraped_at', 'reading_time', 'views', 'rating',
            'original_title', 'original_content', 'rewritten_post', 'teaser',
            'image_prompt', 'is_news', 'editorial_processed',
            'telegram_title', 'telegram_content', 'telegram_hashtags', 'telegram_formatted',
            'telegram_character_count', 'telegram_processed', 'language', 'word_count',
            'reading_time_calculated', 'sentiment', 'keywords', 'summary',
            'difficulty_level', 'relevance_score', 'processing_version', 'last_updated',
            'qdrant_id', 'images', 'original_summary', 'content_type'
        }

        # Обрабатываем kwargs - используем поля напрямую без маппинга
        for key, value in kwargs.items():
            if key in allowed_fields:
                article_data[key] = value
                logger.debug(f"[DB] Добавлено поле из kwargs: {key}={str(value)[:50]}")
            # Логируем неизвестные поля для отладки
            else:
                logger.debug(f"[DB] Пропущен неизвестный kwarg: {key}={str(value)[:50]}")

        # Добавляем поля из LLM результата - используем поля напрямую
        if llm_result:
            # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Маппинг полей от LLM к полям БД
            if 'summary' in llm_result and llm_result['summary']:
                article_data['summary'] = llm_result['summary']
                logger.debug(f"[DB] Добавлено поле summary из LLM: {llm_result['summary'][:50]}")

            # Если есть rewritten_post в результате LLM, используем его
            if 'rewritten_post' in llm_result and llm_result['rewritten_post']:
                article_data['rewritten_post'] = llm_result['rewritten_post']
                logger.debug(f"[DB] Добавлено поле rewritten_post из LLM: {llm_result['rewritten_post'][:50]}")
            # Иначе пытаемся сгенерировать rewritten_post из других полей
            elif 'summary' in llm_result and llm_result['summary']:
                # Используем summary как основу для rewritten_post
                article_data['rewritten_post'] = llm_result['summary']
                logger.info(f"[DB] Создан rewritten_post из summary: {llm_result['summary'][:50]}")

            # Если есть teaser в результате LLM, используем его
            if 'teaser' in llm_result and llm_result['teaser']:
                article_data['teaser'] = llm_result['teaser']
                logger.debug(f"[DB] Добавлено поле teaser из LLM: {llm_result['teaser'][:50]}")
            # Иначе пытаемся создать teaser из summary
            elif 'summary' in llm_result and llm_result['summary']:
                # Создаем teaser из первых 200 символов summary
                article_data['teaser'] = llm_result['summary'][:200] + "..." if len(llm_result['summary']) > 200 else llm_result['summary']
                logger.info(f"[DB] Создан teaser из summary: {article_data['teaser'][:50]}...")

            # Если есть image_prompt в результате LLM, используем его
            if 'image_prompt' in llm_result and llm_result['image_prompt']:
                article_data['image_prompt'] = llm_result['image_prompt']
                logger.debug(f"[DB] Добавлено поле image_prompt из LLM: {llm_result['image_prompt'][:50]}")
            # Иначе создаем image_prompt на основе заголовка
            else:
                article_data['image_prompt'] = f"Технологическая иллюстрация для статьи: {title[:100]}"
                logger.info(f"[DB] Создан image_prompt по умолчанию: {article_data['image_prompt'][:50]}")

            # Добавляем остальные поля
            for key, value in llm_result.items():
                if key in allowed_fields and key not in ['summary', 'rewritten_post', 'teaser', 'image_prompt'] and value is not None:
                    article_data[key] = value
                    logger.debug(f"[DB] Добавлено поле из LLM: {key}={str(value)[:50]}")

            # Всегда помечаем как обработанное, если был LLM вызов
            article_data['editorial_processed'] = True
            logger.info(f"[DB] Добавлены поля из LLM: {[k for k in llm_result.keys() if k in allowed_fields]}")

            # Дополнительная обработка для Telegram
            if llm_result.get('is_news') and (llm_result.get('rewritten_post') or llm_result.get('summary')):
                logger.info(f"[DB] Запуск форматирования для Telegram: {article_id}")
                try:
                    from src.services.editorial_service import get_editorial_service
                    editorial = get_editorial_service()

                    # Используем rewritten_post или summary для форматирования
                    content_for_telegram = llm_result.get('rewritten_post') or llm_result.get('summary') or content
                    title_for_telegram = llm_result.get('title') or title

                    telegram_result = editorial.format_for_telegram(
                        title=title_for_telegram,
                        content=content_for_telegram
                    )

                    if not telegram_result.get('error'):
                        article_data['telegram_title'] = telegram_result.get('telegram_title')
                        article_data['telegram_content'] = telegram_result.get('telegram_content')
                        article_data['telegram_hashtags'] = telegram_result.get('telegram_hashtags')
                        article_data['telegram_formatted'] = telegram_result.get('telegram_formatted')
                        article_data['telegram_character_count'] = telegram_result.get('character_count')
                        article_data['telegram_processed'] = True
                        logger.info(
                            f"[DB] ✓ Telegram форматирование завершено: {telegram_result.get('character_count')} символов")
                    else:
                        logger.error(f"[DB] Ошибка форматирования Telegram: {telegram_result.get('error')}")
                except Exception as e:
                    logger.error(f"[DB] Ошибка форматирования Telegram: {e}")

        logger.debug(f"[DB] Подготовлены данные статьи: {len(article_data)} полей")

        # ДИАГНОСТИКА: Проверяем что попало в article_data
        logger.info("=" * 80)
        logger.info("ДИАГНОСТИКА В save_habr_article: article_data содержит:")
        logger.info(f"  original_title: {article_data.get('original_title', 'ОТСУТСТВУЕТ')[:100]}")
        logger.info(f"  title: {article_data.get('title', 'ОТСУТСТВУЕТ')[:100] if article_data.get('title') else 'NONE'}")
        logger.info(f"  original_content: {len(article_data.get('original_content', ''))} символов")
        logger.info(f"  rewritten_post: {len(article_data.get('rewritten_post', '')) if article_data.get('rewritten_post') else 0} символов")
        logger.info(f"  teaser: {'ДА (' + str(len(article_data.get('teaser', ''))) + ' сим.)' if article_data.get('teaser') else 'NONE'}")
        logger.info(f"  image_prompt: {'ДА (' + str(len(article_data.get('image_prompt', ''))) + ' сим.)' if article_data.get('image_prompt') else 'NONE'}")
        logger.info(f"  relevance_score: {article_data.get('relevance_score', 'NONE')}")
        logger.info(f"  is_news: {article_data.get('is_news', 'NONE')}")
        logger.info(f"  editorial_processed: {article_data.get('editorial_processed', 'NONE')}")

        # Сравнение контента
        if article_data.get('original_content') and article_data.get('rewritten_post'):
            if article_data['original_content'] == article_data['rewritten_post']:
                logger.warning("  ⚠️ Оригинальный и обработанный контент ИДЕНТИЧНЫ!")
            else:
                logger.info("  ✓ Оригинальный и обработанный контент РАЗЛИЧАЮТСЯ")
                # Показываем начало обоих текстов для сравнения
                logger.info(f"  Оригинал (начало): {article_data['original_content'][:200]}...")
                logger.info(f"  Обработанный (начало): {article_data['rewritten_post'][:200]}...")

        logger.info("=" * 80)

        # Создание и сохранение статьи
        try:
            logger.debug(f"[DB] Создание объекта статьи...")
            filtered_article_data = {k: v for k, v in article_data.items() if hasattr(HabrArticle, k)}
            article = HabrArticle(**filtered_article_data)

            logger.debug(f"[DB] Добавление статьи в сессию...")
            session.add(article)
            session.flush()  # Получаем ID без коммита транзакции

            logger.info(f"[DB] ✓ Статья Habr добавлена в сессию: {article_id} - {title[:50]}...")

            # Сохранение в Qdrant и обновление записи в БД в той же транзакции
            try:
                from src.services.deduplication_service import get_deduplication_service
                dedup = get_deduplication_service()

                # Check if Qdrant is connected
                if dedup.is_connected():
                    metadata = {
                        'article_id': article_id,
                        'title': title,
                        'url': url,
                        'author': author,
                        'source': 'habr',
                        'pub_date': published_at.isoformat() if published_at else None,
                    }

                    qdrant_text = f"{title}\n\n{content}"
                    qdrant_id = dedup.save_to_qdrant(
                        text=qdrant_text,
                        record_id=article_id,
                        metadata=metadata,
                        source="habr"
                    )

                    # Обновляем qdrant_id в рамках той же сессии
                    if qdrant_id:
                        article.qdrant_id = qdrant_id
                        logger.debug(f"[DB] Embedding сохранен в Qdrant: {qdrant_id}")
                else:
                    logger.warning("[DB] Qdrant недоступен, пропускаем сохранение вектора")

            except ImportError:
                logger.debug("[DB] Deduplication service недоступен")
            except Exception as e:
                logger.warning(f"[DB] Ошибка сохранения в Qdrant: {e}")

            # Создание записи в TelegramPost если есть контент
            if article_data.get('telegram_content'):
                try:
                    telegram_post = TelegramPost(
                        article_id=article_id,
                        content=article_data['telegram_content'],
                        title=article_data['telegram_title'],
                        hashtags=article_data['telegram_hashtags'],
                        formatted_content=article_data['telegram_formatted'],
                        character_count=article_data['telegram_character_count']
                    )
                    session.add(telegram_post)
                    logger.info(f"[DB] Telegram пост создан для статьи: {article_id}")
                except Exception as e:
                    logger.error(f"[DB] Ошибка создания Telegram поста: {e}")
                    logger.exception("[DB] Stack trace:")

            # Финальный коммит всей транзакции
            session.commit()
            logger.info(f"[DB] ✓ Транзакция успешно завершена для статьи: {article_id}")

            # Проверяем, что статья действительно сохранена
            saved_article = repo.get_by_article_id(article_id)
            if saved_article:
                logger.info(f"[DB] ✓ Проверка: статья {article_id} найдена в БД с ID {saved_article.id}")

                # ДОПОЛНИТЕЛЬНАЯ ПРОВЕРКА: Убедимся, что обработанные данные сохранены
                if saved_article.editorial_processed:
                    logger.info(f"[DB] ✓ Проверка: статья {article_id} обработана (editorial_processed=True)")
                else:
                    logger.warning(f"[DB] ✗ Проверка: статья {article_id} не обработана (editorial_processed=False)")

                if saved_article.rewritten_post:
                    logger.info(f"[DB] ✓ Проверка: rewritten_post сохранен ({len(saved_article.rewritten_post)} символов)")

                    # Проверка, что сохраненный контент отличается от оригинала
                    if saved_article.original_content == saved_article.rewritten_post:
                        logger.warning(f"[DB] ✗ Проверка: сохраненный rewritten_post ИДЕНТИЧЕН original_content!")
                    else:
                        logger.info(f"[DB] ✓ Проверка: сохраненный rewritten_post ОТЛИЧАЕТСЯ от original_content")
                        # Показываем начало обоих текстов для сравнения
                        logger.info(f"[DB] Оригинал (начало): {saved_article.original_content[:200]}...")
                        logger.info(f"[DB] Обработанный (начало): {saved_article.rewritten_post[:200]}...")
                else:
                    logger.warning(f"[DB] ✗ Проверка: rewritten_post отсутствует")

                if saved_article.teaser:
                    logger.info(f"[DB] ✓ Проверка: teaser сохранен ({len(saved_article.teaser)} символов)")
                else:
                    logger.warning(f"[DB] ✗ Проверка: teaser отсутствует")

                if saved_article.image_prompt:
                    logger.info(f"[DB] ✓ Проверка: image_prompt сохранен ({len(saved_article.image_prompt)} символов)")
                else:
                    logger.warning(f"[DB] ✗ Проверка: image_prompt отсутствует")

                return True
            else:
                logger.error(f"[DB] ✗ Ошибка: статья {article_id} не найдена в БД после сохранения")
                return False

        except IntegrityError as e:
            logger.warning(f"[DB] Статья уже существует: {article_id}")
            session.rollback()
            return False
        except Exception as e:
            logger.error(f"[DB] Ошибка сохранения статьи {article_id}: {e}")
            logger.exception("[DB] Stack trace:")
            session.rollback()
            raise

    except Exception as e:
        logger.error(f"[DB] Критическая ошибка при сохранении статьи: {e}")
        logger.exception("[DB] Stack trace:")
        session.rollback()
        return False
    finally:
        if session:
            session.close()


@handle_database_errors
def check_database_connection() -> Dict[str, Any]:
    """
    Проверяет состояние подключения к базе данных.

    Returns:
        Словарь с информацией о состоянии подключения
    """
    try:
        with get_db_session() as session:
            result = session.execute(text("SELECT 1 as test"))
            row = result.fetchone()

            if row and row[0] == 1:
                # Проверяем наличие таблиц
                tables = session.execute(text("""
                    SELECT table_name FROM information_schema.tables 
                    WHERE table_schema = 'public'
                """)).fetchall()

                table_names = [table[0] for table in tables]

                # Проверяем количество записей в основных таблицах
                stats = {}
                for table in ['reddit_posts', 'habr_articles', 'telegram_posts']:
                    if table in table_names:
                        count = session.execute(text(f"SELECT COUNT(*) FROM {table}")).fetchone()[0]
                        stats[table] = count

                return {
                    'status': 'connected',
                    'tables': table_names,
                    'stats': stats
                }
            else:
                return {'status': 'error', 'message': 'Тестовый запрос не вернул ожидаемый результат'}
    except Exception as e:
        logger.error(f"Ошибка проверки подключения к БД: {e}")
        return {'status': 'error', 'message': str(e)}


@handle_database_errors
def get_stats_extended() -> Dict[str, Any]:
    """Получить расширенную статистику (устаревшая функция)."""
    with get_db_session() as session:
        # Get counts
        reddit_posts = session.query(RedditPost).count()
        telegram_messages = session.query(TelegramMessage).count()
        medium_articles = session.query(MediumArticle).count()
        habr_articles = session.query(HabrArticle).count()
        telegram_posts = session.query(TelegramPost).count()

        # Get latest records with only fields we need
        latest_reddit = session.query(
            RedditPost.title,
            RedditPost.scraped_at,
            RedditPost.url
        ).order_by(RedditPost.scraped_at.desc()).first()

        latest_telegram = session.query(
            TelegramMessage.date,
            TelegramMessage.scraped_at
        ).order_by(TelegramMessage.scraped_at.desc()).first()

        latest_medium = session.query(
            MediumArticle.title,
            MediumArticle.scraped_at,
            MediumArticle.url
        ).order_by(MediumArticle.scraped_at.desc()).first()

        latest_habr = session.query(
            HabrArticle.title,
            HabrArticle.scraped_at,
            HabrArticle.url
        ).order_by(HabrArticle.scraped_at.desc()).first()

        latest_telegram_post = session.query(
            TelegramPost.created_at
        ).order_by(TelegramPost.created_at.desc()).first()

        # Convert to dictionaries to avoid session issues
        result = {
            'reddit_posts': reddit_posts,
            'telegram_messages': telegram_messages,
            'medium_articles': medium_articles,
            'habr_articles': habr_articles,
            'telegram_posts': telegram_posts,
            'latest_reddit': {
                'title': latest_reddit.title if latest_reddit else '',
                'scraped_at': latest_reddit.scraped_at.isoformat() if latest_reddit and latest_reddit.scraped_at else '',
                'url': latest_reddit.url if latest_reddit else ''
            },
            'latest_telegram': {
                'date': latest_telegram.date.isoformat() if latest_telegram and latest_telegram.date else '',
                'scraped_at': latest_telegram.scraped_at.isoformat() if latest_telegram and latest_telegram.scraped_at else ''
            },
            'latest_medium': {
                'title': latest_medium.title if latest_medium else '',
                'scraped_at': latest_medium.scraped_at.isoformat() if latest_medium and latest_medium.scraped_at else '',
                'url': latest_medium.url if latest_medium else ''
            },
            'latest_habr': {
                'title': latest_habr.title if latest_habr else '',
                'scraped_at': latest_habr.scraped_at.isoformat() if latest_habr and latest_habr.scraped_at else '',
                'url': latest_habr.url if latest_habr else ''
            },
            'latest_telegram_post': {
                'created_at': latest_telegram_post.created_at.isoformat() if latest_telegram_post and latest_telegram_post.created_at else ''
            }
        }

        return result


# ============================================================================
# ЭКСПОРТ
# ============================================================================

@handle_database_errors
def get_processing_statistics() -> Dict[str, Any]:
    """
    Получить статистику обработки постов.

    Returns:
        Словарь со статистикой:
        {
            'total_raw': int,           # Всего сырых постов
            'total_processed': int,      # Всего обработанных
            'total_news': int,           # Из них новостей
            'processing_rate': float,    # Процент обработки
            'news_rate': float,          # Процент новостей
            'reddit_raw': int,
            'reddit_processed': int,
            'reddit_news': int,
            'habr_total': int,
            'habr_processed': int,
            'habr_news': int,
            'telegram_posts': int,
            'telegram_published': int
        }
    """
    with get_db_session() as session:
        # Reddit статистика
        reddit_raw = session.query(RedditPost).count()
        reddit_processed = session.query(ProcessedRedditPost).count()
        reddit_news = session.query(ProcessedRedditPost).filter_by(is_news=True).count()

        # Habr статистика
        habr_total = session.query(HabrArticle).count()
        habr_processed = session.query(HabrArticle).filter_by(editorial_processed=True).count()
        habr_news = session.query(HabrArticle).filter_by(is_news=True).count()

        # Telegram статистика
        telegram_total = session.query(TelegramPost).count()
        telegram_published = session.query(TelegramPost).filter_by(is_published=True).count()

        # Общая статистика
        total_raw = reddit_raw + habr_total
        total_processed = reddit_processed + habr_processed
        total_news = reddit_news + habr_news

        # Процентные показатели
        processing_rate = (total_processed / total_raw * 100) if total_raw > 0 else 0.0
        news_rate = (total_news / total_processed * 100) if total_processed > 0 else 0.0
        telegram_publish_rate = (telegram_published / telegram_total * 100) if telegram_total > 0 else 0.0

        return {
            'total_raw': total_raw,
            'total_processed': total_processed,
            'total_news': total_news,
            'processing_rate': processing_rate,
            'news_rate': news_rate,
            'reddit_raw': reddit_raw,
            'reddit_processed': reddit_processed,
            'reddit_news': reddit_news,
            'habr_total': habr_total,
            'habr_processed': habr_processed,
            'habr_news': habr_news,
            'telegram_posts': telegram_total,
            'telegram_published': telegram_published,
            'telegram_publish_rate': telegram_publish_rate
        }

__all__ = [
    # Модели
    'Base',
    'RedditPost',
    'ProcessedRedditPost',
    'TelegramMessage',
    'MediumArticle',
    'HabrArticle',
    'TelegramPost',

    # Управление базой данных
    'init_db',
    'get_engine',
    'get_session',
    'get_db_session',
    'get_session_factory',

    # Репозитории
    'BaseRepository',
    'RedditPostRepository',
    'ProcessedRedditPostRepository',
    'HabrArticleRepository',
    'TelegramPostRepository',

    # Устаревшие функции
    'save_reddit_post',
    'save_habr_article',
    'get_stats_extended',
    'get_processing_statistics',
    'check_database_connection',
]