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
    def raise_timeout(*args, **kwargs):
        raise requests.exceptions.Timeout("timed out")

    monkeypatch.setattr(requests, "get", raise_timeout)

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
