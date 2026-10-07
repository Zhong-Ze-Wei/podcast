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

    def __init__(self, db, interval_hours=5 / 60, stale_threshold_hours=6, queue=task_queue):
        """
        Args:
            db: MongoDB数据库实例
            interval_hours: 检查间隔（小时）
            stale_threshold_hours: 超过多久视为需要更新（小时）
        """
        self.db = db
        self.queue = queue
        self.interval_hours = interval_hours
        self.stale_threshold = timedelta(hours=stale_threshold_hours)
        self._running = False
        self._thread = None

    def start(self):
        """启动自动刷新服务"""
        if self._running:
            logger.warning("Auto-refresher is already running")
            return

        self._running = True
        self._thread = threading.Thread(target=self._run_loop, daemon=True)
        self._thread.start()
        logger.info(
            f"Feed auto-refresher started (interval: {self.interval_hours}h, stale: {self.stale_threshold})"
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

            # 等待下一次检查
            sleep_seconds = self.interval_hours * 3600
            time.sleep(sleep_seconds)

    def _check_and_refresh_feeds(self):
        """检查并刷新需要更新的订阅源"""
        from app.models.feed import Feed

        now = datetime.utcnow()
        stale_time = now - self.stale_threshold
        youtube_stale_time = now - timedelta(minutes=15)

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


def start_auto_refresher(db, interval_hours=5 / 60, stale_threshold_hours=6):
    """
    启动自动刷新服务

    Args:
        db: MongoDB数据库实例
        interval_hours: 检查间隔（小时），默认五分钟
        stale_threshold_hours: 超过多久视为需要更新（小时），默认6小时
    """
    global _refresher_instance

    if _refresher_instance is None:
        _refresher_instance = FeedAutoRefresher(
            db, interval_hours, stale_threshold_hours
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
