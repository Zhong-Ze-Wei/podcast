# -*- coding: utf-8 -*-
"""
设置模型 - 存储应用配置
"""

import os
from datetime import datetime
from bson import ObjectId


class SettingModel:
    """设置数据模型"""

    COLLECTION = "settings"

    # 预定义的设置键
    KEY_LLM_CONFIGS = "llm_configs"  # LLM配置列表
    KEY_LLM_ACTIVE = "llm_active_index"  # 当前激活的LLM配置索引
    KEY_TAVILY_CONFIG = "tavily_config"  # Tavily配置

    def __init__(self, db):
        self.db = db
        self.collection = db[self.COLLECTION]

    def get(self, key, default=None):
        """获取设置值"""
        doc = self.collection.find_one({"key": key})
        if doc:
            return doc.get("value", default)
        return default

    def set(self, key, value):
        """设置值"""
        self.collection.update_one(
            {"key": key},
            {
                "$set": {"value": value, "updated_at": datetime.utcnow()},
                "$setOnInsert": {"created_at": datetime.utcnow()},
            },
            upsert=True,
        )

    @staticmethod
    def get_default_llm_config():
        """从环境变量获取默认LLM配置"""
        return {
            "name": os.getenv("LLM_DEFAULT_NAME", "Default"),
            "base_url": os.getenv("LLM_BASE_URL", "http://localhost:8000"),
            "api_key": os.getenv("LLM_API_KEY", ""),
            "model": os.getenv("LLM_MODEL", "gpt-3.5-turbo"),
            "max_tokens": int(os.getenv("LLM_MAX_TOKENS", "4096")),
            "temperature": float(os.getenv("LLM_TEMPERATURE", "0.2")),
        }

    def get_llm_configs(self):
        """获取所有LLM配置"""
        configs = self.get(self.KEY_LLM_CONFIGS, [])
        active_index = self.get(self.KEY_LLM_ACTIVE, 0)

        # 确保至少有一个默认配置（从环境变量读取）
        if not configs:
            configs = [self.get_default_llm_config()]
            self.set(self.KEY_LLM_CONFIGS, configs)
            self.set(self.KEY_LLM_ACTIVE, 0)

        return {"configs": configs, "active_index": active_index}

    def save_llm_configs(self, configs, active_index=None):
        """保存LLM配置列表"""
        # 限制最多5个配置
        if len(configs) > 5:
            configs = configs[:5]

        # 验证配置
        for config in configs:
            if not config.get("name"):
                config["name"] = "Unnamed"
            if not config.get("base_url"):
                raise ValueError("base_url is required")
            if not config.get("model"):
                raise ValueError("model is required")
            # 设置默认值
            config.setdefault("api_key", "")
            config.setdefault("max_tokens", 4096)
            config.setdefault("temperature", 0.2)

        self.set(self.KEY_LLM_CONFIGS, configs)

        if active_index is not None:
            if active_index < 0 or active_index >= len(configs):
                active_index = 0
            self.set(self.KEY_LLM_ACTIVE, active_index)

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
