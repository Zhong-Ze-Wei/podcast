# -*- coding: utf-8 -*-
"""
API装饰器工具

提供常用的API装饰器以减少重复代码
"""

from functools import wraps
from flask import current_app, g, request
from bson import ObjectId
from bson.errors import InvalidId

from ..models.user import User
from ..services.jwt_auth import verify_token


def validate_object_id(param_name="id"):
    """
    验证URL参数中的ObjectId

    使用方式:
        @validate_object_id("feed_id")
        def get_feed(feed_id):  # feed_id已经是ObjectId类型
            ...

    Args:
        param_name: URL参数名

    Returns:
        装饰器函数
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            id_value = kwargs.get(param_name)
            if id_value:
                try:
                    kwargs[param_name] = ObjectId(id_value)
                except InvalidId:
                    from .utils import error_response

                    return error_response(f"Invalid {param_name}", "INVALID_ID", 400)
            return f(*args, **kwargs)

        return decorated_function

    return decorator


def validate_json(*required_fields):
    """
    验证请求体为JSON且包含必需字段

    使用方式:
        @validate_json("rss_url", "title")
        def create_feed():  # request.get_json()已在装饰器中验证
            data = request.get_json()
            ...
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            data = request.get_json()
            if data is None:
                from .utils import error_response

                return error_response("Request body must be JSON", "INVALID_JSON", 400)

            missing = [field for field in required_fields if field not in data]
            if missing:
                from .utils import error_response

                return error_response(
                    f"Missing fields: {', '.join(missing)}", "MISSING_FIELDS", 400
                )

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def _get_db():
    from .. import get_db

    return get_db()


def _default_user():
    return {
        "id": current_app.config.get("DEFAULT_OWNER_ID", "local-default-user"),
        "email": current_app.config.get("DEFAULT_OWNER_EMAIL", "local@podcast.local"),
        "role": User.ROLE_ADMIN,
        "status": User.STATUS_ACTIVE,
        "is_default": True,
    }


def current_user():
    user = getattr(g, "current_user", None)
    if user:
        return user

    auth_header = request.headers.get("Authorization", "")
    token = ""
    if auth_header.lower().startswith("bearer "):
        token = auth_header.split(" ", 1)[1].strip()

    if token:
        payload = verify_token(token, current_app.config["JWT_SECRET"])
        if payload:
            try:
                user_oid = ObjectId(payload["sub"])
            except (InvalidId, TypeError):
                user_oid = None
            doc = _get_db().users.find_one({"_id": user_oid}) if user_oid else None
            if doc and doc.get("status") == User.STATUS_ACTIVE:
                user = User.to_response(doc)
                g.current_user = user
                return user

    if current_app.config.get("AUTH_REQUIRED", False):
        return None

    user = _default_user()
    g.current_user = user
    return user


def current_owner_id():
    user = current_user()
    if user and user.get("is_default"):
        return None
    return user["id"] if user else None


def owner_filter(extra=None):
    query = dict(extra or {})
    owner_id = current_owner_id()
    if owner_id:
        query["owner_id"] = owner_id
    return query


def require_auth(fn):
    @wraps(fn)
    def decorated(*args, **kwargs):
        if not current_user():
            from .utils import error_response

            return error_response("Authentication required", "AUTH_REQUIRED", 401)
        return fn(*args, **kwargs)

    return decorated


def require_admin(fn):
    @wraps(fn)
    def decorated(*args, **kwargs):
        user = current_user()
        if not user:
            from .utils import error_response

            return error_response("Authentication required", "AUTH_REQUIRED", 401)
        if user.get("role") != User.ROLE_ADMIN:
            from .utils import error_response

            return error_response("Admin access required", "ADMIN_REQUIRED", 403)
        return fn(*args, **kwargs)

    return decorated
