# News Aggregator

Агрегатор новостей с поддержкой Reddit, Telegram, Medium.

## Быстрый старт

```bash
# 1. Настройка
cp .env.example .env
nano .env  # Добавьте API ключи

# 2. Запуск
./start.sh

# 3. Открыть
open http://localhost:8501
```

## Структура

```
news-aggregator/
├── docker-compose.yml
├── Dockerfile
├── src/
│   ├── app.py              # Streamlit UI
│   ├── cli.py              # CLI
│   ├── models/
│   │   └── database.py
│   └── scrapers/
│       ├── reddit_scraper.py
│       └── medium_scraper.py
└── tests/
```

## API Credentials

### Reddit
1. https://www.reddit.com/prefs/apps
2. Создать "script" приложение
3. Скопировать client_id и client_secret

### Telegram
1. https://my.telegram.org/apps
2. Создать приложение
3. Скопировать api_id и api_hash

## Использование

### Web UI
```bash
open http://localhost:8501
```

### CLI
```bash
docker-compose exec app bash
python src/cli.py parse-reddit MachineLearning --max-posts 100
python src/cli.py parse-medium --tags python --max-articles 50
python src/cli.py stats
```

## Команды

```bash
./start.sh      # Запуск
./stop.sh       # Остановка
./logs.sh app   # Логи
```

## License

MIT
