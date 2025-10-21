"""CLI интерфейс."""
import argparse
import sys
from dotenv import load_dotenv

load_dotenv()


def parse_reddit(args):
    """Парсит Reddit."""
    from src.scrapers.reddit_scraper import scrape_multiple_subreddits
    from src.models.database import init_db

    print(f"🔴 Парсинг Reddit: {', '.join(args.subreddits)}")
    init_db()

    results = scrape_multiple_subreddits(
        subreddits=args.subreddits,
        max_posts=args.max_posts,
        sort_by=args.sort,
        delay=args.delay
    )

    total_saved = sum(r.get('saved', 0) for r in results if r.get('success'))
    print(f"\n✅ Завершено: {total_saved} постов")


def parse_medium(args):
    """Парсит Medium."""
    from src.scrapers.medium_scraper import scrape_multiple_sources
    from src.models.database import init_db

    print(f"📝 Парсинг Medium")
    init_db()

    results = scrape_multiple_sources(
        tags=args.tags,
        max_articles=args.max_articles,
        delay=args.delay
    )

    total_saved = sum(r.get('saved', 0) for r in results if r.get('success'))
    print(f"\n✅ Завершено: {total_saved} статей")


def show_stats(args):
    """Показывает статистику."""
    from src.models.database import get_stats_extended

    stats = get_stats_extended()

    print("=" * 60)
    print("📊 СТАТИСТИКА")
    print("=" * 60)
    print(f"Reddit:   {stats['reddit_posts']:,}")
    print(f"Telegram: {stats['telegram_messages']:,}")
    print(f"Medium:   {stats['medium_articles']:,}")
    print("=" * 60)


def main():
    parser = argparse.ArgumentParser(description='News Aggregator CLI')
    subparsers = parser.add_subparsers(dest='command')

    p_reddit = subparsers.add_parser('parse-reddit')
    p_reddit.add_argument('subreddits', nargs='+')
    p_reddit.add_argument('--max-posts', type=int, default=50)
    p_reddit.add_argument('--sort', choices=['hot', 'new', 'top'], default='hot')
    p_reddit.add_argument('--delay', type=int, default=5)
    p_reddit.set_defaults(func=parse_reddit)

    p_medium = subparsers.add_parser('parse-medium')
    p_medium.add_argument('--tags', nargs='+')
    p_medium.add_argument('--max-articles', type=int, default=30)
    p_medium.add_argument('--delay', type=int, default=3)
    p_medium.set_defaults(func=parse_medium)

    p_stats = subparsers.add_parser('stats')
    p_stats.set_defaults(func=show_stats)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    try:
        args.func(args)
    except Exception as e:
        print(f"❌ Ошибка: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()