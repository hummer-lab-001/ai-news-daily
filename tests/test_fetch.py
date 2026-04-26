"""fetch.py の基本動作を確認するテスト。"""

import pytest
from src.fetch import (
    Article,
    contains_exclude_keywords,
    deduplicate,
    is_within_lookback,
    normalize_url,
    passes_filter_keywords,
    title_similarity,
)
from datetime import datetime, timedelta, timezone


def make_article(**kwargs) -> Article:
    defaults = dict(
        source_name="Test",
        source_weight=1,
        title="Test Title",
        url="https://example.com/article",
        published_at=datetime.now(timezone.utc).isoformat(),
        summary_raw="",
        lang="en",
    )
    defaults.update(kwargs)
    return Article(**defaults)


def test_normalize_url():
    assert normalize_url("https://example.com/a?q=1#frag") == "https://example.com/a"
    assert normalize_url("https://example.com/b") == "https://example.com/b"


def test_title_similarity_identical():
    assert title_similarity("AI News Today", "AI News Today") == 1.0


def test_title_similarity_different():
    assert title_similarity("AI News Today", "Quantum Computing") < 0.3


def test_is_within_lookback_recent():
    recent = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
    assert is_within_lookback(recent, 24) is True


def test_is_within_lookback_old():
    old = (datetime.now(timezone.utc) - timedelta(hours=30)).isoformat()
    assert is_within_lookback(old, 24) is False


def test_contains_exclude_keywords():
    assert contains_exclude_keywords("仮想通貨の話", ["NFT", "仮想通貨"]) is True
    assert contains_exclude_keywords("AI活用事例", ["NFT", "仮想通貨"]) is False


def test_passes_filter_keywords():
    assert passes_filter_keywords("ChatGPT活用術", ["AI", "ChatGPT"]) is True
    assert passes_filter_keywords("天気予報", ["AI", "ChatGPT"]) is False
    assert passes_filter_keywords("何でもOK", None) is True


def test_deduplicate_by_url():
    a1 = make_article(url="https://example.com/a")
    a2 = make_article(url="https://example.com/a?utm=1")  # 同URLクエリ違い
    result = deduplicate([a1, a2])
    assert len(result) == 1


def test_deduplicate_by_title():
    a1 = make_article(title="OpenAI launches new model GPT-5 today")
    a2 = make_article(title="OpenAI launches new model GPT-5 today!", url="https://other.com/x")
    result = deduplicate([a1, a2])
    assert len(result) == 1
