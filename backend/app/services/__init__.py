# -*- coding: utf-8 -*-
"""
服务模块
"""
from .rss_service import RSSService
from .task_queue import TaskQueue, task_queue

__all__ = ["RSSService", "TaskQueue", "task_queue"]
