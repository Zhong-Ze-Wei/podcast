# -*- coding: utf-8 -*-
"""
Prompt 基类
"""
import json
from abc import ABC, abstractmethod
from typing import Dict, List, Any


class BasePrompt(ABC):
    """Prompt 基类"""

    name: str = "base"
    description: str = "Base prompt"

    # 系统提示
    system_prompt: str = "You are a helpful assistant."

    @abstractmethod
    def build_user_prompt(self, transcript: str, **kwargs) -> str:
        """构建用户提示"""
        pass

    def build_messages(self, transcript: str, **kwargs) -> List[Dict[str, str]]:
        """构建完整的 messages 列表"""
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.build_user_prompt(transcript, **kwargs)}
        ]

    def parse_response(self, content: str) -> Dict[str, Any]:
        """解析 LLM 响应"""
        return json.loads(content)

    def truncate_text(self, text: str, max_chars: int = 100000) -> str:
        """智能截断文本，保留开头和结尾"""
        if len(text) <= max_chars:
            return text

        # 保留开头 60% 和结尾 30%
        head_size = int(max_chars * 0.6)
        tail_size = int(max_chars * 0.3)

        head = text[:head_size]
        tail = text[-tail_size:]

        return f"{head}\n\n[... content truncated, total {len(text)} characters ...]\n\n{tail}"
