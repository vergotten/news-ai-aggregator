"""Тесты database."""
import pytest
from datetime import datetime
from src.models.database import RedditPost


def test_reddit_post_creation():
    """Тест создания RedditPost."""
    post = RedditPost(
        post_id="test123",
        subreddit="test",
        title="Test",
        created_utc=datetime.utcnow()
    )
    assert post.post_id == "test123"
    assert post.subreddit == "test"
