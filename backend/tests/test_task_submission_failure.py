from app.services.task_queue import TaskQueue
from tests.conftest import MockDB
import pytest


def test_rejected_executor_submission_releases_identity_and_records_failure(monkeypatch):
    db = MockDB()
    queue = TaskQueue(max_workers=1)
    queue.set_db(db)
    submit = queue.executor.submit

    def reject(*args, **kwargs):
        raise RuntimeError("executor rejected task")

    try:
        monkeypatch.setattr(queue.executor, "submit", reject)
        with pytest.raises(RuntimeError, match="executor rejected task"):
            queue.submit_unique("download", lambda progress_callback=None: "ok", dedup_key="download:ep")
        assert queue.tasks == {}
        assert queue._futures == {}
        stored = db.tasks.find_one({"dedup_key": "download:ep"})
        assert stored["status"] == "failed"
        assert stored["completed_at"] is not None
        assert stored["error_message"] == "executor rejected task"

        monkeypatch.setattr(queue.executor, "submit", submit)
        retry_id = queue.submit_unique("download", lambda progress_callback=None: "ok", dedup_key="download:ep")
        queue.shutdown()
        assert retry_id != stored["task_id"]
        assert queue.get_status(retry_id)["status"] == "completed"
    finally:
        queue.shutdown()
