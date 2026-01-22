# -*- coding: utf-8 -*-
"""
LLM 客户端封装
支持 OpenAI 兼容接口 (LiteLLM 代理)
"""
import json
import logging
from typing import Optional
from datetime import datetime

import openai

from app.config import get_config

logger = logging.getLogger(__name__)
config = get_config()


class LLMClient:
    """LLM 调用客户端"""

    def __init__(
        self,
        base_url: str = None,
        api_key: str = None,
        model: str = None
    ):
        self.base_url = base_url or config.LLM_BASE_URL
        self.api_key = api_key or config.LLM_API_KEY
        self.model = model or config.LLM_MODEL

        self.client = openai.OpenAI(
            api_key=self.api_key,
            base_url=self.base_url
        )

    def chat(
        self,
        messages: list,
        model: str = None,
        max_tokens: int = None,
        temperature: float = None,
        json_mode: bool = False
    ) -> dict:
        """
        发送聊天请求

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            model: 模型名称，默认使用配置中的模型
            max_tokens: 最大输出 token 数
            temperature: 温度参数
            json_mode: 是否强制 JSON 输出

        Returns:
            {
                "content": "响应内容",
                "usage": {"prompt": x, "completion": y, "total": z},
                "model": "使用的模型",
                "elapsed_seconds": 耗时
            }
        """
        model = model or self.model
        max_tokens = max_tokens or config.LLM_MAX_TOKENS
        temperature = temperature if temperature is not None else config.LLM_TEMPERATURE

        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature
        }

        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        start_time = datetime.now()

        try:
            response = self.client.chat.completions.create(**kwargs)
            elapsed = (datetime.now() - start_time).total_seconds()

            # 检查响应是否有效
            if not response.choices:
                logger.error("LLM returned empty choices")
                raise ValueError("LLM returned empty response (no choices)")

            content = response.choices[0].message.content

            # 检查内容是否为空
            if content is None or content.strip() == "":
                logger.error("LLM returned empty content")
                raise ValueError("LLM returned empty content")

            usage = {
                "prompt": response.usage.prompt_tokens if response.usage else 0,
                "completion": response.usage.completion_tokens if response.usage else 0,
                "total": response.usage.total_tokens if response.usage else 0
            }

            logger.info(
                f"LLM call completed: model={model}, "
                f"tokens={usage['total']}, elapsed={elapsed:.1f}s"
            )

            return {
                "content": content,
                "usage": usage,
                "model": model,
                "elapsed_seconds": elapsed
            }

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def chat_json(
        self,
        messages: list,
        model: str = None,
        max_tokens: int = None,
        temperature: float = None
    ) -> dict:
        """
        发送聊天请求并解析 JSON 响应

        Returns:
            {
                "data": 解析后的 JSON 对象,
                "usage": {...},
                "model": "...",
                "elapsed_seconds": ...
            }
        """
        result = self.chat(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            temperature=temperature,
            json_mode=True
        )

        content = result.get("content", "")

        # 清理可能的 markdown 代码块
        if content:
            content = content.strip()
            if content.startswith("```"):
                lines = content.split("\n")
                # 移除第一行 (```json 或 ```)
                if lines[0].startswith("```"):
                    lines = lines[1:]
                # 移除最后一行如果是 ```
                if lines and lines[-1].strip() == "```":
                    lines = lines[:-1]
                content = "\n".join(lines).strip()
                result["content"] = content

        try:
            data = json.loads(content)
            result["data"] = data
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Content length: {len(content) if content else 0}")
            logger.error(f"Content preview: {repr(content[:200]) if content else 'None'}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")


# 全局客户端实例
_client: Optional[LLMClient] = None
_client_config_hash: Optional[str] = None


def get_llm_client() -> LLMClient:
    """
    获取 LLM 客户端

    优先从数据库获取活动配置，如果数据库不可用则使用环境变量配置
    配置变更时会自动重建客户端
    """
    global _client, _client_config_hash

    active_config = None

    # 尝试从 Flask 应用上下文获取数据库
    try:
        from app import get_db
        from app.models.setting import SettingModel

        db = get_db()
        if db is not None:
            setting_model = SettingModel(db)
            active_config = setting_model.get_active_llm_config()

    except Exception as e:
        logger.debug(f"Failed to get db from Flask context: {e}")

    # 如果 Flask 上下文不可用，直接连接 MongoDB
    if active_config is None:
        try:
            from pymongo import MongoClient
            import os

            mongo_uri = os.getenv("MONGO_URI", "mongodb://localhost:27017")
            mongo_db = os.getenv("MONGO_DB", "podcast")

            client = MongoClient(mongo_uri)
            db = client[mongo_db]

            from app.models.setting import SettingModel
            setting_model = SettingModel(db)
            active_config = setting_model.get_active_llm_config()

        except Exception as e:
            logger.warning(f"Failed to get LLM config from MongoDB: {e}")

    # 使用获取到的配置创建客户端
    if active_config:
        config_hash = f"{active_config.get('base_url')}:{active_config.get('model')}:{active_config.get('api_key', '')[:8]}"

        if _client is None or _client_config_hash != config_hash:
            logger.info(f"Creating LLM client with config: {active_config.get('name', 'unnamed')}")
            _client = LLMClient(
                base_url=active_config.get("base_url"),
                api_key=active_config.get("api_key"),
                model=active_config.get("model")
            )
            _client_config_hash = config_hash

        return _client

    # 回退到环境变量配置
    logger.warning("No LLM config found in database, using environment variables")
    if _client is None:
        _client = LLMClient()
    return _client
