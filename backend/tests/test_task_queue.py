# -*- coding: utf-8 -*-
from flask import Flask, current_app
from bson import ObjectId

from app.services.task_queue import TaskQueue
from app.models.episode import Episode
from tests.conftest import MockDB


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
