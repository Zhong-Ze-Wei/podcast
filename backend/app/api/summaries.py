# -*- coding: utf-8 -*-
"""
Summaries API

摘要管理接口
支持多种摘要类型：general, investment, learning
"""
from flask import Blueprint, request
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime
import logging

from ..models.episode import Episode
from ..models.summary import Summary
from ..services.task_queue import task_queue
from ..services.summary_service import get_summary_service
from .utils import success_response, error_response

logger = logging.getLogger(__name__)
summaries_bp = Blueprint("summaries", __name__)


def get_db():
    from .. import get_db as _get_db
    return _get_db()


@summaries_bp.route("/<episode_id>", methods=["GET"])
def get_summary(episode_id):
    """
    获取单集摘要

    Query Params:
        - summary_type: 摘要类型 (general, investment)，默认返回最新的
    """
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    # 获取摘要类型参数
    summary_type = request.args.get("summary_type")

    if summary_type:
        # 获取指定类型的摘要
        summary = db.summaries.find_one({
            "episode_id": oid,
            "summary_type": summary_type
        })
    else:
        # 获取最新的摘要
        summary = db.summaries.find_one(
            {"episode_id": oid},
            sort=[("created_at", -1)]
        )

    if not summary:
        return error_response("Summary not found", "SUMMARY_NOT_FOUND", 404)

    return success_response(Summary.to_response(summary))


@summaries_bp.route("/<episode_id>", methods=["POST"])
def create_summary(episode_id):
    """
    创建摘要任务 (异步)

    Request Body:
        - summary_type: 摘要类型 (general, investment)，默认 general
        - force: 是否强制重新生成，默认 false
    """
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    # 获取请求参数
    data = request.get_json() or {}
    summary_type = Summary.validate_type(data.get("summary_type", "general"))
    force = data.get("force", False)

    # 检查是否有转录
    transcript = db.transcripts.find_one({"episode_id": oid})
    if not transcript or not transcript.get("text"):
        return error_response(
            "Transcript not found. Please generate transcript first.",
            "TRANSCRIPT_NOT_FOUND",
            400
        )

    # 检查是否已存在该类型的摘要
    if not force:
        existing_summary = db.summaries.find_one({
            "episode_id": oid,
            "summary_type": summary_type
        })
        if existing_summary:
            return error_response(
                f"Summary of type '{summary_type}' already exists. Use force=true to regenerate.",
                "SUMMARY_EXISTS",
                409
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
        return _summarize_sync(str(oid), summary_type, force, progress_callback)

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
        "summary_type": summary_type,
        "status": "queued",
        "message": f"Summary generation started (type: {summary_type})"
    })


def _summarize_sync(episode_id: str, summary_type: str, force: bool, progress_callback=None):
    """同步执行摘要生成，完成后自动翻译"""
    db = get_db()
    oid = ObjectId(episode_id)

    if progress_callback:
        progress_callback(10)

    try:
        # 使用摘要服务生成
        service = get_summary_service(db)
        summary_doc = service.generate_summary(
            episode_id=oid,
            summary_type=summary_type,
            force=force
        )

        if progress_callback:
            progress_callback(60)

        # 自动翻译摘要
        try:
            logger.info(f"Auto-translating summary for episode {episode_id}")
            translated_doc = service.translate_summary(
                episode_id=oid,
                summary_type=summary_type
            )
            if progress_callback:
                progress_callback(100)
            return {
                "summary_id": str(summary_doc["_id"]),
                "summary_type": summary_type,
                "tokens_used": summary_doc.get("tokens_used", {}),
                "has_translation": True
            }
        except Exception as translate_err:
            logger.warning(f"Auto-translation failed (non-critical): {translate_err}")
            if progress_callback:
                progress_callback(100)
            return {
                "summary_id": str(summary_doc["_id"]),
                "summary_type": summary_type,
                "tokens_used": summary_doc.get("tokens_used", {}),
                "has_translation": False
            }

    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        # 回滚状态
        db.episodes.update_one(
            {"_id": oid},
            {"$set": {"status": Episode.STATUS_TRANSCRIBED}}
        )
        raise


@summaries_bp.route("/<episode_id>/translate", methods=["POST"])
def translate_summary(episode_id):
    """
    翻译摘要为中文

    Request Body:
        - summary_type: 摘要类型，默认翻译最新的
    """
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    # 获取请求参数
    data = request.get_json() or {}
    summary_type = data.get("summary_type")

    # 检查摘要是否存在
    query = {"episode_id": oid}
    if summary_type:
        query["summary_type"] = summary_type

    summary = db.summaries.find_one(query, sort=[("created_at", -1)])
    if not summary:
        return error_response("Summary not found", "SUMMARY_NOT_FOUND", 404)

    # 检查是否已翻译
    if summary.get("content_zh"):
        return success_response({
            "message": "Translation already exists",
            "summary": Summary.to_response(summary)
        })

    # 提交翻译任务
    def do_translate(progress_callback=None):
        return _translate_sync(str(oid), summary.get("summary_type", "general"), progress_callback)

    task_id = task_queue.submit(
        task_type="translate",
        func=do_translate,
        episode_id=str(oid)
    )

    return success_response({
        "task_id": task_id,
        "status": "queued",
        "message": "Translation started"
    })


def _translate_sync(episode_id: str, summary_type: str, progress_callback=None):
    """同步执行翻译"""
    db = get_db()
    oid = ObjectId(episode_id)

    if progress_callback:
        progress_callback(10)

    try:
        service = get_summary_service(db)
        summary_doc = service.translate_summary(
            episode_id=oid,
            summary_type=summary_type
        )

        if progress_callback:
            progress_callback(100)

        return {
            "summary_id": str(summary_doc["_id"]),
            "has_translation": True
        }

    except Exception as e:
        logger.error(f"Translation failed: {e}")
        raise


@summaries_bp.route("/<episode_id>", methods=["DELETE"])
def delete_summary(episode_id):
    """
    删除摘要

    Query Params:
        - summary_type: 指定要删除的类型，不指定则删除所有
    """
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    summary_type = request.args.get("summary_type")

    if summary_type:
        # 删除指定类型
        result = db.summaries.delete_one({
            "episode_id": oid,
            "summary_type": summary_type
        })
    else:
        # 删除所有摘要
        result = db.summaries.delete_many({"episode_id": oid})

    if result.deleted_count == 0:
        return error_response("Summary not found", "SUMMARY_NOT_FOUND", 404)

    # 检查是否还有其他摘要
    remaining = db.summaries.count_documents({"episode_id": oid})
    if remaining == 0:
        # 如果没有摘要了，回退状态
        if episode.get("status") == Episode.STATUS_SUMMARIZED:
            db.episodes.update_one(
                {"_id": oid},
                {"$set": {
                    "status": Episode.STATUS_TRANSCRIBED,
                    "has_summary": False
                }}
            )

    return success_response(message=f"Deleted {result.deleted_count} summary(ies)")


@summaries_bp.route("/types", methods=["GET"])
def get_summary_types():
    """获取支持的摘要类型"""
    return success_response({
        "types": [
            {
                "id": "general",
                "name": "General Summary",
                "name_zh": "通用摘要",
                "description": "Standard podcast summary with key points"
            },
            {
                "id": "investment",
                "name": "Investment Analysis",
                "name_zh": "投资分析",
                "description": "Investment-focused analysis with signals and tickers"
            }
        ]
    })
