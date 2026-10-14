# -*- coding: utf-8 -*-
"""订阅更新的个人查看记录，与单集是否已读分开保存。"""
from datetime import datetime


def latest_episode_id(db, feed_id):
    # 使用入库 ID，不使用发布时间；补录旧节目也属于新到的内容。
    latest = list(db.episodes.find({"feed_id": feed_id}, {"_id": 1}).sort("_id", -1).limit(1))
    return latest[0]["_id"] if latest else None


def get_states(db, user_id, feed_ids):
    return {state["feed_id"]: state for state in db.user_feed_states.find(
        {"user_id": user_id, "feed_id": {"$in": feed_ids}}
    )}


def has_unseen_updates(latest_id, state):
    seen_id = state.get("last_seen_episode_id") if state else None
    return latest_id is not None and (seen_id is None or latest_id > seen_id)


def record_view(db, user_id, feed_id, seen_id):
    """只确认已加载的版本；延迟的旧请求不能覆盖较新的查看记录。"""
    db.user_feed_states.update_one(
        {"user_id": user_id, "feed_id": feed_id},
        {"$max": {"last_seen_episode_id": seen_id}, "$set": {"last_viewed_at": datetime.utcnow()}},
        upsert=True,
    )
    state = db.user_feed_states.find_one({"user_id": user_id, "feed_id": feed_id})
    return has_unseen_updates(latest_episode_id(db, feed_id), state)
