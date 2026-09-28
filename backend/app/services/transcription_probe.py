"""Offline environment probe. Does not construct a model or download resources."""
import json
import os
from pathlib import Path
import shutil
import sys


def inspect_runtime(options):
    diarize = options["provider"] == "local_whisperx" and os.getenv("WHISPERX_DIARIZE", "0").lower() in {"1", "true", "yes", "on"}
    if diarize and not any(os.getenv(key) for key in ("HF_TOKEN", "HUGGINGFACE_TOKEN", "HUGGINGFACE_HUB_TOKEN")):
        return {"state": "not_configured", "reason_code": "diarization_token_missing", "reason": "说话人识别已开启，但未配置有模型访问权限的 Hugging Face Token。"}
    import ctranslate2
    from faster_whisper.utils import download_model

    device = options.get("WHISPER_DEVICE") or "cpu"
    compute = options.get("WHISPER_COMPUTE_TYPE") or "int8"
    index = int(options.get("WHISPER_DEVICE_INDEX") or 0)
    if device not in {"cpu", "cuda"}:
        return {"state": "unsupported", "reason_code": "device_unsupported", "reason": "此引擎支持 CPU 或 NVIDIA CUDA，请修改 WHISPER_DEVICE。"}
    supported = ctranslate2.get_supported_compute_types(device, index)
    if compute not in supported and compute not in {"default", "auto"}:
        return {"state": "unsupported", "reason_code": "compute_unsupported", "reason": "当前设备不支持配置的计算精度，请检查 WHISPER_COMPUTE_TYPE。"}
    if not shutil.which("ffmpeg"):
        import imageio_ffmpeg
        imageio_ffmpeg.get_ffmpeg_exe()

    model = options.get("WHISPER_MODEL") or "base"
    model_dir = options.get("WHISPER_MODEL_DIR") or None
    try:
        path = Path(model) if Path(model).is_dir() else Path(download_model(
            model, cache_dir=model_dir, local_files_only=True,
        ))
    except (OSError, ValueError):
        return {"state": "model_missing", "reason_code": "model_missing", "reason": "未找到配置的本地模型，请先运行模型准备命令。"}
    if not all((path / name).is_file() and (path / name).stat().st_size > 0
               for name in ("model.bin", "config.json", "tokenizer.json")):
        return {"state": "model_missing", "reason_code": "model_incomplete", "reason": "模型文件不完整，请重新准备模型。"}

    if options["provider"] == "local_whisperx":
        from whisperx.asr import load_model  # noqa: F401 - check native/runtime imports only
        import torch
        vad = os.getenv("WHISPERX_VAD_METHOD", "silero")
        if vad == "silero":
            torch_root = os.getenv("TORCH_HOME") or (str(Path(model_dir) / "torch") if model_dir else None)
            hub = Path(torch_root) / "hub" if torch_root else Path(torch.hub.get_dir())
            if not any(hub.glob("snakers4_silero-vad_*/**/silero_vad.jit")):
                return {"state": "model_missing", "reason_code": "vad_model_missing", "reason": "WhisperX 的 Silero 语音检测模型尚未准备。"}
        elif vad != "pyannote":
            return {"state": "unsupported", "reason_code": "vad_unsupported", "reason": "不支持配置的 WhisperX 语音检测方式。"}
        if diarize:
            from huggingface_hub import try_to_load_from_cache
            cache = str(Path(model_dir) / "pyannote") if model_dir else None
            for repo in (os.getenv("WHISPERX_DIARIZATION_MODEL", "pyannote/speaker-diarization-3.1"), "pyannote/segmentation-3.0"):
                if not isinstance(try_to_load_from_cache(repo, "config.yaml", cache_dir=cache), str):
                    return {"state": "model_missing", "reason_code": "diarization_model_missing", "reason": "说话人识别模型尚未准备，请先配置 Hugging Face 授权并准备模型，或关闭 WHISPERX_DIARIZE。"}
    return {"state": "ready", "reason_code": "local_ready", "reason": "运行库、设备和本地模型检查通过。"}


if __name__ == "__main__":
    try:
        result = inspect_runtime(json.load(sys.stdin))
    except Exception as exc:
        result = {"state": "runtime_error", "reason_code": "runtime_error", "reason": f"运行库或设备检查失败（{type(exc).__name__}），请检查安装和配置。"}
    print(json.dumps(result, ensure_ascii=False))
