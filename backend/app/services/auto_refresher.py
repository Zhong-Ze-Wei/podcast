# -*- coding: utf-8 -*-
"""
Feed Auto-Refresher

自动刷新订阅源服务
每五分钟检查：YouTube 每十五分钟更新，RSS 保持六小时，B站暂停自动更新。
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from .task_queue import task_queue

logger = logging.getLogger(__name__)


class FeedAutoRefresher:
    """
    自动刷新订阅源服务

    功能：
    - 每五分钟检查可自动更新的订阅源
    - YouTube 每十五分钟、RSS 每六小时检查一次（失败源按同一间隔重试）
    - B站仅保留手动刷新
    - 使用后台线程，不阻塞主服务
    """

    def __init__(self, db, interval_hours=5 / 60, stale_threshold_hours=6, youtube_stale_minutes=15, transcript_sweep_minutes=30, queue=task_queue):
        """
        Args:
            db: MongoDB数据库实例
            interval_hours: 检查间隔（小时）
            stale_threshold_hours: RSS 超过多久视为需要更新（小时）
            youtube_stale_minutes: YouTube 源超过多少分钟视为需要更新
            transcript_sweep_minutes: 存量字幕补捞间隔（分钟）
        """
        self.db = db
        self.queue = queue
        self.interval_hours = interval_hours
        self.stale_threshold = timedelta(hours=stale_threshold_hours)
        self.youtube_stale = timedelta(minutes=youtube_stale_minutes)
        self.transcript_sweep_interval = timedelta(minutes=transcript_sweep_minutes)
        self._running = False
        self._thread = None
        self._last_transcript_sweep = None
        self._last_trash_purge = None

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
        logger.info(
            f"Feed auto-refresher started (interval: {self.interval_hours}h, stale: {self.stale_threshold}, "
            f"youtube stale: {self.youtube_stale}, transcript sweep: {self.transcript_sweep_interval})"
        )

    def stop(self):
        """停止自动刷新服务"""
        self._running = False
        if self._thread:
            self._thread.join(timeout=5)
        logger.info("Feed auto-refresher stopped")

    def _run_loop(self):
        """主循环"""
        # 首次运行等待30秒，让服务完全启动
        time.sleep(30)

        while self._running:
            try:
                self._check_and_refresh_feeds()
            except Exception as e:
                logger.error(f"Auto-refresh error: {e}")

            try:
                self._maybe_sweep_transcripts()
            except Exception as e:
                logger.error(f"Transcript sweep error: {e}")

            try:
                self._maybe_purge_trash()
            except Exception as e:
                logger.error(f"Trash purge error: {e}")

            # 等待下一次检查
            sleep_seconds = self.interval_hours * 3600
            time.sleep(sleep_seconds)

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

    def _maybe_sweep_transcripts(self, limit=8):
        """每 self.transcript_sweep_minutes 把一批无字幕 YouTube 剧集送进抓取队列。

        存量剧集大多在频道 RSS 最近 15 条窗口外，常规刷新永远不碰；
        抓取本身由 transcript_queue_service 统一节流（默认 2 分钟一期），
        这里只负责把积压按发布时间排序投递。
        """
        from .transcript_queue_service import get_transcript_queue, PRIORITY_HISTORY

        now = datetime.utcnow()
        if self._last_transcript_sweep and now - self._last_transcript_sweep < self.transcript_sweep_interval:
            return
        self._last_transcript_sweep = now

        stuck = list(self.db.episodes.find(
            {"audio_type": "video/youtube", "has_transcript": {"$ne": True},
             "guid": {"$regex": "^youtube:"},
             # 已确认无字幕的（频道主没开字幕轨）不再重试，避免每轮空转打 YouTube
             "$nor": [{"transcript_fetch_error": {"$regex": "No subtitles|No transcript"}}]},
            {"_id": 1, "guid": 1, "title": 1, "owner_id": 1, "status": 1, "feed_id": 1, "published": 1},
        ).sort("published", 1).limit(limit))
        if not stuck:
            return
        get_transcript_queue(self.db, self.queue).enqueue(stuck, priority=PRIORITY_HISTORY)
        logger.info("已投递 %d 期历史字幕到抓取队列", len(stuck))

    def _check_and_refresh_feeds(self):
        """检查并刷新需要更新的订阅源"""
        from app.models.feed import Feed

        now = datetime.utcnow()
        stale_time = now - self.stale_threshold
        youtube_stale_time = now - self.youtube_stale

        # 失败源也按同一间隔重试；None 同时匹配尚未检查和旧文档缺失字段。
        feeds_to_refresh = list(
            self.db.feeds.find(
                {
                    "status": {"$in": [Feed.STATUS_ACTIVE, Feed.STATUS_ERROR]},
                    "type": {"$ne": Feed.TYPE_BILIBILI},
                    "$or": [
                        {"type": Feed.TYPE_YOUTUBE, "last_checked": {"$lt": youtube_stale_time}},
                        {"type": {"$ne": Feed.TYPE_YOUTUBE}, "last_checked": {"$lt": stale_time}},
                        {"last_checked": None},
                    ],
                }
            )
        )

        if not feeds_to_refresh:
            logger.debug("No feeds need refreshing")
            return

        logger.info(f"Found {len(feeds_to_refresh)} feeds to refresh")

        for feed in feeds_to_refresh:
            try:
                self._refresh_single_feed(feed)
            except Exception as e:
                logger.error(
                    f"Failed to refresh feed {feed.get('title', 'Unknown')}: {e}"
                )

    def _refresh_single_feed(self, feed):
        """Queue the same synchronization operation as a manual refresh."""
        from .feed_sync_service import FeedSyncService

        from app.models.feed import Feed

        feed_id = str(feed["_id"])

        def refresh(progress_callback=None):
            return FeedSyncService(self.db, queue=self.queue).refresh(feed_id, progress_callback)

        def record_failure(error):
            self.db.feeds.update_one(
                {"_id": feed["_id"]},
                {"$set": {
                    "status": Feed.STATUS_ERROR,
                    "check_error": str(error),
                    "last_checked": datetime.utcnow(),
                }},
            )

        return self.queue.submit_unique(
            "refresh", refresh, dedup_key=f"refresh:{feed_id}",
            feed_id=feed_id, owner_id=feed.get("owner_id"), on_failure=record_failure,
        )


# 全局实例
_refresher_instance = None


def start_auto_refresher(db, interval_hours=5 / 60, stale_threshold_hours=6, youtube_stale_minutes=15, transcript_sweep_minutes=30):
    """
    启动自动刷新服务

    Args:
        db: MongoDB数据库实例
        interval_hours: 检查间隔（小时），默认五分钟
        stale_threshold_hours: RSS 超过多久视为需要更新（小时），默认6小时
        youtube_stale_minutes: YouTube 源刷新间隔（分钟），默认15分钟
        transcript_sweep_minutes: 存量字幕补捞间隔（分钟），默认30分钟
    """
    global _refresher_instance

    if _refresher_instance is None:
        _refresher_instance = FeedAutoRefresher(
            db, interval_hours, stale_threshold_hours, youtube_stale_minutes, transcript_sweep_minutes
        )
        _refresher_instance.start()
    else:
        logger.warning("Auto-refresher already started")


def stop_auto_refresher():
    """停止自动刷新服务"""
    global _refresher_instance

    if _refresher_instance:
        _refresher_instance.stop()
        _refresher_instance = None
