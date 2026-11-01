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
# 同一期连续被限流的最大次数；超过后记为不可用，避免无限重试烧出口 IP
MAX_THROTTLE_ATTEMPTS = 3
# 每抓多少期主动轮换一次出口节点，把负载摊到多个 IP 上（0 = 关闭主动轮换）
PROACTIVE_ROTATE_EVERY = int(os.getenv("TRANSCRIPT_ROTATE_EVERY", "8") or 0)


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
        self._cooldown_until = None
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
        """从统一更新配置恢复节流间隔；没有记录时用默认值。"""
        if self.db is None:
            return
        from . import refresh_settings

        value = refresh_settings.get_settings(self.db)["transcript_interval_minutes"]
        with self._lock:
            self._interval_seconds = max(MIN_INTERVAL_MINUTES, min(MAX_INTERVAL_MINUTES, float(value))) * 60

    def save_interval_to_db(self, minutes):
        if self.db is None:
            return
        from . import refresh_settings

        refresh_settings.save_settings(self.db, {"transcript_interval_minutes": minutes})

    def sync_interval_from_settings(self):
        """每轮抓取前对齐设置页的改动（进程内缓存会过期）。"""
        if self.db is None:
            return
        from . import refresh_settings

        minutes = refresh_settings.get_settings(self.db)["transcript_interval_minutes"]
        seconds = max(MIN_INTERVAL_MINUTES, min(MAX_INTERVAL_MINUTES, float(minutes))) * 60
        with self._lock:
            if seconds != self._interval_seconds:
                self._interval_seconds = seconds
                self._wake.notify_all()

    # ---- 队列操作 ----
    # 轨道探测结论：没有字幕轨的期不再入队，避免"抓一次失败才知道、下轮又重试"
    CAPTION_NONE = "none"          # 确认没有字幕轨
    CAPTION_UNKNOWN = "unknown"    # 探测失败（网络/限流），稍后仍可再试

    def _caption_state(self, episode):
        """读取已有探测结论，返回 none / has / unknown。"""
        if episode.get("has_transcript") or self.db.transcripts.find_one({"episode_id": episode["_id"]}):
            return "has"
        state = episode.get("caption_tracks_state")
        if state == self.CAPTION_NONE:
            return "none"
        if state == "has":
            return "has"
        return "unknown"

    def probe_captions(self, episode, proxy=None):
        """探测并落库一期的字幕轨道状态；返回 has / none / unknown。

        只读元数据不下载字幕，所以能安全地放在入队前跑。

        注意：yt-dlp 有时既不报错误也不返回字幕轨（POT 校验、地区限制、
        自动字幕被隐藏），此时"没有轨道"可能是假阴性。所以探测出的空轨道
        只记为 unavailable，真正判死要等抓取阶段明确返回"字幕已禁用/不存在"。
        """
        from .youtube_service import YouTubeService

        video_id = (episode.get("guid") or "").removeprefix("youtube:")
        if not video_id:
            return self.CAPTION_UNKNOWN
        tracks, error = YouTubeService.probe_captions(video_id, proxy=proxy)
        if tracks is None:
            # 探测本身失败（429、连不上）：不写死结论，留待以后重试
            logger.info("字幕轨道探测失败 %s: %s", episode.get("title", "")[:40], str(error)[:80])
            return self.CAPTION_UNKNOWN
        if not tracks["available"]:
            # 不标 none：可能是假阴性，仍需抓一次才能确认
            self.db.episodes.update_one(
                {"_id": episode["_id"]},
                {"$set": {"caption_tracks_state": self.CAPTION_UNKNOWN,
                          "caption_tracks": {"manual": [], "automatic": []},
                          "caption_probed_at": datetime.utcnow()}},
            )
            return self.CAPTION_UNKNOWN
        self.db.episodes.update_one(
            {"_id": episode["_id"]},
            {"$set": {"caption_tracks_state": "has",
                      "caption_tracks": {"manual": tracks["manual"], "automatic": tracks["automatic"]},
                      "caption_probed_at": datetime.utcnow()}},
        )
        return "has"

    def _mark_no_captions(self, episode, tracks=None):
        """落一个明确的"没有字幕轨"结论，补捞与队列都不会再碰它。"""
        self.db.episodes.update_one(
            {"_id": episode["_id"]},
            {"$set": {"caption_tracks_state": self.CAPTION_NONE,
                      "caption_tracks": {"manual": [], "automatic": []} if tracks is None else {"manual": tracks["manual"], "automatic": tracks["automatic"]},
                      "caption_probed_at": datetime.utcnow(),
                      "transcript_fetch_error": "No subtitles available for this video"}},
        )

    def enqueue(self, episodes, priority=PRIORITY_HISTORY, feed_id=None):
        """把剧集放进抓取队列；已在队列里的会按更小优先级提升。

        已确认没有字幕轨的期直接跳过（不入队、不重试）。
        """
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
                # 已确认没有字幕轨：不再入队，省掉一次注定失败的网络请求
                if episode.get("caption_tracks_state") == self.CAPTION_NONE:
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
        if self._last_fetch_at is None and self._cooldown_until is None:
            return 0
        now = datetime.utcnow()
        # 限流冷却优先：到点前一律不抓；到点后清空，恢复正常节奏
        if self._cooldown_until is not None:
            remaining = (self._cooldown_until - now).total_seconds()
            if remaining > 0:
                return max(0, int(remaining))
            self._cooldown_until = None
        base = self._last_fetch_at or now
        due = base + timedelta(seconds=self._interval_seconds)
        remaining = (due - now).total_seconds() + (slots - 1) * self._interval_seconds
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
            self.sync_interval_from_settings()
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
            self.fetch_next()

    def _proxy_pool(self):
        """直连代理池（YOUTUBE_PROXY_POOL）；空列表表示未配置，走 Clash 轮换。"""
        from ..config import get_config
        return list(getattr(get_config(), "YOUTUBE_PROXY_POOL", []) or [])

    def _probe_proxy(self, proxy: str) -> bool:
        """探测代理对 YouTube 是否可达。"""
        try:
            import requests
            resp = requests.get("https://www.youtube.com/robots.txt",
                                proxies={"http": proxy, "https": proxy}, timeout=(3, 6))
            return resp.status_code == 200
        except Exception:
            return False

    def _rotate_exit(self, reason: str) -> str:
        """换到下一个可用出口：代理池直连优先，未配置时走 Clash 轮换。"""
        pool = self._proxy_pool()
        if pool:
            # 池内轮换：逐个探活直到找到可用代理，代码内完成，不依赖 Clash
            start = (getattr(self, "_pool_index", -1) + 1) % len(pool)
            for offset in range(len(pool)):
                index = (start + offset) % len(pool)
                candidate = pool[index]
                if self._probe_proxy(candidate):
                    self._pool_index = index
                    self._active_proxy = candidate
                    logger.info("字幕队列换代理池出口（%s）→ %s", reason, self._deauth(candidate))
                    return candidate
            logger.warning("代理池 %d 个出口全部不可用", len(pool))
            return ""
        try:
            from . import clash_service
            if not clash_service.available():
                return ""
            node = clash_service.rotate_next_healthy()
            if node:
                logger.info("字幕队列换出口（%s）→ %s", reason, node)
            return node
        except Exception as error:
            logger.debug("出口轮换不可用：%s", error)
            return ""

    @staticmethod
    def _deauth(proxy: str) -> str:
        """日志里隐藏代理凭据。"""
        import re
        return re.sub(r"(://[^/@]+)@", "://***@", proxy)

    def fetch_next(self):
        """同步抓一期队首（队列线程与测试共用）；没有待抓时返回 None。"""
        # 主动轮换：每 N 期换一个出口 IP，避免单个 IP 请求密度过高被限流
        if PROACTIVE_ROTATE_EVERY and self._stats["completed"] and self._stats["completed"] % PROACTIVE_ROTATE_EVERY == 0:
            self._rotate_exit("主动轮换")
        with self._lock:
            if not self._items:
                return None
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
        return item

    def _fetch_one(self, item):
        """抓一期字幕：先补元数据，再抓字幕；429/无字幕写回错误原因。"""
        from bson import ObjectId

        from .feed_sync_service import _humanize_subtitle_error, _needs_youtube_metadata, enrich_video_metadata
        from .youtube_service import YouTubeService, persist_transcript

        db = self.db
        episode = db.episodes.find_one({"_id": ObjectId(item["episode_id"])})
        if episode is None:
            return
        video_id = item["guid"].removeprefix("youtube:")
        # 列表同步只拿到标题，时长/真实发布日期/简介要在这里按节流补一次
        if _needs_youtube_metadata(episode):
            enrich_video_metadata(db, episode)
            episode = db.episodes.find_one({"_id": episode["_id"]}) or episode
        # 标记缺失但字幕已在库（历史残留）时不重复请求平台
        if episode.get("has_transcript") or db.transcripts.find_one({"episode_id": episode["_id"]}):
            return
        started = time.time()
        # 代理池模式下用当前池出口；未配置时用默认 YOUTUBE_PROXY
        transcript, error = YouTubeService.fetch_transcript(video_id, proxy=getattr(self, "_active_proxy", None))
        elapsed = time.time() - started
        if transcript:
            transcript["model"] = "youtube-transcript-api"
            if persist_transcript(db, episode, transcript):
                self._stats["completed"] += 1
                db.episodes.update_one({"_id": episode["_id"]}, {"$unset": {"transcript_fetch_error": ""}})
                logger.info("字幕队列 ✓ %s（%.1fs）", item.get("title", "")[:40], elapsed)
                return
        message = str(error or "unknown error")
        if "429" in message or "throttl" in message.lower() or "无法连接" in message or "暂时限制" in message:
            self._stats["throttled"] += 1
            # 计数必须落库：只存在内存 item 上时，这期被放弃后补捞又会从 0 重来，
            # 于是同一期在 55 次限流里被反复献祭。
            attempts = int(episode.get("transcript_throttle_attempts") or 0) + 1
            # 已放弃的期不再累计、不再换 IP，直接跳过
            if episode.get("transcript_gave_up_at"):
                logger.debug("跳过已放弃的 %s", item.get("title", "")[:40])
                return
            # 连续限流不再无限重试：同一期反复打只会更糟
            if attempts > MAX_THROTTLE_ATTEMPTS:
                self._stats["failed"] += 1
                db.episodes.update_one({"_id": episode["_id"]},
                                       {"$set": {"transcript_fetch_error": _humanize_subtitle_error(message),
                                                 "transcript_throttle_attempts": attempts,
                                                 "transcript_gave_up_at": datetime.utcnow()}})
                logger.warning("字幕队列放弃 %s：连续 %d 次被限流", item.get("title", "")[:40], attempts)
                return
            db.episodes.update_one({"_id": episode["_id"]},
                                   {"$set": {"transcript_throttle_attempts": attempts}})
            item["throttle_attempts"] = attempts
            # 先换出口 IP：换了新 IP 后不需要长退避，短冷却即可重试
            rotated = self._rotate_exit(f"429×{attempts}")
            if rotated:
                backoff = min(self._interval_seconds * attempts, 5 * 60)
            else:
                backoff = min(self._interval_seconds * (2 ** attempts), 30 * 60)
            with self._lock:
                item.pop("started_at", None)
                # 退避期内排到队尾（不占队首），让其他期先试
                item["priority"] = PRIORITY_HISTORY + attempts
                self._items.append(item)
                self._sort_locked()
                # 冷却单独计时，不与常规 interval 叠加
                self._cooldown_until = datetime.utcnow() + timedelta(seconds=backoff)
                self._wake.notify_all()
            logger.warning("字幕队列被限流（第 %d 次，%s），%s 退避 %d 秒后重试",
                           attempts, f"已换出口 {rotated}" if rotated else "未换出口", item.get("title", "")[:40], backoff)
            return
        self._stats["failed"] += 1
        # 明确"没有字幕/字幕被禁用"是终局结论，落成轨道状态，补捞与队列都不再碰
        if "No subtitles" in message or "No transcript" in message or "disabled" in message.lower():
            self._mark_no_captions(episode)
            db.episodes.update_one({"_id": episode["_id"]},
                                   {"$set": {"transcript_fetch_error": _humanize_subtitle_error(message)}})
        else:
            db.episodes.update_one({"_id": episode["_id"]},
                                   {"$set": {"transcript_fetch_error": _humanize_subtitle_error(message)}})


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
