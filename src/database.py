"""Database operations for PostgreSQL"""
import os
from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from datetime import datetime

Base = declarative_base()


class RedditPost(Base):
    """Модель для постов Reddit"""
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

    def __repr__(self):
        return f"<RedditPost {self.post_id}: {self.title[:50]}>"


class TelegramMessage(Base):
    """Модель для сообщений Telegram"""
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
    """Модель для статей Medium"""
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
    source = Column(String(50))  # 'direct' or 'freedium'
    tags = Column(Text)  # JSON array of tags as string
    scraped_at = Column(DateTime, default=datetime.utcnow, index=True)

    def __repr__(self):
        return f"<MediumArticle {self.title[:50]}>"


def get_engine():
    """Создает и возвращает engine для БД"""
    db_url = os.getenv("DATABASE_URL")
    if not db_url:
        raise ValueError("DATABASE_URL не настроен в .env")
    return create_engine(db_url, echo=False)


def init_db():
    """Инициализирует базу данных и создает таблицы"""
    engine = get_engine()
    try:
        # Создаем схему если её нет (исправлено: обернуто в text())
        with engine.connect() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS parsers"))  # ← Исправление здесь
            conn.commit()
        print("✅ Схема 'parsers' создана или уже существует")

        # Создаем таблицы
        Base.metadata.create_all(engine)
        print("✅ База данных инициализирована")
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        raise  # Перебрасываем для отладки, если нужно


def get_session():
    """Возвращает сессию для работы с БД"""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()


def save_reddit_post(post_data: dict):
    """Сохраняет пост Reddit в БД"""
    session = get_session()
    try:
        existing = session.query(RedditPost).filter_by(post_id=post_data['post_id']).first()
        if existing:
            return False

        post = RedditPost(**post_data)
        session.add(post)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"❌ Ошибка сохранения поста: {e}")
        return False
    finally:
        session.close()


def save_telegram_message(msg_data: dict):
    """Сохраняет сообщение Telegram в БД"""
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
        print(f"❌ Ошибка сохранения сообщения: {e}")
        return False
    finally:
        session.close()


def get_stats():
    """Возвращает статистику по собранным данным"""
    session = get_session()
    try:
        reddit_count = session.query(RedditPost).count()
        telegram_count = session.query(TelegramMessage).count()

        # ADD: Medium count
        try:
            medium_count = session.query(MediumArticle).count()
        except:
            medium_count = 0

        latest_reddit = session.query(RedditPost).order_by(
            RedditPost.scraped_at.desc()
        ).first()

        latest_telegram = session.query(TelegramMessage).order_by(
            TelegramMessage.scraped_at.desc()
        ).first()

        # ADD: Latest Medium
        try:
            latest_medium = session.query(MediumArticle).order_by(
                MediumArticle.scraped_at.desc()
            ).first()
        except:
            latest_medium = None

        return {
            'reddit_posts': reddit_count,
            'telegram_messages': telegram_count,
            'medium_articles': medium_count,  # ADD this line
            'latest_reddit': latest_reddit.scraped_at if latest_reddit else None,
            'latest_telegram': latest_telegram.scraped_at if latest_telegram else None,
            'latest_medium': latest_medium.scraped_at if latest_medium else None  # ADD this line
        }
    finally:
        session.close()


def get_posts_by_subreddit(subreddit: str, limit: int = 100):
    """Получает посты из конкретного subreddit"""
    session = get_session()
    try:
        posts = session.query(RedditPost).filter_by(
            subreddit=subreddit
        ).order_by(RedditPost.created_utc.desc()).limit(limit).all()
        return posts
    finally:
        session.close()


def save_medium_article(article_data: dict):
    """Сохраняет статью Medium в БД"""
    session = get_session()
    try:
        existing = session.query(MediumArticle).filter_by(url=article_data['url']).first()
        if existing:
            return False

        # Конвертируем tags в JSON string если есть
        if 'tags' in article_data and isinstance(article_data['tags'], list):
            import json
            article_data['tags'] = json.dumps(article_data['tags'])

        article = MediumArticle(**article_data)
        session.add(article)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        print(f"❌ Ошибка сохранения статьи: {e}")
        return False
    finally:
        session.close()


def get_medium_articles(limit: int = 100, author: str = None, tag: str = None):
    """Получает статьи Medium с фильтрацией"""
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


def get_stats_extended():
    """Расширенная статистика включая Medium"""
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