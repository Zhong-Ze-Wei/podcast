# -*- coding: utf-8 -*-
"""自动补捞：投递到字幕队列、尊重间隔、跳过已确认无字幕的剧集"""
from datetime import datetime, timedelta

from bson import ObjectId

from app.services import transcript_queue_service
from app.services.auto_refresher import FeedAutoRefresher
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


def _queue(db):
    queue = transcript_queue_service.TranscriptQueue(db=db)
    transcript_queue_service._queue_instance = queue
    return queue


def test_sweep_enqueues_missing_transcripts_and_respects_interval():
    db = MockDB()
    _episode(db)

    refresher = FeedAutoRefresher(db)
    queue = _queue(db)
    refresher._maybe_sweep_transcripts(interval_minutes=60, limit=5)

    assert [item["title"] for item in queue.snapshot()["pending"]] == ["Ep"]

    # 间隔未到：即使又出现缺字幕剧集也不再投递
    _episode(db, guid="youtube:def")
    refresher._maybe_sweep_transcripts(interval_minutes=60, limit=5)
    assert queue.snapshot()["queued_count"] == 1

    # 间隔已过：扫新剧集
    refresher._last_transcript_sweep = datetime.utcnow() - timedelta(minutes=61)
    refresher._maybe_sweep_transcripts(interval_minutes=60, limit=5)
    assert queue.snapshot()["queued_count"] == 2


def test_sweep_skips_confirmed_no_subtitle_episodes():
    """已确认无字幕的剧集不再重试；限流/超时类仍然会再扫。"""
    db = MockDB()
    _episode(db, guid="youtube:keep")           # 限流失败，应重试
    _episode(db, guid="youtube:skip")           # 确认无字幕，应跳过
    db.episodes._data[-1]["transcript_fetch_error"] = "No subtitles available for this video"

    queue = _queue(db)
    FeedAutoRefresher(db)._maybe_sweep_transcripts(interval_minutes=60, limit=10)

    assert [item["guid"] for item in queue.snapshot()["pending"]] == ["youtube:keep"]


def test_sweep_uses_configured_batch_size():
    db = MockDB()
    for index in range(4):
        _episode(db, guid=f"youtube:{index}")

    queue = _queue(db)
    FeedAutoRefresher(db)._maybe_sweep_transcripts(interval_minutes=60, limit=2)
    assert queue.snapshot()["queued_count"] == 2
