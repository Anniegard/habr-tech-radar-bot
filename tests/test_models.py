from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from habr_tech_radar.models.article import Article


def test_article_valid() -> None:
    a = Article.model_validate(
        {
            "id": "1",
            "title": "Hello",
            "url": "https://habr.com/ru/post/1/",
            "published_at": datetime(2024, 1, 1, tzinfo=UTC),
        }
    )
    assert a.title == "Hello"
    assert str(a.url).rstrip("/") == "https://habr.com/ru/post/1"


def test_article_invalid_url() -> None:
    with pytest.raises(ValidationError):
        Article.model_validate(
            {
                "id": "1",
                "title": "Hello",
                "url": "not-a-url",
            }
        )
