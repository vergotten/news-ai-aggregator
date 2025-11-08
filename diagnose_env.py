#!/usr/bin/env python3
"""
Диагностика загрузки переменных окружения
"""

import os
import sys
from pathlib import Path


def diagnose():
    """Диагностика проблем с загрузкой .env"""
    print("=== ДИАГНОСТИКА ЗАГРУЗКИ .ENV ===\n")

    # 1. Проверяем структуру проекта
    current_dir = Path.cwd()
    print(f"Текущая директория: {current_dir}")

    # Ищем .env в разных местах
    possible_paths = [
        current_dir / ".env",
        current_dir.parent / ".env",
        current_dir / "src" / ".env",
        Path(__file__).parent / ".env",
    ]

    env_path = None
    for path in possible_paths:
        if path.exists():
            print(f"✅ Найден .env: {path}")
            env_path = path
            break
        else:
            print(f"❌ Не найден .env: {path}")

    if not env_path:
        print("\n❌ Файл .env не найден!")
        print("Создайте файл .env в корне проекта с содержимым:")
        print("""
POSTGRES_USER=newsaggregator
POSTGRES_PASSWORD=changeme123
POSTGRES_DB=news_aggregator
POSTGRES_HOST=localhost
POSTGRES_PORT=5432

REDDIT_CLIENT_ID=your_reddit_client_id
REDDIT_CLIENT_SECRET=your_reddit_client_secret
REDDIT_USER_AGENT=NewsAggregator/1.0

TELEGRAM_API_ID=your_api_id
TELEGRAM_API_HASH=your_api_hash
TELEGRAM_PHONE=+1234567890
""")
        return False

    # 2. Проверяем содержимое .env
    print(f"\n📄 Содержимое {env_path}:")
    try:
        with open(env_path, 'r') as f:
            lines = f.readlines()
            for i, line in enumerate(lines, 1):
                if line.strip() and not line.startswith('#'):
                    key, sep, value = line.partition('=')
                    if sep:
                        # Маскируем чувствительные данные
                        if any(secret in key.upper() for secret in ['PASSWORD', 'SECRET', 'KEY', 'TOKEN', 'HASH']):
                            value = '*' * len(value.strip())
                        print(f"  {i:2d}. {key.strip()}={value}")
                    else:
                        print(f"  {i:2d}. {line.strip()}")
    except Exception as e:
        print(f"❌ Ошибка чтения файла: {e}")
        return False

    # 3. Проверяем переменные окружения
    print("\n🔍 Проверка переменных окружения:")
    required_vars = ['POSTGRES_USER', 'POSTGRES_PASSWORD', 'POSTGRES_DB', 'REDDIT_CLIENT_ID', 'REDDIT_CLIENT_SECRET']

    missing = []
    for var in required_vars:
        value = os.getenv(var)
        if value:
            if any(secret in var for secret in ['PASSWORD', 'SECRET']):
                print(f"  ✅ {var}: {'*' * len(value)}")
            else:
                print(f"  ✅ {var}: {value}")
        else:
            print(f"  ❌ {var}: НЕ ЗАГРУЖЕНА")
            missing.append(var)

    if missing:
        print(f"\n❌ Отсутствуют переменные: {', '.join(missing)}")

        # 4. Пробуем загрузить .env вручную
        print("\n🔧 Попытка загрузки .env вручную...")
        try:
            from dotenv import load_dotenv
            result = load_dotenv(env_path, override=True)
            print(f"load_dotenv вернул: {result}")

            # Проверяем снова
            still_missing = []
            for var in missing:
                if not os.getenv(var):
                    still_missing.append(var)

            if still_missing:
                print(f"❌ После загрузки все еще отсутствуют: {', '.join(still_missing)}")
            else:
                print("✅ Все переменные успешно загружены!")

        except ImportError:
            print("❌ Модуль python-dotenv не установлен!")
            print("Установите его: pip install python-dotenv")
        except Exception as e:
            print(f"❌ Ошибка загрузки .env: {e}")

        return False

    print("\n✅ Все переменные окружения загружены корректно!")
    return True


if __name__ == "__main__":
    success = diagnose()
    sys.exit(0 if success else 1)