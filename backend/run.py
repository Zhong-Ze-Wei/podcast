# -*- coding: utf-8 -*-
"""
Podcast Manager Backend

启动入口 — 自动管理 MongoDB 生命周期
"""
import os
import sys
import glob
import time
import signal
import atexit
import shutil
import subprocess
import socket

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# MongoDB 自动启动（支持 Docker 和本地安装）
# ---------------------------------------------------------------------------

MONGO_CONTAINER_NAME = "podcast-mongodb"

# 标记是否由本脚本启动了 Docker 容器
_mongo_started_by_us = False


def _is_mongo_running(host="localhost", port=27017, timeout=1):
    """通过 TCP 探测 MongoDB 是否在监听"""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (ConnectionRefusedError, OSError):
        return False


def _wait_for_mongo(retries=20, interval=0.5):
    """等待 MongoDB 就绪"""
    for _ in range(retries):
        if _is_mongo_running():
            return True
        time.sleep(interval)
    return False


def _docker_available():
    """检测 docker 命令是否可用"""
    return shutil.which("docker") is not None


def _docker_container_exists(name):
    """检查指定名称的 Docker 容器是否存在（不论状态）"""
    r = subprocess.run(
        ["docker", "inspect", name],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return r.returncode == 0


def _docker_start_existing(name):
    """启动一个已存在但停止的容器"""
    r = subprocess.run(
        ["docker", "start", name],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    return r.returncode == 0


def _docker_run_new(name):
    """创建并运行一个新的 MongoDB 容器，数据持久化到 Docker Volume"""
    r = subprocess.run(
        [
            "docker", "run", "-d",
            "--name", name,
            "-p", "27017:27017",
            "-v", f"{name}-data:/data/db",
            "mongo:latest",
        ],
        stdout=subprocess.DEVNULL, stderr=subprocess.PIPE,
    )
    if r.returncode != 0:
        err = r.stderr.decode(errors="ignore").strip()
        print(f"[MongoDB] Docker 启动失败: {err}")
    return r.returncode == 0


def ensure_mongo():
    """确保 MongoDB 正在运行；优先使用 Docker"""
    global _mongo_started_by_us

    # 1. 已经在运行
    if _is_mongo_running():
        print("[MongoDB] 已在运行")
        return

    # 2. 尝试 Docker
    if _docker_available():
        if _docker_container_exists(MONGO_CONTAINER_NAME):
            print(f"[MongoDB] 正在启动 Docker 容器 '{MONGO_CONTAINER_NAME}' ...")
            _docker_start_existing(MONGO_CONTAINER_NAME)
        else:
            print(f"[MongoDB] 正在创建 Docker 容器 '{MONGO_CONTAINER_NAME}' ...")
            _docker_run_new(MONGO_CONTAINER_NAME)

        if _wait_for_mongo():
            _mongo_started_by_us = True
            print("[MongoDB] Docker 启动成功")
            return
        else:
            print("[MongoDB] Docker 容器启动超时")
            sys.exit(1)

    # 3. 没有 Docker，也没有本地 mongod
    print("[MongoDB] 未检测到 Docker 或本地 mongod")
    print("  请安装 Docker Desktop 或 MongoDB Community Edition")
    print("  Docker: https://www.docker.com/products/docker-desktop")
    print("  MongoDB: https://www.mongodb.com/try/download/community")
    sys.exit(1)


def _stop_mongo():
    """停止由本脚本启动的 Docker 容器"""
    global _mongo_started_by_us
    if not _mongo_started_by_us:
        return
    print("\n[MongoDB] 正在停止 Docker 容器 ...")
    subprocess.run(
        ["docker", "stop", MONGO_CONTAINER_NAME],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )
    print("[MongoDB] 已停止")
    _mongo_started_by_us = False


# ---------------------------------------------------------------------------
# Flask 应用启动
# ---------------------------------------------------------------------------

# 标记是否已经执行过清理
_cleanup_done = False


def cleanup():
    """清理资源"""
    global _cleanup_done
    if _cleanup_done:
        return
    _cleanup_done = True

    print("\nShutting down task queue...")
    try:
        from app.services.task_queue import task_queue
        task_queue.shutdown(wait=False)
        print("Task queue shutdown complete.")
    except Exception:
        pass

    # 关闭由本脚本启动的 MongoDB
    _stop_mongo()


def signal_handler(signum, frame):
    """信号处理器"""
    cleanup()
    sys.exit(0)


def main():
    """主函数"""
    # 注册清理函数
    atexit.register(cleanup)

    # Windows 上只有 SIGINT 和 SIGTERM
    signal.signal(signal.SIGINT, signal_handler)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, signal_handler)

    # ① 先确保 MongoDB 在运行
    ensure_mongo()

    # ② 再创建 Flask 应用
    from app import create_app
    from app.services.task_queue import task_queue
    app = create_app()

    # 获取配置
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"

    print(f"\nStarting Podcast Manager Backend...")
    print(f"Server: http://{host}:{port}")
    print(f"Debug: {debug}")

    try:
        is_windows = sys.platform == 'win32'
        app.run(
            host=host,
            port=port,
            debug=debug,
            use_reloader=not is_windows if debug else False
        )
    except (OSError, SystemExit):
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()
