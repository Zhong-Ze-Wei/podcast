# -*- coding: utf-8 -*-
"""
通用摘要 Prompt
"""
from .base import BasePrompt


class GeneralPrompt(BasePrompt):
    """通用摘要 Prompt"""

    name = "general"
    description = "General podcast summary"

    system_prompt = """You are a professional content analyst.
Your task is to analyze podcast transcripts and generate structured summaries.
Always output valid JSON only, no other text."""

    user_prompt_template = """Analyze the following podcast transcript and generate a structured summary.

## Requirements

1. **TL;DR**: A 1-2 sentence summary of the main topic
2. **Key Points**: 5-8 most important points or insights
3. **Why It Matters**: Brief explanation of the significance
4. **Tags**: 3-5 relevant keywords

## Output Format

Please output in the following JSON format:

{{
  "tldr": "One or two sentence summary of the podcast",
  "key_points": [
    "Key point 1",
    "Key point 2",
    "Key point 3",
    "Key point 4",
    "Key point 5"
  ],
  "why_it_matters": "Why this content is important or valuable",
  "tags": ["tag1", "tag2", "tag3"]
}}

## Podcast Information
Title: {title}
Guest: {guest}

## Transcript
{transcript}
"""

    def build_user_prompt(self, transcript: str, **kwargs) -> str:
        title = kwargs.get("title", "Unknown")
        guest = kwargs.get("guest", "Unknown")

        return self.user_prompt_template.format(
            title=title,
            guest=guest,
            transcript=self.truncate_text(transcript)
        )
