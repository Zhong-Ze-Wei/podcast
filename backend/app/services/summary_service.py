# -*- coding: utf-8 -*-
"""
摘要生成服务
负责调用 LLM 生成播客摘要
"""
import logging
from datetime import datetime
from typing import Optional, Dict, Any
from bson import ObjectId

from app.services.llm_client import get_llm_client
from app.services.prompts import PromptRouter

logger = logging.getLogger(__name__)


class SummaryService:
    """摘要生成服务"""

    def __init__(self, db):
        self.db = db
        self.llm = get_llm_client()

    def generate_summary(
        self,
        episode_id: ObjectId,
        summary_type: str = "general",
        force: bool = False
    ) -> Dict[str, Any]:
        """
        生成摘要（主入口）

        Args:
            episode_id: 节目 ID
            summary_type: 摘要类型 (general, investment)
            force: 是否强制重新生成

        Returns:
            生成的摘要文档
        """
        # 1. 检查是否已存在
        if not force:
            existing = self.db.summaries.find_one({
                "episode_id": episode_id,
                "summary_type": summary_type
            })
            if existing:
                logger.info(f"Summary already exists for episode {episode_id}")
                return existing

        # 2. 获取节目信息
        episode = self.db.episodes.find_one({"_id": episode_id})
        if not episode:
            raise ValueError(f"Episode not found: {episode_id}")

        # 3. 获取转录文本
        transcript = self.db.transcripts.find_one({"episode_id": episode_id})
        if not transcript or not transcript.get("text"):
            raise ValueError(f"Transcript not found for episode: {episode_id}")

        transcript_text = transcript["text"]
        title = episode.get("title", "Unknown")

        # 尝试从标题或描述中提取嘉宾信息
        guest = self._extract_guest(episode)

        logger.info(
            f"Generating {summary_type} summary for episode: {title}, "
            f"transcript length: {len(transcript_text)} chars"
        )

        # 4. 第一阶段：生成英文摘要
        english_summary = self._generate_english_summary(
            transcript_text=transcript_text,
            title=title,
            guest=guest,
            summary_type=summary_type
        )

        # 5. 保存英文版本
        summary_doc = self._create_summary_document(
            episode_id=episode_id,
            summary_type=summary_type,
            content=english_summary["data"],
            usage=english_summary["usage"],
            model=english_summary["model"],
            elapsed=english_summary["elapsed_seconds"]
        )

        # 保存到数据库
        result = self.db.summaries.update_one(
            {"episode_id": episode_id, "summary_type": summary_type},
            {"$set": summary_doc},
            upsert=True
        )

        # 获取完整文档
        saved_doc = self.db.summaries.find_one({
            "episode_id": episode_id,
            "summary_type": summary_type
        })

        # 6. 更新节目状态
        self.db.episodes.update_one(
            {"_id": episode_id},
            {"$set": {
                "has_summary": True,
                "status": "summarized",
                "updated_at": datetime.utcnow()
            }}
        )

        logger.info(f"Summary generated successfully for episode {episode_id}")

        return saved_doc

    def translate_summary(self, episode_id: ObjectId, summary_type: str = "general") -> Dict[str, Any]:
        """
        翻译摘要为中文

        Args:
            episode_id: 节目 ID
            summary_type: 摘要类型

        Returns:
            更新后的摘要文档
        """
        # 1. 获取现有摘要
        summary = self.db.summaries.find_one({
            "episode_id": episode_id,
            "summary_type": summary_type
        })

        if not summary:
            raise ValueError(f"Summary not found for episode: {episode_id}")

        # 检查是否已有中文翻译
        if summary.get("content_zh"):
            logger.info(f"Chinese translation already exists for episode {episode_id}")
            return summary

        content = summary.get("content", {})
        if not content:
            raise ValueError("Summary content is empty")

        logger.info(f"Translating summary for episode {episode_id}")

        # 2. 调用翻译
        translate_prompt = PromptRouter.get_translate_prompt()
        messages = translate_prompt.build_messages(content=content)

        result = self.llm.chat_json(
            messages=messages,
            temperature=0.2
        )

        translated = result["data"]

        # 3. 更新数据库
        update_data = {
            "content_zh": translated,
            "translation_model": result["model"],
            "translation_tokens": result["usage"],
            "translated_at": datetime.utcnow(),
            "updated_at": datetime.utcnow()
        }

        self.db.summaries.update_one(
            {"episode_id": episode_id, "summary_type": summary_type},
            {"$set": update_data}
        )

        # 返回更新后的文档
        return self.db.summaries.find_one({
            "episode_id": episode_id,
            "summary_type": summary_type
        })

    def _generate_english_summary(
        self,
        transcript_text: str,
        title: str,
        guest: str,
        summary_type: str
    ) -> Dict[str, Any]:
        """生成英文摘要"""
        prompt = PromptRouter.get_prompt(summary_type)
        messages = prompt.build_messages(
            transcript=transcript_text,
            title=title,
            guest=guest
        )

        result = self.llm.chat_json(
            messages=messages,
            temperature=0.2
        )

        return result

    def _create_summary_document(
        self,
        episode_id: ObjectId,
        summary_type: str,
        content: Dict,
        usage: Dict,
        model: str,
        elapsed: float
    ) -> Dict:
        """创建摘要文档"""
        now = datetime.utcnow()

        return {
            "episode_id": episode_id,
            "summary_type": summary_type,
            "version": "v2",

            # 从 content 中提取顶级字段
            "tldr": content.get("tldr", ""),
            "tags": content.get("tags", []),

            # 完整内容
            "content": content,

            # 元信息
            "model": model,
            "tokens_used": usage,
            "generation_time_seconds": elapsed,

            # 时间戳
            "created_at": now,
            "updated_at": now
        }

    def _extract_guest(self, episode: Dict) -> str:
        """尝试从节目信息中提取嘉宾"""
        title = episode.get("title", "")

        # 常见模式: "#123 - Guest Name: Topic"
        if " - " in title:
            parts = title.split(" - ", 1)
            if len(parts) > 1:
                guest_part = parts[1].split(":")[0].strip()
                return guest_part

        # 常见模式: "Guest Name | Topic"
        if " | " in title:
            parts = title.split(" | ")
            return parts[0].strip()

        return "Unknown"


def get_summary_service(db) -> SummaryService:
    """获取摘要服务实例"""
    return SummaryService(db)
