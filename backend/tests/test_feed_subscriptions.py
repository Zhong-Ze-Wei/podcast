# -*- coding: utf-8 -*-
"""
视频源订阅测试：YouTube 频道 / B站 UP 主
"""
from datetime import datetime

from bson import ObjectId

from app.api.feeds import feeds_bp, _refresh_youtube_channel_feed, _refresh_bilibili_feed
from app.models.feed import Feed
from app.services.bilibili_service import BilibiliService
from app.services.youtube_service import YouTubeService
from tests.auth_helpers import add_user, auth_headers, make_auth_app


def _add_feed(db, feed_type, channel_ref, title="Channel"):
    db.feeds._data.append({
        "_id": ObjectId(),
        "type": feed_type,
        "channel_ref": channel_ref,
        "owner_id": None,
        "rss_url": f"https://example.com/{channel_ref}",
        "title": title,
        "status": "active",
        "last_checked": datetime(2026, 1, 1),
    })
    return db.feeds._data[-1]


def _yt_video(vid):
    return {"video_id": vid, "title": f"Video {vid}", "published": "2026-09-01"}


def _bili_video(bvid):
    return {"bvid": bvid, "title": f"视频 {bvid}", "published": 1790000000,
            "duration": 300, "description": "", "cover": ""}


def test_refresh_youtube_channel_feed_creates_transcribed_episodes(monkeypatch):
    app = make_auth_app()
    feed = _add_feed(app.db, Feed.TYPE_YOUTUBE, "UCtest", "Dwarkesh")

    monkeypatch.setattr(YouTubeService, "fetch_channel_videos",
                        classmethod(lambda cls, cid: ([_yt_video("aaa11111111"), _yt_video("bbb22222222")], None)))
    monkeypatch.setattr(YouTubeService, "fetch_metadata",
                        classmethod(lambda cls, vid: ({"title": f"Title {vid}", "duration": 3600,
                                                       "uploader": "Dwarkesh", "thumbnail": ""}, None)))
    monkeypatch.setattr(YouTubeService, "fetch_transcript",
                        classmethod(lambda cls, vid: (
                            {"text": "hello", "segments": [{"start": 0.0, "end": 1.0, "text": "hello"}],
                             "language": "en"}, None) if vid == "aaa11111111" else (None, "no transcript")))

    with app.app_context():
        result = _refresh_youtube_channel_feed(app.db, feed)

    assert result["new_episodes"] == 2
    assert result["new_transcripts"] == 1
    assert result["transcript_failures"] == 1

    with_sub = app.db.episodes.find_one({"guid": "youtube:aaa11111111"})
    assert with_sub["status"] == "transcribed"
    assert with_sub["duration"] == 3600
    assert app.db.transcripts.find_one({"episode_id": with_sub["_id"]})["source"] == "youtube"

    without_sub = app.db.episodes.find_one({"guid": "youtube:bbb22222222"})
    assert without_sub["status"] == "new"


def test_refresh_youtube_channel_feed_marks_feed_error_on_failure(monkeypatch):
    app = make_auth_app()
    feed = _add_feed(app.db, Feed.TYPE_YOUTUBE, "UCtest")

    monkeypatch.setattr(YouTubeService, "fetch_channel_videos",
                        classmethod(lambda cls, cid: (None, "RSS failed")))

    import pytest
    with app.app_context():
        with pytest.raises(ValueError):
            _refresh_youtube_channel_feed(app.db, feed)

    stored = app.db.feeds.find_one({"_id": feed["_id"]})
    assert stored["status"] == "error"
    assert stored["check_error"] == "RSS failed"


def test_refresh_bilibili_feed_creates_transcribed_episodes(monkeypatch):
    app = make_auth_app()
    feed = _add_feed(app.db, Feed.TYPE_BILIBILI, "1208823126", "大圆镜科普")

    monkeypatch.setattr(BilibiliService, "fetch_uploader_videos",
                        classmethod(lambda cls, mid, ps=30: ([_bili_video("BV1test1111"), _bili_video("BV2test2222")], None)))
    monkeypatch.setattr(BilibiliService, "fetch_ai_subtitle",
                        classmethod(lambda cls, bvid, title="": (
                            {"text": "你好", "segments": [{"start": 0.0, "end": 2.0, "text": "你好"}],
                             "language": "zh"}, None) if bvid == "BV1test1111" else (None, "No AI subtitle available")))

    with app.app_context():
        result = _refresh_bilibili_feed(app.db, feed)

    assert result["new_episodes"] == 2
    assert result["new_transcripts"] == 1

    with_sub = app.db.episodes.find_one({"guid": "bilibili:BV1test1111"})
    assert with_sub["status"] == "transcribed"
    tr = app.db.transcripts.find_one({"episode_id": with_sub["_id"]})
    assert tr["source"] == "bilibili"
    assert tr["model"] == "bili-ai-subtitle"


def test_create_feed_routes_bilibili_space_url(monkeypatch):
    app = make_auth_app((feeds_bp, "/api/feeds"))
    user = add_user(app.db, "u1@example.com")

    monkeypatch.setattr(BilibiliService, "fetch_uploader_info",
                        classmethod(lambda cls, mid: ({"mid": mid, "name": "测试UP", "sign": "简介", "face": ""}, None)))
    monkeypatch.setattr("app.api.feeds.task_queue.submit", lambda **kw: "task-1")

    client = app.test_client()
    resp = client.post("/api/feeds", json={"rss_url": "https://space.bilibili.com/1208823126/video"},
                       headers=auth_headers(user))
    assert resp.status_code == 201
    feed = resp.get_json()["data"]
    assert feed["type"] == "bilibili"
    assert feed["title"] == "测试UP"


def test_create_feed_routes_youtube_channel_url(monkeypatch):
    app = make_auth_app((feeds_bp, "/api/feeds"))
    user = add_user(app.db, "u1@example.com")

    monkeypatch.setattr(YouTubeService, "resolve_channel",
                        classmethod(lambda cls, url: ({"channel_id": "UCx123", "title": "Test Channel"}, None)))
    monkeypatch.setattr("app.api.feeds.task_queue.submit", lambda **kw: "task-1")

    client = app.test_client()
    resp = client.post("/api/feeds", json={"rss_url": "https://www.youtube.com/@somebody/videos"},
                       headers=auth_headers(user))
    assert resp.status_code == 201
    feed = resp.get_json()["data"]
    assert feed["type"] == "youtube"
    assert feed["channel_ref"] == "UCx123"


def test_ai_subtitle_rejected_when_timeline_exceeds_duration(monkeypatch):
    """串台校验：字幕时间轴超出视频时长 → 拒收"""
    app = make_auth_app()

    meta = {"aid": 1, "cid": 2, "bvid": "BV1x", "title": "t", "duration": 100,
            "cover": "", "uploader": "u"}
    monkeypatch.setattr(BilibiliService, "fetch_video_meta",
                        classmethod(lambda cls, bvid: (meta, None)))

    nav_data = {"wbi_img": {
        "img_url": "https://a.b/i/" + "a" * 32 + ".png",
        "sub_url": "https://a.b/s/" + "b" * 32 + ".png",
    }}
    player_data = {"subtitle": {"subtitles": [
        {"lan": "ai-zh", "subtitle_url": "https://example.com/sub.json"}]}}

    def fake_get(cls, path, params=None, referer=None):
        if "nav" in path:
            return (nav_data, None)
        return (player_data, None)

    monkeypatch.setattr(BilibiliService, "_get", classmethod(fake_get))

    class FakeResp:
        def __init__(self, body):
            self._body = body
        def json(self):
            return self._body

    mismatched = {"body": [{"from": 0, "to": 150, "content": "串台字幕"}]}
    monkeypatch.setattr("curl_cffi.requests.get",
                        lambda url, **kw: FakeResp(mismatched))

    result, error = BilibiliService.fetch_ai_subtitle("BV1x")
    assert result is None
    assert "rejected" in error

    normal = {"body": [{"from": 0, "to": 90, "content": "正常字幕"},
                       {"from": 90, "to": 99, "content": "第二行"}]}
    monkeypatch.setattr("curl_cffi.requests.get",
                        lambda url, **kw: FakeResp(normal))
    result, error = BilibiliService.fetch_ai_subtitle("BV1x")
    assert error is None
    assert result["text"] == "正常字幕 第二行"
