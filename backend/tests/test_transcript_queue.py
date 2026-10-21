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
