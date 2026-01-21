# -*- coding: utf-8 -*-
"""
投资分析 Prompt
专注于从播客中提取投资相关信息
"""
from .base import BasePrompt


class InvestmentPrompt(BasePrompt):
    """投资分析 Prompt"""

    name = "investment"
    description = "Investment-focused analysis for finance professionals"

    system_prompt = """You are a senior financial analyst and investment researcher specializing in technology stocks and US equities.
Your task is to analyze podcast content and extract information valuable for investment decisions.
Always output valid JSON only, no other text."""

    user_prompt_template = """Analyze the following podcast transcript from an investment perspective.

## Analysis Focus

1. **Investment Signals**: Identify the guest's views on companies, industries, and technologies. Determine bullish/bearish/neutral stance.
2. **Mentioned Tickers**: Extract all mentioned public companies and stock symbols.
3. **Market Insights**: Unique perspectives on industry trends, technology development, and market dynamics.
4. **Key Quotes**: Record important direct quotes, especially controversial or unique viewpoints.
5. **Risk Alerts**: Identify mentioned risks, uncertainties, and negative factors.

## Output Format

Please output in the following JSON format:

{{
  "tldr": "1-2 sentence summary of the core investment takeaway",

  "investment_signals": [
    {{
      "type": "bullish or bearish or neutral",
      "target": "Company name or ticker symbol",
      "sector": "Industry sector",
      "reason": "Brief reasoning",
      "confidence": "high or medium or low"
    }}
  ],

  "mentioned_tickers": ["GOOGL", "NVDA", "..."],

  "market_insights": [
    "Insight 1: ...",
    "Insight 2: ..."
  ],

  "key_quotes": [
    {{
      "speaker": "Speaker name",
      "quote": "Direct quote or key point",
      "topic": "Related topic"
    }}
  ],

  "risk_alerts": [
    "Risk 1: ..."
  ],

  "tags": ["AI", "Semiconductors", "..."],

  "investment_thesis": "Comprehensive investment view: Based on this episode, investment recommendations for related targets (2-3 sentences)"
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
