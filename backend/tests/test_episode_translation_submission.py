"""Translation writes use the same shared episode processing reservation."""
from concurrent.futures import ThreadPoolExecutor
from threading import Event
from bson import ObjectId
from flask import Flask
import pytest
from app.api.episodes import episodes_bp
from app.api.transcripts import transcripts_bp
from app.api.summaries import summaries_bp
from app.services.task_queue import TaskQueue
from tests.conftest import MockDB
from tests.test_episode_processing_submission import PendingQueue, race_requests


@pytest.fixture
def app(monkeypatch, tmp_path):
    app = Flask(__name__)
    app.config.update(MEDIA_ROOT=str(tmp_path), AI_ANALYSIS_ENABLED=True)
    app.db = MockDB()
    app.register_blueprint(episodes_bp, url_prefix="/api/episodes")
    app.register_blueprint(transcripts_bp, url_prefix="/api/transcripts")
    app.register_blueprint(summaries_bp, url_prefix="/api/summaries")
    monkeypatch.setattr("app.services.whisper_service.is_available", lambda: False)
    monkeypatch.setattr("app.services.whisperx_service.is_available", lambda: False)
    return app


def summarized_episode(app, translated=False):
    item = app.db.episodes.insert_one({"title": "Result", "status": "summarized", "has_transcript": True, "has_summary": True}).inserted_id
    app.db.transcripts.insert_one({"episode_id": item, "text": "Transcript"})
    summary = {"episode_id": item, "template_name": "learning", "content": {"tldr": "Summary"}}
    if translated:
        summary["content_zh"] = {"tldr": "译文"}
    app.db.summaries.insert_one(summary)
    return item


def test_active_translation_is_visible_and_blocks_result_mutations(app, monkeypatch):
    item = summarized_episode(app)
    queue = PendingQueue(app.db)
    monkeypatch.setattr("app.api.summaries.task_queue", queue)
    client = app.test_client()
    first = client.post(f"/api/summaries/{item}/translate", json={})
    assert first.status_code == 200
    data = client.get(f"/api/episodes/{item}").get_json()["data"]
    assert data["active_tasks"][0]["task_type"] == "translate"
    assert data["actions"]["summarize"] == {"allowed": False, "reason_code": "TASK_IN_PROGRESS"}
    for response in (client.delete(f"/api/summaries/{item}"), client.delete(f"/api/transcripts/{item}"), client.post(f"/api/summaries/{item}", json={"force": True})):
        assert response.status_code == 409 and response.get_json()["error_code"] == "TASK_IN_PROGRESS"
    assert app.db.summaries.count_documents({"episode_id": item}) == 1
    assert app.db.transcripts.count_documents({"episode_id": item}) == 1


def test_simultaneous_translation_requests_reuse_one_task(app, monkeypatch):
    item = summarized_episode(app)
    queue = PendingQueue(app.db)
    monkeypatch.setattr("app.api.summaries.task_queue", queue)
    path = f"/api/summaries/{item}/translate"
    responses = race_requests(app, monkeypatch, item, [(path, {}), (path, {})])
    assert [response.status_code for response in responses] == [200, 200]
    assert {response.get_json()["data"]["task_id"] for response in responses} == {"task-1"}
    assert len(queue.submitted) == 1


@pytest.mark.parametrize("fails", [False, True])
def test_fast_translation_restores_existing_summary_state(app, monkeypatch, fails):
    item = summarized_episode(app)
    class FastQueue(TaskQueue):
        def __init__(self):
            super().__init__(max_workers=1)
            self.finished = Event()
        def _update_status(self, task_id, status, **kwargs):
            result = super()._update_status(task_id, status, **kwargs)
            if status in {"completed", "failed"}:
                self.finished.set()
            return result
        def submit_unique(self, *args, **kwargs):
            task_id = super().submit_unique(*args, **kwargs)
            assert self.finished.wait(5)
            return task_id
    queue = FastQueue()
    queue.set_db(app.db)
    queue.set_app(app)
    monkeypatch.setattr("app.api.summaries.task_queue", queue)
    def translate(*args, **kwargs):
        assert app.db.episodes.find_one({"_id": item})["status"] == "summarizing"
        if fails:
            raise RuntimeError("translation failed")
        app.db.summaries.update_one({"episode_id": item}, {"$set": {"content_zh": {"tldr": "译文"}}})
        return {}
    monkeypatch.setattr("app.api.summaries._translate_sync", translate)
    try:
        response = app.test_client().post(f"/api/summaries/{item}/translate", json={})
        assert response.status_code == 200
        assert queue.finished.wait(5)
        task = queue.get_status(response.get_json()["data"]["task_id"])
        assert task["status"] == ("failed" if fails else "completed")
        episode = app.db.episodes.find_one({"_id": item})
        assert episode["status"] == "summarized" and episode["has_summary"] is True
        assert app.db.summaries.find_one({"episode_id": item})["content"]["tldr"] == "Summary"
    finally:
        queue.shutdown(wait=True)


def test_already_translated_result_is_returned_without_new_processing(app, monkeypatch):
    item = summarized_episode(app, translated=True)
    monkeypatch.setattr("app.api.summaries.task_queue.submit_unique", lambda *a, **kw: pytest.fail("existing translation must not submit"))
    result = app.test_client().post(f"/api/summaries/{item}/translate", json={})
    assert result.status_code == 200
    assert result.get_json()["data"]["summary"]["content_zh"] == {"tldr": "译文"}
    assert app.db.episodes.find_one({"_id": item})["status"] == "summarized"


@pytest.mark.parametrize("failure", ["persist", "executor"])
def test_translation_submission_failure_preserves_summary_and_allows_retry(app, monkeypatch, failure):
    item = summarized_episode(app)
    queue = TaskQueue(max_workers=1)
    queue.set_db(app.db)
    queue.set_app(app)
    monkeypatch.setattr("app.api.summaries.task_queue", queue)
    original_insert, original_submit = app.db.tasks.insert_one, queue.executor.submit
    def refuse(*args, **kwargs):
        raise RuntimeError("submission refused")
    monkeypatch.setattr(app.db.tasks, "insert_one", refuse) if failure == "persist" else monkeypatch.setattr(queue.executor, "submit", refuse)
    try:
        result = app.test_client().post(f"/api/summaries/{item}/translate", json={})
        assert result.status_code == 503 and result.get_json()["error_code"] == "TASK_SUBMIT_FAILED"
        assert app.db.episodes.find_one({"_id": item})["status"] == "summarized"
        assert not queue.tasks
        assert app.db.summaries.find_one({"episode_id": item})["content"]["tldr"] == "Summary"
        monkeypatch.setattr(app.db.tasks, "insert_one", original_insert)
        monkeypatch.setattr(queue.executor, "submit", original_submit)
        monkeypatch.setattr("app.api.summaries._translate_sync", lambda *a, **kw: {})
        assert app.test_client().post(f"/api/summaries/{item}/translate", json={}).status_code == 200
    finally:
        queue.shutdown(wait=True)
