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
    def create(task_type: str, episode_id: ObjectId = None, feed_id: ObjectId = None) -> dict:
        """创建新的Task文档"""
        now = datetime.utcnow()

        return {
            "task_id": str(uuid.uuid4()),
            "task_type": task_type,
            "episode_id": episode_id,
            "feed_id": feed_id,
            "status": Task.STATUS_PENDING,
            "progress": 0,
            "result": None,
            "error_message": None,
            "created_at": now,
            "started_at": None,
            "completed_at": None
        }

    @staticmethod
    def to_response(doc: dict) -> dict:
        """转换为API响应格式"""
        if not doc:
            return None
        return {
            "id": str(doc["_id"]) if doc.get("_id") else None,
            "task_id": doc.get("task_id", ""),
            "task_type": doc.get("task_type", ""),
            "episode_id": str(doc["episode_id"]) if doc.get("episode_id") else None,
            "feed_id": str(doc["feed_id"]) if doc.get("feed_id") else None,
            "status": doc.get("status", Task.STATUS_PENDING),
            "progress": doc.get("progress", 0),
            "result": doc.get("result"),
            "error_message": doc.get("error_message"),
            "created_at": doc.get("created_at").isoformat() + "Z" if doc.get("created_at") else None,
            "started_at": doc.get("started_at").isoformat() + "Z" if doc.get("started_at") else None,
            "completed_at": doc.get("completed_at").isoformat() + "Z" if doc.get("completed_at") else None
        }
