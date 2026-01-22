# -*- coding: utf-8 -*-
"""
Prompt Builder

Dynamically builds prompts from structured templates.
Handles locked sections, optional blocks, and parameters.
"""
import json
import logging
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Dynamic prompt builder for structured templates"""

    # Default max chars for transcript truncation
    DEFAULT_MAX_CHARS = 100000

    def __init__(self, max_chars: int = None):
        self.max_chars = max_chars or self.DEFAULT_MAX_CHARS

    def build(
        self,
        template: Dict,
        transcript: str,
        enabled_blocks: List[str] = None,
        params: Dict = None,
        **context
    ) -> List[Dict[str, str]]:
        """
        Build messages list from template.

        Args:
            template: Template document from database
            transcript: Podcast transcript text
            enabled_blocks: List of block IDs to enable (None = use defaults)
            params: Parameter values (e.g., {"length": "long"})
            **context: Additional context (title, guest, etc.)

        Returns:
            Messages list for LLM API
        """
        params = params or {}
        locked = template.get("locked", {})
        optional_blocks = template.get("optional_blocks", [])
        parameters = template.get("parameters", {})

        # 1. Build system message
        system_prompt = locked.get("system_prompt", "You are a helpful assistant.")

        # 2. Resolve enabled blocks
        active_blocks = self._resolve_enabled_blocks(optional_blocks, enabled_blocks)

        # 3. Build instructions from active blocks
        blocks_instructions = self._build_blocks_instructions(active_blocks)

        # 4. Build dynamic schema from active blocks
        dynamic_schema = self._build_dynamic_schema(locked, active_blocks)

        # 5. Resolve parameter values and build instructions
        length_instruction = self._build_param_instruction(parameters, params, "length")
        language_instruction = self._build_param_instruction(parameters, params, "language")

        # 6. Truncate transcript
        truncated_transcript = self._truncate_text(transcript)

        # 7. Build user prompt from template
        user_prompt_template = template.get("user_prompt_template", "")
        output_format_instruction = locked.get("output_format_instruction", "")

        user_prompt = user_prompt_template.format(
            title=context.get("title", "Unknown"),
            guest=context.get("guest", "Unknown"),
            length_instruction=length_instruction,
            language_instruction=language_instruction,
            optional_blocks_instructions=blocks_instructions,
            output_format_instruction=output_format_instruction,
            dynamic_schema=dynamic_schema,
            transcript=truncated_transcript
        )

        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ]

    def _resolve_enabled_blocks(
        self,
        all_blocks: List[Dict],
        enabled_blocks: List[str] = None
    ) -> List[Dict]:
        """Resolve which blocks are enabled"""
        if enabled_blocks is not None:
            # User specified blocks
            return [b for b in all_blocks if b.get("id") in enabled_blocks]
        else:
            # Use defaults
            return [b for b in all_blocks if b.get("enabled_by_default", False)]

    def _build_blocks_instructions(self, blocks: List[Dict]) -> str:
        """Build instruction text from enabled blocks"""
        if not blocks:
            return ""

        instructions = ["Please analyze and extract the following:"]
        for i, block in enumerate(sorted(blocks, key=lambda x: x.get("order", 0)), 1):
            fragment = block.get("prompt_fragment", "")
            name = block.get("name", "")
            if fragment:
                instructions.append(f"{i}. **{name}**: {fragment}")

        return "\n".join(instructions)

    def _build_dynamic_schema(self, locked: Dict, blocks: List[Dict]) -> str:
        """Build JSON schema string from locked fields and enabled blocks"""
        schema = {}

        # Add required fields
        required_fields = locked.get("required_fields", ["tldr", "tags"])
        for field in required_fields:
            if field == "tldr":
                schema["tldr"] = "string (1-2 sentence summary, required)"
            elif field == "tags":
                schema["tags"] = "[string] (3-5 relevant tags, required)"
            else:
                schema[field] = "string (required)"

        # Add fields from enabled blocks
        for block in sorted(blocks, key=lambda x: x.get("order", 0)):
            output_field = block.get("output_field", {})
            key = output_field.get("key")
            if not key:
                continue

            field_type = output_field.get("type", "string")
            description = output_field.get("description", "")
            items = output_field.get("items")

            if field_type == "string":
                schema[key] = f"string ({description})"
            elif field_type == "array":
                if isinstance(items, str):
                    schema[key] = f"[{items}] ({description})"
                elif isinstance(items, dict):
                    schema[key] = f"[{json.dumps(items)}] ({description})"
                else:
                    schema[key] = f"[...] ({description})"
            elif field_type == "object":
                schema[key] = f"object ({description})"

        # Format as JSON example
        return "Expected JSON structure:\n```json\n" + json.dumps(schema, indent=2) + "\n```"

    def _build_param_instruction(
        self,
        parameters: Dict,
        user_params: Dict,
        param_name: str
    ) -> str:
        """Build instruction string for a parameter"""
        param_def = parameters.get(param_name)
        if not param_def:
            return ""

        # Get user value or default
        value = user_params.get(param_name, param_def.get("default"))
        if not value:
            return ""

        # Get mapped instruction
        mapping = param_def.get("prompt_mapping", {})
        return mapping.get(value, "")

    def _truncate_text(self, text: str) -> str:
        """Smart truncation preserving head and tail"""
        if len(text) <= self.max_chars:
            return text

        # Keep 60% head, 30% tail
        head_size = int(self.max_chars * 0.6)
        tail_size = int(self.max_chars * 0.3)

        head = text[:head_size]
        tail = text[-tail_size:]

        return f"{head}\n\n[... content truncated, total {len(text)} characters ...]\n\n{tail}"

    def get_max_tokens(self, template: Dict, params: Dict = None) -> int:
        """
        Resolve max_tokens based on template and params.

        Priority:
        1. Explicit max_tokens in params
        2. Token hint from length parameter
        3. Default from template
        4. Fallback to 4096
        """
        params = params or {}

        # Check explicit max_tokens
        if "max_tokens" in params:
            return int(params["max_tokens"])

        # Check length parameter for token hint
        parameters = template.get("parameters", {})
        length_param = parameters.get("length")
        if length_param and "length" in params:
            length_value = params["length"]
            options = length_param.get("options", [])
            for opt in options:
                if opt.get("value") == length_value:
                    token_hint = opt.get("token_hint")
                    if token_hint:
                        return int(token_hint)

        # Check default max_tokens in parameters
        max_tokens_param = parameters.get("max_tokens")
        if max_tokens_param:
            return int(max_tokens_param.get("default", 4096))

        # Fallback
        return 4096

    def get_enabled_block_ids(
        self,
        template: Dict,
        enabled_blocks: List[str] = None
    ) -> List[str]:
        """Get list of enabled block IDs"""
        all_blocks = template.get("optional_blocks", [])
        active = self._resolve_enabled_blocks(all_blocks, enabled_blocks)
        return [b.get("id") for b in active]
