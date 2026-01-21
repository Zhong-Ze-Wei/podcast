# -*- coding: utf-8 -*-
"""
Prompt 模块
提供不同类型的摘要 Prompt
"""
from .base import BasePrompt
from .general import GeneralPrompt
from .investment import InvestmentPrompt
from .translate import TranslatePrompt


class PromptRouter:
    """Prompt 路由器"""

    PROMPTS = {
        "general": GeneralPrompt,
        "investment": InvestmentPrompt,
    }

    @classmethod
    def get_prompt(cls, summary_type: str) -> BasePrompt:
        """根据类型获取 Prompt 实例"""
        prompt_class = cls.PROMPTS.get(summary_type, GeneralPrompt)
        return prompt_class()

    @classmethod
    def get_available_types(cls) -> list:
        """获取可用的摘要类型"""
        return list(cls.PROMPTS.keys())

    @classmethod
    def get_translate_prompt(cls) -> TranslatePrompt:
        """获取翻译 Prompt"""
        return TranslatePrompt()


__all__ = [
    "BasePrompt",
    "GeneralPrompt",
    "InvestmentPrompt",
    "TranslatePrompt",
    "PromptRouter"
]
