import requests

from app.services.rss_service import RSSService


class FakeResponse:
    def __init__(self, content=b"", status_code=200):
        self.content = content
        self.status_code = status_code

    def raise_for_status(self):
        if self.status_code >= 400:
            raise requests.exceptions.HTTPError(response=self)


def test_parse_feed_classifies_not_found(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse(status_code=404))

    feed_info, error = RSSService.parse_feed("https://example.com/missing.xml")

    assert feed_info is None
    assert "not found" in error.lower() or "moved" in error.lower()


def test_parse_feed_classifies_ssl_error(monkeypatch):
    def raise_ssl(*args, **kwargs):
        raise requests.exceptions.SSLError("certificate verify failed")

    monkeypatch.setattr(requests, "get", raise_ssl)

    feed_info, error = RSSService.parse_feed("https://example.com/feed.xml")

    assert feed_info is None
    assert "certificate" in error.lower() or "ssl" in error.lower()


def test_parse_feed_classifies_timeout(monkeypatch):
    from app.services import rss_service as rss_module

    def raise_timeout(*args, **kwargs):
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr(requests, "get", raise_timeout)
    monkeypatch.setattr(rss_module, "_curl_fetch", raise_timeout)

    feed_info, error = RSSService.parse_feed("https://example.com/feed.xml")

    assert feed_info is None
    assert "timed out" in error.lower() or "timeout" in error.lower()


def test_parse_feed_classifies_server_error(monkeypatch):
    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse(status_code=503))

    feed_info, error = RSSService.parse_feed("https://example.com/feed.xml")

    assert feed_info is None
    assert "temporarily unavailable" in error.lower() or "5xx" in error.lower()


def test_parse_feed_classifies_invalid_xml(monkeypatch):
    monkeypatch.setattr(
        requests,
        "get",
        lambda *args, **kwargs: FakeResponse(b"<rss><channel><title>broken", status_code=200),
    )

    feed_info, error = RSSService.parse_feed("https://example.com/feed.xml")

    assert feed_info is None
    assert "invalid" in error.lower() or "parse" in error.lower()


OK_RSS = b"<rss><channel><title>OK</title></channel></rss>"


def test_parse_feed_falls_back_to_chrome_fingerprint_on_connection_error(monkeypatch):
    from app.services import rss_service as rss_module

    monkeypatch.setattr(rss_module.Config, "YOUTUBE_PROXY", "")
    calls = []

    def direct_refused(*args, **kwargs):
        raise requests.exceptions.ConnectionError("connection refused")

    def fake_curl(url, headers, timeout, proxies=None):
        calls.append(proxies)
        return FakeResponse(OK_RSS, status_code=200)

    monkeypatch.setattr(requests, "get", direct_refused)
    monkeypatch.setattr(rss_module, "_curl_fetch", fake_curl)

    feed_info, error = RSSService.parse_feed("https://example.com/feed.xml")

    assert error is None
    assert feed_info["title"] == "OK"
    assert calls == [None]


def test_parse_feed_falls_back_to_chrome_fingerprint_on_403(monkeypatch):
    from app.services import rss_service as rss_module

    monkeypatch.setattr(rss_module.Config, "YOUTUBE_PROXY", "")
    calls = []

    def fake_curl(url, headers, timeout, proxies=None):
        calls.append(proxies)
        return FakeResponse(OK_RSS, status_code=200)

    monkeypatch.setattr(requests, "get", lambda *args, **kwargs: FakeResponse(status_code=403))
    monkeypatch.setattr(rss_module, "_curl_fetch", fake_curl)

    feed_info, error = RSSService.parse_feed("https://example.com/feed.xml")

    assert error is None
    assert feed_info["title"] == "OK"
    assert calls == [None]


def test_parse_feed_uses_chrome_fingerprint_proxy_as_last_resort(monkeypatch):
    from app.services import rss_service as rss_module

    monkeypatch.setattr(rss_module.Config, "YOUTUBE_PROXY", "http://127.0.0.1:7891")
    calls = []

    def direct_refused(*args, **kwargs):
        raise requests.exceptions.ConnectionError("connection refused")

    def fake_curl(url, headers, timeout, proxies=None):
        calls.append(proxies)
        if proxies is None:
            raise RuntimeError("still blocked")
        return FakeResponse(OK_RSS, status_code=200)

    monkeypatch.setattr(requests, "get", direct_refused)
    monkeypatch.setattr(rss_module, "_curl_fetch", fake_curl)

    feed_info, error = RSSService.parse_feed("https://example.com/feed.xml")

    assert error is None
    assert feed_info["title"] == "OK"
    assert calls == [None, {"http": "http://127.0.0.1:7891", "https": "http://127.0.0.1:7891"}]


def test_parse_feed_does_not_retry_404(monkeypatch):
    from app.services import rss_service as rss_module

    monkeypatch.setattr(rss_module.Config, "YOUTUBE_PROXY", "http://127.0.0.1:7891")
    calls = []

    def fake_get(*args, **kwargs):
        calls.append(1)
        return FakeResponse(status_code=404)

    def fail_curl(*args, **kwargs):
        raise AssertionError("404 should not trigger chrome-fingerprint retry")

    monkeypatch.setattr(requests, "get", fake_get)
    monkeypatch.setattr(rss_module, "_curl_fetch", fail_curl)

    feed_info, error = RSSService.parse_feed("https://example.com/feed.xml")

    assert feed_info is None
    assert "not found" in error.lower()
    assert len(calls) == 1


def test_extract_transcript_url_ignores_transcript_only_in_tracking_query():
    html = (
        '<a href="https://lexfridman.com/jeff-kaplan/'
        '?utm_source=rss&utm_medium=rss&utm_campaign=jeff-kaplan-transcript">'
        "Episode website</a>"
    )

    transcript_url = RSSService._extract_transcript_url(
        html,
        "https://lexfridman.com/jeff-kaplan/",
    )

    assert transcript_url == "https://lexfridman.com/jeff-kaplan-transcript"


def test_extract_transcript_url_supports_relative_transcript_links():
    html = '<a href="/episodes/sample-transcript">Read transcript</a>'

    transcript_url = RSSService._extract_transcript_url(
        html,
        "https://example.com/episodes/sample",
    )

    assert transcript_url == "https://example.com/episodes/sample-transcript"
