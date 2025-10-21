"""Сервис редакторской обработки через Ollama models."""
import os
import logging
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Dict, Any
from src.services.ollama_service import get_ollama_service

logger = logging.getLogger(__name__)


class EditorialService:
    """
    Сервис для редакторской обработки постов через GPT-OSS LLM.

    Использует XML-промпт из конфигурации для превращения сырых постов
    в полноценные новостные публикации в стиле Петербургской школы текста.
    """

    def __init__(self, prompt_path: Optional[str] = None, model: Optional[str] = None):
        """
        Инициализация редакторского сервиса.

        Args:
            prompt_path: Путь к XML файлу с промптом.
                        Если None, ищет в config/editorial_prompt.xml
            model: Название модели Ollama. Если None, берет из env или использует gpt-oss:20b
        """
        # Получаем модель из env или используем дефолтную
        self.model = model or os.getenv("OLLAMA_MODEL", "gpt-oss:20b")  # llama3.2:3b
        self.ollama = get_ollama_service()
        self.ollama.model = self.model  # Переопределяем модель

        # Определение пути к промпту
        if prompt_path is None:
            base_path = Path(__file__).parent.parent
            self.prompt_path = base_path / "config" / "editorial_prompt.xml"
        else:
            self.prompt_path = Path(prompt_path)

        # Загрузка промпта
        self.system_prompt = self._load_prompt()
        logger.info(f"Редакторский сервис инициализирован: модель={self.model}")

    def _load_prompt(self) -> str:
        """
        Загружает и парсит XML промпт в текстовую инструкцию.

        Returns:
            Системный промпт для LLM
        """
        if not self.prompt_path.exists():
            logger.error(f"Промпт не найден: {self.prompt_path}")
            raise FileNotFoundError(f"Editorial prompt not found: {self.prompt_path}")

        try:
            tree = ET.parse(self.prompt_path)
            root = tree.getroot()

            # Извлекаем ключевые секции
            system_role = root.find('.//system_role/identity').text.strip()
            objective = root.find('.//objective/goal').text.strip()

            # Собираем pipeline
            steps = []
            for step in root.findall('.//pipeline/step'):
                step_num = step.get('number')
                step_name = step.find('name').text.strip()
                step_instruction = step.find('instruction').text.strip()
                steps.append(f"{step_num}. {step_name}\n{step_instruction}")

            # Собираем финальный промпт
            system_prompt = f"""
{system_role}

ЦЕЛЬ: {objective}

ИНСТРУКЦИЯ:

{chr(10).join(steps)}

ФОРМАТ ВЫВОДА:
Строго JSON. Никакого текста до или после JSON-блока.

Если НОВОСТЬ:
{{
  "is_news": true,
  "original_summary": "...",
  "rewritten_post": "...",
  "title": "...",
  "teaser": "...",
  "image_prompt": "..."
}}

Если НЕ НОВОСТЬ:
{{
  "is_news": false
}}

ВАЖНО:
- Факты превыше всего
- Текст живой, но не развлекательный
- Заголовок цепляет смыслом, не кликбейтом
- Всегда переписывай своими словами
- Только JSON в ответе, ничего более
"""

            logger.info("XML промпт загружен и обработан")
            return system_prompt.strip()

        except Exception as e:
            logger.error(f"Ошибка парсинга XML промпта: {e}")
            raise

    def process_post(
            self,
            title: str,
            content: str,
            source: str = "unknown"
    ) -> Dict[str, Any]:
        """
        Обрабатывает пост через редакторский конвейер.

        Args:
            title: Заголовок оригинального поста
            content: Текст поста
            source: Источник (reddit, telegram, medium)

        Returns:
            dict: {
                'is_news': bool,
                'original_summary': str | None,
                'rewritten_post': str | None,
                'title': str | None,
                'teaser': str | None,
                'image_prompt': str | None,
                'processing_time': float,
                'error': str | None
            }
        """
        logger.info("=" * 70)
        logger.info("РЕДАКТОРСКАЯ ОБРАБОТКА")
        logger.info("=" * 70)
        logger.info(f"   Заголовок: {title[:60]}...")
        logger.info(f"   Источник: {source}")
        logger.info(f"   Модель: {self.model}")
        logger.info(f"   Длина текста: {len(content)} символов")

        import time
        start_time = time.time()

        # Подготовка входного текста
        post_content = f"Заголовок: {title}\n\nТекст:\n{content}"

        # Лимит текста для LLM
        max_length = 3000
        if len(post_content) > max_length:
            post_content = post_content[:max_length] + "\n\n[текст обрезан]"
            logger.info(f"   Текст обрезан до {max_length} символов")

        # Формирование финального промпта
        user_prompt = f"""Обработай следующий пост:

<<<
{post_content}
>>>

Верни ТОЛЬКО JSON, без дополнительного текста."""

        try:
            logger.info("   Отправка запроса к GPT-OSS...")

            # Генерация через Ollama
            response = self.ollama.generate(
                prompt=user_prompt,
                system=self.system_prompt,
                temperature=0.3,  # Низкая для детерминированности
                max_tokens=2000
            )

            if not response:
                logger.error("Пустой ответ от LLM")
                return {
                    'is_news': False,
                    'error': 'Empty response from LLM',
                    'processing_time': time.time() - start_time
                }

            logger.info("   Ответ получен, парсинг JSON...")

            # Парсинг JSON из ответа
            # Очистка от возможного мусора до/после JSON
            response_clean = response.strip()

            # Поиск JSON блока
            json_start = response_clean.find('{')
            json_end = response_clean.rfind('}') + 1

            if json_start == -1 or json_end == 0:
                logger.error("JSON не найден в ответе")
                logger.debug(f"   Ответ: {response[:200]}")
                return {
                    'is_news': False,
                    'error': 'Invalid JSON response',
                    'processing_time': time.time() - start_time
                }

            json_str = response_clean[json_start:json_end]
            result = json.loads(json_str)

            processing_time = time.time() - start_time
            result['processing_time'] = processing_time
            result['error'] = None

            # Логирование результата
            if result.get('is_news'):
                logger.info("   ✓ Новость распознана и обработана")
                logger.info(f"   Новый заголовок: {result.get('title', 'N/A')}")
                logger.info(f"   Время обработки: {processing_time:.2f}s")
            else:
                logger.info("   ✗ Не является новостью")
                logger.info(f"   Время обработки: {processing_time:.2f}s")

            logger.info("=" * 70)
            logger.info("РЕДАКТОРСКАЯ ОБРАБОТКА ЗАВЕРШЕНА")
            logger.info("=" * 70)

            return result

        except json.JSONDecodeError as e:
            logger.error(f"Ошибка парсинга JSON: {e}")
            logger.debug(f"   Ответ LLM: {response[:500]}")
            return {
                'is_news': False,
                'error': f'JSON decode error: {str(e)}',
                'processing_time': time.time() - start_time
            }
        except Exception as e:
            logger.error(f"Критическая ошибка: {e}")
            logger.exception("Stack trace:")
            return {
                'is_news': False,
                'error': str(e),
                'processing_time': time.time() - start_time
            }


# Singleton
_editorial_instance: Optional[EditorialService] = None


def get_editorial_service() -> EditorialService:
    """
    Получение singleton экземпляра редакторского сервиса.

    Returns:
        Экземпляр EditorialService с GPT-OSS
    """
    global _editorial_instance
    if _editorial_instance is None:
        _editorial_instance = EditorialService()
    return _editorial_instance