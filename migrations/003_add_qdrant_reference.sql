-- Миграция: добавление поля для связи с Qdrant
-- Дата: 2025-01-XX
-- Описание: Добавляет UUID колонку для хранения идентификатора записи в Qdrant

-- Добавление колонки для UUID из Qdrant
ALTER TABLE parsers.reddit_posts
ADD COLUMN IF NOT EXISTS qdrant_id UUID;

-- Индекс для быстрого поиска по qdrant_id
-- Используется при синхронизации и каскадном удалении
CREATE INDEX IF NOT EXISTS idx_reddit_posts_qdrant_id
ON parsers.reddit_posts(qdrant_id);

-- Документация колонки
COMMENT ON COLUMN parsers.reddit_posts.qdrant_id IS
'UUID записи в Qdrant векторной базе данных. Используется для связи между PostgreSQL и Qdrant для семантического поиска дубликатов.';

-- Опционально: триггер для каскадного удаления
-- (можно раскомментировать при необходимости)
/*
CREATE OR REPLACE FUNCTION cleanup_qdrant_on_delete()
RETURNS TRIGGER AS $$
BEGIN
    -- Здесь можно добавить логику удаления из Qdrant через внешний скрипт
    -- Пример: PERFORM pg_notify('qdrant_cleanup', OLD.qdrant_id::text);
    RETURN OLD;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER trigger_cleanup_qdrant
BEFORE DELETE ON parsers.reddit_posts
FOR EACH ROW
WHEN (OLD.qdrant_id IS NOT NULL)
EXECUTE FUNCTION cleanup_qdrant_on_delete();
*/