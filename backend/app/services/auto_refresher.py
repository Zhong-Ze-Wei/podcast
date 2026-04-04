# -*- coding: utf-8 -*-
"""
Feed Auto-Refresher

自动刷新订阅源服务
每小时检查并更新有需要的订阅源
"""

import logging
import threading
import time
from datetime import datetime, timedelta
from bson import ObjectId

logger = logging.getLogger(__name__)


class FeedAutoRefresher:
    """
    自动刷新订阅源服务

    功能：
    - 每小时自动检查所有订阅源
    - 对于超过6小时未更新的订阅源自动刷新
    - 使用后台线程，不阻塞主服务
    """

    def __init__(self, db, interval_hours=1, stale_threshold_hours=6):
        """
        Args:
            db: MongoDB数据库实例
            interval_hours: 检查间隔（小时）
            stale_threshold_hours: 超过多久视为需要更新（小时）
        """
        self.db = db
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
        from app.services.rss_service import RSSService
        from app.models.episode import Episode

        now = datetime.utcnow()
        stale_time = now - self.stale_threshold

        # 查找需要更新的订阅源（active状态且超过阈值未更新）
        feeds_to_refresh = list(
            self.db.feeds.find(
                {
                    "status": "active",
                    "$or": [
                        {"last_checked": {"$lt": stale_time}},
                        {"last_checked": {"$exists": False}},
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
        """刷新单个订阅源"""
        from app.services.rss_service import RSSService
        from app.models.episode import Episode

        feed_id = feed["_id"]
        rss_url = feed["rss_url"]

        logger.info(f"Refreshing feed: {feed.get('title', 'Unknown')}")

        # 解析RSS
        feed_info, error = RSSService.parse_feed(rss_url)

        if error:
            self.db.feeds.update_one(
                {"_id": feed_id},
                {
                    "$set": {
                        "status": "error",
                        "check_error": error,
                        "last_checked": datetime.utcnow(),
                    }
                },
            )
            logger.warning(f"Feed refresh failed: {error}")
            return

        # 获取已有episodes
        existing_guids = set(
            ep["guid"]
            for ep in self.db.episodes.find({"feed_id": feed_id}, {"guid": 1})
        )

        # 插入新episodes
        new_episodes = []
        episodes = feed_info.get("episodes", [])

        for ep_info in episodes:
            if ep_info["guid"] not in existing_guids:
                ep_doc = Episode.create(
                    feed_id=feed_id,
                    guid=ep_info["guid"],
                    title=ep_info["title"],
                    summary=ep_info.get("summary"),
                    content=ep_info.get("content"),
                    link=ep_info.get("link"),
                    published=ep_info.get("published"),
                    audio_url=ep_info.get("audio_url"),
                    audio_type=ep_info.get("audio_type"),
                    audio_size=ep_info.get("audio_size"),
                    duration=ep_info.get("duration", 0),
                    image=ep_info.get("image"),
                    chapters_url=ep_info.get("chapters_url"),
                    transcript_url=ep_info.get("transcript_url"),
                )
                new_episodes.append(ep_doc)

        if new_episodes:
            self.db.episodes.insert_many(new_episodes)
            logger.info(
                f"Added {len(new_episodes)} new episodes to {feed.get('title', 'Unknown')}"
            )

        # 更新feed信息
        self.db.feeds.update_one(
            {"_id": feed_id},
            {
                "$set": {
                    "title": feed_info.get("title", feed.get("title")),
                    "description": feed_info.get(
                        "description", feed.get("description")
                    ),
                    "image": feed_info.get("image", feed.get("image")),
                    "website": feed_info.get("link", feed.get("website")),
                    "status": "active",
                    "last_checked": datetime.utcnow(),
                    "episode_count": len(episodes),
                },
                "$unset": {"check_error": ""},
            },
        )

        logger.info(f"Feed refreshed successfully: {feed.get('title', 'Unknown')}")


# 全局实例
_refresher_instance = None


def start_auto_refresher(db, interval_hours=1, stale_threshold_hours=6):
    """
    启动自动刷新服务

    Args:
        db: MongoDB数据库实例
        interval_hours: 检查间隔（小时），默认1小时
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
