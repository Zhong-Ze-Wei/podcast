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

            content = response.choices[0].message.content
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

        try:
            data = json.loads(result["content"])
            result["data"] = data
            return result
        except json.JSONDecodeError as e:
            logger.error(f"Failed to parse JSON response: {e}")
            logger.debug(f"Raw content: {result['content'][:500]}")
            raise ValueError(f"Invalid JSON response from LLM: {e}")


# 全局客户端实例
_client: Optional[LLMClient] = None


def get_llm_client() -> LLMClient:
    """获取 LLM 客户端单例"""
    global _client
    if _client is None:
        _client = LLMClient()
    return _client
