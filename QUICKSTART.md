# Quick Start Guide

## Предварительные требования

- Docker & Docker Compose
- Git

## Установка за 5 минут

### 1. Клонирование и настройка

```bash
git clone <your-repo-url>
cd news-aggregator
cp .env.example .env
```

### 2. Редактирование .env

Откройте `.env` и добавьте ваши API ключи:

```bash
# Reddit API
REDDIT_CLIENT_ID=your_id_here
REDDIT_CLIENT_SECRET=your_secret_here

# Telegram API (опционально)
TELEGRAM_API_ID=your_id
TELEGRAM_API_HASH=your_hash

# PostgreSQL (можно оставить по умолчанию)
POSTGRES_PASSWORD=change_this_password
```

### 3. Запуск

```bash
./start.sh
# или
docker-compose up -d
```

### 4. Доступ к интерфейсам

- **Streamlit UI**: http://localhost:8501
- **N8N Automation**: http://localhost:5678 (admin/admin)
- **Database Admin**: http://localhost:8080
- **Ollama API**: http://localhost:11434

## Первый парсинг

### Через Web UI

1. Откройте http://localhost:8501
2. Перейдите во вкладку "Reddit"
3. Выберите subreddits
4. Нажмите "Начать парсинг"

### Через CLI

```bash
# Войти в контейнер
docker-compose exec app bash

# Парсинг Reddit
python src/cli.py parse-reddit MachineLearning Python --max-posts 100

# Парсинг Medium
python src/cli.py parse-medium --tags machine-learning python --max-articles 50

# Статистика
python src/cli.py stats
```

## Настройка N8N автоматизации

1. Откройте http://localhost:5678
2. Войдите (admin/admin)
3. Создайте новый workflow
4. Добавьте Cron node для расписания
5. Добавьте HTTP Request node:
   - Method: POST
   - URL: http://app:8501/api/parse
   - Body: `{"platform": "reddit", "sources": ["MachineLearning"]}`

## Работа с Ollama

```bash
# Загрузить модель
docker exec -it news-aggregator-ollama ollama pull llama2

# Протестировать
curl http://localhost:11434/api/generate -d '{
  "model": "llama2",
  "prompt": "Summarize this article: ..."
}'
```

## Troubleshooting

### Ошибка подключения к БД

```bash
docker-compose logs postgres
docker-compose restart postgres
```

### Reddit API не работает

Проверьте credentials:
```bash
docker-compose exec app env | grep REDDIT
```

### Очистка и перезапуск

```bash
./reset.sh  # Удалит все данные!
./start.sh  # Запуск заново
```

## Полезные команды

```bash
# Логи
docker-compose logs -f app
docker-compose logs -f postgres

# Остановка
docker-compose down

# Остановка с удалением volumes
docker-compose down -v

# Пересборка
docker-compose build --no-cache

# Вход в контейнер
docker-compose exec app bash
docker-compose exec postgres psql -U newsparser -d news_aggregator
```

## Следующие шаги

- Настройте Telegram API для парсинга каналов
- Создайте N8N workflows для автоматического парсинга
- Интегрируйте Ollama для анализа контента
- Настройте мониторинг и алерты
