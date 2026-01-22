# -*- coding: utf-8 -*-
"""
Flask应用工厂
"""
from flask import Flask
from flask_cors import CORS
from pymongo import MongoClient

from .config import get_config

# 全局数据库连接
db = None


def create_app():
    """创建Flask应用"""
    app = Flask(__name__)

    # 加载配置
    config = get_config()
    app.config.from_object(config)

    # 初始化目录
    config.init_dirs()

    # 启用CORS
    CORS(app, resources={r"/api/*": {"origins": "*"}})

    # 初始化数据库
    init_db(app)

    # 注册蓝图
    register_blueprints(app)

    # 注册错误处理
    register_error_handlers(app)

    return app


def init_db(app):
    """初始化MongoDB连接"""
    global db
    client = MongoClient(app.config["MONGO_URI"])
    db = client[app.config["MONGO_DB"]]

    # 创建索引
    ensure_indexes(db)

    # 初始化任务队列的数据库连接
    from .services.task_queue import task_queue
    task_queue.set_db(db)


def ensure_indexes(db):
    """确保数据库索引"""
    # feeds索引
    db.feeds.create_index("rss_url", unique=True)
    db.feeds.create_index("status")
    db.feeds.create_index("is_starred")
    db.feeds.create_index("created_at")

    # episodes索引
    db.episodes.create_index("feed_id")
    db.episodes.create_index("guid")
    db.episodes.create_index([("feed_id", 1), ("guid", 1)], unique=True)
    db.episodes.create_index("status")
    db.episodes.create_index("is_starred")
    db.episodes.create_index("published")

    # transcripts索引
    db.transcripts.create_index("episode_id", unique=True)

    # summaries索引
    db.summaries.create_index("episode_id", unique=True)

    # tasks索引
    db.tasks.create_index("task_id", unique=True)
    db.tasks.create_index("status")
    db.tasks.create_index("created_at")


def register_blueprints(app):
    """注册蓝图"""
    from .api.feeds import feeds_bp
    from .api.episodes import episodes_bp
    from .api.transcripts import transcripts_bp
    from .api.summaries import summaries_bp
    from .api.tasks import tasks_bp
    from .api.stats import stats_bp
    from .api.settings import settings_bp

    prefix = app.config.get("API_PREFIX", "/api")

    app.register_blueprint(feeds_bp, url_prefix=f"{prefix}/feeds")
    app.register_blueprint(episodes_bp, url_prefix=f"{prefix}/episodes")
    app.register_blueprint(transcripts_bp, url_prefix=f"{prefix}/transcripts")
    app.register_blueprint(summaries_bp, url_prefix=f"{prefix}/summaries")
    app.register_blueprint(tasks_bp, url_prefix=f"{prefix}/tasks")
    app.register_blueprint(stats_bp, url_prefix=f"{prefix}")
    app.register_blueprint(settings_bp, url_prefix=f"{prefix}/settings")


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
    """获取数据库连接"""
    return db
