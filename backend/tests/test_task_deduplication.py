from concurrent.futures import ThreadPoolExecutor
from threading import Event
import pytest

from app.services.task_queue import TaskQueue
from tests.conftest import MockDB


def test_concurrent_duplicate_requests_share_one_queued_worker():
    queue = TaskQueue(max_workers=1)
    db = MockDB()
    queue.set_db(db)
    started, release = Event(), Event()
    calls = []

    def blocker(progress_callback=None):
        started.set()
        assert release.wait(10)

    def refresh(progress_callback=None):
        calls.append("refresh")

    try:
        queue.submit("blocker", blocker)
        assert started.wait(5)
        with ThreadPoolExecutor(max_workers=4) as clients:
            ids = list(clients.map(lambda _: queue.submit_unique(
                "refresh", refresh, dedup_key="refresh:feed-1", feed_id="feed-1",
            ), range(8)))
        assert len(set(ids)) == 1
        assert db.tasks.count_documents({"task_type": "refresh"}) == 1
    finally:
        release.set()
        queue.shutdown()
    assert calls == ["refresh"]


def test_finished_operation_can_be_submitted_again_without_forwarding_task_metadata():
    queue = TaskQueue(max_workers=1)
    started, release = Event(), Event()

    def transcribe(language, progress_callback=None):
        started.set()
        assert release.wait(5)
        return language

    try:
        first = queue.submit_unique("transcribe", transcribe, dedup_key="transcribe:episode:en",
                                    episode_id="episode", language="en")
        assert started.wait(5)
        future = queue._futures[first]
        release.set()
        assert future.result(timeout=5) == "en"
        second = queue.submit_unique("transcribe", transcribe, dedup_key="transcribe:episode:en",
                                     episode_id="episode", language="en")
        assert second != first
    finally:
        release.set()
        queue.shutdown()
    assert queue.get_status(second)["status"] == "completed"


def test_distinct_parameters_and_cancelled_operations_have_separate_tasks():
    queue = TaskQueue(max_workers=1)
    started, release = Event(), Event()

    def blocker(progress_callback=None):
        started.set()
        assert release.wait(5)

    try:
        queue.submit("blocker", blocker)
        assert started.wait(5)
        first = queue.submit_unique("transcribe", lambda progress_callback=None: None,
                                    dedup_key="transcribe:episode:en")
        other = queue.submit_unique("transcribe", lambda progress_callback=None: None,
                                    dedup_key="transcribe:episode:zh")
        assert first != other
        assert queue.cancel(first)
        retry = queue.submit_unique("transcribe", lambda progress_callback=None: None,
                                    dedup_key="transcribe:episode:en")
        assert retry not in {first, other}
    finally:
        release.set()
        queue.shutdown()


def test_failed_task_persistence_does_not_reserve_a_deduplication_key(monkeypatch):
    db = MockDB()
    queue = TaskQueue(max_workers=1)
    queue.set_db(db)
    original_insert = db.tasks.insert_one

    def unavailable(doc):
        raise RuntimeError("database unavailable")

    monkeypatch.setattr(db.tasks, "insert_one", unavailable)
    try:
        with pytest.raises(RuntimeError, match="database unavailable"):
            queue.submit_unique("refresh", lambda progress_callback=None: "ok", dedup_key="refresh:feed")
        assert queue.tasks == {}
        monkeypatch.setattr(db.tasks, "insert_one", original_insert)
        retry = queue.submit_unique("refresh", lambda progress_callback=None: "ok", dedup_key="refresh:feed")
    finally:
        queue.shutdown()
    assert queue.get_status(retry)["status"] == "completed"
