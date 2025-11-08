"""
Менеджер персистентных логов с опциональным Redis бэкендом.

Реализует грациозный откат к файловому хранилищу когда Redis недоступен.
Следует Dependency Inversion Principle с абстрактным интерфейсом хранилища.
"""

import json
import logging
import uuid
from abc import ABC, abstractmethod
from datetime import datetime
from typing import List, Dict, Optional, Any
from pathlib import Path
from dataclasses import dataclass, asdict

logger = logging.getLogger(__name__)


@dataclass
class LogEntry:
    """Структурированная запись лога."""
    timestamp: str
    level: str
    message: str
    session_id: str
    context: Optional[Dict[str, Any]] = None

    def to_dict(self) -> Dict[str, Any]:
        """Конвертация в словарь."""
        return asdict(self)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LogEntry':
        """Создание из словаря."""
        return cls(**data)


@dataclass
class Session:
    """Сессия логирования."""
    id: str
    created_at: str
    status: str
    closed_at: Optional[str] = None


class LogStorage(ABC):
    """Абстрактный интерфейс хранилища логов."""

    @abstractmethod
    def add_log(self, entry: LogEntry) -> None:
        """Добавить запись лога."""
        pass

    @abstractmethod
    def get_logs(self, limit: int = 100, session_id: Optional[str] = None) -> List[LogEntry]:
        """Получить записи логов."""
        pass

    @abstractmethod
    def clear_logs(self, session_id: Optional[str] = None) -> None:
        """Очистить записи логов."""
        pass

    @abstractmethod
    def create_session(self) -> str:
        """Создать новую сессию, вернуть ID сессии."""
        pass

    @abstractmethod
    def close_session(self, session_id: str) -> None:
        """Закрыть сессию."""
        pass

    @abstractmethod
    def get_active_sessions(self) -> List[Session]:
        """Получить активные сессии."""
        pass


class RedisLogStorage(LogStorage):
    """Хранилище логов на основе Redis."""

    def __init__(self, redis_url: str = "redis://redis:6379/0", max_logs: int = 1000):
        """
        Инициализация Redis хранилища.

        Args:
            redis_url: URL подключения к Redis
            max_logs: Максимум логов для хранения

        Raises:
            ConnectionError: Если не удаётся подключиться к Redis
        """
        import redis
        self.redis_client = redis.from_url(redis_url, decode_responses=True)
        self.max_logs = max_logs
        self.log_key = "parsing_logs"
        self.session_key = "parsing_sessions"

        # Проверка подключения
        self.redis_client.ping()
        logger.info(f"Redis хранилище инициализировано: {redis_url}")

    def add_log(self, entry: LogEntry) -> None:
        """Добавить запись лога в Redis."""
        self.redis_client.lpush(self.log_key, json.dumps(entry.to_dict()))
        self.redis_client.ltrim(self.log_key, 0, self.max_logs - 1)

    def get_logs(self, limit: int = 100, session_id: Optional[str] = None) -> List[LogEntry]:
        """Получить логи из Redis."""
        logs = self.redis_client.lrange(self.log_key, 0, limit - 1)
        entries = []

        for log in logs:
            try:
                data = json.loads(log)
                if session_id is None or data.get('session_id') == session_id:
                    entries.append(LogEntry.from_dict(data))
            except (json.JSONDecodeError, TypeError) as e:
                logger.warning(f"Не удалось разобрать запись лога: {e}")

        return entries

    def clear_logs(self, session_id: Optional[str] = None) -> None:
        """Очистить логи в Redis."""
        if session_id:
            logs = self.redis_client.lrange(self.log_key, 0, -1)
            to_keep = [
                log for log in logs
                if json.loads(log).get('session_id') != session_id
            ]
            self.redis_client.delete(self.log_key)
            if to_keep:
                self.redis_client.lpush(self.log_key, *to_keep)
        else:
            self.redis_client.delete(self.log_key)

    def create_session(self) -> str:
        """Создать новую сессию в Redis."""
        session_id = str(uuid.uuid4())
        session = Session(
            id=session_id,
            created_at=datetime.utcnow().isoformat(),
            status='active'
        )
        self.redis_client.hset(
            self.session_key,
            session_id,
            json.dumps(asdict(session))
        )
        return session_id

    def close_session(self, session_id: str) -> None:
        """Закрыть сессию в Redis."""
        session_data = self.redis_client.hget(self.session_key, session_id)
        if session_data:
            session = json.loads(session_data)
            session['status'] = 'closed'
            session['closed_at'] = datetime.utcnow().isoformat()
            self.redis_client.hset(
                self.session_key,
                session_id,
                json.dumps(session)
            )

    def get_active_sessions(self) -> List[Session]:
        """Получить активные сессии из Redis."""
        sessions_data = self.redis_client.hgetall(self.session_key)
        active_sessions = []

        for session_id, data in sessions_data.items():
            try:
                session_dict = json.loads(data)
                if session_dict.get('status') == 'active':
                    active_sessions.append(Session(**session_dict))
            except (json.JSONDecodeError, TypeError):
                continue

        return active_sessions


class FileLogStorage(LogStorage):
    """Файловое хранилище логов (резервное)."""

    def __init__(self, log_dir: Path = Path('/app/logs'), max_logs: int = 1000):
        """
        Инициализация файлового хранилища.

        Args:
            log_dir: Директория для файлов логов
            max_logs: Максимум логов для хранения
        """
        self.log_dir = log_dir
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.max_logs = max_logs
        self.logs_file = self.log_dir / 'parsing_logs.json'
        self.sessions_file = self.log_dir / 'sessions.json'
        self._logs: List[Dict] = []
        self._sessions: Dict[str, Dict] = {}
        self._load_data()
        logger.info(f"Файловое хранилище инициализировано: {self.log_dir}")

    def _load_data(self) -> None:
        """Загрузить данные из файлов."""
        if self.logs_file.exists():
            try:
                with open(self.logs_file, 'r', encoding='utf-8') as f:
                    self._logs = json.load(f)
            except Exception as e:
                logger.warning(f"Не удалось загрузить логи: {e}")
                self._logs = []

        if self.sessions_file.exists():
            try:
                with open(self.sessions_file, 'r', encoding='utf-8') as f:
                    self._sessions = json.load(f)
            except Exception as e:
                logger.warning(f"Не удалось загрузить сессии: {e}")
                self._sessions = {}

    def _save_data(self) -> None:
        """Сохранить данные в файлы."""
        try:
            with open(self.logs_file, 'w', encoding='utf-8') as f:
                json.dump(self._logs, f, ensure_ascii=False, indent=2)

            with open(self.sessions_file, 'w', encoding='utf-8') as f:
                json.dump(self._sessions, f, ensure_ascii=False, indent=2)
        except Exception as e:
            logger.error(f"Не удалось сохранить данные: {e}")

    def add_log(self, entry: LogEntry) -> None:
        """Добавить запись лога в файл."""
        self._logs.append(entry.to_dict())
        if len(self._logs) > self.max_logs:
            self._logs = self._logs[-self.max_logs:]
        self._save_data()

    def get_logs(self, limit: int = 100, session_id: Optional[str] = None) -> List[LogEntry]:
        """Получить логи из файла."""
        logs = self._logs[-limit:] if len(self._logs) > limit else self._logs

        if session_id:
            logs = [log for log in logs if log.get('session_id') == session_id]

        return [LogEntry.from_dict(log) for log in logs]

    def clear_logs(self, session_id: Optional[str] = None) -> None:
        """Очистить логи в файле."""
        if session_id:
            self._logs = [
                log for log in self._logs
                if log.get('session_id') != session_id
            ]
        else:
            self._logs = []
        self._save_data()

    def create_session(self) -> str:
        """Создать новую сессию в файле."""
        session_id = str(uuid.uuid4())
        self._sessions[session_id] = {
            'id': session_id,
            'created_at': datetime.utcnow().isoformat(),
            'status': 'active'
        }
        self._save_data()
        return session_id

    def close_session(self, session_id: str) -> None:
        """Закрыть сессию в файле."""
        if session_id in self._sessions:
            self._sessions[session_id]['status'] = 'closed'
            self._sessions[session_id]['closed_at'] = datetime.utcnow().isoformat()
            self._save_data()

    def get_active_sessions(self) -> List[Session]:
        """Получить активные сессии из файла."""
        return [
            Session(**data)
            for data in self._sessions.values()
            if data.get('status') == 'active'
        ]


class LogManager:
    """
    Главный менеджер логов с автоматическим выбором бэкенда хранилища.

    Сначала пытается использовать Redis, откатывается к файловому хранилищу если недоступен.
    """

    def __init__(
        self,
        redis_url: str = "redis://redis:6379/0",
        log_dir: Path = Path('/app/logs'),
        max_logs: int = 1000,
        prefer_redis: bool = True
    ):
        """
        Инициализация менеджера логов.

        Args:
            redis_url: URL подключения к Redis
            log_dir: Директория для файлового отката
            max_logs: Максимум логов для хранения
            prefer_redis: Сначала пробовать Redis если True
        """
        self.storage: Optional[LogStorage] = None

        if prefer_redis:
            try:
                self.storage = RedisLogStorage(redis_url, max_logs)
                logger.info("Использую Redis хранилище логов")
            except Exception as e:
                logger.warning(f"Redis недоступен: {e}, откат к файловому хранилищу")

        if self.storage is None:
            self.storage = FileLogStorage(log_dir, max_logs)
            logger.info("Использую файловое хранилище логов")

    def add_log(
        self,
        message: str,
        level: str = "INFO",
        session_id: Optional[str] = None,
        context: Optional[Dict[str, Any]] = None
    ) -> None:
        """Добавить запись лога."""
        entry = LogEntry(
            timestamp=datetime.utcnow().isoformat(),
            level=level.upper(),
            message=message,
            session_id=session_id or 'default',
            context=context
        )
        self.storage.add_log(entry)

        # Также логируем в Python logger
        log_func = getattr(logger, level.lower(), logger.info)
        log_func(f"[{session_id or 'default'}] {message}")

    def get_logs(self, limit: int = 100, session_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Получить логи как словари."""
        entries = self.storage.get_logs(limit, session_id)
        return [entry.to_dict() for entry in entries]

    def clear_logs(self, session_id: Optional[str] = None) -> None:
        """Очистить логи."""
        self.storage.clear_logs(session_id)

    def create_session(self) -> str:
        """Создать новую сессию логирования."""
        session_id = self.storage.create_session()
        self.add_log(f"Сессия создана: {session_id}", "INFO", session_id)
        return session_id

    def close_session(self, session_id: str) -> None:
        """Закрыть сессию логирования."""
        self.add_log(f"Сессия закрыта: {session_id}", "INFO", session_id)
        self.storage.close_session(session_id)

    def get_active_sessions(self) -> List[Dict[str, Any]]:
        """Получить активные сессии как словари."""
        sessions = self.storage.get_active_sessions()
        return [asdict(session) for session in sessions]


# Singleton экземпляр
_log_manager: Optional[LogManager] = None


def get_log_manager(
    redis_url: str = "redis://redis:6379/0",
    log_dir: Path = Path('/app/logs'),
    prefer_redis: bool = True
) -> LogManager:
    """
    Получить или создать singleton LogManager.

    Args:
        redis_url: URL подключения к Redis
        log_dir: Директория для файлового отката
        prefer_redis: Сначала пробовать Redis

    Returns:
        LogManager: Singleton экземпляр
    """
    global _log_manager

    if _log_manager is None:
        _log_manager = LogManager(
            redis_url=redis_url,
            log_dir=log_dir,
            prefer_redis=prefer_redis
        )

    return _log_manager


__all__ = [
    'LogManager',
    'LogEntry',
    'Session',
    'LogStorage',
    'RedisLogStorage',
    'FileLogStorage',
    'get_log_manager',
]