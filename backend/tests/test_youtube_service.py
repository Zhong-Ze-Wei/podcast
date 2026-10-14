from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from requests import Session
from requests.exceptions import ConnectionError
from youtube_transcript_api._errors import (
    IpBlocked, PoTokenRequired, TranscriptsDisabled, VideoUnplayable,
)

from app.config import Config
from app.services.youtube_service import YouTubeService
from app.services.feed_sync_service import _humanize_subtitle_error


VIDEO_ID = "MWX36ZYnsm0"


def test_error_explains_disabled_captions_instead_of_cutting_off_the_cause():
    message = YouTubeService._classify_error(TranscriptsDisabled(VIDEO_ID))
    assert "字幕" in message and "禁用" in message
    assert "Could not retrieve a transcript" not in message
    assert "频道主" not in message


def test_unplayable_error_keeps_the_actual_reason():
    message = YouTubeService._classify_error(VideoUnplayable(VIDEO_ID, "Members-only video", []))
    assert "Members-only video" in message
    assert "Could not retrieve a transcript" not in message


def test_ip_block_is_not_mislabeled_as_mismatched_subtitle():
    message = _humanize_subtitle_error(YouTubeService._classify_error(IpBlocked(VIDEO_ID)))
    assert "字幕未通过内容校验" not in message
    assert "YouTube" in message
    assert "限制" in message
    # 已保存的旧英文错误也不能被 rejected 这个词误当成内容校验拒收。
    legacy = "YouTube rejected the request (IpBlocked); check YOUTUBE_PROXY"
    assert "字幕未通过内容校验" not in _humanize_subtitle_error(legacy)
    assert "字幕未通过内容校验" in _humanize_subtitle_error("AI subtitle rejected: mismatched subtitle")


def test_unknown_transcript_error_preserves_cause_without_the_library_boilerplate():
    message = YouTubeService._classify_error(PoTokenRequired(VIDEO_ID))
    assert "Could not retrieve a transcript" not in message
    assert "YouTube" in message


def test_network_error_does_not_expose_proxy_credentials(monkeypatch):
    monkeypatch.setattr(Config, "YOUTUBE_PROXY", "http://private-user:private-password@127.0.0.1:7891")
    message = YouTubeService._classify_error(ConnectionError("SSL connection failed"))
    assert "private-user" not in message and "private-password" not in message
    assert "网络" in message or "代理" in message


def test_subtitle_client_bounds_network_time_and_retries_only_transient_failures(monkeypatch):
    captured = {}
    transcript = SimpleNamespace(language_code="en", snippets=[
        SimpleNamespace(start=1, duration=2, text=" First line "),
        SimpleNamespace(start=3, duration=2, text="Second line"),
    ])
    def api(**options):
        captured.update(options)
        return SimpleNamespace(fetch=Mock(return_value=transcript))
    monkeypatch.setattr("youtube_transcript_api.YouTubeTranscriptApi", api)
    monkeypatch.setattr(Config, "YOUTUBE_PROXY", "http://127.0.0.1:7891")
    payload, error = YouTubeService.fetch_transcript(VIDEO_ID)
    assert error is None and payload["text"] == "First line Second line"
    assert payload["segments"] == [{"start": 1, "end": 3, "text": "First line"}, {"start": 3, "end": 5, "text": "Second line"}]
    session = captured["http_client"]
    retries = session.get_adapter("https://").max_retries
    assert retries.total == 1
    assert retries.is_retry("POST", 503)
    assert not retries.is_retry("GET", 403)
    assert not retries.is_retry("GET", 429, has_retry_after=True)
    calls = []
    monkeypatch.setattr(Session, "request", lambda self, method, url, **kwargs: calls.append(kwargs))
    session.get("https://www.youtube.com/watch?v=" + VIDEO_ID)
    assert calls[0]["timeout"] == (5, 20)


@pytest.mark.parametrize("exception", [TranscriptsDisabled(VIDEO_ID), IpBlocked(VIDEO_ID)])
def test_permanent_or_blocked_failure_does_not_repeat_whole_transcript_request(monkeypatch, exception):
    fetch = Mock(side_effect=exception)
    monkeypatch.setattr("youtube_transcript_api.YouTubeTranscriptApi", lambda **kwargs: SimpleNamespace(fetch=fetch))
    # 桩掉降级层：本机配了 YOUTUBE_COOKIES 时 watchpage/yt-dlp 真的能联网成功，测试必须密闭
    monkeypatch.setattr(YouTubeService, "_fetch_transcript_watchpage",
                        classmethod(lambda cls, vid, proxy=None: (None, "Watch page unavailable")))
    monkeypatch.setattr(YouTubeService, "_fetch_transcript_ytdlp",
                        classmethod(lambda cls, vid, proxy=None: (None, "No subtitles available")))
    payload, error = YouTubeService.fetch_transcript(VIDEO_ID)
    assert payload is None and error
    assert fetch.call_count == 1
