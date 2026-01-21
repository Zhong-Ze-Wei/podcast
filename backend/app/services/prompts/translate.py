# -*- coding: utf-8 -*-
"""
翻译 Prompt
用于将英文摘要翻译成中文
"""
import json
from .base import BasePrompt


class TranslatePrompt(BasePrompt):
    """翻译 Prompt"""

    name = "translate"
    description = "Translate summary content to Chinese"

    system_prompt = """You are a professional translator specializing in finance and technology content.
Your task is to translate English content to Chinese while preserving:
1. Technical terms accuracy
2. Stock tickers and company names in original form
3. The structure of the original content
Always output valid JSON only, no other text."""

    user_prompt_template = """Translate the following summary content from English to Chinese.

## Translation Guidelines

1. Keep stock tickers (e.g., GOOGL, NVDA) in English
2. Keep company names with both English and Chinese (e.g., "Google (谷歌)")
3. Translate "bullish" as "看多", "bearish" as "看空", "neutral" as "中性"
4. Translate "high/medium/low" confidence as "高/中/低"
5. Preserve the exact JSON structure

## Original English Content

{content}

## Output

Output the translated JSON with the same structure, adding "_zh" suffix to text fields:

For example, if input has:
{{"tldr": "English text", "key_points": ["point 1", "point 2"]}}

Output should be:
{{"tldr_zh": "中文翻译", "key_points_zh": ["要点1", "要点2"]}}

Now translate the content above:
"""

    def build_user_prompt(self, transcript: str = "", **kwargs) -> str:
        """
        Note: For translation, we use 'content' instead of 'transcript'
        """
        content = kwargs.get("content", "")
        if isinstance(content, dict):
            content = json.dumps(content, ensure_ascii=False, indent=2)

        return self.user_prompt_template.format(content=content)

    def build_messages(self, content: dict, **kwargs) -> list:
        """构建翻译消息"""
        return [
            {"role": "system", "content": self.system_prompt},
            {"role": "user", "content": self.build_user_prompt(content=content)}
        ]
