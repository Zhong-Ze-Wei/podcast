# -*- coding: utf-8 -*-
"""
Task (异步任务) 数据模型
"""
from datetime import datetime
from bson import ObjectId
import uuid


class Task:
    """异步任务模型"""

    # 任务类型
    TYPE_DOWNLOAD = "download"
    TYPE_TRANSCRIBE = "transcribe"
    TYPE_SUMMARIZE = "summarize"
    TYPE_REFRESH = "refresh"

    # 状态常量
    STATUS_PENDING = "pending"
    STATUS_PROCESSING = "processing"
    STATUS_COMPLETED = "completed"
    STATUS_FAILED = "failed"

    @staticmethod
    def create(task_type: str, episode_id: ObjectId = None, feed_id: ObjectId = None, owner_id: str = None) -> dict:
        """创建新的Task文档"""
        now = datetime.utcnow()

        return {
            "task_id": str(uuid.uuid4()),
            "task_type": task_type,
            "episode_id": episode_id,
            "feed_id": feed_id,
            "owner_id": owner_id,
            "status": Task.STATUS_PENDING,
            "progress": 0,
            "result": None,
            "error_message": None,
            "created_at": now,
            "started_at": None,
            "completed_at": None
        }

