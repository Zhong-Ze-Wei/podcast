import sys
import types
from collections.abc import Generator

import pytest

from app.services import whisperx_service


def reset_whisperx_cache(monkeypatch):
    monkeypatch.setattr(whisperx_service, "_model", None)
    monkeypatch.setattr(whisperx_service, "_model_runtime", None)


def test_is_available_returns_true_when_whisperx_imports(monkeypatch):
    monkeypatch.setitem(sys.modules, "whisperx", types.SimpleNamespace())

    assert whisperx_service.is_available() is True


def test_transcribe_audio_uses_configured_runtime_and_returns_segments(monkeypatch, tmp_path):
    reset_whisperx_cache(monkeypatch)
    captured = {}

    class FakeModel:
        def transcribe(self, audio_path, **kwargs):
            captured["audio_path"] = audio_path
            captured["transcribe_kwargs"] = kwargs
            return {
                "language": "en",
                "segments": [
                    {"start": 0.0, "end": 1.5, "text": " Hello world "},
                    {"start": 1.5, "end": 3.0, "speaker": "SPEAKER_00", "text": " Second line."},
                ],
            }

    def fake_load_model(model_name, device, **kwargs):
        captured["model_name"] = model_name
        captured["device"] = device
        captured["load_kwargs"] = kwargs
        return FakeModel()

    fake_whisperx = types.SimpleNamespace(load_model=fake_load_model)
    monkeypatch.setitem(sys.modules, "whisperx", fake_whisperx)
    monkeypatch.setenv("WHISPER_MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("WHISPER_DEVICE", "cuda")
    monkeypatch.setenv("WHISPER_COMPUTE_TYPE", "float16")
    monkeypatch.setenv("WHISPER_DEVICE_INDEX", "0")
    monkeypatch.setenv("WHISPER_NUM_WORKERS", "2")
    monkeypatch.setenv("WHISPERX_DIARIZE", "0")
    monkeypatch.delenv("TORCH_HOME", raising=False)
    monkeypatch.setattr(whisperx_service.shutil, "which", lambda name: "ffmpeg")

    text, segments, language = whisperx_service.transcribe_audio("episode.mp3", model_name="base")

    assert captured["model_name"] == "base"
    assert captured["device"] == "cuda"
    assert captured["load_kwargs"]["compute_type"] == "float16"
    assert captured["load_kwargs"]["download_root"] == str(tmp_path)
    assert captured["load_kwargs"]["vad_method"] == "silero"
    assert "TORCH_HOME" in __import__("os").environ
    assert captured["transcribe_kwargs"]["batch_size"] == 16
    assert text == "Hello world Second line."
    assert language == "en"
    assert segments == [
        {"start": 0.0, "end": 1.5, "time": "00:00", "text": "Hello world"},
        {"start": 1.5, "end": 3.0, "time": "00:01", "speaker": "SPEAKER_00", "text": "Second line."},
    ]


def test_transcribe_audio_runs_diarization_when_enabled(monkeypatch, tmp_path):
    reset_whisperx_cache(monkeypatch)
    captured = {}

    class FakeModel:
        def transcribe(self, audio_path, **kwargs):
            return {
                "language": "en",
                "segments": [{"start": 0.0, "end": 1.0, "text": "Hello speaker."}],
            }

    class FakeDiarizationPipeline:
        def __init__(self, **kwargs):
            captured["diarization_init"] = kwargs

        def __call__(self, audio_path, **kwargs):
            captured["diarization_audio_path"] = audio_path
            captured["diarization_call"] = kwargs
            return "diarization-dataframe"

    def fake_assign_word_speakers(diarize_df, result, fill_nearest=False):
        captured["assign"] = {
            "diarize_df": diarize_df,
            "fill_nearest": fill_nearest,
        }
        result["segments"][0]["speaker"] = "SPEAKER_00"
        return result

    fake_whisperx = types.SimpleNamespace(load_model=lambda *args, **kwargs: FakeModel())
    fake_diarize = types.SimpleNamespace(
        DiarizationPipeline=FakeDiarizationPipeline,
        assign_word_speakers=fake_assign_word_speakers,
    )
    monkeypatch.setitem(sys.modules, "whisperx", fake_whisperx)
    monkeypatch.setitem(sys.modules, "whisperx.diarize", fake_diarize)
    monkeypatch.setenv("WHISPER_MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("WHISPER_DEVICE", "cuda")
    monkeypatch.setenv("WHISPER_DEVICE_INDEX", "0")
    monkeypatch.setenv("WHISPERX_DIARIZE", "1")
    monkeypatch.setenv("WHISPERX_DIARIZATION_MODEL", "pyannote/speaker-diarization-3.1")
    monkeypatch.setenv("HF_TOKEN", "hf_test")
    monkeypatch.setenv("WHISPERX_MIN_SPEAKERS", "")
    monkeypatch.setenv("WHISPERX_MAX_SPEAKERS", "")
    monkeypatch.setattr(whisperx_service.shutil, "which", lambda name: "ffmpeg")

    text, segments, language = whisperx_service.transcribe_audio("episode.mp3", model_name="base")

    assert text == "Hello speaker."
    assert language == "en"
    assert segments[0]["speaker"] == "SPEAKER_00"
    assert captured["diarization_init"]["model_name"] == "pyannote/speaker-diarization-3.1"
    assert captured["diarization_init"]["token"] == "hf_test"
    assert captured["diarization_init"]["device"] == "cuda:0"
    assert captured["diarization_call"]["min_speakers"] is None
    assert captured["diarization_call"]["max_speakers"] is None
    assert captured["assign"]["fill_nearest"] is True


def test_transcribe_audio_requires_token_when_diarization_enabled(monkeypatch, tmp_path):
    reset_whisperx_cache(monkeypatch)

    class FakeModel:
        def transcribe(self, audio_path, **kwargs):
            return {"language": "en", "segments": [{"start": 0, "end": 1, "text": "Hello"}]}

    monkeypatch.setitem(sys.modules, "whisperx", types.SimpleNamespace(load_model=lambda *args, **kwargs: FakeModel()))
    monkeypatch.setenv("WHISPER_MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("WHISPERX_DIARIZE", "1")
    monkeypatch.delenv("HF_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_TOKEN", raising=False)
    monkeypatch.delenv("HUGGINGFACE_HUB_TOKEN", raising=False)
    monkeypatch.setattr(whisperx_service.shutil, "which", lambda name: "ffmpeg")

    try:
        whisperx_service.transcribe_audio("episode.mp3", model_name="base")
    except RuntimeError as exc:
        assert "HF_TOKEN" in str(exc)
    else:
        raise AssertionError("Expected missing HF_TOKEN to fail clearly")


def test_transcribe_audio_fails_clearly_when_ffmpeg_missing(monkeypatch):
    reset_whisperx_cache(monkeypatch)
    monkeypatch.setattr(whisperx_service.shutil, "which", lambda name: None)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", types.SimpleNamespace(get_ffmpeg_exe=lambda: (_ for _ in ()).throw(RuntimeError("missing"))))

    with pytest.raises(RuntimeError) as exc_info:
        whisperx_service.transcribe_audio("episode.mp3", model_name="base")

    assert "FFmpeg is required for local transcription" in str(exc_info.value)


def test_transcribe_audio_uses_imageio_ffmpeg_fallback(monkeypatch):
    reset_whisperx_cache(monkeypatch)

    class FakeModel:
        def transcribe(self, audio_path, **kwargs):
            return {"language": "en", "segments": [{"start": 0, "end": 1, "text": "Hello"}]}

    monkeypatch.setattr(whisperx_service.shutil, "which", lambda name: None)
    monkeypatch.setitem(sys.modules, "imageio_ffmpeg", types.SimpleNamespace(get_ffmpeg_exe=lambda: r"E:\tools\ffmpeg.exe"))
    monkeypatch.setitem(sys.modules, "whisperx", types.SimpleNamespace(load_model=lambda *args, **kwargs: FakeModel()))
    monkeypatch.setattr(whisperx_service.os, "pathsep", ";")
    monkeypatch.setenv("WHISPERX_DIARIZE", "0")
    monkeypatch.setitem(whisperx_service.os.environ, "PATH", r"C:\Windows")
    text, segments, language = whisperx_service.transcribe_audio("episode.mp3", model_name="base")

    assert text == "Hello"
    assert language == "en"
    assert r"E:\tools" in whisperx_service.os.environ["PATH"]


def test_transcribe_audio_normalizes_generator_words(monkeypatch, tmp_path):
    reset_whisperx_cache(monkeypatch)

    def word_generator():
        yield {"start": 0.0, "end": 0.3, "word": "Hello", "score": 0.9}

    class FakeModel:
        def transcribe(self, audio_path, **kwargs):
            return {
                "language": "en",
                "segments": [
                    {
                        "start": 0.0,
                        "end": 1.0,
                        "text": "Hello",
                        "speaker": "SPEAKER_00",
                        "words": word_generator(),
                    }
                ],
            }

    monkeypatch.setitem(sys.modules, "whisperx", types.SimpleNamespace(load_model=lambda *args, **kwargs: FakeModel()))
    monkeypatch.setenv("WHISPER_MODEL_DIR", str(tmp_path))
    monkeypatch.setenv("WHISPERX_DIARIZE", "0")
    monkeypatch.setattr(whisperx_service.shutil, "which", lambda name: "ffmpeg")

    _, segments, _ = whisperx_service.transcribe_audio("episode.mp3", model_name="base")

    assert not isinstance(segments[0]["words"], Generator)
    assert segments[0]["words"] == [{"start": 0.0, "end": 0.3, "word": "Hello", "score": 0.9}]
