"""Telegram scraper для парсинга каналов.

⚠️ В РАЗРАБОТКЕ - Требует настройки Telegram API
"""
import logging
import asyncio
from datetime import datetime
from typing import List, Dict, Any, Optional, Callable
from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, ChatAdminRequiredError, ApiIdInvalidError, PhoneNumberInvalidError
import sys
import os

# Добавляем корневую директорию в sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from src.models.database import get_session, TelegramMessage
from src.utils.log_manager import get_log_manager

# Настройка логирования
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('/app/logs/telegram_scraper.log', mode='a')
    ]
)
logger = logging.getLogger(__name__)

class TelegramScraper:
    """Scraper для Telegram каналов."""

    def __init__(
        self,
        api_id: int,
        api_hash: str,
        phone: str,
        session_name: str = "news_aggregator",
        log_callback: Optional[Callable[[str, str], None]] = None,
        session_id: Optional[str] = None
    ):
        """
        Инициализация Telegram scraper.

        Args:
            api_id: Telegram API ID
            api_hash: Telegram API Hash
            phone: Номер телефона
            session_name: Имя сессии
            log_callback: Callback для логирования
            session_id: ID сессии для логов
        """
        self.api_id = api_id
        self.api_hash = api_hash
        self.phone = phone
        self.session_name = session_name
        self.log_callback = log_callback
        self.session_id = session_id

        # Инициализация лог менеджера
        self.log_manager = get_log_manager()

        # Статистика
        self.stats = {
            'messages_saved': 0,
            'messages_skipped': 0,
            'errors': 0,
            'channels_processed': 0
        }

        # Клиент Telegram
        self.client = None

        self.log("Telegram scraper инициализирован")

    def log(self, message: str, level: str = "INFO"):
        """Универсальное логирование."""
        # Лог в стандартный логгер
        logger_func = getattr(logger, level.lower(), logger.info)
        logger_func(message)

        # Лог в менеджер
        if self.log_manager:
            try:
                self.log_manager.add_log(message, level, self.session_id)
            except Exception as e:
                logger.warning(f"Ошибка в лог менеджере: {e}")

        # Callback для UI
        if self.log_callback:
            try:
                self.log_callback(message, level)
            except Exception as e:
                logger.warning(f"Ошибка в log_callback: {e}")

    async def connect(self) -> bool:
        """Подключиться к Telegram."""
        try:
            self.log("Подключение к Telegram...")

            self.client = TelegramClient(
                self.session_name,
                self.api_id,
                self.api_hash
            )

            await self.client.start(phone=self.phone)

            self.log("✅ Успешное подключение к Telegram", "SUCCESS")
            return True

        except ApiIdInvalidError:
            self.log("❌ Неверный API ID", "ERROR")
            return False
        except PhoneNumberInvalidError:
            self.log("❌ Неверный номер телефона", "ERROR")
            return False
        except Exception as e:
            self.log(f"❌ Ошибка подключения к Telegram: {e}", "ERROR")
            return False

    async def disconnect(self):
        """Отключиться от Telegram."""
        if self.client:
            await self.client.disconnect()
            self.log("Отключение от Telegram")

    def save_message(self, message_data: Dict[str, Any]) -> bool:
        """Сохранить сообщение в базу данных."""
        try:
            session = get_session()

            # Проверяем, существует ли уже сообщение
            existing = session.query(TelegramMessage).filter_by(
                message_id=message_data['message_id'],
                channel=message_data['channel']
            ).first()

            if existing:
                self.log(f"Сообщение уже существует: {message_data['message_id']}", "DEBUG")
                self.stats['messages_skipped'] += 1
                return False

            # Создаем новое сообщение
            message = TelegramMessage(
                message_id=message_data['message_id'],
                text=message_data.get('text', ''),
                sender=message_data.get('sender', ''),
                channel=message_data['channel'],
                channel_username=message_data.get('channel_username', ''),
                channel_title=message_data.get('channel_title', ''),
                date=message_data['date'],
                scraped_at=datetime.utcnow(),
                has_media=message_data.get('has_media', False),
                media_type=message_data.get('media_type', ''),
                views=message_data.get('views', 0),
                forwards=message_data.get('forwards', 0),
                replies=message_data.get('replies', 0)
            )

            session.add(message)
            session.commit()

            self.log(f"✅ Сохранено сообщение: {message_data['message_id']} из {message_data['channel']}", "DEBUG")
            self.stats['messages_saved'] += 1
            return True

        except Exception as e:
            self.log(f"❌ Ошибка сохранения сообщения: {e}", "ERROR")
            self.stats['errors'] += 1
            return False
        finally:
            if 'session' in locals():
                session.close()

    async def scrape_channel(self, channel_username: str, limit: int = 100) -> Dict[str, Any]:
        """
        Спарсить один канал.

        Args:
            channel_username: Юзернейм канала
            limit: Лимит сообщений

        Returns:
            Результат парсинга
        """
        try:
            self.log(f"Начало парсинга канала: {channel_username}")

            # Получаем информацию о канале
            try:
                entity = await self.client.get_entity(channel_username)
                channel_title = entity.title
                self.log(f"Канал найден: {channel_title}")
            except Exception as e:
                self.log(f"❌ Канал не найден: {channel_username} - {e}", "ERROR")
                return {
                    'success': False,
                    'error': f'Канал не найден: {e}',
                    'channel': channel_username
                }

            # Получаем сообщения
            messages_count = 0
            async for message in self.client.iter_messages(
                entity,
                limit=limit,
                reverse=True  # От старых к новым
            ):
                # Пропускаем сервисные сообщения
                if message.message is None:
                    continue

                message_data = {
                    'message_id': message.id,
                    'text': message.text,
                    'sender': getattr(message.sender, 'username', None) or getattr(message.sender, 'first_name', 'Unknown'),
                    'channel': channel_username,
                    'channel_username': channel_username,
                    'channel_title': channel_title,
                    'date': message.date,
                    'has_media': bool(message.media),
                    'media_type': type(message.media).__name__ if message.media else None,
                    'views': getattr(message, 'views', 0),
                    'forwards': getattr(message, 'forwards', 0),
                    'replies': getattr(message, 'replies', 0)
                }

                # Сохраняем сообщение
                self.save_message(message_data)
                messages_count += 1

                # Небольшая задержка между сообщениями
                await asyncio.sleep(0.1)

            self.stats['channels_processed'] += 1

            result = {
                'success': True,
                'channel': channel_username,
                'channel_title': channel_title,
                'messages_found': messages_count,
                'messages_saved': self.stats['messages_saved'],
                'messages_skipped': self.stats['messages_skipped'],
                'errors': self.stats['errors']
            }

            self.log(f"✅ Канал {channel_username} обработан: {messages_count} сообщений", "SUCCESS")
            return result

        except FloodWaitError as e:
            wait_time = e.seconds
            self.log(f"⏳ Flood control: ждем {wait_time} секунд", "WARNING")
            await asyncio.sleep(wait_time)
            return await self.scrape_channel(channel_username, limit)

        except ChatAdminRequiredError:
            self.log(f"❌ Нет доступа к каналу: {channel_username}", "ERROR")
            return {
                'success': False,
                'error': 'Нет доступа к каналу (требуются права администратора)',
                'channel': channel_username
            }

        except Exception as e:
            self.log(f"❌ Ошибка парсинга канала {channel_username}: {e}", "ERROR")
            return {
                'success': False,
                'error': str(e),
                'channel': channel_username
            }

    async def scrape_channels(self, channels: List[str], limit: int = 100) -> List[Dict[str, Any]]:
        """
        Спарсить несколько каналов.

        Args:
            channels: Список каналов
            limit: Лимит сообщений на канал

        Returns:
            Список результатов по каждому каналу
        """
        results = []

        self.log(f"Начало парсинга {len(channels)} каналов")

        for i, channel in enumerate(channels, 1):
            self.log(f"Обработка канала {i}/{len(channels)}: {channel}")

            try:
                result = await self.scrape_channel(channel, limit)
                results.append(result)

                # Задержка между каналами
                if i < len(channels):
                    await asyncio.sleep(2)

            except Exception as e:
                self.log(f"❌ Критическая ошибка при обработке канала {channel}: {e}", "ERROR")
                results.append({
                    'success': False,
                    'error': str(e),
                    'channel': channel
                })

        # Итоговая статистика
        total_saved = sum(r.get('messages_saved', 0) for r in results if r.get('success'))
        total_skipped = sum(r.get('messages_skipped', 0) for r in results if r.get('success'))
        total_errors = sum(r.get('errors', 0) for r in results if r.get('success'))

        self.log(f"🎉 Парсинг завершен")
        self.log(f"Всего сохранено: {total_saved}")
        self.log(f"Пропущено: {total_skipped}")
        self.log(f"Ошибок: {total_errors}")

        return results

async def scrape_telegram_channels(
    channels: List[str],
    limit: int = 100,
    delay: int = 2,
    enable_llm: bool = False,
    log_callback: Optional[Callable[[str, str], None]] = None,
    session_id: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Основная функция для парсинга Telegram каналов.

    ⚠️ В РАЗРАБОТКЕ - Требует настройки Telegram API

    Args:
        channels: Список каналов для парсинга
        limit: Лимит сообщений на канал
        delay: Задержка между каналами (в секундах)
        enable_llm: Включить LLM обработку (пока не реализовано)
        log_callback: Callback для логирования
        session_id: ID сессии для логов

    Returns:
        Список результатов по каждому каналу
    """
    # Проверяем наличие настроек
    try:
        from src.config.config import get_config
        config = get_config()
    except Exception as e:
        logger.error(f"Ошибка загрузки конфигурации: {e}")
        return [{
            'success': False,
            'error': 'Ошибка загрузки конфигурации',
            'channel': 'system'
        }]

    # Проверяем наличие необходимых настроек
    missing_settings = []
    if not config.TELEGRAM_API_ID:
        missing_settings.append("TELEGRAM_API_ID")
    if not config.TELEGRAM_API_HASH:
        missing_settings.append("TELEGRAM_API_HASH")
    if not config.TELEGRAM_PHONE:
        missing_settings.append("TELEGRAM_PHONE")

    if missing_settings:
        error_msg = f"⚠️ Telegram scraper в разработке. Отсутствуют настройки: {', '.join(missing_settings)}"
        logger.warning(error_msg)

        if log_callback:
            log_callback(error_msg, "WARNING")

        return [{
            'success': False,
            'error': error_msg,
            'channel': 'system',
            'missing_settings': missing_settings
        }]

    # Создаем scraper
    scraper = TelegramScraper(
        api_id=config.TELEGRAM_API_ID,
        api_hash=config.TELEGRAM_API_HASH,
        phone=config.TELEGRAM_PHONE,
        log_callback=log_callback,
        session_id=session_id
    )

    try:
        # Подключаемся
        if not await scraper.connect():
            return [{
                'success': False,
                'error': 'Не удалось подключиться к Telegram',
                'channel': 'system'
            }]

        # Парсим каналы
        results = await scraper.scrape_channels(channels, limit)

        return results

    except Exception as e:
        logger.error(f"Критическая ошибка при парсинге Telegram: {e}")
        return [{
            'success': False,
            'error': f'Критическая ошибка: {str(e)}',
            'channel': 'system'
        }]
    finally:
        # Отключаемся
        await scraper.disconnect()

# Функция для совместимости со старым кодом
def save_telegram_message(message_data: Dict[str, Any]) -> bool:
    """
    Сохранить Telegram сообщение (для обратной совместимости).

    ⚠️ В РАЗРАБОТКЕ

    Args:
        message_data: Данные сообщения

    Returns:
        True если сохранено успешно
    """
    logger.warning("⚠️ Telegram scraper в разработке - функция save_telegram_message неактивна")
    return False

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Telegram scraper (в разработке)")
    parser.add_argument("--channels", nargs="+", help="Список каналов")
    parser.add_argument("--limit", type=int, default=100, help="Лимит сообщений")
    parser.add_argument("--debug", action="store_true", help="Включить debug режим")

    args = parser.parse_args()

    if args.debug:
        logging.getLogger().setLevel(logging.DEBUG)

    print("⚠️ Telegram scraper в разработке")
    print("Для использования необходимо настроить Telegram API в config/config.py")

    if args.channels:
        print(f"\nКаналы для парсинга: {args.channels}")
        print(f"Лимит: {args.limit}")
    else:
        print("\nПример запуска:")
        print("python telegram_scraper.py --channels @channel1 @channel2 --limit 50")