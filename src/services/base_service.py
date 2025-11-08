# src/services/base_service.py
"""
Service Layer - бизнес-логика приложения.
Следует принципам SOLID и отделяет бизнес-логику от UI и данных.
"""

import logging
from abc import ABC, abstractmethod
from typing import Optional, List, Dict, Any, TypeVar, Generic
from dataclasses import dataclass
from datetime import datetime, timezone
from uuid import UUID

from src.models.database import (
    get_db_session,
    RedditPost,
    ProcessedRedditPost,
    HabrArticle,
    RedditPostRepository,
    ProcessedRedditPostRepository,
    HabrArticleRepository
)

logger = logging.getLogger(__name__)

T = TypeVar('T')


# ============================================================================
# DATA TRANSFER OBJECTS (DTOs)
# ============================================================================

@dataclass
class RedditPostDTO:
    """DTO для Reddit поста."""
    post_id: str
    title: str
    selftext: Optional[str]
    url: Optional[str]
    author: str
    subreddit: str
    score: int
    num_comments: int
    created_utc: datetime
    scraped_at: datetime
    qdrant_id: Optional[UUID] = None

    @classmethod
    def from_entity(cls, entity: RedditPost) -> 'RedditPostDTO':
        """Создать DTO из entity."""
        return cls(
            post_id=entity.post_id,
            title=entity.title,
            selftext=entity.selftext,
            url=entity.url,
            author=entity.author,
            subreddit=entity.subreddit,
            score=entity.score,
            num_comments=entity.num_comments,
            created_utc=entity.created_utc,
            scraped_at=entity.scraped_at,
            qdrant_id=entity.qdrant_id
        )

    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь."""
        return {
            'post_id': self.post_id,
            'title': self.title,
            'selftext': self.selftext,
            'url': self.url,
            'author': self.author,
            'subreddit': self.subreddit,
            'score': self.score,
            'num_comments': self.num_comments,
            'created_utc': self.created_utc.isoformat(),
            'scraped_at': self.scraped_at.isoformat(),
            'qdrant_id': str(self.qdrant_id) if self.qdrant_id else None
        }


@dataclass
class ProcessedPostDTO:
    """DTO для обработанного поста."""
    post_id: str
    original_title: str
    original_text: Optional[str]
    subreddit: str
    author: str
    score: int
    is_news: bool
    editorial_title: Optional[str]
    teaser: Optional[str]
    rewritten_post: Optional[str]
    image_prompt: Optional[str]
    processed_at: datetime
    processing_time: int
    model_used: str

    @classmethod
    def from_entity(cls, entity: ProcessedRedditPost) -> 'ProcessedPostDTO':
        """Создать DTO из entity."""
        return cls(
            post_id=entity.post_id,
            original_title=entity.original_title,
            original_text=entity.original_text,
            subreddit=entity.subreddit,
            author=entity.author,
            score=entity.score,
            is_news=entity.is_news,
            editorial_title=entity.editorial_title,
            teaser=entity.teaser,
            rewritten_post=entity.rewritten_post,
            image_prompt=entity.image_prompt,
            processed_at=entity.processed_at,
            processing_time=entity.processing_time,
            model_used=entity.model_used
        )


@dataclass
class HabrArticleDTO:
    """DTO для статьи Habr."""
    article_id: str
    title: str
    content: str
    url: str
    author: Optional[str]
    pub_date: Optional[datetime]
    scraped_at: datetime
    is_news: bool
    editorial_processed: bool
    editorial_title: Optional[str] = None
    editorial_teaser: Optional[str] = None
    editorial_rewritten: Optional[str] = None
    rating: Optional[int] = None
    views: Optional[int] = None

    @classmethod
    def from_entity(cls, entity: HabrArticle) -> 'HabrArticleDTO':
        """Создать DTO из entity."""
        return cls(
            article_id=entity.article_id,
            title=entity.title,
            content=entity.content,
            url=entity.url,
            author=entity.author,
            pub_date=entity.pub_date,
            scraped_at=entity.scraped_at,
            is_news=entity.is_news,
            editorial_processed=entity.editorial_processed,
            editorial_title=entity.editorial_title,
            editorial_teaser=entity.editorial_teaser,
            editorial_rewritten=entity.editorial_rewritten,
            rating=entity.rating,
            views=entity.views
        )


@dataclass
class ParsingResult:
    """Результат парсинга."""
    success: bool
    saved: int = 0
    skipped: int = 0
    errors: int = 0
    semantic_duplicates: int = 0
    editorial_processed: int = 0
    error_message: Optional[str] = None
    details: Optional[Dict[str, Any]] = None


@dataclass
class StatisticsDTO:
    """DTO для статистики."""
    reddit_posts: int
    reddit_processed: int
    reddit_news: int
    habr_articles: int
    habr_news: int
    habr_processed: int
    telegram_messages: int
    medium_articles: int
    processing_rate: float
    news_rate: float


# ============================================================================
# BASE SERVICE
# ============================================================================

class BaseService(ABC, Generic[T]):
    """
    Базовый сервис для бизнес-логики.
    Предоставляет общие методы для работы с репозиториями.
    """

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)

    @abstractmethod
    def get_repository(self, session=None):
        """Получить репозиторий для работы с данными."""
        pass

    def validate_data(self, data: Dict[str, Any], required_fields: List[str]) -> bool:
        """
        Валидация входных данных.

        Args:
            data: Данные для валидации
            required_fields: Список обязательных полей

        Returns:
            True если валидация прошла успешно
        """
        missing_fields = [field for field in required_fields if not data.get(field)]
        if missing_fields:
            self.logger.error(f"Missing required fields: {missing_fields}")
            return False
        return True


# ============================================================================
# REDDIT SERVICE
# ============================================================================

class RedditService(BaseService[RedditPost]):
    """Сервис для работы с Reddit постами."""

    def get_repository(self, session=None):
        """Получить репозиторий Reddit."""
        return RedditPostRepository(session)

    def save_post(self, post_data: Dict[str, Any]) -> bool:
        """
        Сохранить пост Reddit.

        Args:
            post_data: Данные поста

        Returns:
            True если пост сохранен успешно
        """
        required_fields = ['post_id', 'title', 'subreddit', 'author', 'created_utc']
        if not self.validate_data(post_data, required_fields):
            return False

        try:
            with self.get_repository() as repo:
                # Проверка дубликатов
                if repo.exists(post_data['post_id']):
                    self.logger.debug(f"Post already exists: {post_data['post_id']}")
                    return False

                # Нормализация даты
                if isinstance(post_data.get('created_utc'), str):
                    post_data['created_utc'] = datetime.fromisoformat(
                        post_data['created_utc'].replace('Z', '+00:00')
                    )

                post = RedditPost(**post_data)
                repo.add(post)
                repo.commit()

                self.logger.info(f"Reddit post saved: {post.post_id}")
                return True

        except Exception as e:
            self.logger.error(f"Failed to save Reddit post: {e}", exc_info=True)
            return False

    def get_posts_by_subreddit(
            self,
            subreddit: str,
            limit: int = 50,
            offset: int = 0
    ) -> List[RedditPostDTO]:
        """
        Получить посты из конкретного subreddit.

        Args:
            subreddit: Название subreddit
            limit: Количество постов
            offset: Смещение

        Returns:
            Список DTO постов
        """
        try:
            with self.get_repository() as repo:
                posts = repo.get_by_subreddit(subreddit, limit, offset)
                return [RedditPostDTO.from_entity(post) for post in posts]
        except Exception as e:
            self.logger.error(f"Failed to get posts by subreddit: {e}", exc_info=True)
            return []

    def get_unprocessed_posts(self, limit: int = 100) -> List[RedditPostDTO]:
        """
        Получить необработанные посты.

        Args:
            limit: Максимальное количество постов

        Returns:
            Список необработанных постов
        """
        try:
            with ProcessedRedditPostRepository() as repo:
                posts = repo.get_unprocessed_posts(limit)
                return [RedditPostDTO.from_entity(post) for post in posts]
        except Exception as e:
            self.logger.error(f"Failed to get unprocessed posts: {e}", exc_info=True)
            return []

    def post_exists(self, post_id: str) -> bool:
        """Проверить существование поста."""
        try:
            with self.get_repository() as repo:
                return repo.exists(post_id)
        except Exception as e:
            self.logger.error(f"Failed to check post existence: {e}", exc_info=True)
            return False


# ============================================================================
# PROCESSED REDDIT SERVICE
# ============================================================================

class ProcessedRedditService(BaseService[ProcessedRedditPost]):
    """Сервис для работы с обработанными постами Reddit."""

    def get_repository(self, session=None):
        """Получить репозиторий обработанных постов."""
        return ProcessedRedditPostRepository(session)

    def save_processed_post(self, post_data: Dict[str, Any]) -> bool:
        """
        Сохранить обработанный пост.

        Args:
            post_data: Данные обработанного поста

        Returns:
            True если пост сохранен успешно
        """
        required_fields = ['post_id', 'original_title', 'subreddit', 'author', 'is_news']
        if not self.validate_data(post_data, required_fields):
            return False

        try:
            with self.get_repository() as repo:
                # Проверка дубликатов
                if repo.is_processed(post_data['post_id']):
                    self.logger.debug(f"Post already processed: {post_data['post_id']}")
                    return False

                # Установка времени обработки
                if 'processed_at' not in post_data:
                    post_data['processed_at'] = datetime.now(timezone.utc)

                post = ProcessedRedditPost(**post_data)
                repo.add(post)
                repo.commit()

                self.logger.info(f"Processed post saved: {post.post_id}")
                return True

        except Exception as e:
            self.logger.error(f"Failed to save processed post: {e}", exc_info=True)
            return False

    def get_news_posts(
            self,
            limit: int = 50,
            offset: int = 0
    ) -> List[ProcessedPostDTO]:
        """
        Получить только новостные посты.

        Args:
            limit: Количество постов
            offset: Смещение

        Returns:
            Список новостных постов
        """
        try:
            with self.get_repository() as repo:
                posts = repo.get_news_only(limit, offset)
                return [ProcessedPostDTO.from_entity(post) for post in posts]
        except Exception as e:
            self.logger.error(f"Failed to get news posts: {e}", exc_info=True)
            return []

    def is_processed(self, post_id: str) -> bool:
        """Проверить, обработан ли пост."""
        try:
            with self.get_repository() as repo:
                return repo.is_processed(post_id)
        except Exception as e:
            self.logger.error(f"Failed to check if post is processed: {e}", exc_info=True)
            return False


# ============================================================================
# HABR SERVICE
# ============================================================================

class HabrService(BaseService[HabrArticle]):
    """Сервис для работы со статьями Habr."""

    def get_repository(self, session=None):
        """Получить репозиторий Habr."""
        return HabrArticleRepository(session)

    def save_article(self, article_data: Dict[str, Any]) -> bool:
        """
        Сохранить статью Habr.

        Args:
            article_data: Данные статьи

        Returns:
            True если статья сохранена успешно
        """
        required_fields = ['article_id', 'title', 'content', 'url']
        if not self.validate_data(article_data, required_fields):
            return False

        try:
            with self.get_repository() as repo:
                # Проверка дубликатов
                if repo.exists(article_data['article_id']):
                    self.logger.warning(f"Article already exists: {article_data['article_id']}")
                    return False

                # Автоматический расчет метрик
                self._calculate_article_metrics(article_data)

                article = HabrArticle(**article_data)
                repo.add(article)
                repo.commit()

                self.logger.info(f"Habr article saved: {article.title[:50]}...")
                return True

        except Exception as e:
            self.logger.error(f"Failed to save Habr article: {e}", exc_info=True)
            return False

    def _calculate_article_metrics(self, article_data: Dict[str, Any]) -> None:
        """Рассчитать метрики статьи."""
        content = article_data.get('content', '')

        if content and 'word_count' not in article_data:
            article_data['word_count'] = len(content.split())

        if article_data.get('word_count') and 'reading_time_calculated' not in article_data:
            # Средняя скорость чтения: 200 слов/минута
            article_data['reading_time_calculated'] = max(
                1,
                article_data['word_count'] // 200
            )

    def get_news_articles(
            self,
            limit: int = 50,
            offset: int = 0
    ) -> List[HabrArticleDTO]:
        """Получить новостные статьи."""
        try:
            with self.get_repository() as repo:
                articles = repo.get_news_articles(limit, offset)
                return [HabrArticleDTO.from_entity(article) for article in articles]
        except Exception as e:
            self.logger.error(f"Failed to get news articles: {e}", exc_info=True)
            return []

    def get_processed_articles(
            self,
            limit: int = 50,
            offset: int = 0
    ) -> List[HabrArticleDTO]:
        """Получить обработанные статьи."""
        try:
            with self.get_repository() as repo:
                articles = repo.get_processed_articles(limit, offset)
                return [HabrArticleDTO.from_entity(article) for article in articles]
        except Exception as e:
            self.logger.error(f"Failed to get processed articles: {e}", exc_info=True)
            return []

    def article_exists(self, article_id: str) -> bool:
        """Проверить существование статьи."""
        try:
            with self.get_repository() as repo:
                return repo.exists(article_id)
        except Exception as e:
            self.logger.error(f"Failed to check article existence: {e}", exc_info=True)
            return False


# ============================================================================
# STATISTICS SERVICE
# ============================================================================

class StatisticsService:
    """Сервис для получения статистики."""

    def __init__(self):
        self.logger = logging.getLogger(self.__class__.__name__)
        self.reddit_service = RedditService()
        self.processed_reddit_service = ProcessedRedditService()
        self.habr_service = HabrService()

    def get_overall_statistics(self) -> StatisticsDTO:
        """
        Получить общую статистику системы.

        Returns:
            DTO со статистикой
        """
        try:
            with get_db_session() as session:
                reddit_repo = RedditPostRepository(session)
                processed_repo = ProcessedRedditPostRepository(session)
                habr_repo = HabrArticleRepository(session)

                # Подсчет записей
                reddit_count = reddit_repo.count()
                reddit_processed_count = processed_repo.count()
                reddit_news_count = len(processed_repo.get_news_only(limit=10000))

                habr_count = habr_repo.count()
                habr_news_count = len(habr_repo.get_news_articles(limit=10000))
                habr_processed_count = len(habr_repo.get_processed_articles(limit=10000))

                # Расчет процентов
                processing_rate = (
                    (reddit_processed_count / reddit_count * 100)
                    if reddit_count > 0 else 0
                )
                news_rate = (
                    (reddit_news_count / reddit_processed_count * 100)
                    if reddit_processed_count > 0 else 0
                )

                return StatisticsDTO(
                    reddit_posts=reddit_count,
                    reddit_processed=reddit_processed_count,
                    reddit_news=reddit_news_count,
                    habr_articles=habr_count,
                    habr_news=habr_news_count,
                    habr_processed=habr_processed_count,
                    telegram_messages=0,  # TODO: Implement
                    medium_articles=0,  # TODO: Implement
                    processing_rate=processing_rate,
                    news_rate=news_rate
                )

        except Exception as e:
            self.logger.error(f"Failed to get statistics: {e}", exc_info=True)
            return StatisticsDTO(
                reddit_posts=0,
                reddit_processed=0,
                reddit_news=0,
                habr_articles=0,
                habr_news=0,
                habr_processed=0,
                telegram_messages=0,
                medium_articles=0,
                processing_rate=0.0,
                news_rate=0.0
            )


# ============================================================================
# EXPORTS
# ============================================================================

__all__ = [
    # DTOs
    'RedditPostDTO',
    'ProcessedPostDTO',
    'HabrArticleDTO',
    'ParsingResult',
    'StatisticsDTO',

    # Services
    'BaseService',
    'RedditService',
    'ProcessedRedditService',
    'HabrService',
    'StatisticsService',
]