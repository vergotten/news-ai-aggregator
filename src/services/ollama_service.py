"""Сервис для работы с Ollama LLM."""
import os
import logging
from typing import Optional, List, Dict, Any
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

logger = logging.getLogger(__name__)


class OllamaService:
    """
    Клиент для взаимодействия с Ollama API.

    Предоставляет методы для:
    - генерации текста через /api/generate
    - чат-режим через /api/chat (с поддержкой system prompts)
    - создания embeddings
    - суммаризации
    - извлечения ключевых слов
    - анализа тональности
    """

    def __init__(
            self,
            base_url: Optional[str] = None,
            model: Optional[str] = None,
            timeout: int = 300,
            max_retries: int = 3
    ):
        """
        Инициализация Ollama сервиса.

        Args:
            base_url: URL Ollama API. Если None, берется из OLLAMA_BASE_URL env.
            model: Название модели для генерации текста. Если None, из env.
            timeout: Таймаут запроса в секундах.
            max_retries: Количество попыток при ошибке.
        """
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://ollama:11434")
        self.model = model or os.getenv("OLLAMA_MODEL", "gpt-oss:20b")  # llama3.2:3b
        self.timeout = timeout

        # Настройка HTTP сессии с автоматическими повторами
        self.session = requests.Session()
        retry_strategy = Retry(
            total=max_retries,
            backoff_factor=1,
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"]
        )
        adapter = HTTPAdapter(max_retries=retry_strategy)
        self.session.mount("http://", adapter)
        self.session.mount("https://", adapter)

        logger.info(f"Ollama сервис инициализирован: {self.base_url}, модель: {self.model}")

    def health_check(self) -> bool:
        """
        Проверка доступности Ollama сервиса.

        Returns:
            True если сервис доступен, False иначе.
        """
        try:
            response = self.session.get(f"{self.base_url}/api/tags", timeout=5)
            return response.status_code == 200
        except requests.RequestException as e:
            logger.error(f"Ollama health check failed: {e}")
            return False

    def chat(
            self,
            messages: List[Dict[str, str]],
            temperature: float = 0.7,
            max_tokens: Optional[int] = None,
            stream: bool = False
    ) -> Optional[str]:
        """
        Чат-режим с поддержкой system prompts через /api/chat.

        Args:
            messages: Список сообщений в формате [{"role": "system/user/assistant", "content": "..."}]
            temperature: Температура сэмплирования (0.0 - детерминировано, 1.0 - креативно).
            max_tokens: Максимальное количество токенов для генерации.
            stream: Потоковая генерация (не реализовано).

        Returns:
            Сгенерированный текст или None при ошибке.

        Examples:
            >>> messages = [
            ...     {"role": "system", "content": "You are a helpful assistant"},
            ...     {"role": "user", "content": "Hello!"}
            ... ]
            >>> response = ollama.chat(messages)
        """
        if stream:
            raise NotImplementedError("Потоковая генерация не реализована")

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        try:
            logger.debug(f"Отправка chat запроса к {self.base_url}/api/chat")
            response = self.session.post(
                f"{self.base_url}/api/chat",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()

            # В /api/chat ответ находится в message.content
            if "message" in data and "content" in data["message"]:
                return data["message"]["content"].strip()
            else:
                logger.error(f"Неожиданный формат ответа: {data}")
                return None

        except requests.Timeout:
            logger.error(f"Ollama request timeout after {self.timeout}s")
            return None
        except requests.RequestException as e:
            logger.error(f"Ollama request failed: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Response body: {e.response.text[:500]}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Invalid response format: {e}")
            return None

    def generate(
            self,
            prompt: str,
            system: Optional[str] = None,
            temperature: float = 0.7,
            max_tokens: Optional[int] = None,
            stream: bool = False
    ) -> Optional[str]:
        """
        Генерация текста через LLM.

        Если передан system prompt, автоматически использует /api/chat,
        иначе использует /api/generate для простых запросов.

        Args:
            prompt: Пользовательский промт (основной запрос).
            system: Системный промт (инструкция для модели).
            temperature: Температура сэмплирования (0.0 - детерминировано, 1.0 - креативно).
            max_tokens: Максимальное количество токенов для генерации.
            stream: Потоковая генерация (не реализовано).

        Returns:
            Сгенерированный текст или None при ошибке.
        """
        # Если есть system prompt, используем chat API
        if system:
            messages = [
                {"role": "system", "content": system},
                {"role": "user", "content": prompt}
            ]
            return self.chat(messages, temperature, max_tokens, stream)

        # Иначе используем generate API
        if stream:
            raise NotImplementedError("Потоковая генерация не реализована")

        payload = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": temperature
            }
        }

        if max_tokens:
            payload["options"]["num_predict"] = max_tokens

        try:
            logger.debug(f"Отправка generate запроса к {self.base_url}/api/generate")
            response = self.session.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout
            )
            response.raise_for_status()

            data = response.json()
            return data.get("response", "").strip()

        except requests.Timeout:
            logger.error(f"Ollama request timeout after {self.timeout}s")
            return None
        except requests.RequestException as e:
            logger.error(f"Ollama request failed: {e}")
            if hasattr(e, 'response') and hasattr(e.response, 'text'):
                logger.error(f"Response body: {e.response.text[:500]}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Invalid response format: {e}")
            return None

    def get_embedding(self, text: str, model: Optional[str] = None) -> Optional[List[float]]:
        """
        Генерация embedding вектора для текста.

        Embeddings используются для семантического поиска и сравнения текстов.
        Модель nomic-embed-text специализирована для создания векторных представлений.

        Args:
            text: Входной текст для векторизации.
            model: Название embedding модели. Если None, использует env или nomic-embed-text.

        Returns:
            Список из 768 чисел (вектор) или None при ошибке.
        """
        embedding_model = model or os.getenv("EMBEDDING_MODEL", "nomic-embed-text")

        payload = {
            "model": embedding_model,
            "prompt": text
        }

        try:
            response = self.session.post(
                f"{self.base_url}/api/embeddings",
                json=payload,
                timeout=30
            )
            response.raise_for_status()

            data = response.json()
            embedding = data.get("embedding")

            if not embedding:
                logger.error("Ollama не вернул embedding")
                return None

            logger.debug(f"Получен embedding размерности {len(embedding)}")
            return embedding

        except requests.RequestException as e:
            logger.error(f"Ошибка получения embedding: {e}")
            return None
        except (KeyError, ValueError) as e:
            logger.error(f"Неверный формат ответа embedding: {e}")
            return None

    def summarize(self, text: str, max_length: int = 200) -> Optional[str]:
        """
        Создание краткого содержания текста.

        Args:
            text: Входной текст для суммаризации.
            max_length: Примерная длина саммари в словах.

        Returns:
            Краткое содержание или None при ошибке.
        """
        system = "Ты помощник для создания кратких саммари. Выводи только саммари без вступлений."
        prompt = f"Создай краткое содержание (~{max_length} слов) следующего текста:\n\n{text}"

        # Низкая температура для более детерминированного результата
        return self.generate(prompt, system=system, temperature=0.3)

    def extract_keywords(self, text: str, count: int = 10) -> Optional[str]:
        """
        Извлечение ключевых слов из текста.

        Args:
            text: Входной текст.
            count: Количество ключевых слов для извлечения.

        Returns:
            Ключевые слова через запятую или None при ошибке.
        """
        system = "Ты помощник для извлечения ключевых слов. Выводи только слова через запятую."
        prompt = f"Извлеки {count} самых важных ключевых слов из текста:\n\n{text}"

        return self.generate(prompt, system=system, temperature=0.2, max_tokens=100)

    def sentiment_analysis(self, text: str) -> Optional[str]:
        """
        Анализ тональности текста.

        Args:
            text: Входной текст.

        Returns:
            Одно из значений: "positive", "negative", "neutral" или None при ошибке.
        """
        system = "Ты классификатор тональности. Отвечай только одним словом: positive, negative или neutral."
        prompt = f"Определи тональность текста:\n\n{text}"

        response = self.generate(prompt, system=system, temperature=0.1, max_tokens=10)

        if response:
            return response.lower().strip()
        return None


# Singleton pattern
_ollama_instance: Optional[OllamaService] = None


def get_ollama_service() -> OllamaService:
    """
    Получение singleton экземпляра Ollama сервиса.

    Returns:
        Экземпляр OllamaService
    """
    global _ollama_instance
    if _ollama_instance is None:
        _ollama_instance = OllamaService()
    return _ollama_instance