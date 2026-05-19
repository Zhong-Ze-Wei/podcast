# -*- coding: utf-8 -*-
"""
Summary Service

摘要生成服务，统一走 v3 template engine。
"""
import json
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from bson import ObjectId

from app.core.summarization import SummarizationEngine, get_summarization_engine
from app.services.llm_client import get_llm_client

logger = logging.getLogger(__name__)

# 翻译 prompt（内联，不再依赖外部文件）
TRANSLATE_SYSTEM_PROMPT = """You are a professional translator specializing in finance and technology content.
Your task is to translate English content to Chinese (Simplified) while preserving:
1. Technical terms accuracy
2. Stock tickers and company names in original form
3. The structure of the original content
Always output valid JSON only, no other text."""

TRANSLATE_USER_PROMPT = """Translate the following JSON content from English to Chinese (Simplified).

## Translation Guidelines
1. Keep stock tickers (e.g., GOOGL, NVDA) in English
2. Keep company names with both English and Chinese (e.g., "Google (谷歌)")
3. Translate "bullish" as "看多", "bearish" as "看空", "neutral" as "中性"
4. Preserve the exact JSON structure and keys
5. Translate all string values; keep arrays and objects structure intact

## Original Content
{content}

## Output
Output the translated JSON with the SAME keys (do NOT add _zh suffix):
{{"tldr": "中文翻译", "key_points": ["要点1", "要点2"], ...}}
"""


class SummaryService:
    """摘要生成服务"""

    def __init__(self, db):
        self.db = db
        self.llm = get_llm_client()
        self._engine = None

    @property
    def engine(self) -> SummarizationEngine:
        if self._engine is None:
            self._engine = get_summarization_engine(self.db, self.llm)
        return self._engine

    def generate_summary(
        self,
        episode_id: ObjectId,
        template_name: str = "learning",
        enabled_blocks: List[str] = None,
        params: Dict = None,
        force: bool = False
    ) -> Dict[str, Any]:
        """
        生成摘要，统一走 v3 template engine。

        Args:
            episode_id: Episode ObjectId
            template_name: 模板名称
            enabled_blocks: 要启用的 block IDs
            params: 参数 (e.g., {"length": "long"})
            force: 强制重新生成
        """
        return self.engine.summarize_episode(
            episode_id=episode_id,
            template_name=template_name,
            enabled_blocks=enabled_blocks,
            params=params,
            force=force
        )

    def translate_summary(
        self,
        episode_id: ObjectId,
        template_name: str = None
    ) -> Dict[str, Any]:
        """
        翻译摘要为中文。

        Args:
            episode_id: Episode ObjectId
            template_name: 模板名称
        """
        query = {"episode_id": episode_id}
        if template_name:
            query["template_name"] = template_name

        summary = self.db.summaries.find_one(query, sort=[("created_at", -1)])
        if not summary:
            raise ValueError(f"Summary not found for episode: {episode_id}")

        if summary.get("content_zh"):
            logger.info(f"Chinese translation already exists for episode {episode_id}")
            return summary

        content = summary.get("content", {})
        if not content:
            raise ValueError("Summary content is empty")

        logger.info(f"Translating summary for episode {episode_id}")

        content_json = json.dumps(content, ensure_ascii=False, indent=2)
        messages = [
            {"role": "system", "content": TRANSLATE_SYSTEM_PROMPT},
            {"role": "user", "content": TRANSLATE_USER_PROMPT.format(content=content_json)},
        ]

        result = self.llm.chat_json(messages=messages, temperature=0.2)
        translated = result["data"]

        now = datetime.utcnow()
        self.db.summaries.update_one(
            {"_id": summary["_id"]},
            {"$set": {
                "content_zh": translated,
                "translation_model": result["model"],
                "translation_tokens": result["usage"],
                "translated_at": now,
                "updated_at": now
            }}
        )

        return self.db.summaries.find_one({"_id": summary["_id"]})

    def get_available_templates(self) -> List[Dict]:
        """获取可用模板列表"""
        return self.engine.get_available_templates()


def get_summary_service(db) -> SummaryService:
    return SummaryService(db)
