import sys
import types
import pytest
from app.services import transcription_probe


@pytest.fixture
def runtime(monkeypatch):
    monkeypatch.setitem(sys.modules, "ctranslate2", types.SimpleNamespace(get_supported_compute_types=lambda *args: {"int8"}))
    monkeypatch.setitem(sys.modules, "faster_whisper", types.ModuleType("faster_whisper"))
    monkeypatch.setattr(transcription_probe.shutil, "which", lambda name: "/bin/ffmpeg")


def test_model_probe_is_offline_and_does_not_load_model(runtime, monkeypatch):
    def lookup(model, **kwargs):
        assert kwargs["local_files_only"] is True
        raise FileNotFoundError("uncached model")
    monkeypatch.setitem(sys.modules, "faster_whisper.utils", types.SimpleNamespace(download_model=lookup))
    result = transcription_probe.inspect_runtime({"provider": "local_whisper", "WHISPER_MODEL": "base"})
    assert result["state"] == "model_missing"
    assert result["reason_code"] == "model_missing"


def test_incomplete_model_is_not_ready(runtime, monkeypatch, tmp_path):
    monkeypatch.setitem(sys.modules, "faster_whisper.utils", types.SimpleNamespace(download_model=lambda *a, **kw: pytest.fail("local path")))
    (tmp_path / "config.json").write_text("{}")
    options = {"provider": "local_whisper", "WHISPER_MODEL": str(tmp_path)}
    assert transcription_probe.inspect_runtime(options)["state"] == "model_missing"
    (tmp_path / "model.bin").write_bytes(b"test fixture")
    (tmp_path / "tokenizer.json").write_text("{}")
    assert transcription_probe.inspect_runtime(options)["state"] == "ready"


def test_unsupported_device_rejected_before_model_lookup(runtime, monkeypatch):
    monkeypatch.setitem(sys.modules, "faster_whisper.utils", types.SimpleNamespace(download_model=lambda *a, **kw: pytest.fail("must not look up model")))
    assert transcription_probe.inspect_runtime({"provider": "local_whisper", "WHISPER_DEVICE": "mps"})["state"] == "unsupported"


def test_diarization_requires_token_even_with_cached_models(monkeypatch):
    monkeypatch.setenv("WHISPERX_DIARIZE", "1")
    for key in ("HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGINGFACE_HUB_TOKEN"):
        monkeypatch.delenv(key, raising=False)
    assert transcription_probe.inspect_runtime({"provider": "local_whisperx"})["state"] == "not_configured"
