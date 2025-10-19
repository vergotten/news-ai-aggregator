#!/bin/bash

# =============================================================================
# News Aggregator - Скрипт автоматического развертывания проекта
# =============================================================================
# Создает полную структуру проекта со всеми файлами и кодом
# Использование: bash setup_project.sh
# =============================================================================

set -e  # Остановка при ошибке

# Цвета для вывода
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Функции для красивого вывода
log_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

log_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

log_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Заголовок
echo -e "${GREEN}"
cat << "EOF"
╔═══════════════════════════════════════════════════════════════╗
║                  NEWS AGGREGATOR SETUP                        ║
║             Автоматическое развертывание проекта              ║
╚═══════════════════════════════════════════════════════════════╝
EOF
echo -e "${NC}"

PROJECT_ROOT=$(pwd)
log_info "Корневая директория: $PROJECT_ROOT"

# =============================================================================
# Создание структуры директорий
# =============================================================================
log_info "Создание структуры директорий..."

mkdir -p src/{models,scrapers,utils}
mkdir -p tests/{unit,integration}
mkdir -p docs
mkdir -p data logs sessions

log_success "Структура директорий создана"

# =============================================================================
# 1. docker-compose.yml
# =============================================================================
log_info "Создание docker-compose.yml..."

cat > docker-compose.yml << 'DCEOF'
services:
  postgres:
    image: postgres:15-alpine
    container_name: news-aggregator-db
    restart: unless-stopped
    environment:
      POSTGRES_USER: ${POSTGRES_USER:-newsaggregator}
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD:-changeme123}
      POSTGRES_DB: ${POSTGRES_DB:-news_aggregator}
      PGDATA: /var/lib/postgresql/data/pgdata
    ports:
      - "${POSTGRES_PORT:-5432}:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
      - ./init-db.sql:/docker-entrypoint-initdb.d/init.sql:ro
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U ${POSTGRES_USER:-newsaggregator} -d ${POSTGRES_DB:-news_aggregator}"]
      interval: 10s
      timeout: 5s
      retries: 5
      start_period: 30s
    networks:
      - news-aggregator-network

  app:
    build:
      context: .
      dockerfile: Dockerfile
    container_name: news-aggregator-app
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DATABASE_URL: postgresql://${POSTGRES_USER:-newsaggregator}:${POSTGRES_PASSWORD:-changeme123}@postgres:5432/${POSTGRES_DB:-news_aggregator}
      REDDIT_CLIENT_ID: ${REDDIT_CLIENT_ID}
      REDDIT_CLIENT_SECRET: ${REDDIT_CLIENT_SECRET}
      REDDIT_USER_AGENT: ${REDDIT_USER_AGENT:-NewsAggregator/1.0}
      TELEGRAM_API_ID: ${TELEGRAM_API_ID}
      TELEGRAM_API_HASH: ${TELEGRAM_API_HASH}
      TELEGRAM_PHONE: ${TELEGRAM_PHONE}
      PYTHONUNBUFFERED: 1
      TZ: ${TZ:-UTC}
      STREAMLIT_SERVER_PORT: ${STREAMLIT_SERVER_PORT:-8501}
      STREAMLIT_SERVER_ADDRESS: ${STREAMLIT_SERVER_ADDRESS:-localhost}
    ports:
      - "${APP_PORT:-8501}:8501"
    volumes:
      - ./src:/app/src:ro
      - app_logs:/app/logs
      - app_data:/app/data
    networks:
      - news-aggregator-network

  n8n:
    image: n8nio/n8n:latest
    container_name: news-aggregator-n8n
    restart: unless-stopped
    depends_on:
      postgres:
        condition: service_healthy
    environment:
      DB_TYPE: postgresdb
      DB_POSTGRESDB_HOST: postgres
      DB_POSTGRESDB_PORT: 5432
      DB_POSTGRESDB_DATABASE: ${N8N_DB:-n8n}
      DB_POSTGRESDB_USER: ${POSTGRES_USER:-newsaggregator}
      DB_POSTGRESDB_PASSWORD: ${POSTGRES_PASSWORD:-changeme123}
      N8N_BASIC_AUTH_ACTIVE: ${N8N_BASIC_AUTH_ACTIVE:-true}
      N8N_BASIC_AUTH_USER: ${N8N_BASIC_AUTH_USER:-admin}
      N8N_BASIC_AUTH_PASSWORD: ${N8N_BASIC_AUTH_PASSWORD:-admin123}
      N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS: ${N8N_ENFORCE_SETTINGS_FILE_PERMISSIONS:-true}
      TZ: ${TZ:-UTC}
    ports:
      - "${N8N_PORT:-5678}:5678"
    volumes:
      - n8n_data:/home/node/.n8n
    networks:
      - news-aggregator-network

  ollama:
    image: ollama/ollama:latest
    container_name: news-aggregator-ollama
    restart: unless-stopped
    environment:
      OLLAMA_HOST: ${OLLAMA_HOST:-http://0.0.0.0:11434}
      OLLAMA_MODELS: ${OLLAMA_MODELS:-/root/.ollama/models}
      OLLAMA_DEBUG: ${OLLAMA_DEBUG:-INFO}
      OLLAMA_CONTEXT_LENGTH: ${OLLAMA_CONTEXT_LENGTH:-4096}
    ports:
      - "${OLLAMA_PORT:-11434}:11434"
    volumes:
      - ollama_data:/root/.ollama
    networks:
      - news-aggregator-network

  adminer:
    image: adminer:latest
    container_name: news-aggregator-adminer
    restart: unless-stopped
    ports:
      - "${ADMINER_PORT:-8080}:8080"
    networks:
      - news-aggregator-network

volumes:
  postgres_data:
  n8n_data:
  ollama_data:
  app_logs:
  app_data:

networks:
  news-aggregator-network:
    driver: bridge
DCEOF

log_success "docker-compose.yml создан"

# =============================================================================
# 2. Dockerfile
# =============================================================================
log_info "Создание Dockerfile..."

cat > Dockerfile << 'DKEOF'
FROM python:3.10-slim as builder

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential gcc g++ && \
    rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

COPY requirements.txt .
RUN pip install --no-cache-dir --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

FROM python:3.10-slim

RUN apt-get update && apt-get install -y --no-install-recommends \
    curl && rm -rf /var/lib/apt/lists/*

RUN groupadd --gid 1000 appuser && \
    useradd --uid 1000 --gid appuser --create-home appuser

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app

RUN mkdir -p /app/logs /app/data && \
    chown -R appuser:appuser /app

COPY --chown=appuser:appuser src/ /app/src/
COPY --chown=appuser:appuser requirements.txt /app/

RUN mkdir -p /home/appuser/.streamlit && \
    echo '[server]' > /home/appuser/.streamlit/config.toml && \
    echo 'port = 8501' >> /home/appuser/.streamlit/config.toml && \
    echo 'address = "0.0.0.0"' >> /home/appuser/.streamlit/config.toml && \
    echo 'headless = true' >> /home/appuser/.streamlit/config.toml && \
    echo '' >> /home/appuser/.streamlit/config.toml && \
    echo '[browser]' >> /home/appuser/.streamlit/config.toml && \
    echo 'gatherUsageStats = false' >> /home/appuser/.streamlit/config.toml && \
    echo 'serverAddress = "localhost"' >> /home/appuser/.streamlit/config.toml && \
    echo 'serverPort = 8501' >> /home/appuser/.streamlit/config.toml && \
    chown -R appuser:appuser /home/appuser/.streamlit

ENV PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    PATH="/opt/venv/bin:$PATH"

USER appuser

EXPOSE 8501

CMD ["python", "-m", "streamlit", "run", "src/app.py", \
     "--server.port=8501", \
     "--server.address=0.0.0.0", \
     "--browser.serverAddress=localhost", \
     "--browser.serverPort=8501"]
DKEOF

log_success "Dockerfile создан"

# =============================================================================
# 3. .env.example
# =============================================================================
log_info "Создание .env.example..."

cat > .env.example << 'ENVEOF'
# PostgreSQL Configuration
POSTGRES_USER=newsaggregator
POSTGRES_PASSWORD=changeme123
POSTGRES_DB=news_aggregator
POSTGRES_PORT=5432

# Database URL for application
DATABASE_URL=postgresql://newsaggregator:changeme123@postgres:5432/news_aggregator

# Reddit API Credentials
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
REDDIT_USER_AGENT=NewsAggregatorBot/1.0 by /u/your_username

# Telegram API Credentials
TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=your_phone_number

# n8n Configuration
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=admin123
N8N_DB=n8n
N8N_PORT=5678

# Ollama Configuration
OLLAMA_HOST=http://ollama:11434
OLLAMA_MODELS=/root/.ollama/models
OLLAMA_DEBUG=INFO
OLLAMA_CONTEXT_LENGTH=4096
OLLAMA_PORT=11434

# Application Configuration
APP_PORT=8501
STREAMLIT_SERVER_PORT=8501
STREAMLIT_SERVER_ADDRESS=localhost
TZ=UTC

# Adminer
ADMINER_PORT=8080
ENVEOF

log_success ".env.example создан"

# =============================================================================
# 4. init-db.sql
# =============================================================================
log_info "Создание init-db.sql..."

cat > init-db.sql << 'SQLEOF'
-- Create databases if they don't exist
SELECT 'CREATE DATABASE news_aggregator OWNER newsaggregator'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'news_aggregator')\gexec

SELECT 'CREATE DATABASE n8n OWNER newsaggregator'
WHERE NOT EXISTS (SELECT FROM pg_database WHERE datname = 'n8n')\gexec

-- Connect to news_aggregator
\c news_aggregator;

CREATE SCHEMA IF NOT EXISTS app;

GRANT ALL PRIVILEGES ON SCHEMA public TO newsaggregator;
GRANT ALL PRIVILEGES ON SCHEMA app TO newsaggregator;

CREATE TABLE IF NOT EXISTS app.articles (
    id SERIAL PRIMARY KEY,
    title TEXT NOT NULL,
    url TEXT UNIQUE NOT NULL,
    source VARCHAR(100) NOT NULL,
    published_date TIMESTAMP,
    content TEXT,
    summary TEXT,
    tags TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app.sources (
    id SERIAL PRIMARY KEY,
    name VARCHAR(100) UNIQUE NOT NULL,
    type VARCHAR(50) NOT NULL,
    url TEXT,
    enabled BOOLEAN DEFAULT TRUE,
    last_scraped TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS app.user_preferences (
    id SERIAL PRIMARY KEY,
    user_id VARCHAR(100) UNIQUE NOT NULL,
    preferred_sources TEXT[],
    preferred_tags TEXT[],
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_articles_source ON app.articles(source);
CREATE INDEX IF NOT EXISTS idx_articles_published_date ON app.articles(published_date);
CREATE INDEX IF NOT EXISTS idx_articles_created_at ON app.articles(created_at);
CREATE INDEX IF NOT EXISTS idx_sources_enabled ON app.sources(enabled);
CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON app.user_preferences(user_id);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA app TO newsaggregator;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA app TO newsaggregator;
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO newsaggregator;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO newsaggregator;

ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT ALL ON TABLES TO newsaggregator;
ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT ALL ON SEQUENCES TO newsaggregator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO newsaggregator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO newsaggregator;

-- Connect to n8n
\c n8n;
GRANT ALL PRIVILEGES ON DATABASE n8n TO newsaggregator;
GRANT ALL PRIVILEGES ON SCHEMA public TO newsaggregator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO newsaggregator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO newsaggregator;
SQLEOF

log_success "init-db.sql создан"

# =============================================================================
# 5. requirements.txt
# =============================================================================
log_info "Создание requirements.txt..."

cat > requirements.txt << 'REQEOF'
# Web Framework
streamlit==1.31.0

# Database
sqlalchemy==2.0.25
psycopg2-binary==2.9.9

# Reddit API
praw==7.8.1

# Web Scraping
requests==2.31.0
beautifulsoup4==4.12.3
lxml==5.1.0

# Telegram (optional)
telethon==1.34.0

# Utilities
python-dotenv==1.0.1
pandas==2.1.4
REQEOF

log_success "requirements.txt создан"

# =============================================================================
# 6. .gitignore
# =============================================================================
log_info "Создание .gitignore..."

cat > .gitignore << 'GITEOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
*.egg-info/
.installed.cfg
*.egg

# Virtual Environment
venv/
.venv/
ENV/
env/

# Environment Variables
.env
.env.local
.env.*.local

# Logs
logs/
*.log

# Data
data/
sessions/

# Docker
postgres_data/
n8n_data/
ollama_data/
app_logs/
app_data/

# IDEs
.vscode/
.idea/
*.swp
*.swo
*~

# OS
.DS_Store
Thumbs.db
GITEOF

log_success ".gitignore создан"

# =============================================================================
# 7. __init__.py файлы
# =============================================================================
log_info "Создание __init__.py файлов..."

touch src/__init__.py
touch src/models/__init__.py
touch src/scrapers/__init__.py
touch src/utils/__init__.py
touch tests/__init__.py
touch tests/unit/__init__.py
touch tests/integration/__init__.py

log_success "__init__.py файлы созданы"

# =============================================================================
# 8. src/models/database.py
# =============================================================================
log_info "Создание src/models/database.py..."

cat > src/models/database.py << 'PYEOF'
"""Database models and operations for News Aggregator."""
import os
from datetime import datetime
from typing import List, Dict, Optional
from dataclasses import dataclass

from sqlalchemy import create_engine, Column, Integer, String, Text, DateTime, Boolean, ARRAY
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.sql import func

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    raise ValueError("DATABASE_URL environment variable not set")

engine = create_engine(DATABASE_URL, pool_pre_ping=True, pool_size=5, max_overflow=10)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


@dataclass
class RedditPost:
    """Reddit post data container."""
    id: int
    subreddit: str
    title: str
    url: str
    score: int
    num_comments: int
    author: str
    created_utc: datetime
    selftext: Optional[str] = None


@dataclass
class MediumArticle:
    """Medium article data container."""
    id: int
    title: str
    url: str
    author: str
    claps: int
    is_paywalled: bool
    published_at: datetime


class Article(Base):
    """Article model for app.articles table."""
    __tablename__ = "articles"
    __table_args__ = {"schema": "app"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    title = Column(Text, nullable=False)
    url = Column(Text, unique=True, nullable=False)
    source = Column(String(100), nullable=False)
    published_date = Column(DateTime)
    content = Column(Text)
    summary = Column(Text)
    tags = Column(ARRAY(Text))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Source(Base):
    """Source model for app.sources table."""
    __tablename__ = "sources"
    __table_args__ = {"schema": "app"}

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), unique=True, nullable=False)
    type = Column(String(50), nullable=False)
    url = Column(Text)
    enabled = Column(Boolean, default=True)
    last_scraped = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


def init_db() -> None:
    """Initialize database connection and verify tables exist."""
    try:
        Base.metadata.create_all(bind=engine)
        print("✅ База данных инициализирована")
    except Exception as e:
        print(f"❌ Ошибка инициализации БД: {e}")
        raise RuntimeError(f"Database initialization failed: {e}")


def get_session() -> Session:
    """Create new database session."""
    return SessionLocal()


def save_article(
    title: str,
    url: str,
    source: str,
    published_date: Optional[datetime] = None,
    content: Optional[str] = None,
    summary: Optional[str] = None,
    tags: Optional[List[str]] = None
) -> bool:
    """Save article to database."""
    session = get_session()
    try:
        existing = session.query(Article).filter_by(url=url).first()
        if existing:
            return False

        article = Article(
            title=title,
            url=url,
            source=source,
            published_date=published_date,
            content=content,
            summary=summary,
            tags=tags or []
        )
        session.add(article)
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        raise RuntimeError(f"Failed to save article: {e}")
    finally:
        session.close()


def get_stats_extended() -> Dict[str, int]:
    """Get extended statistics from database."""
    session = get_session()
    try:
        reddit_count = session.query(func.count(Article.id)).filter(
            Article.source.like('reddit_%')
        ).scalar() or 0

        telegram_count = session.query(func.count(Article.id)).filter(
            Article.source == 'telegram'
        ).scalar() or 0

        medium_count = session.query(func.count(Article.id)).filter(
            Article.source == 'medium'
        ).scalar() or 0

        return {
            'reddit_posts': reddit_count,
            'telegram_messages': telegram_count,
            'medium_articles': medium_count,
            'latest_reddit': None,
            'latest_telegram': None,
            'latest_medium': None
        }
    finally:
        session.close()


def get_posts_by_subreddit(subreddit: str, limit: int = 10) -> List[RedditPost]:
    """Get Reddit posts by subreddit."""
    session = get_session()
    try:
        articles = session.query(Article).filter(
            Article.source == f'reddit_{subreddit.lower()}'
        ).order_by(Article.created_at.desc()).limit(limit).all()

        posts = []
        for article in articles:
            tags = article.tags or []
            posts.append(RedditPost(
                id=article.id,
                subreddit=subreddit,
                title=article.title,
                url=article.url,
                score=int(tags[0]) if tags and tags[0].isdigit() else 0,
                num_comments=int(tags[1]) if len(tags) > 1 and tags[1].isdigit() else 0,
                author=tags[2] if len(tags) > 2 else 'unknown',
                created_utc=article.published_date or article.created_at,
                selftext=article.content
            ))
        return posts
    finally:
        session.close()


def get_medium_articles(limit: int = 10) -> List[MediumArticle]:
    """Get Medium articles."""
    session = get_session()
    try:
        articles = session.query(Article).filter(
            Article.source == 'medium'
        ).order_by(Article.created_at.desc()).limit(limit).all()

        medium_articles = []
        for article in articles:
            tags = article.tags or []
            medium_articles.append(MediumArticle(
                id=article.id,
                title=article.title,
                url=article.url,
                author=tags[0] if tags else 'unknown',
                claps=int(tags[1]) if len(tags) > 1 and tags[1].isdigit() else 0,
                is_paywalled=len(tags) > 2 and tags[2] == 'paywalled',
                published_at=article.published_date or article.created_at
            ))
        return medium_articles
    finally:
        session.close()
PYEOF

log_success "database.py создан"

# =============================================================================
# 9. src/scrapers/reddit_scraper.py
# =============================================================================
log_info "Создание reddit_scraper.py..."

cat > src/scrapers/reddit_scraper.py << 'PYEOF'
"""Reddit scraper using PRAW."""
import os
import time
from datetime import datetime
from typing import List, Dict

import praw
from praw.exceptions import PRAWException

from src.models.database import save_article


def get_reddit_client() -> praw.Reddit:
    """Initialize Reddit API client."""
    client_id = os.getenv("REDDIT_CLIENT_ID")
    client_secret = os.getenv("REDDIT_CLIENT_SECRET")
    user_agent = os.getenv("REDDIT_USER_AGENT", "NewsAggregator/1.0")

    if not client_id or not client_secret:
        raise ValueError("Reddit API credentials not configured")

    return praw.Reddit(
        client_id=client_id,
        client_secret=client_secret,
        user_agent=user_agent
    )


def scrape_subreddit(
    subreddit_name: str,
    max_posts: int = 50,
    sort_by: str = "hot"
) -> Dict[str, any]:
    """
    Scrape posts from a subreddit.

    Args:
        subreddit_name: Name of subreddit
        max_posts: Maximum posts to fetch
        sort_by: Sort method ('hot', 'new', 'top')

    Returns:
        Dict with results
    """
    print(f"🔍 Парсинг r/{subreddit_name}")

    reddit = get_reddit_client()
    saved = 0
    skipped = 0
    errors = []

    try:
        subreddit = reddit.subreddit(subreddit_name)

        if sort_by == "hot":
            posts = subreddit.hot(limit=max_posts)
        elif sort_by == "new":
            posts = subreddit.new(limit=max_posts)
        elif sort_by == "top":
            posts = subreddit.top(limit=max_posts)
        else:
            posts = subreddit.hot(limit=max_posts)

        for post in posts:
            try:
                published_date = datetime.utcfromtimestamp(post.created_utc)

                # Store metadata in tags
                tags = [
                    str(post.score),
                    str(post.num_comments),
                    str(post.author) if post.author else 'deleted'
                ]

                is_saved = save_article(
                    title=post.title,
                    url=post.url,
                    source=f'reddit_{subreddit_name.lower()}',
                    published_date=published_date,
                    content=post.selftext if hasattr(post, 'selftext') else None,
                    tags=tags
                )

                if is_saved:
                    saved += 1
                else:
                    skipped += 1

            except Exception as e:
                errors.append(str(e))
                continue

        print(f"✅ r/{subreddit_name}: {saved} новых, {skipped} пропущено")

        return {
            'success': True,
            'subreddit': subreddit_name,
            'saved': saved,
            'skipped': skipped,
            'errors': errors
        }

    except PRAWException as e:
        print(f"❌ Ошибка r/{subreddit_name}: {e}")
        return {
            'success': False,
            'subreddit': subreddit_name,
            'saved': saved,
            'skipped': skipped,
            'errors': [f"PRAW error: {str(e)}"]
        }
    except Exception as e:
        print(f"❌ Ошибка r/{subreddit_name}: {e}")
        return {
            'success': False,
            'subreddit': subreddit_name,
            'saved': saved,
            'skipped': skipped,
            'errors': [f"Unexpected error: {str(e)}"]
        }


def scrape_multiple_subreddits(
    subreddits: List[str],
    max_posts: int = 50,
    sort_by: str = "hot",
    delay: int = 5
) -> List[Dict[str, any]]:
    """
    Scrape multiple subreddits with delay between requests.

    Args:
        subreddits: List of subreddit names
        max_posts: Maximum posts per subreddit
        sort_by: Sort method
        delay: Delay in seconds between subreddits

    Returns:
        List of result dicts
    """
    results = []

    for idx, subreddit in enumerate(subreddits):
        result = scrape_subreddit(subreddit, max_posts, sort_by)
        results.append(result)

        if idx < len(subreddits) - 1:
            time.sleep(delay)

    return results
PYEOF

log_success "reddit_scraper.py создан"

# =============================================================================
# 10. src/scrapers/medium_scraper.py
# =============================================================================
log_info "Создание medium_scraper.py..."

cat > src/scrapers/medium_scraper.py << 'PYEOF'
"""Medium scraper using web scraping."""
import time
from typing import List, Dict
from datetime import datetime

import requests
from bs4 import BeautifulSoup

from src.models.database import save_article


HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
}


def scrape_medium_tag(tag: str, max_articles: int = 10) -> Dict[str, any]:
    """
    Scrape Medium articles by tag.

    Args:
        tag: Medium tag (e.g., 'machine-learning')
        max_articles: Maximum articles to fetch

    Returns:
        Dict with results
    """
    print(f"🔍 Парсинг Medium: #{tag}")

    saved = 0
    skipped = 0
    errors = []

    try:
        url = f"https://medium.com/tag/{tag}"
        response = requests.get(url, headers=HEADERS, timeout=10)
        response.raise_for_status()

        soup = BeautifulSoup(response.text, 'html.parser')

        # Find article cards - Medium's structure varies
        articles = soup.find_all('article', limit=max_articles * 2)

        for article in articles[:max_articles]:
            try:
                # Extract title
                title_elem = article.find('h2') or article.find('h3')
                if not title_elem:
                    continue
                title = title_elem.get_text(strip=True)

                # Extract link
                link_elem = article.find('a', href=True)
                if not link_elem:
                    continue
                article_url = link_elem['href']
                if not article_url.startswith('http'):
                    article_url = f"https://medium.com{article_url}"

                # Extract author
                author_elem = article.find('p', class_=lambda x: x and 'author' in x.lower())
                author = author_elem.get_text(strip=True) if author_elem else 'Unknown'

                # Check paywall indicator
                is_paywalled = bool(article.find(text=lambda t: t and 'member' in t.lower()))

                # Estimate claps (not always available via scraping)
                claps = 0
                claps_elem = article.find(text=lambda t: t and 'clap' in t.lower())
                if claps_elem:
                    try:
                        claps = int(''.join(filter(str.isdigit, claps_elem)))
                    except ValueError:
                        pass

                tags = [author, str(claps)]
                if is_paywalled:
                    tags.append('paywalled')

                is_saved = save_article(
                    title=title,
                    url=article_url,
                    source='medium',
                    published_date=datetime.utcnow(),
                    tags=tags
                )

                if is_saved:
                    saved += 1
                else:
                    skipped += 1

            except Exception as e:
                errors.append(f"Article parse error: {str(e)}")
                continue

        print(f"✅ #{tag}: {saved} новых, {skipped} пропущено")

        return {
            'success': True,
            'tag': tag,
            'saved': saved,
            'skipped': skipped,
            'errors': errors
        }

    except requests.RequestException as e:
        print(f"❌ Ошибка Medium #{tag}: {e}")
        return {
            'success': False,
            'tag': tag,
            'saved': saved,
            'skipped': skipped,
            'errors': [f"Request error: {str(e)}"]
        }
    except Exception as e:
        print(f"❌ Ошибка Medium #{tag}: {e}")
        return {
            'success': False,
            'tag': tag,
            'saved': saved,
            'skipped': skipped,
            'errors': [f"Unexpected error: {str(e)}"]
        }


def scrape_multiple_sources(
    tags: List[str],
    max_articles: int = 10,
    delay: int = 3
) -> List[Dict[str, any]]:
    """
    Scrape multiple Medium tags with delay.

    Args:
        tags: List of Medium tags
        max_articles: Maximum articles per tag
        delay: Delay in seconds between requests

    Returns:
        List of result dicts
    """
    results = []

    for idx, tag in enumerate(tags):
        result = scrape_medium_tag(tag, max_articles)
        results.append(result)

        if idx < len(tags) - 1:
            time.sleep(delay)

    return results
PYEOF

log_success "medium_scraper.py создан"

# =============================================================================
# 11. src/app.py - Streamlit UI
# =============================================================================
log_info "Создание app.py (Streamlit UI)..."

cat > src/app.py << 'APPEOF'
"""Streamlit веб-интерфейс для News Aggregator."""
import streamlit as st
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

st.set_page_config(
    page_title="News Aggregator",
    page_icon="📰",
    layout="wide"
)

DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    st.error("❌ DATABASE_URL не настроен")
    st.stop()

try:
    from src.models.database import (
        init_db,
        get_stats_extended,
        get_posts_by_subreddit,
        get_medium_articles
    )
    init_db()
except Exception as e:
    st.error(f"❌ Ошибка БД: {e}")
    st.stop()

st.title("📰 News Aggregator")
st.caption("Reddit • Telegram • Medium")

col1, col2, col3 = st.columns(3)
with col1:
    if os.getenv("REDDIT_CLIENT_ID"):
        st.success("✅ Reddit API")
    else:
        st.warning("⚠️ Reddit API")
with col2:
    if os.getenv("TELEGRAM_API_ID"):
        st.success("✅ Telegram API")
    else:
        st.warning("⚠️ Telegram API")
with col3:
    st.success("✅ Database")

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

tab1, tab2, tab3, tab4 = st.tabs(["🔴 Reddit", "🔵 Telegram", "📝 Medium", "📊 Analytics"])

with tab1:
    st.header("Reddit Parser")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("⚙️ Настройки")

        default_subs = ["MachineLearning", "artificial", "Python"]
        selected_subs = st.multiselect(
            "Subreddits:",
            default_subs,
            default=["MachineLearning"]
        )

        col_a, col_b, col_c = st.columns(3)
        with col_a:
            max_posts = st.slider("Макс. постов:", 10, 200, 50)
        with col_b:
            delay = st.slider("Задержка (сек):", 3, 30, 5)
        with col_c:
            sort_by = st.selectbox("Сортировка:", ["hot", "new", "top"])

        if st.button("🚀 Начать парсинг Reddit", type="primary", use_container_width=True):
            if not selected_subs:
                st.error("❌ Выберите subreddits")
            elif not os.getenv("REDDIT_CLIENT_ID"):
                st.error("❌ Reddit API не настроен")
            else:
                with st.spinner("🔄 Парсинг..."):
                    try:
                        from src.scrapers.reddit_scraper import scrape_multiple_subreddits

                        results = scrape_multiple_subreddits(
                            subreddits=selected_subs,
                            max_posts=max_posts,
                            sort_by=sort_by,
                            delay=delay
                        )

                        st.success("✅ Завершено!")
                        for result in results:
                            if result['success']:
                                st.write(
                                    f"**r/{result['subreddit']}**: "
                                    f"✅ {result['saved']}, "
                                    f"⏭️ {result['skipped']}"
                                )
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ {str(e)}")

    with col2:
        st.subheader("📊 Статистика")
        st.metric("Постов", f"{stats['reddit_posts']:,}")

        if stats['reddit_posts'] > 0 and selected_subs:
            st.subheader("📄 Последние")
            try:
                posts = get_posts_by_subreddit(selected_subs[0], limit=5)
                for post in posts:
                    with st.expander(f"⬆️ {post.score} | {post.title[:40]}..."):
                        st.write(f"**r/{post.subreddit}** • {post.num_comments} комм.")
                        if post.url:
                            st.link_button("Открыть", post.url)
            except Exception as e:
                st.caption(f"Ошибка: {e}")

with tab2:
    st.header("Telegram Parser")
    st.info("🚧 В разработке")

with tab3:
    st.header("Medium Parser")

    col1, col2 = st.columns([2, 1])

    with col1:
        st.subheader("⚙️ Настройки")

        default_tags = ["machine-learning", "python"]
        selected_tags = st.multiselect(
            "Теги:",
            default_tags,
            default=["machine-learning"]
        )

        col_a, col_b = st.columns(2)
        with col_a:
            max_articles = st.slider("Статей:", 5, 50, 10)
        with col_b:
            delay_medium = st.slider("Задержка:", 2, 10, 3)

        if st.button("🚀 Начать парсинг Medium", type="primary", use_container_width=True):
            if not selected_tags:
                st.error("❌ Выберите теги")
            else:
                with st.spinner("🔄 Парсинг..."):
                    try:
                        from src.scrapers.medium_scraper import scrape_multiple_sources

                        results = scrape_multiple_sources(
                            tags=selected_tags,
                            max_articles=max_articles,
                            delay=delay_medium
                        )

                        st.success("✅ Завершено!")
                        for result in results:
                            if result['success']:
                                st.write(
                                    f"🏷️ **{result['tag']}**: "
                                    f"✅ {result['saved']}, "
                                    f"⏭️ {result['skipped']}"
                                )
                        st.rerun()
                    except Exception as e:
                        st.error(f"❌ {str(e)}")

    with col2:
        st.subheader("📊 Статистика")
        st.metric("Статей", f"{stats['medium_articles']:,}")

        if stats['medium_articles'] > 0:
            st.subheader("📄 Последние")
            try:
                articles = get_medium_articles(limit=5)
                for article in articles:
                    icon = "🔒" if article.is_paywalled else "📖"
                    with st.expander(f"{icon} {article.title[:40]}..."):
                        st.write(f"**{article.author}** • 👏 {article.claps}")
                        col_a, col_b = st.columns(2)
                        with col_a:
                            st.link_button("Открыть", article.url)
                        with col_b:
                            if article.is_paywalled:
                                st.link_button("🔓 Freedium", f"https://freedium.cfd/{article.url}")
            except Exception as e:
                st.caption(f"Ошибка: {e}")

with tab4:
    st.header("Аналитика")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Reddit", f"{stats['reddit_posts']:,}")
    with col2:
        st.metric("Telegram", f"{stats['telegram_messages']:,}")
    with col3:
        st.metric("Medium", f"{stats['medium_articles']:,}")
    with col4:
        total = stats['reddit_posts'] + stats['telegram_messages'] + stats['medium_articles']
        st.metric("Всего", f"{total:,}")

    st.markdown("---")

    if total > 0:
        st.subheader("📈 Активность")
        import pandas as pd

        chart_data = pd.DataFrame({
            'Платформа': ['Reddit', 'Telegram', 'Medium'],
            'Записей': [
                stats['reddit_posts'],
                stats['telegram_messages'],
                stats['medium_articles']
            ]
        })
        st.bar_chart(chart_data.set_index('Платформа'))
    else:
        st.info("📊 Нет данных. Запустите парсинг!")

st.markdown("---")
col_f1, col_f2 = st.columns([3, 1])
with col_f1:
    st.caption("PostgreSQL • Docker • N8N • Ollama")
with col_f2:
    if st.button("🔄 Обновить"):
        st.rerun()
APPEOF

log_success "app.py создан"

# =============================================================================
# 12. Вспомогательные скрипты
# =============================================================================
log_info "Создание вспомогательных скриптов..."

cat > start.sh << 'STARTEOF'
#!/bin/bash
echo "🚀 Запуск News Aggregator..."
docker compose up -d
echo ""
echo "✅ Сервисы запущены!"
echo ""
echo "📱 Интерфейсы:"
echo "   Streamlit:  http://localhost:8501"
echo "   N8N:        http://localhost:5678 (admin/admin123)"
echo "   Adminer:    http://localhost:8080"
echo "   Ollama:     http://localhost:11434"
echo ""
echo "📊 Проверка статуса:"
echo "   docker compose ps"
echo ""
echo "📋 Логи:"
echo "   docker compose logs -f app"
STARTEOF
chmod +x start.sh

cat > stop.sh << 'STOPEOF'
#!/bin/bash
echo "🛑 Остановка News Aggregator..."
docker compose down
echo "✅ Все сервисы остановлены"
STOPEOF
chmod +x stop.sh

cat > logs.sh << 'LOGSEOF'
#!/bin/bash
SERVICE=${1:-app}
echo "📊 Логи сервиса: $SERVICE"
echo "Нажмите Ctrl+C для выхода"
echo "---"
docker compose logs -f $SERVICE
LOGSEOF
chmod +x logs.sh

cat > clean.sh << 'CLEANEOF'
#!/bin/bash
echo "🧹 Полная очистка проекта..."
read -p "Удалить все данные и volumes? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]
then
    docker compose down -v
    docker volume prune -f
    echo "✅ Очистка завершена"
else
    echo "❌ Отменено"
fi
CLEANEOF
chmod +x clean.sh

log_success "Вспомогательные скрипты созданы"

# =============================================================================
# 13. README.md
# =============================================================================
log_info "Создание README.md..."

cat > README.md << 'READMEEOF'
# News Aggregator

Многофункциональный агрегатор новостей с поддержкой парсинга Reddit, Telegram и Medium.

## 🚀 Быстрый старт

```bash
# 1. Клонирование и настройка
git clone <repository>
cd news-aggregator

# 2. Настройка окружения
cp .env.example .env
nano .env  # Добавьте API ключи

# 3. Запуск
./start.sh

# 4. Открыть веб-интерфейс
open http://localhost:8501
```

## 📋 Требования

- Docker 20.10+
- Docker Compose 2.0+
- 2GB свободного места на диске
- Доступ к интернету

## 🏗️ Архитектура

```
news-aggregator/
├── docker-compose.yml      # Оркестрация сервисов
├── Dockerfile              # Образ приложения
├── init-db.sql             # Инициализация БД
├── requirements.txt        # Python зависимости
├── .env                    # Конфигурация (не коммитить!)
├── src/
│   ├── app.py              # Streamlit веб-интерфейс
│   ├── models/
│   │   └── database.py     # SQLAlchemy модели
│   └── scrapers/
│       ├── reddit_scraper.py
│       └── medium_scraper.py
├── docs/
│   ├── DATABASE_ACCESS.md  # Руководство по БД
│   └── REDDIT_API_SETUP.md # Настройка Reddit API
└── tests/
    ├── unit/
    └── integration/
```

## 🔧 Настройка API

### Reddit API

1. Перейдите: https://www.reddit.com/prefs/apps
2. Создайте приложение типа "script"
3. Скопируйте `client_id` и `client_secret`
4. Добавьте в `.env`:

```bash
REDDIT_CLIENT_ID=ваш_client_id
REDDIT_CLIENT_SECRET=ваш_client_secret
REDDIT_USER_AGENT=NewsAggregatorBot/1.0 by /u/ваш_username
```

Подробнее: [docs/REDDIT_API_SETUP.md](docs/REDDIT_API_SETUP.md)

### Telegram API (опционально)

1. Перейдите: https://my.telegram.org/apps
2. Создайте приложение
3. Скопируйте `api_id` и `api_hash`

## 📊 Использование

### Веб-интерфейс (рекомендуется)

```bash
./start.sh
open http://localhost:8501
```

Функции:
- ✅ Парсинг Reddit subreddits
- ✅ Парсинг Medium статей
- ✅ Просмотр статистики
- ✅ Визуализация данных
- 🚧 Парсинг Telegram каналов (в разработке)

### Доступ к базе данных

Adminer (веб-интерфейс):
```
URL: http://localhost:8080
System: PostgreSQL
Server: postgres
Username: newsaggregator
Password: changeme123
Database: news_aggregator
```

Подробнее: [docs/DATABASE_ACCESS.md](docs/DATABASE_ACCESS.md)

## 🐳 Docker команды

```bash
# Запуск всех сервисов
./start.sh
# или
docker compose up -d

# Остановка
./stop.sh
# или
docker compose down

# Просмотр логов
./logs.sh app
./logs.sh postgres
./logs.sh n8n

# Перезапуск одного сервиса
docker compose restart app

# Пересборка после изменений
docker compose up --build

# Полная очистка (удаление всех данных)
./clean.sh
```

## 📦 Компоненты системы

| Сервис | Порт | Описание |
|--------|------|----------|
| **Streamlit App** | 8501 | Веб-интерфейс для управления парсингом |
| **PostgreSQL** | 5432 | База данных для хранения статей |
| **N8N** | 5678 | Автоматизация и планирование задач |
| **Ollama** | 11434 | Локальная LLM для анализа текста |
| **Adminer** | 8080 | Веб-интерфейс для управления БД |

## 🔐 Безопасность

⚠️ **Важно для продакшена:**

1. Измените все пароли в `.env`
2. Не коммитьте `.env` в Git
3. Используйте HTTPS для публичного доступа
4. Ограничьте доступ к портам через firewall

## 🧪 Тестирование

```bash
# Запуск тестов
pytest tests/ -v

# С покрытием
pytest tests/ --cov=src --cov-report=html
```

## 📈 Мониторинг

```bash
# Статус контейнеров
docker compose ps

# Использование ресурсов
docker stats

# Размер volumes
docker system df -v
```

## 🐛 Решение проблем

### Adminer не открывается

```bash
docker compose up -d adminer
docker logs news-aggregator-adminer
```

### Reddit API возвращает 401

Проверьте правильность `client_id` и `client_secret` в `.env`

### База данных не инициализируется

```bash
docker compose down -v  # Удалить volumes
docker compose up -d    # Пересоздать
```

### Приложение падает сразу после старта

```bash
docker compose logs app  # Проверить логи
# Убедитесь что DATABASE_URL настроен
```

## 📚 Документация

- [Доступ к базе данных](docs/DATABASE_ACCESS.md)
- [Настройка Reddit API](docs/REDDIT_API_SETUP.md)

## 🤝 Вклад в проект

1. Fork репозитория
2. Создайте feature branch (`git checkout -b feature/amazing-feature`)
3. Commit изменений (`git commit -m 'Add amazing feature'`)
4. Push в branch (`git push origin feature/amazing-feature`)
5. Откройте Pull Request

## 📝 Лицензия

MIT License - см. [LICENSE](LICENSE)

## 👥 Авторы

- Ваше имя - [@your_handle](https://github.com/your_handle)

## 🙏 Благодарности

- [PRAW](https://praw.readthedocs.io/) - Reddit API wrapper
- [Streamlit](https://streamlit.io/) - Фреймворк для веб-интерфейса
- [SQLAlchemy](https://www.sqlalchemy.org/) - ORM для Python
READMEEOF

log_success "README.md создан"

# =============================================================================
# 14. Makefile
# =============================================================================
log_info "Создание Makefile..."

cat > Makefile << 'MAKEFILEEOF'
.PHONY: help build up down restart logs clean test docs

help:
	@echo "News Aggregator - Команды Make"
	@echo ""
	@echo "make build     - Собрать Docker образы"
	@echo "make up        - Запустить все сервисы"
	@echo "make down      - Остановить все сервисы"
	@echo "make restart   - Перезапустить сервисы"
	@echo "make logs      - Показать логи (app)"
	@echo "make clean     - Удалить все данные и volumes"
	@echo "make test      - Запустить тесты"
	@echo "make docs      - Открыть документацию"

build:
	docker compose build --no-cache

up:
	./start.sh

down:
	./stop.sh

restart:
	docker compose restart

logs:
	docker compose logs -f app

clean:
	./clean.sh

test:
	pytest tests/ -v

docs:
	@echo "📚 Документация:"
	@echo "   DATABASE_ACCESS.md - docs/DATABASE_ACCESS.md"
	@echo "   REDDIT_API_SETUP.md - docs/REDDIT_API_SETUP.md"
MAKEFILEEOF

log_success "Makefile создан"

# =============================================================================
# Создание .env если не существует
# =============================================================================
if [ ! -f .env ]; then
    log_info "Создание .env из .env.example..."
    cp .env.example .env
    log_warning ".env создан - не забудьте добавить API ключи!"
fi

# =============================================================================
# Финальная сводка
# =============================================================================
echo ""
echo "=========================================================================="
log_success "ПРОЕКТ УСПЕШНО СОЗДАН!"
echo "=========================================================================="
echo ""
echo "📁 Структура проекта:"
echo "   $(find src -type f -name '*.py' 2>/dev/null | wc -l | tr -d ' ') Python файлов"
echo "   $(find tests -type f -name '*.py' 2>/dev/null | wc -l | tr -d ' ') тестов"
echo "   $(find docs -type f 2>/dev/null | wc -l | tr -d ' ') документов"
echo ""
echo "✅ Созданные файлы:"
echo "   • docker-compose.yml"
echo "   • Dockerfile"
echo "   • .env (настройте API ключи!)"
echo "   • init-db.sql"
echo "   • requirements.txt"
echo "   • src/app.py"
echo "   • src/models/database.py"
echo "   • src/scrapers/reddit_scraper.py"
echo "   • src/scrapers/medium_scraper.py"
echo "   • docs/DATABASE_ACCESS.md"
echo "   • docs/REDDIT_API_SETUP.md"
echo "   • README.md"
echo "   • Makefile"
echo "   • start.sh, stop.sh, logs.sh, clean.sh"
echo ""
echo "=========================================================================="
echo "🚀 СЛЕДУЮЩИЕ ШАГИ:"
echo "=========================================================================="
echo ""
echo "1️⃣  Настройте .env файл:"
echo "    nano .env"
echo "    # Добавьте REDDIT_CLIENT_ID и REDDIT_CLIENT_SECRET"
echo "    # См. docs/REDDIT_API_SETUP.md"
echo ""
echo "2️⃣  Запустите проект:"
echo "    ./start.sh"
echo ""
echo "3️⃣  Откройте веб-интерфейсы:"
echo "    • Streamlit:  http://localhost:8501"
echo "    • N8N:        http://localhost:5678 (admin/admin123)"
echo "    • Adminer:    http://localhost:8080 (newsaggregator/changeme123)"
echo "    • Ollama:     http://localhost:11434"
echo ""
echo "4️⃣  Проверьте статус:"
echo "    docker compose ps"
echo "    ./logs.sh app"
echo ""
echo "=========================================================================="
log_success "Установка завершена! 🎉"
echo "=========================================================================="
echo ""
log_info "Документация:"
echo "   • Доступ к БД: docs/DATABASE_ACCESS.md"
echo "   • Настройка Reddit API: docs/REDDIT_API_SETUP.md"
echo "   • Основной README: README.md"
echo ""