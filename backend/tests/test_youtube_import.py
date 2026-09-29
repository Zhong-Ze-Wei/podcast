# -*- coding: utf-8 -*-
"""
YouTube 视频导入测试
"""
from app.api.video_import import _import_youtube_sync, video_import_bp
from app.services.youtube_service import YouTubeService
from tests.auth_helpers import add_user, auth_headers, make_auth_app


def _mock_source(monkeypatch, title="Test Video", duration=5400):
    monkeypatch.setattr(
        YouTubeService,
        "fetch_metadata",
        classmethod(lambda cls, vid: ({"title": title, "duration": duration,
                                       "uploader": "Chan", "thumbnail": ""}, None)),
    )
    monkeypatch.setattr(
        YouTubeService,
        "fetch_transcript",
        classmethod(lambda cls, vid: ({
            "text": "hello world",
            "segments": [{"start": 0.0, "end": 2.0, "text": "hello world"}],
            "language": "en",
        }, None)),
    )


def test_extract_video_id():
    cases = {
        "https://www.youtube.com/watch?v=vif8NQcjVf0": "vif8NQcjVf0",
        "https://youtu.be/vif8NQcjVf0": "vif8NQcjVf0",
        "https://www.youtube.com/shorts/vif8NQcjVf0": "vif8NQcjVf0",
        "vif8NQcjVf0": "vif8NQcjVf0",
        "https://www.youtube.com/watch?v=short": None,
        "": None,
        "not a url at all": None,
    }
    for raw, expected in cases.items():
        assert YouTubeService.extract_video_id(raw) == expected, raw


def test_import_creates_feed_episode_and_transcript(monkeypatch):
    app = make_auth_app((video_import_bp, "/api/video-import"))
    user = add_user(app.db, "user1@example.com")
    owner_id = str(user["_id"])
    _mock_source(monkeypatch)

    with app.app_context():
        app.db  # 绑定 app.db 为 current_app.db
        from flask import current_app
        assert current_app.db is app.db
        result = _import_youtube_sync("vif8NQcjVf0", owner_id)

    assert result["already_imported"] is False
    episode = app.db.episodes.find_one({"guid": "youtube:vif8NQcjVf0"})
    assert episode is not None
    assert episode["title"] == "Test Video"
    assert episode["duration"] == 5400
    assert episode["status"] == "transcribed"

    feed = app.db.feeds.find_one({"rss_url": "youtube:import", "owner_id": owner_id})
    assert feed is not None
    assert episode["feed_id"] == feed["_id"]

    transcript = app.db.transcripts.find_one({"episode_id": episode["_id"]})
    assert transcript["source"] == "youtube"
    assert transcript["text"] == "hello world"


def test_import_twice_returns_existing(monkeypatch):
    app = make_auth_app((video_import_bp, "/api/video-import"))
    user = add_user(app.db, "user1@example.com")
    owner_id = str(user["_id"])
    _mock_source(monkeypatch)

    with app.app_context():
        first = _import_youtube_sync("vif8NQcjVf0", owner_id)
        second = _import_youtube_sync("vif8NQcjVf0", owner_id)

    assert first["already_imported"] is False
    assert second["already_imported"] is True
    assert second["episode_id"] == first["episode_id"]
    assert len(app.db.episodes._data) == 1


def test_import_endpoint_queues_task(monkeypatch):
    app = make_auth_app((video_import_bp, "/api/video-import"))
    user = add_user(app.db, "user1@example.com")

    captured = {}

    def fake_submit(**kwargs):
        captured.update(kwargs)
        return "task-123"

    monkeypatch.setattr("app.api.video_import.task_queue.submit", fake_submit)

    client = app.test_client()
    resp = client.post(
        "/api/video-import/youtube",
        json={"url": "https://www.youtube.com/watch?v=vif8NQcjVf0"},
        headers=auth_headers(user),
    )
    assert resp.status_code == 200
    assert resp.get_json()["data"]["task_id"] == "task-123"
    assert captured["task_type"] == "video_import"


def test_import_endpoint_rejects_invalid_url():
    app = make_auth_app((video_import_bp, "/api/video-import"))
    user = add_user(app.db, "user1@example.com")

    client = app.test_client()
    resp = client.post(
        "/api/video-import/youtube",
        json={"url": "https://example.com/nope"},
        headers=auth_headers(user),
    )
    assert resp.status_code == 400
    assert resp.get_json()["error_code"] == "INVALID_YOUTUBE_URL"
