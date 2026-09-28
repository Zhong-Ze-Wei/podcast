"""Read-only capability discovery shared by the UI and transcription tasks."""
from importlib.metadata import PackageNotFoundError, version
import json
import os
from pathlib import Path
import subprocess
import sys


LOCAL_PROVIDERS = {
    "local_whisper": ("faster-whisper", "local-whisper", "本地 Whisper"),
    "local_whisperx": ("whisperx", "local-whisperx", "WhisperX"),
}


class TranscriptionUnavailable(RuntimeError):
    pass


def package_installed(name):
    try:
        version(name)
        return True
    except PackageNotFoundError:
        return False


def probe_local(provider, config):
    """Native library failures stay in a bounded, offline subprocess."""
    options = {key: config.get(key) for key in (
        "WHISPER_MODEL", "WHISPER_MODEL_DIR", "WHISPER_DEVICE",
        "WHISPER_COMPUTE_TYPE", "WHISPER_DEVICE_INDEX",
    )}
    options["provider"] = provider
    env = dict(os.environ, HF_HUB_OFFLINE="1", TRANSFORMERS_OFFLINE="1")
    try:
        result = subprocess.run(
            [sys.executable, str(Path(__file__).with_name("transcription_probe.py"))],
            input=json.dumps(options), capture_output=True, text=True, timeout=20, env=env,
        )
        if result.returncode != 0:
            return {"state": "runtime_error", "reason_code": "runtime_error", "reason": "转录运行库检查失败，请检查安装版本和设备配置。"}
        return json.loads(result.stdout.strip().splitlines()[-1])
    except (subprocess.TimeoutExpired, OSError, ValueError, IndexError):
        return {"state": "runtime_error", "reason_code": "probe_failed", "reason": "转录运行库检查失败或超时，请检查环境后重试。"}


def _capability(provider, label, state, reason, **extra):
    return {"id": provider, "label": label, "state": state,
            "available": state == "ready", "reason": reason, **extra}


def get_provider_capability(provider, config):
    if provider == "official":
        return _capability(provider, "官方字幕", "ready", "可读取节目源提供的字幕；是否有字幕取决于具体单集。", reason_code="official_ready")
    if provider in LOCAL_PROVIDERS:
        package, extra, label = LOCAL_PROVIDERS[provider]
        setup = {"install_command": f"uv sync --extra {extra}",
                 "prepare_command": f"uv run --extra {extra} python scripts/prepare_transcription.py --provider {provider}"}
        if not package_installed(package):
            return _capability(provider, label, "not_installed", "未安装本地转录引擎。", reason_code="engine_missing", **setup)
        if not config.get("TRANSCRIPTION_LOCAL_ENABLED", False):
            return _capability(provider, label, "disabled", "引擎已安装；准备模型后设置 TRANSCRIPTION_LOCAL_ENABLED=1 并重启后端。", reason_code="local_disabled", **setup)
        result = probe_local(provider, config)
        return _capability(provider, label, result["state"], result["reason"], reason_code=result.get("reason_code", result["state"]), **setup)
    if provider == "assemblyai":
        setup = {"install_command": "uv sync --extra cloud-transcription"}
        if not config.get("TRANSCRIPTION_CLOUD_ENABLED", False):
            return _capability(provider, "AssemblyAI 云端", "disabled", "云转录未启用；启用后会上传音频并产生服务费用。", reason_code="cloud_disabled", **setup)
        if not package_installed("assemblyai"):
            return _capability(provider, "AssemblyAI 云端", "not_installed", "未安装云转录扩展。", reason_code="cloud_missing", **setup)
        if not config.get("ASSEMBLYAI_API_KEY"):
            return _capability(provider, "AssemblyAI 云端", "not_configured", "尚未配置 ASSEMBLYAI_API_KEY。", reason_code="cloud_key_missing", **setup)
        return _capability(provider, "AssemblyAI 云端", "ready", "已配置云转录；连接与密钥将在提交时验证。", reason_code="cloud_ready", **setup)
    return _capability(provider, "手动导入", "unsupported", "当前版本尚不支持此转录方式。", reason_code="unsupported")


def get_capabilities(config):
    providers = ("official", *LOCAL_PROVIDERS, "assemblyai", "manual")
    return {"transcription": {p: get_provider_capability(p, config) for p in providers}}


def ensure_transcription_available(provider, config):
    capability = get_provider_capability(provider, config)
    if not capability["available"]:
        raise TranscriptionUnavailable(capability["reason"])
