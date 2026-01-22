# -*- coding: utf-8 -*-
"""
Summarization Core Module

Provides structured podcast summarization with:
- Database-driven prompt templates
- Dynamic prompt building
- Output schema validation
- Extensible architecture for future LangChain integration
"""
from .engine import SummarizationEngine, get_summarization_engine
from .prompt_builder import PromptBuilder
from .schema_validator import SchemaValidator

__all__ = [
    "SummarizationEngine",
    "get_summarization_engine",
    "PromptBuilder",
    "SchemaValidator"
]
