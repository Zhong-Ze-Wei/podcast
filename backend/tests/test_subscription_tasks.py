from urllib.parse import quote
from unittest.mock import Mock

import pytest

from app.api.feeds import feeds_bp
from app.api.tasks import tasks_bp
from app.services.feed_identity import normalize_feed_url
from app.services.youtube_service import YouTubeService
from tests.auth_helpers import add_user, auth_headers, make_auth_app
from tests.test_feed_refresh_queue import RecordingQueue


HANDLE = "钦文和他的朋友们-i3u"
URL = f"https://www.youtube.com/@{HANDLE}"
ENCODED = f"https://www.youtube.com/@{quote(HANDLE)}"


@pytest.mark.parametrize("url", [URL, ENCODED, ENCODED + "/videos?view=0"])
def test_chinese_handles_are_channels_and_have_one_identity(url):
    assert YouTubeService.is_channel_url(url)
    assert normalize_feed_url(url) == normalize_feed_url(URL)
    assert not YouTubeService.is_channel_url("https://example.com/youtube.com/@test")


def test_encoded_handle_is_decoded_for_the_channel_extractor(monkeypatch):
    extractor = Mock()
    extractor.__enter__ = Mock(return_value=extractor)
    extractor.__exit__ = Mock(return_value=False)
    extractor.extract_info.return_value = {"channel_id": "UCtest", "channel": HANDLE}
    monkeypatch.setattr("yt_dlp.YoutubeDL", lambda options: extractor)
    channel, error = YouTubeService.resolve_channel(ENCODED)
    assert error is None and channel["title"] == HANDLE
    extractor.extract_info.assert_called_once_with(URL, download=False, process=False)


def test_submission_returns_before_channel_resolution_and_deduplicates_pending_work(monkeypatch):
    app = make_auth_app((feeds_bp, "/api/feeds"))
    user = add_user(app.db, "subscriber@example.com")
    queue = RecordingQueue(fail_feed_id="not-this-task")
    monkeypatch.setattr("app.api.feeds.task_queue", queue)
    resolver = Mock(return_value=({"channel_id": "UCtest", "title": HANDLE}, None))
    monkeypatch.setattr(YouTubeService, "resolve_channel", resolver)
    headers = auth_headers(user)
    with app.test_client() as client:
        response = client.post("/api/feeds", json={"rss_url": ENCODED, "asynchronous": True}, headers=headers)
        assert response.status_code == 202
        task_id = response.json["data"]["task_id"]
        assert response.json["data"]["feed_title"] == f"@{HANDLE}"
        resolver.assert_not_called()
        again = client.post("/api/feeds", json={"rss_url": URL, "asynchronous": True}, headers=headers)
        assert again.json["data"]["task_id"] == task_id
    with app.app_context():
        result = queue.run(task_id)
    assert result["type"] == "youtube" and result["title"] == HANDLE
    assert queue.tasks[task_id]["status"] == "completed"
    assert len(queue.tasks) == 2  # Creation finishes; listing refresh is a separate task.


def test_resolution_failure_stays_in_the_task_and_does_not_create_a_feed(monkeypatch):
    app = make_auth_app((feeds_bp, "/api/feeds"))
    user = add_user(app.db, "subscriber@example.com")
    queue = RecordingQueue(fail_feed_id="not-this-task")
    monkeypatch.setattr("app.api.feeds.task_queue", queue)
    monkeypatch.setattr(YouTubeService, "resolve_channel", Mock(return_value=(None, "Temporarily unavailable")))
    response = app.test_client().post("/api/feeds", json={"rss_url": ENCODED, "asynchronous": True}, headers=auth_headers(user))
    with app.app_context():
        queue.run(response.json["data"]["task_id"])
    assert next(iter(queue.tasks.values()))["status"] == "failed"
    assert app.db.feeds.count_documents({}) == 0


def test_completed_subscription_has_a_feed_destination_and_is_private():
    app = make_auth_app((tasks_bp, "/api/tasks"))
    user = add_user(app.db, "subscriber@example.com")
    other = add_user(app.db, "other@example.com")
    feed_id = app.db.feeds.insert_one({"title": HANDLE}).inserted_id
    app.db.tasks.insert_one({"task_id": "subscription", "task_type": "subscribe", "owner_id": str(user["_id"]),
                             "status": "completed", "result": {"id": str(feed_id)},
                             "report_context": {"feed_title": f"@{HANDLE}"}})
    client = app.test_client()
    response = client.get("/api/tasks", headers=auth_headers(user))
    task = response.json["data"][0]
    assert (task["target_type"], task["target_id"], task["feed_title"]) == ("feed", str(feed_id), HANDLE)
    assert client.get("/api/tasks", headers=auth_headers(other)).json["data"] == []
