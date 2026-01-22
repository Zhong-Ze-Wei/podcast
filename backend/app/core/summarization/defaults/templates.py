# -*- coding: utf-8 -*-
"""
Default Prompt Templates

System-level templates that are loaded into the database on initialization.
These templates are protected and cannot be modified by users.
"""

# Common locked section for all templates
COMMON_LOCKED = {
    "system_prompt": "You are a professional content analyst. Your task is to analyze podcast transcripts and generate structured summaries. Always output valid JSON only, no other text.",
    "output_format_instruction": """
Output strictly in JSON format with the required fields.
Ensure all JSON is properly formatted and valid.
Do not include any text outside the JSON structure.
""",
    "required_fields": ["tldr", "tags"]
}

# Common user prompt template
COMMON_USER_PROMPT = """Analyze the following podcast transcript.

## Podcast Information
Title: {title}
Guest: {guest}

## Analysis Requirements
{length_instruction}
{language_instruction}

{optional_blocks_instructions}

## Output Format
{output_format_instruction}

{dynamic_schema}

## Transcript
{transcript}
"""

# Common parameters
COMMON_PARAMETERS = {
    "length": {
        "type": "enum",
        "name": "length",
        "label": "Summary Length",
        "label_zh": "摘要长度",
        "options": [
            {"value": "short", "label": "Short", "label_zh": "简短", "token_hint": 2000},
            {"value": "medium", "label": "Medium", "label_zh": "适中", "token_hint": 4096},
            {"value": "long", "label": "Long", "label_zh": "详细", "token_hint": 8000}
        ],
        "default": "medium",
        "prompt_mapping": {
            "short": "Be concise. Keep each section under 50 words. Focus on the most essential points only.",
            "medium": "Provide moderate detail. Each section should be 50-150 words.",
            "long": "Be thorough and detailed. Each section should be 150-300 words. Include examples and nuances."
        }
    },
    "language": {
        "type": "enum",
        "name": "language",
        "label": "Output Language",
        "label_zh": "输出语言",
        "options": [
            {"value": "en", "label": "English", "label_zh": "英文"},
            {"value": "zh", "label": "Chinese", "label_zh": "中文"}
        ],
        "default": "en",
        "prompt_mapping": {
            "en": "Output all content in English.",
            "zh": "Output all content in Chinese (Simplified)."
        }
    }
}

# Common optional blocks (shared across templates)
COMMON_BLOCKS = {
    "core_content": {
        "id": "core_content",
        "name": "Core Content",
        "name_zh": "核心内容",
        "prompt_fragment": "Identify and summarize the main topic and core message of this podcast episode.",
        "output_field": {
            "key": "core_content",
            "type": "string",
            "description": "The main topic and core message"
        },
        "enabled_by_default": True,
        "order": 1
    },
    "guest_background": {
        "id": "guest_background",
        "name": "Guest Background",
        "name_zh": "受访者背景",
        "prompt_fragment": "Extract the guest's professional background, expertise, and relevant experience.",
        "output_field": {
            "key": "guest_background",
            "type": "string",
            "description": "Guest's professional background and expertise"
        },
        "enabled_by_default": True,
        "order": 2
    },
    "unique_insights": {
        "id": "unique_insights",
        "name": "Unique Insights",
        "name_zh": "独特见解",
        "prompt_fragment": "Identify unique, contrarian, or particularly insightful viewpoints expressed.",
        "output_field": {
            "key": "unique_insights",
            "type": "array",
            "items": "string",
            "description": "List of unique or contrarian insights"
        },
        "enabled_by_default": True,
        "order": 3
    },
    "key_points": {
        "id": "key_points",
        "name": "Key Points",
        "name_zh": "关键要点",
        "prompt_fragment": "Extract 5-8 most important points or takeaways from the discussion.",
        "output_field": {
            "key": "key_points",
            "type": "array",
            "items": "string",
            "description": "List of key points"
        },
        "enabled_by_default": True,
        "order": 4
    },
    "key_quotes": {
        "id": "key_quotes",
        "name": "Key Quotes",
        "name_zh": "关键引用",
        "prompt_fragment": "Extract important direct quotes from speakers, especially memorable or impactful statements.",
        "output_field": {
            "key": "key_quotes",
            "type": "array",
            "items": {"speaker": "string", "quote": "string", "context": "string"},
            "description": "Notable quotes with speaker and context"
        },
        "enabled_by_default": False,
        "order": 5
    },
    "action_items": {
        "id": "action_items",
        "name": "Action Items",
        "name_zh": "行动建议",
        "prompt_fragment": "List actionable takeaways that listeners can implement.",
        "output_field": {
            "key": "action_items",
            "type": "array",
            "items": "string",
            "description": "Actionable recommendations"
        },
        "enabled_by_default": False,
        "order": 6
    },
    "investment_signals": {
        "id": "investment_signals",
        "name": "Investment Signals",
        "name_zh": "投资信号",
        "prompt_fragment": "Extract bullish/bearish/neutral signals with target company, sector, reasoning and confidence level (high/medium/low).",
        "output_field": {
            "key": "investment_signals",
            "type": "array",
            "items": {
                "type": "bullish/bearish/neutral",
                "target": "company or ticker",
                "sector": "industry sector",
                "reason": "brief reasoning",
                "confidence": "high/medium/low"
            },
            "description": "Investment signals with sentiment analysis"
        },
        "enabled_by_default": False,
        "order": 10
    },
    "mentioned_tickers": {
        "id": "mentioned_tickers",
        "name": "Mentioned Tickers",
        "name_zh": "提及股票",
        "prompt_fragment": "List all public company stock tickers mentioned in the discussion.",
        "output_field": {
            "key": "mentioned_tickers",
            "type": "array",
            "items": "string",
            "description": "Stock ticker symbols mentioned"
        },
        "enabled_by_default": False,
        "order": 11
    },
    "market_insights": {
        "id": "market_insights",
        "name": "Market Insights",
        "name_zh": "市场洞察",
        "prompt_fragment": "Extract insights about market trends, industry dynamics, and economic factors.",
        "output_field": {
            "key": "market_insights",
            "type": "array",
            "items": "string",
            "description": "Market and industry insights"
        },
        "enabled_by_default": False,
        "order": 12
    },
    "risk_alerts": {
        "id": "risk_alerts",
        "name": "Risk Alerts",
        "name_zh": "风险提示",
        "prompt_fragment": "Identify risks, uncertainties, negative factors, and potential downsides mentioned.",
        "output_field": {
            "key": "risk_alerts",
            "type": "array",
            "items": "string",
            "description": "Risk factors and warnings"
        },
        "enabled_by_default": False,
        "order": 13
    },
    "technologies": {
        "id": "technologies",
        "name": "Technologies",
        "name_zh": "技术栈",
        "prompt_fragment": "List technologies, frameworks, tools, and technical concepts discussed.",
        "output_field": {
            "key": "technologies",
            "type": "array",
            "items": "string",
            "description": "Technologies and tools mentioned"
        },
        "enabled_by_default": False,
        "order": 20
    },
    "product_insights": {
        "id": "product_insights",
        "name": "Product Insights",
        "name_zh": "产品洞察",
        "prompt_fragment": "Extract product design decisions, feature discussions, and UX considerations.",
        "output_field": {
            "key": "product_insights",
            "type": "array",
            "items": "string",
            "description": "Product and design insights"
        },
        "enabled_by_default": False,
        "order": 21
    },
    "tech_trends": {
        "id": "tech_trends",
        "name": "Tech Trends",
        "name_zh": "技术趋势",
        "prompt_fragment": "Identify technology trends, emerging patterns, and future predictions.",
        "output_field": {
            "key": "tech_trends",
            "type": "array",
            "items": "string",
            "description": "Technology trends and predictions"
        },
        "enabled_by_default": False,
        "order": 22
    },
    "business_model": {
        "id": "business_model",
        "name": "Business Model",
        "name_zh": "商业模式",
        "prompt_fragment": "Describe the business model, revenue streams, and monetization strategies discussed.",
        "output_field": {
            "key": "business_model",
            "type": "string",
            "description": "Business model description"
        },
        "enabled_by_default": False,
        "order": 30
    },
    "growth_tactics": {
        "id": "growth_tactics",
        "name": "Growth Tactics",
        "name_zh": "增长策略",
        "prompt_fragment": "Extract growth strategies, customer acquisition methods, and scaling approaches.",
        "output_field": {
            "key": "growth_tactics",
            "type": "array",
            "items": "string",
            "description": "Growth and scaling strategies"
        },
        "enabled_by_default": False,
        "order": 31
    },
    "lessons_learned": {
        "id": "lessons_learned",
        "name": "Lessons Learned",
        "name_zh": "经验教训",
        "prompt_fragment": "Identify mistakes, failures, and lessons learned from experience.",
        "output_field": {
            "key": "lessons_learned",
            "type": "array",
            "items": "string",
            "description": "Lessons from experience"
        },
        "enabled_by_default": False,
        "order": 32
    },
    "key_concepts": {
        "id": "key_concepts",
        "name": "Key Concepts",
        "name_zh": "核心概念",
        "prompt_fragment": "Explain key concepts, terminology, and ideas introduced in the discussion.",
        "output_field": {
            "key": "key_concepts",
            "type": "array",
            "items": {"concept": "string", "explanation": "string"},
            "description": "Key concepts with explanations"
        },
        "enabled_by_default": False,
        "order": 40
    },
    "examples": {
        "id": "examples",
        "name": "Examples",
        "name_zh": "案例举例",
        "prompt_fragment": "Extract concrete examples, case studies, and real-world applications mentioned.",
        "output_field": {
            "key": "examples",
            "type": "array",
            "items": "string",
            "description": "Examples and case studies"
        },
        "enabled_by_default": False,
        "order": 41
    },
    "resources": {
        "id": "resources",
        "name": "Resources",
        "name_zh": "推荐资源",
        "prompt_fragment": "List books, articles, tools, websites, or other resources recommended.",
        "output_field": {
            "key": "resources",
            "type": "array",
            "items": "string",
            "description": "Recommended resources"
        },
        "enabled_by_default": False,
        "order": 42
    },
    "life_lessons": {
        "id": "life_lessons",
        "name": "Life Lessons",
        "name_zh": "人生经验",
        "prompt_fragment": "Extract personal life lessons, wisdom, and philosophy shared by the guest.",
        "output_field": {
            "key": "life_lessons",
            "type": "array",
            "items": "string",
            "description": "Personal life lessons and wisdom"
        },
        "enabled_by_default": False,
        "order": 50
    },
    "controversial_views": {
        "id": "controversial_views",
        "name": "Controversial Views",
        "name_zh": "争议观点",
        "prompt_fragment": "Identify controversial, unconventional, or debate-worthy opinions expressed.",
        "output_field": {
            "key": "controversial_views",
            "type": "array",
            "items": "string",
            "description": "Controversial or unconventional opinions"
        },
        "enabled_by_default": False,
        "order": 51
    }
}


# =============================================================================
# TEMPLATE DEFINITIONS
# =============================================================================

TEMPLATE_INVESTMENT = {
    "name": "investment",
    "display_name": "Investment Analysis",
    "description": "Extract investment signals, stock mentions, and market insights from finance podcasts.",
    "is_system": True,
    "is_active": True,
    "locked": {
        **COMMON_LOCKED,
        "system_prompt": "You are a senior financial analyst and investment researcher specializing in technology stocks and US equities. Your task is to analyze podcast content and extract information valuable for investment decisions. Always output valid JSON only, no other text."
    },
    "optional_blocks": [
        COMMON_BLOCKS["core_content"],
        COMMON_BLOCKS["guest_background"],
        COMMON_BLOCKS["unique_insights"],
        {**COMMON_BLOCKS["investment_signals"], "enabled_by_default": True},
        {**COMMON_BLOCKS["mentioned_tickers"], "enabled_by_default": True},
        {**COMMON_BLOCKS["market_insights"], "enabled_by_default": True},
        COMMON_BLOCKS["key_quotes"],
        {**COMMON_BLOCKS["risk_alerts"], "enabled_by_default": True},
        COMMON_BLOCKS["action_items"]
    ],
    "parameters": COMMON_PARAMETERS,
    "user_prompt_template": COMMON_USER_PROMPT
}

TEMPLATE_TECH = {
    "name": "tech",
    "display_name": "Tech & Product",
    "description": "Analyze technology discussions, product insights, and tech industry trends.",
    "is_system": True,
    "is_active": True,
    "locked": {
        **COMMON_LOCKED,
        "system_prompt": "You are a technology analyst specializing in software development, product management, and tech industry trends. Your task is to extract technical insights and product knowledge. Always output valid JSON only, no other text."
    },
    "optional_blocks": [
        COMMON_BLOCKS["core_content"],
        COMMON_BLOCKS["guest_background"],
        COMMON_BLOCKS["unique_insights"],
        {**COMMON_BLOCKS["technologies"], "enabled_by_default": True},
        {**COMMON_BLOCKS["product_insights"], "enabled_by_default": True},
        {**COMMON_BLOCKS["tech_trends"], "enabled_by_default": True},
        COMMON_BLOCKS["key_quotes"],
        COMMON_BLOCKS["action_items"],
        COMMON_BLOCKS["resources"]
    ],
    "parameters": COMMON_PARAMETERS,
    "user_prompt_template": COMMON_USER_PROMPT
}

TEMPLATE_STARTUP = {
    "name": "startup",
    "display_name": "Startup & Business",
    "description": "Extract business models, growth strategies, and entrepreneurship lessons.",
    "is_system": True,
    "is_active": True,
    "locked": {
        **COMMON_LOCKED,
        "system_prompt": "You are a business analyst specializing in startups, entrepreneurship, and growth strategies. Your task is to extract actionable business insights. Always output valid JSON only, no other text."
    },
    "optional_blocks": [
        COMMON_BLOCKS["core_content"],
        COMMON_BLOCKS["guest_background"],
        COMMON_BLOCKS["unique_insights"],
        {**COMMON_BLOCKS["business_model"], "enabled_by_default": True},
        {**COMMON_BLOCKS["growth_tactics"], "enabled_by_default": True},
        {**COMMON_BLOCKS["lessons_learned"], "enabled_by_default": True},
        COMMON_BLOCKS["key_quotes"],
        COMMON_BLOCKS["action_items"],
        COMMON_BLOCKS["resources"]
    ],
    "parameters": COMMON_PARAMETERS,
    "user_prompt_template": COMMON_USER_PROMPT
}

TEMPLATE_LEARNING = {
    "name": "learning",
    "display_name": "Learning Notes",
    "description": "General-purpose learning summary with key concepts and actionable takeaways.",
    "is_system": True,
    "is_active": True,
    "locked": COMMON_LOCKED,
    "optional_blocks": [
        COMMON_BLOCKS["core_content"],
        COMMON_BLOCKS["guest_background"],
        {**COMMON_BLOCKS["key_points"], "enabled_by_default": True},
        {**COMMON_BLOCKS["key_concepts"], "enabled_by_default": True},
        COMMON_BLOCKS["examples"],
        {**COMMON_BLOCKS["action_items"], "enabled_by_default": True},
        COMMON_BLOCKS["resources"]
    ],
    "parameters": COMMON_PARAMETERS,
    "user_prompt_template": COMMON_USER_PROMPT
}

TEMPLATE_INTERVIEW = {
    "name": "interview",
    "display_name": "Interview & Stories",
    "description": "Focus on personal stories, life lessons, and memorable quotes from interviews.",
    "is_system": True,
    "is_active": True,
    "locked": COMMON_LOCKED,
    "optional_blocks": [
        COMMON_BLOCKS["core_content"],
        {**COMMON_BLOCKS["guest_background"], "enabled_by_default": True},
        COMMON_BLOCKS["unique_insights"],
        {**COMMON_BLOCKS["key_quotes"], "enabled_by_default": True},
        {**COMMON_BLOCKS["life_lessons"], "enabled_by_default": True},
        {**COMMON_BLOCKS["controversial_views"], "enabled_by_default": True},
        COMMON_BLOCKS["resources"]
    ],
    "parameters": COMMON_PARAMETERS,
    "user_prompt_template": COMMON_USER_PROMPT
}

# All default templates
DEFAULT_TEMPLATES = [
    TEMPLATE_INVESTMENT,
    TEMPLATE_TECH,
    TEMPLATE_STARTUP,
    TEMPLATE_LEARNING,
    TEMPLATE_INTERVIEW
]


def get_default_templates():
    """Get all default templates"""
    return DEFAULT_TEMPLATES


def get_template_by_name(name: str):
    """Get a specific default template by name"""
    for t in DEFAULT_TEMPLATES:
        if t["name"] == name:
            return t
    return None
