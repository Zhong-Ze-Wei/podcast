# -*- coding: utf-8 -*-
"""
API工具函数
"""
from flask import jsonify, request
from functools import wraps


def success_response(data=None, message=None, status_code=200):
    """成功响应"""
    response = {
        "success": True,
        "data": data,
        "message": message
    }
    return jsonify(response), status_code


def error_response(message, error_code=None, status_code=400):
    """错误响应"""
    response = {
        "success": False,
        "data": None,
        "message": message,
        "error_code": error_code
    }
    return jsonify(response), status_code


def paginated_response(data, page, per_page, total):
    """分页响应"""
    pages = (total + per_page - 1) // per_page if per_page > 0 else 0
    response = {
        "success": True,
        "data": data,
        "pagination": {
            "page": page,
            "per_page": per_page,
            "total": total,
            "pages": pages,
            "has_next": page < pages,
            "has_prev": page > 1
        }
    }
    return jsonify(response), 200


def get_pagination_params():
    """从请求中获取分页参数"""
    try:
        page = int(request.args.get("page", 1))
        per_page = int(request.args.get("per_page", 20))
    except ValueError:
        page = 1
        per_page = 20

    # 限制范围
    page = max(1, page)
    per_page = max(1, min(500, per_page))

    return page, per_page


def get_bool_param(name, default=None):
    """获取布尔类型的查询参数"""
    value = request.args.get(name)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes")
