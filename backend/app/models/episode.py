# -*- coding: utf-8 -*-
"""
Episode (单集) 数据模型
"""
from datetime import datetime
from bson import ObjectId


class Episode:
    """播客单集模型"""

    # 状态常量
    STATUS_NEW = "new"
    STATUS_DOWNLOADING = "downloading"
    STATUS_DOWNLOADED = "downloaded"
    STATUS_TRANSCRIBING = "transcribing"
    STATUS_TRANSCRIBED = "transcribed"
    STATUS_SUMMARIZING = "summarizing"
    STATUS_SUMMARIZED = "summarized"
    STATUS_ERROR = "error"

    # 处理中状态列表 (用于锁检查)
    PROCESSING_STATUSES = [STATUS_DOWNLOADING, STATUS_TRANSCRIBING, STATUS_SUMMARIZING]

    @staticmethod
    def create(feed_id: ObjectId, guid: str, title: str, **kwargs) -> dict:
        """创建新的Episode文档"""
        now = datetime.utcnow()
        return {
            "feed_id": feed_id,
            "guid": guid,
            "title": title,
            "summary": kwargs.get("summary", ""),
            "content": kwargs.get("content", ""),
            "link": kwargs.get("link", ""),
            "published": kwargs.get("published"),
            "audio_url": kwargs.get("audio_url", ""),
            "audio_type": kwargs.get("audio_type", "audio/mpeg"),
            "audio_size": kwargs.get("audio_size", 0),
            "duration": kwargs.get("duration", 0),
            "image": kwargs.get("image", ""),
            "chapters_url": kwargs.get("chapters_url"),
            "transcript_url": kwargs.get("transcript_url"),
            "status": Episode.STATUS_NEW,
            "audio_path": None,
            "is_read": False,
            "is_starred": False,
            "is_favorite": False,
            "play_position": 0,
            "popularity_score": 0,
            "created_at": now,
            "updated_at": now
        }

    @staticmethod
    def format_duration(seconds: int) -> str:
        """格式化时长为 H:MM:SS 或 MM:SS"""
        if not seconds or seconds <= 0:
            return "00:00"
        hours = seconds // 3600
        minutes = (seconds % 3600) // 60
        secs = seconds % 60
        if hours > 0:
            return f"{hours}:{minutes:02d}:{secs:02d}"
        return f"{minutes:02d}:{secs:02d}"

    @staticmethod
    def to_response(doc: dict, include_feed_title: bool = False) -> dict:
        """转换为API响应格式"""
        if not doc:
            return None

        duration = doc.get("duration", 0)

        # 兼容旧数据: description字段映射到summary
        summary = doc.get("summary", "") or doc.get("description", "")

        result = {
            "id": str(doc["_id"]),
            "feed_id": str(doc["feed_id"]) if doc.get("feed_id") else None,
            "guid": doc.get("guid", ""),
            "title": doc.get("title", ""),
            "summary": summary,
            "content": doc.get("content", ""),
            "description": summary,  # 保持向后兼容
            "link": doc.get("link", ""),
            "published": doc.get("published").isoformat() + "Z" if doc.get("published") else None,
            "published_at": doc.get("published").isoformat() + "Z" if doc.get("published") else None,
            "audio_url": doc.get("audio_url", ""),
            "audio_type": doc.get("audio_type", ""),
            "audio_size": doc.get("audio_size", 0),
            "duration": duration,
            "duration_formatted": Episode.format_duration(duration),
            "image": doc.get("image", ""),
            "chapters_url": doc.get("chapters_url"),
            "transcript_url": doc.get("transcript_url"),
            "status": doc.get("status", Episode.STATUS_NEW),
            "audio_path": doc.get("audio_path"),
            "local_path": doc.get("local_path"),
            "is_read": doc.get("is_read", False),
            "is_starred": doc.get("is_starred", False),
            "is_favorite": doc.get("is_favorite", False),
            "play_position": doc.get("play_position", 0),
            "has_transcript": doc.get("has_transcript", False),
            "has_summary": doc.get("has_summary", False),
            "created_at": doc.get("created_at").isoformat() + "Z" if doc.get("created_at") else None,
            "updated_at": doc.get("updated_at").isoformat() + "Z" if doc.get("updated_at") else None
        }

        if include_feed_title and doc.get("feed_title"):
            result["feed_title"] = doc["feed_title"]

        return result

    @staticmethod
    def can_download(status: str) -> bool:
        """检查是否可以开始下载"""
        return status == Episode.STATUS_NEW

    @staticmethod
    def can_transcribe(status: str) -> bool:
        """检查是否可以开始转录"""
        return status == Episode.STATUS_DOWNLOADED

    @staticmethod
    def can_summarize(status: str) -> bool:
        """检查是否可以开始摘要"""
        return status == Episode.STATUS_TRANSCRIBED

    @staticmethod
    def is_processing(status: str) -> bool:
        """检查是否正在处理中"""
        return status in Episode.PROCESSING_STATUSES
