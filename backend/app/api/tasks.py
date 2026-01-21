# -*- coding: utf-8 -*-
"""
Tasks API

任务管理接口
"""
from flask import Blueprint, request
from bson import ObjectId
from bson.errors import InvalidId

from ..services.task_queue import task_queue
from .utils import (
    success_response,
    error_response,
    paginated_response,
    get_pagination_params
)

tasks_bp = Blueprint("tasks", __name__)


def get_db():
    from .. import get_db as _get_db
    return _get_db()


@tasks_bp.route("", methods=["GET"])
def list_tasks():
    """获取任务列表"""
    db = get_db()
    page, per_page = get_pagination_params()

    # 构建查询条件
    query = {}

    status = request.args.get("status")
    if status:
        query["status"] = status

    task_type = request.args.get("type")
    if task_type:
        query["task_type"] = task_type

    episode_id = request.args.get("episode_id")
    if episode_id:
        query["episode_id"] = episode_id

    feed_id = request.args.get("feed_id")
    if feed_id:
        query["feed_id"] = feed_id

    # 查询
    total = db.tasks.count_documents(query)
    skip = (page - 1) * per_page

    tasks = list(
        db.tasks.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(per_page)
    )

    # 转换格式
    data = []
    for task in tasks:
        data.append(_format_task(task))

    return paginated_response(data, page, per_page, total)


@tasks_bp.route("/<task_id>", methods=["GET"])
def get_task(task_id):
    """获取任务状态"""
    # 先从任务队列获取 (内存中的最新状态)
    task = task_queue.get_status(task_id)

    if task:
        return success_response(_format_task(task))

    # 从数据库获取
    db = get_db()
    task = db.tasks.find_one({"task_id": task_id})

    if not task:
        return error_response("Task not found", "TASK_NOT_FOUND", 404)

    return success_response(_format_task(task))


@tasks_bp.route("/<task_id>/cancel", methods=["POST"])
def cancel_task(task_id):
    """取消任务"""
    success = task_queue.cancel(task_id)

    if not success:
        # 检查任务是否存在
        task = task_queue.get_status(task_id)
        if not task:
            db = get_db()
            task = db.tasks.find_one({"task_id": task_id})
            if not task:
                return error_response("Task not found", "TASK_NOT_FOUND", 404)

        return error_response(
            "Cannot cancel task (only pending tasks can be cancelled)",
            "CANNOT_CANCEL",
            400
        )

    return success_response(message="Task cancelled successfully")


def _format_task(task: dict) -> dict:
    """格式化任务响应"""
    return {
        "id": task.get("task_id"),
        "type": task.get("task_type"),
        "status": task.get("status"),
        "progress": task.get("progress", 0),
        "episode_id": task.get("episode_id"),
        "feed_id": task.get("feed_id"),
        "result": task.get("result"),
        "error_message": task.get("error_message"),
        "created_at": _format_datetime(task.get("created_at")),
        "started_at": _format_datetime(task.get("started_at")),
        "completed_at": _format_datetime(task.get("completed_at"))
    }


def _format_datetime(dt) -> str:
    """格式化日期时间"""
    if dt:
        return dt.isoformat() + "Z" if hasattr(dt, "isoformat") else str(dt)
    return None
