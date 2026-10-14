# -*- coding: utf-8 -*-
"""YouTube 字幕降级链：主库（youtube-transcript-api）被网络掐断时走 yt-dlp 下载 VTT 并解析"""
from app.services.youtube_service import YouTubeService

SAMPLE_VTT = """WEBVTT

00:00:01.160 --> 00:00:03.720
Hello <c>world</c> from the show

00:00:04.000 --> 00:00:06.500
Second line
continues here
"""


def test_parse_vtt_segments_strips_tags_and_merges_lines():
    segments = YouTubeService._parse_vtt_segments(SAMPLE_VTT)
    assert segments == [
        {"start": 1, "end": 3, "text": "Hello world from the show"},
        {"start": 4, "end": 6, "text": "Second line continues here"},
    ]


def test_parse_vtt_segments_empty_content():
    assert YouTubeService._parse_vtt_segments("WEBVTT\n") == []


def test_fetch_transcript_falls_back_when_primary_fails(monkeypatch):
    import sys
    import types

    calls = {"fallback": 0}

    class FakeApi:
        def __init__(self, *args, **kwargs):
            pass

        def fetch(self, video_id, languages):
            raise ConnectionError("network cut")

    # 桩掉 youtube_transcript_api 模块本身（fetch_transcript 函数内局部 import）
    stub = types.ModuleType("youtube_transcript_api")
    stub.YouTubeTranscriptApi = FakeApi
    proxies_stub = types.ModuleType("youtube_transcript_api.proxies")
    proxies_stub.GenericProxyConfig = lambda **kwargs: None
    stub.proxies = proxies_stub
    monkeypatch.setitem(sys.modules, "youtube_transcript_api", stub)
    monkeypatch.setitem(sys.modules, "youtube_transcript_api.proxies", proxies_stub)

    def fake_ytdlp(video_id, proxy=None):
        calls["fallback"] += 1
        return {"text": "备份字幕内容", "segments": [{"start": 0, "end": 2, "text": "备份字幕内容"}], "language": "zh"}, None

    monkeypatch.setattr(
        YouTubeService, "_fetch_transcript_ytdlp",
        classmethod(lambda cls, vid, proxy=None: fake_ytdlp(vid, proxy=proxy)),
    )

    result, error = YouTubeService.fetch_transcript("abc123")
    assert error is None
    assert result["text"] == "备份字幕内容"
    assert calls["fallback"] == 1
