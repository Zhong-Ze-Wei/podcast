# -*- coding: utf-8 -*-
"""
剧集个人状态（已读/加星/播放进度）

共享库模式下剧集文档全员可见，个人状态按用户隔离存储在 user_episode_states，
不再写在剧集文档上（旧字段仅作历史数据保留）。
"""
from datetime import datetime

STATE_DEFAULTS = {"is_read": False, "is_starred": False, "play_position": 0}
STATE_FIELDS = tuple(STATE_DEFAULTS)


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
    """个人状态只取当前用户的记录，不继承共享剧集的历史字段。"""
    response.update(STATE_DEFAULTS)
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


def unread_count(db, user_id, feed_id):
    read_ids = episode_ids_with(db, user_id, "is_read")
    return db.episodes.count_documents({"feed_id": feed_id, "_id": {"$nin": read_ids}})


def user_filter_condition(db, user_id, is_read=None, is_starred=None):
    """个人状态过滤直接排除已读/已收藏 ID，不读取全库文稿。"""
    conditions = []
    for flag, value in (("is_read", is_read), ("is_starred", is_starred)):
        if value is not None:
            ids = episode_ids_with(db, user_id, flag)
            conditions.append({"_id": {"$in" if value else "$nin": ids}})
    if not conditions:
        return None
    return conditions[0] if len(conditions) == 1 else {"$and": conditions}
