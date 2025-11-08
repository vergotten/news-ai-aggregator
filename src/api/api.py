"""REST API для News Aggregator."""
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any
from datetime import datetime
import logging
import json

from src.models.database import get_session, HabrArticle, RedditPost, get_stats_extended, ProcessedRedditPost, TelegramMessage, MediumArticle
from src.utils.log_manager import get_log_manager

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/logs/api.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="News Aggregator API",
    description="API для доступа к данным новостного агрегатора",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Зависимости
def get_db() -> Session:
    """Получить сессию БД."""
    return get_session()

# Модели ответа
from pydantic import BaseModel

class HabrArticleResponse(BaseModel):
    id: int
    article_id: str
    title: str
    content: Optional[str]
    url: str
    author: Optional[str]
    description: Optional[str]
    categories: Optional[str]
    # tags: Optional[str]
    pub_date: Optional[datetime]
    scraped_at: datetime
    reading_time: Optional[int]
    views: Optional[int]
    rating: Optional[int]
    is_news: bool
    editorial_processed: bool
    relevance_score: Optional[float]
    word_count: Optional[int]
    language: str
    sentiment: Optional[str]
    keywords: Optional[str]
    summary: Optional[str]
    difficulty_level: Optional[str]
    processing_version: Optional[str]
    last_updated: Optional[datetime]

    class Config:
        from_attributes = True

class RedditPostResponse(BaseModel):
    id: int
    post_id: str
    title: str
    selftext: Optional[str]
    url: Optional[str]
    author: Optional[str]
    subreddit: str
    score: int
    num_comments: int
    created_utc: datetime
    scraped_at: datetime

    class Config:
        from_attributes = True

class ProcessedRedditPostResponse(BaseModel):
    id: int
    post_id: str
    original_title: str
    original_text: Optional[str]
    subreddit: str
    author: Optional[str]
    url: Optional[str]
    score: int
    is_news: bool
    original_summary: Optional[str]
    rewritten_post: Optional[str]
    editorial_title: Optional[str]
    teaser: Optional[str]
    image_prompt: Optional[str]
    processed_at: datetime
    processing_time: Optional[int]
    model_used: Optional[str]

    class Config:
        from_attributes = True

class TelegramMessageResponse(BaseModel):
    id: int
    message_id: int
    text: Optional[str]
    sender: Optional[str]
    channel: Optional[str]
    date: datetime
    scraped_at: datetime

    class Config:
        from_attributes = True

class MediumArticleResponse(BaseModel):
    id: int
    article_id: str
    title: str
    content: Optional[str]
    author: Optional[str]
    url: Optional[str]
    publication: Optional[str]
    claps: Optional[int]
    responses: Optional[int]
    published_at: Optional[datetime]
    scraped_at: datetime

    class Config:
        from_attributes = True

class LogEntry(BaseModel):
    timestamp: str
    level: str
    message: str
    session_id: str

class StatsResponse(BaseModel):
    reddit_posts: int
    telegram_messages: int
    medium_articles: int
    habr_articles: int
    latest_reddit: Optional[dict]
    latest_telegram: Optional[dict]
    latest_medium: Optional[dict]
    latest_habr: Optional[dict]

class UnifiedDataResponse(BaseModel):
    """Унифицированная модель для всех данных."""
    source: str
    total_count: int
    items: List[Dict[str, Any]]
    metadata: Dict[str, Any]

class AllDataResponse(BaseModel):
    """Ответ со всеми агрегированными данными."""
    timestamp: str
    total_items: int
    sources: Dict[str, UnifiedDataResponse]
    summary: Dict[str, Any]

class DataSummaryResponse(BaseModel):
    """Ответ со сводкой данных."""
    timestamp: str
    total_items: int
    sources: Dict[str, Any]
    processing_stats: Dict[str, Any]

# Эндпоинты
@app.get("/")
async def root():
    """Корневой эндпоинт."""
    logger.info("Запрос к корневому эндпоинту")
    return {"message": "News Aggregator API", "version": "1.0.0"}

@app.get("/stats", response_model=StatsResponse)
async def get_stats():
    """Получить статистику."""
    logger.info("Запрос статистики")
    try:
        stats = get_stats_extended()

        # Конвертируем datetime в строки
        for key in ['latest_reddit', 'latest_telegram', 'latest_medium', 'latest_habr']:
            if stats[key]:
                stats[key] = {
                    'title': stats[key].title[:100] if hasattr(stats[key], 'title') else '',
                    'scraped_at': stats[key].scraped_at.isoformat() if hasattr(stats[key], 'scraped_at') else '',
                    'url': stats[key].url if hasattr(stats[key], 'url') else ''
                }

        logger.debug(f"Статистика получена: {stats}")
        return stats
    except Exception as e:
        logger.error(f"Ошибка получения статистики: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/habr/articles", response_model=List[HabrArticleResponse])
async def get_habr_articles(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    is_news: Optional[bool] = None,
    language: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Получить список Habr статей."""
    logger.info(f"Запрос Habr статей: skip={skip}, limit={limit}, is_news={is_news}, language={language}")
    try:
        query = db.query(HabrArticle)

        if is_news is not None:
            query = query.filter(HabrArticle.is_news == is_news)

        if language:
            query = query.filter(HabrArticle.language == language)

        articles = query.order_by(HabrArticle.scraped_at.desc()).offset(skip).limit(limit).all()
        logger.debug(f"Найдено {len(articles)} статей")
        return articles
    except Exception as e:
        logger.error(f"Ошибка получения Habr статей: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/habr/articles/{article_id}", response_model=HabrArticleResponse)
async def get_habr_article(article_id: str, db: Session = Depends(get_db)):
    """Получить конкретную Habr статью."""
    logger.info(f"Запрос статьи Habr: {article_id}")
    try:
        article = db.query(HabrArticle).filter(HabrArticle.article_id == article_id).first()
        if not article:
            logger.warning(f"Статья не найдена: {article_id}")
            raise HTTPException(status_code=404, detail="Статья не найдена")
        logger.debug(f"Статья найдена: {article.title[:50]}")
        return article
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Ошибка получения Habr статьи: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reddit/posts", response_model=List[RedditPostResponse])
async def get_reddit_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    subreddit: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Получить список Reddit постов."""
    logger.info(f"Запрос Reddit постов: skip={skip}, limit={limit}, subreddit={subreddit}")
    try:
        query = db.query(RedditPost)

        if subreddit:
            query = query.filter(RedditPost.subreddit == subreddit)

        posts = query.order_by(RedditPost.scraped_at.desc()).offset(skip).limit(limit).all()
        logger.debug(f"Найдено {len(posts)} постов")
        return posts
    except Exception as e:
        logger.error(f"Ошибка получения Reddit постов: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/reddit/posts/processed", response_model=List[ProcessedRedditPostResponse])
async def get_processed_reddit_posts(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    is_news: Optional[bool] = None,
    db: Session = Depends(get_db)
):
    """Получить список обработанных Reddit постов."""
    logger.info(f"Запрос обработанных Reddit постов: skip={skip}, limit={limit}, is_news={is_news}")
    try:
        query = db.query(ProcessedRedditPost)

        if is_news is not None:
            query = query.filter(ProcessedRedditPost.is_news == is_news)

        posts = query.order_by(ProcessedRedditPost.processed_at.desc()).offset(skip).limit(limit).all()
        logger.debug(f"Найдено {len(posts)} обработанных постов")
        return posts
    except Exception as e:
        logger.error(f"Ошибка получения обработанных Reddit постов: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/telegram/messages", response_model=List[TelegramMessageResponse])
async def get_telegram_messages(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    channel: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Получить список Telegram сообщений."""
    logger.info(f"Запрос Telegram сообщений: skip={skip}, limit={limit}, channel={channel}")
    try:
        query = db.query(TelegramMessage)

        if channel:
            query = query.filter(TelegramMessage.channel == channel)

        messages = query.order_by(TelegramMessage.date.desc()).offset(skip).limit(limit).all()
        logger.debug(f"Найдено {len(messages)} сообщений")
        return messages
    except Exception as e:
        logger.error(f"Ошибка получения Telegram сообщений: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/medium/articles", response_model=List[MediumArticleResponse])
async def get_medium_articles(
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=1000),
    publication: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """Получить список Medium статей."""
    logger.info(f"Запрос Medium статей: skip={skip}, limit={limit}, publication={publication}")
    try:
        query = db.query(MediumArticle)

        if publication:
            query = query.filter(MediumArticle.publication == publication)

        articles = query.order_by(MediumArticle.scraped_at.desc()).offset(skip).limit(limit).all()
        logger.debug(f"Найдено {len(articles)} статей")
        return articles
    except Exception as e:
        logger.error(f"Ошибка получения Medium статей: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/logs", response_model=List[LogEntry])
async def get_logs(
    limit: int = Query(100, ge=1, le=1000),
    session_id: Optional[str] = None,
    level: Optional[str] = None
):
    """Получить логи парсинга."""
    logger.info(f"Запрос логов: limit={limit}, session_id={session_id}, level={level}")
    try:
        log_manager = get_log_manager()
        logs = log_manager.get_logs(limit=limit, session_id=session_id)

        # Фильтрация по уровню
        if level:
            logs = [log for log in logs if log.get('level') == level.upper()]

        logger.debug(f"Возвращено {len(logs)} записей лога")
        return logs
    except Exception as e:
        logger.error(f"Ошибка получения логов: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/logs")
async def clear_logs(session_id: Optional[str] = None):
    """Очистить логи."""
    logger.info(f"Запрос очистки логов: session_id={session_id}")
    try:
        log_manager = get_log_manager()
        log_manager.clear_logs(session_id=session_id)
        logger.info(f"Логи очищены (сессия: {session_id or 'все'})")
        return {"message": f"Логи очищены (сессия: {session_id or 'все'})"}
    except Exception as e:
        logger.error(f"Ошибка очистки логов: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/health")
async def health_check():
    """Проверка здоровья API."""
    logger.debug("Health check запрос")
    return {
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
        "version": "1.0.0"
    }

@app.get("/sessions")
async def get_sessions():
    """Получить список активных сессий."""
    logger.info("Запрос списка сессий")
    try:
        log_manager = get_log_manager()
        sessions = log_manager.redis_client.hgetall("parsing_sessions")

        session_list = []
        for session_id, data in sessions.items():
            try:
                session_data = json.loads(data)
                session_list.append({
                    "id": session_id,
                    "created_at": session_data.get("created_at"),
                    "status": session_data.get("status"),
                    "closed_at": session_data.get("closed_at")
                })
            except json.JSONDecodeError:
                continue

        return {"sessions": session_list}
    except Exception as e:
        logger.error(f"Ошибка получения сессий: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/data/all", response_model=AllDataResponse)
async def get_all_data(
    limit: int = Query(50, ge=1, le=1000),
    include_content: bool = Query(False, description="Включать полный контент (увеличивает размер ответа)"),
    sources: Optional[str] = Query(None, description="Фильтр по источникам через запятую (reddit,habr,telegram,medium)"),
    db: Session = Depends(get_db)
):
    """
    Получить все агрегированные данные из всех источников в красивом формате.

    Query Parameters:
    - limit: Максимальное количество записей на источник
    - include_content: Включать полный контент статей/постов
    - sources: Фильтр источников (например: "reddit,habr")
    """
    logger.info("Запрос всех агрегированных данных")

    # Парсинг фильтра источников
    allowed_sources = ["reddit", "habr", "telegram", "medium"]
    if sources:
        requested_sources = [s.strip().lower() for s in sources.split(",")]
        sources_to_fetch = [s for s in requested_sources if s in allowed_sources]
    else:
        sources_to_fetch = allowed_sources

    result = {
        "timestamp": datetime.utcnow().isoformat(),
        "total_items": 0,
        "sources": {},
        "summary": {}
    }

    # Reddit сырые данные
    if "reddit" in sources_to_fetch:
        try:
            reddit_posts = db.query(RedditPost).order_by(RedditPost.scraped_at.desc()).limit(limit).all()

            reddit_items = []
            for post in reddit_posts:
                item = {
                    "id": post.id,
                    "post_id": post.post_id,
                    "title": post.title,
                    "author": post.author,
                    "subreddit": post.subreddit,
                    "score": post.score,
                    "num_comments": post.num_comments,
                    "url": post.url,
                    "created_utc": post.created_utc.isoformat() if post.created_utc else None,
                    "scraped_at": post.scraped_at.isoformat(),
                    "has_vector": bool(post.qdrant_id),
                    "word_count": len(post.title.split()) + len((post.selftext or "").split())
                }

                if include_content and post.selftext:
                    item["selftext"] = post.selftext[:500] + "..." if len(post.selftext) > 500 else post.selftext

                reddit_items.append(item)

            result["sources"]["reddit"] = UnifiedDataResponse(
                source="reddit",
                total_count=len(reddit_items),
                items=reddit_items,
                metadata={
                    "latest_post": reddit_posts[0].created_utc.isoformat() if reddit_posts else None,
                    "top_subreddits": list(set([p.subreddit for p in reddit_posts[:10]])),
                    "avg_score": sum(p.score for p in reddit_posts) / len(reddit_posts) if reddit_posts else 0
                }
            )
            result["total_items"] += len(reddit_items)

        except Exception as e:
            logger.error(f"Ошибка получения Reddit данных: {e}")
            result["sources"]["reddit"] = UnifiedDataResponse(
                source="reddit",
                total_count=0,
                items=[],
                metadata={"error": str(e)}
            )

    # Reddit обработанные данные
    if "reddit" in sources_to_fetch:
        try:
            processed_posts = db.query(ProcessedRedditPost).order_by(ProcessedRedditPost.processed_at.desc()).limit(limit).all()

            processed_items = []
            for post in processed_posts:
                item = {
                    "id": post.id,
                    "post_id": post.post_id,
                    "original_title": post.original_title,
                    "editorial_title": post.editorial_title,
                    "teaser": post.teaser,
                    "subreddit": post.subreddit,
                    "author": post.author,
                    "score": post.score,
                    "is_news": post.is_news,
                    "processed_at": post.processed_at.isoformat(),
                    "processing_time_ms": post.processing_time,
                    "model_used": post.model_used,
                    "word_count": len(post.original_title.split()) + len((post.original_text or "").split())
                }

                if include_content and post.rewritten_post:
                    item["rewritten_post"] = post.rewritten_post[:500] + "..." if len(post.rewritten_post) > 500 else post.rewritten_post
                if include_content and post.original_summary:
                    item["summary"] = post.original_summary

                processed_items.append(item)

            result["sources"]["reddit_processed"] = UnifiedDataResponse(
                source="reddit_processed",
                total_count=len(processed_items),
                items=processed_items,
                metadata={
                    "latest_processed": processed_posts[0].processed_at.isoformat() if processed_posts else None,
                    "news_count": sum(1 for p in processed_items if p.is_news),
                    "avg_processing_time": sum(p.processing_time for p in processed_items) / len(processed_items) if processed_items else 0
                }
            )
            result["total_items"] += len(processed_items)

        except Exception as e:
            logger.error(f"Ошибка получения обработанных Reddit данных: {e}")
            result["sources"]["reddit_processed"] = UnifiedDataResponse(
                source="reddit_processed",
                total_count=0,
                items=[],
                metadata={"error": str(e)}
            )

    # Habr статьи
    if "habr" in sources_to_fetch:
        try:
            habr_articles = db.query(HabrArticle).order_by(HabrArticle.scraped_at.desc()).limit(limit).all()

            habr_items = []
            for article in habr_articles:
                item = {
                    "id": article.id,
                    "article_id": article.article_id,
                    "title": article.title,
                    "author": article.author,
                    "url": article.url,
                    "categories": article.categories.split(",") if article.categories else [],
                    # "tags": article.tags.split(",") if article.tags else [],
                    "rating": article.rating,
                    "views": article.views,
                    "reading_time": article.reading_time,
                    "word_count": article.word_count or len((article.content or "").split()),
                    "is_news": article.is_news,
                    "editorial_processed": article.editorial_processed,
                    "scraped_at": article.scraped_at.isoformat(),
                    "pub_date": article.pub_date.isoformat() if article.pub_date else None,
                    "has_vector": bool(article.qdrant_id),
                    "language": article.language,
                    "relevance_score": article.relevance_score
                }

                if include_content and article.content:
                    item["content_preview"] = article.content[:500] + "..." if len(article.content) > 500 else article.content
                if include_content and article.editorial_teaser:
                    item["teaser"] = article.editorial_teaser
                if include_content and article.editorial_title:
                    item["editorial_title"] = article.editorial_title

                habr_items.append(item)

            result["sources"]["habr"] = UnifiedDataResponse(
                source="habr",
                total_count=len(habr_items),
                items=habr_items,
                metadata={
                    "latest_article": habr_articles[0].scraped_at.isoformat() if habr_articles else None,
                    "news_count": sum(1 for a in habr_items if a.get("is_news")),
                    "processed_count": sum(1 for a in habr_items if a.get("editorial_processed")),
                    "avg_rating": sum(a.rating or 0 for a in habr_articles) / len(habr_articles) if habr_articles else 0,
                    "top_categories": list(set([cat for a in habr_articles for cat in (a.categories or "").split(",") if cat]))[:10]
                }
            )
            result["total_items"] += len(habr_items)

        except Exception as e:
            logger.error(f"Ошибка получения Habr данных: {e}")
            result["sources"]["habr"] = UnifiedDataResponse(
                source="habr",
                total_count=0,
                items=[],
                metadata={"error": str(e)}
            )

    # Telegram сообщения
    if "telegram" in sources_to_fetch:
        try:
            telegram_messages = db.query(TelegramMessage).order_by(TelegramMessage.date.desc()).limit(limit).all()

            telegram_items = []
            for msg in telegram_messages:
                item = {
                    "id": msg.id,
                    "message_id": msg.message_id,
                    "text": msg.text,
                    "sender": msg.sender,
                    "channel": msg.channel,
                    "date": msg.date.isoformat(),
                    "scraped_at": msg.scraped_at.isoformat(),
                    "has_vector": bool(msg.qdrant_id),
                    "word_count": len((msg.text or "").split())
                }

                if include_content and msg.text:
                    item["text_preview"] = msg.text[:300] + "..." if len(msg.text) > 300 else msg.text

                telegram_items.append(item)

            result["sources"]["telegram"] = UnifiedDataResponse(
                source="telegram",
                total_count=len(telegram_items),
                items=telegram_items,
                metadata={
                    "latest_message": telegram_messages[0].date.isoformat() if telegram_messages else None,
                    "unique_channels": list(set([m.channel for m in telegram_messages])),
                    "avg_message_length": sum(len(m.text or "") for m in telegram_messages) / len(telegram_messages) if telegram_messages else 0
                }
            )
            result["total_items"] += len(telegram_items)

        except Exception as e:
            logger.error(f"Ошибка получения Telegram данных: {e}")
            result["sources"]["telegram"] = UnifiedDataResponse(
                source="telegram",
                total_count=0,
                items=[],
                metadata={"error": str(e)}
            )

    # Medium статьи
    if "medium" in sources_to_fetch:
        try:
            medium_articles = db.query(MediumArticle).order_by(MediumArticle.scraped_at.desc()).limit(limit).all()

            medium_items = []
            for article in medium_articles:
                item = {
                    "id": article.id,
                    "article_id": article.article_id,
                    "title": article.title,
                    "author": article.author,
                    "url": article.url,
                    "publication": article.publication,
                    "claps": article.claps,
                    "responses": article.responses,
                    "published_at": article.published_at.isoformat() if article.published_at else None,
                    "scraped_at": article.scraped_at.isoformat(),
                    "has_vector": bool(article.qdrant_id),
                    "word_count": len((article.content or "").split())
                }

                if include_content and article.content:
                    item["content_preview"] = article.content[:500] + "..." if len(article.content) > 500 else article.content

                medium_items.append(item)

            result["sources"]["medium"] = UnifiedDataResponse(
                source="medium",
                total_count=len(medium_items),
                items=medium_items,
                metadata={
                    "latest_article": medium_articles[0].scraped_at.isoformat() if medium_articles else None,
                    "unique_publications": list(set([a.publication for a in medium_articles if a.publication])),
                    "avg_claps": sum(a.claps or 0 for a in medium_articles) / len(medium_articles) if medium_articles else 0
                }
            )
            result["total_items"] += len(medium_items)

        except Exception as e:
            logger.error(f"Ошибка получения Medium данных: {e}")
            result["sources"]["medium"] = UnifiedDataResponse(
                source="medium",
                total_count=0,
                items=[],
                metadata={"error": str(e)}
            )

    # Формируем сводную статистику
    result["summary"] = {
        "total_sources": len(result["sources"]),
        "items_per_source": {source: data.total_count for source, data in result["sources"].items()},
        "latest_timestamps": {
            source: data.metadata.get("latest_" + ("post" if "reddit" in source else "article" if source in ["habr", "medium"] else "message"))
            for source, data in result["sources"].items()
            if data.metadata.get("latest_" + ("post" if "reddit" in source else "article" if source in ["habr", "medium"] else "message"))
        },
        "content_included": include_content,
        "filters_applied": {
            "limit": limit,
            "sources": sources_to_fetch
        }
    }

    logger.info(f"Возвращено {result['total_items']} записей из {len(result['sources'])} источников")
    return result

def _calculate_similarity(text1: str, text2: str) -> float:
    """Calculate simple word-based Jaccard similarity between texts."""
    if not text1 or not text2:
        return 0.0

    words1 = set(text1.lower().split())
    words2 = set(text2.lower().split())

    if not words1 or not words2:
        return 0.0

    intersection = words1.intersection(words2)
    union = words1.union(words2)

    return len(intersection) / len(union) if union else 0.0

@app.get("/data/comparison")
async def get_data_comparison(
    source: str = Query("habr", pattern="^(habr|reddit)$"),  # ИСПРАВЛЕНО: regex -> pattern
    limit: int = Query(10, ge=1, le=100),
    only_processed: bool = Query(False),
    db: Session = Depends(get_db)
):
    """
    Compare original vs processed content side-by-side.

    Shows transformation quality for editorial processing.
    Perfect for debugging LLM output issues.

    Args:
        source: 'habr' or 'reddit'
        limit: Number of items to return (1-100)
        only_processed: Show only items that have been processed

    Returns:
        Comparison data with similarity metrics

    Example:
        GET /data/comparison?source=habr&limit=5&only_processed=true
    """
    logger.info(f"Data comparison request: {source}, limit={limit}")

    try:
        result = {
            "source": source,
            "timestamp": datetime.utcnow().isoformat(),
            "items": [],
            "stats": {
                "total": 0,
                "processed": 0,
                "avg_title_similarity": 0.0,
                "avg_content_similarity": 0.0
            }
        }

        if source == "habr":
            query = db.query(HabrArticle).order_by(HabrArticle.scraped_at.desc())

            if only_processed:
                query = query.filter(HabrArticle.editorial_processed == True)

            articles = query.limit(limit).all()
            result["stats"]["total"] = len(articles)

            title_sims = []
            content_sims = []

            for article in articles:
                item = {
                    "id": article.article_id,
                    "url": article.url,
                    "scraped_at": article.scraped_at.isoformat(),
                    "is_processed": article.editorial_processed,
                    "is_news": article.is_news,
                    "relevance_score": article.relevance_score,
                    "original": {
                        "title": article.title,
                        "content_preview": article.content[:500] if article.content else "",
                        "content_length": len(article.content or ""),
                        "author": article.author
                    },
                    "processed": {}
                }

                if article.editorial_processed:
                    result["stats"]["processed"] += 1

                    item["processed"] = {
                        "title": article.editorial_title,
                        "content_preview": article.editorial_rewritten[:500] if article.editorial_rewritten else "",
                        "content_length": len(article.editorial_rewritten or ""),
                        "teaser": article.editorial_teaser,
                        "image_prompt": article.image_prompt
                    }

                    # Calculate similarity metrics
                    if article.title and article.editorial_title:
                        title_sim = _calculate_similarity(article.title, article.editorial_title)
                        title_sims.append(title_sim)
                        item["title_similarity"] = round(title_sim, 3)

                    if article.content and article.editorial_rewritten:
                        content_sim = _calculate_similarity(
                            article.content[:1000],
                            article.editorial_rewritten[:1000]
                        )
                        content_sims.append(content_sim)
                        item["content_similarity"] = round(content_sim, 3)

                result["items"].append(item)

            if title_sims:
                result["stats"]["avg_title_similarity"] = round(sum(title_sims) / len(title_sims), 3)
            if content_sims:
                result["stats"]["avg_content_similarity"] = round(sum(content_sims) / len(content_sims), 3)

        elif source == "reddit":
            # Get raw posts with their processed versions
            raw_posts = db.query(RedditPost).order_by(RedditPost.scraped_at.desc()).limit(limit).all()
            result["stats"]["total"] = len(raw_posts)

            title_sims = []
            content_sims = []

            for post in raw_posts:
                processed = db.query(ProcessedRedditPost).filter(
                    ProcessedRedditPost.post_id == post.post_id
                ).first()

                item = {
                    "id": post.post_id,
                    "url": post.url,
                    "scraped_at": post.scraped_at.isoformat(),
                    "is_processed": bool(processed),
                    "is_news": processed.is_news if processed else False,
                    "original": {
                        "title": post.title,
                        "content_preview": (post.selftext or "")[:500],
                        "content_length": len(post.selftext or ""),
                        "author": post.author,
                        "subreddit": post.subreddit,
                        "score": post.score
                    },
                    "processed": {}
                }

                if processed:
                    result["stats"]["processed"] += 1

                    item["processed"] = {
                        "title": processed.editorial_title,
                        "content_preview": (processed.rewritten_post or "")[:500],
                        "content_length": len(processed.rewritten_post or ""),
                        "teaser": processed.teaser,
                        "image_prompt": processed.image_prompt
                    }

                    # Calculate similarity
                    if post.title and processed.editorial_title:
                        title_sim = _calculate_similarity(post.title, processed.editorial_title)
                        title_sims.append(title_sim)
                        item["title_similarity"] = round(title_sim, 3)

                    if post.selftext and processed.rewritten_post:
                        content_sim = _calculate_similarity(
                            post.selftext[:1000],
                            processed.rewritten_post[:1000]
                        )
                        content_sims.append(content_sim)
                        item["content_similarity"] = round(content_sim, 3)

                result["items"].append(item)

            if title_sims:
                result["stats"]["avg_title_similarity"] = round(sum(title_sims) / len(title_sims), 3)
            if content_sims:
                result["stats"]["avg_content_similarity"] = round(sum(content_sims) / len(content_sims), 3)

        logger.info(f"Comparison returned: {result['stats']['processed']}/{result['stats']['total']} processed")
        return result

    except Exception as e:
        logger.error(f"Comparison error: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/data/summary", response_model=DataSummaryResponse)
async def get_data_summary(db: Session = Depends(get_db)):
    """
    Получить краткую сводку по всем данным без самих записей.
    """
    logger.info("Запрос сводки данных")

    try:
        # Получаем количество записей по каждому источнику
        reddit_count = db.query(RedditPost).count()
        reddit_processed_count = db.query(ProcessedRedditPost).count()
        habr_count = db.query(HabrArticle).count()
        telegram_count = db.query(TelegramMessage).count()
        medium_count = db.query(MediumArticle).count()

        # Получаем последние временные метки
        latest_reddit = db.query(RedditPost).order_by(RedditPost.scraped_at.desc()).first()
        latest_habr = db.query(HabrArticle).order_by(HabrArticle.scraped_at.desc()).first()
        latest_telegram = db.query(TelegramMessage).order_by(TelegramMessage.date.desc()).first()
        latest_medium = db.query(MediumArticle).order_by(MediumArticle.scraped_at.desc()).first()

        # Дополнительная статистика
        reddit_news_count = db.query(ProcessedRedditPost).filter(ProcessedRedditPost.is_news == True).count()
        habr_news_count = db.query(HabrArticle).filter(HabrArticle.is_news == True).count()
        habr_processed_count = db.query(HabrArticle).filter(HabrArticle.editorial_processed == True).count()

        summary = {
            "timestamp": datetime.utcnow().isoformat(),
            "total_items": reddit_count + reddit_processed_count + habr_count + telegram_count + medium_count,
            "sources": {
                "reddit": {
                    "raw_count": reddit_count,
                    "processed_count": reddit_processed_count,
                    "news_count": reddit_news_count,
                    "latest": latest_reddit.scraped_at.isoformat() if latest_reddit else None
                },
                "habr": {
                    "total_count": habr_count,
                    "news_count": habr_news_count,
                    "processed_count": habr_processed_count,
                    "latest": latest_habr.scraped_at.isoformat() if latest_habr else None
                },
                "telegram": {
                    "count": telegram_count,
                    "latest": latest_telegram.date.isoformat() if latest_telegram else None
                },
                "medium": {
                    "count": medium_count,
                    "latest": latest_medium.scraped_at.isoformat() if latest_medium else None
                }
            },
            "processing_stats": {
                "reddit_processing_rate": (reddit_processed_count / reddit_count * 100) if reddit_count > 0 else 0,
                "habr_processing_rate": (habr_processed_count / habr_count * 100) if habr_count > 0 else 0,
                "total_news": reddit_news_count + habr_news_count,
                "total_processed": reddit_processed_count + habr_processed_count
            }
        }

        logger.info(f"Сводка сформирована: {summary['total_items']} всего записей")
        return summary

    except Exception as e:
        logger.error(f"Ошибка получения сводки: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


from fastapi import BackgroundTasks
from pydantic import BaseModel, Field
import uuid
from typing import Optional, List
import asyncio
from datetime import datetime

# In-memory job storage (use Redis in production)
scraper_jobs = {}

# ============================================================================
# Pydantic Models for Scraper Requests
# ============================================================================

class HabrScrapeRequest(BaseModel):
    """Request model for Habr scraper."""
    max_articles: int = Field(default=10, ge=1, le=100, description="Number of articles to scrape")
    hubs: Optional[List[str]] = Field(default=None, description="List of hubs to scrape (e.g., ['python', 'ai'])")
    enable_llm: bool = Field(default=True, description="Enable LLM processing")
    enable_deduplication: bool = Field(default=True, description="Enable semantic deduplication")

    class Config:
        json_schema_extra = {
            "example": {
                "max_articles": 20,
                "hubs": ["python", "artificial_intelligence"],
                "enable_llm": True,
                "enable_deduplication": True
            }
        }

class RedditScrapeRequest(BaseModel):
    """Модель запроса для парсинга Reddit."""
    subreddit: str = Field(..., description="Subreddit name")
    max_posts: int = Field(default=50, ge=1, le=1000, description="Maximum posts to scrape")
    sort: str = Field(default="hot", pattern="^(hot|new|top|rising)$", description="Sort method")  # ИСПРАВЛЕНО: regex -> pattern
    enable_llm: bool = Field(default=True, description="Enable LLM processing")

    class Config:
        json_schema_extra = {
            "example": {
                "max_posts": 15,
                "subreddits": ["MachineLearning", "LocalLLaMA"],
                "sort": "hot",
                "enable_llm": True,
                "enable_deduplication": True
            }
        }

class ScrapeJobResponse(BaseModel):
    """Response model for scrape job."""
    job_id: str
    status: str  # pending, running, completed, failed
    source: str
    created_at: str
    message: str

class ScrapeStatusResponse(BaseModel):
    """Response model for scrape status."""
    job_id: str
    status: str
    source: str
    created_at: str
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

# ============================================================================
# Background Scraper Functions
# ============================================================================

def run_habr_scraper_background(job_id: str, request: HabrScrapeRequest):
    """Run Habr scraper in background."""
    try:
        scraper_jobs[job_id]["status"] = "running"
        scraper_jobs[job_id]["started_at"] = datetime.utcnow().isoformat()

        logger.info(f"Starting Habr scraper job {job_id}")

        # Import here to avoid circular imports
        from src.scrapers.habr_scraper import scrape_habr

        # Run scraper
        result = scrape_habr(
            max_articles=request.max_articles,
            hubs=request.hubs,
            enable_llm=request.enable_llm,
            enable_deduplication=request.enable_deduplication,
            debug=False
        )

        scraper_jobs[job_id]["status"] = "completed"
        scraper_jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
        scraper_jobs[job_id]["results"] = result

        logger.info(f"Habr scraper job {job_id} completed: {result.get('saved', 0)} articles saved")

    except Exception as e:
        logger.error(f"Habr scraper job {job_id} failed: {e}")
        scraper_jobs[job_id]["status"] = "failed"
        scraper_jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
        scraper_jobs[job_id]["error"] = str(e)

def run_reddit_scraper_background(job_id: str, request: RedditScrapeRequest):
    """Run Reddit scraper in background."""
    try:
        scraper_jobs[job_id]["status"] = "running"
        scraper_jobs[job_id]["started_at"] = datetime.utcnow().isoformat()

        logger.info(f"Starting Reddit scraper job {job_id}")

        # Import here to avoid circular imports
        from src.scrapers.reddit_scraper import get_reddit_client, scrape_subreddit

        reddit = get_reddit_client()
        total_saved = 0
        total_skipped = 0

        # ИСПРАВЛЕНО: исправлена ошибка с отсутствием поля subreddits
        subreddits = [request.subreddit]  # Преобразуем单个 subreddit в список

        for subreddit in subreddits:
            result = scrape_subreddit(
                reddit=reddit,
                subreddit_name=subreddit,
                max_posts=request.max_posts,
                sort_method=request.sort,
                enable_llm=request.enable_llm,
                enable_deduplication=request.enable_deduplication
            )
            total_saved += result.get('saved', 0)
            total_skipped += result.get('skipped', 0)

        scraper_jobs[job_id]["status"] = "completed"
        scraper_jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
        scraper_jobs[job_id]["results"] = {
            "success": True,
            "saved": total_saved,
            "skipped": total_skipped,
            "subreddits": subreddits
        }

        logger.info(f"Reddit scraper job {job_id} completed: {total_saved} posts saved")

    except Exception as e:
        logger.error(f"Reddit scraper job {job_id} failed: {e}")
        scraper_jobs[job_id]["status"] = "failed"
        scraper_jobs[job_id]["completed_at"] = datetime.utcnow().isoformat()
        scraper_jobs[job_id]["error"] = str(e)

# ============================================================================
# API Endpoints
# ============================================================================

@app.post("/scrape/habr", response_model=ScrapeJobResponse)
async def scrape_habr_endpoint(
    request: HabrScrapeRequest,
    background_tasks: BackgroundTasks
):
    """
    Launch Habr scraper.

    Scrapes articles from Habr.com and processes them with LLM.
    Returns immediately with job_id - use /scrape/status/{job_id} to check progress.

    **Parameters:**
    - `max_articles`: Number of articles to scrape (1-100, default: 10)
    - `hubs`: List of hubs to scrape (optional, e.g., ["python", "ai"])
    - `enable_llm`: Enable LLM processing (default: true)
    - `enable_deduplication`: Enable semantic deduplication (default: true)

    **Example:**
    ```bash
    curl -X POST http://localhost:8000/scrape/habr \
      -H "Content-Type: application/json" \
      -d '{"max_articles": 20, "hubs": ["python"], "enable_llm": true}'
    ```
    """
    job_id = str(uuid.uuid4())

    scraper_jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "source": "habr",
        "created_at": datetime.utcnow().isoformat(),
        "request": request.dict()
    }

    background_tasks.add_task(run_habr_scraper_background, job_id, request)

    logger.info(f"Habr scraper job {job_id} queued")

    return ScrapeJobResponse(
        job_id=job_id,
        status="pending",
        source="habr",
        created_at=scraper_jobs[job_id]["created_at"],
        message=f"Habr scraper job queued. Check status at /scrape/status/{job_id}"
    )

@app.post("/scrape/reddit", response_model=ScrapeJobResponse)
async def scrape_reddit_endpoint(
    request: RedditScrapeRequest,
    background_tasks: BackgroundTasks
):
    """
    Launch Reddit scraper.

    Scrapes posts from Reddit subreddits and processes them with LLM.
    Returns immediately with job_id - use /scrape/status/{job_id} to check progress.

    **Parameters:**
    - `max_posts`: Number of posts per subreddit (1-100, default: 10)
    - `subreddits`: List of subreddits (required, e.g., ["Python", "MachineLearning"])
    - `sort`: Sort method: "hot", "new", "top", or "rising" (default: "hot")
    - `enable_llm`: Enable LLM processing (default: true)
    - `enable_deduplication`: Enable semantic deduplication (default: true)

    **Example:**
    ```bash
    curl -X POST http://localhost:8000/scrape/reddit \
      -H "Content-Type: application/json" \
      -d '{"max_posts": 15, "subreddits": ["Python", "MachineLearning"], "sort": "hot"}'
    ```
    """
    job_id = str(uuid.uuid4())

    scraper_jobs[job_id] = {
        "job_id": job_id,
        "status": "pending",
        "source": "reddit",
        "created_at": datetime.utcnow().isoformat(),
        "request": request.dict()
    }

    background_tasks.add_task(run_reddit_scraper_background, job_id, request)

    logger.info(f"Reddit scraper job {job_id} queued")

    return ScrapeJobResponse(
        job_id=job_id,
        status="pending",
        source="reddit",
        created_at=scraper_jobs[job_id]["created_at"],
        message=f"Reddit scraper job queued. Check status at /scrape/status/{job_id}"
    )

@app.get("/scrape/status/{job_id}", response_model=ScrapeStatusResponse)
async def get_scrape_status(job_id: str):
    """
    Get scraper job status.

    Check the status and results of a scraping job.

    **Status values:**
    - `pending`: Job queued but not started
    - `running`: Job currently running
    - `completed`: Job finished successfully
    - `failed`: Job failed with error

    **Example:**
    ```bash
    curl http://localhost:8000/scrape/status/abc-123-def
    ```
    """
    if job_id not in scraper_jobs:
        raise HTTPException(status_code=404, detail=f"Job {job_id} not found")

    job = scraper_jobs[job_id]

    return ScrapeStatusResponse(
        job_id=job["job_id"],
        status=job["status"],
        source=job["source"],
        created_at=job["created_at"],
        started_at=job.get("started_at"),
        completed_at=job.get("completed_at"),
        results=job.get("results"),
        error=job.get("error")
    )

@app.get("/scrape/jobs")
async def list_scrape_jobs(limit: int = Query(20, ge=1, le=100)):
    """
    List all scraper jobs.

    Returns list of recent scraper jobs with their status.

    **Example:**
    ```bash
    curl http://localhost:8000/scrape/jobs?limit=10
    ```
    """
    jobs = list(scraper_jobs.values())

    # Sort by created_at descending
    jobs.sort(key=lambda x: x["created_at"], reverse=True)

    return {
        "total": len(jobs),
        "jobs": jobs[:limit]
    }

@app.delete("/scrape/jobs")
async def clear_scrape_jobs():
    """
    Clear all completed/failed jobs.

    Removes jobs with status 'completed' or 'failed' from memory.
    Keeps 'pending' and 'running' jobs.

    **Example:**
    ```bash
    curl -X DELETE http://localhost:8000/scrape/jobs
    ```
    """
    cleared = 0
    job_ids_to_remove = []

    for job_id, job in scraper_jobs.items():
        if job["status"] in ["completed", "failed"]:
            job_ids_to_remove.append(job_id)
            cleared += 1

    for job_id in job_ids_to_remove:
        del scraper_jobs[job_id]

    return {
        "message": f"Cleared {cleared} completed/failed jobs",
        "remaining": len(scraper_jobs)
    }


if __name__ == "__main__":
    import uvicorn
    logger.info("Запуск API сервера")
    uvicorn.run(app, host="0.0.0.0", port=8000, log_level="debug")