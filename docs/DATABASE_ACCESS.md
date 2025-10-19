# Руководство по доступу к базе данных

## Обзор

Это руководство объясняет, как получить доступ и просмотреть данные, хранящиеся в PostgreSQL базе данных системы News Aggregator.

## Предварительные требования

- Docker контейнеры должны быть запущены
- Сервис Adminer должен быть активен (порт 8080)

## Способы доступа

### Способ 1: Веб-интерфейс Adminer (Рекомендуется)

#### 1. Откройте Adminer

Перейдите по адресу: **http://localhost:8080**

#### 2. Данные для входа

Заполните форму входа следующими параметрами:

| Поле | Значение |
|------|----------|
| **Движок (System)** | PostgreSQL |
| **Сервер (Server)** | `postgres` |
| **Имя пользователя (Username)** | `newsaggregator` |
| **Пароль (Password)** | `changeme123` |
| **База данных (Database)** | `news_aggregator` |

#### 3. Нажмите "Войти"

---

## Просмотр постов Reddit

### Вариант А: Через интерфейс Adminer

1. После входа перейдите в **SQL команда** в левом меню
2. Выполните один из запросов ниже

### Вариант Б: Прямой просмотр таблицы

1. Кликните на схему **`app`** в левой боковой панели
2. Кликните на таблицу **`articles`**
3. Нажмите **"Выбрать данные"** для просмотра всех записей

---

## Полезные SQL запросы

### 1. Просмотр всех постов Reddit

```sql
SELECT 
    id,
    title,
    url,
    source,
    tags,
    published_date,
    created_at
FROM app.articles
WHERE source LIKE 'reddit_%'
ORDER BY created_at DESC;
```

### 2. Просмотр постов из конкретного subreddit

```sql
SELECT 
    id,
    title,
    url,
    tags[1] AS score,
    tags[2] AS comments,
    tags[3] AS author,
    published_date
FROM app.articles
WHERE source = 'reddit_machinelearning'
ORDER BY published_date DESC
LIMIT 20;
```

### 3. Топ постов по рейтингу

```sql
SELECT 
    title,
    url,
    source,
    CAST(tags[1] AS INTEGER) AS score,
    CAST(tags[2] AS INTEGER) AS comments,
    published_date
FROM app.articles
WHERE source LIKE 'reddit_%'
ORDER BY CAST(tags[1] AS INTEGER) DESC
LIMIT 10;
```

### 4. Статистика по источникам

```sql
SELECT 
    source,
    COUNT(*) AS total_posts,
    MAX(published_date) AS latest_post,
    MIN(published_date) AS oldest_post
FROM app.articles
WHERE source LIKE 'reddit_%'
GROUP BY source
ORDER BY total_posts DESC;
```

### 5. Поиск постов по ключевому слову

```sql
SELECT 
    title,
    url,
    source,
    created_at
FROM app.articles
WHERE 
    (title ILIKE '%machine learning%' OR content ILIKE '%machine learning%')
    AND source LIKE 'reddit_%'
ORDER BY created_at DESC;
```

### 6. Недавние посты (за последние 24 часа)

```sql
SELECT 
    title,
    source,
    published_date,
    created_at
FROM app.articles
WHERE 
    source LIKE 'reddit_%'
    AND created_at > NOW() - INTERVAL '24 hours'
ORDER BY created_at DESC;
```

---

## Структура данных

### Таблица: `app.articles`

| Колонка | Тип | Описание |
|---------|-----|----------|
| `id` | INTEGER | Уникальный идентификатор (автоинкремент) |
| `title` | TEXT | Заголовок поста |
| `url` | TEXT | URL поста (уникальный) |
| `source` | VARCHAR(100) | Идентификатор источника (например, `reddit_machinelearning`) |
| `published_date` | TIMESTAMP | Дата публикации оригинального поста на Reddit |
| `content` | TEXT | Содержимое поста (selftext) |
| `summary` | TEXT | AI-сгенерированное резюме (будущая функция) |
| `tags` | TEXT[] | Массив: [score, num_comments, author] |
| `created_at` | TIMESTAMP | Когда запись была сохранена в БД |
| `updated_at` | TIMESTAMP | Время последнего обновления |

### Структура массива tags

Для постов Reddit массив `tags` содержит:

- `tags[1]` → Рейтинг поста (upvotes)
- `tags[2]` → Количество комментариев
- `tags[3]` → Имя автора

---

## Способ 2: Командная строка PostgreSQL (psql)

### Подключение к базе данных

```bash
docker exec -it news-aggregator-db psql -U newsaggregator -d news_aggregator
```

### Внутри psql

```sql
-- Список всех схем
\dn

-- Список таблиц в схеме app
\dt app.*

-- Просмотр структуры таблицы
\d app.articles

-- Запрос данных
SELECT * FROM app.articles WHERE source LIKE 'reddit_%' LIMIT 5;

-- Выход
\q
```

---

## Способ 3: Python скрипт

Создайте файл `scripts/view_reddit_posts.py`:

```python
import os
import psycopg2
from psycopg2.extras import RealDictCursor

DATABASE_URL = "postgresql://newsaggregator:changeme123@localhost:5432/news_aggregator"

conn = psycopg2.connect(DATABASE_URL, cursor_factory=RealDictCursor)
cur = conn.cursor()

cur.execute("""
    SELECT 
        id, title, url, source, 
        tags[1] as score, 
        tags[2] as comments,
        tags[3] as author,
        published_date
    FROM app.articles
    WHERE source LIKE 'reddit_%'
    ORDER BY created_at DESC
    LIMIT 10
""")

posts = cur.fetchall()

for post in posts:
    print(f"\n[{post['id']}] {post['title'][:60]}...")
    print(f"    Рейтинг: {post['score']} | Комментарии: {post['comments']} | Автор: {post['author']}")
    print(f"    URL: {post['url']}")
    print(f"    Опубликовано: {post['published_date']}")

cur.close()
conn.close()
```

Запуск:
```bash
python scripts/view_reddit_posts.py
```

---

## Экспорт данных

### Из Adminer

1. Перейдите к таблице **app.articles**
2. Нажмите **"Экспорт"**
3. Выберите формат: CSV, JSON, SQL
4. Нажмите **"Экспортировать"**

### Используя psql

```bash
docker exec -it news-aggregator-db psql -U newsaggregator -d news_aggregator -c "\copy (SELECT * FROM app.articles WHERE source LIKE 'reddit_%') TO '/tmp/reddit_posts.csv' WITH CSV HEADER"

docker cp news-aggregator-db:/tmp/reddit_posts.csv ./reddit_posts.csv
```

---

## Решение проблем

### Adminer недоступен на порту 8080

Проверьте, запущен ли Adminer:

```bash
docker ps | grep adminer
```

Если не запущен:

```bash
docker compose up -d adminer
```

### Отказ в соединении

Убедитесь, что контейнер PostgreSQL работает корректно:

```bash
docker ps | grep postgres
docker logs news-aggregator-db
```

### Данные не отображаются

Проверьте, был ли выполнен парсинг:

```bash
docker logs news-aggregator-app | grep "Парсинг"
```

Запустите парсинг из Streamlit UI по адресу http://localhost:8501

---

## Примечания по безопасности

⚠️ **Предупреждение для продакшена**: Стандартные учётные данные предназначены только для разработки.

Для продакшен-развертывания:
1. Измените пароль базы данных в `.env`
2. Используйте переменные окружения для чувствительных данных
3. Ограничьте доступ к Adminer правилами firewall
4. Включите SSL для PostgreSQL подключений

---

## Краткая справка

```
URL Adminer:    http://localhost:8080
Движок:         PostgreSQL
Сервер:         postgres
Пользователь:   newsaggregator
Пароль:         changeme123
База данных:    news_aggregator
Схема:          app
Главная таблица: articles
```

---

## Дополнительные ресурсы

- [Документация Adminer](https://www.adminer.org/en/)
- [Документация PostgreSQL](https://www.postgresql.org/docs/)
- [Документация SQLAlchemy](https://docs.sqlalchemy.org/)