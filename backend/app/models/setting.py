# -*- coding: utf-8 -*-
"""
设置模型 - 存储应用配置
"""

import os
import re
from datetime import datetime


class SettingModel:
    """设置数据模型"""

    COLLECTION = "settings"

    # 预定义的设置键
    KEY_LLM_CONFIGS = "llm_configs"  # LLM配置列表
    KEY_LLM_ACTIVE = "llm_active_index"  # 当前激活的LLM配置索引
    KEY_LLM_TASK_ROUTES = "llm_task_routes"  # AI任务到配置ID的路由
    KEY_TAVILY_CONFIG = "tavily_config"  # Tavily配置

    LLM_TASKS = ("summary", "transcript_normalize", "briefing")
    API_FORMAT_OPENAI = "openai_compatible"
    API_FORMAT_ANTHROPIC = "anthropic_messages"
    API_FORMATS = {API_FORMAT_OPENAI, API_FORMAT_ANTHROPIC}

    def __init__(self, db, owner_id=None):
        self.db = db
        self.collection = db[self.COLLECTION]
        self.owner_id = owner_id

    def _query(self, key):
        query = {"key": key}
        if self.owner_id is not None:
            query["owner_id"] = self.owner_id
        return query

    def get(self, key, default=None):
        """获取设置值"""
        doc = self.collection.find_one(self._query(key))
        if doc:
            return doc.get("value", default)
        return default

    def set(self, key, value):
        """设置值"""
        self.collection.update_one(
            self._query(key),
            {
                "$set": {"value": value, "owner_id": self.owner_id, "updated_at": datetime.utcnow()},
                "$setOnInsert": {"created_at": datetime.utcnow()},
            },
            upsert=True,
        )

    @staticmethod
    def get_default_llm_config():
        """从环境变量获取默认LLM配置"""
        return {
            "id": os.getenv("LLM_DEFAULT_ID", "modelscope-default"),
            "name": os.getenv("LLM_DEFAULT_NAME", "ModelScope"),
            "provider": os.getenv("LLM_PROVIDER", "modelscope"),
            "api_format": os.getenv("LLM_API_FORMAT", SettingModel.API_FORMAT_OPENAI),
            "base_url": os.getenv("LLM_BASE_URL", "https://api-inference.modelscope.cn/v1"),
            "api_key": os.getenv("LLM_API_KEY", ""),
            "model": os.getenv("LLM_MODEL", "deepseek-ai/DeepSeek-V4-Flash"),
            "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "4096")),
            "temperature": float(os.getenv("LLM_TEMPERATURE", "0.2")),
            "supports_streaming": os.getenv("LLM_SUPPORTS_STREAMING", "1").lower() in ("1", "true", "yes", "on"),
            "enabled": os.getenv("LLM_ENABLED", "1").lower() in ("1", "true", "yes", "on"),
        }

    @staticmethod
    def _slug(value: str, fallback: str = "config") -> str:
        slug = re.sub(r"[^a-z0-9]+", "-", (value or "").lower()).strip("-")
        return slug or fallback

    @classmethod
    def normalize_llm_config(cls, config, index=0):
        """Normalize one LLM config to the current provider-first schema."""
        normalized = dict(config or {})
        provider = normalized.get("provider") or normalized.get("name") or f"config-{index + 1}"
        provider_id = cls._slug(provider, f"config-{index + 1}")

        normalized.setdefault("id", provider_id)
        normalized["id"] = cls._slug(normalized["id"], provider_id)
        normalized.setdefault("name", normalized["id"])
        normalized.setdefault("provider", normalized["id"])
        normalized["provider"] = cls._slug(normalized["provider"], normalized["id"])

        api_format = normalized.get("api_format") or cls.API_FORMAT_OPENAI
        if api_format not in cls.API_FORMATS:
            api_format = cls.API_FORMAT_OPENAI
        normalized["api_format"] = api_format

        if not normalized.get("base_url"):
            raise ValueError("base_url is required")
        normalized["base_url"] = str(normalized["base_url"]).strip().rstrip("/")

        if not normalized.get("model"):
            raise ValueError("model is required")
        normalized["model"] = str(normalized["model"]).strip()

        normalized.setdefault("api_key", "")
        normalized["api_key"] = str(normalized.get("api_key") or "").strip()
        normalized["max_tokens"] = int(normalized.get("max_tokens") or 4096)
        normalized["temperature"] = float(normalized.get("temperature", 0.2))
        normalized["supports_streaming"] = bool(normalized.get("supports_streaming", True))
        normalized["enabled"] = bool(normalized.get("enabled", True))
        return normalized

    def get_llm_configs(self):
        """获取所有LLM配置"""
        configs = self.get(self.KEY_LLM_CONFIGS, [])
        active_index = self.get(self.KEY_LLM_ACTIVE, 0)

        # 确保至少有一个默认配置（从环境变量读取）
        if not configs:
            configs = [self.get_default_llm_config()]
            self.set(self.KEY_LLM_CONFIGS, configs)
            self.set(self.KEY_LLM_ACTIVE, 0)
        else:
            configs = [self.normalize_llm_config(config, i) for i, config in enumerate(configs)]

        return {
            "configs": configs,
            "active_index": active_index,
            "task_routes": self.get_llm_task_routes(configs),
        }

    def save_llm_configs(self, configs, active_index=None):
        """保存LLM配置列表"""
        # 限制最多5个配置
        if len(configs) > 5:
            configs = configs[:5]

        configs = [self.normalize_llm_config(config, i) for i, config in enumerate(configs)]

        self.set(self.KEY_LLM_CONFIGS, configs)

        if active_index is not None:
            if active_index < 0 or active_index >= len(configs):
                active_index = 0
            self.set(self.KEY_LLM_ACTIVE, active_index)

    def get_llm_task_routes(self, configs=None):
        """Get task route mapping, falling back to the active/default config."""
        configs = configs or self.get(self.KEY_LLM_CONFIGS, [])
        available_ids = {
            config["id"]
            for i, config in enumerate(configs)
            for config in [self.normalize_llm_config(config, i)]
            if config.get("enabled", True)
        }
        saved = self.get(self.KEY_LLM_TASK_ROUTES, {}) or {}
        routes = {}
        for task in self.LLM_TASKS:
            config_id = saved.get(task, "default")
            routes[task] = config_id if config_id in available_ids else "default"
        return routes

    def save_llm_task_routes(self, task_routes, configs):
        """Persist task routes, only allowing configured and enabled config IDs."""
        available_ids = {
            config["id"]
            for config in configs
            if config.get("enabled", True)
        }
        routes = {}
        for task in self.LLM_TASKS:
            config_id = (task_routes or {}).get(task, "default")
            routes[task] = config_id if config_id in available_ids else "default"
        self.set(self.KEY_LLM_TASK_ROUTES, routes)
        return routes

    def get_active_llm_config(self):
        """获取当前激活的LLM配置"""
        data = self.get_llm_configs()
        configs = data["configs"]
        active_index = data["active_index"]

        if not configs:
            return None

        if active_index >= len(configs):
            active_index = 0

        return configs[active_index]

    def set_active_llm_index(self, index):
        """设置激活的LLM配置索引"""
        data = self.get_llm_configs()
        if index < 0 or index >= len(data["configs"]):
            raise ValueError(f"Invalid index: {index}")
        self.set(self.KEY_LLM_ACTIVE, index)

    @staticmethod
    def get_default_tavily_config():
        """从环境变量获取默认Tavily配置"""
        import json
        import os

        # 从环境变量读取Tavily密钥
        tavily_keys_str = os.getenv("TAVILY_KEYS", "[]")
        try:
            api_keys = json.loads(tavily_keys_str)
            if not isinstance(api_keys, list):
                api_keys = []
        except (json.JSONDecodeError, ValueError):
            api_keys = []

        return {
            "enabled": len(api_keys) > 0,
            "api_keys": api_keys,
            "search_depth": os.getenv("TAVILY_SEARCH_DEPTH", "basic"),
            "max_results": int(os.getenv("TAVILY_MAX_RESULTS", "5")),
            "include_domains": [],
            "exclude_domains": [],
            "days_back": int(os.getenv("TAVILY_DAYS_BACK", "30")),
        }

    def get_tavily_config(self):
        """获取Tavily配置"""
        config = self.get(self.KEY_TAVILY_CONFIG, None)

        if config is None:
            # 使用默认配置（从环境变量读取）
            config = self.get_default_tavily_config()
            self.set(self.KEY_TAVILY_CONFIG, config)

        return config

    def save_tavily_config(self, config):
        """保存Tavily配置"""
        # 验证配置
        if not isinstance(config, dict):
            raise ValueError("Config must be a dictionary")

        # 设置默认值
        config.setdefault("enabled", False)
        config.setdefault("api_keys", [])
        config.setdefault("search_depth", "basic")
        config.setdefault("max_results", 5)
        config.setdefault("include_domains", [])
        config.setdefault("exclude_domains", [])
        config.setdefault("days_back", 30)

        # 验证搜索深度
        if config["search_depth"] not in ["basic", "advanced"]:
            raise ValueError("search_depth must be 'basic' or 'advanced'")

        # 验证数值范围
        if config["max_results"] < 1 or config["max_results"] > 20:
            raise ValueError("max_results must be between 1 and 20")

        if config["days_back"] < 1 or config["days_back"] > 365:
            raise ValueError("days_back must be between 1 and 365")

        self.set(self.KEY_TAVILY_CONFIG, config)
