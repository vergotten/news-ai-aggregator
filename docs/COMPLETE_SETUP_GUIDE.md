# Полное руководство по установке и настройке News Aggregator

## 📋 Содержание

1. [Системные требования](#системные-требования)
2. [Установка зависимостей](#установка-зависимостей)
3. [Развертывание проекта](#развертывание-проекта)
4. [Настройка API ключей](#настройка-api-ключей)
5. [Запуск проекта](#запуск-проекта)
6. [Проверка работоспособности](#проверка-работоспособности)
7. [Основные команды Docker](#основные-команды-docker)
8. [Использование веб-интерфейса](#использование-веб-интерфейса)
9. [Решение проблем](#решение-проблем)
10. [Полезные команды](#полезные-команды)

---

## Системные требования

### Минимальные требования

- **ОС**: Linux, macOS, Windows 10/11 (с WSL2)
- **RAM**: 4 GB (рекомендуется 8 GB)
- **Диск**: 5 GB свободного места
- **CPU**: 2 ядра (рекомендуется 4)
- **Интернет**: стабильное подключение

### Программное обеспечение

- Docker версии 20.10 или выше
- Docker Compose версии 2.0 или выше
- Git (для клонирования репозитория)
- Текстовый редактор (nano, vim, VSCode)

---

## Установка зависимостей

### Ubuntu/Debian

```bash
# Обновление системы
sudo apt update && sudo apt upgrade -y

# Установка Docker
sudo apt install -y docker.io docker-compose-v2

# Добавление пользователя в группу docker
sudo usermod -aG docker $USER

# Перелогиниться для применения изменений
newgrp docker

# Проверка установки
docker --version
docker compose version
```

### macOS

```bash
# Установка Homebrew (если нет)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Установка Docker Desktop
brew install --cask docker

# Запустить Docker Desktop из Applications
# Или через командную строку:
open -a Docker

# Проверка
docker --version
docker compose version
```

### Windows (WSL2)

```powershell
# 1. Включить WSL2
wsl --install

# 2. Установить Ubuntu из Microsoft Store
# https://www.microsoft.com/store/productId/9PDXGNCFSCZV

# 3. Установить Docker Desktop for Windows
# https://www.docker.com/products/docker-desktop

# 4. В Docker Desktop включить WSL2 integration
# Settings → Resources → WSL Integration → Enable

# 5. В WSL терминале проверить
docker --version
docker compose version
```

---

## Развертывание проекта

### Шаг 1: Получение проекта

#### Вариант А: Клонирование из Git (если есть репозиторий)

```bash
# Клонировать репозиторий
git clone https://github.com/yourusername/news-aggregator.git
cd news-aggregator
```

#### Вариант Б: Создание с нуля через setup скрипт

```bash
# Создать директорию проекта
mkdir news-aggregator
cd news-aggregator

# Скачать setup скрипт (или создать вручную)
# Скопировать содержимое setup_project.sh из артефакта

# Дать права на выполнение
chmod +x setup_project.sh

# Запустить установку
./setup_project.sh
```

### Шаг 2: Проверка структуры проекта

```bash
# Проверить созданные файлы
ls -la

# Должны быть:
# ├── docker-compose.yml
# ├── Dockerfile
# ├── .env.example
# ├── .env
# ├── init-db.sql
# ├── requirements.txt
# ├── start.sh
# ├── stop.sh
# ├── logs.sh
# ├── clean.sh
# ├── Makefile
# ├── README.md
# ├── src/
# ├── docs/
# └── tests/
```

---

## Настройка API ключей

### Шаг 1: Создание .env файла

```bash
# Если .env не существует
cp .env.example .env

# Открыть для редактирования
nano .env
```

### Шаг 2: Получение Reddit API ключей

#### 2.1 Создание Reddit приложения

1. Войдите в Reddit: https://www.reddit.com
2. Перейдите: https://www.reddit.com/prefs/apps
3. Нажмите **"create another app"** или **"are you a developer? create an app..."**
4. Заполните форму:
   - **name**: `NewsAggregator`
   - **App type**: выберите **"script"** (важно!)
   - **description**: `News aggregation bot`
   - **about url**: оставьте пустым
   - **redirect uri**: `http://localhost:8080`
5. Нажмите **"create app"**

#### 2.2 Копирование ключей

После создания вы увидите:

```
NewsAggregator
abc123XYZ456           ← Это ваш CLIENT_ID (под названием приложения)
personal use script by YourUsername

secret: def789UVW012  ← Это ваш CLIENT_SECRET (нажмите "edit" чтобы увидеть)
```

#### 2.3 Добавление в .env

```bash
# Reddit API Credentials
REDDIT_CLIENT_ID=abc123XYZ456
REDDIT_CLIENT_SECRET=def789UVW012
REDDIT_USER_AGENT=NewsAggregatorBot/1.0 by /u/ВАШ_REDDIT_USERNAME
```

⚠️ **Замените** `ВАШ_REDDIT_USERNAME` на ваше реальное имя пользователя Reddit!

### Шаг 3: Настройка паролей БД (опционально)

Для продакшена измените пароли:

```bash
# PostgreSQL
POSTGRES_PASSWORD=ваш_надежный_пароль_здесь

# N8N
N8N_BASIC_AUTH_PASSWORD=другой_надежный_пароль
```

### Шаг 4: Сохранение и проверка

```bash
# Сохранить файл (в nano: Ctrl+O, Enter, Ctrl+X)

# Проверить содержимое (без показа паролей)
cat .env | grep -v PASSWORD
```

**Подробная инструкция**: [docs/REDDIT_API_SETUP.md](docs/REDDIT_API_SETUP.md)

---

## Запуск проекта

### Вариант 1: Через start скрипт (рекомендуется)

```bash
# Запустить все сервисы
./start.sh

# Вывод:
# 🚀 Запуск News Aggregator...
# [+] Running 5/5
#  ✔ Container news-aggregator-db      Started
#  ✔ Container news-aggregator-ollama  Started
#  ✔ Container news-aggregator-app     Started
#  ✔ Container news-aggregator-n8n     Started
#  ✔ Container news-aggregator-adminer Started
#
# ✅ Сервисы запущены!
# 
# 📱 Интерфейсы:
#    Streamlit:  http://localhost:8501
#    N8N:        http://localhost:5678 (admin/admin123)
#    Adminer:    http://localhost:8080
#    Ollama:     http://localhost:11434
```

### Вариант 2: Через Docker Compose напрямую

```bash
# Запуск в фоновом режиме
docker compose up -d

# Запуск с выводом логов
docker compose up

# Запуск с пересборкой образов
docker compose up --build -d
```

### Вариант 3: Через Makefile

```bash
# Собрать образы
make build

# Запустить
make up
```

---

## Проверка работоспособности

### Шаг 1: Проверка статуса контейнеров

```bash
# Показать запущенные контейнеры
docker compose ps

# Ожидаемый вывод:
# NAME                        STATUS    PORTS
# news-aggregator-adminer     Up        0.0.0.0:8080->8080/tcp
# news-aggregator-app         Up        0.0.0.0:8501->8501/tcp
# news-aggregator-db          Up        0.0.0.0:5432->5432/tcp
# news-aggregator-n8n         Up        0.0.0.0:5678->5678/tcp
# news-aggregator-ollama      Up        0.0.0.0:11434->11434/tcp
```

### Шаг 2: Проверка логов

```bash
# Логи всех сервисов
docker compose logs

# Логи конкретного сервиса
docker compose logs app
docker compose logs postgres

# Следить за логами в реальном времени
docker compose logs -f app

# Последние 100 строк
docker compose logs --tail=100 app
```

### Шаг 3: Проверка базы данных

```bash
# Подключиться к PostgreSQL
docker exec -it news-aggregator-db psql -U newsaggregator -d news_aggregator

# Внутри psql:
\l              # Список баз данных (должны быть news_aggregator и n8n)
\c news_aggregator  # Подключиться к БД
\dn             # Список схем (должна быть app)
\dt app.*       # Список таблиц в схеме app
SELECT COUNT(*) FROM app.articles;  # Проверить данные
\q              # Выход
```

### Шаг 4: Проверка веб-интерфейсов

Откройте в браузере:

1. **Streamlit** (основное приложение): http://localhost:8501
   - Должна открыться страница "News Aggregator"
   - Три индикатора статуса API вверху

2. **Adminer** (управление БД): http://localhost:8080
   - System: PostgreSQL
   - Server: postgres
   - Username: newsaggregator
   - Password: changeme123
   - Database: news_aggregator

3. **N8N** (автоматизация): http://localhost:5678
   - Login: admin
   - Password: admin123

4. **Ollama** (LLM API): http://localhost:11434
   - Должен вернуть: "Ollama is running"

---

## Основные команды Docker

### Управление контейнерами

```bash
# Запустить все сервисы
docker compose up -d

# Остановить все сервисы
docker compose down

# Перезапустить все сервисы
docker compose restart

# Перезапустить один сервис
docker compose restart app

# Остановить один сервис
docker compose stop app

# Запустить один сервис
docker compose start app

# Удалить контейнеры и volumes (ПОТЕРЯ ДАННЫХ!)
docker compose down -v
```

### Просмотр информации

```bash
# Статус контейнеров
docker compose ps

# Подробная информация
docker compose ps -a

# Логи
docker compose logs app
docker compose logs -f app  # следить в реальном времени
docker compose logs --tail=50 app  # последние 50 строк

# Использование ресурсов
docker stats

# Использование дискового пространства
docker system df
docker system df -v  # подробно
```

### Работа с образами

```bash
# Список образов
docker images

# Пересборка образов
docker compose build

# Пересборка без кеша
docker compose build --no-cache

# Пересборка и запуск
docker compose up --build -d

# Удаление неиспользуемых образов
docker image prune
docker image prune -a  # удалить все неиспользуемые
```

### Работа с volumes

```bash
# Список volumes
docker volume ls

# Информация о volume
docker volume inspect news-aggregator_postgres_data

# Удаление volumes (ПОТЕРЯ ДАННЫХ!)
docker volume rm news-aggregator_postgres_data

# Удаление всех неиспользуемых volumes
docker volume prune
```

### Выполнение команд внутри контейнеров

```bash
# Запустить bash в контейнере
docker exec -it news-aggregator-app bash

# Запустить команду без входа в контейнер
docker exec news-aggregator-app python --version

# Подключиться к PostgreSQL
docker exec -it news-aggregator-db psql -U newsaggregator -d news_aggregator

# Просмотреть переменные окружения
docker exec news-aggregator-app env | grep REDDIT
```

### Очистка системы

```bash
# Удалить остановленные контейнеры
docker container prune

# Удалить неиспользуемые образы
docker image prune -a

# Удалить неиспользуемые volumes
docker volume prune

# Удалить всё неиспользуемое
docker system prune -a --volumes

# Показать что будет удалено (без удаления)
docker system prune --dry-run
```

---

## Использование веб-интерфейса

### Streamlit (http://localhost:8501)

#### Парсинг Reddit

1. Откройте вкладку **"🔴 Reddit"**
2. Выберите subreddits из списка или добавьте свои
3. Настройте параметры:
   - **Макс. постов**: 10-200 (рекомендуется 50)
   - **Задержка**: 3-30 секунд (рекомендуется 5)
   - **Сортировка**: hot, new или top
4. Нажмите **"🚀 Начать парсинг Reddit"**
5. Дождитесь завершения (появится сообщение "✅ Завершено!")
6. Просмотрите статистику и последние посты справа

#### Парсинг Medium

1. Откройте вкладку **"📝 Medium"**
2. Выберите теги (например: machine-learning, python)
3. Настройте параметры:
   - **Статей**: 5-50 (рекомендуется 10)
   - **Задержка**: 2-10 секунд (рекомендуется 3)
4. Нажмите **"🚀 Начать парсинг Medium"**
5. Просмотрите результаты

#### Просмотр аналитики

1. Откройте вкладку **"📊 Analytics"**
2. Увидите:
   - Общее количество постов по платформам
   - График активности
   - Статистику парсинга

### Adminer (http://localhost:8080)

См. подробную инструкцию: [docs/DATABASE_ACCESS.md](docs/DATABASE_ACCESS.md)

#### Быстрый доступ к данным:

1. Войдите с учётными данными
2. Слева выберите схему **"app"**
3. Кликните на таблицу **"articles"**
4. Нажмите **"Выбрать данные"**

#### Выполнение SQL запросов:

1. В левом меню выберите **"SQL команда"**
2. Введите запрос, например:

```sql
SELECT title, source, created_at 
FROM app.articles 
ORDER BY created_at DESC 
LIMIT 10;
```

3. Нажмите **"Выполнить"**

### N8N (http://localhost:5678)

Платформа для автоматизации парсинга.

#### Создание workflow для автоматического парсинга:

1. Войдите (admin/admin123)
2. Создайте новый workflow
3. Добавьте узел **"Schedule Trigger"**
   - Настройте расписание (например, каждый день в 9:00)
4. Добавьте узел **"HTTP Request"**
   - URL: `http://news-aggregator-app:8501`
5. Добавьте узел **"PostgreSQL"**
   - Host: postgres
   - Database: news_aggregator
   - User: newsaggregator
   - Password: changeme123
6. Активируйте workflow

---

## Решение проблем

### Проблема: Контейнеры не запускаются

```bash
# Проверить логи
docker compose logs

# Проверить статус
docker compose ps -a

# Пересоздать контейнеры
docker compose down
docker compose up -d
```

### Проблема: Порты заняты

```bash
# Проверить какой процесс использует порт 8501
sudo lsof -i :8501
# или
netstat -tulpn | grep 8501

# Убить процесс
sudo kill -9 PID

# Или изменить порт в .env
APP_PORT=8502
docker compose up -d
```

### Проблема: Reddit API возвращает 401

```bash
# Проверить переменные окружения
docker exec news-aggregator-app env | grep REDDIT

# Убедиться что REDDIT_CLIENT_ID и SECRET заполнены
nano .env

# Перезапустить контейнер
docker compose restart app
```

### Проблема: База данных не инициализируется

```bash
# Полная переинициализация
docker compose down -v  # УДАЛИТ ВСЕ ДАННЫЕ!
docker compose up -d

# Проверить логи PostgreSQL
docker compose logs postgres

# Проверить что схема создана
docker exec -it news-aggregator-db psql -U newsaggregator -d news_aggregator -c "\dn"
```

### Проблема: Adminer не открывается

```bash
# Проверить что контейнер запущен
docker compose ps | grep adminer

# Если нет - запустить
docker compose up -d adminer

# Проверить логи
docker compose logs adminer

# Проверить доступность порта
curl http://localhost:8080
```

### Проблема: Нет свободного места на диске

```bash
# Проверить использование Docker
docker system df

# Очистить неиспользуемые данные
docker system prune -a

# Удалить старые образы
docker image prune -a

# Удалить неиспользуемые volumes
docker volume prune
```

### Проблема: Медленная работа Docker

```bash
# Увеличить ресурсы Docker Desktop
# Settings → Resources → Advanced
# CPU: 4 ядра
# Memory: 4-8 GB

# Для Linux - проверить использование
docker stats

# Перезапустить Docker
sudo systemctl restart docker  # Linux
# или перезапустить Docker Desktop (macOS/Windows)
```

---

## Полезные команды

### Быстрые скрипты

```bash
# Запуск проекта
./start.sh

# Остановка проекта
./stop.sh

# Просмотр логов
./logs.sh app
./logs.sh postgres

# Полная очистка (с подтверждением)
./clean.sh
```

### Резервное копирование

```bash
# Бэкап базы данных
docker exec news-aggregator-db pg_dump -U newsaggregator news_aggregator > backup_$(date +%Y%m%d).sql

# Восстановление из бэкапа
docker exec -i news-aggregator-db psql -U newsaggregator news_aggregator < backup_20241012.sql

# Экспорт данных в CSV
docker exec -i news-aggregator-db psql -U newsaggregator -d news_aggregator -c "\copy (SELECT * FROM app.articles) TO STDOUT WITH CSV HEADER" > articles.csv
```

### Мониторинг

```bash
# Следить за логами всех сервисов
docker compose logs -f

# Показать использование ресурсов
docker stats

# Проверить здоровье контейнеров
docker compose ps

# Проверить сеть
docker network ls
docker network inspect news-aggregator_news-aggregator-network
```

### Отладка

```bash
# Войти в контейнер приложения
docker exec -it news-aggregator-app bash

# Проверить Python зависимости
docker exec news-aggregator-app pip list

# Проверить доступность БД из приложения
docker exec news-aggregator-app python -c "import psycopg2; print('OK')"

# Запустить Python скрипт
docker exec news-aggregator-app python src/cli.py stats
```

---

## Дополнительные ресурсы

### Документация проекта

- [README.md](README.md) - Основная документация
- [docs/DATABASE_ACCESS.md](docs/DATABASE_ACCESS.md) - Работа с базой данных
- [docs/REDDIT_API_SETUP.md](docs/REDDIT_API_SETUP.md) - Настройка Reddit API

### Внешние ресурсы

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Reddit API Documentation](https://www.reddit.com/dev/api/)
- [PRAW Documentation](https://praw.readthedocs.io/)
- [Streamlit Documentation](https://docs.streamlit.io/)
- [PostgreSQL Documentation](https://www.postgresql.org/docs/)

---

## Поддержка

При возникновении проблем:

1. Проверьте раздел [Решение проблем](#решение-проблем)
2. Изучите логи: `docker compose logs app`
3. Проверьте документацию в папке `docs/`
4. Создайте issue в репозитории проекта

---

## Контрольный чеклист установки

- [ ] Установлен Docker и Docker Compose
- [ ] Создана структура проекта (через setup_project.sh)
- [ ] Настроен .env файл
- [ ] Получены Reddit API ключи
- [ ] Запущены все сервисы (`./start.sh`)
- [ ] Проверен статус контейнеров (`docker compose ps`)
- [ ] Открывается Streamlit (http://localhost:8501)
- [ ] Открывается Adminer (http://localhost:8080)
- [ ] База данных инициализирована (видны таблицы в Adminer)
- [ ] Успешный тестовый парсинг Reddit
- [ ] Данные появились в базе данных

✅ Если все пункты отмечены - установка завершена успешно!

---

**Последнее обновление**: 2025-10-12  
**Версия документа**: 1.0