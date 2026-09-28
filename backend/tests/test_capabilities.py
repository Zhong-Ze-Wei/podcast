import sys
from flask import Flask
import pytest

from app.api.capabilities import capabilities_bp
from app.services import capabilities
from app.api import transcripts
from tests.test_transcription_providers import make_app, add_episode
from tests.conftest import MockDB


def test_base_install_reports_missing_engines_without_importing_them(monkeypatch):
    monkeypatch.setattr(capabilities, "package_installed", lambda name: False)
    monkeypatch.setattr(capabilities, "probe_local", lambda *a: pytest.fail("must not probe missing engine"))
    before = set(sys.modules)
    result = capabilities.get_capabilities({})
    assert result["transcription"]["official"]["available"] is True
    for name in ("local_whisper", "local_whisperx"):
        assert result["transcription"][name]["state"] == "not_installed"
        assert result["transcription"][name]["available"] is False
    assert result["transcription"]["assemblyai"]["state"] == "disabled"
    assert not ({"torch", "whisperx", "faster_whisper"} & (set(sys.modules) - before))


@pytest.mark.parametrize("state", ["model_missing", "runtime_error", "unsupported", "ready"])
def test_local_capability_uses_runtime_result(monkeypatch, state):
    monkeypatch.setattr(capabilities, "package_installed", lambda name: True)
    monkeypatch.setattr(capabilities, "probe_local", lambda *a: {"state": state, "reason": state})
    result = capabilities.get_provider_capability("local_whisper", {"TRANSCRIPTION_LOCAL_ENABLED": True})
    assert result["state"] == state
    assert result["available"] == (state == "ready")


def test_disabled_engine_does_not_probe_or_load_models(monkeypatch):
    monkeypatch.setattr(capabilities, "package_installed", lambda name: True)
    monkeypatch.setattr(capabilities, "probe_local", lambda *a: pytest.fail("disabled"))
    assert capabilities.get_provider_capability("local_whisper", {})["state"] == "disabled"


def test_cloud_requires_both_package_and_key(monkeypatch):
    config = {"TRANSCRIPTION_CLOUD_ENABLED": True}
    monkeypatch.setattr(capabilities, "package_installed", lambda name: False)
    assert capabilities.get_provider_capability("assemblyai", config)["state"] == "not_installed"
    monkeypatch.setattr(capabilities, "package_installed", lambda name: True)
    assert capabilities.get_provider_capability("assemblyai", config)["state"] == "not_configured"
    config["ASSEMBLYAI_API_KEY"] = "test-key"
    result = capabilities.get_provider_capability("assemblyai", config)
    assert result["available"] is True
    assert "test-key" not in str(result)


def test_capabilities_endpoint_does_not_need_database(monkeypatch):
    monkeypatch.setattr(capabilities, "package_installed", lambda name: False)
    app = Flask(__name__)
    app.register_blueprint(capabilities_bp, url_prefix="/api")
    response = app.test_client().get("/api/capabilities")
    assert response.status_code == 200
    assert response.json["data"]["transcription"]["local_whisper"]["state"] == "not_installed"
    assert response.json["data"]["transcription"]["local_whisper"]["reason_code"] == "engine_missing"


def test_localized_clients_receive_probe_reason_code(monkeypatch):
    monkeypatch.setattr(capabilities, "package_installed", lambda name: True)
    monkeypatch.setattr(capabilities, "probe_local", lambda *a: {
        "state": "model_missing", "reason": "模型文件不完整", "reason_code": "model_incomplete",
    })
    result = capabilities.get_provider_capability("local_whisper", {"TRANSCRIPTION_LOCAL_ENABLED": True})
    assert result["reason_code"] == "model_incomplete"


def test_unavailable_engine_rejected_before_task_or_episode_mutation(monkeypatch, tmp_path):
    app = make_app(MEDIA_ROOT=str(tmp_path))
    audio = tmp_path / "episode.mp3"
    audio.write_bytes(b"audio")
    db = MockDB()
    episode_id = add_episode(db, local_path="episode.mp3")
    monkeypatch.setattr(transcripts, "get_db", lambda: db)
    monkeypatch.setattr(capabilities, "package_installed", lambda name: False)
    monkeypatch.setattr(transcripts.task_queue, "submit", lambda **kw: pytest.fail("must not queue"))
    with app.test_request_context("/", method="POST", json={"provider": "local_whisper"}):
        response, status = transcripts.create_transcript(str(episode_id))
    assert status == 409
    assert response.json["error_code"] == "TRANSCRIPTION_UNAVAILABLE"
    assert db.episodes.find_one({"_id": episode_id})["status"] == "downloaded"
    assert db.tasks.count_documents({}) == 0


def test_execution_rechecks_after_engine_removed(monkeypatch):
    app = make_app()
    db = MockDB()
    episode_id = add_episode(db)
    monkeypatch.setattr(transcripts, "get_db", lambda: db)
    monkeypatch.setattr(capabilities, "package_installed", lambda name: False)
    with app.app_context(), pytest.raises(capabilities.TranscriptionUnavailable):
        transcripts._transcribe_sync(str(episode_id), provider="local_whisper")


def test_probe_timeout_is_not_reported_as_ready(monkeypatch):
    import subprocess
    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("probe", 20)
    monkeypatch.setattr(capabilities.subprocess, "run", timeout)
    assert capabilities.probe_local("local_whisper", {})["state"] == "runtime_error"
