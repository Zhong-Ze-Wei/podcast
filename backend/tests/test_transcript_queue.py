"""字幕抓取队列：单通道节流、按时间排序、新剧集插队、429 重试。"""
from datetime import datetime

import pytest

from app.services.transcript_queue_service import (
    MAX_INTERVAL_MINUTES, MIN_INTERVAL_MINUTES, PRIORITY_HISTORY, PRIORITY_NEW_EPISODE,
    TranscriptQueue,
)


def episode(index, prefix="ep", title=None):
    return {"_id": f"{index:024x}", "guid": f"youtube:{prefix}{index}",
            "title": title or f"{prefix} {index}"}


def test_queue_orders_by_priority_then_enqueue_time():
    queue = TranscriptQueue()
    queue.enqueue([episode(0, "hist"), episode(1, "hist")], priority=PRIORITY_HISTORY)
    queue.enqueue([episode(2, "new")], priority=PRIORITY_NEW_EPISODE)
    assert [item["title"] for item in queue.snapshot()["pending"]] == ["new 2", "hist 0", "hist 1"]


def test_new_episode_promotes_queued_backlog_item():
    queue = TranscriptQueue()
    old = episode(5, "old")
    queue.enqueue([episode(6, "old"), old], priority=PRIORITY_HISTORY)
    queue.enqueue([old], priority=PRIORITY_NEW_EPISODE)
    pending = queue.snapshot()["pending"]
    assert pending[0]["title"] == "old 5"
    assert pending[0]["priority"] == PRIORITY_NEW_EPISODE


def test_same_episode_is_not_duplicated():
    queue = TranscriptQueue()
    item = episode(7)
    assert queue.enqueue([item], priority=PRIORITY_HISTORY) == 1
    assert queue.enqueue([item], priority=PRIORITY_HISTORY) == 0
    assert len(queue.snapshot()["pending"]) == 1


def test_non_youtube_episodes_are_ignored():
    queue = TranscriptQueue()
    assert queue.enqueue([{"_id": "a" * 24, "guid": "rss:abc", "title": "RSS"}]) == 0
    assert queue.pending_count() == 0


@pytest.mark.parametrize("minutes,expected", [(1, 1), (0, 1), (300, 300), (999, MAX_INTERVAL_MINUTES), (45, 45)])
def test_interval_is_clamped(minutes, expected):
    queue = TranscriptQueue()
    assert queue.set_interval_minutes(minutes) == expected
    assert MIN_INTERVAL_MINUTES <= queue.snapshot()["interval_minutes"] <= MAX_INTERVAL_MINUTES


def test_snapshot_reports_positions_and_eta():
    queue = TranscriptQueue()
    queue.enqueue([episode(i, "hist") for i in range(3)], priority=PRIORITY_HISTORY)
    snapshot = queue.snapshot()
    assert [item["position"] for item in snapshot["pending"]] == [1, 2, 3]
    # 尚未抓过任何一期时，队首可立即开始
    assert snapshot["pending"][0]["eta_seconds"] == 0
    assert snapshot["queued_count"] == 3


def test_clear_empties_queue():
    queue = TranscriptQueue()
    queue.enqueue([episode(1), episode(2)])
    assert queue.clear() == 2
    assert queue.snapshot()["queued_count"] == 0


def test_throttle_backoff_sets_cooldown_instead_of_immediate_retry():
    """被限流时应设置冷却窗口并把该期排到队尾，而不是立刻重试同一期。"""
    from datetime import timedelta
    queue = TranscriptQueue()
    queue._interval_seconds = 60
    item = {"episode_id": "a" * 24, "guid": "youtube:abc", "title": "番外",
            "priority": PRIORITY_HISTORY, "enqueued_at": datetime.utcnow()}
    queue._items = [item]
    # 模拟第一次限流后的处理
    queue._cooldown_until = datetime.utcnow() + timedelta(seconds=120)
    delay = queue._next_slot_delay()
    assert delay > 0, "冷却期内不应立即抓取"
    # 冷却到点后自动清空，恢复常规节奏
    queue._cooldown_until = datetime.utcnow() - timedelta(seconds=1)
    queue._last_fetch_at = datetime.utcnow() - timedelta(seconds=120)
    queue._next_slot_delay()
    assert queue._cooldown_until is None


def test_proxy_pool_rotation_prefers_pool_over_clash(monkeypatch):
    """配置了直连代理池时轮换在池内完成，不调用 Clash。"""
    from app.services import transcript_queue_service as module

    queue = TranscriptQueue()
    pool = ["socks5://p1:1080", "socks5://p2:1080", "socks5://p3:1080"]
    monkeypatch.setattr(queue, "_proxy_pool", lambda: pool)
    monkeypatch.setattr(queue, "_probe_proxy", lambda proxy: proxy != pool[0])
    called = []
    from app.services import clash_service
    monkeypatch.setattr(clash_service, "available", lambda: called.append(1) or True)

    first = queue._rotate_exit("429")
    assert first == pool[1], "应跳过不可用的 p1 选到 p2"
    assert not called, "代理池可用时不应触碰 Clash"
    second = queue._rotate_exit("主动轮换")
    assert second == pool[2]
    # 再转一圈回到 p2（p1 始终不可用被跳过）
    third = queue._rotate_exit("主动轮换")
    assert third == pool[1]


def test_proxy_pool_all_down_falls_back_to_clash(monkeypatch):
    """池内全部不可用时应返回空串（调用方据此走长退避）。"""
    queue = TranscriptQueue()
    monkeypatch.setattr(queue, "_proxy_pool", lambda: ["socks5://dead:1080"])
    monkeypatch.setattr(queue, "_probe_proxy", lambda proxy: False)
    assert queue._rotate_exit("429") == ""


def test_deauth_hides_credentials_in_logs():
    assert TranscriptQueue._deauth("socks5://user:secret@1.2.3.4:1080") == "socks5://***@1.2.3.4:1080"
    assert TranscriptQueue._deauth("http://1.2.3.4:8080") == "http://1.2.3.4:8080"


def _db_episode(db, episode_id):
    db.episodes.insert_one({"_id": episode_id, "guid": "youtube:abc", "title": "Ep",
                            "status": "new", "audio_type": "video/youtube"})


def test_throttle_count_persists_across_requeue(monkeypatch):
    """限流计数落库：这期被放弃后重新入队，不能从 0 重新献祭。"""
    from bson import ObjectId
    from app.services import transcript_queue_service as module
    from app.services.youtube_service import YouTubeService
    from tests.conftest import MockDB

    db = MockDB()
    queue = module.TranscriptQueue(db=db)
    episode_id = ObjectId()
    _db_episode(db, episode_id)

    monkeypatch.setattr(module.TranscriptQueue, "_rotate_exit", lambda self, reason: "")
    monkeypatch.setattr(YouTubeService, "fetch_transcript",
                        classmethod(lambda cls, vid, proxy=None: (None, "HTTP Error 429")))
    monkeypatch.setattr("app.services.feed_sync_service._needs_youtube_metadata", lambda ep: False)

    item = {"episode_id": str(episode_id), "guid": "youtube:abc", "title": "Ep",
            "priority": module.PRIORITY_HISTORY, "enqueued_at": None}
    for _ in range(module.MAX_THROTTLE_ATTEMPTS + 1):
        queue._fetch_one(dict(item))

    stored = db.episodes.find_one({"_id": episode_id})
    assert stored["transcript_gave_up_at"] is not None
    assert stored["transcript_throttle_attempts"] > module.MAX_THROTTLE_ATTEMPTS

    # 再次入队重试：计数已落库，不会重新累计到上限后又来一轮
    before = stored["transcript_throttle_attempts"]
    queue._fetch_one(dict(item))
    assert db.episodes.find_one({"_id": episode_id})["transcript_throttle_attempts"] == before


def test_caption_tracks_detects_manual_and_automatic(monkeypatch):
    from app.services.youtube_service import YouTubeService

    info = {"subtitles": {"en": [{"ext": "vtt"}], "ja": []},
            "automatic_captions": {"en-orig": [{}], "zh-Hans": [{}], "de": [{}]}}
    tracks = YouTubeService.caption_tracks(info)
    assert tracks["manual"] == ["en"]              # ja 不在关注语种内
    assert tracks["automatic"] == ["en-orig", "zh-Hans"]
    assert tracks["available"] is True
    assert YouTubeService.caption_tracks({"subtitles": {}, "automatic_captions": {}})["available"] is False


def test_enqueue_skips_probed_episodes_without_captions(monkeypatch):
    """已探测确认没字幕轨的期不会再入队。"""
    from bson import ObjectId
    from app.services import transcript_queue_service as module
    from tests.conftest import MockDB

    db = MockDB()
    queue = module.TranscriptQueue(db=db)
    episode_id = ObjectId()
    db.episodes.insert_one({"_id": episode_id, "guid": "youtube:abc", "title": "Ep",
                            "audio_type": "video/youtube", "caption_tracks_state": "none"})
    episode = db.episodes.find_one({"_id": episode_id})

    calls = []
    monkeypatch.setattr(module.TranscriptQueue, "probe_captions",
                        lambda self, ep, proxy=None: calls.append(ep["_id"]) or "none")

    queue.enqueue([episode], priority=module.PRIORITY_HISTORY)
    assert queue.pending_count() == 0


def test_probe_empty_tracks_are_not_treated_as_missing(monkeypatch):
    """yt-dlp 有时不返回轨道但视频其实有字幕（POT/地区），空轨道只能记为 unknown。"""
    from bson import ObjectId
    from app.services import transcript_queue_service as module
    from app.services.youtube_service import YouTubeService
    from tests.conftest import MockDB

    db = MockDB()
    queue = module.TranscriptQueue(db=db)
    episode_id = ObjectId()
    db.episodes.insert_one({"_id": episode_id, "guid": "youtube:abc", "title": "Ep",
                            "audio_type": "video/youtube"})
    episode = db.episodes.find_one({"_id": episode_id})

    monkeypatch.setattr(YouTubeService, "probe_captions",
                        classmethod(lambda cls, vid, proxy=None: (
                            {"manual": [], "automatic": [], "available": False, "title": "Ep"}, None)))

    assert queue.probe_captions(episode) == module.TranscriptQueue.CAPTION_UNKNOWN
    stored = db.episodes.find_one({"_id": episode_id})
    # 关键：不能写死 none，否则这期再也不会被尝试，即使平台其实有字幕
    assert stored["caption_tracks_state"] == "unknown"
    assert "transcript_fetch_error" not in stored


def test_probe_failure_does_not_mark_episode_as_unavailable(monkeypatch):
    """探测本身失败（网络/限流）不能写死"没字幕"，否则会永久漏掉可抓的期。"""
    from bson import ObjectId
    from app.services import transcript_queue_service as module
    from app.services.youtube_service import YouTubeService
    from tests.conftest import MockDB

    db = MockDB()
    queue = module.TranscriptQueue(db=db)
    episode_id = ObjectId()
    db.episodes.insert_one({"_id": episode_id, "guid": "youtube:abc", "title": "Ep",
                            "audio_type": "video/youtube"})
    episode = db.episodes.find_one({"_id": episode_id})

    monkeypatch.setattr(YouTubeService, "probe_captions",
                        classmethod(lambda cls, vid, proxy=None: (None, "无法连接 YouTube")))

    assert queue.probe_captions(episode) == module.TranscriptQueue.CAPTION_UNKNOWN
    assert "caption_tracks_state" not in db.episodes.find_one({"_id": episode_id})
