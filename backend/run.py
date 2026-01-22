# -*- coding: utf-8 -*-
"""
Podcast Manager Backend

启动入口
"""
import os
import sys
import signal
import atexit

# 加载环境变量
from dotenv import load_dotenv
load_dotenv()

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.services.task_queue import task_queue

app = create_app()

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
        task_queue.shutdown(wait=False)
        print("Task queue shutdown complete.")
    except Exception as e:
        # 忽略清理过程中的错误
        pass


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

    # 获取配置
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"

    print(f"Starting Podcast Manager Backend...")
    print(f"Server: http://{host}:{port}")
    print(f"Debug: {debug}")

    try:
        # Windows 上 debug 模式的 reloader 会导致退出问题
        # 使用 use_reloader=False 可以避免，但保留 debug 的其他功能
        is_windows = sys.platform == 'win32'
        app.run(
            host=host,
            port=port,
            debug=debug,
            use_reloader=not is_windows if debug else False
        )
    except (OSError, SystemExit):
        # Windows 上的套接字错误或正常退出
        pass
    finally:
        cleanup()


if __name__ == "__main__":
    main()
