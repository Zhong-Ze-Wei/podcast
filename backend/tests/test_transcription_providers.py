from bson import ObjectId
from flask import Flask
import sys
import types

from app.api import transcripts
from app.models.episode import Episode
from tests.conftest import MockDB


def make_app(**config):
    app = Flask(__name__)
    app.config.update(
        TRANSCRIPTION_DEFAULT_PROVIDER="official",
        TRANSCRIPTION_CLOUD_ENABLED=False,
        MEDIA_ROOT=".",
        WHISPER_MODEL="base",
        TRANSCRIPTION_DEFAULT_LANGUAGE="auto",
        TRANSCRIPTION_AI_NORMALIZE_ENABLED=False,
    )
    app.config.update(config)
    return app


def add_episode(db, **overrides):
    episode_id = ObjectId()
    doc = {
        "_id": episode_id,
        "title": "Test Episode",
        "status": Episode.STATUS_DOWNLOADED,
        "audio_url": "https://example.com/audio.mp3",
        "transcript_url": None,
        "local_path": None,
    }
    doc.update(overrides)
    db.episodes._data.append(doc)
    return episode_id


def test_auto_provider_without_official_transcript_does_not_queue_cloud_task(monkeypatch):
    app = make_app()
    db = MockDB()
    episode_id = add_episode(db, transcript_url=None)
    monkeypatch.setattr(transcripts, "get_db", lambda: db)
    monkeypatch.setattr(
        transcripts.task_queue,
        "submit",
        lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("cloud task should not be queued")),
    )

    with app.test_request_context(f"/api/transcripts/{episode_id}", method="POST", json={"provider": "auto"}):
        response, status_code = transcripts.create_transcript(str(episode_id))

    body = response.get_json()
    assert status_code == 400
    assert body["error_code"] == "TRANSCRIPTION_PROVIDER_REQUIRED"


def test_assemblyai_provider_is_blocked_when_cloud_transcription_disabled(monkeypatch):
    app = make_app(TRANSCRIPTION_CLOUD_ENABLED=False)
    db = MockDB()
    episode_id = add_episode(db)
    monkeypatch.setattr(transcripts, "get_db", lambda: db)

    with app.test_request_context(f"/api/transcripts/{episode_id}", method="POST", json={"provider": "assemblyai"}):
        response, status_code = transcripts.create_transcript(str(episode_id))

    assert status_code == 423
    assert response.get_json()["error_code"] == "CLOUD_TRANSCRIPTION_DISABLED"


def test_official_provider_queues_transcribe_task(monkeypatch):
    app = make_app()
    db = MockDB()
    episode_id = add_episode(db, transcript_url="https://example.com/transcript.vtt")
    submitted = {}
    monkeypatch.setattr(transcripts, "get_db", lambda: db)

    def fake_submit(**kwargs):
        submitted.update(kwargs)
        return "task-1"

    monkeypatch.setattr(transcripts.task_queue, "submit", fake_submit)

    with app.test_request_context(f"/api/transcripts/{episode_id}", method="POST", json={"provider": "official"}):
        response, status_code = transcripts.create_transcript(str(episode_id))

    body = response.get_json()
    assert status_code == 200
    assert body["data"]["task_id"] == "task-1"
    assert body["data"]["provider"] == "official"
    assert submitted["task_type"] == "transcribe"


def test_local_whisper_provider_requires_existing_local_audio(monkeypatch, tmp_path):
    app = make_app(MEDIA_ROOT=str(tmp_path))
    db = MockDB()
    episode_id = add_episode(db, local_path="audio/missing.mp3")
    monkeypatch.setattr(transcripts, "get_db", lambda: db)

    with app.test_request_context(f"/api/transcripts/{episode_id}", method="POST", json={"provider": "local_whisper"}):
        response, status_code = transcripts.create_transcript(str(episode_id))

    assert status_code == 400
    assert response.get_json()["error_code"] == "LOCAL_AUDIO_NOT_FOUND"


def test_local_whisperx_provider_can_be_queued_when_local_audio_exists(monkeypatch, tmp_path):
    # This test isolates dispatch/persistence; capability gates are tested separately.
    monkeypatch.setattr(transcripts, "ensure_transcription_available", lambda *args: None)
    app = make_app(MEDIA_ROOT=str(tmp_path))
    db = MockDB()
    audio_file = tmp_path / "audio" / "episode.mp3"
    audio_file.parent.mkdir()
    audio_file.write_bytes(b"audio")
    episode_id = add_episode(db, local_path="audio/episode.mp3")
    submitted = {}
    monkeypatch.setattr(transcripts, "get_db", lambda: db)

    def fake_submit(**kwargs):
        submitted.update(kwargs)
        return "task-whisperx"

    monkeypatch.setattr(transcripts.task_queue, "submit", fake_submit)

    with app.test_request_context(f"/api/transcripts/{episode_id}", method="POST", json={"provider": "local_whisperx"}):
        response, status_code = transcripts.create_transcript(str(episode_id))

    body = response.get_json()
    assert status_code == 200
    assert body["data"]["provider"] == "local_whisperx"
    assert submitted["task_type"] == "transcribe"


def test_create_transcript_accepts_language_hint(monkeypatch, tmp_path):
    # This test isolates dispatch/persistence; capability gates are tested separately.
    monkeypatch.setattr(transcripts, "ensure_transcription_available", lambda *args: None)
    app = make_app(MEDIA_ROOT=str(tmp_path))
    db = MockDB()
    audio_file = tmp_path / "audio" / "episode.mp3"
    audio_file.parent.mkdir()
    audio_file.write_bytes(b"audio")
    episode_id = add_episode(db, local_path="audio/episode.mp3")
    submitted = {}
    monkeypatch.setattr(transcripts, "get_db", lambda: db)

    def fake_submit(**kwargs):
        submitted.update(kwargs)
        return "task-zh"

    monkeypatch.setattr(transcripts.task_queue, "submit", fake_submit)

    with app.test_request_context(
        f"/api/transcripts/{episode_id}",
        method="POST",
        json={"provider": "local_whisper", "language": "zh"},
    ):
        response, status_code = transcripts.create_transcript(str(episode_id))

    body = response.get_json()
    assert status_code == 200
    assert body["data"]["language"] == "zh"
    assert submitted["task_type"] == "transcribe"


def test_transcribe_sync_local_whisper_saves_transcript(monkeypatch, tmp_path):
    # This test isolates dispatch/persistence; capability gates are tested separately.
    monkeypatch.setattr(transcripts, "ensure_transcription_available", lambda *args: None)
    app = make_app(
        MEDIA_ROOT=str(tmp_path),
        WHISPER_MODEL="small",
        WHISPER_DEVICE="cuda",
        WHISPER_COMPUTE_TYPE="float16",
    )
    db = MockDB()
    audio_file = tmp_path / "audio" / "episode.mp3"
    audio_file.parent.mkdir()
    audio_file.write_bytes(b"audio")
    episode_id = add_episode(db, local_path="audio/episode.mp3")
    monkeypatch.setattr(transcripts, "get_db", lambda: db)
    monkeypatch.setattr(
        "app.services.whisper_service.transcribe_audio",
        lambda audio_path, model_name, language=None, progress_callback=None: (
            "这 是 中文",
            [{"start": 0, "end": 1, "text": "这 是 中文"}],
            language or "zh",
        ),
    )

    with app.app_context():
        result = transcripts._transcribe_sync(str(episode_id), provider="local_whisper", language="zh")

    saved = db.transcripts.find_one({"episode_id": episode_id})
    assert result["source"] == "local_whisper"
    assert result["model"] == "faster-whisper:small:cuda:float16"
    assert saved["text"] == "这是中文"
    assert saved["source"] == "local_whisper"
    assert saved["model"] == "faster-whisper:small:cuda:float16"
    assert saved["language"] == "zh"


def test_transcribe_sync_local_whisperx_saves_transcript(monkeypatch, tmp_path):
    # This test isolates dispatch/persistence; capability gates are tested separately.
    monkeypatch.setattr(transcripts, "ensure_transcription_available", lambda *args: None)
    app = make_app(
        MEDIA_ROOT=str(tmp_path),
        WHISPER_MODEL="base",
        WHISPER_DEVICE="cuda",
        WHISPER_COMPUTE_TYPE="float16",
    )
    db = MockDB()
    audio_file = tmp_path / "audio" / "episode.mp3"
    audio_file.parent.mkdir()
    audio_file.write_bytes(b"audio")
    episode_id = add_episode(db, local_path="audio/episode.mp3")
    monkeypatch.setattr(transcripts, "get_db", lambda: db)
    monkeypatch.setattr(
        "app.services.whisperx_service.transcribe_audio",
        lambda audio_path, model_name, language=None, progress_callback=None: (
            "hello whisperx",
            [{"start": 0, "end": 1, "time": "00:00", "text": "hello whisperx"}],
            language or "en",
        ),
    )

    with app.app_context():
        result = transcripts._transcribe_sync(str(episode_id), provider="local_whisperx")

    saved = db.transcripts.find_one({"episode_id": episode_id})
    assert result["source"] == "local_whisperx"
    assert result["model"] == "whisperx:base:cuda:float16"
    assert saved["text"] == "hello whisperx"
    assert saved["source"] == "local_whisperx"


def test_fetch_external_transcript_saves_paragraph_segments(monkeypatch):
    app = make_app()
    db = MockDB()
    episode_id = add_episode(db, transcript_url="https://example.com/transcript")
    monkeypatch.setattr(transcripts, "get_db", lambda: db)
    class FakeResult:
        text = "Intro paragraph.\n\nSpeaker A: Main transcript paragraph."
        segments = []
        format = "html"
        confidence = 0.4

    monkeypatch.setattr(
        transcripts.TranscriptFetcher,
        "fetch_transcript_result",
        lambda url: (FakeResult(), None),
    )

    with app.test_request_context(f"/api/transcripts/{episode_id}/fetch", method="POST"):
        response, status_code = transcripts.fetch_external_transcript(str(episode_id))

    saved = db.transcripts.find_one({"episode_id": episode_id})
    assert status_code == 200
    assert saved["segments"] == [
        {"text": "Intro paragraph.", "time": ""},
        {"text": "Speaker A: Main transcript paragraph.", "time": ""},
    ]


def test_fetch_external_transcript_prefers_structured_segments(monkeypatch):
    app = make_app()
    db = MockDB()
    episode_id = add_episode(db, transcript_url="https://example.com/transcript")
    monkeypatch.setattr(transcripts, "get_db", lambda: db)

    class FakeResult:
        text = "Host (00:01:02)\nWelcome to the episode."
        segments = [{"speaker": "Host", "time": "00:01:02", "start": 62, "text": "Welcome to the episode."}]
        format = "html"
        confidence = 0.9

    monkeypatch.setattr(
        transcripts.TranscriptFetcher,
        "fetch_transcript_result",
        lambda url: (FakeResult(), None),
    )

    with app.test_request_context(f"/api/transcripts/{episode_id}/fetch", method="POST"):
        response, status_code = transcripts.fetch_external_transcript(str(episode_id))

    saved = db.transcripts.find_one({"episode_id": episode_id})
    assert status_code == 200
    assert saved["segments"] == FakeResult.segments


def test_assemblyai_transcription_config_includes_required_speech_models(monkeypatch):
    app = make_app(TRANSCRIPTION_CLOUD_ENABLED=True)
    db = MockDB()
    episode_id = add_episode(db)
    episode = db.episodes.find_one({"_id": episode_id})
    captured = {}

    class FakeTranscriptStatus:
        error = "error"

    class FakeConfig:
        def __init__(self, **kwargs):
            captured.update(kwargs)

    class FakeUtterance:
        start = 0
        end = 1000
        speaker = "A"
        text = "hello cloud"

    class FakeTranscript:
        status = "completed"
        error = None
        text = "hello cloud"
        utterances = [FakeUtterance()]
        chapters = []
        entities = []
        language_code = "en"
        audio_duration = 1

    class FakeTranscriber:
        def transcribe(self, audio_url, config=None):
            captured["audio_url"] = audio_url
            captured["config"] = config
            return FakeTranscript()

    fake_assemblyai = types.SimpleNamespace(
        settings=types.SimpleNamespace(api_key=None),
        TranscriptStatus=FakeTranscriptStatus,
        TranscriptionConfig=FakeConfig,
        Transcriber=FakeTranscriber,
    )

    monkeypatch.setitem(sys.modules, "assemblyai", fake_assemblyai)
    monkeypatch.setenv("ASSEMBLYAI_API_KEY", "test-key")
    monkeypatch.setattr(transcripts, "get_db", lambda: db)

    with app.app_context():
        result = transcripts._transcribe_with_assemblyai(
            "https://example.com/audio.mp3",
            episode_id,
            episode,
            language="zh",
        )

    assert result["source"] == "assemblyai"
    assert captured["speech_models"] == ["universal-3-pro", "universal-2"]
    assert captured["language_code"] == "zh"
    assert "entity_detection" not in captured
