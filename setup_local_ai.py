#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
本地 AI 转写组件按需安装器（faster-whisper / WhisperX / torch / torchaudio）。

这些组件约 1-3GB 且与机器强相关（CUDA 轮子只适用于 NVIDIA GPU，macOS 只能用通用轮子），
因此不放在默认依赖里。git clone 后按需加载：

    python setup_local_ai.py          # 自动检测平台与 GPU，选择合适变体
    python setup_local_ai.py --cpu    # 强制 CPU / Apple Silicon 通用版
    python setup_local_ai.py --cuda   # 强制 CUDA 12.8 版（NVIDIA）

组件安装进 backend/.venv（由 uv 管理），仓库目录不落任何文件。
"""
import os
import platform
import shutil
import subprocess
import sys

ROOT = os.path.dirname(os.path.abspath(__file__))
BACKEND = os.path.join(ROOT, "backend")
PYTORCH_CU128_INDEX = "https://download.pytorch.org/whl/cu128"

LOCAL_AI_PKGS = ["faster-whisper>=1.1.0", "whisperx>=3.8.5", "imageio-ffmpeg>=0.6.0"]
CUDA_PKGS = ["torch==2.8.0+cu128", "torchaudio==2.8.0+cu128"]

TERMUX_HINT = """\
检测到 Android/Termux 环境。本项目依赖 MongoDB 与较大体积的 PyTorch，不适合在手机上作宿主机：
推荐部署在 PC / 小主机 / 服务器上，手机通过浏览器访问（项目已内置 Tailscale 公网访问方案）。
如坚持在 Termux 实验：pkg install python python-pip 及社区 torch 包，自行探索，本脚本不自动安装。"""


def is_termux() -> bool:
    return bool(os.environ.get("TERMUX_VERSION")) or "com.termux" in os.environ.get("PREFIX", "")


def has_nvidia_gpu() -> bool:
    if platform.system() == "Darwin":
        return False
    smi = shutil.which("nvidia-smi")
    if not smi:
        return False
    try:
        return subprocess.run([smi], capture_output=True, timeout=10).returncode == 0
    except Exception:
        return False


def total_ram_gb():
    """尽力用标准库探测物理内存，失败返回 None"""
    try:
        if platform.system() == "Windows":
            import ctypes

            class MEMORYSTATUSEX(ctypes.Structure):
                _fields_ = [
                    ("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                    ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                    ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                    ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                    ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                ]

            stat = MEMORYSTATUSEX()
            stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX)
            ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat))
            return round(stat.ullTotalPhys / 1024 ** 3, 1)
        if platform.system() == "Darwin":
            out = subprocess.run(["sysctl", "-n", "hw.memsize"], capture_output=True, text=True, timeout=10)
            return round(int(out.stdout.strip()) / 1024 ** 3, 1)
        page = os.sysconf("SC_PAGE_SIZE")
        count = os.sysconf("SC_PHYS_PAGES")
        return round(page * count / 1024 ** 3, 1)
    except Exception:
        return None


def detect_variant():
    """返回 (variant, 说明)；variant ∈ cuda / cpu / termux"""
    if is_termux():
        return "termux", "Android/Termux"
    system = platform.system()
    if has_nvidia_gpu() and system in ("Windows", "Linux"):
        return "cuda", f"{system} + NVIDIA GPU（CUDA 12.8 轮子，GPU 加速转写）"
    if system == "Darwin":
        chip = "Apple Silicon（MPS 加速）" if platform.machine() == "arm64" else "Intel（CPU）"
        return "cpu", f"macOS · {chip}"
    return "cpu", f"{system or '未知平台'} · CPU 通用版"


def run(cmd):
    print("[执行]", " ".join(cmd), flush=True)
    subprocess.run(cmd, cwd=BACKEND, check=True)


def main():
    force = None
    if "--cpu" in sys.argv:
        force = "cpu"
    elif "--cuda" in sys.argv:
        force = "cuda"

    variant, note = (force, "强制指定") if force else detect_variant()
    print(f"平台检测：{note} → 变体：{variant}\n")

    if variant == "termux":
        print(TERMUX_HINT)
        return 0

    if not shutil.which("uv"):
        print("未找到 uv（本项目用它管理依赖）。安装：https://docs.astral.sh/uv/getting-started/installation/")
        return 1

    ram = total_ram_gb()
    if ram and ram < 8:
        print(f"[警告] 物理内存 {ram}GB，WhisperX 转写建议 ≥ 8GB，长音频可能失败或极慢。\n")

    if variant == "cuda":
        print("预计下载约 3GB（CUDA 轮子较大）。\n")
        # PyPI 为主索引，cu128 作为补充——+cu128 版本号只存在于 PyTorch 官方索引
        run(["uv", "pip", "install", *LOCAL_AI_PKGS, *CUDA_PKGS,
             "--extra-index-url", PYTORCH_CU128_INDEX])
    else:
        print("预计下载约 1-2GB（CPU / 通用轮子）。\n")
        run(["uv", "sync", "--group", "local-ai", "--inexact"])

    print("""
[验证] cd backend && uv run python -c "import whisperx; print('OK')"
[注意] 之后如运行裸 uv sync（不带 --inexact），已安装的可选组件会被移除；
       更新组件请重跑本脚本，或使用 uv sync --group local-ai --inexact。""")
    return 0


if __name__ == "__main__":
    sys.exit(main())
