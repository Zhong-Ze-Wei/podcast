# -*- coding: utf-8 -*-
"""
Prompt Builder

动态构建 prompt，从模板生成精确的 JSON Schema。
"""
import json
import logging
from typing import Dict, List

logger = logging.getLogger(__name__)


class PromptBuilder:
    """Dynamic prompt builder for structured templates"""

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
        从模板构建 LLM messages。

        Args:
            template: 数据库中的模板文档
            transcript: 播客转录文本
            enabled_blocks: 启用的 block IDs
            params: 参数 {"length": "long", "language": "zh"}
            **context: title, guest 等
        """
        params = params or {}
        locked = template.get("locked", {})
        optional_blocks = template.get("optional_blocks", [])
        parameters = template.get("parameters", {})

        system_prompt = locked.get("system_prompt", "You are a helpful assistant.")

        active_blocks = self._resolve_enabled_blocks(optional_blocks, enabled_blocks)
        blocks_instructions = self._build_blocks_instructions(active_blocks)
        dynamic_schema = self._build_dynamic_schema(locked, active_blocks)

        length_instruction = self._build_param_instruction(parameters, params, "length")
        language_instruction = self._build_param_instruction(parameters, params, "language")

        truncated_transcript = self._truncate_text(transcript)

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
        if enabled_blocks is not None:
            return [b for b in all_blocks if b.get("id") in enabled_blocks]
        return [b for b in all_blocks if b.get("enabled_by_default", False)]

    def _build_blocks_instructions(self, blocks: List[Dict]) -> str:
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
        """
        生成精确的 JSON Schema 示例。

        关键改进：输出一个完整的 JSON 示例而非自然语言描述，
        让 LLM 直接参照格式输出。
        """
        # 构建示例值
        example = {}

        required_fields = locked.get("required_fields", ["tldr", "tags"])
        for field in required_fields:
            if field == "tldr":
                example["tldr"] = "1-2 sentence summary of the episode"
            elif field == "tags":
                example["tags"] = ["tag1", "tag2", "tag3"]
            else:
                example[field] = f"(required) {field}"

        for block in sorted(blocks, key=lambda x: x.get("order", 0)):
            output_field = block.get("output_field", {})
            key = output_field.get("key")
            if not key:
                continue

            field_type = output_field.get("type", "string")
            items = output_field.get("items")

            if field_type == "string":
                example[key] = f"(string) {output_field.get('description', '')}"
            elif field_type == "array":
                if isinstance(items, dict):
                    # 结构化数组：生成带示例 key 的对象
                    example_obj = {}
                    for k, v in items.items():
                        example_obj[k] = f"({v})"
                    example[key] = [example_obj]
                else:
                    example[key] = [f"(string) item"]
            elif field_type == "object":
                example[key] = {"key": "value"}

        # 生成严格的格式说明 + 示例
        field_list = ", ".join(list(example.keys()))
        schema_text = (
            f"CRITICAL: Output ONLY a valid JSON object with exactly these keys: [{field_list}]\n"
            f"Do NOT add any keys not listed below.\n"
            f"Do NOT wrap in markdown code blocks.\n\n"
            f"Example structure:\n"
            f"```json\n{json.dumps(example, indent=2, ensure_ascii=False)}\n```"
        )
        return schema_text

    def _build_param_instruction(
        self,
        parameters: Dict,
        user_params: Dict,
        param_name: str
    ) -> str:
        param_def = parameters.get(param_name)
        if not param_def:
            return ""

        value = user_params.get(param_name, param_def.get("default"))
        if not value:
            return ""

        mapping = param_def.get("prompt_mapping", {})
        return mapping.get(value, "")

    def _truncate_text(self, text: str) -> str:
        """
        智能截断：保留开头、中间抽样、结尾。
        播客内容通常中间最核心（开头寒暄，结尾总结）。
        """
        if len(text) <= self.max_chars:
            return text

        # 40% 头部 + 20% 中间抽样 + 30% 尾部
        head_size = int(self.max_chars * 0.4)
        mid_size = int(self.max_chars * 0.2)
        tail_size = int(self.max_chars * 0.3)

        head = text[:head_size]

        # 从中间区域抽取
        mid_start = len(text) // 2 - mid_size // 2
        mid = text[mid_start:mid_start + mid_size]

        tail = text[-tail_size:]

        return (
            f"{head}\n\n"
            f"[... beginning truncated ...]\n\n"
            f"{mid}\n\n"
            f"[... middle section sampled ...]\n\n"
            f"{tail}"
        )

    def get_max_tokens(self, template: Dict, params: Dict = None) -> int:
        """
        解析 max_tokens。

        优先级：params.max_tokens > length token_hint > 默认 4096
        """
        params = params or {}

        if "max_tokens" in params:
            return int(params["max_tokens"])

        parameters = template.get("parameters", {})
        length_param = parameters.get("length")
        if length_param and "length" in params:
            length_value = params["length"]
            for opt in length_param.get("options", []):
                if opt.get("value") == length_value:
                    token_hint = opt.get("token_hint")
                    if token_hint:
                        return int(token_hint)

        return 4096

    def get_enabled_block_ids(
        self,
        template: Dict,
        enabled_blocks: List[str] = None
    ) -> List[str]:
        all_blocks = template.get("optional_blocks", [])
        active = self._resolve_enabled_blocks(all_blocks, enabled_blocks)
        return [b.get("id") for b in active]
