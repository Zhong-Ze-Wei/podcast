"""自动刷新视频源、失败重试与字幕补齐的业务回归测试。"""
from datetime import datetime, timedelta

from bson import ObjectId

from app.models.episode import Episode
from app.models.feed import Feed
from app.services.auto_refresher import FeedAutoRefresher
from app.services.bilibili_service import BilibiliService
from app.services.youtube_service import YouTubeService
from tests.conftest import MockCollection, MockDB


NOW = datetime(2026, 10, 1, 12)


class FrozenDatetime(datetime):
    @classmethod
    def utcnow(cls):
        return NOW


class FeedCollection(MockCollection):
    """补充共享轻量 mock 尚未支持的 MongoDB $or。"""
    def _match(self, doc, query):
        conditions = query.get("$or")
        remaining = {key: value for key, value in query.items() if key != "$or"}
        return super()._match(doc, remaining) and (
            conditions is None or any(super(FeedCollection, self)._match(doc, item) for item in conditions)
        )


def make_db(monkeypatch):
    monkeypatch.setattr("app.services.auto_refresher.datetime", FrozenDatetime)
    db = MockDB()
    db.feeds = FeedCollection("feeds")
    return db


def add_feed(db, feed_type=Feed.TYPE_RSS, status=Feed.STATUS_ACTIVE, hours_ago=7):
    feed = Feed.create(
        "https://example.com/feed", title="Channel", type=feed_type,
        channel_ref="channel-1", owner_id="user-1",
    )
    feed.update({"_id": ObjectId(), "status": status, "last_checked": NOW - timedelta(hours=hours_ago)})
    db.feeds._data.append(feed)
    return feed


def reject_rss(monkeypatch):
    def parse_feed(*args, **kwargs):
        raise AssertionError("视频频道不应调用 RSS 解析器")
    monkeypatch.setattr("app.services.rss_service.RSSService.parse_feed", parse_feed)
    monkeypatch.setattr("time.sleep", lambda seconds: None)


def test_refresh_selection_retries_errors_but_respects_interval_and_paused(monkeypatch):
    db = make_db(monkeypatch)
    active_old = add_feed(db)
    error_old = add_feed(db, status=Feed.STATUS_ERROR)
    active_none = add_feed(db)
    active_none["last_checked"] = None
    error_missing = add_feed(db, status=Feed.STATUS_ERROR)
    error_missing.pop("last_checked")
    add_feed(db, status=Feed.STATUS_PAUSED)
    add_feed(db, hours_ago=1)
    add_feed(db, status=Feed.STATUS_ERROR, hours_ago=1)
    add_feed(db, status=Feed.STATUS_ERROR, hours_ago=6)
    selected = []
    refresher = FeedAutoRefresher(db)
    monkeypatch.setattr(refresher, "_refresh_single_feed", lambda feed: selected.append(feed["_id"]))

    refresher._check_and_refresh_feeds()

    assert set(selected) == {active_old["_id"], error_old["_id"], active_none["_id"], error_missing["_id"]}


def test_auto_youtube_refresh_discovers_video_and_backfills_missing_subtitle(monkeypatch):
    db = make_db(monkeypatch)
    reject_rss(monkeypatch)
    feed = add_feed(db, Feed.TYPE_YOUTUBE, Feed.STATUS_ERROR)
    feed["check_error"] = "RSS parse error"
    previous = Episode.create(feed["_id"], "youtube:old", "Old", owner_id="user-1")
    db.episodes.insert_one(previous)
    videos = [{"video_id": vid, "title": vid, "published": NOW} for vid in ("old", "new")]
    monkeypatch.setattr(YouTubeService, "fetch_channel_videos", classmethod(lambda cls, channel: (videos, None)))
    monkeypatch.setattr(YouTubeService, "fetch_metadata", classmethod(lambda cls, vid: (
        {"title": vid, "duration": 120, "uploader": "Channel", "thumbnail": ""}, None)))
    monkeypatch.setattr(YouTubeService, "fetch_transcript", classmethod(lambda cls, vid: (
        {"text": f"Full transcript for {vid}", "segments": [], "language": "en"}, None)))

    FeedAutoRefresher(db)._check_and_refresh_feeds()

    stored = db.feeds.find_one({"_id": feed["_id"]})
    assert stored["status"] == Feed.STATUS_ACTIVE
    assert stored["check_error"] is None
    assert stored["episode_count"] == 2
    assert db.episodes.count_documents({"feed_id": feed["_id"]}) == 2
    for vid in ("old", "new"):
        episode = db.episodes.find_one({"guid": f"youtube:{vid}"})
        assert episode["status"] == "transcribed"
        assert episode["owner_id"] == "user-1"
        assert db.transcripts.find_one({"episode_id": episode["_id"]})["source"] == "youtube"


def test_auto_bilibili_refresh_backfills_without_refetching_existing_transcript(monkeypatch):
    db = make_db(monkeypatch)
    reject_rss(monkeypatch)
    feed = add_feed(db, Feed.TYPE_BILIBILI)
    for bvid in ("old", "done"):
        episode = Episode.create(feed["_id"], f"bilibili:{bvid}", bvid, owner_id="user-1")
        db.episodes.insert_one(episode)
        if bvid == "done":
            db.transcripts.insert_one({"episode_id": episode["_id"], "owner_id": "user-1", "text": "Existing done subtitle"})
    videos = [{"bvid": bvid, "title": bvid, "duration": 60, "cover": ""} for bvid in ("old", "new", "done")]
    monkeypatch.setattr(BilibiliService, "fetch_uploader_videos", classmethod(lambda cls, channel: (videos, None)))
    subtitle_calls = []
    def fetch_subtitle(cls, bvid, title=""):
        subtitle_calls.append(bvid)
        return {"text": f"Full subtitle for {bvid}", "segments": [], "language": "zh"}, None
    monkeypatch.setattr(BilibiliService, "fetch_ai_subtitle", classmethod(fetch_subtitle))

    FeedAutoRefresher(db)._check_and_refresh_feeds()

    assert subtitle_calls == ["old", "new"]
    assert db.episodes.count_documents({"feed_id": feed["_id"]}) == 3
    assert db.transcripts.count_documents({"owner_id": "user-1"}) == 3
    assert db.feeds.find_one({"_id": feed["_id"]})["episode_count"] == 3
    for bvid in ("old", "new"):
        episode = db.episodes.find_one({"guid": f"bilibili:{bvid}"})
        assert db.transcripts.find_one({"episode_id": episode["_id"]})["source"] == "bilibili"


def test_failed_refresh_records_attempt_and_continues_with_other_feeds(monkeypatch):
    db = make_db(monkeypatch)
    video = add_feed(db, Feed.TYPE_YOUTUBE, Feed.STATUS_ERROR)
    rss = add_feed(db)
    calls = []
    def fetch_videos(cls, channel):
        calls.append(channel)
        return None, "upstream unavailable"
    monkeypatch.setattr(YouTubeService, "fetch_channel_videos", classmethod(fetch_videos))
    monkeypatch.setattr("app.services.rss_service.RSSService.parse_feed", lambda url: ({"episodes": []}, None))
    refresher = FeedAutoRefresher(db)

    refresher._check_and_refresh_feeds()
    refresher._check_and_refresh_feeds()

    stored = db.feeds.find_one({"_id": video["_id"]})
    assert stored["status"] == Feed.STATUS_ERROR
    assert stored["check_error"] == "upstream unavailable"
    assert stored["last_checked"] == NOW
    assert calls == ["channel-1"]
    assert db.feeds.find_one({"_id": rss["_id"]})["last_checked"] == NOW
