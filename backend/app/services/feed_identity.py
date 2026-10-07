"""Subscription identity shared by imports and briefing source selection."""
from urllib.parse import urlparse, parse_qsl, urlencode, unquote


def normalize_feed_url(url: str) -> str:
    """保留已有订阅语义：去跟踪参数、尾斜杠并统一大小写。"""
    parts = urlparse((url or "").strip())
    if parts.hostname in {"youtube.com", "www.youtube.com", "m.youtube.com"}:
        path = unquote(parts.path).rstrip("/")
        for suffix in ("/videos", "/shorts", "/streams", "/featured"):
            if path.endswith(suffix):
                path = path[:-len(suffix)]
        return parts._replace(netloc="www.youtube.com", path=path, query="", fragment="").geturl().lower()
    query = urlencode([
        (key, value) for key, value in parse_qsl(parts.query)
        if not key.lower().startswith(("utm_", "spm"))
    ])
    return parts._replace(query=query, path=parts.path.rstrip("/")).geturl().lower()
