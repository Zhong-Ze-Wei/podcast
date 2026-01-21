# -*- coding: utf-8 -*-
"""
Podcast Manager Backend

启动入口
"""
import os
import sys

# 添加项目路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app import create_app
from app.services.task_queue import task_queue

app = create_app()


def main():
    """主函数"""
    # 获取配置
    host = os.environ.get("FLASK_HOST", "0.0.0.0")
    port = int(os.environ.get("FLASK_PORT", 5000))
    debug = os.environ.get("FLASK_DEBUG", "true").lower() == "true"

    print(f"Starting Podcast Manager Backend...")
    print(f"Server: http://{host}:{port}")
    print(f"Debug: {debug}")

    try:
        app.run(host=host, port=port, debug=debug)
    finally:
        # 关闭任务队列
        print("Shutting down task queue...")
        task_queue.shutdown(wait=True)


if __name__ == "__main__":
    main()
