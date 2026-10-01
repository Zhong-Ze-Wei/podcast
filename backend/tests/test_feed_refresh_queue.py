"""Scheduled and manual feed refreshes share a single task operation."""
from datetime import datetime
from threading import Event
from bson import ObjectId
from flask import Flask
import pytest
from app.api import feeds
from app.services.auto_refresher import FeedAutoRefresher
from app.services.task_queue import TaskQueue
from tests.conftest import MockDB


class RecordingQueue:
    def __init__(self, fail_feed_id=None):
        self.tasks = {}
        self.fail_feed_id = fail_feed_id

    def submit_unique(self, task_type, func, *, dedup_key, **kwargs):
        if kwargs.get("feed_id") == self.fail_feed_id:
            raise RuntimeError("queue unavailable")
        for task in self.tasks.values():
            if task["dedup_key"] == dedup_key and task["status"] in {"pending", "processing"}:
                return task["task_id"]
        task_id = f"refresh-{len(self.tasks) + 1}"
        self.tasks[task_id] = {"task_id": task_id, "task_type": task_type, "dedup_key": dedup_key, "status": "pending", "func": func, **kwargs}
        return task_id

    def run(self, task_id):
        task = self.tasks[task_id]
        task["status"] = "processing"
        try:
            task["result"] = task["func"](progress_callback=lambda progress: None)
            task["status"] = "completed"
        except Exception as error:
            task["status"] = "failed"
            if task.get("on_failure"):
                task["on_failure"](error)
        return task.get("result")


class ImmediateQueue(RecordingQueue):
    def submit_unique(self, *args, **kwargs):
        task_id = super().submit_unique(*args, **kwargs)
        self.run(task_id)
        return task_id


def add_feed(db, status="active"):
    feed = {"_id": ObjectId(), "owner_id": "shared-user", "title": "Feed", "rss_url": "https://example.com/feed.xml", "status": status, "last_checked": datetime(2020, 1, 1)}
    db.feeds._data.append(feed)
    return feed


def test_scheduling_does_not_change_last_checked_and_paused_is_skipped(monkeypatch):
    db = MockDB()
    active = add_feed(db)
    add_feed(db, status="paused")
    queue = RecordingQueue()
    monkeypatch.setattr("app.services.rss_service.RSSService.parse_feed", lambda url: ({"episodes": []}, None))
    FeedAutoRefresher(db, queue=queue)._check_and_refresh_feeds()
    assert len(queue.tasks) == 1
    assert db.feeds.find_one({"_id": active["_id"]})["last_checked"] == datetime(2020, 1, 1)
    queue.run(next(iter(queue.tasks)))
    assert db.feeds.find_one({"_id": active["_id"]})["last_checked"] > datetime(2020, 1, 1)


def test_scheduler_submission_failure_does_not_stop_other_sources():
    db = MockDB()
    failed = add_feed(db)
    other = add_feed(db)
    queue = RecordingQueue(fail_feed_id=str(failed["_id"]))
    FeedAutoRefresher(db, queue=queue)._check_and_refresh_feeds()
    assert len(queue.tasks) == 1
    assert next(iter(queue.tasks.values()))["feed_id"] == str(other["_id"])
    assert db.feeds.find_one({"_id": failed["_id"]})["last_checked"] == datetime(2020, 1, 1)


def test_sync_failure_is_recorded_only_when_worker_runs(monkeypatch):
    db = MockDB()
    feed = add_feed(db)
    queue = RecordingQueue()
    monkeypatch.setattr("app.services.rss_service.RSSService.parse_feed", lambda url: (None, "upstream unavailable"))
    FeedAutoRefresher(db, queue=queue)._check_and_refresh_feeds()
    assert db.feeds.find_one({"_id": feed["_id"]})["status"] == "active"
    queue.run(next(iter(queue.tasks)))
    result = db.feeds.find_one({"_id": feed["_id"]})
    assert result["status"] == "error"
    assert result["check_error"] == "upstream unavailable"
    assert result["last_checked"] > datetime(2020, 1, 1)


def test_manual_and_scheduled_refresh_reuse_one_real_running_task(monkeypatch):
    db = MockDB()
    feed = add_feed(db)
    started, release = Event(), Event()
    def parse_feed(url):
        started.set()
        assert release.wait(5)
        return {"episodes": []}, None
    monkeypatch.setattr("app.services.rss_service.RSSService.parse_feed", parse_feed)
    queue = TaskQueue(max_workers=1)
    app = Flask(__name__)
    app.db = db
    app.register_blueprint(feeds.feeds_bp, url_prefix="/api/feeds")
    queue.set_app(app)
    queue.set_db(db)
    monkeypatch.setattr(feeds, "task_queue", queue)
    scheduler = FeedAutoRefresher(db, queue=queue)
    try:
        scheduler._check_and_refresh_feeds()
        assert started.wait(5)
        task_id = next(iter(queue.tasks))
        future = queue._futures[task_id]
        response = app.test_client().post(f"/api/feeds/{feed['_id']}/refresh")
        assert response.status_code == 200
        assert response.get_json()["data"]["task_id"] == task_id
        scheduler._check_and_refresh_feeds()
        assert len(queue.tasks) == 1
        assert db.feeds.find_one({"_id": feed["_id"]})["last_checked"] == datetime(2020, 1, 1)
        release.set()
        assert future.result(timeout=5)["new_episodes"] == 0
    finally:
        release.set()
        queue.shutdown(wait=True)
    assert queue.get_status(task_id)["status"] == "completed"
