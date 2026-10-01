# -*- coding: utf-8 -*-
"""
Flask应用工厂
"""

import os

from flask import Flask, abort, send_from_directory
from flask_cors import CORS
from pymongo import MongoClient
from werkzeug.utils import safe_join

from .config import get_config


def create_app():
    """创建Flask应用"""
    app = Flask(__name__)

    # 加载配置
    config = get_config()
    app.config.from_object(config)

    # 初始化目录
    config.init_dirs()

    # 启用CORS - 限制为本地开发环境
    CORS(
        app,
        resources={
            r"/api/*": {
                "origins": ["http://localhost:3000", "http://127.0.0.1:3000"],
                "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                "allow_headers": ["Content-Type", "Authorization"],
            }
        },
    )

    # 存储 MongoDB 客户端实例到应用对象
    app.mongo_client = MongoClient(app.config["MONGO_URI"])
    app.db = app.mongo_client[app.config["MONGO_DB"]]

    # 创建索引
    ensure_indexes(app.db)

    # 初始化任务队列的数据库连接
    from .services.task_queue import task_queue

    task_queue.set_app(app)
    task_queue.set_db(app.db)
    task_queue.recover_interrupted_tasks()

    # 启动自动刷新服务（每小时检查一次，超过6小时未更新的订阅源自动刷新）
    from .services.auto_refresher import start_auto_refresher

    start_auto_refresher(app.db, interval_hours=1, stale_threshold_hours=6)

    # 注册蓝图
    register_media_routes(app)
    register_blueprints(app)

    # 注册错误处理
    register_error_handlers(app)

    return app


def ensure_indexes(db):
    """确保数据库索引"""
    # users索引
    db.users.create_index("email", unique=True)
    db.users.create_index("role")
    db.users.create_index("status")

    # feeds索引
    try:
        db.feeds.drop_index("rss_url_1")
    except Exception:
        pass
    db.feeds.create_index([("owner_id", 1), ("rss_url", 1)], unique=True)
    db.feeds.create_index("owner_id")
    db.feeds.create_index("status")
    db.feeds.create_index("is_starred")
    db.feeds.create_index("is_favorite")
    db.feeds.create_index("created_at")

    # episodes索引
    db.episodes.create_index("feed_id")
    db.episodes.create_index("guid")
    try:
        db.episodes.drop_index("feed_id_1_guid_1")
    except Exception:
        pass
    db.episodes.create_index([("owner_id", 1), ("feed_id", 1), ("guid", 1)], unique=True)
    db.episodes.create_index("owner_id")
    db.episodes.create_index("status")
    db.episodes.create_index("is_starred")
    db.episodes.create_index("published")
    db.episodes.create_index("has_transcript")
    db.episodes.create_index("has_summary")
    db.episodes.create_index([("feed_id", 1), ("is_read", 1)])

    # 剧集个人状态（已读/加星/播放进度按用户隔离）
    db.user_episode_states.create_index([("user_id", 1), ("episode_id", 1)], unique=True)
    db.user_episode_states.create_index("episode_id")

    # transcripts索引
    try:
        db.transcripts.drop_index("episode_id_1")
    except Exception:
        pass
    db.transcripts.create_index([("owner_id", 1), ("episode_id", 1)], unique=True)
    db.transcripts.create_index("owner_id")

    # summaries索引 - 需要先删除旧的唯一索引（如果存在）
    try:
        # 检查是否存在旧的唯一索引，如果存在则删除
        existing_indexes = list(db.summaries.list_indexes())
        for idx in existing_indexes:
            if idx.get("name") == "episode_id_1" and idx.get("unique"):
                db.summaries.drop_index("episode_id_1")
                break
    except Exception:
        pass
    db.summaries.create_index("episode_id")
    db.summaries.create_index([("episode_id", 1), ("template_name", 1)])
    db.summaries.create_index("owner_id")

    # prompt_templates索引
    db.prompt_templates.create_index("name", unique=True)
    db.prompt_templates.create_index("is_active")
    db.prompt_templates.create_index("is_system")

    # tasks索引
    db.tasks.create_index("task_id", unique=True)
    db.tasks.create_index("owner_id")
    db.tasks.create_index("status")
    db.tasks.create_index("episode_id")
    db.tasks.create_index("created_at")
    db.tasks.create_index(
        "completed_at",
        expireAfterSeconds=7 * 24 * 60 * 60,
        name="tasks_completed_at_ttl",
    )

    # briefings索引（AI简报，按策略+时间窗口独立缓存）
    for legacy in ("date_1", "date_1_strategy_1"):
        try:
            db.briefings.drop_index(legacy)
        except Exception:
            pass
    db.briefings.create_index([("date", 1), ("strategy", 1), ("days", 1)], unique=True)


def register_media_routes(app):
    """Serve local media files through the API prefix for the Vite proxy."""
    prefix = app.config.get("API_PREFIX", "/api")
    media_root = app.config["MEDIA_ROOT"]

    @app.route(f"{prefix}/media/<path:filename>", methods=["GET"])
    def serve_media(filename):
        resolved = safe_join(media_root, filename)
        if not resolved or not os.path.isfile(resolved):
            abort(404)
        return send_from_directory(media_root, filename, conditional=True, max_age=604800)


def register_blueprints(app):
    """注册蓝图"""
    from .api.feeds import feeds_bp
    from .api.episodes import episodes_bp
    from .api.transcripts import transcripts_bp
    from .api.summaries import summaries_bp
    from .api.tasks import tasks_bp
    from .api.stats import stats_bp
    from .api.settings import settings_bp
    from .api.prompt_templates import prompt_templates_bp
    from .api.insights import insights_bp
    from .api.briefing_lab import briefing_lab_bp
    from .api.briefing_reports import briefing_reports_bp
    from .api.auth import auth_bp
    from .api.admin import admin_bp
    from .api.video_import import video_import_bp

    prefix = app.config.get("API_PREFIX", "/api")

    app.register_blueprint(auth_bp, url_prefix=f"{prefix}/auth")
    app.register_blueprint(admin_bp, url_prefix=f"{prefix}/admin")
    app.register_blueprint(feeds_bp, url_prefix=f"{prefix}/feeds")
    app.register_blueprint(episodes_bp, url_prefix=f"{prefix}/episodes")
    app.register_blueprint(transcripts_bp, url_prefix=f"{prefix}/transcripts")
    app.register_blueprint(summaries_bp, url_prefix=f"{prefix}/summaries")
    app.register_blueprint(tasks_bp, url_prefix=f"{prefix}/tasks")
    app.register_blueprint(stats_bp, url_prefix=f"{prefix}")
    app.register_blueprint(settings_bp, url_prefix=f"{prefix}/settings")
    app.register_blueprint(prompt_templates_bp, url_prefix=f"{prefix}/prompt-templates")
    app.register_blueprint(insights_bp, url_prefix=f"{prefix}/insights")
    app.register_blueprint(briefing_lab_bp, url_prefix=f"{prefix}/briefing-lab")
    app.register_blueprint(briefing_reports_bp, url_prefix=f"{prefix}/briefing-reports")
    app.register_blueprint(video_import_bp, url_prefix=f"{prefix}/video-import")


def register_error_handlers(app):
    """注册错误处理器"""
    from .api.utils import error_response

    @app.errorhandler(404)
    def not_found(e):
        return error_response("Resource not found", "NOT_FOUND", 404)

    @app.errorhandler(500)
    def internal_error(e):
        return error_response("Internal server error", "INTERNAL_ERROR", 500)


def get_db():
    """获取数据库连接 - 从当前应用上下文"""
    from flask import current_app

    return current_app.db
