# -*- coding: utf-8 -*-
"""
Authentication API.
"""
from datetime import datetime

from bson import ObjectId
from bson.errors import InvalidId
from flask import Blueprint, current_app, request

from ..models.user import User
from ..services.jwt_auth import create_token
from .decorators import current_user, require_auth
from .utils import error_response, success_response

auth_bp = Blueprint("auth", __name__)


def get_db():
    from .. import get_db as _get_db

    return _get_db()


def _token_for(user_doc):
    return create_token(
        {
            "sub": str(user_doc["_id"]),
            "email": user_doc["email"],
            "role": user_doc.get("role", User.ROLE_USER),
        },
        current_app.config["JWT_SECRET"],
        current_app.config.get("JWT_EXPIRES_HOURS", 168),
    )


@auth_bp.route("/register", methods=["POST"])
def register():
    data = request.get_json() or {}
    email = User.normalize_email(data.get("email"))
    password = data.get("password", "")
    if not email or not password:
        return error_response("Email and password are required", "MISSING_CREDENTIALS", 400)
    if len(password) < 8:
        return error_response("Password must be at least 8 characters", "WEAK_PASSWORD", 400)

    db = get_db()
    if db.users.find_one({"email": email}):
        return error_response("Email already exists", "USER_EXISTS", 409)

    role = User.ROLE_USER
    if db.users.count_documents({}) == 0:
        role = User.ROLE_ADMIN

    user_doc = User.create(email, password, role=role)
    result = db.users.insert_one(user_doc)
    user_doc["_id"] = result.inserted_id

    return success_response(
        {"user": User.to_response(user_doc), "token": _token_for(user_doc)},
        "User registered",
        201,
    )


@auth_bp.route("/login", methods=["POST"])
def login():
    data = request.get_json() or {}
    email = User.normalize_email(data.get("email"))
    password = data.get("password", "")
    db = get_db()
    user_doc = db.users.find_one({"email": email})
    if not user_doc or not User.verify_password(user_doc, password):
        return error_response("Invalid email or password", "INVALID_CREDENTIALS", 401)
    if user_doc.get("status") == User.STATUS_DISABLED:
        return error_response("User is disabled", "USER_DISABLED", 403)

    db.users.update_one(
        {"_id": user_doc["_id"]},
        {"$set": {"last_login_at": datetime.utcnow(), "updated_at": datetime.utcnow()}},
    )
    user_doc["last_login_at"] = datetime.utcnow()
    return success_response({"user": User.to_response(user_doc), "token": _token_for(user_doc)})


@auth_bp.route("/me", methods=["GET"])
@require_auth
def me():
    return success_response({"user": current_user()})
