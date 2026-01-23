# -*- coding: utf-8 -*-
"""
Summary (摘要) 数据模型
支持多种摘要类型：general, investment, learning
"""
from datetime import datetime
from bson import ObjectId
from typing import Dict, Any, Optional


class Summary:
    """摘要结果模型"""

    # 支持的摘要类型
    TYPE_GENERAL = "general"
    TYPE_INVESTMENT = "investment"
    TYPE_LEARNING = "learning"

    VALID_TYPES = [TYPE_GENERAL, TYPE_INVESTMENT, TYPE_LEARNING]

    @staticmethod
    def create(
        episode_id: ObjectId,
        summary_type: str,
        content: Dict[str, Any],
        model: str = "",
        tokens_used: Dict[str, int] = None,
        **kwargs
    ) -> dict:
        """创建新的 Summary 文档"""
        now = datetime.utcnow()

        return {
            "episode_id": episode_id,
            "summary_type": summary_type,
            "version": "v2",

            # 从 content 提取顶级字段
            "tldr": content.get("tldr", ""),
            "tags": content.get("tags", []),

            # 完整内容 (类型特定)
            "content": content,

            # 中文翻译 (可选，后续填充)
            "content_zh": kwargs.get("content_zh"),

            # 元信息
            "model": model,
            "tokens_used": tokens_used or {},
            "generation_time_seconds": kwargs.get("generation_time_seconds", 0),

            # 时间戳
            "created_at": now,
            "updated_at": now
        }

    @staticmethod
    def to_response(doc: dict) -> Optional[dict]:
        """转换为 API 响应格式"""
        if not doc:
            return None

        content = doc.get("content", {})
        content_zh = doc.get("content_zh", {})
        summary_type = doc.get("summary_type", "general")
        template_name = doc.get("template_name", summary_type)  # 兼容旧数据

        response = {
            "id": str(doc["_id"]),
            "episode_id": str(doc["episode_id"]) if doc.get("episode_id") else None,
            "summary_type": summary_type,
            "template_name": template_name,
            "version": doc.get("version", "v1"),

            # 顶级字段
            "tldr": doc.get("tldr", ""),
            "tldr_zh": content_zh.get("tldr_zh", ""),
            "tags": doc.get("tags", []),

            # 完整内容
            "content": content,
            "content_zh": content_zh,

            # 是否有中文翻译
            "has_translation": bool(content_zh),

            # 元信息
            "model": doc.get("model", ""),
            "tokens_used": doc.get("tokens_used", {}),

            # 时间戳
            "created_at": doc.get("created_at").isoformat() + "Z" if doc.get("created_at") else None,
            "translated_at": doc.get("translated_at").isoformat() + "Z" if doc.get("translated_at") else None
        }

        # 根据类型或内容存在性添加特定字段的快捷访问
        # 优先检查 content 中是否存在数据，以支持新模板系统
        if content.get("investment_signals") or summary_type == Summary.TYPE_INVESTMENT:
            response["investment_signals"] = content.get("investment_signals", [])
            response["mentioned_tickers"] = content.get("mentioned_tickers", [])
            response["market_insights"] = content.get("market_insights", [])
            response["key_quotes"] = content.get("key_quotes", [])
            response["risk_alerts"] = content.get("risk_alerts", [])
            response["investment_thesis"] = content.get("investment_thesis", "")

        if content.get("key_points") or summary_type == Summary.TYPE_GENERAL:
            response["key_points"] = content.get("key_points", [])
            response["why_it_matters"] = content.get("why_it_matters", "")

        # 新模板系统的额外字段
        if content.get("unique_insights"):
            response["unique_insights"] = content.get("unique_insights", [])
        if content.get("core_content"):
            response["core_content"] = content.get("core_content", "")
        if content.get("guest_background"):
            response["guest_background"] = content.get("guest_background", "")

        # Data & Evidence 模板字段
        if content.get("cited_data"):
            response["cited_data"] = content.get("cited_data", [])
        if content.get("data_sources"):
            response["data_sources"] = content.get("data_sources", [])
        if content.get("factual_claims"):
            response["factual_claims"] = content.get("factual_claims", [])
        if content.get("opinion_claims"):
            response["opinion_claims"] = content.get("opinion_claims", [])
        if content.get("missing_data"):
            response["missing_data"] = content.get("missing_data", [])
        if content.get("frameworks"):
            response["frameworks"] = content.get("frameworks", [])

        # Stakeholder 模板字段
        if content.get("speaker_profile"):
            response["speaker_profile"] = content.get("speaker_profile", "")
        if content.get("stakeholders"):
            response["stakeholders"] = content.get("stakeholders", [])
        if content.get("hidden_agendas"):
            response["hidden_agendas"] = content.get("hidden_agendas", [])
        if content.get("power_dynamics"):
            response["power_dynamics"] = content.get("power_dynamics", "")
        if content.get("contrasting_views"):
            response["contrasting_views"] = content.get("contrasting_views", [])

        return response

    @staticmethod
    def validate_type(summary_type: str) -> str:
        """验证摘要类型，返回有效类型"""
        if summary_type in Summary.VALID_TYPES:
            return summary_type
        return Summary.TYPE_GENERAL
