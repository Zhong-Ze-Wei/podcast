# -*- coding: utf-8 -*-
"""
Schema Validator

校验 LLM 输出是否符合预期 schema。
正常模式下：required 字段必须存在，block 字段缺失则 warning 并补默认值。
"""
import logging
from typing import Dict, List, Tuple

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Schema validation error"""
    def __init__(self, message: str, missing_fields: List[str] = None):
        super().__init__(message)
        self.missing_fields = missing_fields or []


class SchemaValidator:
    """
    校验 LLM JSON 输出。

    strictness:
    - strict: 所有字段必须存在且类型匹配
    - normal: required 必须存在，block 字段缺失补默认值
    """

    STRICTNESS_STRICT = "strict"
    STRICTNESS_NORMAL = "normal"

    def __init__(self, strictness: str = None):
        self.strictness = strictness or self.STRICTNESS_NORMAL

    def validate(
        self,
        data: Dict,
        template: Dict,
        enabled_blocks: List[str] = None
    ) -> Tuple[bool, List[str]]:
        """
        校验 LLM 输出。

        Returns:
            (is_valid, errors)
        """
        errors = []
        locked = template.get("locked", {})
        all_blocks = template.get("optional_blocks", [])

        # 1. 检查 required fields
        required_fields = locked.get("required_fields", ["tldr", "tags"])
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
            elif self.strictness == self.STRICTNESS_STRICT:
                if field == "tldr" and not isinstance(data[field], str):
                    errors.append(f"'tldr' must be string, got {type(data[field]).__name__}")
                elif field == "tags" and not isinstance(data[field], list):
                    errors.append(f"'tags' must be array, got {type(data[field]).__name__}")

        # 2. 检查 block 字段
        if enabled_blocks is not None:
            active_blocks = [b for b in all_blocks if b.get("id") in enabled_blocks]
        else:
            active_blocks = [b for b in all_blocks if b.get("enabled_by_default", False)]

        for block in active_blocks:
            output_field = block.get("output_field", {})
            key = output_field.get("key")
            if not key:
                continue

            if key not in data:
                if self.strictness == self.STRICTNESS_STRICT:
                    errors.append(f"Missing field from block '{block.get('id')}': {key}")
                else:
                    logger.warning(f"Missing block field: {key} (block: {block.get('id')})")

        return len(errors) == 0, errors

    def ensure_required_fields(self, data: Dict, template: Dict) -> Dict:
        """补全缺失的 required 字段默认值"""
        locked = template.get("locked", {})
        required_fields = locked.get("required_fields", ["tldr", "tags"])

        result = dict(data)
        for field in required_fields:
            if field not in result:
                if field == "tldr":
                    result["tldr"] = "Summary not available"
                elif field == "tags":
                    result["tags"] = []
                else:
                    result[field] = ""
                logger.warning(f"Filled default for missing required field: {field}")

        return result
