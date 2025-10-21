"""Thread-safe logger для многопоточной обработки."""
import logging
from typing import Optional
from datetime import datetime
from queue import Queue
import threading

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(name)s: %(message)s'
)


class ThreadSafeLogger:
    """
    Thread-safe логгер для использования в многопоточных операциях.

    Использует Queue для безопасной передачи логов между потоками
    и основным процессом Streamlit.
    """

    def __init__(self, name: str = "processing"):
        self.logger = logging.getLogger(name)
        self.log_queue: Queue = Queue()
        self._lock = threading.Lock()

    def log(self, message: str, level: str = "INFO"):
        """
        Потокобезопасное логирование.

        Args:
            message: Текст сообщения
            level: Уровень (INFO, SUCCESS, WARNING, ERROR, DEBUG)
        """
        timestamp = datetime.now().strftime("%H:%M:%S")

        # Логирование в стандартный logger
        logger_func = getattr(self.logger, level.lower(), self.logger.info)
        logger_func(message)

        # Добавление в очередь для UI (если используется)
        with self._lock:
            self.log_queue.put({
                'timestamp': timestamp,
                'level': level,
                'message': message
            })

    def get_logs(self, max_items: Optional[int] = None) -> list:
        """
        Получить все логи из очереди.

        Args:
            max_items: Максимальное количество элементов для возврата

        Returns:
            Список логов
        """
        logs = []
        count = 0

        while not self.log_queue.empty():
            if max_items and count >= max_items:
                break
            try:
                logs.append(self.log_queue.get_nowait())
                count += 1
            except:
                break

        return logs

    def format_for_ui(self, log_entry: dict) -> str:
        """Форматирование лога для UI."""
        icons = {
            "INFO": "ℹ️",
            "SUCCESS": "✅",
            "WARNING": "⚠️",
            "ERROR": "❌",
            "DEBUG": "🔍"
        }

        icon = icons.get(log_entry['level'], "📝")
        return f"{icon} `{log_entry['timestamp']}` {log_entry['message']}"


# Singleton
_logger_instance: Optional[ThreadSafeLogger] = None


def get_thread_safe_logger() -> ThreadSafeLogger:
    """Получить singleton экземпляр логгера."""
    global _logger_instance
    if _logger_instance is None:
        _logger_instance = ThreadSafeLogger()
    return _logger_instance