"""Сервис для работы с Qdrant векторной базой данных."""
import os
import logging
import uuid
from typing import Optional, List, Dict, Any
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

logger = logging.getLogger(__name__)


class QdrantService:
    """
    Клиент для взаимодействия с Qdrant.

    Инкапсулирует всю логику работы с векторным хранилищем:
    - создание коллекций
    - поиск похожих векторов
    - добавление/обновление точек
    """

    COLLECTION_NAME = "reddit_posts"
    VECTOR_SIZE = 768  # размерность для nomic-embed-text

    def __init__(self, url: Optional[str] = None):
        """
        Инициализация клиента Qdrant.

        Args:
            url: URL сервера Qdrant. Если None, берется из QDRANT_URL env.
        """
        self.url = url or os.getenv("QDRANT_URL", "http://qdrant:6333")

        try:
            self.client = QdrantClient(url=self.url, timeout=10)
            logger.info(f"Qdrant подключен: {self.url}")
            self._ensure_collection_exists()
        except Exception as e:
            logger.error(f"Ошибка подключения к Qdrant: {e}")
            raise

    def _ensure_collection_exists(self):
        """
        Создает коллекцию если её не существует.

        Идемпотентная операция - безопасна для повторного вызова.
        """
        try:
            collections = self.client.get_collections().collections
            exists = any(c.name == self.COLLECTION_NAME for c in collections)

            if not exists:
                logger.info(f"Создание коллекции '{self.COLLECTION_NAME}'")

                self.client.create_collection(
                    collection_name=self.COLLECTION_NAME,
                    vectors_config=VectorParams(
                        size=self.VECTOR_SIZE,
                        distance=Distance.COSINE  # косинусное расстояние для similarity
                    )
                )

                logger.info(f"Коллекция '{self.COLLECTION_NAME}' создана")
            else:
                logger.debug(f"Коллекция '{self.COLLECTION_NAME}' существует")

        except Exception as e:
            logger.error(f"Ошибка создания коллекции: {e}")
            raise

    def health_check(self) -> bool:
        """
        Проверка доступности Qdrant.

        Returns:
            True если сервис доступен, False иначе.
        """
        try:
            self.client.get_collections()
            return True
        except Exception as e:
            logger.error(f"Qdrant health check failed: {e}")
            return False

    def search_similar(
        self,
        vector: List[float],
        limit: int = 5,
        score_threshold: float = 0.95
    ) -> List[Dict[str, Any]]:
        """
        Поиск похожих векторов через cosine similarity.

        Args:
            vector: Вектор для поиска (768 чисел)
            limit: Максимальное количество результатов
            score_threshold: Минимальный порог схожести (0.0 - 1.0)

        Returns:
            Список словарей с найденными похожими постами:
            [
                {
                    'qdrant_id': str,  # UUID записи в Qdrant
                    'post_id': str,    # ID поста из PostgreSQL
                    'title': str,      # заголовок поста
                    'subreddit': str,  # название subreddit
                    'score': float     # оценка схожести (0.0 - 1.0)
                },
                ...
            ]
        """
        try:
            results = self.client.search(
                collection_name=self.COLLECTION_NAME,
                query_vector=vector,
                limit=limit,
                score_threshold=score_threshold
            )

            similar_posts = []
            for hit in results:
                similar_posts.append({
                    'qdrant_id': str(hit.id),
                    'post_id': hit.payload.get('post_id'),
                    'title': hit.payload.get('title'),
                    'subreddit': hit.payload.get('subreddit'),
                    'score': hit.score
                })

            logger.debug(f"Найдено {len(similar_posts)} похожих записей")
            return similar_posts

        except Exception as e:
            logger.error(f"Ошибка поиска в Qdrant: {e}")
            return []

    def upsert_point(
        self,
        vector: List[float],
        post_id: str,
        metadata: Dict[str, Any],
        qdrant_id: Optional[str] = None
    ) -> str:
        """
        Добавление или обновление вектора в Qdrant.

        Args:
            vector: Embedding вектор (768 чисел)
            post_id: ID поста из PostgreSQL
            metadata: Метаданные для payload (title, subreddit, author, score)
            qdrant_id: UUID для записи. Если None - генерируется новый.

        Returns:
            UUID созданной или обновленной записи (строка)

        Raises:
            Exception: При ошибке сохранения
        """
        if qdrant_id is None:
            qdrant_id = str(uuid.uuid4())

        payload = {
            'post_id': post_id,
            'subreddit': metadata.get('subreddit'),
            'title': metadata.get('title'),
            'author': metadata.get('author'),
            'score': metadata.get('score'),
        }

        try:
            point = PointStruct(
                id=qdrant_id,
                vector=vector,
                payload=payload
            )

            self.client.upsert(
                collection_name=self.COLLECTION_NAME,
                points=[point]
            )

            logger.debug(f"Вектор сохранен в Qdrant: {qdrant_id}")
            return qdrant_id

        except Exception as e:
            logger.error(f"Ошибка сохранения в Qdrant: {e}")
            raise

    def delete_point(self, qdrant_id: str) -> bool:
        """
        Удаление записи из Qdrant.

        Args:
            qdrant_id: UUID записи для удаления

        Returns:
            True если удалено успешно, False при ошибке
        """
        try:
            self.client.delete(
                collection_name=self.COLLECTION_NAME,
                points_selector=[qdrant_id]
            )
            logger.debug(f"Удалено из Qdrant: {qdrant_id}")
            return True
        except Exception as e:
            logger.error(f"Ошибка удаления из Qdrant: {e}")
            return False

    def get_collection_info(self) -> Dict[str, Any]:
        """
        Получение информации о коллекции.

        Returns:
            Словарь с метриками коллекции:
            {
                'name': str,
                'vectors_count': int,
                'points_count': int,
                'status': str
            }
        """
        try:
            info = self.client.get_collection(self.COLLECTION_NAME)
            return {
                'name': self.COLLECTION_NAME,
                'vectors_count': info.vectors_count,
                'points_count': info.points_count,
                'status': info.status
            }
        except Exception as e:
            logger.error(f"Ошибка получения info: {e}")
            return {}


# Singleton pattern для переиспользования одного подключения
_qdrant_instance: Optional[QdrantService] = None


def get_qdrant_service() -> QdrantService:
    """
    Получение singleton экземпляра Qdrant сервиса.

    Гарантирует что в приложении существует только один экземпляр клиента,
    что экономит ресурсы и избегает множественных подключений.

    Returns:
        Экземпляр QdrantService
    """
    global _qdrant_instance
    if _qdrant_instance is None:
        _qdrant_instance = QdrantService()
    return _qdrant_instance