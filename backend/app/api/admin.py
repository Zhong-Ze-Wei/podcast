# -*- coding: utf-8 -*-
"""
Minimal admin API for early multi-user operation.
"""
from datetime import datetime

from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, request

from ..models.user import User
from .decorators import require_admin
from .utils import error_response, success_response

admin_bp = Blueprint("admin", __name__)


def get_db():
    from .. import get_db as _get_db

    return _get_db()


@admin_bp.route("/users", methods=["GET"])
@require_admin
def list_users():
    db = get_db()
    users = list(db.users.find({}).sort("created_at", -1))
    return success_response([User.to_response(user) for user in users])


@admin_bp.route("/users/<user_id>", methods=["PATCH"])
@require_admin
def update_user(user_id):
    try:
        oid = ObjectId(user_id)
    except InvalidId:
        return error_response("Invalid user ID", "INVALID_ID", 400)

    data = request.get_json() or {}
    updates = {}
    if "status" in data:
        if data["status"] not in {User.STATUS_ACTIVE, User.STATUS_DISABLED}:
            return error_response("Invalid status", "INVALID_STATUS", 400)
        updates["status"] = data["status"]
    if "role" in data:
        if data["role"] not in {User.ROLE_USER, User.ROLE_ADMIN}:
            return error_response("Invalid role", "INVALID_ROLE", 400)
        updates["role"] = data["role"]

    if not updates:
        return error_response("No supported fields provided", "NO_UPDATES", 400)

    updates["updated_at"] = datetime.utcnow()
    db = get_db()
    result = db.users.update_one({"_id": oid}, {"$set": updates})
    if not getattr(result, "matched_count", 0):
        return error_response("User not found", "USER_NOT_FOUND", 404)

    return success_response(User.to_response(db.users.find_one({"_id": oid})))


@admin_bp.route("/tasks", methods=["GET"])
@require_admin
def task_overview():
    db = get_db()
    return success_response({
        "pending": db.tasks.count_documents({"status": "pending"}),
        "processing": db.tasks.count_documents({"status": "processing"}),
        "completed": db.tasks.count_documents({"status": "completed"}),
        "failed": db.tasks.count_documents({"status": "failed"}),
    })


@admin_bp.route("/health", methods=["GET"])
@require_admin
def health():
    db = get_db()
    return success_response({
        "mongodb": "ok",
        "users": db.users.count_documents({}),
        "feeds": db.feeds.count_documents({}),
        "episodes": db.episodes.count_documents({}),
        "tasks": db.tasks.count_documents({}),
    })
