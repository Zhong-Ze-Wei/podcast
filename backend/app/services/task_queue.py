# -*- coding: utf-8 -*-
"""
异步任务队列服务

使用 ThreadPoolExecutor 实现轻量级异步任务队列
MVP阶段使用内存存储，后续可替换为 Redis + Celery
"""
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from typing import Callable, Any, Optional
import uuid
import logging

logger = logging.getLogger(__name__)


class TaskQueue:
    """异步任务队列管理器"""

    def __init__(self, max_workers: int = 3):
        self.executor = ThreadPoolExecutor(max_workers=max_workers)
        self.tasks = {}  # 内存存储，task_id -> task_info
        self._db = None

    def set_db(self, db):
        """设置数据库连接 (用于持久化任务状态)"""
        self._db = db

    def submit(
        self,
        task_type: str,
        func: Callable,
        episode_id: str = None,
        feed_id: str = None,
        *args,
        **kwargs
    ) -> str:
        """
        提交异步任务

        Args:
            task_type: 任务类型 (download, transcribe, summarize, refresh)
            func: 要执行的函数
            episode_id: 关联的episode ID
            feed_id: 关联的feed ID
            *args, **kwargs: 传递给func的参数

        Returns:
            task_id: 任务ID
        """
        task_id = str(uuid.uuid4())
        now = datetime.utcnow()

        # 创建任务记录
        task_info = {
            "task_id": task_id,
            "task_type": task_type,
            "episode_id": episode_id,
            "feed_id": feed_id,
            "status": "pending",
            "progress": 0,
            "result": None,
            "error_message": None,
            "created_at": now,
            "started_at": None,
            "completed_at": None
        }

        self.tasks[task_id] = task_info

        # 持久化到数据库
        if self._db:
            self._db.tasks.insert_one(task_info.copy())

        # 包装函数以更新状态
        def wrapper():
            self._update_status(task_id, "processing", started_at=datetime.utcnow())
            try:
                # 执行任务，传入 progress_callback
                result = func(
                    *args,
                    progress_callback=lambda p: self._update_progress(task_id, p),
                    **kwargs
                )
                self._update_status(
                    task_id,
                    "completed",
                    progress=100,
                    result=result,
                    completed_at=datetime.utcnow()
                )
                return result
            except Exception as e:
                logger.exception(f"Task {task_id} failed: {e}")
                self._update_status(
                    task_id,
                    "failed",
                    error_message=str(e),
                    completed_at=datetime.utcnow()
                )
                raise

        # 提交到线程池
        self.executor.submit(wrapper)

        logger.info(f"Task submitted: {task_id} ({task_type})")
        return task_id

    def _update_status(self, task_id: str, status: str, **kwargs):
        """更新任务状态"""
        if task_id in self.tasks:
            self.tasks[task_id]["status"] = status
            for key, value in kwargs.items():
                self.tasks[task_id][key] = value

        # 同步到数据库
        if self._db:
            update_doc = {"status": status, **kwargs}
            self._db.tasks.update_one(
                {"task_id": task_id},
                {"$set": update_doc}
            )

    def _update_progress(self, task_id: str, progress: int):
        """更新任务进度"""
        if task_id in self.tasks:
            self.tasks[task_id]["progress"] = progress

        # 同步到数据库 (进度更新不太频繁，可以每次都写)
        if self._db:
            self._db.tasks.update_one(
                {"task_id": task_id},
                {"$set": {"progress": progress}}
            )

    def get_status(self, task_id: str) -> Optional[dict]:
        """获取任务状态"""
        # 先从内存获取
        if task_id in self.tasks:
            return self.tasks[task_id].copy()

        # 从数据库获取
        if self._db:
            task = self._db.tasks.find_one({"task_id": task_id})
            if task:
                # 转换ObjectId等
                task["_id"] = str(task["_id"]) if task.get("_id") else None
                if task.get("episode_id"):
                    task["episode_id"] = str(task["episode_id"])
                if task.get("feed_id"):
                    task["feed_id"] = str(task["feed_id"])
                return task

        return None

    def get_all_tasks(
        self,
        status: str = None,
        task_type: str = None,
        limit: int = 50
    ) -> list:
        """获取任务列表"""
        if self._db:
            query = {}
            if status:
                query["status"] = status
            if task_type:
                query["task_type"] = task_type

            tasks = list(
                self._db.tasks.find(query)
                .sort("created_at", -1)
                .limit(limit)
            )

            # 转换格式
            for task in tasks:
                task["_id"] = str(task["_id"]) if task.get("_id") else None
                if task.get("episode_id"):
                    task["episode_id"] = str(task["episode_id"])
                if task.get("feed_id"):
                    task["feed_id"] = str(task["feed_id"])

            return tasks

        # 从内存获取
        result = list(self.tasks.values())
        if status:
            result = [t for t in result if t["status"] == status]
        if task_type:
            result = [t for t in result if t["task_type"] == task_type]
        return sorted(result, key=lambda x: x["created_at"], reverse=True)[:limit]

    def cancel(self, task_id: str) -> bool:
        """取消任务 (仅能取消pending状态的任务)"""
        task = self.get_status(task_id)
        if not task:
            return False

        if task["status"] != "pending":
            return False

        self._update_status(
            task_id,
            "failed",
            error_message="Cancelled by user",
            completed_at=datetime.utcnow()
        )
        return True

    def shutdown(self, wait: bool = True):
        """关闭任务队列"""
        self.executor.shutdown(wait=wait)


# 全局任务队列实例
task_queue = TaskQueue()
