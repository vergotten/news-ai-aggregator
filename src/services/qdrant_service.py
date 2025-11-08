"""
Сервис для работы с Qdrant — поддерживает несколько коллекций по источнику.
"""

import os
import logging
import uuid
from typing import Optional, List, Dict, Any

from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

logger = logging.getLogger(__name__)


class QdrantService:
    """
    Клиент-обертка для Qdrant с поддержкой нескольких коллекций:
    - habr_articles
    - reddit_posts
    - telegram_news (резерв)

    Автоматически создаёт коллекцию если её нет.
    """

    COLLECTIONS = {
        "habr": {
            "name": "habr_articles",
            "vector_size": 768,  # ← ИЗМЕНЕНО: 768 для nomic-embed-text
            "distance": Distance.COSINE
        },
        "reddit": {
            "name": "reddit_posts",
            "vector_size": 768,  # ← ИЗМЕНЕНО: 768 для nomic-embed-text
            "distance": Distance.COSINE
        },
    }

    def __init__(self, url: Optional[str] = None):
        self.url = url or os.getenv("QDRANT_URL", "http://qdrant:6333")

        self.client = QdrantClient(url=self.url, timeout=10)
        logger.info(f"Qdrant подключен: {self.url}")

        self._ensure_all_collections()

    def _ensure_all_collections(self):
        """Создаёт коллекции если отсутствуют."""
        existing = {c.name for c in self.client.get_collections().collections}

        for source, cfg in self.COLLECTIONS.items():
            if cfg["name"] not in existing:
                logger.info(f"Создание коллекции: {cfg['name']} (размер: {cfg['vector_size']})")
                self.client.create_collection(
                    collection_name=cfg["name"],
                    vectors_config=VectorParams(
                        size=cfg["vector_size"],
                        distance=cfg["distance"]
                    )
                )
            else:
                logger.debug(f"Коллекция '{cfg['name']}' уже существует")

    def recreate_collections(self):
        """Пересоздать все коллекции с правильной размерностью."""
        for source, cfg in self.COLLECTIONS.items():
            try:
                self.client.delete_collection(cfg["name"])
                logger.info(f"Удалена коллекция: {cfg['name']}")
            except:
                pass

            self.client.create_collection(
                collection_name=cfg["name"],
                vectors_config=VectorParams(
                    size=cfg["vector_size"],
                    distance=cfg["distance"]
                )
            )
            logger.info(f"Создана коллекция: {cfg['name']} (размер: {cfg['vector_size']})")

    def save_embedding(
        self,
        source: str,
        vector: List[float],
        metadata: Dict[str, Any],
        qdrant_id: Optional[str] = None,
    ) -> str:
        """
        Добавить (upsert) embedding в Qdrant.

        Args:
            source: 'habr' | 'reddit'
            vector: embedding моделью
            metadata: метаданные (title, url, author,…)
        """
        cfg = self.COLLECTIONS[source]

        qdrant_id = qdrant_id or str(uuid.uuid4())

        self.client.upsert(
            collection_name=cfg["name"],
            points=[PointStruct(id=qdrant_id, vector=vector, payload=metadata)],
        )

        logger.debug(f"[Qdrant] Saved → {source}: {metadata.get('title', '')}")
        return qdrant_id

    def search_similar(
        self,
        source: str,
        vector: List[float],
        limit: int = 5,
        score_threshold: float = 0.9
    ) -> List[Dict[str, Any]]:
        """Поиск похожих объектов в соответствующей коллекции."""
        cfg = self.COLLECTIONS[source]

        try:
            results = self.client.search(
                collection_name=cfg["name"],
                query_vector=vector,
                limit=limit,
                score_threshold=score_threshold,
            )

            return [
                {
                    "qdrant_id": hit.id,
                    "score": hit.score,
                    **hit.payload
                }
                for hit in results
            ]

        except Exception as e:
            logger.error(f"Ошибка поиска в Qdrant ({source}): {e}")
            return []


_qdrant_instance: Optional[QdrantService] = None


def get_qdrant_service() -> QdrantService:
    global _qdrant_instance
    if _qdrant_instance is None:
        _qdrant_instance = QdrantService()
    return _qdrant_instance