# -*- coding: utf-8 -*-
"""
Summaries API

摘要管理接口
"""
from flask import Blueprint, request
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime

from ..models.episode import Episode
from ..models.summary import Summary
from ..services.task_queue import task_queue
from .utils import success_response, error_response

summaries_bp = Blueprint("summaries", __name__)


def get_db():
    from .. import get_db as _get_db
    return _get_db()


@summaries_bp.route("/<episode_id>", methods=["GET"])
def get_summary(episode_id):
    """获取单集摘要"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    summary = db.summaries.find_one({"episode_id": oid})
    if not summary:
        return error_response("Summary not found", "SUMMARY_NOT_FOUND", 404)

    return success_response(Summary.to_response(summary))


@summaries_bp.route("/<episode_id>", methods=["POST"])
def create_summary(episode_id):
    """创建摘要任务 (异步)"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    # 检查是否可以生成摘要
    if not Episode.can_summarize(episode):
        return error_response(
            "Episode cannot be summarized in current state",
            "INVALID_STATE",
            400
        )

    # 检查是否有进行中的任务
    existing_task = db.tasks.find_one({
        "episode_id": str(oid),
        "task_type": "summarize",
        "status": {"$in": ["pending", "processing"]}
    })
    if existing_task:
        return error_response(
            "Summarize task already in progress",
            "TASK_IN_PROGRESS",
            409
        )

    # 提交摘要任务
    def do_summarize(progress_callback=None):
        return _summarize_sync(str(oid), progress_callback)

    task_id = task_queue.submit(
        task_type="summarize",
        func=do_summarize,
        episode_id=str(oid)
    )

    # 更新状态为摘要中
    db.episodes.update_one(
        {"_id": oid},
        {"$set": {"status": Episode.STATUS_SUMMARIZING}}
    )

    return success_response({
        "task_id": task_id,
        "status": "queued"
    })


def _summarize_sync(episode_id: str, progress_callback=None):
    """同步执行摘要生成"""
    db = get_db()
    oid = ObjectId(episode_id)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        raise ValueError("Episode not found")

    # 获取转录文本
    transcript = db.transcripts.find_one({"episode_id": oid})
    if not transcript:
        raise ValueError("Transcript not found")

    transcript_text = transcript.get("text", "")
    if not transcript_text:
        raise ValueError("Transcript is empty")

    if progress_callback:
        progress_callback(10)

    # TODO: 集成本地LLM生成摘要
    # 可参考 D:\zz\try.py 中的本地模型调用方式

    # 模拟摘要结果
    summary_text = f"[Placeholder] Summary for episode: {episode.get('title', '')}"
    keywords = []
    highlights = []

    if progress_callback:
        progress_callback(80)

    # 创建摘要文档
    summary_doc = Summary.create(
        episode_id=oid,
        content=summary_text,
        keywords=keywords,
        highlights=highlights,
        model="placeholder"
    )

    # 检查是否已存在
    existing = db.summaries.find_one({"episode_id": oid})
    if existing:
        db.summaries.update_one(
            {"episode_id": oid},
            {"$set": {
                "content": summary_text,
                "keywords": keywords,
                "highlights": highlights,
                "model": "placeholder",
                "updated_at": datetime.utcnow()
            }}
        )
    else:
        db.summaries.insert_one(summary_doc)

    if progress_callback:
        progress_callback(90)

    # 更新episode状态
    db.episodes.update_one(
        {"_id": oid},
        {"$set": {
            "status": Episode.STATUS_SUMMARIZED,
            "updated_at": datetime.utcnow()
        }}
    )

    if progress_callback:
        progress_callback(100)

    return {"summary_length": len(summary_text)}


@summaries_bp.route("/<episode_id>", methods=["DELETE"])
def delete_summary(episode_id):
    """删除摘要"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    result = db.summaries.delete_one({"episode_id": oid})
    if result.deleted_count == 0:
        return error_response("Summary not found", "SUMMARY_NOT_FOUND", 404)

    # 如果状态是summarized，回退到transcribed
    if episode.get("status") == Episode.STATUS_SUMMARIZED:
        db.episodes.update_one(
            {"_id": oid},
            {"$set": {"status": Episode.STATUS_TRANSCRIBED}}
        )

    return success_response(message="Summary deleted successfully")
