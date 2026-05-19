# -*- coding: utf-8 -*-
"""Central switch for freezing new AI analysis work."""
from flask import current_app

AI_DISABLED_MESSAGE = (
    "AI analysis is currently frozen. Existing summaries and cached briefings remain readable, "
    "but new summary, translation, and briefing generation is disabled."
)


def is_ai_analysis_enabled() -> bool:
    return bool(current_app.config.get("AI_ANALYSIS_ENABLED", False))
