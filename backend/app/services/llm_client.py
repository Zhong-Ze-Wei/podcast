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
import requests

from app.config import get_config

logger = logging.getLogger(__name__)
config = get_config()


class EmptyLLMResponse(ValueError):
    """模型已响应但没有正文；保留用量和结束原因供调用方审计、重试。"""

    def __init__(self, message, response):
        super().__init__(message)
        self.response = response


class LLMClient:
    """LLM 调用客户端"""

    API_FORMAT_OPENAI = "openai_compatible"
    API_FORMAT_ANTHROPIC = "anthropic_messages"

    def __init__(
        self,
        base_url: str = None,
        api_key: str = None,
        model: str = None,
        api_format: str = None,
        supports_streaming: bool = True,
    ):
        self.base_url = (base_url or config.LLM_BASE_URL).rstrip("/")
        self.api_key = api_key or config.LLM_API_KEY
        self.model = model or config.LLM_MODEL
        default_api_format = getattr(config, "LLM_API_FORMAT", self.API_FORMAT_OPENAI)
        self.api_format = api_format or default_api_format
        self.supports_streaming = supports_streaming

        self.client = None
        if self.api_format == self.API_FORMAT_OPENAI:
            self.client = openai.OpenAI(api_key=self.api_key, base_url=self.base_url)

    def chat(
        self,
        messages: list,
        model: str = None,
        max_tokens: int = None,
        temperature: float = None,
        json_mode: bool = False,
        response_schema: dict = None,
    ) -> dict:
        """
        发送聊天请求

        Args:
            messages: 消息列表 [{"role": "user", "content": "..."}]
            model: 模型名称，默认使用配置中的模型
            max_tokens: 最大输出 token 数
            temperature: 温度参数
            json_mode: 是否强制 JSON 输出
            response_schema: 可选的严格 JSON Schema 输出契约

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

        if self.api_format == self.API_FORMAT_ANTHROPIC:
            return self._chat_anthropic(
                messages=messages,
                model=model,
                max_tokens=max_tokens,
                temperature=temperature,
                response_schema=response_schema,
            )

        kwargs = {
            "model": model,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

        if response_schema is not None:
            kwargs["response_format"] = {"type": "json_schema", "json_schema": {
                "name": "structured_result", "strict": True, "schema": response_schema,
            }}
        elif json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        start_time = datetime.now()

        try:
            response = self.client.chat.completions.create(**kwargs)
            elapsed = (datetime.now() - start_time).total_seconds()

            usage = {
                "prompt": response.usage.prompt_tokens if response.usage else 0,
                "completion": response.usage.completion_tokens if response.usage else 0,
                "total": response.usage.total_tokens if response.usage else 0,
            }
            choice = response.choices[0] if response.choices else None
            result = {
                "content": (choice.message.content or "") if choice else "",
                "usage": usage,
                "model": model,
                "elapsed_seconds": elapsed,
                "finish_reason": choice.finish_reason if choice else None,
            }
            if not result["content"].strip():
                reason = "LLM returned empty content" if choice else "LLM returned empty response (no choices)"
                raise EmptyLLMResponse(reason, result)

            logger.info(
                f"LLM call completed: model={model}, "
                f"tokens={usage['total']}, elapsed={elapsed:.1f}s"
            )

            return result

        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            raise

    def _chat_anthropic(
        self,
        messages: list,
        model: str,
        max_tokens: int,
        temperature: float,
        response_schema: dict = None,
    ) -> dict:
        """Call Anthropic Messages API using the same return shape as chat()."""
        system_parts = []
        anthropic_messages = []
        for message in messages:
            role = message.get("role")
            content = message.get("content", "")
            if role == "system":
                system_parts.append(content)
            elif role in ("user", "assistant"):
                anthropic_messages.append({"role": role, "content": content})

        payload = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        }
        if system_parts:
            payload["system"] = "\n\n".join(system_parts)
        if response_schema is not None:
            payload["output_config"] = {"format": {"type": "json_schema", "schema": response_schema}}

        start_time = datetime.now()
        response = requests.post(
            f"{self.base_url}/messages",
            headers={
                "x-api-key": self.api_key,
                "anthropic-version": "2023-06-01",
                "content-type": "application/json",
            },
            json=payload,
            timeout=120,
        )
        response.raise_for_status()
        body = response.json()
        elapsed = (datetime.now() - start_time).total_seconds()

        content = "".join(
            item.get("text", "")
            for item in body.get("content", [])
            if item.get("type") == "text"
        ).strip()
        raw_usage = body.get("usage", {}) or {}
        usage = {
            "prompt": raw_usage.get("input_tokens", 0),
            "completion": raw_usage.get("output_tokens", 0),
            "total": raw_usage.get("input_tokens", 0) + raw_usage.get("output_tokens", 0),
        }

        result = {
            "content": content,
            "usage": usage,
            "model": body.get("model", model),
            "elapsed_seconds": elapsed,
            "finish_reason": body.get("stop_reason"),
        }
        if not content:
            raise EmptyLLMResponse("LLM returned empty content", result)
        return result

    def chat_json(
        self,
        messages: list,
        model: str = None,
        max_tokens: int = None,
        temperature: float = None,
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
            json_mode=True,
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
            # 完整 JSON 之后附带多余文字（模型常见的收尾碎语）：截取首个完整 JSON 值
            if "Extra data" in str(e):
                try:
                    data, _ = json.JSONDecoder().raw_decode(content.lstrip())
                    logger.warning("LLM JSON 后有多余内容（char %s），已截取首个 JSON 对象", e.pos)
                    result["data"] = data
                    return result
                except json.JSONDecodeError:
                    pass
            # 字符串未闭合或输出顶到 max_tokens 上限 → 输出被截断，翻倍上限重试一次
            effective_cap = max_tokens or config.LLM_MAX_TOKENS
            completion_tokens = (result.get("usage") or {}).get("completion", 0)
            truncated = "Unterminated" in str(e) or completion_tokens >= effective_cap > 0
            if truncated and effective_cap < 16384:
                logger.warning(
                    f"LLM JSON output truncated (completion={completion_tokens}, "
                    f"cap={effective_cap}); retrying with doubled max_tokens"
                )
                return self.chat_json(
                    messages=messages,
                    model=model,
                    max_tokens=effective_cap * 2,
                    temperature=temperature,
                )
            logger.error(f"Failed to parse JSON response: {e}")
            logger.error(f"Content length: {len(content) if content else 0}")
            logger.error(
                f"Content preview: {repr(content[:200]) if content else 'None'}"
            )
            raise ValueError(f"Invalid JSON response from LLM: {e}")


def get_llm_client(task=None) -> LLMClient:
    """
    获取 LLM 客户端 - 每次创建新实例（线程安全）

    Args:
        task: 可选任务名 (summary/briefing/transcript_normalize)，用于 task route 解析
    """
    active_config = None

    # 尝试从 Flask 应用上下文获取数据库
    try:
        from app import get_db
        from app.models.setting import SettingModel

        db = get_db()
        if db is not None:
            setting_model = SettingModel(db)
            active_config = setting_model.get_active_llm_config(task=task)

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
            active_config = setting_model.get_active_llm_config(task=task)

        except Exception as e:
            logger.warning(f"Failed to get LLM config from MongoDB: {e}")

    # 使用获取到的配置创建客户端
    if active_config:
        logger.debug(
            f"Creating LLM client: task={task}, model={active_config.get('model', 'unknown')}"
        )
        return LLMClient(
            base_url=active_config.get("base_url"),
            api_key=active_config.get("api_key"),
            model=active_config.get("model"),
            api_format=active_config.get("api_format"),
            supports_streaming=active_config.get("supports_streaming", True),
        )

    # 回退到环境变量配置
    logger.debug("Using environment variables for LLM config")
    return LLMClient()
