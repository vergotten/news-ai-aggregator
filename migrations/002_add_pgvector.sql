-- Включаем расширение pgvector
CREATE EXTENSION IF NOT EXISTS vector;

-- Добавляем колонку для хранения embedding векторов
-- 768 измерений для модели nomic-embed-text (или 1024 для llama)
ALTER TABLE parsers.reddit_posts
ADD COLUMN IF NOT EXISTS embedding vector(768);

-- Создаём индекс для быстрого поиска похожих векторов
-- HNSW (Hierarchical Navigable Small World) - оптимален для similarity search
CREATE INDEX IF NOT EXISTS idx_reddit_posts_embedding
ON parsers.reddit_posts
USING hnsw (embedding vector_cosine_ops);

-- Добавляем функцию для поиска похожих постов
CREATE OR REPLACE FUNCTION find_similar_posts(
    query_embedding vector(768),
    similarity_threshold float DEFAULT 0.95,
    max_results int DEFAULT 5
)
RETURNS TABLE (
    post_id varchar(50),
    title text,
    similarity float
) AS $$
BEGIN
    RETURN QUERY
    SELECT
        p.post_id,
        p.title,
        1 - (p.embedding <=> query_embedding) as similarity
    FROM parsers.reddit_posts p
    WHERE p.embedding IS NOT NULL
        AND 1 - (p.embedding <=> query_embedding) >= similarity_threshold
    ORDER BY p.embedding <=> query_embedding
    LIMIT max_results;
END;
$$ LANGUAGE plpgsql;

-- Комментарии для документации
COMMENT ON COLUMN parsers.reddit_posts.embedding IS
'Векторное представление текста поста (title + selftext) через embedding модель';

COMMENT ON FUNCTION find_similar_posts IS
'Поиск семантически похожих постов через cosine similarity';