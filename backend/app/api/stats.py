# -*- coding: utf-8 -*-
"""
Stats API

统计信息接口
"""
from flask import Blueprint

from ..models.episode import Episode
from ..services.user_episode_state import episode_ids_with
from .decorators import current_user, require_auth
from .utils import success_response

stats_bp = Blueprint("stats", __name__)


def get_db():
    from .. import get_db as _get_db
    return _get_db()


@stats_bp.route("", methods=["GET"])
@require_auth
def get_stats():
    """获取统计信息"""
    db = get_db()

    # Feed统计
    total_feeds = db.feeds.count_documents({})
    active_feeds = db.feeds.count_documents({"status": "active"})

    # Episode统计（未读按用户隔离：全库减去当前用户已读）
    total_episodes = db.episodes.count_documents({})
    read_ids = episode_ids_with(db, current_user()["id"], "is_read")
    unread_episodes = db.episodes.count_documents({"_id": {"$nin": read_ids}})

    # 按状态统计
    downloaded = db.episodes.count_documents({
        "status": {"$in": [
            Episode.STATUS_DOWNLOADED,
            Episode.STATUS_TRANSCRIBING,
            Episode.STATUS_TRANSCRIBED,
            Episode.STATUS_SUMMARIZING,
            Episode.STATUS_SUMMARIZED
        ]}
    })
    transcribed = db.episodes.count_documents({
        "status": {"$in": [
            Episode.STATUS_TRANSCRIBED,
            Episode.STATUS_SUMMARIZING,
            Episode.STATUS_SUMMARIZED
        ]}
    })
    summarized = db.episodes.count_documents({
        "status": Episode.STATUS_SUMMARIZED
    })

    # 任务统计
    pending_tasks = db.tasks.count_documents({"status": "pending"})
    processing_tasks = db.tasks.count_documents({"status": "processing"})

    return success_response({
        "feeds": {
            "total": total_feeds,
            "active": active_feeds
        },
        "episodes": {
            "total": total_episodes,
            "unread": unread_episodes,
            "downloaded": downloaded,
            "transcribed": transcribed,
            "summarized": summarized
        },
        "tasks": {
            "pending": pending_tasks,
            "processing": processing_tasks
        }
    })
