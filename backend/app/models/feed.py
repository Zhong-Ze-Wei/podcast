# -*- coding: utf-8 -*-
"""
Feed (订阅源) 数据模型
"""
from datetime import datetime
from bson import ObjectId


class Feed:
    """RSS订阅源模型"""

    # 状态常量
    STATUS_ACTIVE = "active"
    STATUS_PAUSED = "paused"
    STATUS_ERROR = "error"

    @staticmethod
    def create(rss_url: str, title: str = None, **kwargs) -> dict:
        """创建新的Feed文档"""
        now = datetime.utcnow()
        return {
            "rss_url": rss_url,
            "title": title or "",
            "website": kwargs.get("website", ""),
            "image": kwargs.get("image", ""),
            "description": kwargs.get("description", ""),
            "author": kwargs.get("author", ""),
            "language": kwargs.get("language", ""),
            "status": Feed.STATUS_ACTIVE,
            "last_checked": None,
            "last_updated": None,
            "check_error": None,
            "is_starred": False,
            "is_favorite": False,
            "tags": kwargs.get("tags", []),
            "episode_count": 0,
            "unread_count": 0,
            "created_at": now,
            "updated_at": now
        }

    @staticmethod
    def to_response(doc: dict) -> dict:
        """转换为API响应格式"""
        if not doc:
            return None
        return {
            "id": str(doc["_id"]),
            "rss_url": doc.get("rss_url", ""),
            "title": doc.get("title", ""),
            "website": doc.get("website", ""),
            "image": doc.get("image", ""),
            "description": doc.get("description", ""),
            "author": doc.get("author", ""),
            "language": doc.get("language", ""),
            "status": doc.get("status", Feed.STATUS_ACTIVE),
            "last_checked": doc.get("last_checked").isoformat() + "Z" if doc.get("last_checked") else None,
            "last_updated": doc.get("last_updated").isoformat() + "Z" if doc.get("last_updated") else None,
            "check_error": doc.get("check_error"),
            "is_starred": doc.get("is_starred", False),
            "is_favorite": doc.get("is_favorite", False),
            "note": doc.get("note", ""),
            "tags": doc.get("tags", []),
            "episode_count": doc.get("episode_count", 0),
            "unread_count": doc.get("unread_count", 0),
            "created_at": doc.get("created_at").isoformat() + "Z" if doc.get("created_at") else None,
            "updated_at": doc.get("updated_at").isoformat() + "Z" if doc.get("updated_at") else None
        }

    @staticmethod
    def validate_rss_url(url: str) -> bool:
        """验证RSS URL格式"""
        if not url:
            return False
        return url.startswith("http://") or url.startswith("https://")
