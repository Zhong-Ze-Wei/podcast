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
