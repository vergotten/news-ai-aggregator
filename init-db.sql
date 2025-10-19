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
CREATE INDEX IF NOT EXISTS idx_sources_enabled ON app.sources(enabled);
CREATE INDEX IF NOT EXISTS idx_user_preferences_user_id ON app.user_preferences(user_id);

GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA app TO newsaggregator;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA app TO newsaggregator;

ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT ALL ON TABLES TO newsaggregator;
ALTER DEFAULT PRIVILEGES IN SCHEMA app GRANT ALL ON SEQUENCES TO newsaggregator;

-- Connect to n8n
\c n8n;
GRANT ALL PRIVILEGES ON DATABASE n8n TO newsaggregator;
GRANT ALL PRIVILEGES ON SCHEMA public TO newsaggregator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON TABLES TO newsaggregator;
ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT ALL ON SEQUENCES TO newsaggregator;