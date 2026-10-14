# -*- coding: utf-8 -*-
"""订阅删除的垃圾箱。

删除订阅源时，其剧集连同字幕/摘要/个人状态整体搬进 trash 集合：
- 正常业务查询天然看不到（不需要给全站查询加 deleted 过滤）
- 保留期内重新订阅同一来源，按 restore_key 匹配自动捞回（字幕/摘要原样恢复）
- 超过保留期由后台定时物理清除，数据不可再恢复

每个剧集一个桶文档（episode + 其 transcripts/summaries/user_episode_states），
避免大订阅源单文档超 16MB 限制。
"""
from datetime import datetime, timedelta

from .feed_identity import normalize_feed_url

TRASH_RETENTION_DAYS = 30


def _restore_keys(feed: dict) -> list:
    """能识别"同一个源"的键：规范化 URL + 频道标识。"""
    keys = []
    url = (feed.get("rss_url") or "").strip()
    if url:
        normalized = normalize_feed_url(url)
        if normalized:
            keys.append(normalized)
    ref = (feed.get("channel_ref") or "").strip()
    if ref:
        keys.append(ref)
    return keys


def trash_feed_content(db, feed: dict) -> int:
    """删除订阅时调用：剧集及附属数据入桶。返回入桶剧集数。"""
    episodes = list(db.episodes.find({"feed_id": feed["_id"]}))
    if not episodes:
        return 0
    keys = _restore_keys(feed)
    now = datetime.utcnow()
    count = 0
    for episode in episodes:
        _trash_one(db, feed, keys, episode, now)
        count += 1
    return count


def trash_orphan_episodes(db) -> int:
    """清掉所属订阅源已不存在的孤儿剧集（历史残留）。没有源信息，入桶只作保留期安全网。"""
    feed_ids = [f["_id"] for f in db.feeds.find({}, {"_id": 1})]
    orphans = db.episodes.find({"feed_id": {"$nin": feed_ids}})
    now = datetime.utcnow()
    count = 0
    for episode in orphans:
        _trash_one(db, {"_id": episode.get("feed_id"), "title": "(已删除的源)"}, [], episode, now)
        count += 1
    return count


def _trash_one(db, feed: dict, keys: list, episode: dict, deleted_at: datetime):
    eid = episode["_id"]
    transcripts = list(db.transcripts.find({"episode_id": eid}))
    summaries = list(db.summaries.find({"episode_id": eid}))
    states = list(db.user_episode_states.find({"episode_id": eid}))
    db.trash.insert_one({
        "kind": "episode",
        "feed_id": feed.get("_id"),
        "feed_title": feed.get("title", ""),
        "restore_keys": keys,
        "owner_id": episode.get("owner_id"),
        "deleted_at": deleted_at,
        "episode": episode,
        "transcripts": transcripts,
        "summaries": summaries,
        "user_episode_states": states,
    })
    db.user_episode_states.delete_many({"episode_id": eid})
    db.summaries.delete_many({"episode_id": eid})
    db.transcripts.delete_many({"episode_id": eid})
    db.episodes.delete_one({"_id": eid})


def restore_feed_content(db, feed: dict) -> int:
    """（重新）订阅时调用：捞回同源历史剧集。返回恢复的剧集数。"""
    keys = _restore_keys(feed)
    if not keys:
        return 0
    existing_guids = {d["guid"] for d in db.episodes.find(
        {"feed_id": feed["_id"], "guid": {"$ne": None}}, {"guid": 1})}
    restored = 0
    for bucket in list(db.trash.find({"kind": "episode", "restore_keys": {"$in": keys}})):
        episode = bucket.get("episode") or {}
        guid = episode.get("guid")
        if guid and guid in existing_guids:
            db.trash.delete_one({"_id": bucket["_id"]})  # 新库里已有同 guid 剧集，桶作废
            continue
        episode["feed_id"] = feed["_id"]  # 换绑到新订阅
        db.episodes.insert_one(episode)
        if guid:
            existing_guids.add(guid)
        attachments = (bucket.get("transcripts") or [], bucket.get("summaries") or [],
                       bucket.get("user_episode_states") or [])
        for collection, docs in zip(
                (db.transcripts, db.summaries, db.user_episode_states), attachments):
            for doc in docs:
                if not collection.find_one({"episode_id": episode["_id"]}, {"_id": 1}):
                    collection.insert_one(doc)
        db.trash.delete_one({"_id": bucket["_id"]})
        restored += 1
    return restored


def purge_expired(db, retention_days: int = TRASH_RETENTION_DAYS) -> int:
    """物理清除超过保留期的桶（之后不可恢复）。返回清除的桶数。"""
    cutoff = datetime.utcnow() - timedelta(days=retention_days)
    result = db.trash.delete_many({"deleted_at": {"$lt": cutoff}})
    return result.deleted_count or 0
