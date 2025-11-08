"""Сервис для дедупликации и векторизации контента."""

import logging
import os
import uuid
from typing import Optional, Dict, Any, List
from qdrant_client import QdrantClient
from qdrant_client.http.models import Filter, FieldCondition, MatchValue
from qdrant_client.http.models import PointStruct
from sqlalchemy.orm import Session

from src.models.database import get_session, HabrArticle, RedditPost, TelegramMessage, MediumArticle
from src.services.ollama_service import get_ollama_service

logger = logging.getLogger(__name__)


class DeduplicationService:
    """Сервис для дедупликации и векторизации контента."""

    def __init__(self):
        """Инициализация сервиса."""
        self.qdrant_host = os.getenv("QDRANT_HOST", "qdrant")
        self.qdrant_port = int(os.getenv("QDRANT_PORT", 6333))
        self.client = QdrantClient(host=self.qdrant_host, port=self.qdrant_port)
        self.ollama = get_ollama_service()
        self.embedding_model = os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

    def _get_collection_name(self, source: str) -> str:
        """Получить имя коллекции по источнику."""
        if source == "reddit":
            return "reddit_posts"
        elif source == "habr":
            return "habr_articles"
        elif source == "telegram":
            return "telegram_messages"
        elif source == "medium":
            return "medium_articles"
        else:
            raise ValueError(f"Неизвестный источник: {source}")

    def _convert_id_to_uuid(self, record_id: str) -> str:
        """Преобразовать ID записи в UUID."""
        # Создаем UUID на основе ID записи и источника
        return str(uuid.uuid5(uuid.NAMESPACE_DNS, str(record_id)))

    def save_to_qdrant(
        self,
        text: str,
        record_id: str,
        metadata: Dict[str, Any],
        source: str
    ) -> Optional[str]:
        """
        Сохранить текст в Qdrant с вектором.

        Args:
            text: Текст для векторизации
            record_id: ID записи
            metadata: Метаданные
            source: Источник (reddit, habr, telegram, medium)

        Returns:
            ID точки в Qdrant или None в случае ошибки
        """
        try:
            collection_name = self._get_collection_name(source)

            # Проверяем существование коллекции
            if not self.client.collection_exists(collection_name):
                self.client.create_collection(
                    collection_name=collection_name,
                    vectors_config={
                        "size": 768,  # Размерность для nomic-embed-text
                        "distance": "Cosine"
                    }
                )
                logger.info(f"Создана коллекция: {collection_name}")

            # Получаем вектор
            vector = self.ollama.get_embedding(text, self.embedding_model)
            if not vector:
                logger.error(f"Не удалось получить вектор для текста")
                return None

            # Преобразуем ID в UUID
            point_id = self._convert_id_to_uuid(record_id)

            # Создаем точку
            point = PointStruct(
                id=point_id,  # Используем UUID вместо строкового ID
                vector=vector,
                payload={
                    "record_id": record_id,  # Сохраняем оригинальный ID в payload
                    "source": source,
                    **metadata
                }
            )

            # Сохраняем в Qdrant
            self.client.upsert(
                collection_name=collection_name,
                points=[point]
            )

            logger.debug(f"Текст сохранен в Qdrant: {point_id}")
            return point_id

        except Exception as e:
            logger.error(f"Ошибка сохранения в Qdrant: {e}")
            return None

    def update_postgres_with_qdrant_id(
        self,
        record_id: str,
        qdrant_id: str,
        source: str
    ) -> bool:
        """
        Обновить запись в PostgreSQL с ID из Qdrant.

        Args:
            record_id: ID записи
            qdrant_id: ID точки в Qdrant
            source: Источник

        Returns:
            True в случае успеха, False в случае ошибки
        """
        try:
            with get_session() as session:
                if source == "reddit":
                    post = session.query(RedditPost).filter_by(post_id=record_id).first()
                    if post:
                        post.qdrant_id = qdrant_id
                elif source == "habr":
                    article = session.query(HabrArticle).filter_by(article_id=record_id).first()
                    if article:
                        article.qdrant_id = qdrant_id
                elif source == "telegram":
                    message = session.query(TelegramMessage).filter_by(message_id=record_id).first()
                    if message:
                        message.qdrant_id = qdrant_id
                elif source == "medium":
                    article = session.query(MediumArticle).filter_by(article_id=record_id).first()
                    if article:
                        article.qdrant_id = qdrant_id
                else:
                    logger.error(f"Неизвестный источник: {source}")
                    return False

                session.commit()
                logger.debug(f"Обновлена запись в PostgreSQL: {record_id} -> {qdrant_id}")
                return True

        except Exception as e:
            logger.error(f"Ошибка обновления PostgreSQL: {e}")
            return False

    def check_duplicate(
        self,
        text: str,
        source: str,
        threshold: float = 0.85
    ) -> tuple[bool, Optional[str], float]:
        """
        Проверить наличие дубликатов в Qdrant.

        Args:
            text: Текст для проверки
            source: Источник
            threshold: Порог схожести

        Returns:
            Кортеж (is_duplicate, duplicate_id, similarity_score)
        """
        try:
            collection_name = self._get_collection_name(source)

            # Проверяем существование коллекции
            if not self.client.collection_exists(collection_name):
                return False, None, 0.0

            # Получаем вектор
            vector = self.ollama.get_embedding(text, self.embedding_model)
            if not vector:
                logger.error(f"Не удалось получить вектор для текста")
                return False, None, 0.0

            # Ищем похожие векторы
            search_result = self.client.search(
                collection_name=collection_name,
                query_vector=vector,
                limit=1,
                score_threshold=threshold
            )

            if search_result:
                duplicate_id = search_result[0].payload.get("record_id")
                similarity_score = search_result[0].score
                logger.debug(f"Найден дубликат: {duplicate_id} (схожесть: {similarity_score:.2f})")
                return True, duplicate_id, similarity_score

            return False, None, 0.0

        except Exception as e:
            logger.error(f"Ошибка проверки дубликатов: {e}")
            return False, None, 0.0

    def find_similar(
        self,
        text: str,
        source: str,
        limit: int = 5,
        threshold: float = 0.7
    ) -> List[Dict[str, Any]]:
        """
        Найти похожие записи в Qdrant.

        Args:
            text: Текст для поиска
            source: Источник
            limit: Максимальное количество результатов
            threshold: Порог схожести

        Returns:
            Список похожих записей
        """
        try:
            collection_name = self._get_collection_name(source)

            # Проверяем существование коллекции
            if not self.client.collection_exists(collection_name):
                return []

            # Получаем вектор
            vector = self.ollama.get_embedding(text, self.embedding_model)
            if not vector:
                logger.error(f"Не удалось получить вектор для текста")
                return []

            # Ищем похожие векторы
            search_result = self.client.search(
                collection_name=collection_name,
                query_vector=vector,
                limit=limit,
                score_threshold=threshold
            )

            results = []
            for result in search_result:
                results.append({
                    "record_id": result.payload.get("record_id"),
                    "source": result.payload.get("source"),
                    "similarity": result.score,
                    "metadata": result.payload
                })

            return results

        except Exception as e:
            logger.error(f"Ошибка поиска похожих записей: {e}")
            return []


# Singleton
_deduplication_instance: Optional[DeduplicationService] = None


def get_deduplication_service() -> DeduplicationService:
    """
    Получить экземпляр сервиса дедупликации.

    Returns:
        Экземпляр DeduplicationService
    """
    global _deduplication_instance
    if _deduplication_instance is None:
        _deduplication_instance = DeduplicationService()
    return _deduplication_instance