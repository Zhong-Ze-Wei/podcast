# -*- coding: utf-8 -*-
"""
Feed Auto-Refresher

后台静默同步订阅源：按设置页配置的间隔逐源刷新，同一时刻只打一个源。
"""
import logging
import threading
import time
from datetime import datetime, timedelta

from . import refresh_settings
from .task_queue import task_queue

logger = logging.getLogger(__name__)


class FeedAutoRefresher:
    """
    自动刷新订阅源服务

    功能：
    - 按 check_interval_minutes 定时巡检，YouTube 与 RSS 共用同一个更新间隔
    - 每轮最多提交 feeds_per_tick 个源，失败源按同一间隔重试
    - B站仅保留手动刷新
    - 刷新进度写内存状态给「更新动态」用，不生成面向用户的任务记录
    - 使用后台线程，不阻塞主服务
    """

    def __init__(self, db, queue=task_queue):
        """
        Args:
            db: MongoDB数据库实例
            queue: 任务队列（默认全局实例）
        """
        self.db = db
        self.queue = queue
        self._running = False
        self._thread = None
        self._last_transcript_sweep = None
        self._last_trash_purge = None
        self._last_daily_report = None
        # 每日完成统计：{YYYY-MM-DD: {"done": n, "failed": n, "feeds": n}}
        self._daily = {"date": None, "done": 0, "failed": 0, "feeds": 0, "last_feed": ""}

    # ---- 生命周期 ----
    def start(self):
        """启动自动刷新服务"""
        if self._running:
            logger.warning("Auto-refresher is already running")
            return

        self._running = True
        # 启动即视为刚扫过一轮：避免每次重启服务都立刻打一轮外部接口
        self._last_transcript_sweep = datetime.utcnow()
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info("Feed auto-refresher started")

    def stop(self):
        """停止自动刷新服务"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Feed auto-refresher stopped")

    def _settings(self):
        return refresh_settings.get_settings(self.db)

    def _run_loop(self):
        """主循环：每次都用最新配置计算下一轮等待时间。"""
        # 首次运行等待30秒，让服务完全启动
        time.sleep(30)

        while self._running:
            settings = self._settings()
            try:
                if settings["enabled"]:
                    self._check_and_refresh_feeds(settings)
                    self._maybe_sweep_transcripts(settings)
            except Exception as e:
                logger.error(f"Auto-refresh error: {e}")

            try:
                self._maybe_purge_trash()
            except Exception as e:
                logger.error(f"Trash purge error: {e}")

            time.sleep(max(60, settings["check_interval_minutes"] * 60))

    # ---- 维护任务 ----
    def _ensure_youtube_exit(self, max_rotations: int = 6) -> bool:
        """确保默认代理通道当前出口能访问 YouTube（探 watch 页），不行就轮换，直到可用或试满。"""
        from .youtube_service import YouTubeService

        for _ in range(max_rotations + 1):
            if YouTubeService.watchpage_reachable():
                return True
            from .clash_service import rotate_next
            if not rotate_next():
                return False
        return YouTubeService.watchpage_reachable()

    def _maybe_purge_trash(self, interval_hours=24):
        """每天清一次过期垃圾箱（超过保留期的删除数据物理清除）。"""
        from . import trash_service

        now = datetime.utcnow()
        if self._last_trash_purge and now - self._last_trash_purge < timedelta(hours=interval_hours):
            return
        self._last_trash_purge = now
        purged = trash_service.purge_expired(self.db)
        if purged:
            logger.info("Trash purge: %d 个过期桶已物理清除", purged)

    # ---- 订阅刷新 ----
    def _due_feeds(self, settings, now=None):
        """按统一间隔挑出到期源，随机打散避免每次都是同样顺序。"""
        import random

        from app.models.feed import Feed

        now = now or datetime.utcnow()
        stale_time = now - refresh_settings.feed_interval(settings)
        # 失败源也按同一间隔重试；None 同时匹配尚未检查和旧文档缺失字段。
        feeds = list(
            self.db.feeds.find(
                {
                    "status": {"$in": [Feed.STATUS_ACTIVE, Feed.STATUS_ERROR]},
                    "type": {"$ne": Feed.TYPE_BILIBILI},
                    "$or": [
                        {"last_checked": {"$lt": stale_time}},
                        {"last_checked": None},
                    ],
                }
            )
        )
        random.shuffle(feeds)
        return feeds

    def _check_and_refresh_feeds(self, settings=None):
        """检查并刷新需要更新的订阅源，每轮最多 feeds_per_tick 个。"""
        settings = settings or self._settings()
        feeds_to_refresh = self._due_feeds(settings)
        if not feeds_to_refresh:
            logger.debug("No feeds need refreshing")
            return []
        batch = feeds_to_refresh[:settings["feeds_per_tick"]]
        logger.info("Found %d feeds due, refreshing %d this round", len(feeds_to_refresh), len(batch))
        submitted = []
        for feed in batch:
            try:
                submitted.append(self._refresh_single_feed(feed))
            except Exception as e:
                logger.error(f"Failed to refresh feed {feed.get('title', 'Unknown')}: {e}")
        return submitted

    def _refresh_single_feed(self, feed):
        """提交一次与手动刷新完全相同、但静默执行的同步操作。"""
        from .feed_sync_service import FeedSyncService

        from app.models.feed import Feed

        feed_id = str(feed["_id"])

        def refresh(progress_callback=None):
            return FeedSyncService(self.db, queue=self.queue).refresh(feed_id, progress_callback)

        def record_failure(error):
            self._record(feed, False)
            self.db.feeds.update_one(
                {"_id": feed["_id"]},
                {"$set": {
                    "status": Feed.STATUS_ERROR,
                    "check_error": str(error),
                    "last_checked": datetime.utcnow(),
                }},
            )

        def record_success(result):
            self._record(feed, True)

        return self.queue.submit_silent(
            "refresh", refresh, dedup_key=f"refresh:{feed_id}",
            feed_id=feed_id, owner_id=feed.get("owner_id"),
            on_failure=record_failure, on_success=record_success,
        )

    # ---- 每日完成统计 ----
    def _record(self, feed, ok):
        """累计当天的自动更新结果，供任务面板展示“已完成 x/y 更新”。"""
        today = datetime.utcnow().date().isoformat()
        if self._daily["date"] != today:
            self._daily = {"date": today, "done": 0, "failed": 0, "feeds": 0, "last_feed": ""}
        self._daily["feeds"] += 1
        if ok:
            self._daily["done"] += 1
        else:
            self._daily["failed"] += 1
        self._daily["last_feed"] = feed.get("title", "")

    def daily_summary(self, settings=None):
        """当天已完成的自动更新；跨天时清零。"""
        today = datetime.utcnow().date().isoformat()
        if self._daily["date"] != today:
            return {"date": today, "done": 0, "failed": 0, "feeds": 0, "last_feed": ""}
        return dict(self._daily)

    # ---- 存量字幕补捞 ----
    def _maybe_sweep_transcripts(self, settings=None, *, interval_minutes=None, limit=None):
        """按设置的间隔把一批无字幕 YouTube 剧集送进抓取队列。

        存量剧集大多在频道 RSS 最近 15 条窗口外，常规刷新永远不碰；
        抓取本身由 transcript_queue_service 统一节流，这里只负责投递。
        投递前先探测字幕轨道：确认没有轨道的不再入队，避免抓一次失败才知道、
        下轮又重试一遍。
        """
        from .transcript_queue_service import PRIORITY_HISTORY, get_transcript_queue

        settings = settings or self._settings()
        interval = timedelta(minutes=interval_minutes or settings["transcript_sweep_minutes"])
        limit = limit or settings["transcript_sweep_batch"]

        now = datetime.utcnow()
        if self._last_transcript_sweep and now - self._last_transcript_sweep < interval:
            return 0
        self._last_transcript_sweep = now

        query = {
            "audio_type": "video/youtube", "has_transcript": {"$ne": True},
            "guid": {"$regex": "^youtube:"},
            # 已确认无字幕的（频道主没开字幕轨）不再重试，避免每轮空转打 YouTube；
            # 连续限流到上限的也已放弃，捞回来只会重复献祭同一个出口 IP
            "transcript_gave_up_at": {"$exists": False},
            "caption_tracks_state": {"$ne": "none"},
            "$nor": [{"transcript_fetch_error": {"$regex": "No subtitles|No transcript"}}],
        }
        projection = {"_id": 1, "guid": 1, "title": 1, "owner_id": 1, "status": 1,
                      "feed_id": 1, "published": 1, "caption_tracks_state": 1}
        queue = get_transcript_queue(self.db, self.queue)

        # 先给从没探测过的期做轨道探测；没有轨道的结论不可靠（可能假阴性），
        # 所以探测只是让"确认有字幕"的期优先，其余照样排队，由抓取阶段定论
        unprobed = list(self.db.episodes.find(
            {**query, "caption_tracks_state": {"$exists": False}}, projection
        ).sort("published", 1).limit(limit))
        confirmed = []
        for episode in unprobed:
            if queue.probe_captions(episode) == "has":
                confirmed.append(episode)

        stuck = confirmed + list(self.db.episodes.find(
            {**query, "caption_tracks_state": {"$in": ["has", "unknown"]}}, projection
        ).sort("published", 1).limit(max(0, limit - len(confirmed))))
        if not stuck:
            return 0
        queue.enqueue(stuck, priority=PRIORITY_HISTORY)
        logger.info("已投递 %d 期历史字幕到抓取队列（新探测 %d 期，确认有轨道 %d 期）",
                    len(stuck), len(unprobed), len(confirmed))
        return len(stuck)


# 全局实例
_refresher_instance = None


def start_auto_refresher(db, queue=task_queue):
    """启动自动刷新服务；刷新节奏存在设置里，运行时改完即生效。"""
    global _refresher_instance

    if _refresher_instance is None:
        _refresher_instance = FeedAutoRefresher(db, queue=queue)
        _refresher_instance.start()
    else:
        logger.warning("Auto-refresher already started")
    return _refresher_instance


def stop_auto_refresher():
    """停止自动刷新服务"""
    global _refresher_instance

    if _refresher_instance:
        _refresher_instance.stop()
        _refresher_instance = None


def get_auto_refresher():
    return _refresher_instance
