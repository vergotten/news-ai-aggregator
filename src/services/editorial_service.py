"""Сервис редакторской обработки через Ollama models."""
import os
import json
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Optional, Dict, Any
import logging
from src.services.ollama_service import get_ollama_service

logger = logging.getLogger(__name__)


class EditorialService:
    """
    Сервис для редакторской обработки постов через GPT-OSS LLM.

    Использует XML-промпт из конфигурации для превращения сырых постов
    в полноценные новостные публикации в стиле Петербургской школы текста.
    """

    # Схема валидации ответа LLM
    REQUIRED_FIELDS = {
        'is_news': bool,
        'relevance_score': (int, float),
        'relevance_reason': str
    }

    OPTIONAL_FIELDS = {
        'original_summary': str,
        'rewritten_post': str,
        'title': str,
        'teaser': str,
        'image_prompt': str,
        'content_type': str
    }

    INVALID_VALUES = {'N/A', 'None', 'null', 'undefined', 'none', 'n/a', 'NULL', '', 'N', 'A'}

    def __init__(self, prompt_path: Optional[str] = None, telegram_prompt_path: Optional[str] = None, model: Optional[str] = None):
        """
        Инициализация редакторского сервиса.

        Args:
            prompt_path: Путь к XML файлу с промптом для статей.
            telegram_prompt_path: Путь к XML файлу с промптом для Telegram.
            model: Название модели Ollama.
        """
        self.model = model or os.getenv("LLM_MODEL") or os.getenv("OLLAMA_MODEL") or "gpt-oss:20b"
        self.ollama = get_ollama_service()
        self.ollama.model = self.model

        # Определение путей к промптам
        base_path = Path(__file__).parent.parent
        self.prompt_path = Path(prompt_path) if prompt_path else base_path / "config" / "editorial_prompt.xml"
        self.telegram_prompt_path = Path(telegram_prompt_path) if telegram_prompt_path else base_path / "config" / "telegram_prompt.xml"

        # Загрузка промптов
        self.system_prompt = self._load_prompt()
        self.telegram_system_prompt = self._load_telegram_prompt()

    def _load_prompt(self) -> str:
        """Загружает и парсит XML промпт в текстовую инструкцию."""
        if not self.prompt_path.exists():
            raise FileNotFoundError(f"Editorial prompt not found: {self.prompt_path}")

        try:
            tree = ET.parse(self.prompt_path)
            root = tree.getroot()

            system_role = root.find('.//system_role/identity').text.strip()
            objective = root.find('.//objective/goal').text.strip()

            steps = []
            for step in root.findall('.//pipeline/step'):
                step_num = step.get('number')
                step_name = step.find('name').text.strip()
                step_instruction = step.find('instruction').text.strip()
                steps.append(f"{step_num}. {step_name}\n{step_instruction}")

            system_prompt = f"""
{system_role}

ЦЕЛЬ: {objective}

ИНСТРУКЦИЯ:
{chr(10).join(steps)}

КРИТИЧЕСКИ ВАЖНО - ФОРМАТ ОТВЕТА:

Ты ОБЯЗАН вернуть ТОЛЬКО валидный JSON без какого-либо дополнительного текста.

Если статья ПОДХОДИТ для технического канала (релевантность > 0.6):
{{
  "is_news": true,
  "original_summary": "краткое резюме оригинала",
  "rewritten_post": "полностью переписанный текст от первого лица",
  "title": "цепляющий заголовок",
  "teaser": "краткая аннотация 2-3 предложения",
  "image_prompt": "описание для генерации изображения",
  "relevance_score": 0.85,
  "relevance_reason": "объяснение почему подходит",
  "content_type": "news|research|tutorial|humor|meme|discussion"
}}

Если статья НЕ ПОДХОДИТ (релевантность <= 0.6):
{{
  "is_news": false,
  "relevance_score": 0.3,
  "relevance_reason": "детальное объяснение почему не подходит",
  "original_summary": "краткое резюме оригинала"
}}

ПРАВИЛА:
1. ВСЕГДА заполняй is_news как true или false
2. ВСЕГДА заполняй relevance_score числом от 0.0 до 1.0
3. ВСЕГДА заполняй relevance_reason текстом (минимум 10 слов)
4. НИКОГДА не используй значения: "N/A", "None", null, пустые строки
5. Если is_news=true, ВСЕ поля обязательны и должны содержать значимый контент
6. Переписывай от первого лица множественного числа ("мы обнаружили")
7. Текст БЕЗ markdown форматирования (без **, *, #)
8. ТОЛЬКО JSON в ответе - без вступлений, объяснений, комментариев
"""
            return system_prompt.strip()

        except Exception as e:
            raise Exception(f"Ошибка парсинга XML промпта: {e}")

    def _load_telegram_prompt(self) -> str:
        """Загружает и парсит XML промпт для Telegram."""
        if not self.telegram_prompt_path.exists():
            raise FileNotFoundError(f"Telegram prompt not found: {self.telegram_prompt_path}")

        try:
            tree = ET.parse(self.telegram_prompt_path)
            root = tree.getroot()

            system_role = root.find('.//system_role/identity').text.strip()
            objective = root.find('.//objective/goal').text.strip()

            steps = []
            for step in root.findall('.//pipeline/step'):
                step_num = step.get('number')
                step_name = step.find('name').text.strip()
                step_instruction = step.find('instruction').text.strip()
                steps.append(f"{step_num}. {step_name}\n{step_instruction}")

            system_prompt = f"""
{system_role}

ЦЕЛЬ: {objective}

ИНСТРУКЦИЯ:
{chr(10).join(steps)}

ФОРМАТ ВЫВОДА (ТОЛЬКО JSON):
{{
  "telegram_title": "заголовок для Telegram",
  "telegram_content": "сжатый контент до 3500 символов",
  "telegram_hashtags": "#тег1 #тег2 #тег3",
  "telegram_formatted": "контент с markdown форматированием",
  "character_count": 1234
}}

ПРАВИЛА:
1. Максимум 3500 символов с пробелами
2. Используй markdown: **жирный**, *курсив*, `код`
3. 3-5 релевантных хештегов через пробел
4. НЕ используй эмодзи
5. Структурируй для мобильного чтения
6. ТОЛЬКО JSON без дополнительного текста
"""
            return system_prompt.strip()

        except Exception as e:
            raise Exception(f"Ошибка парсинга XML промпта для Telegram: {e}")

    def _clean_json_string(self, text: str) -> str:
        """
        Очистка текста для извлечения JSON.

        Args:
            text: Сырой ответ от LLM

        Returns:
            Очищенная JSON строка
        """
        text = text.strip()

        # Удаляем markdown code blocks
        if text.startswith('```'):
            text = text.split('```')[1]
            if text.startswith('json'):
                text = text[4:]

        # Ищем JSON между фигурными скобками
        start = text.find('{')
        end = text.rfind('}')

        if start == -1 or end == -1:
            # Если скобки не найдены, пытаем извлечь весь текст как JSON
            # Это сработает, если LLM вернул чистый JSON без markdown
            try:
                json.loads(text)  # Проверяем, является ли весь текст валидным JSON
                return text
            except:
                # Если не JSON, пытаем найти границы
                pass

        # Если скобки найдены, возвращаем JSON между ними
        return text[start:end+1]

    def _validate_and_fix_response(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Валидация и исправление ответа LLM.

        Args:
            data: Распарсенный JSON от LLM

        Returns:
            Валидированный и исправленный словарь
        """
        fixed_data = {}

        # Очистка невалидных значений
        for key, value in data.items():
            if isinstance(value, str):
                value = value.strip()
                if value in self.INVALID_VALUES or not value:
                    value = None
            fixed_data[key] = value

        # Проверка обязательных полей
        for field, field_type in self.REQUIRED_FIELDS.items():
            if field not in fixed_data or fixed_data[field] is None:
                # Автоматическое восстановление обязательных полей
                if field == 'is_news':
                    score = fixed_data.get('relevance_score', 0.0)
                    if isinstance(score, (int, float)):
                        fixed_data['is_news'] = score > 0.6
                    else:
                        fixed_data['is_news'] = False
                elif field == 'relevance_score':
                    if fixed_data.get('is_news'):
                        fixed_data['relevance_score'] = 0.7
                    else:
                        fixed_data['relevance_score'] = 0.3
                elif field == 'relevance_reason':
                    if fixed_data.get('is_news'):
                        fixed_data['relevance_reason'] = "Статья соответствует критериям технического канала"
                    else:
                        fixed_data['relevance_reason'] = "Статья не соответствует критериям отбора"
                continue

            # Проверка типа
            if not isinstance(fixed_data[field], field_type):
                # Попытка преобразования типа
                if field == 'relevance_score' and isinstance(fixed_data[field], str):
                    try:
                        fixed_data[field] = float(fixed_data[field])
                    except ValueError:
                        fixed_data[field] = 0.7 if fixed_data.get('is_news') else 0.3
                elif field == 'is_news' and isinstance(fixed_data[field], str):
                    fixed_data[field] = fixed_data[field].lower() in ('true', '1', 'yes')

        # Нормализация relevance_score
        if isinstance(fixed_data.get('relevance_score'), (int, float)):
            fixed_data['relevance_score'] = max(0.0, min(1.0, float(fixed_data['relevance_score'])))

        # Валидация опциональных полей для новостей
        if fixed_data.get('is_news'):
            for field in ['title', 'rewritten_post', 'teaser', 'image_prompt']:
                if not fixed_data.get(field):
                    # Заполняем пустые поля значениями по умолчанию
                    if field == 'title':
                        fixed_data[field] = "Техническая новость"
                    elif field == 'rewritten_post':
                        fixed_data[field] = "Содержание статьи в обработке"
                    elif field == 'teaser':
                        fixed_data[field] = "Краткое описание статьи"
                    elif field == 'image_prompt':
                        fixed_data[field] = "Технологическая иллюстрация"

        return fixed_data

    def _parse_json_response(self, response: str) -> Dict[str, Any]:
        """
        Надежный парсинг JSON-ответа от LLM с валидацией.

        Args:
            response: Текстовый ответ от LLM

        Returns:
            Словарь с распарсенными и валидированными данными
        """
        try:
            # Очистка и извлечение JSON
            json_str = self._clean_json_string(response)

            # Парсинг JSON
            result = json.loads(json_str)

            if not isinstance(result, dict):
                raise ValueError("JSON is not a dictionary")

            # Валидация и исправление
            result = self._validate_and_fix_response(result)

            return result

        except json.JSONDecodeError as e:
            # Попытка исправить распространенные ошибки
            try:
                # Замена одинарных кавычек на двойные
                fixed_json = response.replace("'", '"').replace('\n', ' ')
                fixed_json = self._clean_json_string(fixed_json)
                result = json.loads(fixed_json)
                result = self._validate_and_fix_response(result)
                return result
            except Exception:
                return {'error': f'JSON decode error: {str(e)}'}

        except ValueError as e:
            return {'error': f'JSON validation error: {str(e)}'}

        except Exception as e:
            return {'error': f'Unknown parsing error: {str(e)}'}

    def process_post(
            self,
            title: str,
            content: str,
            source: str = "unknown",
            default_relevant: bool = False
    ) -> Dict[str, Any]:
        """
        Обрабатывает пост через редакторский конвейер.

        Args:
            title: Заголовок оригинального поста
            content: Текст поста
            source: Источник (reddit, telegram, medium, habr)
            default_relevant: Считать ли контент релевантным по умолчанию (для Habr)

        Returns:
            dict: {
                'is_news': bool,
                'original_summary': str | None,
                'rewritten_post': str | None,
                'title': str | None,
                'teaser': str | None,
                'image_prompt': str | None,
                'relevance_score': float,
                'relevance_reason': str,
                'content_type': str | None,
                'processing_time': float,
                'error': str | None
            }
        """
        import time
        start_time = time.time()

        # ДОБАВЛЕНО: Логирование входных данных
        logger.info(f"[EDITORIAL] Начало обработки поста из {source}")
        logger.debug(f"[EDITORIAL] Заголовок: {title[:100]}...")
        logger.debug(f"[EDITORIAL] Контент: {content[:500]}...")
        logger.debug(f"[EDITORIAL] Длина контента: {len(content)} символов")
        logger.debug(f"[EDITORIAL] Default relevant: {default_relevant}")

        # Подготовка входного текста
        post_content = f"Заголовок: {title}\n\nТекст:\n{content}"

        # Формирование промпта
        user_prompt = f"""Обработай следующий технический пост:

<<<
{post_content}
>>>

ВАЖНО: Верни ТОЛЬКО JSON без дополнительного текста.
Все обязательные поля должны быть заполнены валидными значениями.
"""

        try:
            # Генерация с повышенной температурой для креативности
            logger.debug(f"[EDITORIAL] Отправка запроса к LLM модель: {self.model}")
            response = self.ollama.generate(
                prompt=user_prompt,
                system=self.system_prompt,
                temperature=0.7,  # Повышено для креативной переработки
                max_tokens=8000
            )

            # ДОБАВЛЕНО: Логирование ответа LLM
            logger.debug(f"[EDITORIAL] Полный ответ LLM: {response[:1000] if response else 'EMPTY'}...")
            logger.debug(f"[EDITORIAL] Длина ответа LLM: {len(response) if response else 0} символов")

            if not response:
                # Для Habr все равно сохраняем с базовыми данными
                logger.warning("[EDITORIAL] Пустой ответ от LLM")
                return {
                    'is_news': True if default_relevant else False,
                    'original_summary': content[:500] + "..." if len(content) > 500 else content,
                    'rewritten_post': content,
                    'title': title,
                    'teaser': content[:200] + "..." if len(content) > 200 else content,
                    'image_prompt': "Технологическая иллюстрация",
                    'relevance_score': 0.8 if default_relevant else 0.0,
                    'relevance_reason': "LLM вернул пустой ответ" if not default_relevant else "Статья с Habr, сохранена по умолчанию",
                    'content_type': 'news',
                    'processing_time': time.time() - start_time,
                    'error': 'Empty response from LLM'
                }

            # Парсинг с валидацией
            result = self._parse_json_response(response)

            # ДОБАВЛЕНО: Логирование распарсенного результата
            logger.debug(f"[EDITORIAL] Распарсенный результат: {result}")

            if result.get('error'):
                # Для Habr все равно сохраняем с базовыми данными
                logger.error(f"[EDITORIAL] Ошибка парсинга LLM ответа: {result['error']}")
                return {
                    'is_news': True if default_relevant else False,
                    'original_summary': content[:500] + "..." if len(content) > 500 else content,
                    'rewritten_post': content,
                    'title': title,
                    'teaser': content[:200] + "..." if len(content) > 200 else content,
                    'image_prompt': "Технологическая иллюстрация",
                    'relevance_score': 0.8 if default_relevant else 0.0,
                    'relevance_reason': f"Ошибка парсинга: {result['error']}" if not default_relevant else "Статья с Habr, сохранена по умолчанию",
                    'content_type': 'news',
                    'processing_time': time.time() - start_time,
                    'error': result['error']
                }

            # ДОБАВЛЕНО: Проверка, что rewritten_post отличается от оригинала
            if result.get('rewritten_post'):
                original_len = len(content)
                rewritten_len = len(result['rewritten_post'])
                similarity = 1.0 - abs(original_len - rewritten_len) / max(original_len, rewritten_len, 1)

                logger.debug(f"[EDITORIAL] Длина оригинала: {original_len} символов")
                logger.debug(f"[EDITORIAL] Длина обработанного: {rewritten_len} символов")
                logger.debug(f"[EDITORIAL] Сходство по длине: {similarity:.2f}")

                if similarity > 0.9:  # Если тексты очень похожи по длине
                    logger.warning("[EDITORIAL] Обработанный текст слишком похож на оригинал!")

                # ДОБАВЛЕНО: Логирование начала обработанного текста
                logger.debug(f"[EDITORIAL] Начало обработанного текста: {result['rewritten_post'][:500]}...")

            # Добавляем метаданные
            processing_time = time.time() - start_time
            result['processing_time'] = processing_time
            result['error'] = None

            # КЛЮЧЕВОЕ ИЗМЕНЕНИЕ: Для Habr всегда устанавливаем is_news=True
            if default_relevant:
                result['is_news'] = True
                result['relevance_score'] = max(result.get('relevance_score', 0.0), 0.8)  # Минимум 0.8
                if result.get('relevance_score') < 0.8:
                    result['relevance_reason'] = f"Статья с Habr (оригинальная оценка: {result.get('relevance_score', 0.0):.2f})"

            logger.info(f"[EDITORIAL] Обработка завершена за {processing_time:.2f}с")
            logger.debug(f"[EDITORIAL] Итоговый результат: {result}")

            return result

        except Exception as e:
            # Даже при ошибке сохраняем Habr статьи
            logger.error(f"[EDITORIAL] Критическая ошибка обработки: {e}")
            logger.exception("[EDITORIAL] Stack trace:")
            return {
                'is_news': True if default_relevant else False,
                'original_summary': content[:500] + "..." if len(content) > 500 else content,
                'rewritten_post': content,
                'title': title,
                'teaser': content[:200] + "..." if len(content) > 200 else content,
                'image_prompt': "Технологическая иллюстрация",
                'relevance_score': 0.8 if default_relevant else 0.0,
                'relevance_reason': f"Критическая ошибка: {str(e)}" if not default_relevant else "Статья с Habr, сохранена несмотря на ошибку",
                'content_type': 'news',
                'processing_time': time.time() - start_time,
                'error': str(e)
            }

    def format_for_telegram(self, title: str, content: str) -> Dict[str, Any]:
        """
        Форматирует обработанную статью для Telegram.

        Args:
            title: Заголовок обработанной статьи
            content: Содержание обработанной статьи

        Returns:
            dict с форматированным контентом для Telegram
        """
        import time
        start_time = time.time()

        # ДОБАВЛЕНО: Логирование входных данных
        logger.info(f"[EDITORIAL] Начало форматирования для Telegram")
        logger.debug(f"[EDITORIAL] Заголовок: {title[:100]}...")
        logger.debug(f"[EDITORIAL] Контент: {content[:500]}...")
        logger.debug(f"[EDITORIAL] Длина контента: {len(content)} символов")

        post_content = f"Заголовок: {title}\n\nТекст:\n{content}"

        user_prompt = f"""Отформатируй следующую статью для Telegram:

<<<
{post_content}
>>>

ВАЖНО: Верни ТОЛЬКО JSON. Максимум 3500 символов."""

        try:
            response = self.ollama.generate(
                prompt=user_prompt,
                system=self.telegram_system_prompt,
                temperature=0.3,
                max_tokens=4000
            )

            # ДОБАВЛЕНО: Логирование ответа LLM
            logger.debug(f"[EDITORIAL] Ответ LLM для Telegram: {response[:1000] if response else 'EMPTY'}...")

            if not response:
                return {
                    'error': 'Empty response from LLM',
                    'processing_time': time.time() - start_time
                }

            result = self._parse_json_response(response)

            if result.get('error'):
                return {**result, 'processing_time': time.time() - start_time}

            # Проверка обязательных полей
            required_fields = ['telegram_title', 'telegram_content', 'telegram_hashtags',
                             'telegram_formatted', 'character_count']
            missing = [f for f in required_fields if not result.get(f)]

            if missing:
                return {
                    'error': f'Missing fields: {missing}',
                    'processing_time': time.time() - start_time
                }

            # ДОБАВЛЕНО: Логирование результата
            logger.debug(f"[EDITORIAL] Результат форматирования для Telegram: {result}")

            processing_time = time.time() - start_time
            result['processing_time'] = processing_time
            result['error'] = None

            return result

        except Exception as e:
            logger.error(f"[EDITORIAL] Ошибка форматирования для Telegram: {e}")
            logger.exception("[EDITORIAL] Stack trace:")
            return {
                'error': str(e),
                'processing_time': time.time() - start_time
            }


# Singleton
_editorial_instance: Optional[EditorialService] = None


def get_editorial_service() -> EditorialService:
    """Получение singleton экземпляра редакторского сервиса."""
    global _editorial_instance
    if _editorial_instance is None:
        _editorial_instance = EditorialService()
    return _editorial_instance