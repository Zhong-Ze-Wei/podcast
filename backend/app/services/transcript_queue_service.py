# -*- coding: utf-8 -*-
"""字幕抓取队列：全局单通道、按集节流、新剧集可插队。

此前每个订阅刷新任务内部各自 sleep 2.5s 顺序补齐，多个源同时刷新时
等于并发打 YouTube，容易被 429。这里改为一个进程级队列：

- 所有待抓字幕进同一个队列，默认每 2 分钟抓一期（可在设置里 1–300 分钟调节）
- 队列按 enqueued_at 排序：历史积压按时间先后慢慢消化
- 刷新发现的新剧集用 priority=0 插到队首，优先拿到文稿
- 每期抓取结果写回 episode，并在任务面板显示排队位置与预计时间
"""
import logging
import os
import threading
import time
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

# 节流区间（分钟），设置页的滑杆也用它做上下限
MIN_INTERVAL_MINUTES = 1
MAX_INTERVAL_MINUTES = 300
DEFAULT_INTERVAL_MINUTES = 2
# 优先级：数值越小越先抓
PRIORITY_NEW_EPISODE = 0
PRIORITY_HISTORY = 10


class TranscriptQueue:
    """进程内单通道字幕抓取队列。"""

    def __init__(self, db=None, queue=None):
        self.db = db
        self.task_queue = queue
        self._lock = threading.RLock()
        self._wake = threading.Condition(self._lock)
        self._items = []          # [{episode_id, feed_id, guid, priority, enqueued_at, task_id}]
        self._running = False
        self._thread = None
        self._active = None       # 正在抓取的那一期
        self._last_fetch_at = None
        self._interval_seconds = DEFAULT_INTERVAL_MINUTES * 60
        self._stats = {"completed": 0, "failed": 0, "throttled": 0}

    # ---- 配置 ----
    def interval_minutes(self):
        return max(MIN_INTERVAL_MINUTES, min(MAX_INTERVAL_MINUTES, self._interval_seconds / 60))

    def set_interval_minutes(self, minutes):
        value = DEFAULT_INTERVAL_MINUTES if minutes is None or minutes == "" else float(minutes)
        value = max(MIN_INTERVAL_MINUTES, min(MAX_INTERVAL_MINUTES, value))
        with self._lock:
            self._interval_seconds = value * 60
            self._wake.notify_all()
        return self.interval_minutes()

    def load_interval_from_db(self):
        """从用户偏好恢复节流间隔；没有记录时用默认值。"""
        if self.db is None:
            return
        doc = self.db.briefing_preferences.find_one({"key": "transcript_queue"}) or {}
        value = doc.get("interval_minutes")
        if value:
            with self._lock:
                self._interval_seconds = max(MIN_INTERVAL_MINUTES, min(MAX_INTERVAL_MINUTES, float(value))) * 60

    def save_interval_to_db(self, minutes):
        if self.db is None:
            return
        self.db.briefing_preferences.update_one(
            {"key": "transcript_queue"},
            {"$set": {"key": "transcript_queue", "interval_minutes": minutes,
                      "updated_at": datetime.utcnow()}},
            upsert=True,
        )

    # ---- 队列操作 ----
    def enqueue(self, episodes, priority=PRIORITY_HISTORY, feed_id=None):
        """把剧集放进抓取队列；已在队列里的会按更小优先级提升。"""
        added = []
        with self._lock:
            known = {item["episode_id"] for item in self._items}
            if self._active:
                known.add(self._active["episode_id"])
            for episode in episodes:
                episode_id = str(episode.get("_id") or episode.get("episode_id") or "")
                guid = episode.get("guid") or ""
                if not episode_id or not guid.startswith("youtube:"):
                    continue
                if episode_id in known:
                    # 已在排队：新剧集可以把历史积压提上来（同时刷新入队时间，否则旧时间会把它压在后面）
                    promoted = False
                    for item in self._items:
                        if item["episode_id"] == episode_id and priority < item["priority"]:
                            item["priority"] = priority
                            item["enqueued_at"] = datetime.utcnow()
                            promoted = True
                    if promoted:
                        self._sort_locked()
                        self._wake.notify_all()
                    continue
                item = {
                    "episode_id": episode_id,
                    "feed_id": str(feed_id or episode.get("feed_id") or ""),
                    "guid": guid,
                    "title": episode.get("title") or "",
                    "priority": priority,
                    "enqueued_at": datetime.utcnow(),
                }
                self._items.append(item)
                known.add(episode_id)
                added.append(item)
            if added:
                self._sort_locked()
            self._wake.notify_all()
        if added:
            logger.info("字幕队列新增 %d 期（优先 %s）", len(added), priority)
        return len(added)

    def _sort_locked(self):
        self._items.sort(key=lambda item: (item["priority"], item["enqueued_at"]))

    def snapshot(self):
        """给接口/任务面板用：当前队列、当前抓取、间隔与预计时间。"""
        with self._lock:
            interval = self._interval_seconds
            now = datetime.utcnow()
            pending = []
            for index, item in enumerate(self._items):
                # 队首且当前空闲时立即可抓；否则按未用掉的剩余冷却时间起算
                slots = index + (1 if self._active else 0)
                eta = self._next_slot_delay(slots)
                pending.append({
                    "episode_id": item["episode_id"], "guid": item["guid"],
                    "title": item["title"], "feed_id": item["feed_id"],
                    "priority": item["priority"], "position": index + 1,
                    "enqueued_at": item["enqueued_at"].isoformat(),
                    "eta_seconds": eta,
                })
            active = None
            if self._active:
                active = {"episode_id": self._active["episode_id"], "guid": self._active["guid"],
                          "title": self._active["title"], "started_at": self._active.get("started_at")}
            return {"interval_minutes": interval / 60, "active": active, "pending": pending,
                    "queued_count": len(pending), "running": self._running,
                    "last_fetch_at": self._last_fetch_at.isoformat() if self._last_fetch_at else None,
                    "stats": dict(self._stats),
                    "next_fetch_in_seconds": self._next_slot_delay(1 if self._active else 0)}

    def _next_slot_delay(self, slots=1):
        """再等 slots 个节流窗口需要多少秒（0 表示随时可抓）。"""
        if self._last_fetch_at is None:
            return 0
        due = self._last_fetch_at + timedelta(seconds=self._interval_seconds)
        remaining = (due - datetime.utcnow()).total_seconds() + (slots - 1) * self._interval_seconds
        return max(0, int(remaining))

    def pending_count(self):
        with self._lock:
            return len(self._items)

    def clear(self):
        with self._lock:
            removed = len(self._items)
            self._items.clear()
        return removed

    # ---- 运行 ----
    def start(self):
        if self._running:
            return
        self._running = True
        self.load_interval_from_db()
        self._thread = threading.Thread(target=self._run_loop, name="transcript-queue", daemon=True)
        self._thread.start()
        logger.info("字幕抓取队列已启动（每 %.1f 分钟一期）", self.interval_minutes())

    def stop(self):
        self._running = False
        with self._lock:
            self._wake.notify_all()
        if self._thread:
            self._thread.join(timeout=5)

    def _run_loop(self):
        while self._running:
            with self._lock:
                while self._running and not self._items:
                    self._wake.wait(timeout=30)
                if not self._running:
                    return
                wait_seconds = self._next_slot_delay(1 if self._last_fetch_at else 0) if self._last_fetch_at else 0
                if wait_seconds > 0:
                    # 等待期间若有人插队或改间隔，会被 notify 唤醒后重算
                    self._wake.wait(timeout=min(wait_seconds, 30))
                    continue
                item = self._items.pop(0)
                item["started_at"] = datetime.utcnow()
                self._active = item
            try:
                self._fetch_one(item)
            except Exception as error:  # 单期失败不能拖垮队列
                logger.error("字幕队列抓取失败 %s: %s", item.get("title", ""), error)
                self._stats["failed"] += 1
            finally:
                with self._lock:
                    self._last_fetch_at = datetime.utcnow()
                    self._active = None

    def _fetch_one(self, item):
        """抓一期字幕：成功写库，429/无字幕写回错误原因。"""
        from bson import ObjectId
        from .youtube_service import YouTubeService, persist_transcript

        db = self.db
        episode = db.episodes.find_one({"_id": ObjectId(item["episode_id"])})
        if episode is None:
            return
        if episode.get("has_transcript"):
            return
        video_id = item["guid"].removeprefix("youtube:")
        started = time.time()
        transcript, error = YouTubeService.fetch_transcript(video_id)
        elapsed = time.time() - started
        if transcript:
            transcript["model"] = "youtube-transcript-api"
            if persist_transcript(db, episode, transcript):
                self._stats["completed"] += 1
                db.episodes.update_one({"_id": episode["_id"]}, {"$unset": {"transcript_fetch_error": ""}})
                logger.info("字幕队列 ✓ %s（%.1fs）", item.get("title", "")[:40], elapsed)
                return
        message = str(error or "unknown error")
        if "429" in message or "throttl" in message.lower():
            self._stats["throttled"] += 1
            # 被限流不判死：保留在队首稍后重试，避免永久丢失
            with self._lock:
                item["priority"] = max(item["priority"], PRIORITY_HISTORY) - 1
                item.pop("started_at", None)
                self._items.insert(0, item)
                # 限流时把下次窗口拉长到 3 倍，给出口 IP 冷却时间
                self._last_fetch_at = datetime.utcnow() + timedelta(seconds=self._interval_seconds * 2)
            logger.warning("字幕队列被限流，%s 稍后重试", item.get("title", "")[:40])
            return
        self._stats["failed"] += 1
        db.episodes.update_one({"_id": episode["_id"]},
                               {"$set": {"transcript_fetch_error": message[:200]}})


_queue_instance = None


def get_transcript_queue(db=None, queue=None):
    global _queue_instance
    if _queue_instance is None:
        _queue_instance = TranscriptQueue(db=db, queue=queue)
    elif db is not None:
        _queue_instance.db = db
    return _queue_instance


def start_transcript_queue(db, queue=None):
    instance = get_transcript_queue(db, queue)
    instance.start()
    return instance


def stop_transcript_queue():
    global _queue_instance
    if _queue_instance:
        _queue_instance.stop()
        _queue_instance = None
