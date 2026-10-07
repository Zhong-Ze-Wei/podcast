"""视频列表先可见，文稿在独立队列逐期补齐。"""
from datetime import datetime, timedelta
from threading import Event
from unittest.mock import Mock

import pytest
import requests
from bson import ObjectId

from app.models.feed import Feed
from app.services.auto_refresher import FeedAutoRefresher
from app.services.feed_sync_service import FeedSyncService
from app.services.task_queue import TaskQueue
from app.services.youtube_service import YouTubeService
from tests.conftest import MockDB
from tests.test_feed_refresh_queue import RecordingQueue


@pytest.fixture
def channel(monkeypatch):
    db = MockDB()
    feed = Feed.create("https://youtube.com/@test", title="Channel", type="youtube", channel_ref="UCtest")
    feed["_id"] = ObjectId()
    db.feeds.insert_one(feed)
    videos = [{"video_id": str(i), "title": f"Video {i}", "published": datetime(2026, 10, i + 1),
               "thumbnail": f"https://example.test/{i}.jpg"} for i in range(3)]
    monkeypatch.setattr(YouTubeService, "fetch_channel_videos", lambda cid: (list(videos), None))
    monkeypatch.setattr(YouTubeService, "fetch_metadata", lambda vid: ({"duration": 120}, None))
    monkeypatch.setattr(YouTubeService, "fetch_transcript", lambda vid: (
        {"text": f"Transcript {vid}", "segments": [], "language": "en"}, None))
    monkeypatch.setattr("app.services.feed_sync_service._persist_feed_icon", lambda *a, **k: None)
    monkeypatch.setattr("time.sleep", lambda seconds: None)
    return db, feed, videos


def test_discovery_never_waits_for_metadata_or_transcripts(channel, monkeypatch):
    db, feed, _ = channel
    calls = Mock(side_effect=AssertionError("Discovery must not fetch individual videos"))
    monkeypatch.setattr(YouTubeService, "fetch_metadata", calls)
    monkeypatch.setattr(YouTubeService, "fetch_transcript", calls)
    queue = RecordingQueue()
    result = FeedSyncService(db, queue).refresh(str(feed["_id"]))
    assert result["new_episodes"] == 3
    assert db.feeds.find_one({"_id": feed["_id"]})["episode_count"] == 3
    assert db.transcripts.count_documents({}) == 0
    assert db.episodes.find_one({"guid": "youtube:0"})["image"] == "https://example.test/0.jpg"
    assert queue.tasks[result["transcript_task_id"]]["task_type"] == "fetch_transcripts"
    assert not calls.called


def test_repeated_discovery_reuses_caption_task_and_saved_transcripts(channel):
    db, feed, _ = channel
    queue = RecordingQueue()
    service = FeedSyncService(db, queue)
    first = service.refresh(str(feed["_id"]))
    second = service.refresh(str(feed["_id"]))
    assert second["new_episodes"] == 0
    assert second["transcript_task_id"] == first["transcript_task_id"]
    assert queue.run(first["transcript_task_id"])["new_transcripts"] == 3
    assert service.refresh(str(feed["_id"]))["transcript_task_id"] is None
    assert len(queue.tasks) == 1


def test_metadata_failure_does_not_prevent_captions_and_caption_failure_keeps_video(channel, monkeypatch):
    db, feed, _ = channel
    monkeypatch.setattr(YouTubeService, "fetch_metadata", lambda vid: (None, "metadata unavailable"))
    monkeypatch.setattr(YouTubeService, "fetch_transcript", lambda vid: (
        (None, "Subtitles disabled") if vid == "1" else ({"text": vid, "segments": []}, None)))
    queue = RecordingQueue()
    result = FeedSyncService(db, queue).refresh(str(feed["_id"]))
    assert queue.run(result["transcript_task_id"]) == {"new_transcripts": 2, "transcript_failures": 1}
    assert db.episodes.count_documents({}) == 3
    assert db.feeds.find_one({"_id": feed["_id"]})["status"] == "active"
    assert "禁用" in db.episodes.find_one({"guid": "youtube:1"})["transcript_fetch_error"]


def test_caption_worker_does_not_block_discovery_and_picks_up_new_video(channel, monkeypatch):
    db, feed, videos = channel
    started, release, finished = Event(), Event(), Event()
    caption_calls = []
    def captions(vid):
        caption_calls.append(vid)
        started.set()
        assert release.wait(5)
        if vid == "new":
            finished.set()
        return {"text": vid, "segments": []}, None
    monkeypatch.setattr(YouTubeService, "fetch_transcript", captions)
    queue = TaskQueue(max_workers=1)
    queue.set_db(db)
    service = FeedSyncService(db, queue)
    try:
        first = service.refresh(str(feed["_id"]))
        assert started.wait(5)
        videos.append({"video_id": "new", "title": "Newest", "published": datetime(2026, 10, 7)})
        discovered = Event()
        def refresh(progress_callback=None):
            result = service.refresh(str(feed["_id"]))
            assert result["transcript_task_id"] == first["transcript_task_id"]
            discovered.set()
            return result
        queue.submit("refresh", refresh, feed_id=str(feed["_id"]))
        assert discovered.wait(5), "Slow captions must not occupy the discovery executor"
        assert db.episodes.count_documents({}) == 4
        assert db.transcripts.count_documents({}) == 0
        release.set()
        assert finished.wait(5)
    finally:
        release.set()
        queue.shutdown()
    assert set(caption_calls) == {"0", "1", "2", "new"}
    assert db.transcripts.count_documents({}) == 4


def test_auto_refresh_pauses_bilibili_and_checks_youtube_every_15_minutes(monkeypatch):
    db = MockDB()
    now = datetime.utcnow()
    expected = []
    for kind, age in [("bilibili", 1000), ("youtube", 16), ("youtube", 14), ("rss", 16), ("rss", 361)]:
        feed = Feed.create("https://example.test/feed", type=kind)
        feed.update(_id=ObjectId(), last_checked=now - timedelta(minutes=age))
        db.feeds.insert_one(feed)
        if (kind, age) in [("youtube", 16), ("rss", 361)]:
            expected.append(feed["_id"])
    never_checked = Feed.create("https://example.test/bili", type="bilibili")
    db.feeds.insert_one(never_checked)
    selected = []
    refresher = FeedAutoRefresher(db, queue=RecordingQueue())
    monkeypatch.setattr(refresher, "_refresh_single_feed", lambda feed: selected.append(feed["_id"]))
    refresher._check_and_refresh_feeds()
    assert set(selected) == set(expected)


@pytest.mark.parametrize("failure", ["404", "html"])
def test_invalid_rss_uses_flat_uploads_list(monkeypatch, failure):
    response = Mock(content=b"<html>Not Found</html>")
    if failure == "404":
        response.raise_for_status.side_effect = requests.HTTPError("404")
    monkeypatch.setattr("requests.get", lambda *a, **k: response)
    fallback = Mock(return_value=([{"video_id": "existing", "title": "Video"}], None))
    monkeypatch.setattr(YouTubeService, "_fetch_channel_uploads", fallback)
    videos, error = YouTubeService.fetch_channel_videos("UCtest")
    assert videos[0]["video_id"] == "existing"
    assert error is None
    fallback.assert_called_once_with("UCtest")


def test_failed_fallback_is_not_reported_as_an_empty_success(monkeypatch):
    response = Mock()
    response.raise_for_status.side_effect = requests.HTTPError("404")
    monkeypatch.setattr("requests.get", lambda *a, **k: response)
    monkeypatch.setattr(YouTubeService, "_fetch_channel_uploads", lambda cid: (None, "channel unavailable"))
    assert YouTubeService.fetch_channel_videos("UCtest") == (None, "channel unavailable")


def test_flat_fallback_does_not_fetch_individual_videos(monkeypatch):
    captured = {}
    class FlatYoutubeDL:
        def __init__(self, opts):
            captured.update(opts)
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def extract_info(self, url, download=False):
            captured["url"] = url
            return {"entries": [{"id": "video", "title": "Newest", "timestamp": 1790000000,
                                  "duration": 180, "thumbnails": [{"url": "https://image.test"}]}]}
    monkeypatch.setattr("yt_dlp.YoutubeDL", FlatYoutubeDL)
    videos, error = YouTubeService._fetch_channel_uploads("UCtest")
    assert captured["extract_flat"] is True
    assert captured["playlistend"] == 15
    assert captured["url"].endswith("list=UUtest")
    assert videos[0]["duration"] == 180
    assert error is None
