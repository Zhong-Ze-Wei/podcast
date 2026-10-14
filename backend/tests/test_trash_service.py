# -*- coding: utf-8 -*-
"""垃圾箱：删源入桶、重订捞回、过期物理清除"""
from datetime import datetime, timedelta

from bson import ObjectId

from app.services import trash_service
from tests.conftest import MockDB


def _feed(db, url="https://www.youtube.com/feeds/videos.xml?channel_id=UCtest"):
    fid = ObjectId()
    db.feeds._data.append({
        "_id": fid, "rss_url": url, "channel_ref": "UCtest", "title": "测试源",
        "owner_id": "u1", "type": "youtube",
    })
    return fid


def _episode(db, fid, guid="youtube:v1", with_transcript=True):
    eid = ObjectId()
    db.episodes._data.append({
        "_id": eid, "feed_id": fid, "guid": guid, "title": "Ep1",
        "owner_id": "u1", "audio_type": "video/youtube", "has_transcript": with_transcript,
    })
    if with_transcript:
        db.transcripts._data.append({"_id": ObjectId(), "episode_id": eid, "owner_id": "u1", "text": "字幕"})
    db.summaries._data.append({"_id": ObjectId(), "episode_id": eid, "owner_id": "u1", "template_name": "learning"})
    db.user_episode_states._data.append({"_id": ObjectId(), "episode_id": eid, "owner_id": "u1", "progress": 30})
    return eid


def test_trash_then_restore_roundtrip():
    db = MockDB()
    fid = _feed(db)
    eid = _episode(db, fid)

    feed = db.feeds.find_one({"_id": fid})
    assert trash_service.trash_feed_content(db, feed) == 1
    # 入桶后：活动集合全部清空，垃圾箱有一桶
    assert db.episodes.count_documents({}) == 0
    assert db.transcripts.count_documents({}) == 0
    assert db.summaries.count_documents({}) == 0
    assert db.user_episode_states.count_documents({}) == 0
    assert db.trash.count_documents({"kind": "episode"}) == 1

    # 重新订阅同一来源：整体捞回
    new_fid = ObjectId()
    new_feed = {**feed, "_id": new_fid}
    assert trash_service.restore_feed_content(db, new_feed) == 1
    ep = db.episodes.find_one({})
    assert ep["feed_id"] == new_fid  # 换绑到新订阅
    assert ep["_id"] == eid
    assert db.transcripts.count_documents({}) == 1
    assert db.summaries.count_documents({}) == 1
    assert db.user_episode_states.count_documents({}) == 1
    assert db.trash.count_documents({}) == 0  # 桶清空


def test_restore_skips_when_guid_already_reimported():
    db = MockDB()
    fid = _feed(db)
    _episode(db, fid, guid="youtube:v1")

    trash_service.trash_feed_content(db, db.feeds.find_one({"_id": fid}))
    # 重新订阅后 RSS 又导入了同 guid 的新剧集
    new_fid = _feed(db)
    db.episodes._data.append({"_id": ObjectId(), "feed_id": new_fid, "guid": "youtube:v1",
                              "title": "新导入", "owner_id": "u1"})
    new_feed = db.feeds.find_one({"_id": new_fid})
    assert trash_service.restore_feed_content(db, new_feed) == 0  # 同 guid 不重复捞
    assert db.episodes.count_documents({}) == 1
    assert db.trash.count_documents({}) == 0  # 冲突桶作废


def test_purge_expired_only_removes_old_buckets():
    db = MockDB()
    fid = _feed(db)
    _episode(db, fid)
    trash_service.trash_feed_content(db, db.feeds.find_one({"_id": fid}))

    # 手动把桶改成 31 天前 → 应被清除
    db.trash._data[0]["deleted_at"] = datetime.utcnow() - timedelta(days=31)
    db.trash._data.append({"kind": "episode", "deleted_at": datetime.utcnow(), "episode": {}})
    assert trash_service.purge_expired(db, retention_days=30) == 1
    assert db.trash.count_documents({}) == 1


def test_trash_orphan_episodes():
    db = MockDB()
    fid = _feed(db)
    _episode(db, fid)                      # 正常剧集，不动
    _episode(db, ObjectId())               # 孤儿剧集（源不存在）

    assert trash_service.trash_orphan_episodes(db) == 1
    assert db.episodes.count_documents({}) == 1
    assert db.trash.count_documents({}) == 1
