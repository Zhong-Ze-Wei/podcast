# -*- coding: utf-8 -*-
from flask import Flask, current_app
from bson import ObjectId

from app.services.task_queue import TaskQueue
from app.models.episode import Episode
from tests.conftest import MockDB
from threading import Event


def test_task_queue_runs_tasks_inside_flask_app_context():
    app = Flask(__name__)
    app.config["SENTINEL"] = "available"
    queue = TaskQueue(max_workers=1)
    queue.set_app(app)

    def read_current_app(progress_callback=None):
        return current_app.config["SENTINEL"]

    task_id = queue.submit("probe", read_current_app)
    queue.shutdown(wait=True)

    task = queue.get_status(task_id)
    assert task["status"] == "completed"
    assert task["result"] == "available"


def test_cancelling_queued_task_prevents_execution_and_persists_cancelled():
    queue = TaskQueue(max_workers=1)
    db = MockDB()
    queue.set_db(db)
    started, release = Event(), Event()
    calls = []

    def blocker(progress_callback=None):
        started.set()
        assert release.wait(5)

    def queued(progress_callback=None):
        calls.append("executed")

    try:
        queue.submit("blocker", blocker)
        assert started.wait(5)
        task_id = queue.submit("probe", queued)
        assert queue.cancel(task_id)
        assert queue.cancel(task_id)  # Repeated cancellation is idempotent.
    finally:
        release.set()
        queue.shutdown()

    assert calls == []
    assert queue.get_status(task_id)["status"] == "cancelled"
    assert db.tasks.find_one({"task_id": task_id})["status"] == "cancelled"


def test_running_task_cannot_be_reported_as_cancelled():
    queue = TaskQueue(max_workers=1)
    started, release = Event(), Event()

    def running(progress_callback=None):
        started.set()
        assert release.wait(5)
        return "finished"

    try:
        task_id = queue.submit("probe", running)
        assert started.wait(5)
        assert queue.cancel(task_id) is False
        assert queue.get_status(task_id)["status"] == "processing"
    finally:
        release.set()
        queue.shutdown()
    assert queue.get_status(task_id)["status"] == "completed"


def test_terminal_task_ignores_late_progress_and_status_updates():
    queue = TaskQueue(max_workers=1)
    task_id = queue.submit("probe", lambda progress_callback=None: "done")
    queue.shutdown()
    completed = queue.get_status(task_id)
    queue._update_progress(task_id, (12, "late progress"))
    queue._update_status(task_id, "processing")
    assert queue.get_status(task_id) == completed


def test_cancelled_download_restores_episode_to_retryable_state():
    queue = TaskQueue(max_workers=1)
    db = MockDB()
    queue.set_db(db)
    episode_id = db.episodes.insert_one({"status": "downloading"}).inserted_id
    started, release = Event(), Event()

    def blocker(progress_callback=None):
        started.set()
        assert release.wait(5)

    try:
        queue.submit("blocker", blocker)
        assert started.wait(5)
        task_id = queue.submit("download", lambda progress_callback=None: None,
                               episode_id=str(episode_id))
        assert queue.cancel(task_id)
        assert db.episodes.find_one({"_id": episode_id})["status"] == "new"
    finally:
        release.set()
        queue.shutdown()


def test_task_queue_calls_failure_callback_when_task_fails():
    queue = TaskQueue(max_workers=1)
    failures = []

    def fail(progress_callback=None):
        raise RuntimeError("boom")

    def on_failure(error):
        failures.append(str(error))

    task_id = queue.submit("probe", fail, on_failure=on_failure)
    queue.shutdown(wait=True)

    task = queue.get_status(task_id)
    assert task["status"] == "failed"
    assert task["error_message"] == "boom"
    assert failures == ["boom"]


def test_task_queue_recovers_interrupted_processing_tasks():
    db = MockDB()
    queue = TaskQueue(max_workers=1)
    queue.set_db(db)

    db.episodes.insert_one({
        "status": Episode.STATUS_TRANSCRIBING,
        "has_transcript": False,
        "local_path": "audio/example.mp3",
    })
    episode_id = db.episodes.find_one({"status": Episode.STATUS_TRANSCRIBING})["_id"]
    db.tasks.insert_one({
        "task_id": "stale-transcribe",
        "task_type": "transcribe",
        "episode_id": str(episode_id),
        "status": "processing",
        "progress": 25,
        "error_message": None,
        "completed_at": None,
    })

    recovered = queue.recover_interrupted_tasks()

    task = db.tasks.find_one({"task_id": "stale-transcribe"})
    episode = db.episodes.find_one({"_id": episode_id})
    assert recovered == 1
    assert task["status"] == "failed"
    assert "Backend restarted" in task["error_message"]
    assert task["completed_at"] is not None
    assert episode["status"] == Episode.STATUS_DOWNLOADED
    assert "Backend restarted" in episode["last_transcript_error"]


def test_task_queue_materializes_generator_results_before_persisting():
    db = MockDB()
    queue = TaskQueue(max_workers=1)
    queue.set_db(db)

    def generate_result(progress_callback=None):
        return (item for item in [{"value": 1}])

    task_id = queue.submit("probe", generate_result)
    queue.shutdown(wait=True)

    task = queue.get_status(task_id)
    stored = db.tasks.find_one({"task_id": task_id})
    assert task["result"] == [{"value": 1}]
    assert stored["result"] == [{"value": 1}]


def test_briefing_period_is_persisted_without_being_forwarded_to_worker():
    db = MockDB()
    queue = TaskQueue(max_workers=1)
    queue.set_db(db)
    period = {"type": "month", "start": "2026-10-01", "total_count": 8}

    def generate(progress_callback=None):
        return "october"

    task_id = queue.submit("briefing-report", generate, report_period=period)
    queue.shutdown(wait=True)
    stored = db.tasks.find_one({"task_id": task_id})
    assert queue.get_status(task_id)["status"] == "completed"
    assert stored["report_period"] == {"type": "month", "start": "2026-10-01"}
    assert stored["result"] == "october"


def test_unlimited_memory_task_listing_keeps_active_tasks_beyond_default_page():
    queue = TaskQueue(max_workers=1)
    queue.tasks = {str(index): {"created_at": index, "status": "pending", "task_type": "briefing-report"} for index in range(60)}
    assert len(queue.get_all_tasks(status="pending", task_type="briefing-report")) == 50
    assert len(queue.get_all_tasks(status="pending", task_type="briefing-report", limit=0)) == 60
    queue.shutdown(wait=True)


def test_progress_callback_accepts_message_tuple():
    """progress_callback 支持传 (percent, message)，任务记录带 progress_message"""
    from app.services.task_queue import TaskQueue

    q = TaskQueue(max_workers=1)
    captured = {}

    def job(progress_callback=None):
        progress_callback((42, "拉取字幕 5/12"))
        return "ok"

    def cb(**kw):
        pass

    task_id = q.submit(task_type="refresh", func=job, **{})
    q.wait_all() if hasattr(q, "wait_all") else None
    # TaskQueue 测试环境的等待方式参照现有用例；这里直接等一小段时间
    import time
    for _ in range(30):
        info = q.tasks.get(task_id) or {}
        if info.get("status") in ("completed", "failed"):
            break
        time.sleep(0.1)
    info = q.tasks[task_id]
    assert info["status"] == "completed"
    assert info["progress_message"] == "拉取字幕 5/12"  # 完成态归 100，消息保留
