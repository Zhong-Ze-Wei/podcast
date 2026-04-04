# -*- coding: utf-8 -*-
"""
API装饰器工具

提供常用的API装饰器以减少重复代码
"""

from functools import wraps
from flask import request
from bson import ObjectId
from bson.errors import InvalidId


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
