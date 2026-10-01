import pytest


@pytest.mark.parametrize("url, expected", [
    (" https://EXAMPLE.com/rss/?utm_source=old&spm_id=123&category=AI ", "https://example.com/rss?category=ai"),
    ("https://example.com/rss?category=AI", "https://example.com/rss?category=ai"),
    ("https://example.com/other/rss/", "https://example.com/other/rss"),
])
def test_tracking_aliases_share_subscription_identity_without_dropping_business_query(url, expected):
    from app.services.feed_identity import normalize_feed_url
    assert normalize_feed_url(url) == expected
