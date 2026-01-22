# -*- coding: utf-8 -*-
"""
Summaries API

Summary management endpoints.
Supports both legacy summary_type API and new template-based API.
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
    Get episode summary.

    Query Params:
        - template_name: Template name (new API)
        - summary_type: Summary type (legacy API)
    """
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    # Check for template_name (new API) or summary_type (legacy)
    template_name = request.args.get("template_name")
    summary_type = request.args.get("summary_type")

    query = {"episode_id": oid}
    if template_name:
        query["template_name"] = template_name
    elif summary_type:
        query["summary_type"] = summary_type

    if template_name or summary_type:
        summary = db.summaries.find_one(query)
    else:
        # Get latest summary
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
    Create summary task (async).

    Request Body (New API - template-based):
        - template_name: Template to use (e.g., "investment", "tech", "learning")
        - enabled_blocks: List of block IDs to enable (optional)
        - params: Parameters like {"length": "long"} (optional)
        - force: Force regenerate (default: false)

    Request Body (Legacy API - backward compatible):
        - summary_type: "general" or "investment"
        - force: Force regenerate
    """
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    # Parse request body
    data = request.get_json() or {}

    # New API parameters
    template_name = data.get("template_name")
    enabled_blocks = data.get("enabled_blocks")  # List of block IDs
    params = data.get("params", {})  # e.g., {"length": "long"}

    # Legacy API parameters
    summary_type = data.get("summary_type")

    # Determine which API is being used
    if template_name:
        # New template-based API
        identifier = template_name
        identifier_field = "template_name"
    elif summary_type:
        # Legacy API
        summary_type = Summary.validate_type(summary_type)
        identifier = summary_type
        identifier_field = "summary_type"
    else:
        # Default to learning template
        template_name = "learning"
        identifier = template_name
        identifier_field = "template_name"

    force = data.get("force", False)

    # Check for transcript
    transcript = db.transcripts.find_one({"episode_id": oid})
    if not transcript or not transcript.get("text"):
        return error_response(
            "Transcript not found. Please generate transcript first.",
            "TRANSCRIPT_NOT_FOUND",
            400
        )

    # Check for existing summary
    if not force:
        existing_query = {"episode_id": oid, identifier_field: identifier}
        existing_summary = db.summaries.find_one(existing_query)
        if existing_summary:
            return error_response(
                f"Summary with {identifier_field}='{identifier}' already exists. Use force=true to regenerate.",
                "SUMMARY_EXISTS",
                409
            )

    # Check for in-progress task
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

    # Submit task
    def do_summarize(progress_callback=None):
        return _summarize_sync(
            episode_id=str(oid),
            template_name=template_name,
            summary_type=summary_type,
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

    # Update episode status
    db.episodes.update_one(
        {"_id": oid},
        {"$set": {"status": Episode.STATUS_SUMMARIZING}}
    )

    response_data = {
        "task_id": task_id,
        "status": "queued",
        "message": "Summary generation started"
    }

    if template_name:
        response_data["template_name"] = template_name
        if enabled_blocks:
            response_data["enabled_blocks"] = enabled_blocks
        if params:
            response_data["params"] = params
    else:
        response_data["summary_type"] = summary_type

    return success_response(response_data)


def _summarize_sync(
    episode_id: str,
    template_name: str = None,
    summary_type: str = None,
    enabled_blocks: list = None,
    params: dict = None,
    force: bool = False,
    progress_callback=None
):
    """Synchronous summary generation with optional translation."""
    db = get_db()
    oid = ObjectId(episode_id)

    if progress_callback:
        progress_callback(10)

    try:
        service = get_summary_service(db)
        summary_doc = service.generate_summary(
            episode_id=oid,
            template_name=template_name,
            summary_type=summary_type,
            enabled_blocks=enabled_blocks,
            params=params,
            force=force
        )

        if progress_callback:
            progress_callback(60)

        # Auto-translate
        try:
            logger.info(f"Auto-translating summary for episode {episode_id}")
            translated_doc = service.translate_summary(
                episode_id=oid,
                template_name=template_name,
                summary_type=summary_type
            )
            if progress_callback:
                progress_callback(100)
            return {
                "summary_id": str(summary_doc["_id"]),
                "template_name": template_name,
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
                "template_name": template_name,
                "summary_type": summary_type,
                "tokens_used": summary_doc.get("tokens_used", {}),
                "has_translation": False
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
    Translate summary to Chinese.

    Request Body:
        - template_name: Template name (new API)
        - summary_type: Summary type (legacy API)
    """
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    data = request.get_json() or {}
    template_name = data.get("template_name")
    summary_type = data.get("summary_type")

    # Build query
    query = {"episode_id": oid}
    if template_name:
        query["template_name"] = template_name
    elif summary_type:
        query["summary_type"] = summary_type

    summary = db.summaries.find_one(query, sort=[("created_at", -1)])
    if not summary:
        return error_response("Summary not found", "SUMMARY_NOT_FOUND", 404)

    # Check if already translated
    if summary.get("content_zh"):
        return success_response({
            "message": "Translation already exists",
            "summary": Summary.to_response(summary)
        })

    # Submit translation task
    def do_translate(progress_callback=None):
        return _translate_sync(
            episode_id=str(oid),
            template_name=summary.get("template_name"),
            summary_type=summary.get("summary_type"),
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


def _translate_sync(
    episode_id: str,
    template_name: str = None,
    summary_type: str = None,
    progress_callback=None
):
    """Synchronous translation."""
    db = get_db()
    oid = ObjectId(episode_id)

    if progress_callback:
        progress_callback(10)

    try:
        service = get_summary_service(db)
        summary_doc = service.translate_summary(
            episode_id=oid,
            template_name=template_name,
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
    Delete summary.

    Query Params:
        - template_name: Delete specific template summary
        - summary_type: Delete specific type summary (legacy)
        - (none): Delete all summaries for episode
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
    summary_type = request.args.get("summary_type")

    if template_name:
        result = db.summaries.delete_one({
            "episode_id": oid,
            "template_name": template_name
        })
    elif summary_type:
        result = db.summaries.delete_one({
            "episode_id": oid,
            "summary_type": summary_type
        })
    else:
        result = db.summaries.delete_many({"episode_id": oid})

    if result.deleted_count == 0:
        return error_response("Summary not found", "SUMMARY_NOT_FOUND", 404)

    # Check remaining summaries
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
    """
    Get available summary templates.

    Returns templates from database with their blocks and parameters.
    """
    db = get_db()
    service = get_summary_service(db)
    templates = service.get_available_templates()

    return success_response({
        "templates": templates,
        "total": len(templates)
    })


@summaries_bp.route("/types", methods=["GET"])
def get_summary_types():
    """
    Get supported summary types (legacy API).

    Deprecated: Use /templates endpoint instead.
    """
    db = get_db()

    # Try to get from database first
    templates = list(db.prompt_templates.find({"is_active": True}))

    if templates:
        types = [
            {
                "id": t.get("name"),
                "name": t.get("display_name"),
                "description": t.get("description")
            }
            for t in templates
        ]
    else:
        # Fallback to hardcoded
        types = [
            {
                "id": "general",
                "name": "General Summary",
                "name_zh": "General Summary",
                "description": "Standard podcast summary with key points"
            },
            {
                "id": "investment",
                "name": "Investment Analysis",
                "name_zh": "Investment Analysis",
                "description": "Investment-focused analysis with signals and tickers"
            }
        ]

    return success_response({"types": types})
