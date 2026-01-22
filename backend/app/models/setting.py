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
                "$set": {
                    "value": value,
                    "updated_at": datetime.utcnow()
                },
                "$setOnInsert": {
                    "created_at": datetime.utcnow()
                }
            },
            upsert=True
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
            "temperature": float(os.getenv("LLM_TEMPERATURE", "0.2"))
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

        return {
            "configs": configs,
            "active_index": active_index
        }

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
