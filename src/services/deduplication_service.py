"""Сервис дедупликации постов через семантический поиск."""
import logging
from typing import Optional, Tuple, Dict, Any
from src.services.ollama_service import get_ollama_service
from src.services.qdrant_service import get_qdrant_service
from src.models.database import get_session, RedditPost

logger = logging.getLogger(__name__)


class DeduplicationService:
    """
    Сервис для проверки семантических дубликатов постов.

    Использует векторный поиск для обнаружения постов со схожим содержанием,
    даже если их заголовки и тексты отличаются дословно.
    """

    def __init__(self, similarity_threshold: float = 0.95):
        """
        Инициализация сервиса дедупликации.

        Args:
            similarity_threshold: Порог схожести для определения дубликата (0.0 - 1.0).
                0.95 означает 95% схожести - очень строгий порог.
        """
        self.threshold = similarity_threshold
        self.ollama = get_ollama_service()
        self.qdrant = get_qdrant_service()

    def check_duplicate(self, text: str) -> Tuple[bool, Optional[str], Optional[float]]:
        """
        Проверка является ли текст семантическим дубликатом существующих постов.

        Алгоритм:
        1. Генерация embedding вектора для входного текста
        2. Поиск похожих векторов в Qdrant
        3. Сравнение score с threshold

        Args:
            text: Текст для проверки (обычно title + selftext)

        Returns:
            Кортеж из трех элементов:
            - is_duplicate: True если найден дубликат
            - duplicate_post_id: ID найденного поста-дубликата
            - similarity_score: Оценка схожести (0.0 - 1.0)

        Examples:
            >>> is_dup, dup_id, score = service.check_duplicate("GPT-4 is amazing")
            >>> if is_dup:
            ...     print(f"Duplicate of {dup_id} with {score:.2%} similarity")
        """
        logger.debug("Проверка на семантические дубликаты")

        # Шаг 1: Генерация embedding через Ollama
        embedding = self.ollama.get_embedding(text)
        if not embedding:
            logger.warning("Не удалось получить embedding, пропускаем проверку дубликатов")
            return False, None, None

        # Шаг 2: Поиск похожих векторов в Qdrant
        similar = self.qdrant.search_similar(
            vector=embedding,
            limit=1,  # нужен только самый похожий
            score_threshold=self.threshold
        )

        # Шаг 3: Анализ результатов
        if similar:
            duplicate = similar[0]
            logger.info(f"Найден дубликат: {duplicate['post_id']}")
            logger.info(f"Заголовок: {duplicate['title'][:60]}")
            logger.info(f"Схожесть: {duplicate['score']:.2%}")

            return True, duplicate['post_id'], duplicate['score']

        logger.debug("Дубликатов не найдено")
        return False, None, None

    def save_to_qdrant(
        self,
        text: str,
        post_id: str,
        metadata: Dict[str, Any]
    ) -> Optional[str]:
        """
        Генерация embedding и сохранение в Qdrant.

        Args:
            text: Текст поста для векторизации
            post_id: ID поста из PostgreSQL (для связи)
            metadata: Метаданные для payload (title, subreddit, author, score)

        Returns:
            UUID записи в Qdrant (строка) или None при ошибке
        """
        logger.debug(f"Сохранение в Qdrant: {post_id}")

        # Генерация embedding
        embedding = self.ollama.get_embedding(text)
        if not embedding:
            logger.error(f"Не удалось сгенерировать embedding для {post_id}")
            return None

        # Сохранение в Qdrant
        try:
            qdrant_id = self.qdrant.upsert_point(
                vector=embedding,
                post_id=post_id,
                metadata=metadata
            )

            logger.debug(f"Сохранено в Qdrant: {qdrant_id}")
            return qdrant_id

        except Exception as e:
            logger.error(f"Ошибка сохранения в Qdrant: {e}")
            return None

    def update_postgres_with_qdrant_id(self, post_id: str, qdrant_id: str) -> bool:
        """
        Обновление записи в PostgreSQL с UUID из Qdrant.

        Создает двустороннюю связь между PostgreSQL и Qdrant для
        возможности синхронизации и каскадного удаления.

        Args:
            post_id: ID поста в PostgreSQL
            qdrant_id: UUID записи в Qdrant

        Returns:
            True если обновление успешно, False при ошибке
        """
        session = get_session()
        try:
            post = session.query(RedditPost).filter_by(post_id=post_id).first()
            if not post:
                logger.error(f"Пост {post_id} не найден в PostgreSQL")
                return False

            # Преобразование строки UUID в объект UUID для PostgreSQL
            import uuid as uuid_lib
            post.qdrant_id = uuid_lib.UUID(qdrant_id)
            session.commit()

            logger.debug(f"PostgreSQL обновлен: {post_id} -> {qdrant_id}")
            return True

        except Exception as e:
            logger.error(f"Ошибка обновления PostgreSQL: {e}")
            session.rollback()
            return False
        finally:
            session.close()


# Singleton pattern
_dedup_instance: Optional[DeduplicationService] = None


def get_deduplication_service() -> DeduplicationService:
    """
    Получение singleton экземпляра сервиса дедупликации.

    Returns:
        Экземпляр DeduplicationService
    """
    global _dedup_instance
    if _dedup_instance is None:
        _dedup_instance = DeduplicationService()
    return _dedup_instance