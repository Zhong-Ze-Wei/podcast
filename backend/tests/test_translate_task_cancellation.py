from threading import Event

from app.services.task_queue import TaskQueue
from tests.conftest import MockDB


def test_cancelled_queued_translation_restores_saved_summary():
    db = MockDB()
    queue = TaskQueue(max_workers=1)
    queue.set_db(db)
    episode_id = db.episodes.insert_one({"status": "summarizing", "has_summary": True, "has_transcript": True}).inserted_id
    started, release = Event(), Event()

    def blocker(progress_callback=None):
        started.set()
        assert release.wait(5)

    try:
        queue.submit("blocker", blocker)
        assert started.wait(5)
        task_id = queue.submit("translate", lambda progress_callback=None: None, episode_id=str(episode_id))
        assert queue.cancel(task_id)
        assert db.episodes.find_one({"_id": episode_id})["status"] == "summarized"
    finally:
        release.set()
        queue.shutdown()


def test_interrupted_translation_recovers_to_retryable_saved_summary():
    db = MockDB()
    queue = TaskQueue(max_workers=1)
    queue.set_db(db)
    episode_id = db.episodes.insert_one({"status": "summarizing", "has_summary": True, "has_transcript": True}).inserted_id
    db.tasks.insert_one({"task_id": "interrupted-translation", "task_type": "translate",
                         "episode_id": str(episode_id), "status": "processing"})
    try:
        assert queue.recover_interrupted_tasks() == 1
        assert db.tasks.find_one({"task_id": "interrupted-translation"})["status"] == "failed"
        episode = db.episodes.find_one({"_id": episode_id})
        assert episode["status"] == "summarized"
        assert "Backend restarted" in episode["last_summary_error"]
    finally:
        queue.shutdown()
