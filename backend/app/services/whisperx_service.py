# -*- coding: utf-8 -*-
"""
WhisperX transcription service.

This is an optional advanced local backend. Basic WhisperX transcription works
without diarization; speaker diarization is intentionally not enabled by
default because it needs Hugging Face model access.
"""
import os
import shutil
from collections.abc import Iterable
from typing import Optional, List, Dict, Tuple, Callable


_model = None
_model_runtime = None


def is_available() -> bool:
    try:
        import whisperx  # noqa: F401
        return True
    except ImportError:
        return False


def _parse_int_env(name: str, default: int) -> int:
    value = os.getenv(name, str(default)).strip()
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {value!r}") from exc


def _parse_optional_int_env(name: str) -> Optional[int]:
    value = os.getenv(name, "").strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer when set, got {value!r}") from exc


def _parse_bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _ensure_ffmpeg_available() -> None:
    if shutil.which("ffmpeg"):
        return

    try:
        import imageio_ffmpeg

        ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    except Exception as exc:
        raise RuntimeError(
            "FFmpeg is required for local transcription but was not found in PATH. "
            "Install FFmpeg and restart the backend, or use official/cloud transcription."
        ) from exc

    executable_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    if os.path.basename(ffmpeg_exe).lower() != executable_name:
        backend_dir = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
        ffmpeg_dir = os.path.join(backend_dir, ".runtime", "ffmpeg")
        os.makedirs(ffmpeg_dir, exist_ok=True)
        shim_path = os.path.join(ffmpeg_dir, executable_name)
        if not os.path.exists(shim_path):
            shutil.copy2(ffmpeg_exe, shim_path)
        ffmpeg_exe = shim_path

    ffmpeg_dir = os.path.dirname(ffmpeg_exe)
    current_path = os.environ.get("PATH", "")
    if ffmpeg_dir and ffmpeg_dir not in current_path.split(os.pathsep):
        os.environ["PATH"] = ffmpeg_dir + os.pathsep + current_path


def _runtime_options(model_name: str):
    model_dir = os.getenv("WHISPER_MODEL_DIR", "").strip()
    device = os.getenv("WHISPER_DEVICE", "cpu").strip() or "cpu"
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8").strip() or "int8"
    device_index = _parse_int_env("WHISPER_DEVICE_INDEX", 0)
    num_workers = _parse_int_env("WHISPER_NUM_WORKERS", 1)
    batch_size = _parse_int_env("WHISPERX_BATCH_SIZE", 16)
    vad_method = os.getenv("WHISPERX_VAD_METHOD", "silero").strip() or "silero"
    diarize = _parse_bool_env("WHISPERX_DIARIZE", False)
    diarization_model = os.getenv(
        "WHISPERX_DIARIZATION_MODEL",
        "pyannote/speaker-diarization-3.1",
    ).strip()
    min_speakers = _parse_optional_int_env("WHISPERX_MIN_SPEAKERS")
    max_speakers = _parse_optional_int_env("WHISPERX_MAX_SPEAKERS")
    return {
        "model_name": model_name,
        "model_dir": model_dir,
        "device": device,
        "compute_type": compute_type,
        "device_index": device_index,
        "num_workers": num_workers,
        "batch_size": batch_size,
        "vad_method": vad_method,
        "diarize": diarize,
        "diarization_model": diarization_model,
        "min_speakers": min_speakers,
        "max_speakers": max_speakers,
    }


def get_model(model_name: str = "base"):
    global _model, _model_runtime

    options = _runtime_options(model_name)
    runtime = (
        options["model_name"],
        options["model_dir"],
        options["device"],
        options["compute_type"],
        options["device_index"],
        options["num_workers"],
    )
    if _model is not None and _model_runtime == runtime:
        return _model

    try:
        import whisperx
    except ImportError as exc:
        raise RuntimeError(
            "WhisperX runtime is not installed. Keep using faster-whisper, or install and configure WhisperX as the advanced local transcription backend."
        ) from exc

    load_kwargs = {
        "local_files_only": True,
        "compute_type": options["compute_type"],
        "device_index": options["device_index"],
        "threads": options["num_workers"],
        "vad_method": options["vad_method"],
    }
    if options["model_dir"]:
        os.makedirs(options["model_dir"], exist_ok=True)
        if not os.getenv("TORCH_HOME"):
            os.environ["TORCH_HOME"] = os.path.join(options["model_dir"], "torch")
        load_kwargs["download_root"] = options["model_dir"]

    _model = whisperx.load_model(options["model_name"], options["device"], **load_kwargs)
    # Override the hardcoded _num_workers=1 in FasterWhisperPipeline.__init__.
    # On Windows (spawn start method), DataLoader workers require pickling the dataset.
    # The dataset wraps a generator, which cannot be pickled → "cannot pickle 'generator' object".
    # Forcing 0 makes DataLoader run in the main thread with no pickling.
    _model._num_workers = 0
    _model_runtime = runtime
    return _model


def transcribe_audio(
    audio_path: str,
    model_name: str = "base",
    language: Optional[str] = None,
    progress_callback: Optional[Callable[[int], None]] = None,
) -> Tuple[str, List[Dict], str]:
    if progress_callback:
        progress_callback(10)

    _ensure_ffmpeg_available()

    options = _runtime_options(model_name)
    model = get_model(model_name)

    if progress_callback:
        progress_callback(25)

    transcribe_kwargs = {
        "batch_size": options["batch_size"],
        # num_workers controls PyTorch DataLoader worker processes.
        # On Windows, torch uses 'spawn' (not fork), which pickles the audio
        # pipeline — and the pipeline contains generator objects that cannot
        # be pickled.  Keep this at 0 so loading runs in the main thread.
        "num_workers": 0,
    }
    if language:
        transcribe_kwargs["language"] = language

    result = model.transcribe(audio_path, **transcribe_kwargs)

    if options["diarize"]:
        if progress_callback:
            progress_callback(82)
        result = _apply_diarization(audio_path, result, options)

    if progress_callback:
        progress_callback(90 if options["diarize"] else 80)

    raw_segments = result.get("segments", []) if isinstance(result, dict) else getattr(result, "segments", [])
    segments = [_normalize_segment(segment) for segment in raw_segments if segment and segment.get("text")]
    full_text = " ".join(segment["text"] for segment in segments).strip()
    detected_language = (
        result.get("language")
        if isinstance(result, dict)
        else getattr(result, "language", None)
    ) or language or ""

    if progress_callback:
        progress_callback(95)

    return full_text, segments, detected_language


def _apply_diarization(audio_path: str, result: dict, options: dict) -> dict:
    token = (
        os.getenv("HF_TOKEN")
        or os.getenv("HUGGINGFACE_TOKEN")
        or os.getenv("HUGGINGFACE_HUB_TOKEN")
    )
    if not token:
        raise RuntimeError("WHISPERX_DIARIZE=1 requires HF_TOKEN with access to the configured pyannote diarization model.")

    from whisperx.diarize import DiarizationPipeline, assign_word_speakers

    device = options["device"]
    if device == "cuda":
        device = f"cuda:{options['device_index']}"

    cache_dir = os.path.join(options["model_dir"], "pyannote") if options["model_dir"] else None
    if cache_dir:
        os.makedirs(cache_dir, exist_ok=True)

    try:
        diarize_model = DiarizationPipeline(
            model_name=options["diarization_model"],
            token=token,
            device=device,
            cache_dir=cache_dir,
        )
        diarize_segments = diarize_model(
            audio_path,
            min_speakers=options["min_speakers"],
            max_speakers=options["max_speakers"],
        )
    except Exception as exc:
        raise RuntimeError(
            "WhisperX diarization failed. Make sure your Hugging Face account has accepted access to both "
            "pyannote/speaker-diarization-3.1 and pyannote/segmentation-3.0, and that HF_TOKEN is valid."
        ) from exc
    return assign_word_speakers(diarize_segments, result, fill_nearest=True)


def _normalize_segment(segment: Dict) -> Dict:
    start = float(segment.get("start", 0) or 0)
    normalized = {
        "start": start,
        "end": float(segment.get("end", 0) or 0),
        "time": _format_timestamp(start),
        "text": str(segment.get("text", "")).strip(),
    }
    if segment.get("speaker"):
        normalized["speaker"] = segment["speaker"]
    if segment.get("words"):
        normalized_words = _normalize_words(segment["words"])
        if normalized_words:
            normalized["words"] = normalized_words
    return normalized


def _normalize_words(words) -> List[Dict]:
    if isinstance(words, dict):
        words = [words]
    elif isinstance(words, (str, bytes)) or not isinstance(words, Iterable):
        return []

    normalized = []
    for word in words:
        if not isinstance(word, dict):
            continue

        item = {}
        for key in ("start", "end", "score"):
            if word.get(key) is not None:
                try:
                    item[key] = float(word[key])
                except (TypeError, ValueError):
                    pass

        token = word.get("word") or word.get("text")
        if token is not None:
            item["word"] = str(token)

        if word.get("speaker"):
            item["speaker"] = str(word["speaker"])

        if item:
            normalized.append(item)

    return normalized


def _format_timestamp(seconds: float) -> str:
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
