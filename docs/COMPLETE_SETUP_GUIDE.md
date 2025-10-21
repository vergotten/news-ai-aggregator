# 📰 News Aggregator - Система агрегации и обработки новостей с AI

> Комплексная платформа для автоматизированного сбора, обработки и классификации контента из Reddit, Telegram и Medium с использованием LLM, векторного поиска и семантической дедупликации

[![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)](https://www.python.org/downloads/)
[![Docker](https://img.shields.io/badge/Docker-24.0+-blue.svg)](https://www.docker.com/)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15+-green.svg)](https://www.postgresql.org/)
[![Qdrant](https://img.shields.io/badge/Qdrant-1.7+-orange.svg)](https://qdrant.tech/)
[![Ollama](https://img.shields.io/badge/Ollama-Latest-red.svg)](https://ollama.ai/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.29+-ff4b4b.svg)](https://streamlit.io/)
[![License](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## 📋 Содержание

- [О проекте](#-о-проекте)
- [Архитектура системы](#-архитектура-системы)
- [Технологический стек](#-технологический-стек)
- [Системные требования](#-системные-требования)
- [Установка Docker](#-установка-docker)
- [Установка проекта](#-установка-проекта)
- [Настройка](#-настройка)
- [Первый запуск](#-первый-запуск)
- [После установки](#-после-установки)
- [Использование системы](#-использование-системы)
- [Интерфейс и скриншоты](#-интерфейс-и-скриншоты)
- [Docker команды](#-docker-команды)
- [Решение проблем](#-решение-проблем)
- [Разработка](#-разработка)
- [Лицензия](#-лицензия)

---

## 🎯 О проекте

**News Aggregator** - это интеллектуальная система для автоматизированного сбора, обработки и классификации новостного контента из различных источников. Система использует современные технологии машинного обучения для семантического анализа, дедупликации и редакторской обработки текстов.

### Ключевые возможности

#### 🔍 Мультиисточниковый парсинг
- **Reddit**: интеграция через PRAW API с фильтрацией по subreddits
- **Telegram**: мониторинг каналов через Telethon
- **Medium**: сбор статей через RSS с фильтрацией по тегам
- Унифицированный API для добавления новых источников

#### 🤖 LLM-обработка контента
- **Автоматическая классификация**: определение является ли пост новостью
- **Редакторская обработка**: переписывание в стиле "Петербургской школы текста"
- **Генерация метаданных**: создание заголовков, тизеров и описаний для изображений
- **Модель**: GPT-OSS 20B параметров для качественной обработки

#### 🧠 Семантическая дедупликация
- **Векторные embeddings**: преобразование текста в 768-мерные векторы
- **Similarity search**: поиск похожих текстов в Qdrant
- **Умное обнаружение дубликатов**: 95% порог схожести
- **Кросс-платформенная фильтрация**: дубликаты между разными источниками

#### 📊 Управление данными
- **PostgreSQL**: структурированное хранение данных
- **Qdrant**: векторное хранилище для семантического поиска
- **Двунаправленная связь**: PostgreSQL ↔ Qdrant через UUID
- **Полнотекстовый поиск**: расширенные возможности поиска

#### 🎨 Веб-интерфейс
- **Streamlit UI**: современный responsive интерфейс
- **Live-логи**: отслеживание процесса в реальном времени
- **Просмотр данных**: фильтрация, сортировка, детальный просмотр
- **Аналитика**: графики, статистика, dashboards
- **Управление настройками**: конфигурация через UI

#### 🔄 Автоматизация
- **N8N workflows**: планировщик задач для периодического парсинга
- **Batch processing**: пакетная обработка больших объемов
- **Параллельная обработка**: настраиваемое количество потоков
- **Обработка ошибок**: retry logic с экспоненциальной задержкой

### Применение

- 📰 **Новостные порталы**: автоматизированное создание контента
- 📊 **Мониторинг брендов**: отслеживание упоминаний компании
- 🔍 **Исследования**: анализ трендов и тем в социальных медиа
- 💼 **Конкурентный анализ**: мониторинг активности конкурентов
- 📚 **Knowledge base**: построение базы знаний из разрозненных источников
- 🎓 **Образование**: исследовательские проекты по NLP и ML

---

## 🏗 Архитектура системы

### Общая схема архитектуры

![Архитектура системы](assets/diagram-2025-10-21-053351.svg)

Система построена по многоуровневой архитектуре:

**1. Data Sources Layer (Слой источников данных)**
- Внешние API: Reddit, Telegram, Medium
- Rate limiting и error handling на уровне источников
- Унифицированный интерфейс для добавления новых источников

**2. Scrapers Layer (Слой парсеров)**
- Python-модули для каждого источника
- Нормализация данных к единому формату
- Логирование и мониторинг процесса

**3. Storage Layer (Слой хранения)**
- **PostgreSQL**: реляционные данные, метаинформация
- **Qdrant**: векторные представления текстов
- **Ollama**: LLM inference server

**4. Processing Layer (Слой обработки)**
- **Deduplication Service**: проверка на дубликаты
- **Editorial Service**: редакторская обработка через LLM
- **Vectorization Service**: генерация embeddings

**5. Presentation Layer (Слой представления)**
- **Streamlit**: веб-интерфейс для пользователей
- **N8N**: автоматизация и планирование задач
- **Adminer**: администрирование базы данных

### Детальный Data Flow

```
┌─────────────────────────────────────────────────────────────────┐
│ ЭТАП 1: СБОР ДАННЫХ                                             │
├─────────────────────────────────────────────────────────────────┤
│ Reddit API (PRAW) → Получение постов из subreddits             │
│   ↓                                                              │
│ reddit_scraper.py → Парсинг и извлечение данных                │
│   ↓                                                              │
│ Нормализация: {post_id, title, selftext, author, score, ...}   │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ ЭТАП 2: ПРОВЕРКА ТОЧНЫХ ДУБЛИКАТОВ                             │
├─────────────────────────────────────────────────────────────────┤
│ PostgreSQL: SELECT * WHERE post_id = ?                          │
│   ↓                                                              │
│ Если EXISTS → STOP (дубликат)                                   │
│ Если NOT EXISTS → Продолжить                                    │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ ЭТАП 3: СОХРАНЕНИЕ В POSTGRESQL                                │
├─────────────────────────────────────────────────────────────────┤
│ INSERT INTO parsers.reddit_posts                                │
│   - Присвоен ID                                                 │
│   - Сохранены все поля                                          │
│   - Timestamp: scraped_at                                       │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ ЭТАП 4: ГЕНЕРАЦИЯ EMBEDDING                                     │
├─────────────────────────────────────────────────────────────────┤
│ Подготовка текста: title + "\n\n" + selftext                   │
│   ↓                                                              │
│ Ollama API: nomic-embed-text                                    │
│   - Input: текст (до 8K токенов)                               │
│   - Output: вектор [768 float чисел]                           │
│   - Время: ~100-200ms                                           │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ ЭТАП 5: ПРОВЕРКА СЕМАНТИЧЕСКИХ ДУБЛИКАТОВ                      │
├─────────────────────────────────────────────────────────────────┤
│ Qdrant: Similarity Search                                       │
│   - Collection: reddit_posts                                    │
│   - Method: Cosine Similarity                                   │
│   - Threshold: 0.95 (95%)                                       │
│   ↓                                                              │
│ Если similarity >= 95%:                                         │
│   - DELETE from PostgreSQL                                      │
│   - STOP (семантический дубликат)                              │
│   ↓                                                              │
│ Если уникальный:                                                │
│   - Продолжить                                                  │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ ЭТАП 6: СОХРАНЕНИЕ ВЕКТОРА                                     │
├─────────────────────────────────────────────────────────────────┤
│ Qdrant: Upsert Point                                            │
│   - Vector: [768 floats]                                        │
│   - Payload: {post_id, title, subreddit, author, score}        │
│   - Returns: UUID                                               │
│   ↓                                                              │
│ PostgreSQL: UPDATE reddit_posts SET qdrant_id = UUID           │
│   - Установлена связь PostgreSQL ↔ Qdrant                      │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ ЭТАП 7: EDITORIAL ОБРАБОТКА (LLM)                              │
├─────────────────────────────────────────────────────────────────┤
│ Загрузка промпта: config/editorial_prompt.xml                  │
│   ↓                                                              │
│ Подготовка запроса:                                             │
│   - System: "Ты профессиональный редактор..."                  │
│   - User: "Заголовок: {title}\n\nТекст:\n{selftext}"          │
│   ↓                                                              │
│ Ollama API: gpt-oss:20b                                         │
│   - Temperature: 0.3 (детерминированность)                     │
│   - Max tokens: 2000                                            │
│   - Время: 30-90 секунд                                         │
│   ↓                                                              │
│ Парсинг JSON response:                                          │
│   {                                                              │
│     "is_news": true/false,                                      │
│     "original_summary": "краткое содержание",                  │
│     "rewritten_post": "переписанный текст",                    │
│     "title": "редакторский заголовок",                         │
│     "teaser": "подводка",                                       │
│     "image_prompt": "описание для DALL-E"                      │
│   }                                                              │
│   ↓                                                              │
│ Если is_news = false → Пропустить                              │
│ Если is_news = true → Продолжить                               │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ ЭТАП 8: СОХРАНЕНИЕ ОБРАБОТАННЫХ ДАННЫХ                        │
├─────────────────────────────────────────────────────────────────┤
│ INSERT INTO parsers.processed_reddit_posts                      │
│   - original_title, original_text                               │
│   - is_news (boolean)                                           │
│   - rewritten_post, editorial_title, teaser                    │
│   - image_prompt                                                │
│   - processed_at (timestamp)                                    │
│   - processing_time (milliseconds)                              │
│   - model_used ("gpt-oss:20b")                                 │
└─────────────────────────────────────────────────────────────────┘
                              ↓
┌─────────────────────────────────────────────────────────────────┐
│ ЭТАП 9: ОТОБРАЖЕНИЕ В UI                                       │
├─────────────────────────────────────────────────────────────────┤
│ Streamlit читает данные из:                                     │
│   - parsers.reddit_posts (сырые)                               │
│   - parsers.processed_reddit_posts (обработанные)              │
│                                                                  │
│ Пользователь видит:                                             │
│   - Статистику парсинга                                        │
│   - Список постов с фильтрацией                                │
│   - Детальный просмотр каждого поста                           │
│   - Сравнение оригинала и LLM output                           │
└─────────────────────────────────────────────────────────────────┘
```

### Схема базы данных PostgreSQL

```
news_aggregator (database)
│
├── parsers (schema) ─────────────────────────────────────────────
│   │
│   ├── reddit_posts ──────────────────────────────────────────
│   │   ├── id                    SERIAL PRIMARY KEY
│   │   ├── post_id               VARCHAR(100) UNIQUE NOT NULL
│   │   ├── subreddit             VARCHAR(100) INDEXED
│   │   ├── title                 TEXT NOT NULL
│   │   ├── selftext              TEXT
│   │   ├── author                VARCHAR(100)
│   │   ├── url                   TEXT
│   │   ├── score                 INTEGER
│   │   ├── num_comments          INTEGER
│   │   ├── created_utc           TIMESTAMP INDEXED
│   │   ├── scraped_at            TIMESTAMP DEFAULT NOW() INDEXED
│   │   ├── qdrant_id             UUID (FK → Qdrant)
│   │   └── INDEXES:
│   │       - idx_post_id (post_id)
│   │       - idx_subreddit (subreddit)
│   │       - idx_created_utc (created_utc)
│   │       - idx_scraped_at (scraped_at)
│   │
│   ├── processed_reddit_posts ───────────────────────────────
│   │   ├── id                    SERIAL PRIMARY KEY
│   │   ├── post_id               VARCHAR(100) UNIQUE (FK → reddit_posts)
│   │   ├── original_title        TEXT
│   │   ├── original_text         TEXT
│   │   ├── subreddit             VARCHAR(100)
│   │   ├── is_news               BOOLEAN INDEXED
│   │   ├── original_summary      TEXT
│   │   ├── rewritten_post        TEXT
│   │   ├── editorial_title       TEXT
│   │   ├── teaser                TEXT
│   │   ├── image_prompt          TEXT
│   │   ├── processed_at          TIMESTAMP DEFAULT NOW() INDEXED
│   │   ├── processing_time       INTEGER (milliseconds)
│   │   ├── model_used            VARCHAR(50)
│   │   └── INDEXES:
│   │       - idx_is_news (is_news)
│   │       - idx_processed_at (processed_at)
│   │
│   ├── telegram_messages ────────────────────────────────────
│   │   ├── id                    SERIAL PRIMARY KEY
│   │   ├── message_id            BIGINT NOT NULL
│   │   ├── channel_username      VARCHAR(100) INDEXED
│   │   ├── text                  TEXT NOT NULL
│   │   ├── date                  TIMESTAMP INDEXED
│   │   ├── views                 INTEGER
│   │   ├── forwards              INTEGER
│   │   ├── scraped_at            TIMESTAMP DEFAULT NOW()
│   │   └── UNIQUE (channel_username, message_id)
│   │
│   └── medium_articles ──────────────────────────────────────
│       ├── id                    SERIAL PRIMARY KEY
│       ├── url                   TEXT UNIQUE NOT NULL
│       ├── title                 TEXT NOT NULL
│       ├── author                VARCHAR(200)
│       ├── full_text             TEXT
│       ├── claps                 INTEGER
│       ├── published_date        TIMESTAMP INDEXED
│       └── scraped_at            TIMESTAMP DEFAULT NOW()
│
└── n8n (database) ───────────────────────────────────────────
    └── (N8N internal tables)
```

### Архитектура Qdrant Vector Database

```
Qdrant Server (http://localhost:6333)
│
├── Collection: reddit_posts ─────────────────────────────────
│   │
│   ├── Vector Configuration:
│   │   ├── size: 768 (nomic-embed-text output dimension)
│   │   ├── distance: Cosine (для similarity search)
│   │   └── on_disk: false (хранение в RAM для скорости)
│   │
│   ├── Index Configuration:
│   │   ├── type: HNSW (Hierarchical Navigable Small World)
│   │   ├── m: 16 (количество связей на узел)
│   │   ├── ef_construct: 100 (точность построения индекса)
│   │   └── ef_search: 128 (точность поиска)
│   │
│   ├── Points (записи):
│   │   ├── id: UUID (связь с PostgreSQL)
│   │   ├── vector: [0.123, -0.456, ..., 0.789] (768 чисел)
│   │   └── payload:
│   │       ├── post_id: "abc123"
│   │       ├── title: "Заголовок поста"
│   │       ├── subreddit: "python"
│   │       ├── author: "username"
│   │       ├── score: 442
│   │       └── created_utc: "2025-10-20T18:41:00Z"
│   │
│   └── Operations:
│       ├── upsert() → Добавить/обновить вектор
│       ├── search() → Найти похожие (top-K, threshold)
│       ├── delete() → Удалить вектор по ID
│       └── get() → Получить вектор по ID
│
└── Collection: telegram_messages (аналогично)
```

### Ollama LLM Server

```
Ollama Server (http://localhost:11434)
│
├── Models ───────────────────────────────────────────────────
│   │
│   ├── gpt-oss:20b ──────────────────────────────────────
│   │   ├── Parameters: 20 billion
│   │   ├── Size on disk: ~12 GB
│   │   ├── RAM required: 12-16 GB
│   │   ├── Context window: 8192 tokens
│   │   ├── Use case: Editorial processing
│   │   └── Temperature: 0.3 (в нашей настройке)
│   │
│   └── nomic-embed-text ─────────────────────────────────
│       ├── Parameters: 137 million
│       ├── Size on disk: 274 MB
│       ├── RAM required: ~1 GB
│       ├── Output: 768-dimensional vector
│       ├── Context window: 8192 tokens
│       └── Use case: Text embeddings
│
├── API Endpoints ────────────────────────────────────────────
│   ├── POST /api/generate → Text generation
│   ├── POST /api/chat → Chat completion
│   ├── POST /api/embeddings → Generate embeddings
│   ├── GET /api/tags → List models
│   └── GET / → Health check
│
└── Configuration ────────────────────────────────────────────
    ├── gpu_layers: -1 (auto-detect GPU)
    ├── num_thread: auto
    ├── num_ctx: 8192
    └── repeat_penalty: 1.1
```

---

## 🔧 Технологический стек

### Основные компоненты

| Компонент | Технология | Назначение | Порт | Версия |
|-----------|-----------|-----------|------|--------|
| **База данных** | PostgreSQL | Хранение структурированных данных | 5432 | 15-alpine |
| **Векторная БД** | Qdrant | Хранение embeddings, similarity search | 6333, 6334 | 1.7+ |
| **LLM Сервер** | Ollama | Локальный inference для LLM | 11434 | latest |
| **Веб-интерфейс** | Streamlit | UI для пользователей | 8501 | 1.29+ |
| **Автоматизация** | N8N | Планирование задач, workflows | 5678 | latest |
| **DB Админ** | Adminer | Управление PostgreSQL через браузер | 8080 | latest |

### Python библиотеки

**Core Dependencies:**
```
streamlit>=1.29.0           # Веб-интерфейс
praw>=7.7.1                 # Reddit API
telethon>=1.34.0            # Telegram API
feedparser>=6.0.10          # Medium RSS
psycopg2-binary>=2.9.9      # PostgreSQL driver
sqlalchemy>=2.0.23          # ORM
qdrant-client>=1.7.0        # Qdrant Python SDK
requests>=2.31.0            # HTTP клиент
```

**LLM & Embeddings:**
```
ollama>=0.1.0               # Ollama Python client
langchain>=0.1.0            # LLM orchestration (опционально)
```

**Utilities:**
```
python-dotenv>=1.0.0        # Управление .env
beautifulsoup4>=4.12.2      # HTML парсинг
lxml>=4.9.3                 # XML парсинг
pandas>=2.1.4               # Анализ данных
plotly>=5.18.0              # Графики и визуализация
```

### Docker образы

```yaml
services:
  postgres:
    image: postgres:15-alpine
    volumes:
      - postgres_data:/var/lib/postgresql/data
    
  qdrant:
    image: qdrant/qdrant:latest
    volumes:
      - qdrant_data:/qdrant/storage
    
  ollama:
    image: ollama/ollama:latest
    volumes:
      - ollama_data:/root/.ollama
    
  app:
    build: .
    image: news-aggregator:latest
    
  n8n:
    image: n8nio/n8n:latest
    volumes:
      - n8n_data:/home/node/.n8n
    
  adminer:
    image: adminer:latest
```

---

## 💻 Системные требования

### Минимальные требования

- **ОС**: Linux (Ubuntu 20.04+), macOS (12+), Windows 10/11 с WSL2
- **CPU**: 4 ядра (Intel i5 / AMD Ryzen 5)
- **RAM**: 8 GB
- **Диск**: 20 GB свободного места (SSD рекомендуется)
- **Интернет**: стабильное подключение для загрузки моделей и парсинга

### Рекомендуемые требования

- **ОС**: Ubuntu 22.04 LTS / macOS 13+ / Windows 11 с WSL2
- **CPU**: 8 ядер (Intel i7 / AMD Ryzen 7 / Apple M1 Pro+)
- **RAM**: 16 GB (32 GB для комфортной работы с gpt-oss:20b)
- **Диск**: 50 GB SSD
- **Интернет**: 100 Mbps+

### Требования для LLM

**Для использования gpt-oss:20b:**
- **RAM**: минимум 12 GB свободной RAM только для модели
- **CPU**: поддержка AVX2 инструкций
- **VRAM** (опционально): NVIDIA GPU с 16+ GB для ускорения inference

**Для использования nomic-embed-text:**
- **RAM**: ~1 GB
- Работает быстро даже на CPU

### Проверка совместимости CPU

```bash
# Linux: проверка поддержки AVX2
grep avx2 /proc/cpuinfo

# macOS: все процессоры после 2013 года поддерживают
sysctl -a | grep machdep.cpu.features

# Windows (PowerShell)
Get-CimInstance -ClassName Win32_Processor | Select-Object -Property Name
```

---

## 🐋 Установка Docker

### Ubuntu / Debian

```bash
# Шаг 1: Обновление системы
sudo apt update && sudo apt upgrade -y

# Шаг 2: Установка зависимостей
sudo apt install -y \
    apt-transport-https \
    ca-certificates \
    curl \
    gnupg \
    lsb-release

# Шаг 3: Добавление GPG ключа Docker
sudo mkdir -p /etc/apt/keyrings
curl -fsSL https://download.docker.com/linux/ubuntu/gpg | \
    sudo gpg --dearmor -o /etc/apt/keyrings/docker.gpg

# Шаг 4: Добавление репозитория Docker
echo \
  "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] \
  https://download.docker.com/linux/ubuntu \
  $(lsb_release -cs) stable" | \
  sudo tee /etc/apt/sources.list.d/docker.list > /dev/null

# Шаг 5: Установка Docker Engine
sudo apt update
sudo apt install -y \
    docker-ce \
    docker-ce-cli \
    containerd.io \
    docker-buildx-plugin \
    docker-compose-plugin

# Шаг 6: Добавление пользователя в группу docker
sudo usermod -aG docker $USER

# Шаг 7: Применение изменений (или перелогиниться)
newgrp docker

# Шаг 8: Проверка установки
docker --version
docker compose version

# Ожидаемый вывод:
# Docker version 24.0.7, build afdd53b
# Docker Compose version v2.23.0
```

### macOS

```bash
# Вариант 1: Через Homebrew (рекомендуется)

# Установка Homebrew (если не установлен)
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Установка Docker Desktop
brew install --cask docker

# Запуск Docker Desktop
open -a Docker

# Подождите 30-60 секунд пока Docker Engine запустится

# Проверка
docker --version
docker compose version

# Вариант 2: Скачать напрямую с официального сайта
# https://www.docker.com/products/docker-desktop
```

### Windows с WSL2 (рекомендуется)

#### Этап 1: Установка WSL2

```powershell
# Откройте PowerShell от имени администратора
# Win + X → "Windows PowerShell (Администратор)"

# Установите WSL2
wsl --install

# Перезагрузите компьютер
```

После перезагрузки:

```powershell
# Проверьте версию WSL
wsl --list --verbose

# Должно быть:
# NAME      STATE    VERSION
# * Ubuntu  Running  2

# Если версия 1, обновите до 2:
wsl --set-version Ubuntu 2
wsl --set-default-version 2
```

#### Этап 2: Установка Docker Desktop

1. Скачайте Docker Desktop: https://www.docker.com/products/docker-desktop
2. Запустите установщик `Docker Desktop Installer.exe`
3. ✅ Убедитесь что выбрано: **"Use WSL 2 instead of Hyper-V"**
4. Завершите установку
5. Перезагрузите компьютер

#### Этап 3: Настройка интеграции с WSL

1. Откройте **Docker Desktop**
2. Перейдите: **Settings** → **Resources** → **WSL Integration**
3. ✅ Включите: **"Enable integration with my default WSL distro"**
4. ✅ Выберите: **Ubuntu** (или вашу WSL дистрибуцию)
5. Нажмите: **Apply & Restart**

#### Этап 4: Проверка в WSL терминале

```bash
# Откройте Ubuntu из меню Пуск

# Проверка установки
docker --version
docker compose version

# Тестовый запуск
docker run hello-world

# Если всё работает, увидите:
# Hello from Docker!
# This message shows that your installation appears to be working correctly.
```

### Windows без WSL (не рекомендуется)

**Внимание**: Hyper-V работает медленнее и потребляет больше ресурсов чем WSL2.

**Требования**:
- Windows 10 Pro/Enterprise/Education
- Включенный Hyper-V

**Установка**:
1. Включите Hyper-V: Панель управления → Программы → Включение/отключение компонентов Windows → ✅ Hyper-V
2. Перезагрузите
3. Установите Docker Desktop (без галочки WSL2)

---

## 📦 Установка проекта

### Вариант 1: Клонирование из Git (рекомендуется)

```bash
# Клонирование репозитория
git clone https://github.com/yourusername/news-aggregator.git

# Переход в директорию проекта
cd news-aggregator

# Проверка структуры
ls -la

# Ожидаемая структура:
# drwxr-xr-x  config/
# drwxr-xr-x  docs/
# drwxr-xr-x  src/
# drwxr-xr-x  tests/
# -rw-r--r--  .env.example
# -rw-r--r--  docker-compose.yml
# -rw-r--r--  Dockerfile
# -rw-r--r--  requirements.txt
# -rw-r--r--  README.md
```

### Вариант 2: Скачивание ZIP архива

```bash
# Скачайте архив с GitHub
wget https://github.com/yourusername/news-aggregator/archive/refs/heads/main.zip

# Распакуйте
unzip main.zip

# Переименуйте директорию
mv news-aggregator-main news-aggregator

# Перейдите в директорию
cd news-aggregator
```

### Вариант 3: Автоматическая установка через скрипт

```bash
# Создайте директорию проекта
mkdir news-aggregator
cd news-aggregator

# Скачайте setup скрипт
curl -O https://raw.githubusercontent.com/yourusername/news-aggregator/main/setup_project.sh

# Дайте права на выполнение
chmod +x setup_project.sh

# Запустите установку
./setup_project.sh

# Скрипт автоматически:
# - Создаст структуру директорий
# - Скачает все необходимые файлы
# - Настроит .env файл
# - Инициализирует базу данных
```

### Проверка структуры проекта

```bash
tree -L 2

# Должна быть следующая структура:
news-aggregator/
├── README.md                  # Эта документация
├── .env.example               # Шаблон конфигурации
├── .env                       # Ваша конфигурация (создать!)
├── docker-compose.yml         # Docker конфигурация
├── Dockerfile                 # Образ приложения
├── requirements.txt           # Python зависимости
├── Makefile                   # Полезные команды
│
├── config/                    # Конфигурационные файлы
│   ├── sources.json           # Список источников
│   └── editorial_prompt.xml   # Промпт для LLM
│
├── src/                       # Исходный код
│   ├── app.py                 # Streamlit приложение
│   ├── cli.py                 # CLI интерфейс
│   ├── models/
│   │   └── database.py        # SQLAlchemy модели
│   ├── scrapers/
│   │   ├── reddit_scraper.py
│   │   ├── medium_scraper.py
│   │   └── telegram_scraper.py
│   ├── services/
│   │   ├── ollama_service.py
│   │   ├── qdrant_service.py
│   │   ├── deduplication_service.py
│   │   └── editorial_service.py
│   └── utils/
│       ├── thread_safe_logger.py
│       └── translations.py
│
├── docs/                      # Документация
│   ├── INSTALLATION.md
│   ├── DATABASE_ACCESS.md
│   └── REDDIT_API_SETUP.md
│
├── tests/                     # Тесты
│   ├── test_scrapers.py
│   └── test_services.py
│
└── assets/                    # Ресурсы (скриншоты, диаграммы)
    ├── 01-reddit-parser-main.png
    ├── 02-parsing-live-logs.png
    └── diagram-2025-10-21-053351.svg
```

---

## ⚙️ Настройка

### Создание .env файла

```bash
# Скопируйте шаблон
cp .env.example .env

# Откройте для редактирования
nano .env
# или
vim .env
# или
code .env  # VS Code
```

### Полная конфигурация .env

```bash
# =============================================================================
# REDDIT API (ОБЯЗАТЕЛЬНО)
# =============================================================================
# Получите ключи на https://www.reddit.com/prefs/apps
REDDIT_CLIENT_ID=ваш_client_id_здесь
REDDIT_CLIENT_SECRET=ваш_client_secret_здесь
REDDIT_USER_AGENT=NewsAggregator/1.0 by /u/ВАШ_REDDIT_USERNAME

# =============================================================================
# TELEGRAM API (ОПЦИОНАЛЬНО)
# =============================================================================
# Получите на https://my.telegram.org
TELEGRAM_API_ID=
TELEGRAM_API_HASH=
TELEGRAM_PHONE=

# =============================================================================
# POSTGRESQL
# =============================================================================
POSTGRES_USER=newsaggregator
POSTGRES_PASSWORD=changeme123
POSTGRES_DB=news_aggregator
POSTGRES_PORT=5432

# Внутренний URL (для Docker)
DATABASE_URL=postgresql://newsaggregator:changeme123@postgres:5432/news_aggregator

# Внешний URL (для локального подключения)
# DATABASE_URL=postgresql://newsaggregator:changeme123@localhost:5432/news_aggregator

# =============================================================================
# QDRANT VECTOR DATABASE
# =============================================================================
QDRANT_URL=http://qdrant:6333
QDRANT_PORT=6333
QDRANT_GRPC_PORT=6334

# =============================================================================
# OLLAMA LLM SERVER
# =============================================================================
OLLAMA_BASE_URL=http://ollama:11434
OLLAMA_PORT=11434

# Модели
OLLAMA_MODEL=gpt-oss:20b
EMBEDDING_MODEL=nomic-embed-text

# =============================================================================
# APPLICATION SETTINGS
# =============================================================================
APP_PORT=8501
TZ=Europe/Moscow
DEBUG=false

# =============================================================================
# N8N AUTOMATION
# =============================================================================
N8N_PORT=5678
N8N_DB=n8n
N8N_BASIC_AUTH_ACTIVE=true
N8N_BASIC_AUTH_USER=admin
N8N_BASIC_AUTH_PASSWORD=admin123

# =============================================================================
# ADMINER (DATABASE UI)
# =============================================================================
ADMINER_PORT=8080

# =============================================================================
# LLM PROCESSING SETTINGS
# =============================================================================
# Провайдер: ollama, openai, anthropic
LLM_PROVIDER=ollama

# Модель для editorial обработки
LLM_MODEL=gpt-oss:20b

# Temperature (0.0-2.0): чем ниже - тем детерминированнее
# 0.3 - рекомендуется для новостей (факты важнее креативности)
LLM_TEMPERATURE=0.3

# Максимум токенов в ответе
LLM_MAX_TOKENS=2000

# Top-p sampling (0.0-1.0)
LLM_TOP_P=0.9

# Количество параллельных LLM запросов
# 1 - последовательная обработка (рекомендуется)
# >1 - параллельная (быстрее, но больше RAM)
MAX_PARALLEL_TASKS=1

# =============================================================================
# PARSING SETTINGS
# =============================================================================
# Значения по умолчанию для парсинга
DEFAULT_MAX_POSTS=50
DEFAULT_DELAY=5
DEFAULT_SORT=hot
DEFAULT_ENABLE_LLM=true

# Размер батча для массовой обработки
BATCH_SIZE=10

# =============================================================================
# QUALITY SETTINGS
# =============================================================================
# Минимальная длина текста для обработки (символов)
MIN_TEXT_LENGTH=50

# Включить семантическую дедупликацию
ENABLE_SEMANTIC_DEDUP=true

# Порог схожести для дедупликации (0.0-1.0)
# 0.95 = 95% схожести считается дубликатом
DEDUP_THRESHOLD=0.95

# Включить векторизацию (сохранение в Qdrant)
ENABLE_VECTORIZATION=true

# =============================================================================
# UI SETTINGS
# =============================================================================
# Максимальная длина логов в UI (строк)
LOGS_MAX_LENGTH=500

# Лимит записей по умолчанию в Data Viewer
VIEWER_DEFAULT_LIMIT=100

# Показывать debug информацию в UI
SHOW_DEBUG_INFO=false

# Язык интерфейса (ru, en)
UI_LANGUAGE=ru
```

### Получение Reddit API ключей

#### Пошаговая инструкция с деталями

**Шаг 1: Авторизация на Reddit**

1. Откройте https://www.reddit.com
2. Войдите в свой аккаунт (или создайте новый)
3. **Важно**: Используйте аккаунт старше 30 дней для надежности

**Шаг 2: Переход на страницу Apps**

1. Откройте https://www.reddit.com/prefs/apps
2. Или: Настройки → Приложения → Внизу страницы

**Шаг 3: Создание приложения**

1. Нажмите кнопку: **"are you a developer? create an app..."**
2. Заполните форму:

```
┌─────────────────────────────────────────────────────────────┐
│ Create Application                                          │
├─────────────────────────────────────────────────────────────┤
│                                                              │
│ name *                                                       │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ NewsAggregator                                          │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ App type: *                                                  │
│ ( ) web app                                                  │
│ ( ) installed app                                            │
│ (•) script          ← ВЫБЕРИТЕ ЭТО!                         │
│                                                              │
│ description:                                                 │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ News aggregation and processing bot                     │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ about url:                                                   │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ (оставьте пустым)                                       │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│ redirect uri: *                                              │
│ ┌─────────────────────────────────────────────────────────┐ │
│ │ http://localhost:8080                                   │ │
│ └─────────────────────────────────────────────────────────┘ │
│                                                              │
│         [ create app ]  [ cancel ]                           │
└─────────────────────────────────────────────────────────────┘
```

3. Нажмите: **"create app"**

**Шаг 4: Копирование credentials**

После создания вы увидите:

```
┌────────────────────────────────────────────────────────────────┐
│ NewsAggregator                                   [edit] [delete]│
├────────────────────────────────────────────────────────────────┤
│ abc123XYZ456defGHI789    ← ЭТО ВАШ CLIENT_ID                  │
│                            (строка под названием приложения)   │
│ personal use script by your_username                            │
│                                                                 │
│ http://localhost:8080                                           │
│                                                                 │
│ secret: jkl012MNO345pqrSTU678   ← ЭТО ВАШ CLIENT_SECRET       │
│         (нажмите "edit" чтобы увидеть полностью)               │
└────────────────────────────────────────────────────────────────┘
```

**CLIENT_ID** - это строка символов сразу под названием приложения (14-20 символов)
**CLIENT_SECRET** - показывается рядом со словом "secret:" (27-30 символов)

**Шаг 5: Добавление в .env**

```bash
# Откройте .env файл
nano .env

# Добавьте (замените на свои значения):
REDDIT_CLIENT_ID=abc123XYZ456defGHI789
REDDIT_CLIENT_SECRET=jkl012MNO345pqrSTU678
REDDIT_USER_AGENT=NewsAggregator/1.0 by /u/ваш_reddit_username

# Сохраните файл (Ctrl+O, Enter, Ctrl+X в nano)
```

**Важные замечания:**

⚠️ **Тип приложения**: обязательно выберите **"script"**, не "web app" и не "installed app"!

⚠️ **User Agent**: замените `ваш_reddit_username` на ваше реальное имя пользователя Reddit

⚠️ **Безопасность**: НЕ публикуйте credentials в публичных репозиториях!

**Проверка правильности:**

```bash
# После запуска системы проверьте:
docker compose logs app | grep -i reddit

# Если видите:
# ✅ "Reddit API подключен успешно" - всё работает
# ❌ "Reddit API: 401 Unauthorized" - проверьте credentials
```

### Получение Telegram API ключей (опционально)

**Шаг 1: Авторизация**

1. Откройте https://my.telegram.org
2. Войдите через Telegram (придет код в приложение)

**Шаг 2: Создание приложения**

1. Нажмите: **API Development Tools**
2. Заполните форму:
   - **App title**: NewsAggregator
   - **Short name**: newsagg
   - **Platform**: Other
   - **Description**: News aggregation bot
3. Нажмите: **Create application**

**Шаг 3: Копирование ключей**

```
App configuration
─────────────────────────────────────
App api_id:        12345678         ← API_ID
App api_hash:      abc123def456...  ← API_HASH
```

**Шаг 4: Добавление в .env**

```bash
TELEGRAM_API_ID=12345678
TELEGRAM_API_HASH=abc123def456ghi789jkl012mno345pq
TELEGRAM_PHONE=+1234567890  # Ваш номер телефона в формате +71234567890
```

---

## 🚀 Первый запуск

### Запуск через скрипт (самый простой способ)

```bash
# Дайте права на выполнение скриптов
chmod +x start.sh stop.sh logs.sh clean.sh

# Запустите систему
./start.sh
```

**Вывод в консоли:**

```
🚀 Запуск News Aggregator...

[+] Building 45.3s (15/15) FINISHED
 => [internal] load build definition from Dockerfile
 => [internal] load .dockerignore
 => [internal] load metadata for docker.io/library/python:3.11-slim
 => [1/10] FROM docker.io/library/python:3.11-slim
 => [2/10] WORKDIR /app
 => [3/10] COPY requirements.txt .
 => [4/10] RUN pip install --no-cache-dir -r requirements.txt
 => [5/10] COPY . .
 => exporting to image
 => => naming to docker.io/library/news-aggregator-app

[+] Running 7/7
 ✔ Network news-aggregator_default          Created   0.1s
 ✔ Volume "news-aggregator_postgres_data"   Created   0.0s
 ✔ Volume "news-aggregator_qdrant_data"     Created   0.0s
 ✔ Volume "news-aggregator_ollama_data"     Created   0.0s
 ✔ Volume "news-aggregator_n8n_data"        Created   0.0s
 ✔ Container news-aggregator-postgres       Started   1.2s
 ✔ Container news-aggregator-qdrant         Started   1.4s
 ✔ Container news-aggregator-ollama         Started   1.6s
 ✔ Container news-aggregator-app            Started   2.1s
 ✔ Container news-aggregator-n8n            Started   2.3s
 ✔ Container news-aggregator-adminer        Started   2.5s

✅ Все сервисы запущены успешно!

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
📱 ДОСТУПНЫЕ ИНТЕРФЕЙСЫ:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

🎨 Streamlit (основное приложение)
   http://localhost:8501
   
🔧 Adminer (управление БД)
   http://localhost:8080
   Логин:    newsaggregator
   Пароль:   changeme123
   БД:       news_aggregator
   
🔄 N8N (автоматизация)
   http://localhost:5678
   Логин:    admin
   Пароль:   admin123
   
🔍 Qdrant Dashboard (векторная БД)
   http://localhost:6333/dashboard
   
🤖 Ollama API
   http://localhost:11434

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🔍 ПОЛЕЗНЫЕ КОМАНДЫ:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Проверить статус:    docker compose ps
Просмотреть логи:    docker compose logs -f app
Остановить:          ./stop.sh
Перезапустить:       docker compose restart
Полная очистка:      ./clean.sh

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

⏳ Ожидание загрузки моделей Ollama (это может занять 10-30 минут)...
   Следите за прогрессом: docker compose logs -f ollama
```

### Запуск через Docker Compose напрямую

```bash
# Фоновый режим (detached) - рекомендуется
docker compose up -d

# С выводом логов в консоль
docker compose up

# С пересборкой образов (если меняли код)
docker compose up --build -d

# Только определенный сервис
docker compose up -d postgres qdrant
```

### Первоначальная загрузка LLM моделей

При первом запуске Ollama автоматически загрузит модели:

```bash
# Следите за процессом загрузки
docker compose logs -f ollama
```

**Вывод в консоли:**

```
ollama  | Pulling gpt-oss:20b...
ollama  | ━━━━━━━━━━━━━━━━━╸━━━━━━━━━━━━━ 45% 1.2 GB/s
ollama  | ━━━━━━━━━━━━━━━━━━━━━━━━━━━╸━━━ 78% 980 MB/s
ollama  | ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%
ollama  | ✓ gpt-oss:20b pulled successfully
ollama  | 
ollama  | Pulling nomic-embed-text...
ollama  | ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━ 100%
ollama  | ✓ nomic-embed-text pulled successfully
ollama  | 
ollama  | Ollama server is ready!
```

**Размеры моделей и время загрузки:**

| Модель | Размер | Время (100 Mbps) | Время (1 Gbps) |
|--------|--------|------------------|----------------|
| gpt-oss:20b | ~12 GB | 15-20 минут | 2-3 минуты |
| nomic-embed-text | ~274 MB | 30 секунд | 3 секунды |

**Проверка загрузки моделей:**

```bash
# Войдите в контейнер Ollama
docker exec -it news-aggregator-ollama bash

# Проверьте список моделей
ollama list

# Ожидаемый вывод:
# NAME                      ID              SIZE      MODIFIED
# gpt-oss:20b               a1b2c3d4e5f6    12 GB     2 minutes ago
# nomic-embed-text:latest   f6e5d4c3b2a1    274 MB    2 minutes ago

# Выход из контейнера
exit
```

### Проверка статуса контейнеров

```bash
docker compose ps
```

**Ожидаемый вывод:**

```
NAME                          IMAGE                     STATUS         PORTS
news-aggregator-adminer       adminer:latest            Up 5 minutes   0.0.0.0:8080->8080/tcp
news-aggregator-app           news-aggregator-app       Up 5 minutes   0.0.0.0:8501->8501/tcp
news-aggregator-n8n           n8nio/n8n:latest          Up 5 minutes   0.0.0.0:5678->5678/tcp
news-aggregator-ollama        ollama/ollama:latest      Up 5 minutes   0.0.0.0:11434->11434/tcp
news-aggregator-postgres      postgres:15-alpine        Up 5 minutes   0.0.0.0:5432->5432/tcp
news-aggregator-qdrant        qdrant/qdrant:latest      Up 5 minutes   0.0.0.0:6333-6334->6333-6334/tcp
```

**Все контейнеры должны быть в статусе `Up`!**

Если какой-то контейнер в статусе `Exited` или `Restarting`:

```bash
# Проверьте логи проблемного контейнера
docker compose logs <имя_контейнера>

# Например:
docker compose logs postgres
docker compose logs app
```

### Проверка доступности веб-интерфейсов

```bash
# Проверка Streamlit
curl -I http://localhost:8501
# Ожидается: HTTP/1.1 200 OK

# Проверка Ollama
curl http://localhost:11434
# Ожидается: Ollama is running

# Проверка Qdrant
curl http://localhost:6333/health
# Ожидается: {"status":"ok"}

# Проверка PostgreSQL
docker exec news-aggregator-postgres pg_isready -U newsaggregator
# Ожидается: /var/run/postgresql:5432 - accepting connections
```

### Первоначальная проверка базы данных

```bash
# Подключитесь к PostgreSQL
docker exec -it news-aggregator-postgres psql -U newsaggregator -d news_aggregator

# Внутри psql выполните:
```

```sql
-- Список баз данных
\l

-- Ожидается:
--                                                  List of databases
--      Name       |     Owner      | Encoding |  Collate   |   Ctype    |       Access privileges
-- ----------------+----------------+----------+------------+------------+-------------------------------
--  n8n            | newsaggregator | UTF8     | en_US.utf8 | en_US.utf8 |
--  news_aggregator| newsaggregator | UTF8     | en_US.utf8 | en_US.utf8 |
--  postgres       | newsaggregator | UTF8     | en_US.utf8 | en_US.utf8 |

-- Подключитесь к базе
\c news_aggregator

-- Список схем
\dn

-- Ожидается:
--   List of schemas
--   Name   |  Owner
-- ---------+---------------
--  parsers | newsaggregator
--  public  | pg_database_owner

-- Список таблиц в схеме parsers
\dt parsers.*

-- Ожидается:
--                     List of relations
--  Schema  |           Name            | Type  |     Owner
-- ---------+---------------------------+-------+----------------
--  parsers | medium_articles           | table | newsaggregator
--  parsers | processed_reddit_posts    | table | newsaggregator
--  parsers | reddit_posts              | table | newsaggregator
--  parsers | telegram_messages         | table | newsaggregator

-- Проверка количества записей (должно быть 0)
SELECT COUNT(*) FROM parsers.reddit_posts;

-- Выход
\q
```

---

## 🎉 После установки

### Шаг 1: Открытие Streamlit UI

Откройте браузер и перейдите: **http://localhost:8501**

![Главная страница Reddit Parser](assets/01-reddit-parser-main.png)

**Что вы должны увидеть:**

1. **Заголовок**: "Агрегатор Новостей"
2. **Индикаторы статуса** (вверху справа):
   - ✅ **Reddit API**: зеленая галочка (если настроили credentials)
   - ⚠️ **Telegram API**: желтый треугольник (если не настроили)
   - ✅ **База данных**: зеленая галочка

3. **Вкладки навигации**:
   - 🔴 Reddit
   - 💬 Telegram
   - 📝 Medium
   - 📊 Просмотр данных
   - 📈 Аналитика
   - ⚙️ Настройки

4. **Основная панель парсинга**:
   - Фильтр по категориям
   - Multi-select список subreddits
   - Настройки парсинга (макс. постов, задержка, сортировка)
   - Переключатель LLM обработки
   - Кнопка "Запустить парсинг"

5. **Боковая панель** (справа):
   - Статистика постов
   - Последние добавленные посты

### Шаг 2: Проверка базы данных через Adminer

Откройте: **http://localhost:8080**

**Вход в систему:**

```
┌────────────────────────────────────────┐
│ System:    PostgreSQL                  │
│ Server:    postgres                    │
│ Username:  newsaggregator              │
│ Password:  changeme123                 │
│ Database:  news_aggregator             │
│            [ Login ]                    │
└────────────────────────────────────────┘
```

После входа:

1. **Слева в списке** выберите схему **"parsers"**
2. Увидите таблицы:
   - `reddit_posts`
   - `processed_reddit_posts`
   - `telegram_messages`
   - `medium_articles`

3. Кликните на **`reddit_posts`**
4. Нажмите **"Выбрать данные"** (Select data)
5. Сейчас таблица пустая - это нормально

### Шаг 3: Настройка LLM параметров

![Страница настроек](assets/08-settings-llm-config.png)

1. Откройте вкладку **⚙️ Настройки** в Streamlit
2. Раскройте секцию **🤖 LLM Обработка**

**Проверьте конфигурацию:**

| Параметр | Значение | Описание |
|----------|----------|----------|
| **МОДЕЛЬ** | gpt-oss:20b | LLM для редакторской обработки |
| **MAX TOKENS** | 8000 | Максимальная длина контекста |
| **TEMPERATURE** | 0.7 | Креативность (0.0-2.0) |
| **ПАРАЛЛЕЛЬНЫХ ПОТОКОВ** | 1 | Количество одновременных запросов |

**Рекомендации по temperature:**

- **0.1-0.3**: Детерминированность, точность (для новостей)
- **0.4-0.7**: Баланс (универсально)
- **0.8-1.2**: Креативность (для генерации контента)
- **1.3-2.0**: Максимальная креативность (художественные тексты)

**Для нашей задачи рекомендуется 0.3-0.5** (факты важнее креативности)

### Шаг 4: Первый тестовый парсинг

#### 4.1 Настройка параметров

1. Вернитесь на вкладку **🔴 Reddit**
2. **Фильтр по категории**: выберите **"AI"**
3. **Subreddits**: выберите **1-2 subreddit** для теста:
   - ✅ `MachineLearning`
   - ✅ `artificial`

4. **Настройки парсинга**:
   ```
   Макс. постов:     5    (для быстрого теста)
   Задержка (сек):   5    (защита от rate limiting)
   Сортировка:       hot  (самые популярные)
   ```

5. **LLM Предобработка**: ✅ **включено**

#### 4.2 Запуск парсинга

Нажмите кнопку: **🚀 Запустить парсинг Reddit**

![Парсинг в процессе](assets/02-parsing-live-logs.png)

**Что происходит (live-логи):**

```
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
🚀 НОВАЯ СЕССИЯ #1 - 2025-10-21 05:00:17
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📊 Начало парсинга: 2 subreddits
⚙️  Настройки: max_posts=5, sort=hot, llm=ON

═══════════════════════════════════════════════════════════════

🔍 [1/2] Обработка r/MachineLearning (Editorial: ON)
─────────────────────────────────────────────────────────────

05:00:19  🔗 Подключение к Reddit API...
05:00:19  ✓ Подключено к r/MachineLearning
05:00:20  📥 Получено 5 постов

05:00:21  ⏳ [1/5] Обработка: "[D] Self-Promotion Thread"
05:00:21     ✓ Сохранено в БД (ID: 1)
05:00:21     ⏳ Проверка дубликатов...
05:00:21     🔍 Генерация embedding через Ollama...
05:00:22     ✓ Embedding создан (768-dim, 0.18s)
05:00:22     🔍 Поиск похожих в Qdrant...
05:00:22     ✓ Дубликатов не найдено (similarity < 95%)
05:00:22     💾 Сохранение вектора в Qdrant...
05:00:23     ✓ Вектор сохранен (UUID: 3y11d83d-8884...)
05:00:23     🤖 Отправка в LLM (gpt-oss:20b)...
05:00:45     ✓ LLM обработан (22.3s)
05:00:45     📰 НОВОСТЬ: "Еженедельный тред самопродвижения в ML"
05:00:45     💾 Сохранено в processed_reddit_posts

⏱️  Ожидание 5 секунд...

05:00:50  ⏳ [2/5] Обработка: "Denmark Passes Law for..."
05:00:50     ✓ Сохранено в БД (ID: 2)
05:00:50     ⏳ Проверка дубликатов...
05:00:51     🔍 Генерация embedding...
05:00:51     ✓ Embedding создан (0.15s)
05:00:51     🔍 Поиск похожих в Qdrant...
05:00:52     ✓ Уникальный пост
05:00:52     💾 Вектор сохранен
05:00:52     🤖 Отправка в LLM...
05:01:23     ✓ LLM обработан (31.1s)
05:01:23     📰 НОВОСТЬ: "Дания вводит авторские права на лицо"
05:01:23     💾 Сохранено в processed_reddit_posts

[продолжается для всех 5 постов...]

05:02:35  ✅ r/MachineLearning завершено!
05:02:35  📊 Сохранено [5]: Denmark..., Self-Promotion..., ...
05:02:35     🔹 Векторизовано: 5/5 (100%)
05:02:35     🔹 Обработано LLM: 5/5 (100%)
05:02:35     🔹 Новостей: 3/5 (60%)
05:02:35     🔹 ID дубликатов: 0
05:02:35     🔹 Семантических дубликатов: 0

═══════════════════════════════════════════════════════════════

🔍 [2/2] Обработка r/artificial (Editorial: ON)
─────────────────────────────────────────────────────────────

[аналогичный процесс...]

═══════════════════════════════════════════════════════════════
✅ ПАРСИНГ ЗАВЕРШЕН!
═══════════════════════════════════════════════════════════════

🏁 Итоговая статистика:
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
   📊 Успешно обработано: 2/2 subreddits (100%)
   💾 Всего сохранено: 10 постов
   🤖 Обработано LLM: 10 (100%)
   📰 Новостей: 6 (60%)
   ❌ ID дубликатов: 0
   🔍 Семантических дубликатов: 0
   ⏱️  Общее время: 2 мин 18 сек
   ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
```

![Парсинг завершен](assets/03-parsing-completed.png)

#### 4.3 Что происходило под капотом

**Для каждого поста:**

1. ✅ **Fetching**: Получение данных из Reddit API
2. ✅ **Exact Dedup**: Проверка `post_id` в PostgreSQL
3. ✅ **Save Raw**: Сохранение в `parsers.reddit_posts`
4. ✅ **Embedding**: Генерация 768-мерного вектора (nomic-embed-text)
5. ✅ **Semantic Dedup**: Поиск похожих в Qdrant (порог 95%)
6. ✅ **Vectorization**: Сохранение вектора в Qdrant + линк PostgreSQL
7. ✅ **LLM Processing**: Редакторская обработка (gpt-oss:20b)
8. ✅ **Save Processed**: Сохранение результата в `processed_reddit_posts`

**Затраченное время на один пост:**
- Fetching: ~1-2 сек
- Exact dedup: ~0.01 сек
- Save raw: ~0.02 сек
- Embedding: ~0.15-0.20 сек
- Semantic dedup: ~0.05-0.10 сек
- Vectorization: ~0.05 сек
- LLM processing: **~20-90 сек** (самая долгая операция)
- Save processed: ~0.03 сек

**Итого**: ~25-95 секунд на один пост (в зависимости от LLM)

### Шаг 5: Просмотр результатов

#### 5.1 В Streamlit Data Viewer

![Data Viewer - список постов](assets/04-data-viewer-list.png)

1. Откройте вкладку **📊 Просмотр данных**
2. **Режим просмотра**: выберите **"🤖 Только обработанные"**
3. **Фильтр**: ✅ **News only**
4. **Сортировка**: **"Обработаны (новые)"**
5. **Записей**: 100

**Вы увидите список постов:**

```
┌────────────────────────────────────────────────────────────────┐
│ ❌ r/Oobabooga • Is there a way to connect the text...         │
│ 💬 6 комментариев • 🔼 3 upvotes                               │
│ 📅 20 окт 18:41 → 📥 21 окт 05:02 → 🤖 21 окт 05:02          │
├────────────────────────────────────────────────────────────────┤
│ 📰 r/technology • News Outlets Won't Describe the...           │
│ 💬 42 комментария • 🔼 442 upvotes                            │
│ 📅 20 окт 16:23 → 📥 21 окт 05:16 → 🤖 21 окт 05:16          │
├────────────────────────────────────────────────────────────────┤
│ 📰 r/Futurology • World population will decline much...        │
│ 💬 128 комментариев • 🔼 234 upvotes                          │
│ 📅 20 окт 14:15 → 📥 21 окт 05:16 → 🤖 21 окт 05:16          │
└────────────────────────────────────────────────────────────────┘
```

**Легенда:**
- 📰 = Классифицировано как **новость**
- ❌ = **Не является** новостью
- 📅 = Опубликовано на Reddit
- 📥 = Получено в нашу систему
- 🤖 = Обработано LLM

#### 5.2 Детальный просмотр поста

Нажмите на любой пост чтобы открыть детальный вид.

**Вкладка "📄 Оригинал":**

![Оригинал поста](assets/05-post-detail-original.png)

```
┌────────────────────────────────────────────────────────────────┐
│ r/artificial • В Дании теперь действует закон, по которому... │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│ ✅ News        🤖 Vector        ⚡ 89440ms        gpt-oss-20b  │
│                                                                 │
│ 📅 Опубликовано:  2025-10-20 18:41  (10 ч назад)             │
│ 📥 Получено:      2025-10-21 05:01  (15 мин назад)           │
│ 🤖 Обработано:    2025-10-21 05:02  (13 мин назад)           │
│                                                                 │
├────────────────────────────────────────────────────────────────┤
│ 🎯 Оригинальный заголовок                                      │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Denmark Passes Law for Citizen Copyright over their face       │
│                                                                 │
├────────────────────────────────────────────────────────────────┤
│ 📝 Оригинальный текст                                          │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Denmark Passes Law for Citizen Copyright over their face       │
│                                                                 │
│ Denmark Passes Law for Citizen Copyright over their face       │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

**Вкладка "✏️ LLM Output":**

![LLM Output](assets/06-post-detail-llm-output.png)

```
┌────────────────────────────────────────────────────────────────┐
│ ✨ Заголовок (Teaser)                                          │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│ В Дании теперь действует закон, по которому граждане могут     │
│ претендовать на авторские права на собственное лицо, что       │
│ меняет правила использования фотографий и видео.               │
│                                                                 │
├────────────────────────────────────────────────────────────────┤
│ 📰 Редакторский заголовок                                      │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Дания вводит авторские права на лицо граждан                  │
│                                                                 │
├────────────────────────────────────────────────────────────────┤
│ ✏️ Переписанный текст (LLM Output)                            │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│ В Дании вступил в силу закон, который даёт гражданам          │
│ авторские права на собственное лицо. Это означает, что        │
│ любые фотографии и видеоматериалы, где изображено лицо,       │
│ могут использоваться только с согласия владельца, а не без    │
│ ограничений.                                                    │
│                                                                 │
│ Новый закон затрагивает широкий спектр ситуаций — от          │
│ публикации фотографий в социальных сетях до использования     │
│ изображений в коммерческих целях. Теперь для законного        │
│ использования изображения человека требуется его явное        │
│ разрешение.                                                     │
│                                                                 │
│ [продолжение статьи...]                                        │
│                                                                 │
├────────────────────────────────────────────────────────────────┤
│ 🎨 Image Prompt (для DALL-E)                                   │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│ Danish parliament building, people with cameras, citizen       │
│ rights concept, professional photography, modern legislation,  │
│ privacy protection theme                                        │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

**Вкладка "🏷️ Метаданные":**

![Метаданные](assets/07-post-detail-metadata.png)

```
┌────────────────────────────────────────────────────────────────┐
│ 📊 Метаданные обработки                                        │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│ 🤖 Модель                    gpt-oss:20b                       │
│ ⚡ Время обработки           89440ms (89.44s)                  │
│ 📅 Дата обработки            2025-10-21 05:02:43 UTC          │
│                                                                 │
├────────────────────────────────────────────────────────────────┤
│ 📝 Классификация                                               │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│ ✅ Новость                   is_news: true                     │
│                                                                 │
├────────────────────────────────────────────────────────────────┤
│ 🔍 Векторизация                                                │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│ ✅ В Qdrant                  да                                │
│ 🔑 UUID                      3y11d83d-8884-4023-a182-...       │
│ 📐 Размерность               768 (nomic-embed-text)            │
│ 🎯 Метрика                   Cosine Similarity                 │
│                                                                 │
├────────────────────────────────────────────────────────────────┤
│ 📊 Reddit метрики                                              │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│ ⬆️ Score                     442 upvotes                       │
│ 💬 Комментарии               42                                │
│ 👤 Автор                     u/username                        │
│ 📍 Subreddit                 r/artificial                      │
│                                                                 │
├────────────────────────────────────────────────────────────────┤
│ 📈 Статистика векторизации проекта                            │
├────────────────────────────────────────────────────────────────┤
│                                                                 │
│ ВСЕГО ПОСТОВ:                23                                │
│ ВЕКТОРИЗОВАНО:               22 (95.7%)                        │
│ ОБРАБОТАНО:                  22 (95.7%)                        │
│ НОВОСТЕЙ:                    6 (26.1%)                         │
│                                                                 │
└────────────────────────────────────────────────────────────────┘
```

#### 5.3 В PostgreSQL через Adminer

1. Откройте Adminer: http://localhost:8080
2. Войдите в систему
3. Выберите схему **parsers**
4. Кликните на таблицу **reddit_posts**
5. Нажмите **"Выбрать данные"**

**SQL запрос для просмотра:**

```sql
SELECT 
    title,
    subreddit,
    score,
    created_utc,
    scraped_at,
    qdrant_id IS NOT NULL AS vectorized
FROM parsers.reddit_posts
ORDER BY scraped_at DESC
LIMIT 10;
```

**Просмотр обработанных постов:**

```sql
SELECT 
    editorial_title,
    teaser,
    is_news,
    processing_time,
    processed_at
FROM parsers.processed_reddit_posts
WHERE is_news = true
ORDER BY processed_at DESC
LIMIT 10;
```

#### 5.4 В Qdrant Dashboard

1. Откройте: http://localhost:6333/dashboard
2. Перейдите: **Collections** → **reddit_posts**
3. Увидите:
   ```
   Collection: reddit_posts
   ├── Points count:    10
   ├── Vectors count:   10
   ├── Indexed vectors: 10
   └── Status:          green
   ```

4. Нажмите **"Scroll points"** чтобы увидеть данные
5. Выберите любой point чтобы увидеть:
   - Vector: массив из 768 чисел
   - Payload: метаданные (post_id, title, subreddit...)

---

## 📱 Использование системы

### Парсинг Reddit

#### Массовый парсинг множества subreddits

1. Откройте вкладку **🔴 Reddit**
2. **Фильтр по категории**: выберите **"All"** (все категории)
3. **Subreddits**: выберите несколько (Ctrl+Click или Cmd+Click):
   ```
   ✅ MachineLearning
   ✅ artificial  
   ✅ LocalLLaMA
   ✅ singularity
   ✅ StableDiffusion
   ✅ deeplearning
   ✅ learnmachinelearning
   ```

4. **Настройки**:
   ```
   Макс. постов:     50   (больше данных)
   Задержка (сек):   5    (защита от rate limit)
   Сортировка:       hot  (самые популярные)
   ```

5. ✅ **LLM Предобработка**: включено

6. Нажмите: **🚀 Запустить парсинг Reddit**

**Ожидаемое время**: ~40-60 минут для 7 subreddits × 50 постов

#### Парсинг через CLI

```bash
# Войдите в контейнер
docker exec -it news-aggregator-app bash

# Парсинг одного subreddit
python src/cli.py parse-reddit python --max-posts 10

# Парсинг нескольких subreddits
python src/cli.py parse-reddit \
    python machinelearning datascience \
    --max-posts 20 \
    --sort hot \
    --delay 5

# Без LLM обработки (быстрее)
python src/cli.py parse-reddit python --max-posts 10 --no-llm

# Другая сортировка
python src/cli.py parse-reddit python --sort new  # новые
python src/cli.py parse-reddit python --sort top  # лучшие за все время

# Просмотр статистики
python src/cli.py stats

# Ожидаемый вывод:
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 📊 СТАТИСТИКА БАЗЫ ДАННЫХ
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 
# Reddit:
#   Всего постов:        127
#   Обработано LLM:      120 (94.5%)
#   Новостей:            48 (37.8%)
#   Векторизовано:       120 (94.5%)
# 
# По subreddits:
#   MachineLearning:     45 постов
#   artificial:          38 постов
#   LocalLLaMA:          24 постов
#   python:              20 постов
```

### Парсинг Medium

```bash
# Через UI
1. Откройте вкладку "📝 Medium"
2. Выберите теги:
   ✅ machine-learning
   ✅ python
   ✅ artificial-intelligence
   ✅ data-science
3. Настройки:
   Макс статей:    10
   Задержка (сек): 3
4. Нажмите "Запустить парсинг Medium"

# Через CLI
docker exec news-aggregator-app python src/cli.py parse-medium \
    --tags machine-learning python ai \
    --max-articles 10
```

### Парсинг Telegram

```bash
# Через UI (требуется API)
1. Откройте вкладку "💬 Telegram"
2. Введите username канала (например: @durov)
3. Настройки:
   Макс сообщений: 50
   Задержка (сек): 2
4. Нажмите "Запустить парсинг Telegram"

# Через CLI
docker exec news-aggregator-app python src/cli.py parse-telegram \
    --channel durov \
    --max-messages 50
```

### Просмотр и фильтрация данных

#### Режимы просмотра

**🔴 Только сырые посты:**
- Необработанные данные из источников
- Оригинальные заголовки и тексты
- Без LLM классификации

**🤖 Только обработанные:**
- Посты прошедшие через LLM
- С редакторскими заголовками и тизерами
- Классификация: новость/не новость

**📋 Все посты:**
- Комбинированный вид
- Показывает и сырые и обработанные

#### Фильтры

```
Сортировка:
├── Получены (новые)     - по дате парсинга (DESC)
├── Получены (старые)    - по дате парсинга (ASC)
├── Обработаны (новые)   - по дате LLM обработки (DESC)
├── Обработаны (старые)  - по дате LLM обработки (ASC)
├── Рейтинг (высокий)    - по score (DESC)
└── Рейтинг (низкий)     - по score (ASC)

Лимит: 10, 50, 100, 500 записей
News only: ✅ (только is_news = true)
```

### Ручная обработка постов через LLM

#### Batch Processing (пакетная обработка)

1. Откройте вкладку **📊 Просмотр данных**
2. Раскройте секцию **🔧 Управление предобработкой**
3. Проверьте статистику:
   ```
   Сырых постов:        150
   Обработано:          80
   Необработано:        70
   ```

4. Настройте:
   ```
   Batch size:          10    (количество за раз)
   ```

5. Нажмите: **Запустить обработку**

**Процесс обработки:**

```
🤖 Начало параллельной обработки: 10 постов
Параллельных потоков: 1
Модель: gpt-oss:20b

[1/10] 🤖 Отправка в LLM: "Python 3.12 Released with..."
[1/10] ⏳ Ожидание ответа от LLM...
[1/10] ✓ Ответ получен (28.4s)