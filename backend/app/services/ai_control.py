# -*- coding: utf-8 -*-
"""Central switch for freezing new AI analysis work."""
from flask import current_app

AI_DISABLED_MESSAGE = (
    "AI analysis is currently frozen. Existing summaries and cached briefings remain readable, "
    "but new summary, translation, and briefing generation is disabled."
)


def is_ai_analysis_enabled() -> bool:
    """数据库设置优先（设置页开关），无记录时回退环境变量默认值。"""
    db = getattr(current_app, "db", None)
    if db is not None:
        doc = db.settings.find_one({"_id": "ai_analysis"})
        if doc and "enabled" in doc:
            return bool(doc["enabled"])
    return bool(current_app.config.get("AI_ANALYSIS_ENABLED", False))
