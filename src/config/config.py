"""
Централизованная конфигурация приложения с поддержкой переменных окружения
"""

import os
import sys
import logging
from typing import Optional, Dict, Any
from pathlib import Path
from dataclasses import dataclass, field
from functools import lru_cache

# Настройка логирования
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Определяем корневую директорию проекта
if getattr(sys, 'frozen', False):
    # Если приложение упаковано (PyInstaller)
    PROJECT_ROOT = Path(sys.executable).parent
else:
    # Обычный запуск
    PROJECT_ROOT = Path(__file__).parent.parent.parent

ENV_FILE = PROJECT_ROOT / ".env"


def load_env_file() -> bool:
    """Ручная загрузка .env без зависимости от python-dotenv"""

    # Список путей для поиска
    search_paths = [
        Path.cwd() / ".env",  # Текущая директория
        Path(__file__).resolve().parent.parent.parent / ".env",  # /app/.env
        Path(__file__).resolve().parent.parent / ".env",  # /app/src/.env
        Path("/app/.env"),  # Docker путь
    ]

    logger.info("=" * 70)
    logger.info("РУЧНАЯ ЗАГРУЗКА .env")
    logger.info("=" * 70)
    logger.info(f"Рабочая директория: {os.getcwd()}")
    logger.info(f"__file__: {Path(__file__).resolve()}")

    env_vars_loaded = {}

    for i, env_path in enumerate(search_paths, 1):
        try:
            env_path = env_path.resolve()
            logger.info(f"[{i}] Проверка: {env_path}")

            if not env_path.exists():
                logger.info(f"    ✗ Не существует")
                continue

            size = env_path.stat().st_size
            logger.info(f"    ✓ Найден (размер: {size} байт)")

            if size == 0:
                logger.warning(f"    ⚠ Файл пустой")
                continue

            # Читаем и парсим файл
            logger.info(f"    Парсинг...")
            with open(env_path, 'r', encoding='utf-8') as f:
                for line_num, line in enumerate(f, 1):
                    line = line.strip()

                    # Пропускаем комментарии и пустые строки
                    if not line or line.startswith('#'):
                        continue

                    # Парсим KEY=VALUE
                    if '=' not in line:
                        continue

                    key, value = line.split('=', 1)
                    key = key.strip()
                    value = value.strip()

                    # Удаляем кавычки если есть
                    for quote in ['"', "'"]:
                        if value.startswith(quote) and value.endswith(quote):
                            value = value[1:-1]
                            break

                    # КРИТИЧНО: Устанавливаем в os.environ
                    os.environ[key] = value
                    env_vars_loaded[key] = value

                    # Логируем (маскируем секреты)
                    if any(secret in key.upper() for secret in ['PASSWORD', 'SECRET', 'TOKEN', 'KEY']):
                        logger.info(f"      {key} = {'*' * min(len(value), 10)}")
                    else:
                        logger.info(f"      {key} = {value[:50]}")

            # Проверяем что критические переменные загрузились
            critical = ['REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET']
            loaded_critical = [var for var in critical if var in env_vars_loaded]

            logger.info(f"    Всего загружено: {len(env_vars_loaded)} переменных")
            logger.info(f"    Критических загружено: {len(loaded_critical)}/{len(critical)}")

            if len(loaded_critical) == len(critical):
                logger.info("✓✓✓ УСПЕШНО: Все критические переменные загружены")
                logger.info(f"✓✓✓ Источник: {env_path}")
                logger.info("=" * 70)
                return True
            else:
                missing = set(critical) - set(loaded_critical)
                logger.warning(f"    ⚠ Не хватает переменных: {missing}")

        except Exception as e:
            logger.error(f"    ❌ Ошибка обработки {env_path}: {e}")
            continue

    logger.warning("⚠ .env не найден или не содержит Reddit API ключи")
    logger.warning("⚠ Будут использованы значения по умолчанию")
    logger.info("=" * 70)
    return False

# ЗАГРУЖАЕМ .env ПРЯМО СЕЙЧАС
load_env_file()

@dataclass
class DatabaseConfig:
    """Конфигурация базы данных PostgreSQL"""
    user: str
    password: str
    database: str
    host: str = "localhost"
    port: int = 5432

    @property
    def url(self) -> str:
        """Сформировать URL для подключения к базе данных"""
        return f"postgresql://{self.user}:{self.password}@{self.host}:{self.port}/{self.database}"

@dataclass
class RedditConfig:
    """Конфигурация Reddit API"""
    client_id: str
    client_secret: str
    user_agent: str = "NewsAggregator/1.0"

@dataclass
class TelegramConfig:
    """Конфигурация Telegram API"""
    api_id: str
    api_hash: str
    phone: str

@dataclass
class QdrantConfig:
    """Конфигурация Qdrant"""
    url: str = "http://qdrant:6333"
    port: int = 6333
    grpc_port: int = 6334

@dataclass
class OllamaConfig:
    """Конфигурация Ollama"""
    base_url: str = "http://ollama:11434"
    port: int = 11434
    model: str = "llama2"
    embedding_model: str = "nomic-embed-text"

@dataclass
class LLMConfig:
    """Конфигурация LLM провайдера"""
    provider: str = "ollama"
    model: str = "llama2"
    temperature: float = 0.7
    max_tokens: int = 2000
    top_p: float = 0.9
    base_url: str = "http://localhost:11434"
    max_parallel_tasks: int = 2

@dataclass
class ApplicationConfig:
    """Конфигурация приложения"""
    port: int = 8501
    timezone: str = "UTC"
    adminer_port: int = 8080
    debug: bool = False
    default_max_posts: int = 50
    default_delay: int = 5
    default_sort: str = "hot"
    default_enable_llm: bool = True
    batch_size: int = 10
    min_text_length: int = 100
    enable_semantic_dedup: bool = True
    enable_vectorization: bool = True
    logs_max_length: int = 1000
    viewer_default_limit: int = 50
    show_debug_info: bool = False

@dataclass
class N8NConfig:
    """Конфигурация N8N"""
    port: int = 5678
    database: str = "n8n"
    basic_auth_active: bool = True
    basic_auth_user: str = "admin"
    basic_auth_password: str = "admin123"

@dataclass
class Config:
    """Основная конфигурация приложения"""
    # Поля без значений по умолчанию должны идти первыми
    database: DatabaseConfig
    reddit: RedditConfig
    telegram: TelegramConfig

    # Поля со значениями по умолчанию
    qdrant: QdrantConfig = field(default_factory=QdrantConfig)
    ollama: OllamaConfig = field(default_factory=OllamaConfig)
    llm: LLMConfig = field(default_factory=LLMConfig)
    app: ApplicationConfig = field(default_factory=ApplicationConfig)
    n8n: N8NConfig = field(default_factory=N8NConfig)

    # Прямые атрибуты для обратной совместимости
    @property
    def POSTGRES_USER(self) -> str:
        return self.database.user

    @property
    def POSTGRES_PASSWORD(self) -> str:
        return self.database.password

    @property
    def POSTGRES_HOST(self) -> str:
        return self.database.host

    @property
    def POSTGRES_PORT(self) -> int:
        return self.database.port

    @property
    def POSTGRES_DB(self) -> str:
        return self.database.database

    @property
    def REDDIT_CLIENT_ID(self) -> str:
        return self.reddit.client_id

    @property
    def REDDIT_CLIENT_SECRET(self) -> str:
        return self.reddit.client_secret

    @property
    def REDDIT_USER_AGENT(self) -> str:
        return self.reddit.user_agent

    @property
    def TELEGRAM_API_ID(self) -> str:
        return self.telegram.api_id

    @property
    def TELEGRAM_API_HASH(self) -> str:
        return self.telegram.api_hash

    @property
    def TELEGRAM_PHONE(self) -> str:
        return self.telegram.phone

    @property
    def QDRANT_URL(self) -> str:
        return self.qdrant.url

    @property
    def QDRANT_PORT(self) -> int:
        return self.qdrant.port

    @property
    def QDRANT_GRPC_PORT(self) -> int:
        return self.qdrant.grpc_port

    @property
    def OLLAMA_BASE_URL(self) -> str:
        return self.ollama.base_url

    @property
    def OLLAMA_PORT(self) -> int:
        return self.ollama.port

    @property
    def LLM_PROVIDER(self) -> str:
        return self.llm.provider

    @property
    def LLM_MODEL(self) -> str:
        return self.llm.model

    @property
    def LLM_TEMPERATURE(self) -> float:
        return self.llm.temperature

    @property
    def LLM_MAX_TOKENS(self) -> int:
        return self.llm.max_tokens

    @property
    def LLM_TOP_P(self) -> float:
        return self.llm.top_p

    @property
    def LLM_BASE_URL(self) -> str:
        return self.llm.base_url

    @property
    def MAX_PARALLEL_TASKS(self) -> int:
        return self.llm.max_parallel_tasks

    @property
    def APP_PORT(self) -> int:
        return self.app.port

    @property
    def TZ(self) -> str:
        return self.app.timezone

    @property
    def ADMINER_PORT(self) -> int:
        return self.app.adminer_port

    @property
    def DEBUG(self) -> bool:
        return self.app.debug

    @property
    def DEFAULT_MAX_POSTS(self) -> int:
        return self.app.default_max_posts

    @property
    def DEFAULT_DELAY(self) -> int:
        return self.app.default_delay

    @property
    def DEFAULT_SORT(self) -> str:
        return self.app.default_sort

    @property
    def DEFAULT_ENABLE_LLM(self) -> bool:
        return self.app.default_enable_llm

    @property
    def BATCH_SIZE(self) -> int:
        return self.app.batch_size

    @property
    def MIN_TEXT_LENGTH(self) -> int:
        return self.app.min_text_length

    @property
    def ENABLE_SEMANTIC_DEDUP(self) -> bool:
        return self.app.enable_semantic_dedup

    @property
    def ENABLE_VECTORIZATION(self) -> bool:
        return self.app.enable_vectorization

    @property
    def LOGS_MAX_LENGTH(self) -> int:
        return self.app.logs_max_length

    @property
    def VIEWER_DEFAULT_LIMIT(self) -> int:
        return self.app.viewer_default_limit

    @property
    def SHOW_DEBUG_INFO(self) -> bool:
        return self.app.show_debug_info

    @property
    def N8N_PORT(self) -> int:
        return self.n8n.port

    @property
    def N8N_DB(self) -> str:
        return self.n8n.database

    @property
    def N8N_BASIC_AUTH_ACTIVE(self) -> bool:
        return self.n8n.basic_auth_active

    @property
    def N8N_BASIC_AUTH_USER(self) -> str:
        return self.n8n.basic_auth_user

    @property
    def N8N_BASIC_AUTH_PASSWORD(self) -> str:
        return self.n8n.basic_auth_password

def get_env_bool(key: str, default: bool = False) -> bool:
    """Получить булево значение из переменной окружения"""
    value = os.getenv(key, str(default)).lower()
    return value in ('true', '1', 'yes', 'on')

def get_env_int(key: str, default: int) -> int:
    """Получить целочисленное значение из переменной окружения"""
    try:
        return int(os.getenv(key, str(default)))
    except ValueError:
        logger.error(f"Переменная окружения {key} должна быть целым числом, используется значение по умолчанию: {default}")
        return default

def get_env_float(key: str, default: float) -> float:
    """Получить вещественное значение из переменной окружения"""
    try:
        return float(os.getenv(key, str(default)))
    except ValueError:
        logger.error(f"Переменная окружения {key} должна быть числом, используется значение по умолчанию: {default}")
        return default


def get_postgres_host() -> str:
    """Определить хост PostgreSQL автоматически"""
    # Приоритет 1: Переменная окружения
    env_host = os.getenv('POSTGRES_HOST')
    if env_host:
        return env_host

    # Приоритет 2: Проверка окружения
    if os.path.exists('/.dockerenv'):
        # Запуск внутри Docker
        logger.info("Обнаружен Docker → host=postgres")
        return 'postgres'
    else:
        # Локальный запуск → пробуем localhost
        logger.info("Локальный запуск → host=localhost")

        # Проверяем доступность localhost:5432
        import socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        result = sock.connect_ex(('localhost', 5432))
        sock.close()

        if result == 0:
            logger.info("✓ PostgreSQL доступен на localhost:5432")
            return 'localhost'
        else:
            logger.warning("⚠ localhost:5432 недоступен, пробуем 127.0.0.1")
            return '127.0.0.1'

def load_config() -> Config:
    """
    Загрузить конфигурацию из переменных окружения с дефолтами

    Returns:
        Объект конфигурации

    Raises:
        ValueError: Если отсутствуют обязательные переменные окружения
    """
    # Проверяем ТОЛЬКО Reddit API (остальное имеет дефолты)
    required_vars = {
        'REDDIT_CLIENT_ID': 'ID клиента Reddit API',
        'REDDIT_CLIENT_SECRET': 'Секрет клиента Reddit API'
    }

    missing_vars = []
    for var, description in required_vars.items():
        if not os.getenv(var):
            missing_vars.append(f"{var} ({description})")

    if missing_vars:
        error_msg = f"Отсутствуют обязательные переменные окружения:\n" + "\n".join(f"- {var}" for var in missing_vars)
        logger.error(error_msg)
        logger.error("=== ДИАГНОСТИКА ===")
        logger.error(f"Рабочая директория: {os.getcwd()}")
        logger.error(f"Корень проекта: {PROJECT_ROOT}")
        logger.error(f"Ищем .env в: {ENV_FILE}")
        logger.error(f".env существует: {ENV_FILE.exists()}")
        logger.error("Текущие переменные окружения:")
        for var in required_vars:
            value = os.getenv(var)
            if value:
                logger.error(f"  {var}: {'*' * len(value) if 'SECRET' in var else value}")
            else:
                logger.error(f"  {var}: НЕ УСТАНОВЛЕНА")
        logger.error("=== КОНЕЦ ДИАГНОСТИКИ ===")
        raise ValueError(error_msg)

    # Конфигурация базы данных (с дефолтами из вашего .env)
    database = DatabaseConfig(
        user=os.getenv('POSTGRES_USER', 'newsaggregator'),
        password=os.getenv('POSTGRES_PASSWORD', 'changeme123'),
        database=os.getenv('POSTGRES_DB', 'news_aggregator'),
        host=get_postgres_host(),
        port=get_env_int('POSTGRES_PORT', 5432)
    )

    # Конфигурация Reddit (ОБЯЗАТЕЛЬНО из env)
    reddit = RedditConfig(
        client_id=os.getenv('REDDIT_CLIENT_ID'),  # Обязательно
        client_secret=os.getenv('REDDIT_CLIENT_SECRET'),  # Обязательно
        user_agent=os.getenv('REDDIT_USER_AGENT', 'NewsAggregator/1.0')
    )

    # Конфигурация Telegram (с плейсхолдерами)
    telegram = TelegramConfig(
        api_id=os.getenv('TELEGRAM_API_ID', 'your_api_id'),
        api_hash=os.getenv('TELEGRAM_API_HASH', 'your_api_hash'),
        phone=os.getenv('TELEGRAM_PHONE', '+1234567890')
    )

    # Конфигурация Qdrant (с дефолтами из вашего .env)
    qdrant = QdrantConfig(
        url=os.getenv('QDRANT_URL', 'http://qdrant:6333'),
        port=get_env_int('QDRANT_PORT', 6333),
        grpc_port=get_env_int('QDRANT_GRPC_PORT', 6334)
    )

    # Конфигурация Ollama (с дефолтами из вашего .env)
    ollama = OllamaConfig(
        base_url=os.getenv('OLLAMA_BASE_URL', 'http://ollama:11434'),
        port=get_env_int('OLLAMA_PORT', 11434),
        model=os.getenv('OLLAMA_MODEL', 'llama2'),
        embedding_model=os.getenv('EMBEDDING_MODEL', 'nomic-embed-text')
    )

    # Конфигурация LLM (с дефолтами из вашего .env)
    llm = LLMConfig(
        provider=os.getenv('LLM_PROVIDER', 'ollama'),
        model=os.getenv('LLM_MODEL', 'llama2'),
        temperature=get_env_float('LLM_TEMPERATURE', 0.7),
        max_tokens=get_env_int('LLM_MAX_TOKENS', 2000),
        top_p=get_env_float('LLM_TOP_P', 0.9),
        base_url=os.getenv('LLM_BASE_URL', 'http://localhost:11434'),
        max_parallel_tasks=get_env_int('MAX_PARALLEL_TASKS', 2)
    )

    # Конфигурация приложения (с дефолтами из вашего .env)
    app = ApplicationConfig(
        port=get_env_int('APP_PORT', 8501),
        timezone=os.getenv('TZ', 'UTC'),
        adminer_port=get_env_int('ADMINER_PORT', 8080),
        debug=get_env_bool('DEBUG', False),
        default_max_posts=get_env_int('DEFAULT_MAX_POSTS', 50),
        default_delay=get_env_int('DEFAULT_DELAY', 5),
        default_sort=os.getenv('DEFAULT_SORT', 'hot'),
        default_enable_llm=get_env_bool('DEFAULT_ENABLE_LLM', True),
        batch_size=get_env_int('BATCH_SIZE', 10),
        min_text_length=get_env_int('MIN_TEXT_LENGTH', 100),
        enable_semantic_dedup=get_env_bool('ENABLE_SEMANTIC_DEDUP', True),
        enable_vectorization=get_env_bool('ENABLE_VECTORIZATION', True),
        logs_max_length=get_env_int('LOGS_MAX_LENGTH', 1000),
        viewer_default_limit=get_env_int('VIEWER_DEFAULT_LIMIT', 50),
        show_debug_info=get_env_bool('SHOW_DEBUG_INFO', False)
    )

    # Конфигурация N8N (с дефолтами из вашего .env)
    n8n = N8NConfig(
        port=get_env_int('N8N_PORT', 5678),
        database=os.getenv('N8N_DB', 'n8n'),
        basic_auth_active=get_env_bool('N8N_BASIC_AUTH_ACTIVE', True),
        basic_auth_user=os.getenv('N8N_BASIC_AUTH_USER', 'admin'),
        basic_auth_password=os.getenv('N8N_BASIC_AUTH_PASSWORD', 'admin123')
    )

    logger.info("✓ Конфигурация успешно загружена")
    logger.info(f"  PostgreSQL: {database.user}@{database.host}:{database.port}/{database.database}")
    logger.info(f"  Reddit: client_id={reddit.client_id[:10]}***")
    logger.info(f"  LLM: {llm.provider}/{llm.model}")

    return Config(
        database=database,
        reddit=reddit,
        telegram=telegram,
        qdrant=qdrant,
        ollama=ollama,
        llm=llm,
        app=app,
        n8n=n8n
    )

# Глобальный экземпляр конфигурации
_config: Optional[Config] = None

@lru_cache(maxsize=1)
def get_config() -> Config:
    """
    Получить экземпляр конфигурации (синглтон)

    Returns:
        Объект конфигурации

    Raises:
        ValueError: Если конфигурация не может быть загружена
    """
    global _config
    if _config is None:
        _config = load_config()
    return _config

def reset_config() -> None:
    """Сбросить кэшированную конфигурацию (полезно для тестов)"""
    global _config
    _config = None
    get_config.cache_clear()

def validate_config() -> Dict[str, Any]:
    """
    Проверить конфигурацию и вернуть отчет о проверке

    Returns:
        Словарь с результатами проверки
    """
    config = get_config()
    issues = []
    warnings = []

    # Проверка конфигурации базы данных
    if not config.database.user:
        issues.append("Не указано имя пользователя базы данных")
    if not config.database.password:
        issues.append("Не указан пароль базы данных")
    if not config.database.database:
        issues.append("Не указано имя базы данных")

    # Проверка конфигурации Reddit
    if not config.reddit.client_id:
        issues.append("Не указан ID клиента Reddit")
    if not config.reddit.client_secret:
        issues.append("Не указан секрет клиента Reddit")

    # Проверка конфигурации Telegram
    if not config.telegram.api_id or config.telegram.api_id == 'your_api_id':
        warnings.append("Не указан API ID Telegram (используется значение по умолчанию)")
    if not config.telegram.api_hash or config.telegram.api_hash == 'your_api_hash':
        warnings.append("Не указан API Hash Telegram (используется значение по умолчанию)")
    if not config.telegram.phone or config.telegram.phone == '+1234567890':
        warnings.append("Не указан номер телефона Telegram (используется значение по умолчанию)")

    return {
        'valid': len(issues) == 0,
        'issues': issues,
        'warnings': warnings
    }

# Экспорт
__all__ = [
    'Config',
    'get_config',
    'reset_config',
    'validate_config',
    'DatabaseConfig',
    'RedditConfig',
    'TelegramConfig',
    'QdrantConfig',
    'OllamaConfig',
    'LLMConfig',
    'ApplicationConfig',
    'N8NConfig'
]