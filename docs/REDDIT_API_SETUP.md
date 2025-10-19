# Настройка Reddit API

## Обзор

Это руководство описывает процесс получения учётных данных Reddit API и их настройку для работы с News Aggregator.

---

## Шаг 1: Создание аккаунта Reddit

Если у вас нет аккаунта Reddit:

1. Перейдите на https://www.reddit.com
2. Нажмите **"Sign Up"** (Регистрация)
3. Заполните форму регистрации
4. Подтвердите email (если требуется)

⚠️ **Важно**: Для создания приложения требуется аккаунт с подтверждённым email.

---

## Шаг 2: Создание Reddit приложения

### 1. Откройте страницу приложений

Перейдите по ссылке: https://www.reddit.com/prefs/apps

Или:
1. Войдите в Reddit
2. Откройте настройки профиля (User Settings)
3. Перейдите на вкладку **"Safety & Privacy"**
4. Прокрутите вниз до раздела **"Apps"**

### 2. Создайте новое приложение

Нажмите кнопку:
- **"are you a developer? create an app..."**
- или **"create another app..."** (если уже есть приложения)

### 3. Заполните форму

Заполните следующие поля:

| Поле | Значение | Описание |
|------|----------|----------|
| **name** | `NewsAggregator` | Название вашего приложения (любое) |
| **App type** | ☑️ **script** | Обязательно выберите "script" |
| **description** | `News aggregation bot` | Описание (необязательно) |
| **about url** | *оставить пустым* | URL с информацией о приложении (необязательно) |
| **redirect uri** | `http://localhost:8080` | Любой локальный URL (обязательно) |

⚠️ **Критично**: Тип приложения должен быть **script**, а не web app или installed app!

### 4. Нажмите "create app"

---

## Шаг 3: Получение учётных данных

После создания приложения вы увидите:

```
NewsAggregator                        [edit] [delete]
personal use script by YourUsername
```

### Где найти учётные данные:

#### 1. Client ID
Находится **под названием приложения** в виде строки символов:

```
NewsAggregator
qpyZocAcLob0M8zbug8lrg  ← Это ваш CLIENT_ID
personal use script by YourUsername
```

#### 2. Client Secret
Находится рядом с надписью **"secret"**:

```
secret: wafZuaOqukeh2lpBEakIG3emDB1bkA  ← Это ваш CLIENT_SECRET
```

⚠️ **Важно**: 
- Client Secret отображается только один раз при создании
- Если потеряли — нужно пересоздать приложение
- Не делитесь этими данными публично!

---

## Шаг 4: Настройка .env файла

### 1. Откройте файл `.env` в корне проекта

```bash
nano .env
# или
code .env
```

### 2. Обновите следующие строки:

```bash
# Reddit API Credentials
REDDIT_CLIENT_ID=qpyZocAcLob0M8zbug8lrg
REDDIT_CLIENT_SECRET=wafZuaOqukeh2lpBEakIG3emDB1bkA
REDDIT_USER_AGENT=NewsAggregatorBot/1.0 by /u/ВАШ_REDDIT_USERNAME
```

⚠️ **Замените**:
- `qpyZocAcLob0M8zbug8lrg` → ваш реальный Client ID
- `wafZuaOqukeh2lpBEakIG3emDB1bkA` → ваш реальный Client Secret
- `ВАШ_REDDIT_USERNAME` → ваше имя пользователя на Reddit

### 3. Пример заполненного .env:

```bash
# Reddit API Credentials
REDDIT_CLIENT_ID=abc123XYZ456
REDDIT_CLIENT_SECRET=def789UVW012-secret-key
REDDIT_USER_AGENT=NewsAggregatorBot/1.0 by /u/john_doe
```

---

## Шаг 5: Перезапуск приложения

После обновления `.env`:

```bash
# Остановите контейнеры
docker compose down

# Запустите заново
docker compose up -d

# Проверьте логи
docker logs news-aggregator-app
```

---

## Шаг 6: Проверка работы

### Способ 1: Через Streamlit UI

1. Откройте http://localhost:8501
2. Перейдите на вкладку **"🔴 Reddit"**
3. Выберите subreddit (например, `MachineLearning`)
4. Нажмите **"🚀 Начать парсинг Reddit"**

Ожидаемый результат:
```
✅ r/MachineLearning: 10 новых, 0 пропущено
```

### Способ 2: Проверка через логи

```bash
docker logs news-aggregator-app | grep -i reddit
```

Успешный вывод:
```
✅ r/MachineLearning: 10 новых, 0 пропущено
```

Ошибка 401:
```
❌ Ошибка r/MachineLearning: received 401 HTTP response
```

---

## Решение проблем

### ❌ Ошибка 401: Unauthorized

**Причины**:
- Неправильный Client ID или Client Secret
- Не сохранили изменения в `.env`
- Не перезапустили контейнеры

**Решение**:
1. Проверьте правильность Client ID и Secret
2. Убедитесь, что нет лишних пробелов
3. Перезапустите: `docker compose restart app`

### ❌ Ошибка 403: Forbidden

**Причины**:
- Неправильный User Agent
- Слишком много запросов (rate limit)

**Решение**:
1. Проверьте формат User Agent: `AppName/Version by /u/username`
2. Увеличьте задержку между запросами в UI

### ❌ Ошибка 429: Too Many Requests

**Причины**:
- Превышен лимит Reddit API (60 запросов/минуту)

**Решение**:
1. Подождите 1-2 минуты
2. Уменьшите количество subreddits
3. Увеличьте задержку до 5-10 секунд

### ❌ Приложение не видит .env

**Решение**:
```bash
# Проверьте, что .env в корне проекта
ls -la .env

# Убедитесь, что переменные доступны
docker exec news-aggregator-app env | grep REDDIT
```

---

## Лимиты Reddit API

### Без OAuth (только Client ID/Secret)

| Параметр | Значение |
|----------|----------|
| Запросов в минуту | 60 |
| Запросов в день | Нет лимита |
| Тип доступа | Read-only |

### Рекомендации

- ✅ Используйте задержку **минимум 3-5 секунд** между запросами
- ✅ Не парсите более **10 subreddits** за раз
- ✅ Ограничьте `max_posts` значением **50-100**
- ❌ Не делайте параллельные запросы к одному API

---

## Альтернатива: Парсинг без API

Если не хотите создавать Reddit приложение, используйте веб-скрейпер:

### 1. Переключитесь на JSON endpoint

В файле `src/app.py` измените импорт:

```python
# Было:
from src.scrapers.reddit_scraper import scrape_multiple_subreddits

# Стало:
from src.scrapers.reddit_scraper_web import scrape_multiple_subreddits
```

### 2. Удалите praw из requirements.txt

```bash
# Закомментируйте или удалите строку:
# praw==7.8.1
```

### 3. Перезапустите

```bash
docker compose up --build
```

**Преимущества**:
- ✅ Не требует API ключей
- ✅ Работает сразу "из коробки"

**Недостатки**:
- ❌ Меньше данных (нет selftext и некоторых метаданных)
- ❌ Может сломаться при изменении структуры Reddit
- ❌ Более строгий rate limit

---

## Безопасность

### ❌ НЕ ДЕЛАЙТЕ:

```bash
# НЕ коммитьте .env в Git
git add .env  # ❌ ПЛОХО!

# НЕ публикуйте ключи в коде
REDDIT_CLIENT_ID = "qpyZocAcLob0M8zbug8lrg"  # ❌ ПЛОХО!
```

### ✅ ПРАВИЛЬНО:

```bash
# Добавьте .env в .gitignore
echo ".env" >> .gitignore

# Используйте переменные окружения
REDDIT_CLIENT_ID = os.getenv("REDDIT_CLIENT_ID")  # ✅ ХОРОШО!

# Создайте .env.example для других разработчиков
cp .env .env.example
# Замените реальные значения на плейсхолдеры
```

**Пример .env.example**:

```bash
# Reddit API Credentials
REDDIT_CLIENT_ID=your_client_id_here
REDDIT_CLIENT_SECRET=your_client_secret_here
REDDIT_USER_AGENT=YourAppName/1.0 by /u/your_username
```

---

## Тестирование API вручную

### Используя curl

```bash
# Получить access token
curl -X POST -d "grant_type=client_credentials" \
  --user "CLIENT_ID:CLIENT_SECRET" \
  https://www.reddit.com/api/v1/access_token \
  -H "User-Agent: NewsAggregator/1.0"

# Запрос к API
curl -H "Authorization: bearer ACCESS_TOKEN" \
  -H "User-Agent: NewsAggregator/1.0" \
  https://oauth.reddit.com/r/MachineLearning/hot?limit=5
```

### Используя Python (вне Docker)

```python
import praw

reddit = praw.Reddit(
    client_id="ВАШ_CLIENT_ID",
    client_secret="ВАШ_CLIENT_SECRET",
    user_agent="NewsAggregator/1.0 by /u/your_username"
)

# Тест подключения
for post in reddit.subreddit("MachineLearning").hot(limit=5):
    print(post.title)
```

---

## Дополнительные ресурсы

- 📖 [Официальная документация Reddit API](https://www.reddit.com/dev/api/)
- 📖 [PRAW документация](https://praw.readthedocs.io/)
- 📖 [Reddit API Wiki](https://github.com/reddit-archive/reddit/wiki/API)
- 💬 [r/redditdev - сообщество разработчиков](https://www.reddit.com/r/redditdev/)

---

## Краткая памятка

```
1. https://www.reddit.com/prefs/apps
2. "create app" → тип "script"
3. Client ID: под названием приложения
4. Client Secret: рядом с "secret"
5. Обновить .env файл
6. docker compose restart app
7. Проверить в http://localhost:8501
```

---

## Поддержка

При возникновении проблем:

1. Проверьте логи: `docker logs news-aggregator-app`
2. Проверьте переменные: `docker exec news-aggregator-app env | grep REDDIT`
3. Убедитесь в правильности Client ID/Secret
4. Пересоздайте приложение на Reddit (если не работает)
5. Используйте альтернативный веб-скрейпер (без API)