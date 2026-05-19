# -*- coding: utf-8 -*-
"""
Summaries API

摘要管理端点，统一使用 template_name。
"""
from flask import Blueprint, request
from bson import ObjectId
from bson.errors import InvalidId
import logging

from ..models.episode import Episode
from ..models.summary import Summary
from ..services.task_queue import task_queue
from ..services.summary_service import get_summary_service
from ..services.ai_control import AI_DISABLED_MESSAGE, is_ai_analysis_enabled
from .utils import success_response, error_response

logger = logging.getLogger(__name__)
summaries_bp = Blueprint("summaries", __name__)


def get_db():
    from .. import get_db as _get_db
    return _get_db()


def _get_template(db, template_name: str):
    """获取模板文档，用于 to_response 动态展开"""
    return db.prompt_templates.find_one({"name": template_name, "is_active": True})


@summaries_bp.route("/<episode_id>", methods=["GET"])
def get_summary(episode_id):
    """
    获取摘要。

    Query Params:
        - template_name: 模板名称（可选，不传则返回最新的）
    """
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    template_name = request.args.get("template_name")

    query = {"episode_id": oid}
    if template_name:
        query["template_name"] = template_name

    summary = db.summaries.find_one(
        query,
        sort=[("created_at", -1)]
    )

    if not summary:
        return error_response("Summary not found", "SUMMARY_NOT_FOUND", 404)

    template = _get_template(db, summary.get("template_name", ""))
    return success_response(Summary.to_response(summary, template))


@summaries_bp.route("/<episode_id>", methods=["POST"])
def create_summary(episode_id):
    """
    创建摘要任务（异步）。

    Request Body:
        - template_name: 模板名称（默认 "learning"）
        - enabled_blocks: 启用的 block ID 列表（可选）
        - params: 参数 {"length": "long", "language": "zh"}（可选）
        - force: 强制重新生成（默认 false）
    """
    if not is_ai_analysis_enabled():
        return error_response(AI_DISABLED_MESSAGE, "AI_ANALYSIS_DISABLED", 423)

    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    data = request.get_json() or {}
    template_name = data.get("template_name", "learning")
    enabled_blocks = data.get("enabled_blocks")
    params = data.get("params", {})
    force = data.get("force", False)

    # 检查转录
    transcript = db.transcripts.find_one({"episode_id": oid})
    if not transcript or not transcript.get("text"):
        return error_response(
            "Transcript not found. Please generate transcript first.",
            "TRANSCRIPT_NOT_FOUND", 400
        )

    # 检查已有摘要
    if not force:
        existing = db.summaries.find_one({
            "episode_id": oid,
            "template_name": template_name
        })
        if existing:
            return error_response(
                f"Summary with template '{template_name}' already exists. Use force=true to regenerate.",
                "SUMMARY_EXISTS", 409
            )

    # 检查进行中的任务
    existing_task = db.tasks.find_one({
        "episode_id": str(oid),
        "task_type": "summarize",
        "status": {"$in": ["pending", "processing"]}
    })
    if existing_task:
        return error_response("Summarize task already in progress", "TASK_IN_PROGRESS", 409)

    # 提交任务
    def do_summarize(progress_callback=None):
        return _summarize_sync(
            episode_id=str(oid),
            template_name=template_name,
            enabled_blocks=enabled_blocks,
            params=params,
            force=force,
            progress_callback=progress_callback
        )

    task_id = task_queue.submit(
        task_type="summarize",
        func=do_summarize,
        episode_id=str(oid)
    )

    db.episodes.update_one(
        {"_id": oid},
        {"$set": {"status": Episode.STATUS_SUMMARIZING}}
    )

    return success_response({
        "task_id": task_id,
        "status": "queued",
        "template_name": template_name,
        "message": "Summary generation started"
    })


def _summarize_sync(
    episode_id: str,
    template_name: str = "learning",
    enabled_blocks: list = None,
    params: dict = None,
    force: bool = False,
    progress_callback=None
):
    """同步摘要生成 + 自动翻译"""
    from bson import ObjectId
    db = get_db()
    oid = ObjectId(episode_id)

    if progress_callback:
        progress_callback(10)

    try:
        service = get_summary_service(db)

        # force 时先清除旧翻译
        if force:
            db.summaries.update_one(
                {"episode_id": oid, "template_name": template_name},
                {"$unset": {"content_zh": "", "translated_at": ""}}
            )

        summary_doc = service.generate_summary(
            episode_id=oid,
            template_name=template_name,
            enabled_blocks=enabled_blocks,
            params=params,
            force=force
        )

        if progress_callback:
            progress_callback(60)

        # 自动翻译
        has_translation = False
        try:
            service.translate_summary(
                episode_id=oid,
                template_name=template_name
            )
            has_translation = True
        except Exception as translate_err:
            logger.warning(f"Auto-translation failed (non-critical): {translate_err}")

        if progress_callback:
            progress_callback(100)

        return {
            "summary_id": str(summary_doc["_id"]),
            "template_name": template_name,
            "tokens_used": summary_doc.get("tokens_used", {}),
            "has_translation": has_translation
        }

    except Exception as e:
        logger.error(f"Summary generation failed: {e}")
        db.episodes.update_one(
            {"_id": oid},
            {"$set": {"status": Episode.STATUS_TRANSCRIBED}}
        )
        raise


@summaries_bp.route("/<episode_id>/translate", methods=["POST"])
def translate_summary(episode_id):
    """
    翻译摘要为中文。

    Request Body:
        - template_name: 模板名称（可选）
    """
    if not is_ai_analysis_enabled():
        return error_response(AI_DISABLED_MESSAGE, "AI_ANALYSIS_DISABLED", 423)

    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    data = request.get_json() or {}
    template_name = data.get("template_name")

    query = {"episode_id": oid}
    if template_name:
        query["template_name"] = template_name

    summary = db.summaries.find_one(query, sort=[("created_at", -1)])
    if not summary:
        return error_response("Summary not found", "SUMMARY_NOT_FOUND", 404)

    if summary.get("content_zh"):
        template = _get_template(db, summary.get("template_name", ""))
        return success_response({
            "message": "Translation already exists",
            "summary": Summary.to_response(summary, template)
        })

    def do_translate(progress_callback=None):
        return _translate_sync(
            episode_id=str(oid),
            template_name=summary.get("template_name"),
            progress_callback=progress_callback
        )

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


def _translate_sync(episode_id: str, template_name: str = None, progress_callback=None):
    """同步翻译"""
    from bson import ObjectId
    db = get_db()
    oid = ObjectId(episode_id)

    if progress_callback:
        progress_callback(10)

    try:
        service = get_summary_service(db)
        summary_doc = service.translate_summary(
            episode_id=oid,
            template_name=template_name
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
    删除摘要。

    Query Params:
        - template_name: 删除特定模板摘要（可选，不传则删除全部）
    """
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    template_name = request.args.get("template_name")

    if template_name:
        result = db.summaries.delete_one({
            "episode_id": oid,
            "template_name": template_name
        })
    else:
        result = db.summaries.delete_many({"episode_id": oid})

    if result.deleted_count == 0:
        return error_response("Summary not found", "SUMMARY_NOT_FOUND", 404)

    # 检查剩余摘要
    remaining = db.summaries.count_documents({"episode_id": oid})
    if remaining == 0:
        if episode.get("status") == Episode.STATUS_SUMMARIZED:
            db.episodes.update_one(
                {"_id": oid},
                {"$set": {
                    "status": Episode.STATUS_TRANSCRIBED,
                    "has_summary": False
                }}
            )

    return success_response(message=f"Deleted {result.deleted_count} summary(ies)")


@summaries_bp.route("/templates", methods=["GET"])
def get_available_templates():
    """获取可用摘要模板"""
    db = get_db()
    service = get_summary_service(db)
    templates = service.get_available_templates()

    return success_response({
        "templates": templates,
        "total": len(templates)
    })
