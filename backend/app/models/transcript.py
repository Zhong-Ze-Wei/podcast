# -*- coding: utf-8 -*-
"""
Transcript (转录) 数据模型
"""
from datetime import datetime
from bson import ObjectId


class Transcript:
    """转录结果模型"""

    # 来源类型
    SOURCE_WHISPER = "whisper"
    SOURCE_OFFICIAL = "official"
    SOURCE_MANUAL = "manual"

    @staticmethod
    def create(episode_id: ObjectId, text: str, segments: list = None, **kwargs) -> dict:
        """创建新的Transcript文档"""
        now = datetime.utcnow()
        word_count = len(text.split()) if text else 0

        return {
            "episode_id": episode_id,
            "text": text,
            "segments": segments or [],
            "language": kwargs.get("language", "en"),
            "word_count": word_count,
            "source": kwargs.get("source", Transcript.SOURCE_WHISPER),
            "model": kwargs.get("model", "base"),
            "created_at": now
        }

    @staticmethod
    def to_response(doc: dict) -> dict:
        """转换为API响应格式"""
        if not doc:
            return None
        return {
            "id": str(doc["_id"]),
            "episode_id": str(doc["episode_id"]) if doc.get("episode_id") else None,
            "text": doc.get("text", ""),
            "segments": doc.get("segments", []),
            "language": doc.get("language", ""),
            "word_count": doc.get("word_count", 0),
            "source": doc.get("source", ""),
            "model": doc.get("model", ""),
            "created_at": doc.get("created_at").isoformat() + "Z" if doc.get("created_at") else None
        }
