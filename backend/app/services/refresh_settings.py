# -*- coding: utf-8 -*-
"""订阅更新节奏的统一配置源。

所有更新间隔只在设置页调节，存 `settings` 集合的单条文档（_id=feed_refresh），
运行时改动立即生效。不再读环境变量：多个来源会让设置页显示的值和实际行为对不上。
"""
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

DOC_ID = "feed_refresh"

# 可调参数的边界与默认值：YouTube 与 RSS 共用同一个更新间隔
LIMITS = {
    "feed_interval_hours": (1, 168),
    "check_interval_minutes": (1, 60),
    "feeds_per_tick": (1, 20),
    "transcript_interval_minutes": (1, 300),
    "transcript_sweep_minutes": (5, 1440),
    "transcript_sweep_batch": (1, 50),
}
DEFAULTS = {
    "feed_interval_hours": 12,
    "check_interval_minutes": 15,
    "feeds_per_tick": 1,
    "transcript_interval_minutes": 2,
    "transcript_sweep_minutes": 60,
    "transcript_sweep_batch": 8,
    "enabled": True,
}


def _coerce(key, value):
    """夹到合法区间；整型参数保持整型，避免设置页出现 12.0。"""
    low, high = LIMITS[key]
    try:
        number = float(value)
    except (TypeError, ValueError):
        return DEFAULTS[key]
    number = max(low, min(high, number))
    return int(round(number)) if isinstance(DEFAULTS[key], int) else number


def defaults():
    return dict(DEFAULTS)


def get_settings(db):
    """读取当前生效配置；库里没有记录时返回默认值（不写库）。"""
    values = defaults()
    doc = db.settings.find_one({"_id": DOC_ID}) or {}
    for key in LIMITS:
        if key in doc:
            values[key] = _coerce(key, doc[key])
    if "enabled" in doc:
        values["enabled"] = bool(doc["enabled"])
    return values


def save_settings(db, changes):
    """只保存白名单内的字段，返回保存后生效的配置。"""
    updates = {}
    for key, value in (changes or {}).items():
        if key == "enabled":
            updates[key] = bool(value)
        elif key in LIMITS:
            updates[key] = _coerce(key, value)
    if updates:
        updates["updated_at"] = datetime.utcnow()
        db.settings.update_one({"_id": DOC_ID}, {"$set": updates}, upsert=True)
        logger.info("订阅更新参数已更新: %s", {key: value for key, value in updates.items()
                                              if key != "updated_at"})
    return get_settings(db)


def feed_interval(settings):
    return timedelta(hours=settings["feed_interval_hours"])


def is_due(last_checked, settings, now=None):
    """单个源是否到了更新时间：从未检查过，或已超过统一间隔。"""
    if not last_checked:
        return True
    return (now or datetime.utcnow()) - last_checked >= feed_interval(settings)


def daily_window(now=None, hours=24):
    """每日摘要的统计窗口（最近 24 小时）。"""
    return (now or datetime.utcnow()) - timedelta(hours=hours)
