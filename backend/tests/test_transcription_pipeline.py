"""A transcription request owns its download dependency in the backend."""
from bson import ObjectId
import pytest
from app.api import transcripts
from tests.test_transcription_providers import make_app, add_episode
from tests.conftest import MockDB


def test_explicit_download_opt_in_runs_one_backend_pipeline(monkeypatch, tmp_path):
    app = make_app(MEDIA_ROOT=str(tmp_path))
    db = MockDB()
    episode_id = add_episode(db, status="new")
    submitted = []
    monkeypatch.setattr(transcripts, "get_db", lambda: db)
    monkeypatch.setattr("app.services.whisper_service.is_available", lambda: True)
    monkeypatch.setattr(transcripts.task_queue, "submit_unique", lambda **kw: submitted.append(kw) or "pipeline-1")
    calls = []
    def download(self, episode_id, progress_callback=None):
        calls.append("download")
        (tmp_path / "audio.mp3").write_bytes(b"audio")
        db.episodes.update_one({"_id": ObjectId(episode_id)}, {"$set": {"local_path": "audio.mp3", "has_local_audio": True, "status": "downloaded"}})
        return {"local_path": "audio.mp3"}
    def transcribe_audio(path, **kwargs):
        calls.append("transcribe")
        return "hello", [{"start": 0, "end": 1, "text": "hello"}], "en"

    with app.test_request_context(method="POST", json={"provider": "local_whisper", "download_if_needed": True}):
        response, code = transcripts.create_transcript(str(episode_id))
    assert code == 200
    assert response.get_json()["data"]["task_id"] == "pipeline-1"
    assert len(submitted) == 1
    from app.services.download_service import DownloadService
    monkeypatch.setattr(DownloadService, "download", download)
    monkeypatch.setattr("app.services.whisper_service.transcribe_audio", transcribe_audio)
    with app.app_context():
        submitted[0]["func"]()
    assert calls == ["download", "transcribe"]
    assert db.episodes.find_one({"_id": episode_id})["has_transcript"] is True


def test_pipeline_reuses_audio_and_failure_keeps_downloaded_artifact(monkeypatch, tmp_path):
    from app.services.transcription_service import TranscriptionService
    from app.services.download_service import DownloadService
    app = make_app(MEDIA_ROOT=str(tmp_path))
    db = MockDB()
    (tmp_path / "audio.mp3").write_bytes(b"audio")
    episode_id = add_episode(db, status="transcribing", local_path="audio.mp3")
    monkeypatch.setattr(DownloadService, "download", lambda *a, **kw: pytest.fail("existing audio must be reused"))
    def fail(*args, **kwargs):
        raise RuntimeError("transcription failed")
    monkeypatch.setattr("app.services.whisper_service.transcribe_audio", fail)
    with app.app_context():
        service = TranscriptionService(db)
        with pytest.raises(RuntimeError, match="transcription failed"):
            service.run(str(episode_id), "local_whisper", download_if_needed=True)
        service.restore_episode_status(str(episode_id), "transcription failed")
    episode = db.episodes.find_one({"_id": episode_id})
    assert episode["status"] == "downloaded"
    assert episode["local_path"] == "audio.mp3"


def test_download_failure_does_not_start_transcription(monkeypatch, tmp_path):
    from app.services.transcription_service import TranscriptionService
    from app.services.download_service import DownloadService
    app = make_app(MEDIA_ROOT=str(tmp_path))
    db = MockDB()
    episode_id = add_episode(db, status="new")
    def fail(*args, **kwargs):
        raise RuntimeError("download failed")
    monkeypatch.setattr(DownloadService, "download", fail)
    monkeypatch.setattr("app.services.whisper_service.transcribe_audio", lambda *a, **kw: pytest.fail("no audio means no transcription"))
    with app.app_context(), pytest.raises(RuntimeError, match="download failed"):
        TranscriptionService(db).run(str(episode_id), "local_whisper", download_if_needed=True)


def test_interrupted_download_never_publishes_partial_audio(monkeypatch, tmp_path):
    from app.services.download_service import DownloadService
    app = make_app(MEDIA_ROOT=str(tmp_path))
    db = MockDB()
    episode_id = add_episode(db, status="downloading", feed_id=ObjectId())
    class Response:
        headers = {}
        def raise_for_status(self):
            pass
        def iter_content(self, chunk_size):
            yield b"partial"
            raise OSError("network interrupted")
        def close(self):
            pass
    monkeypatch.setattr("requests.get", lambda *a, **kw: Response())
    with app.app_context(), pytest.raises(OSError, match="network interrupted"):
        DownloadService(db).download(str(episode_id))
    assert list(tmp_path.rglob("*.mp3")) == []
    assert list(tmp_path.rglob("*.part")) == []
    assert not db.episodes.find_one({"_id": episode_id}).get("has_local_audio")


def test_pipeline_finishes_with_a_single_queue_worker(monkeypatch, tmp_path):
    from threading import Event
    from app.services.task_queue import TaskQueue
    from app.services.transcription_service import TranscriptionService
    from app.services.download_service import DownloadService
    app = make_app(MEDIA_ROOT=str(tmp_path))
    db = MockDB()
    app.db = db
    episode_id = add_episode(db, status="new")
    finished = Event()
    def download(self, episode_id, progress_callback=None):
        (tmp_path / "audio.mp3").write_bytes(b"audio")
        db.episodes.update_one({"_id": ObjectId(episode_id)}, {"$set": {"local_path": "audio.mp3"}})
    def transcribe(path, **kwargs):
        finished.set()
        return "hello", [], "en"
    monkeypatch.setattr(DownloadService, "download", download)
    monkeypatch.setattr("app.services.whisper_service.transcribe_audio", transcribe)
    queue = TaskQueue(max_workers=1)
    queue.set_app(app)
    queue.set_db(db)
    def run(progress_callback=None):
        return TranscriptionService(db).run(str(episode_id), "local_whisper", download_if_needed=True, progress_callback=progress_callback)
    task_id = queue.submit_unique("transcribe", run, dedup_key=f"test:{episode_id}")
    try:
        assert finished.wait(5), "download dependency must not wait for another worker"
    finally:
        queue.shutdown(wait=finished.is_set())
    assert queue.get_status(task_id)["status"] == "completed"
    assert db.episodes.find_one({"_id": episode_id})["has_transcript"] is True
