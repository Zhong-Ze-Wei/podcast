# -*- coding: utf-8 -*-
"""
API模块
"""
from .feeds import feeds_bp
from .episodes import episodes_bp
from .transcripts import transcripts_bp
from .summaries import summaries_bp
from .tasks import tasks_bp
from .stats import stats_bp

__all__ = [
    "feeds_bp",
    "episodes_bp",
    "transcripts_bp",
    "summaries_bp",
    "tasks_bp",
    "stats_bp"
]
