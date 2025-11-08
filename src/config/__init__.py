"""
Конфигурация приложения
"""

# Загружаем .env при импорте пакета
import os
from pathlib import Path

# Определяем корневую директорию проекта
PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_FILE = PROJECT_ROOT / ".env"

# Загружаем .env при импорте пакета
try:
    from dotenv import load_dotenv
    if ENV_FILE.exists():
        load_dotenv(ENV_FILE, override=True)
except ImportError:
    pass
except Exception:
    pass

from .config import get_config, Config, validate_config

__all__ = ['get_config', 'Config', 'validate_config']