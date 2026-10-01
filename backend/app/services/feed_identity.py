"""Subscription identity shared by imports and briefing source selection."""
from urllib.parse import urlparse, parse_qsl, urlencode


def normalize_feed_url(url: str) -> str:
    """保留已有订阅语义：去跟踪参数、尾斜杠并统一大小写。"""
    parts = urlparse((url or "").strip())
    query = urlencode([
        (key, value) for key, value in parse_qsl(parts.query)
        if not key.lower().startswith(("utm_", "spm"))
    ])
    return parts._replace(query=query, path=parts.path.rstrip("/")).geturl().lower()
