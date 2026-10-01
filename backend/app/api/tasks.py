# -*- coding: utf-8 -*-
"""
Tasks API

任务管理接口
"""
from flask import Blueprint, request
from bson import ObjectId
from bson.errors import InvalidId
from datetime import date

from ..services.task_queue import task_queue
from .utils import (
    success_response,
    error_response,
    paginated_response,
    get_pagination_params
)
from .decorators import current_owner_id, current_user, owner_filter, require_auth, require_role

tasks_bp = Blueprint("tasks", __name__)
PERSONAL_TASK_TYPES = ("briefing-report", "briefing-lab")


def _visible_task_query():
    return {"$or": [
        {"task_type": {"$nin": list(PERSONAL_TASK_TYPES)}},
        {"owner_id": current_owner_id()},
    ]}


def _task_is_visible(task):
    return task.get("task_type") not in PERSONAL_TASK_TYPES or task.get("owner_id") == current_owner_id()


def _task_is_owned(task):
    owner = current_owner_id()
    return owner is None or task.get("owner_id") == owner


def get_db():
    from .. import get_db as _get_db
    return _get_db()


@tasks_bp.route("", methods=["GET"])
@require_auth
def list_tasks():
    """获取任务列表"""
    db = get_db()
    page, per_page = get_pagination_params()

    # 构建查询条件
    query = _visible_task_query()

    status = request.args.get("status")
    if status:
        status_query = _task_status_query(status)
        if status_query is not None:
            query["status"] = status_query

    task_type = request.args.get("type")
    if task_type:
        query["task_type"] = task_type

    episode_id = request.args.get("episode_id")
    if episode_id:
        query["episode_id"] = episode_id

    feed_id = request.args.get("feed_id")
    if feed_id:
        query["feed_id"] = feed_id

    period_type = request.args.get("period_type")
    period_start = request.args.get("period_start")
    if period_type is not None:
        if period_type not in ("week", "month"):
            return error_response("周期请选择周或月", "INVALID_PERIOD", 400)
        query["report_period.type"] = period_type
    if period_start is not None:
        try:
            valid_date = date.fromisoformat(period_start)
        except ValueError:
            return error_response("周期日期须为 YYYY-MM-DD", "INVALID_PERIOD", 400)
        if valid_date.isoformat() != period_start:
            return error_response("周期日期须为 YYYY-MM-DD", "INVALID_PERIOD", 400)
        query["report_period.start"] = period_start

    # 查询
    total = db.tasks.count_documents(query)
    skip = (page - 1) * per_page

    tasks = list(
        db.tasks.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(per_page)
    )

    target_maps = _build_task_target_maps(db, tasks)
    data = [_format_task(task, target_maps) for task in tasks]

    return paginated_response(data, page, per_page, total)


@tasks_bp.route("/<task_id>", methods=["GET"])
@require_auth
def get_task(task_id):
    """获取任务状态"""
    db = get_db()

    # 先从任务队列获取 (内存中的最新状态)
    task = task_queue.get_status(task_id)

    if task is None:
        task = db.tasks.find_one({"task_id": task_id})
    if not task or not _task_is_visible(task):
        return error_response("Task not found", "TASK_NOT_FOUND", 404)

    target_maps = _build_task_target_maps(db, [task])
    return success_response(_format_task(task, target_maps))


@tasks_bp.route("/<task_id>/cancel", methods=["POST"])
@require_role("user", "admin")
def cancel_task(task_id):
    """取消任务"""
    task = task_queue.get_status(task_id)
    if task is None:
        task = get_db().tasks.find_one({"task_id": task_id})
    if not task or not _task_is_visible(task) or not _task_is_owned(task):
        return error_response("Task not found", "TASK_NOT_FOUND", 404)

    success = task_queue.cancel(task_id)

    if not success:
        return error_response(
            "任务已开始执行或不在当前执行队列中，无法安全取消",
            "CANNOT_CANCEL",
            400
        )

    return success_response(message="Task cancelled successfully")


def _build_task_target_maps(db, tasks: list[dict]) -> dict:
    """Fetch episode/feed display metadata for a page of tasks."""
    episode_oids = set()
    feed_oids = set()

    for task in tasks:
        episode_oid = _to_object_id(task.get("episode_id"))
        feed_oid = _to_object_id(task.get("feed_id"))
        if episode_oid:
            episode_oids.add(episode_oid)
        if feed_oid:
            feed_oids.add(feed_oid)

    episodes = {}
    if episode_oids:
        for episode in db.episodes.find(
            owner_filter({"_id": {"$in": list(episode_oids)}}),
            {"title": 1, "status": 1, "feed_id": 1},
        ):
            episodes[str(episode["_id"])] = episode
            if episode.get("feed_id"):
                feed_oids.add(episode["feed_id"])

    feeds = {}
    if feed_oids:
        for feed in db.feeds.find(
            owner_filter({"_id": {"$in": list(feed_oids)}}),
            {"title": 1},
        ):
            feeds[str(feed["_id"])] = feed

    return {"episodes": episodes, "feeds": feeds}


def _format_task(task: dict, target_maps: dict = None) -> dict:
    """格式化任务响应"""
    target_maps = target_maps or {"episodes": {}, "feeds": {}}
    episode_id = _string_id(task.get("episode_id"))
    feed_id = _string_id(task.get("feed_id"))
    episode = target_maps["episodes"].get(episode_id) if episode_id else None
    feed = None

    if episode and episode.get("feed_id"):
        feed_id = _string_id(episode.get("feed_id"))
    if feed_id:
        feed = target_maps["feeds"].get(feed_id)

    target_type = None
    target_id = None
    target_exists = True
    if episode_id:
        target_type = "episode"
        target_id = episode_id
        target_exists = episode is not None
    elif feed_id:
        target_type = "feed"
        target_id = feed_id
        target_exists = feed is not None

    return {
        "id": task.get("task_id"),
        "type": task.get("task_type"),
        "status": task.get("status"),
        "can_cancel": (_task_is_owned(task) and current_user().get("role") in ("user", "admin")
                       and task_queue.can_cancel(task.get("task_id"))),
        "report_period": task.get("report_period"),
        "progress": task.get("progress", 0),
        "progress_message": task.get("progress_message"),
        "episode_id": episode_id,
        "feed_id": feed_id,
        "episode_title": episode.get("title") if episode else None,
        "episode_status": episode.get("status") if episode else None,
        "feed_title": feed.get("title") if feed else None,
        "target_type": target_type,
        "target_id": target_id,
        "target_exists": target_exists,
        "result": task.get("result"),
        "error_message": task.get("error_message"),
        "created_at": _format_datetime(task.get("created_at")),
        "started_at": _format_datetime(task.get("started_at")),
        "completed_at": _format_datetime(task.get("completed_at"))
    }


def _to_object_id(value):
    if not value:
        return None
    if isinstance(value, ObjectId):
        return value
    try:
        return ObjectId(str(value))
    except (InvalidId, TypeError):
        return None


def _string_id(value):
    return str(value) if value else None


def _task_status_query(status: str):
    statuses = [item.strip() for item in status.split(",") if item.strip()]
    if not statuses:
        return None
    if len(statuses) > 1:
        return {"$in": statuses}
    return statuses[0]


def _format_datetime(dt) -> str:
    """格式化日期时间"""
    if dt:
        return dt.isoformat() + "Z" if hasattr(dt, "isoformat") else str(dt)
    return None
