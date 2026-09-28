# -*- coding: utf-8 -*-
"""
Feed 刷新的 owner 继承测试

刷新任务在后台线程执行，没有 HTTP 请求上下文，
episode 的 owner_id 必须继承自 feed 文档，不能回退读取请求头。
"""
from datetime import datetime

from bson import ObjectId

from app.api.feeds import _refresh_feed_sync
from app.services.auto_refresher import FeedAutoRefresher
from tests.auth_helpers import make_auth_app
from tests.conftest import MockDB


def _episode_info(guid):
    return {
        "guid": guid,
        "title": f"Episode {guid}",
        "link": "https://example.com/ep",
        "audio_url": "https://example.com/ep.mp3",
    }


def _add_feed(db, owner_id):
    feed_id = ObjectId()
    db.feeds._data.append({
        "_id": feed_id,
        "owner_id": owner_id,
        "title": "Feed",
        "rss_url": "https://example.com/feed.xml",
        "status": "active",
        "last_checked": datetime(2026, 1, 1),
    })
    return feed_id


def _parse_feed_with(guids):
    feed_info = {"title": "Feed", "episodes": [_episode_info(g) for g in guids]}
    return lambda rss_url, timeout=30: (feed_info, None)


def test_refresh_feed_without_owner_works_outside_request_context(monkeypatch):
    app = make_auth_app()
    feed_id = _add_feed(app.db, None)
    monkeypatch.setattr("app.services.rss_service.RSSService.parse_feed", _parse_feed_with(["ep-1"]))

    with app.app_context():  # 只有应用上下文，没有请求上下文
        result = _refresh_feed_sync(str(feed_id))

    assert result["new_episodes"] == 1
    episode = app.db.episodes.find_one({"feed_id": feed_id})
    assert episode["guid"] == "ep-1"
    assert episode["owner_id"] is None


def test_refresh_feed_inherits_feed_owner(monkeypatch):
    app = make_auth_app()
    feed_id = _add_feed(app.db, "user-1")
    monkeypatch.setattr("app.services.rss_service.RSSService.parse_feed", _parse_feed_with(["ep-1"]))

    with app.app_context():
        _refresh_feed_sync(str(feed_id))

    episode = app.db.episodes.find_one({"feed_id": feed_id})
    assert episode["owner_id"] == "user-1"


def test_auto_refresher_inherits_feed_owner(monkeypatch):
    db = MockDB()
    feed_id = _add_feed(db, "user-1")
    monkeypatch.setattr("app.services.rss_service.RSSService.parse_feed", _parse_feed_with(["ep-1"]))

    refresher = FeedAutoRefresher(db)
    refresher._refresh_single_feed(db.feeds.find_one({"_id": feed_id}))

    episode = db.episodes.find_one({"feed_id": feed_id})
    assert episode is not None
    assert episode["owner_id"] == "user-1"


def test_fallback_transcription_picks_oldest_eligible(monkeypatch):
    """刷新尾部自动兜底：挑最老的超3天无字幕视频剧集排队转写"""
    from datetime import datetime, timedelta
    from bson import ObjectId
    from app.api.feeds import _maybe_queue_fallback_transcription
    from app.services.youtube_service import YouTubeService

    app = make_auth_app()
    db = app.db
    old_date = datetime.utcnow() - timedelta(days=10)
    recent_date = datetime.utcnow() - timedelta(days=1)
    feed = {"_id": ObjectId(), "type": "youtube", "owner_id": None, "title": "F"}

    def _ep(guid, published, no_speech=None):
        doc = {
            "_id": ObjectId(), "feed_id": feed["_id"], "guid": guid,
            "status": "new", "published": published, "title": guid,
        }
        if no_speech:
            doc["no_speech"] = True
        db.episodes._data.append(doc)

    _ep("youtube:old1", old_date)                 # 最老 → 应被选中
    _ep("youtube:old2", old_date + timedelta(days=1))
    _ep("youtube:recent", recent_date)            # 未满3天 → 跳过
    _ep("youtube:nospeech", old_date, no_speech=True)  # 无人声 → 跳过

    captured = {}

    def fake_submit(**kwargs):
        captured.update(kwargs)
        return "task-fb"

    monkeypatch.setattr("app.api.feeds.task_queue.submit", fake_submit)

    with app.app_context():
        _maybe_queue_fallback_transcription(db, feed)

    assert captured.get("episode_id") is not None
    picked = db.episodes.find_one({"_id": ObjectId(captured["episode_id"])})
    assert picked["guid"] == "youtube:old1"
    assert picked["status"] == "transcribing"


def test_fallback_skips_recent_and_nospeech(monkeypatch):
    from datetime import datetime, timedelta
    from bson import ObjectId
    from app.api.feeds import _maybe_queue_fallback_transcription

    app = make_auth_app()
    db = app.db
    feed = {"_id": ObjectId(), "type": "youtube", "owner_id": None}
    db.episodes._data.append({
        "_id": ObjectId(), "feed_id": feed["_id"], "guid": "youtube:r",
        "status": "new", "published": datetime.utcnow() - timedelta(days=1),
    })

    called = {}
    monkeypatch.setattr("app.api.feeds.task_queue.submit", lambda **kw: called.update(kw))

    with app.app_context():
        _maybe_queue_fallback_transcription(db, feed)

    assert not called  # 未满 3 天不排队
