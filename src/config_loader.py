"""Загрузчик конфигурации источников."""
import json
from pathlib import Path
from typing import Dict, List


class SourceConfig:
    """Управляет загрузкой и доступом к конфигурации источников."""

    def __init__(self, config_path: str = None):
        if config_path is None:
            # Путь по умолчанию: ищем config рядом с src
            # src/config_loader.py -> src/../config/sources.json
            base_path = Path(__file__).parent.parent
            self.config_path = base_path / "config" / "sources.json"

            # Если не нашли, пробуем относительно src
            if not self.config_path.exists():
                self.config_path = Path(__file__).parent / "config" / "sources.json"
        else:
            self.config_path = Path(config_path)

        self._config = self._load_config()

    def _load_config(self) -> Dict:
        """Загружает конфигурацию из JSON файла."""
        if not self.config_path.exists():
            raise FileNotFoundError(f"Конфиг не найден: {self.config_path}")

        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def reload(self):
        """Перезагружает конфигурацию из файла."""
        self._config = self._load_config()

    def get_reddit_subreddits(self, category: str = None) -> List[str]:
        """
        Возвращает список названий subreddit'ов.

        Args:
            category: Фильтр по категории (tech, ai, dev и т.д.). None = все.

        Returns:
            Список названий subreddit'ов
        """
        subreddits = self._config.get('reddit', {}).get('subreddits', [])

        if category:
            subreddits = [s for s in subreddits if s.get('category') == category]

        return [s['name'] for s in subreddits]

    def get_reddit_categories(self) -> List[str]:
        """Возвращает уникальные категории Reddit."""
        subreddits = self._config.get('reddit', {}).get('subreddits', [])
        return sorted(set(s.get('category', 'other') for s in subreddits))

    def get_medium_tags(self, category: str = None) -> List[str]:
        """
        Возвращает список тегов Medium.

        Args:
            category: Фильтр по категории. None = все.

        Returns:
            Список названий тегов
        """
        tags = self._config.get('medium', {}).get('tags', [])

        if category:
            tags = [t for t in tags if t.get('category') == category]

        return [t['name'] for t in tags]

    def get_telegram_channels(self) -> List[str]:
        """Возвращает список username'ов Telegram каналов."""
        channels = self._config.get('telegram', {}).get('channels', [])
        return [c['username'] for c in channels]


# Singleton инстанс
_config_instance = None


def get_config() -> SourceConfig:
    """Возвращает singleton инстанс конфига."""
    global _config_instance
    if _config_instance is None:
        _config_instance = SourceConfig()
    return _config_instance