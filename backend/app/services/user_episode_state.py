# -*- coding: utf-8 -*-
"""
剧集个人状态（已读/加星/播放进度）

共享库模式下剧集文档全员可见，个人状态按用户隔离存储在 user_episode_states，
不再写在剧集文档上（旧字段仅作历史数据保留）。
"""
from datetime import datetime

STATE_FIELDS = ("is_read", "is_starred", "play_position")


def get_states(db, user_id, episode_ids):
    """批量取用户在指定剧集上的状态文档，返回 {episode_id: state}"""
    ids = [i for i in episode_ids if i is not None]
    if not ids:
        return {}
    return {
        s["episode_id"]: s
        for s in db.user_episode_states.find({"user_id": user_id, "episode_id": {"$in": ids}})
    }


def apply_to_response(response, state):
    """把个人状态合并进剧集响应；用户无状态时保持文档默认值"""
    if state:
        for field in STATE_FIELDS:
            if field in state:
                response[field] = state[field]
    return response


def episode_ids_with(db, user_id, flag, value=True):
    """取用户在某个状态位（is_read/is_starred）上为真的剧集 id 列表"""
    return [
        s["episode_id"]
        for s in db.user_episode_states.find({"user_id": user_id, flag: value}, {"episode_id": 1})
    ]


def upsert(db, user_id, episode_id, fields):
    """写入用户在某剧集上的状态（只接受 STATE_FIELDS 内的字段）"""
    fields = {f: v for f, v in fields.items() if f in STATE_FIELDS}
    if not fields:
        return
    fields["updated_at"] = datetime.utcnow()
    db.user_episode_states.update_one(
        {"user_id": user_id, "episode_id": episode_id},
        {"$set": fields},
        upsert=True,
    )


def user_filter_condition(db, user_id, is_read=None, is_starred=None):
    """
    把 is_read / is_starred 过滤解析为单个 _id 查询条件（个人状态过滤）。
    取反条件（如 is_read=false）以全库剧集减去命中集实现，规模在千级内可接受。
    """
    if is_read is None and is_starred is None:
        return None

    universe = None

    def effective_ids(flag, positive):
        nonlocal universe
        matched = set(episode_ids_with(db, user_id, flag))
        if positive:
            return matched
        if universe is None:
            universe = {e["_id"] for e in db.episodes.find({}, {})}
        return universe - matched

    result = None
    if is_read is not None:
        result = effective_ids("is_read", is_read)
    if is_starred is not None:
        starred = effective_ids("is_starred", is_starred)
        result = starred if result is None else result & starred
    return {"_id": {"$in": list(result)}}
