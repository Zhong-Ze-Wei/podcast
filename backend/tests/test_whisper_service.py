import sys
import types

import pytest

from app.services import whisper_service


def test_get_model_passes_configured_download_root(monkeypatch, tmp_path):
    captured = {}

    class FakeWhisperModel:
        def __init__(self, model_name, **kwargs):
            captured["model_name"] = model_name
            captured.update(kwargs)

    monkeypatch.setenv("WHISPER_MODEL_DIR", str(tmp_path))
    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        types.SimpleNamespace(WhisperModel=FakeWhisperModel),
    )
    monkeypatch.setattr(whisper_service, "_model", None)
    monkeypatch.setattr(whisper_service, "_model_name", None)
    monkeypatch.setattr(whisper_service, "_model_dir", None)

    whisper_service.get_model("base")

    assert captured["model_name"] == "base"
    assert captured["download_root"] == str(tmp_path)


def test_get_model_passes_configured_runtime_options(monkeypatch, tmp_path):
    captured = {}

    class FakeWhisperModel:
        def __init__(self, model_name, **kwargs):
            captured["model_name"] = model_name
            captured.update(kwargs)

    monkeypatch.setenv("WHISPER_MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("WHISPER_DEVICE", "cuda")
    monkeypatch.setenv("WHISPER_COMPUTE_TYPE", "float16")
    monkeypatch.setenv("WHISPER_DEVICE_INDEX", "0")
    monkeypatch.setenv("WHISPER_NUM_WORKERS", "2")
    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        types.SimpleNamespace(WhisperModel=FakeWhisperModel),
    )
    monkeypatch.setattr(whisper_service, "_model", None)
    monkeypatch.setattr(whisper_service, "_model_name", None)
    monkeypatch.setattr(whisper_service, "_model_dir", None)
    monkeypatch.setattr(whisper_service, "_model_runtime", None)

    whisper_service.get_model("base")

    assert captured["model_name"] == "base"
    assert captured["device"] == "cuda"
    assert captured["compute_type"] == "float16"
    assert captured["device_index"] == 0
    assert captured["num_workers"] == 2
    assert captured["download_root"] == str(tmp_path)


def test_get_model_reloads_when_runtime_options_change(monkeypatch, tmp_path):
    created = []

    class FakeWhisperModel:
        def __init__(self, model_name, **kwargs):
            created.append((model_name, kwargs))

    monkeypatch.setenv("WHISPER_MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("WHISPER_DEVICE", "cpu")
    monkeypatch.setenv("WHISPER_COMPUTE_TYPE", "int8")
    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        types.SimpleNamespace(WhisperModel=FakeWhisperModel),
    )
    monkeypatch.setattr(whisper_service, "_model", None)
    monkeypatch.setattr(whisper_service, "_model_name", None)
    monkeypatch.setattr(whisper_service, "_model_dir", None)
    monkeypatch.setattr(whisper_service, "_model_runtime", None)

    whisper_service.get_model("base")
    monkeypatch.setenv("WHISPER_DEVICE", "cuda")
    monkeypatch.setenv("WHISPER_COMPUTE_TYPE", "float16")
    whisper_service.get_model("base")

    assert len(created) == 2
    assert created[0][1]["device"] == "cpu"
    assert created[1][1]["device"] == "cuda"


def test_transcribe_audio_fails_clearly_when_ffmpeg_missing(monkeypatch):
    monkeypatch.setattr(whisper_service.shutil, "which", lambda name: None)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", types.SimpleNamespace(get_ffmpeg_exe=lambda: (_ for _ in ()).throw(RuntimeError("missing"))))

    with pytest.raises(RuntimeError) as exc_info:
        whisper_service.transcribe_audio("episode.mp3", model_name="base")

    assert "FFmpeg is required for local transcription" in str(exc_info.value)


def test_transcribe_audio_uses_imageio_ffmpeg_fallback(monkeypatch):
    class FakeWhisperModel:
        def transcribe(self, audio_path, **kwargs):
            info = types.SimpleNamespace(language="en", language_probability=0.99, duration=1.0)
            segment = types.SimpleNamespace(start=0.0, end=1.0, text=" Hello ")
            return [segment], info

    monkeypatch.setattr(whisper_service.shutil, "which", lambda name: None)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", types.SimpleNamespace(get_ffmpeg_exe=lambda: r"E:\tools\ffmpeg.exe"))
    monkeypatch.setitem(
        sys.modules,
        "faster_whisper",
        types.SimpleNamespace(WhisperModel=lambda *args, **kwargs: FakeWhisperModel()),
    )
    monkeypatch.setattr(whisper_service, "_model", None)
    monkeypatch.setattr(whisper_service, "_model_name", None)
    monkeypatch.setattr(whisper_service, "_model_dir", None)
    monkeypatch.setattr(whisper_service, "_model_runtime", None)
    monkeypatch.setitem(whisper_service.os.environ, "PATH", r"C:\Windows")

    text, segments, language = whisper_service.transcribe_audio("episode.mp3", model_name="base")

    assert text == "Hello"
    assert language == "en"
    assert r"E:\tools" in whisper_service.os.environ["PATH"]
