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
{user_focus_instruction}
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
    },
    # Stakeholder Analysis blocks
    "speaker_profile": {
        "id": "speaker_profile",
        "name": "Speaker Profile",
        "name_zh": "发言人画像",
        "prompt_fragment": "Analyze the speaker's background, current position, potential biases based on their affiliations, and vested interests that may influence their viewpoints.",
        "output_field": {
            "key": "speaker_profile",
            "type": "object",
            "items": {
                "background": "string",
                "position": "string",
                "affiliations": "array of strings",
                "potential_biases": "array of strings"
            },
            "description": "Speaker background and potential biases"
        },
        "enabled_by_default": True,
        "order": 60
    },
    "stakeholders": {
        "id": "stakeholders",
        "name": "Stakeholders",
        "name_zh": "利益相关方",
        "prompt_fragment": "Identify all stakeholders mentioned or implied: who benefits, who loses, who is affected by the topics discussed. Include companies, groups, and individuals.",
        "output_field": {
            "key": "stakeholders",
            "type": "array",
            "items": {
                "party": "string",
                "interest": "beneficiary/affected/loser",
                "reasoning": "string"
            },
            "description": "Stakeholders and their interests"
        },
        "enabled_by_default": True,
        "order": 61
    },
    "hidden_agendas": {
        "id": "hidden_agendas",
        "name": "Hidden Agendas",
        "name_zh": "潜在动机",
        "prompt_fragment": "Identify unstated motivations, hidden interests, or underlying reasons that may drive the speaker's narrative. What are they NOT saying?",
        "output_field": {
            "key": "hidden_agendas",
            "type": "array",
            "items": "string",
            "description": "Potential hidden motivations"
        },
        "enabled_by_default": True,
        "order": 62
    },
    "power_dynamics": {
        "id": "power_dynamics",
        "name": "Power Dynamics",
        "name_zh": "权力关系",
        "prompt_fragment": "Analyze the power dynamics: who has influence, whose voice is amplified, whose perspective is missing or underrepresented.",
        "output_field": {
            "key": "power_dynamics",
            "type": "object",
            "items": {
                "influential_parties": "array of strings",
                "missing_voices": "array of strings",
                "analysis": "string"
            },
            "description": "Power dynamics analysis"
        },
        "enabled_by_default": False,
        "order": 63
    },
    "contrasting_views": {
        "id": "contrasting_views",
        "name": "Contrasting Views",
        "name_zh": "对立观点",
        "prompt_fragment": "For each major claim, provide what opponents or critics might argue. Present the other side of the debate.",
        "output_field": {
            "key": "contrasting_views",
            "type": "array",
            "items": {
                "original_claim": "string",
                "counter_argument": "string",
                "source_perspective": "string"
            },
            "description": "Contrasting viewpoints"
        },
        "enabled_by_default": True,
        "order": 64
    },
    # Data & Evidence blocks
    "cited_data": {
        "id": "cited_data",
        "name": "Cited Data",
        "name_zh": "引用数据",
        "prompt_fragment": "Extract ALL specific numbers, statistics, percentages, and quantitative claims from the transcript. Include the exact figures as stated with their context.",
        "output_field": {
            "key": "cited_data",
            "type": "array",
            "items": {
                "data_point": "string (the exact number/statistic)",
                "context": "string",
                "claim": "string"
            },
            "description": "Quantitative data points cited"
        },
        "enabled_by_default": True,
        "order": 70
    },
    "data_sources": {
        "id": "data_sources",
        "name": "Data Sources",
        "name_zh": "数据来源",
        "prompt_fragment": "Identify the sources of data and claims: research institutions, studies, reports, or whether claims are unattributed. Rate credibility where possible.",
        "output_field": {
            "key": "data_sources",
            "type": "array",
            "items": {
                "source": "string",
                "type": "study/report/institution/personal/unattributed",
                "credibility_note": "string"
            },
            "description": "Sources of cited data"
        },
        "enabled_by_default": True,
        "order": 71
    },
    "factual_claims": {
        "id": "factual_claims",
        "name": "Factual Claims",
        "name_zh": "事实断言",
        "prompt_fragment": "List statements presented as facts that can be verified or fact-checked. These are objective claims about reality.",
        "output_field": {
            "key": "factual_claims",
            "type": "array",
            "items": {
                "claim": "string",
                "verifiable": "yes/partially/no",
                "source_mentioned": "string or null"
            },
            "description": "Verifiable factual claims"
        },
        "enabled_by_default": True,
        "order": 72
    },
    "opinion_claims": {
        "id": "opinion_claims",
        "name": "Opinion Claims",
        "name_zh": "观点断言",
        "prompt_fragment": "List statements that are opinions, predictions, or subjective judgments rather than verifiable facts.",
        "output_field": {
            "key": "opinion_claims",
            "type": "array",
            "items": {
                "claim": "string",
                "type": "opinion/prediction/judgment",
                "speaker": "string"
            },
            "description": "Subjective opinion claims"
        },
        "enabled_by_default": True,
        "order": 73
    },
    "missing_data": {
        "id": "missing_data",
        "name": "Missing Data",
        "name_zh": "缺失数据",
        "prompt_fragment": "Identify important data or evidence that SHOULD have been provided but wasn't. What questions remain unanswered? What evidence would strengthen or weaken the arguments?",
        "output_field": {
            "key": "missing_data",
            "type": "array",
            "items": "string",
            "description": "Missing evidence and unanswered questions"
        },
        "enabled_by_default": True,
        "order": 74
    },
    "frameworks": {
        "id": "frameworks",
        "name": "Frameworks",
        "name_zh": "思维框架",
        "prompt_fragment": "Extract any mental models, analytical frameworks, methodologies, or structured approaches mentioned that can be reused.",
        "output_field": {
            "key": "frameworks",
            "type": "array",
            "items": {
                "name": "string",
                "description": "string",
                "application": "string"
            },
            "description": "Reusable frameworks and mental models"
        },
        "enabled_by_default": False,
        "order": 75
    }
}


# =============================================================================
# TEMPLATE DEFINITIONS
# =============================================================================

TEMPLATE_INVESTMENT = {
    "name": "investment",
    "display_name": "Investment Analysis",
    "display_name_zh": "投资分析",
    "description": "Extract investment signals, stock mentions, and market insights from finance podcasts.",
    "description_zh": "从财经播客中提取投资信号、股票提及和市场洞察",
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

TEMPLATE_STAKEHOLDER = {
    "name": "stakeholder",
    "display_name": "Stakeholder Analysis",
    "display_name_zh": "利益相关方分析",
    "description": "Analyze speakers, stakeholders, hidden agendas, and power dynamics. Who benefits? Who loses?",
    "description_zh": "分析发言人、利益相关方、潜在动机和权力关系。谁受益？谁受损？",
    "is_system": True,
    "is_active": True,
    "locked": {
        **COMMON_LOCKED,
        "system_prompt": "You are a critical analyst specializing in stakeholder analysis and power dynamics. Your task is to identify who benefits, who loses, and what hidden interests may be driving the narrative. Be skeptical and analytical. Always output valid JSON only, no other text."
    },
    "optional_blocks": [
        COMMON_BLOCKS["core_content"],
        {**COMMON_BLOCKS["speaker_profile"], "enabled_by_default": True},
        {**COMMON_BLOCKS["stakeholders"], "enabled_by_default": True},
        {**COMMON_BLOCKS["hidden_agendas"], "enabled_by_default": True},
        COMMON_BLOCKS["power_dynamics"],
        {**COMMON_BLOCKS["contrasting_views"], "enabled_by_default": True},
        COMMON_BLOCKS["key_quotes"]
    ],
    "parameters": COMMON_PARAMETERS,
    "user_prompt_template": COMMON_USER_PROMPT
}

TEMPLATE_DATA_EVIDENCE = {
    "name": "data_evidence",
    "display_name": "Data & Evidence",
    "display_name_zh": "数据与证据",
    "description": "Extract cited data, verify sources, distinguish facts from opinions. What evidence is provided? What's missing?",
    "description_zh": "提取引用数据，验证来源，区分事实与观点。提供了什么证据？缺少什么？",
    "is_system": True,
    "is_active": True,
    "locked": {
        **COMMON_LOCKED,
        "system_prompt": "You are a fact-checker and research analyst. Your task is to extract all data points, identify their sources, and distinguish between factual claims and opinions. Be rigorous about evidence. Always output valid JSON only, no other text."
    },
    "optional_blocks": [
        COMMON_BLOCKS["core_content"],
        {**COMMON_BLOCKS["cited_data"], "enabled_by_default": True},
        {**COMMON_BLOCKS["data_sources"], "enabled_by_default": True},
        {**COMMON_BLOCKS["factual_claims"], "enabled_by_default": True},
        {**COMMON_BLOCKS["opinion_claims"], "enabled_by_default": True},
        {**COMMON_BLOCKS["missing_data"], "enabled_by_default": True},
        COMMON_BLOCKS["frameworks"]
    ],
    "parameters": COMMON_PARAMETERS,
    "user_prompt_template": COMMON_USER_PROMPT
}

# All default templates
DEFAULT_TEMPLATES = [
    TEMPLATE_INVESTMENT,
    TEMPLATE_STAKEHOLDER,
    TEMPLATE_DATA_EVIDENCE
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
