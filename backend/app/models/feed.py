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
            "updated_at": now,
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
            "last_checked": doc.get("last_checked").isoformat() + "Z"
            if doc.get("last_checked")
            else None,
            "last_updated": doc.get("last_updated").isoformat() + "Z"
            if doc.get("last_updated")
            else None,
            "check_error": doc.get("check_error"),
            "is_starred": doc.get("is_starred", False),
            "is_favorite": doc.get("is_favorite", False),
            "note": doc.get("note", ""),
            "tags": doc.get("tags", []),
            "episode_count": doc.get("episode_count", 0),
            "unread_count": doc.get("unread_count", 0),
            "created_at": doc.get("created_at").isoformat() + "Z"
            if doc.get("created_at")
            else None,
            "updated_at": doc.get("updated_at").isoformat() + "Z"
            if doc.get("updated_at")
            else None,
        }

    @staticmethod
    def validate_rss_url(url: str) -> bool:
        """验证RSS URL格式并防止SSRF"""
        if not url:
            return False

        from urllib.parse import urlparse

        try:
            parsed = urlparse(url)

            # 只允许http/https
            if parsed.scheme not in ("http", "https"):
                return False

            # 禁止内网IP和localhost
            hostname = parsed.hostname
            if not hostname:
                return False

            # 禁止localhost和常见内网地址
            blocked_hosts = {"localhost", "127.0.0.1", "0.0.0.0", "::1"}
            if hostname.lower() in blocked_hosts:
                return False

            # 禁止私有IP段 (192.168.x.x, 10.x.x.x, 172.16-31.x.x)
            import ipaddress

            try:
                ip = ipaddress.ip_address(hostname)
                if ip.is_private or ip.is_loopback or ip.is_reserved:
                    return False
            except ValueError:
                # 不是IP地址，是域名，允许
                pass

            return True

        except Exception:
            return False
