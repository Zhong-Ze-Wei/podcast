"""Episode submission coordinates shared processing operations before workers run."""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, Event
from bson import ObjectId
from flask import Flask
import pytest
from app.api.episodes import episodes_bp
from app.api.transcripts import transcripts_bp
from app.api.summaries import summaries_bp
from app.services.task_queue import TaskQueue
from tests.conftest import MockDB


@pytest.fixture
def app(tmp_path):
    app = Flask(__name__)
    app.config.update(MEDIA_ROOT=str(tmp_path), AI_ANALYSIS_ENABLED=True)
    app.db = MockDB()
    app.register_blueprint(episodes_bp, url_prefix="/api/episodes")
    app.register_blueprint(transcripts_bp, url_prefix="/api/transcripts")
    app.register_blueprint(summaries_bp, url_prefix="/api/summaries")
    return app


def add_episode(app, **fields):
    doc = {"title": "Shared", "status": "new", "audio_url": "https://example.com/audio.mp3", "transcript_url": "https://example.com/sub.vtt"}
    doc.update(fields)
    return app.db.episodes.insert_one(doc).inserted_id


class PendingQueue:
    def __init__(self, db):
        self.db = db
        self.submitted = []

    def submit_unique(self, **kwargs):
        task_id = f"task-{len(self.submitted) + 1}"
        self.submitted.append(kwargs)
        self.db.tasks.insert_one({"task_id": task_id, "episode_id": kwargs["episode_id"], "task_type": kwargs["task_type"], "status": "pending", "dedup_key": kwargs["dedup_key"]})
        return task_id

    def submit(self, **kwargs):
        return self.submit_unique(dedup_key="legacy-summary", **kwargs)


def race_requests(app, monkeypatch, item, requests):
    """Both request handlers read the same episode version before submitting."""
    read = app.db.episodes.find_one
    both_read = Barrier(2)
    reads = 0
    def synchronized_read(query, *args, **kwargs):
        nonlocal reads
        result = read(query, *args, **kwargs)
        if query == {"_id": item} and reads < 2:
            reads += 1
            both_read.wait(timeout=5)
        return result
    monkeypatch.setattr(app.db.episodes, "find_one", synchronized_read)
    def post(request):
        path, payload = request
        with app.test_client() as client:
            return client.post(path, json=payload)
    with ThreadPoolExecutor(max_workers=2) as workers:
        futures = [workers.submit(post, request) for request in requests]
        return [future.result(timeout=10) for future in futures]


@pytest.mark.parametrize("operations", [("download", "transcribe"), ("download", "summarize"), ("transcribe", "summarize")])
def test_concurrent_different_operations_reserve_only_one_task(app, monkeypatch, operations):
    item = add_episode(app)
    app.db.transcripts.insert_one({"episode_id": item, "text": "Existing text"})
    queue = PendingQueue(app.db)
    monkeypatch.setattr("app.api.episodes.task_queue", queue)
    monkeypatch.setattr("app.api.transcripts.task_queue", queue)
    monkeypatch.setattr("app.api.summaries.task_queue", queue)
    paths = {"download": f"/api/episodes/{item}/download", "transcribe": f"/api/transcripts/{item}", "summarize": f"/api/summaries/{item}"}
    payloads = {"download": {}, "transcribe": {"provider": "official"}, "summarize": {}}
    responses = race_requests(app, monkeypatch, item, [(paths[operation], payloads[operation]) for operation in operations])
    assert sorted(response.status_code for response in responses) == [200, 409]
    assert len(queue.submitted) == 1
    assert next(response for response in responses if response.status_code == 409).get_json()["error_code"] == "TASK_IN_PROGRESS"


@pytest.mark.parametrize("operation", ["download", "transcribe", "summarize"])
def test_concurrent_same_operation_reuses_single_task(app, monkeypatch, operation):
    item = add_episode(app, has_transcript=operation == "summarize")
    app.db.transcripts.insert_one({"episode_id": item, "text": "Existing text"})
    queue = PendingQueue(app.db)
    for module in ("episodes", "transcripts", "summaries"):
        monkeypatch.setattr(f"app.api.{module}.task_queue", queue)
    path = {"download": f"/api/episodes/{item}/download", "transcribe": f"/api/transcripts/{item}", "summarize": f"/api/summaries/{item}"}[operation]
    payload = {"provider": "official"} if operation == "transcribe" else {}
    responses = race_requests(app, monkeypatch, item, [(path, payload), (path, payload)])
    assert [response.status_code for response in responses] == [200, 200]
    assert len(queue.submitted) == 1
    assert {response.get_json()["data"]["task_id"] for response in responses} == {"task-1"}


@pytest.mark.parametrize("operation,status,fields", [
    ("download", "new", {}),
    ("transcribe", "downloaded", {"local_path": "exists.mp3"}),
    ("summarize", "summarized", {"has_transcript": True, "has_summary": True}),
])
@pytest.mark.parametrize("failure", ["persist", "executor"])
def test_submission_failure_restores_results_and_next_attempt_is_retryable(app, monkeypatch, tmp_path, operation, status, fields, failure):
    (tmp_path / "exists.mp3").write_bytes(b"audio")
    item = add_episode(app, status=status, **fields)
    app.db.transcripts.insert_one({"episode_id": item, "text": "Existing text"})
    queue = TaskQueue(max_workers=1)
    queue.set_db(app.db)
    queue.set_app(app)
    for module in ("episodes", "transcripts", "summaries"):
        monkeypatch.setattr(f"app.api.{module}.task_queue", queue)
    original_insert = app.db.tasks.insert_one
    original_submit = queue.executor.submit
    def fail(*args, **kwargs):
        raise RuntimeError("submission refused")
    if failure == "persist":
        monkeypatch.setattr(app.db.tasks, "insert_one", fail)
    else:
        monkeypatch.setattr(queue.executor, "submit", fail)
    path = {"download": f"/api/episodes/{item}/download", "transcribe": f"/api/transcripts/{item}", "summarize": f"/api/summaries/{item}"}[operation]
    payload = {"provider": "official"} if operation == "transcribe" else {"force": True}
    try:
        response = app.test_client().post(path, json=payload)
        assert response.status_code == 503
        assert response.get_json()["error_code"] == "TASK_SUBMIT_FAILED"
        assert app.db.episodes.find_one({"_id": item})["status"] == status
        assert not queue.tasks and not queue._futures
        monkeypatch.setattr(app.db.tasks, "insert_one", original_insert)
        monkeypatch.setattr(queue.executor, "submit", original_submit)
        monkeypatch.setattr("app.api.episodes._download_episode_sync", lambda *a, **kw: {})
        monkeypatch.setattr("app.services.transcription_service.TranscriptionService.run", lambda *a, **kw: {})
        monkeypatch.setattr("app.api.summaries._summarize_sync", lambda *a, **kw: {})
        retried = app.test_client().post(path, json=payload)
        assert retried.status_code == 200
    finally:
        queue.shutdown(wait=True)


def test_cas_does_not_overwrite_a_changed_episode(app, monkeypatch):
    item = add_episode(app)
    queue = PendingQueue(app.db)
    monkeypatch.setattr("app.api.episodes.task_queue", queue)
    update = app.db.episodes.update_one
    def change_before_reserving(query, updates, **kwargs):
        if updates.get("$set", {}).get("status") == "downloading":
            update({"_id": item}, {"$set": {"status": "transcribing"}})
        return update(query, updates, **kwargs)
    monkeypatch.setattr(app.db.episodes, "update_one", change_before_reserving)
    response = app.test_client().post(f"/api/episodes/{item}/download")
    assert response.status_code == 409 and response.get_json()["error_code"] == "TASK_IN_PROGRESS"
    assert app.db.episodes.find_one({"_id": item})["status"] == "transcribing"
    assert not queue.submitted


@pytest.mark.parametrize("operation", ["download", "transcribe", "summarize"])
def test_active_identical_submission_is_reused_after_artifact_is_saved(app, monkeypatch, tmp_path, operation):
    (tmp_path / "saved.mp3").write_bytes(b"audio")
    item = add_episode(app, has_transcript=operation == "summarize")
    app.db.transcripts.insert_one({"episode_id": item, "text": "Existing text"})
    queue = PendingQueue(app.db)
    for module in ("episodes", "transcripts", "summaries"):
        monkeypatch.setattr(f"app.api.{module}.task_queue", queue)
    path = {"download": f"/api/episodes/{item}/download", "transcribe": f"/api/transcripts/{item}", "summarize": f"/api/summaries/{item}"}[operation]
    payload = {"provider": "official"} if operation == "transcribe" else {}
    client = app.test_client()
    first = client.post(path, json=payload)
    assert first.status_code == 200
    updates = {"local_path": "saved.mp3"} if operation == "download" else {"has_transcript": True} if operation == "transcribe" else {"has_summary": True}
    app.db.episodes.update_one({"_id": item}, {"$set": updates})
    if operation == "summarize":
        app.db.summaries.insert_one({"episode_id": item, "template_name": "learning"})
    repeated = client.post(path, json=payload)
    assert repeated.status_code == 200
    assert repeated.get_json()["data"]["task_id"] == first.get_json()["data"]["task_id"]
    assert len(queue.submitted) == 1


@pytest.mark.parametrize("operation", ["download", "transcribe", "summarize"])
@pytest.mark.parametrize("fails", [False, True])
def test_fast_worker_terminal_state_is_not_overwritten_after_submission(app, monkeypatch, tmp_path, operation, fails):
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
            assert self.finished.wait(5), "the test worker must finish before the HTTP submission returns"
            return task_id

    (tmp_path / "existing.mp3").write_bytes(b"audio")
    fields = {"local_path": "existing.mp3", "status": "downloaded"} if operation == "transcribe" else {"has_transcript": True, "has_summary": True, "status": "summarized"} if operation == "summarize" else {}
    item = add_episode(app, **fields)
    app.db.transcripts.insert_one({"episode_id": item, "text": "Existing text"})
    queue = FastQueue()
    queue.set_db(app.db)
    queue.set_app(app)
    for module in ("episodes", "transcripts", "summaries"):
        monkeypatch.setattr(f"app.api.{module}.task_queue", queue)
    def worker(*args, **kwargs):
        status = app.db.episodes.find_one({"_id": item})["status"]
        assert status == {"download": "downloading", "transcribe": "transcribing", "summarize": "summarizing"}[operation]
        if fails:
            raise RuntimeError("worker failed")
        changes = {"status": {"download": "downloaded", "transcribe": "transcribed", "summarize": "summarized"}[operation]}
        if operation == "download":
            changes.update(local_path="existing.mp3", has_local_audio=True)
        elif operation == "transcribe":
            changes["has_transcript"] = True
        else:
            changes["has_summary"] = True
        app.db.episodes.update_one({"_id": item}, {"$set": changes})
        return {"_id": ObjectId()}
    monkeypatch.setattr("app.api.episodes._download_episode_sync", worker)
    monkeypatch.setattr("app.services.transcription_service.TranscriptionService.run", worker)
    class SummaryService:
        def generate_summary(self, **kwargs):
            return worker(**kwargs)
        def translate_summary(self, **kwargs):
            return {}
    monkeypatch.setattr("app.api.summaries.get_summary_service", lambda db: SummaryService())
    path = {"download": f"/api/episodes/{item}/download", "transcribe": f"/api/transcripts/{item}", "summarize": f"/api/summaries/{item}"}[operation]
    payload = {"provider": "official"} if operation == "transcribe" else {"force": True}
    try:
        response = app.test_client().post(path, json=payload)
        assert response.status_code == 200
        task = queue.get_status(response.get_json()["data"]["task_id"])
        assert task["status"] == ("failed" if fails else "completed")
        expected = {"download": "new", "transcribe": "downloaded", "summarize": "summarized"} if fails else {"download": "downloaded", "transcribe": "transcribed", "summarize": "summarized"}
        assert app.db.episodes.find_one({"_id": item})["status"] == expected[operation]
    finally:
        queue.shutdown(wait=True)


def test_legacy_video_submission_reuses_the_same_reserved_task(app, monkeypatch):
    monkeypatch.setattr("app.services.whisperx_service.is_available", lambda: True)
    item = add_episode(app, guid="youtube:video-1")
    queue = PendingQueue(app.db)
    monkeypatch.setattr("app.api.transcripts.task_queue", queue)
    client = app.test_client()
    path = f"/api/transcripts/{item}/fetch-video-audio"
    first = client.post(path)
    assert first.status_code == 200
    repeated = client.post(path)
    assert repeated.status_code == 200
    assert repeated.get_json()["data"]["task_id"] == first.get_json()["data"]["task_id"]
    assert len(queue.submitted) == 1


@pytest.mark.parametrize("resource", ["transcript", "summary"])
def test_delete_cannot_remove_results_while_shared_processing_is_active(app, resource):
    item = add_episode(app, has_transcript=True, has_summary=True)
    app.db.transcripts.insert_one({"episode_id": item, "text": "Keep transcript"})
    app.db.summaries.insert_one({"episode_id": item, "template_name": "learning"})
    app.db.tasks.insert_one({"task_id": "active", "episode_id": str(item), "task_type": "download", "status": "pending", "owner_id": "another-user"})
    path = f"/api/{'transcripts' if resource == 'transcript' else 'summaries'}/{item}"
    response = app.test_client().delete(path)
    assert response.status_code == 409 and response.get_json()["error_code"] == "TASK_IN_PROGRESS"
    assert app.db.transcripts.count_documents({"episode_id": item}) == 1
    assert app.db.summaries.count_documents({"episode_id": item}) == 1


def test_external_fetch_does_not_hold_submission_lock_and_rechecks_before_saving(app, monkeypatch):
    from types import SimpleNamespace
    item = add_episode(app)
    downloading = PendingQueue(app.db)
    monkeypatch.setattr("app.api.episodes.task_queue", downloading)
    fetching, release = Event(), Event()
    def fetch(url):
        fetching.set()
        assert release.wait(5)
        return SimpleNamespace(text="Fetched subtitle", segments=[]), None
    monkeypatch.setattr("app.api.transcripts.TranscriptFetcher.fetch_transcript_result", fetch)
    def request(path):
        with app.test_client() as client:
            return client.post(path)
    with ThreadPoolExecutor(max_workers=2) as workers:
        external = workers.submit(request, f"/api/transcripts/{item}/fetch")
        try:
            assert fetching.wait(5)
            download = workers.submit(request, f"/api/episodes/{item}/download")
            assert download.result(timeout=5).status_code == 200
            release.set()
            response = external.result(timeout=5)
        finally:
            release.set()
    assert response.status_code == 409 and response.get_json()["error_code"] == "TASK_IN_PROGRESS"
    assert app.db.transcripts.count_documents({"episode_id": item}) == 0
    assert app.db.episodes.find_one({"_id": item})["status"] == "downloading"


def test_delete_updates_artifact_flags_and_retains_other_existing_results(app):
    item = add_episode(app, status="summarized", has_transcript=True, has_summary=True)
    app.db.transcripts.insert_one({"episode_id": item, "text": "Text"})
    app.db.summaries.insert_one({"episode_id": item, "template_name": "learning"})
    client = app.test_client()
    assert client.delete(f"/api/transcripts/{item}").status_code == 200
    current = app.db.episodes.find_one({"_id": item})
    assert current["has_transcript"] is False and current["has_summary"] is True and current["status"] == "summarized"
    assert client.delete(f"/api/summaries/{item}").status_code == 200
    current = app.db.episodes.find_one({"_id": item})
    assert current["has_summary"] is False and current["status"] == "new"
    assert client.get("/api/episodes?processed=true").get_json()["pagination"]["total"] == 0
