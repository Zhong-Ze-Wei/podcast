"""视频列表先可见，文稿进全局节流队列逐期补齐。"""
from datetime import datetime, timedelta
from threading import Event
from unittest.mock import Mock

import pytest
import requests
from bson import ObjectId

from app.models.feed import Feed
from app.models.episode import Episode
from app.services import transcript_queue_service
from app.services.auto_refresher import FeedAutoRefresher
from app.services.feed_sync_service import FeedSyncService
from app.services.task_queue import TaskQueue
from app.services.youtube_service import YouTubeService
from tests.conftest import MockDB
from tests.test_feed_refresh_queue import RecordingQueue


@pytest.fixture(autouse=True)
def transcript_queue():
    """每个用例用独立队列，避免串味。"""
    queue = transcript_queue_service.TranscriptQueue()
    transcript_queue_service._queue_instance = queue
    yield queue
    transcript_queue_service._queue_instance = None


@pytest.fixture
def channel(monkeypatch, transcript_queue):
    db = MockDB()
    transcript_queue.db = db
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


def drain(queue):
    """把队列里的剧集逐期处理完（等价于后台线程跑完积压）。"""
    while queue.fetch_next() is not None:
        pass


def test_discovery_never_waits_for_metadata_or_transcripts(channel, monkeypatch, transcript_queue):
    db, feed, _ = channel
    calls = Mock(side_effect=AssertionError("Discovery must not fetch individual videos"))
    monkeypatch.setattr(YouTubeService, "fetch_metadata", calls)
    monkeypatch.setattr(YouTubeService, "fetch_transcript", calls)
    result = FeedSyncService(db, RecordingQueue()).refresh(str(feed["_id"]))
    assert result["new_episodes"] == 3
    assert result["transcript_queue_depth"] == 3
    assert db.feeds.find_one({"_id": feed["_id"]})["episode_count"] == 3
    assert db.transcripts.count_documents({}) == 0
    assert db.episodes.find_one({"guid": "youtube:0"})["image"] == "https://example.test/0.jpg"
    assert [item["title"] for item in transcript_queue.snapshot()["pending"]] == [
        "Video 0", "Video 1", "Video 2"]
    assert not calls.called


def test_repeated_discovery_does_not_duplicate_queue_entries(channel, transcript_queue):
    db, feed, _ = channel
    service = FeedSyncService(db, RecordingQueue())
    first = service.refresh(str(feed["_id"]))
    second = service.refresh(str(feed["_id"]))
    assert second["new_episodes"] == 0
    assert second["transcript_queue_depth"] == first["transcript_queue_depth"] == 3
    drain(transcript_queue)
    assert db.transcripts.count_documents({}) == 3


def test_metadata_failure_does_not_prevent_captions_and_caption_failure_keeps_video(channel, monkeypatch, transcript_queue):
    db, feed, _ = channel
    monkeypatch.setattr(YouTubeService, "fetch_metadata", lambda vid: (None, "metadata unavailable"))
    monkeypatch.setattr(YouTubeService, "fetch_transcript", lambda vid: (
        (None, "Subtitles disabled") if vid == "1" else ({"text": vid, "segments": []}, None)))
    FeedSyncService(db, RecordingQueue()).refresh(str(feed["_id"]))
    drain(transcript_queue)
    assert db.episodes.count_documents({}) == 3
    assert db.feeds.find_one({"_id": feed["_id"]})["status"] == "active"
    assert db.transcripts.count_documents({}) == 2
    assert "禁用" in db.episodes.find_one({"guid": "youtube:1"})["transcript_fetch_error"]


def test_refresh_retries_failed_captions_and_clears_error_without_refetching_saved_text(channel, monkeypatch, transcript_queue):
    db, feed, _ = channel
    captions = Mock(side_effect=lambda vid: (None, "Subtitles disabled") if vid == "1" else (
        {"text": f"Transcript {vid}", "segments": []}, None))
    monkeypatch.setattr(YouTubeService, "fetch_transcript", captions)
    service = FeedSyncService(db, RecordingQueue())
    service.refresh(str(feed["_id"]))
    drain(transcript_queue)
    episode = db.episodes.find_one({"guid": "youtube:1"})
    assert "禁用" in episode["transcript_fetch_error"]

    captions.reset_mock()
    captions.side_effect = lambda vid: ({"text": "Recovered transcript", "segments": []}, None)
    retry = service.refresh(str(feed["_id"]))
    # 缺字幕的剧集再次进队；已有文稿的两期不再排队
    assert retry["transcript_queue_depth"] == 1
    drain(transcript_queue)
    captions.assert_called_once_with("1")
    assert "transcript_fetch_error" not in db.episodes.find_one({"_id": episode["_id"]})
    assert db.transcripts.find_one({"episode_id": episode["_id"]})["text"] == "Recovered transcript"


def test_refresh_recovers_from_channel_fetch_failure(channel, monkeypatch):
    db, feed, videos = channel
    listing = Mock(side_effect=[(None, "upstream unavailable"), (videos, None)])
    monkeypatch.setattr(YouTubeService, "fetch_channel_videos", listing)
    service = FeedSyncService(db, RecordingQueue())
    with pytest.raises(ValueError, match="upstream unavailable"):
        service.refresh(str(feed["_id"]))
    assert db.feeds.find_one({"_id": feed["_id"]})["check_error"]
    assert service.refresh(str(feed["_id"]))["new_episodes"] == 3
    assert db.feeds.find_one({"_id": feed["_id"]})["check_error"] is None


def test_slow_caption_worker_does_not_block_discovery(channel, monkeypatch, transcript_queue):
    db, feed, videos = channel
    started, release, finished = Event(), Event(), Event()

    def captions(vid):
        started.set()
        assert release.wait(5)
        if vid == "new":
            finished.set()
        return {"text": vid, "segments": []}, None

    monkeypatch.setattr(YouTubeService, "fetch_transcript", captions)
    service = FeedSyncService(db, RecordingQueue())
    service.refresh(str(feed["_id"]))
    worker = Event()

    def run_worker():
        transcript_queue.fetch_next()
        worker.set()

    import threading
    threading.Thread(target=run_worker, daemon=True).start()
    assert started.wait(5)
    # 抓字幕期间仍可刷新列表，并发现新视频
    videos.append({"video_id": "new", "title": "Newest", "published": datetime(2026, 10, 7)})
    result = service.refresh(str(feed["_id"]))
    assert result["new_episodes"] == 1
    assert db.episodes.count_documents({}) == 4
    assert db.episodes.find_one({"guid": "youtube:new"})["title"] == "Newest"
    release.set()
    assert finished.wait(5) or worker.wait(1)


def test_auto_refresh_shares_one_interval_and_limits_feeds_per_round(monkeypatch):
    db = MockDB()
    now = datetime.utcnow()
    due, not_due = [], []
    for kind, age_hours in [("youtube", 13), ("rss", 13), ("youtube", 1), ("rss", 1), ("bilibili", 100)]:
        feed = Feed.create("https://example.test/feed", type=kind)
        feed.update(_id=ObjectId(), status="active", last_checked=now - timedelta(hours=age_hours))
        db.feeds.insert_one(feed)
        (due if age_hours > 12 and kind != "bilibili" else not_due).append(feed["_id"])
    never_checked = Feed.create("https://example.test/never", type="rss")
    never_checked.update(_id=ObjectId(), status="active", last_checked=None)
    db.feeds.insert_one(never_checked)

    refresher = FeedAutoRefresher(db, queue=RecordingQueue())
    selected = []
    monkeypatch.setattr(refresher, "_refresh_single_feed", lambda feed: selected.append(feed["_id"]))

    settings = refresher._settings()
    refresher._check_and_refresh_feeds(settings)

    # 每轮只提交 feeds_per_tick 个源：不会在同一时刻一起打所有源
    assert len(selected) == settings["feeds_per_tick"] == 1
    due_ids = set(due) | {never_checked["_id"]}
    refresher._check_and_refresh_feeds(settings)
    assert len(selected) == 2
    assert set(selected) <= due_ids
    assert not (set(selected) & set(not_due))
    # B站不参与自动更新
    for feed_id in selected:
        assert db.feeds.find_one({"_id": feed_id})["type"] != "bilibili"


def test_auto_refresh_records_daily_completion(monkeypatch):
    db = MockDB()
    refresher = FeedAutoRefresher(db, queue=RecordingQueue())
    monkeypatch.setattr(refresher, "_refresh_single_feed", lambda feed: refresher._record(feed, True))
    feed = Feed.create("https://example.test/feed", title="A", type="rss")
    feed.update(_id=ObjectId(), status="active", last_checked=None)
    db.feeds.insert_one(feed)

    refresher._check_and_refresh_feeds(refresher._settings())

    assert refresher.daily_summary()["done"] == 1
    assert refresher.daily_summary()["feeds"] == 1


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
                                  "duration": 180, "thumbnails": [{"url": "https://image.test"}]},
                                 {"id": "unknown", "title": "No publish date"}]}
    monkeypatch.setattr("yt_dlp.YoutubeDL", FlatYoutubeDL)
    videos, error = YouTubeService._fetch_channel_uploads("UCtest")
    assert captured["extract_flat"] is True
    assert captured["playlistend"] == 15
    assert captured["url"].endswith("list=UUtest")
    assert videos[0]["duration"] == 180
    assert videos[1]["published"] is None
    assert "extractor_args" not in captured
    assert error is None


def test_refresh_corrects_existing_metadata_without_losing_saved_work(channel):
    db, feed, videos = channel
    episode = Episode.create(feed["_id"], "youtube:0", "Old title", published=datetime(2026, 10, 7),
                             duration=3473, image="/api/media/covers/yt_0.jpg")
    episode.update(status=Episode.STATUS_SUMMARIZED, is_read=True, is_favorite=True, play_position=90)
    db.episodes.insert_one(episode)
    db.transcripts.insert_one({"episode_id": episode["_id"], "text": "Saved transcript"})
    db.summaries.insert_one({"episode_id": episode["_id"], "content": "Saved AI analysis"})
    FeedSyncService(db, RecordingQueue()).refresh(str(feed["_id"]))
    stored = db.episodes.find_one({"_id": episode["_id"]})
    assert stored["title"] == videos[0]["title"]
    assert stored["published"] == videos[0]["published"]
    assert stored["duration"] == 3473  # RSS 没有时长，不能把已有值清零。
    assert stored["image"] == "/api/media/covers/yt_0.jpg"
    assert stored["status"] == Episode.STATUS_SUMMARIZED
    assert stored["is_read"] and stored["is_favorite"] and stored["play_position"] == 90
    assert db.transcripts.find_one({"episode_id": episode["_id"]})["text"] == "Saved transcript"
    assert db.summaries.find_one({"episode_id": episode["_id"]})["content"] == "Saved AI analysis"


def test_saved_transcript_still_gets_duration_date_and_description_once(channel, monkeypatch, transcript_queue):
    db, feed, videos = channel
    videos[:] = videos[:1]
    episode = Episode.create(feed["_id"], "youtube:0", "Video", published=datetime(2026, 10, 7), duration=0)
    episode["youtube_metadata_fetched_at"] = datetime(2026, 10, 7)  # 兼容旧版本已获取但不全的数据。
    db.episodes.insert_one(episode)
    db.transcripts.insert_one({"episode_id": episode["_id"], "text": "Existing captions"})
    metadata = Mock(return_value=({"duration": 3473, "published": datetime(2026, 1, 22),
                                  "description": "Official episode description", "title": "Current title"}, None))
    captions = Mock(side_effect=AssertionError("Saved captions must be reused"))
    monkeypatch.setattr(YouTubeService, "fetch_metadata", metadata)
    monkeypatch.setattr(YouTubeService, "fetch_transcript", captions)
    FeedSyncService(db, RecordingQueue()).refresh(str(feed["_id"]))
    drain(transcript_queue)
    stored = db.episodes.find_one({"_id": episode["_id"]})
    assert stored["duration"] == 3473
    assert stored["published"] == datetime(2026, 1, 22)
    assert stored["summary"] == "Official episode description"
    assert Episode.to_response(stored)["duration_formatted"] == "57:53"
    metadata.assert_called_once_with("0")
    assert not captions.called


def test_undated_discovered_video_is_not_excluded_by_older_dated_videos(channel, transcript_queue):
    db, feed, videos = channel
    videos[:] = [{"video_id": "new", "title": "New upload", "published": None}]
    for i in range(15):
        db.episodes.insert_one(Episode.create(feed["_id"], f"youtube:old-{i}", "Old video",
                                             published=datetime(2025, 1, i + 1)))
    FeedSyncService(db, RecordingQueue()).refresh(str(feed["_id"]))
    discovered = db.episodes.find_one({"guid": "youtube:new"})
    assert discovered["published"] is None
    assert Episode.to_response(discovered)["duration_formatted"] is None
    drain(transcript_queue)
    assert db.transcripts.find_one({"episode_id": discovered["_id"]})


@pytest.mark.parametrize("dates, expected", [
    ({"timestamp": 1769082481, "upload_date": "20260101"}, datetime(2026, 1, 22, 11, 48, 1)),
    ({"upload_date": "20260122"}, datetime(2026, 1, 22)),
])
def test_metadata_keeps_authoritative_publication_and_full_description(monkeypatch, dates, expected):
    class MetadataYoutubeDL:
        def __init__(self, opts):
            pass
        def __enter__(self):
            return self
        def __exit__(self, *args):
            pass
        def extract_info(self, url, download=False):
            return {"title": "Video", "duration": 3473, "description": "Full episode description", **dates}
    monkeypatch.setattr("yt_dlp.YoutubeDL", MetadataYoutubeDL)
    metadata, error = YouTubeService.fetch_metadata("video")
    assert error is None
    assert metadata["published"] == expected
    assert metadata["description"] == "Full episode description"
