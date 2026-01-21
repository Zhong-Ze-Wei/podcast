# -*- coding: utf-8 -*-
"""
配置管理模块
"""
import os
from datetime import timedelta


class Config:
    """应用配置"""

    # 基础目录
    BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    # MongoDB配置
    MONGO_URI = os.getenv("MONGO_URI", "mongodb://localhost:27017")
    MONGO_DB = os.getenv("MONGO_DB", "podcast")

    # 媒体文件目录
    MEDIA_ROOT = os.getenv("MEDIA_ROOT", os.path.join(BASE_DIR, "media"))
    AUDIO_DIR = os.path.join(MEDIA_ROOT, "audio")
    COVERS_DIR = os.path.join(MEDIA_ROOT, "covers")
    TEMP_DIR = os.path.join(MEDIA_ROOT, "temp")

    # Flask配置
    SECRET_KEY = os.getenv("SECRET_KEY", "dev-secret-key-change-in-production")
    DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"

    # API配置
    API_PREFIX = "/api"
    PER_PAGE_DEFAULT = 20
    PER_PAGE_MAX = 100

    # 任务队列配置
    TASK_WORKERS = int(os.getenv("TASK_WORKERS", "3"))

    # RSS配置
    RSS_TIMEOUT = int(os.getenv("RSS_TIMEOUT", "30"))
    RSS_USER_AGENT = "PodcastManager/1.0"

    # Whisper配置 (后续AI功能)
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")

    # LLM配置 (后续AI功能)
    LLM_ENDPOINT = os.getenv("LLM_ENDPOINT", "http://localhost:11434")

    @classmethod
    def init_dirs(cls):
        """确保必要目录存在"""
        for d in [cls.AUDIO_DIR, cls.COVERS_DIR, cls.TEMP_DIR]:
            os.makedirs(d, exist_ok=True)


class DevelopmentConfig(Config):
    """开发环境配置"""
    DEBUG = True


class ProductionConfig(Config):
    """生产环境配置"""
    DEBUG = False


# 配置映射
config_map = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "default": DevelopmentConfig
}


def get_config():
    """获取当前配置"""
    env = os.getenv("FLASK_ENV", "development")
    return config_map.get(env, config_map["default"])
