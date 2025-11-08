"""Загрузчик конфигурации из sources.json."""
import json
import os
from typing import List, Dict, Any


class SourceConfig:
    """Класс для работы с конфигурацией источников."""

    def __init__(self, config_path: str = None):
        """
        Инициализация конфигурации.

        Args:
            config_path: Путь к sources.json (опционально)
        """
        if config_path is None:
            # Поиск в разных местах
            possible_paths = [
                'config/sources.json',
                'src/config/sources.json',
                '../config/sources.json',
                os.path.join(os.path.dirname(__file__), 'config', 'sources.json')
            ]

            for path in possible_paths:
                if os.path.exists(path):
                    config_path = path
                    break

            if config_path is None:
                raise FileNotFoundError(
                    "sources.json не найден. Проверьте путь или укажите config_path"
                )

        self.config_path = config_path
        self._config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """Загружает конфигурацию из JSON."""
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    def reload(self):
        """Перезагружает конфигурацию из файла."""
        self._config = self._load_config()

    # ==================== REDDIT ====================

    def get_subreddits(self, category: str = None) -> List[str]:
        """
        Возвращает список subreddit'ов.

        Args:
            category: Категория (ai, crypto, tech, news, finance, etc.)

        Returns:
            Список имен subreddit'ов
        """
        subreddits = self._config.get('reddit', {}).get('subreddits', [])

        if category:
            subreddits = [s for s in subreddits if s.get('category') == category]

        return [s['name'] for s in subreddits]

    def get_reddit_subreddits(self, category: str = None) -> List[str]:
        """
        Алиас для get_subreddits() для обратной совместимости.

        Args:
            category: Категория (ai, crypto, tech, news, finance, etc.)

        Returns:
            Список имен subreddit'ов
        """
        return self.get_subreddits(category=category)

    def get_reddit_categories(self) -> List[str]:
        """Возвращает уникальные категории Reddit."""
        subreddits = self._config.get('reddit', {}).get('subreddits', [])
        categories = set(s.get('category', 'other') for s in subreddits)
        return sorted(categories)

    def get_subreddit_info(self, name: str) -> Dict[str, Any]:
        """
        Возвращает полную информацию о subreddit.

        Args:
            name: Имя subreddit

        Returns:
            Словарь с информацией или None
        """
        subreddits = self._config.get('reddit', {}).get('subreddits', [])
        for sub in subreddits:
            if sub['name'] == name:
                return sub
        return None

    # ==================== TELEGRAM ====================

    def get_telegram_channels(self) -> List[str]:
        """Возвращает список Telegram каналов."""
        return self._config.get('telegram', {}).get('channels', [])

    # ==================== MEDIUM ====================

    def get_medium_publications(self, category: str = None) -> List[str]:
        """
        Возвращает список Medium публикаций.

        Args:
            category: Категория (ai, tech, etc.)

        Returns:
            Список публикаций
        """
        publications = self._config.get('medium', {}).get('publications', [])

        if category:
            publications = [p for p in publications if p.get('category') == category]

        return [p['name'] for p in publications]

    def get_medium_publication_list(self, category: str = None) -> List[str]:
        """Алиас для get_medium_publications() для обратной совместимости."""
        return self.get_medium_publications(category=category)

    def get_medium_categories(self) -> List[str]:
        """Возвращает уникальные категории Medium."""
        publications = self._config.get('medium', {}).get('publications', [])
        categories = set(p.get('category', 'other') for p in publications)
        return sorted(categories)

    def get_medium_tags(self) -> List[str]:
        """Возвращает список тегов Medium."""
        return self._config.get('medium', {}).get('tags', [])

    # ==================== HABR ====================

    def get_habr_hubs(self, category: str = None) -> List[str]:
        """
        Возвращает список хабов Habr.

        Args:
            category: Категория (ai, tech, etc.)

        Returns:
            Список имен хабов
        """
        hubs = self._config.get('habr', {}).get('hubs', [])

        if category:
            hubs = [h for h in hubs if h.get('category') == category]

        return [h['name'] for h in hubs]

    def get_habr_tags(self, category: str = None) -> List[str]:
        """
        Возвращает список тегов Habr.

        Args:
            category: Категория (ai, tech, etc.)

        Returns:
            Список тегов
        """
        tags = self._config.get('habr', {}).get('tags', [])

        if category:
            tags = [t for t in tags if t.get('category') == category]

        return [t['name'] for t in tags]

    def get_habr_categories(self) -> List[str]:
        """Возвращает уникальные категории Habr."""
        hubs = self._config.get('habr', {}).get('hubs', [])
        tags = self._config.get('habr', {}).get('tags', [])

        categories = set(h.get('category', 'other') for h in hubs)
        categories.update(t.get('category', 'other') for t in tags)

        return sorted(categories)

    def get_habr_hub_info(self, name: str) -> Dict[str, Any]:
        """
        Возвращает полную информацию о хабе Habr.

        Args:
            name: Имя хаба

        Returns:
            Словарь с информацией или None
        """
        hubs = self._config.get('habr', {}).get('hubs', [])
        for hub in hubs:
            if hub['name'] == name:
                return hub
        return None

    # ==================== ОБЩИЕ ====================

    def get_all_sources(self) -> Dict[str, Any]:
        """Возвращает полную конфигурацию всех источников."""
        return self._config

    def get_source_config(self, source: str) -> Dict[str, Any]:
        """
        Возвращает конфигурацию конкретного источника.

        Args:
            source: Имя источника (reddit, telegram, medium, habr)

        Returns:
            Словарь с конфигурацией
        """
        return self._config.get(source, {})


# Singleton инстанс
_config_instance = None


def get_config(config_path: str = None) -> SourceConfig:
    """
    Получить singleton инстанс конфигурации.

    Args:
        config_path: Путь к sources.json (используется только при первом вызове)

    Returns:
        SourceConfig инстанс
    """
    global _config_instance

    if _config_instance is None:
        _config_instance = SourceConfig(config_path)

    return _config_instance


def reload_config():
    """Перезагрузить конфигурацию из файла."""
    if _config_instance:
        _config_instance.reload()


# Пример использования
if __name__ == '__main__':
    config = get_config()

    print("=== Reddit ===")
    print("Категории:", config.get_reddit_categories())
    print("AI subreddits:", config.get_subreddits(category='ai'))

    print("\n=== Telegram ===")
    print("Каналы:", config.get_telegram_channels())

    print("\n=== Medium ===")
    print("Категории:", config.get_medium_categories())
    print("AI publications:", config.get_medium_publications(category='ai'))

    print("\n=== Habr ===")
    print("Категории:", config.get_habr_categories())
    print("AI хабы:", config.get_habr_hubs(category='ai'))
    print("AI теги:", config.get_habr_tags(category='ai')[:5], "...")