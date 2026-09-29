# -*- coding: utf-8 -*-
"""
配置管理模块
"""
import os


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
    DEBUG = os.getenv("FLASK_DEBUG", "1") == "1"

    # API配置
    API_PREFIX = "/api"

    # Auth配置
    AUTH_REQUIRED = os.getenv("AUTH_REQUIRED", "0").lower() in ("1", "true", "yes", "on")
    JWT_SECRET = os.getenv("JWT_SECRET", os.getenv("SECRET_KEY", "dev-insecure-change-me"))
    JWT_EXPIRES_HOURS = int(os.getenv("JWT_EXPIRES_HOURS", "168"))
    DEFAULT_OWNER_ID = os.getenv("DEFAULT_OWNER_ID", "local-default-user")
    DEFAULT_OWNER_EMAIL = os.getenv("DEFAULT_OWNER_EMAIL", "local@podcast.local")

    # Whisper配置 (后续AI功能)
    WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")
    # 视频源配置 (YouTube 字幕/元数据获取的代理，空=直连)
    YOUTUBE_PROXY = os.getenv("YOUTUBE_PROXY", "")
    # B站登录态 Cookie（SESSDATA），用于 UP 主投稿列表与 AI 字幕；从浏览器 Cookie 手动复制
    BILI_SESSDATA = os.getenv("BILI_SESSDATA", "")
    WHISPER_MODEL_DIR = os.getenv("WHISPER_MODEL_DIR", "")
    WHISPER_DEVICE = os.getenv("WHISPER_DEVICE", "cpu")
    WHISPER_COMPUTE_TYPE = os.getenv("WHISPER_COMPUTE_TYPE", "int8")
    WHISPER_DEVICE_INDEX = int(os.getenv("WHISPER_DEVICE_INDEX", "0"))
    WHISPER_NUM_WORKERS = int(os.getenv("WHISPER_NUM_WORKERS", "1"))
    TRANSCRIPTION_DEFAULT_PROVIDER = os.getenv("TRANSCRIPTION_DEFAULT_PROVIDER", "official").lower()
    TRANSCRIPTION_CLOUD_ENABLED = os.getenv("TRANSCRIPTION_CLOUD_ENABLED", "0").lower() in ("1", "true", "yes", "on")
    TRANSCRIPTION_DEFAULT_LANGUAGE = os.getenv("TRANSCRIPTION_DEFAULT_LANGUAGE", "auto").lower()
    TRANSCRIPTION_AI_NORMALIZE_ENABLED = os.getenv("TRANSCRIPTION_AI_NORMALIZE_ENABLED", "0").lower() in ("1", "true", "yes", "on")

    # LLM配置 (摘要生成) - 从环境变量读取，无默认值
    AI_ANALYSIS_ENABLED = os.getenv("AI_ANALYSIS_ENABLED", "0").lower() in ("1", "true", "yes", "on")
    LLM_BASE_URL = os.getenv("LLM_BASE_URL", "")
    LLM_API_KEY = os.getenv("LLM_API_KEY", "")
    LLM_MODEL = os.getenv("LLM_MODEL", "")
    LLM_API_FORMAT = os.getenv("LLM_API_FORMAT", "openai_compatible")
    LLM_MAX_TOKENS = int(os.getenv("LLM_MAX_TOKENS", "4096"))
    LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.2"))

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
