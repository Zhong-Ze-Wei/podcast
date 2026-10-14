# -*- coding: utf-8 -*-
"""自动补捞：节流间隔生效、成功落库、失败记原因"""
from datetime import datetime, timedelta

from bson import ObjectId

from app.services.auto_refresher import FeedAutoRefresher
from app.services import youtube_service as yt_module
from tests.conftest import MockDB


def _episode(db, guid="youtube:abc", has_transcript=False):
    eid = ObjectId()
    db.episodes._data.append({
        "_id": eid, "owner_id": None, "guid": guid, "title": "Ep",
        "status": "new", "audio_type": "video/youtube",
        "has_transcript": has_transcript, "published": datetime.utcnow(),
        "created_at": datetime.utcnow(), "updated_at": datetime.utcnow(),
    })
    return eid


def test_sweep_persists_success_and_respects_interval(monkeypatch):
    db = MockDB()
    eid = _episode(db)

    refresher = FeedAutoRefresher(db)
    monkeypatch.setattr(
        yt_module.YouTubeService, "fetch_transcript",
        classmethod(lambda cls, vid, proxy=None: ({"text": "字幕内容", "segments": [{"start": 0, "end": 2, "text": "字幕内容"}], "language": "en"}, None)),
    )
    monkeypatch.setattr(
        yt_module.YouTubeService, "watchpage_reachable", classmethod(lambda cls: True),
    )  # 测试不碰真实代理/节点
    refresher._maybe_sweep_transcripts(interval_minutes=30, limit=5)

    assert db.episodes._data[0]["has_transcript"] is True
    assert db.transcripts.count_documents({}) == 1

    # 间隔未到：即使又出现缺字幕剧集也不再扫
    _episode(db, guid="youtube:def")
    refresher._maybe_sweep_transcripts(interval_minutes=30, limit=5)
    assert db.transcripts.count_documents({}) == 1

    # 间隔已过：扫新剧集
    refresher._last_transcript_sweep = datetime.utcnow() - timedelta(minutes=31)
    refresher._maybe_sweep_transcripts(interval_minutes=30, limit=5)
    assert db.transcripts.count_documents({}) == 2


def test_sweep_records_error_on_failure(monkeypatch):
    db = MockDB()
    _episode(db)

    refresher = FeedAutoRefresher(db)
    monkeypatch.setattr(
        yt_module.YouTubeService, "fetch_transcript",
        classmethod(lambda cls, vid, proxy=None: (None, "HTTP Error 429")),
    )
    monkeypatch.setattr(
        yt_module.YouTubeService, "watchpage_reachable", classmethod(lambda cls: True),
    )
    monkeypatch.setattr("time.sleep", lambda s: None)
    refresher._maybe_sweep_transcripts(interval_minutes=30, limit=5)

    assert db.episodes._data[0]["transcript_fetch_error"] == "HTTP Error 429"
    assert db.transcripts.count_documents({}) == 0


def test_sweep_skips_confirmed_no_subtitle_episodes(monkeypatch):
    """已确认无字幕的剧集不再重试；限流/超时类仍然会再扫。"""
    db = MockDB()
    eid_stuck = _episode(db, guid="youtube:keep")           # 限流失败，应重试
    eid_nosub = _episode(db, guid="youtube:skip")           # 确认无字幕，应跳过
    db.episodes._data[-1]["transcript_fetch_error"] = "No subtitles available for this video"

    calls = []

    def fake_fetch(cls, vid, proxy=None):
        calls.append(vid)
        return {"text": "字幕", "segments": [{"start": 0, "end": 1, "text": "字幕"}], "language": "en"}, None

    refresher = FeedAutoRefresher(db)
    monkeypatch.setattr(yt_module.YouTubeService, "fetch_transcript", classmethod(fake_fetch))
    monkeypatch.setattr(yt_module.YouTubeService, "watchpage_reachable", classmethod(lambda cls: True))
    monkeypatch.setattr("time.sleep", lambda s: None)
    refresher._maybe_sweep_transcripts(interval_minutes=30, limit=10)

    assert calls == ["keep"]  # 只碰了限流那集，无字幕的直接跳过
    assert db.episodes._data[0]["has_transcript"] is True
