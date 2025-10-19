"""Medium scraper."""
import requests
import time
from datetime import datetime
from bs4 import BeautifulSoup
from src.models.database import save_medium_article


class MediumScraper:
    """Scraper для Medium."""

    FREEDIUM_BASE = "https://freedium.cfd"
    MEDIUM_BASE = "https://medium.com"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0'
        })

    def get_tag_articles(self, tag, max_articles=50):
        """Получает статьи по тегу."""
        tag_url = f"{self.MEDIUM_BASE}/tag/{tag}"
        print(f"🔍 Парсинг тега: {tag}")

        try:
            response = self.session.get(tag_url, timeout=10)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            articles = []
            for link in soup.find_all('a', href=True):
                href = link.get('href', '')
                if 'medium.com' in href and '/' in href:
                    article_url = href.split('?')[0]
                    if article_url not in articles and len(articles) < max_articles:
                        articles.append(article_url)

            print(f"✅ Найдено {len(articles)} статей")
            return articles[:max_articles]
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return []

    def scrape_article(self, url):
        """Парсит статью."""
        freedium_url = f"{self.FREEDIUM_BASE}/{url}"
        try:
            response = self.session.get(freedium_url, timeout=15)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, 'html.parser')

            title = soup.find('h1')
            title = title.get_text() if title else 'Untitled'

            article_body = soup.find('article')
            full_text = article_body.get_text(separator='\n', strip=True) if article_body else ''

            return {
                'url': url,
                'title': title,
                'author': 'Unknown',
                'description': full_text[:300],
                'full_text': full_text,
                'claps': 0,
                'published_date': datetime.utcnow(),
                'is_paywalled': True,
                'source': 'freedium'
            }
        except Exception as e:
            print(f"❌ Ошибка: {e}")
            return None


def scrape_medium_tag(tag, max_articles=30, delay=3):
    """Парсит статьи по тегу."""
    scraper = MediumScraper()
    article_urls = scraper.get_tag_articles(tag, max_articles)

    if not article_urls:
        return {'success': False, 'tag': tag}

    saved_count = 0
    skipped_count = 0

    for url in article_urls:
        article_data = scraper.scrape_article(url)
        if article_data:
            article_data['tags'] = tag
            if save_medium_article(article_data):
                saved_count += 1
            else:
                skipped_count += 1
        time.sleep(delay)

    print(f"✅ #{tag}: {saved_count} новых, {skipped_count} пропущено")

    return {
        'success': True,
        'tag': tag,
        'saved': saved_count,
        'skipped': skipped_count
    }


def scrape_multiple_sources(users=None, tags=None, max_articles=30, delay=3):
    """Парсит несколько источников."""
    results = []
    if tags:
        for tag in tags:
            result = scrape_medium_tag(tag, max_articles, delay)
            results.append(result)
    return results
