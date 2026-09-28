# -*- coding: utf-8 -*-
"""
Whisper转录服务

使用Faster-Whisper进行本地AI转录
"""
import logging
import os
import shutil
from typing import Optional, List, Dict, Tuple, Callable

logger = logging.getLogger(__name__)

# 全局模型实例（延迟加载）
_model = None
_model_name = None
_model_dir = None
_model_runtime = None


def _parse_int_env(name: str, default: int) -> int:
    value = os.getenv(name, str(default)).strip()
    try:
        return int(value)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer, got {value!r}") from exc


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


def get_model(model_name: str = "small"):
    """
    获取或加载Whisper模型

    Args:
        model_name: 模型名称 (tiny, base, small, medium, large-v3, turbo)

    Returns:
        WhisperModel实例
    """
    global _model, _model_name, _model_dir, _model_runtime

    model_dir = os.getenv("WHISPER_MODEL_DIR", "").strip()
    device = os.getenv("WHISPER_DEVICE", "cpu").strip() or "cpu"
    compute_type = os.getenv("WHISPER_COMPUTE_TYPE", "int8").strip() or "int8"
    device_index = _parse_int_env("WHISPER_DEVICE_INDEX", 0)
    num_workers = _parse_int_env("WHISPER_NUM_WORKERS", 1)
    runtime = (device, compute_type, device_index, num_workers)

    if (
        _model is not None
        and _model_name == model_name
        and _model_dir == model_dir
        and _model_runtime == runtime
    ):
        return _model

    try:
        from faster_whisper import WhisperModel

        logger.info(
            "Loading Whisper model: %s (device=%s, compute_type=%s, device_index=%s)",
            model_name,
            device,
            compute_type,
            device_index,
        )
        model_options = {
            "local_files_only": True,
            "device": device,
            "compute_type": compute_type,
            "device_index": device_index,
            "num_workers": num_workers,
        }
        if model_dir:
            os.makedirs(model_dir, exist_ok=True)
            model_options["download_root"] = model_dir

        _model = WhisperModel(model_name, **model_options)
        _model_name = model_name
        _model_dir = model_dir
        _model_runtime = runtime
        logger.info(f"Whisper model {model_name} loaded successfully")
        return _model

    except ImportError:
        logger.error("faster-whisper not installed. Run: pip install faster-whisper")
        raise RuntimeError("faster-whisper not installed")
    except Exception as e:
        logger.exception(f"Failed to load Whisper model: {e}")
        raise


def transcribe_audio(
    audio_path: str,
    model_name: str = "small",
    language: Optional[str] = None,
    progress_callback: Optional[Callable[[int], None]] = None
) -> Tuple[str, List[Dict], str]:
    """
    转录音频文件

    Args:
        audio_path: 音频文件路径
        model_name: 模型名称
        language: 指定语言（None为自动检测）
        progress_callback: 进度回调函数

    Returns:
        (full_text, segments, detected_language)
    """
    if progress_callback:
        progress_callback(10)

    _ensure_ffmpeg_available()

    model = get_model(model_name)

    if progress_callback:
        progress_callback(20)

    logger.info(f"Transcribing: {audio_path}")

    # 转录参数
    transcribe_options = {
        "beam_size": 5,
        "vad_filter": True,  # 启用VAD过滤，跳过静音
        "vad_parameters": {
            "threshold": 0.5,
            "min_speech_duration_ms": 250,
            "min_silence_duration_ms": 1000
        }
    }

    if language:
        transcribe_options["language"] = language

    # 执行转录
    segments_iter, info = model.transcribe(audio_path, **transcribe_options)

    detected_language = info.language
    logger.info(f"Detected language: {detected_language} (prob: {info.language_probability:.2f})")

    # 收集分段
    segments = []
    full_text_parts = []
    total_duration = info.duration

    if progress_callback:
        progress_callback(30)

    for seg in segments_iter:
        # 格式化时间戳
        start_time = format_timestamp(seg.start)
        end_time = format_timestamp(seg.end)

        segment_data = {
            "start": seg.start,
            "end": seg.end,
            "time": f"{start_time}",
            "text": seg.text.strip()
        }
        segments.append(segment_data)
        full_text_parts.append(seg.text.strip())

        # 更新进度（30% - 90%）
        if progress_callback and total_duration > 0:
            progress = 30 + int((seg.end / total_duration) * 60)
            progress_callback(min(progress, 90))

    full_text = " ".join(full_text_parts)

    if progress_callback:
        progress_callback(95)

    logger.info(f"Transcription complete: {len(full_text)} chars, {len(segments)} segments")

    return full_text, segments, detected_language


def format_timestamp(seconds: float) -> str:
    """格式化时间戳为 MM:SS 或 HH:MM:SS"""
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)

    if hours > 0:
        return f"{hours}:{minutes:02d}:{secs:02d}"
    return f"{minutes:02d}:{secs:02d}"
