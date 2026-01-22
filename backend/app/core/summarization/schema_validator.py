# -*- coding: utf-8 -*-
"""
Schema Validator

Validates LLM output against expected schema.
Provides flexible validation with configurable strictness.
"""
import logging
from typing import Dict, List, Any, Tuple, Optional

logger = logging.getLogger(__name__)


class ValidationError(Exception):
    """Schema validation error"""
    def __init__(self, message: str, missing_fields: List[str] = None, extra_info: Dict = None):
        super().__init__(message)
        self.missing_fields = missing_fields or []
        self.extra_info = extra_info or {}


class SchemaValidator:
    """
    Validates LLM output against template schema.

    Strictness levels:
    - strict: All required fields must exist with correct types
    - normal: Required fields must exist, type mismatches logged as warnings
    - relaxed: Only check required fields exist, ignore types
    """

    STRICTNESS_STRICT = "strict"
    STRICTNESS_NORMAL = "normal"
    STRICTNESS_RELAXED = "relaxed"

    def __init__(self, strictness: str = None):
        self.strictness = strictness or self.STRICTNESS_NORMAL

    def validate(
        self,
        data: Dict,
        template: Dict,
        enabled_blocks: List[str] = None
    ) -> Tuple[bool, List[str]]:
        """
        Validate output data against template schema.

        Args:
            data: LLM output data (parsed JSON)
            template: Template document
            enabled_blocks: List of enabled block IDs

        Returns:
            Tuple of (is_valid, list of error messages)
        """
        errors = []
        locked = template.get("locked", {})
        all_blocks = template.get("optional_blocks", [])

        # 1. Check required fields from locked section
        required_fields = locked.get("required_fields", ["tldr", "tags"])
        for field in required_fields:
            if field not in data:
                errors.append(f"Missing required field: {field}")
            elif self.strictness == self.STRICTNESS_STRICT:
                # Type check for strict mode
                if field == "tldr" and not isinstance(data[field], str):
                    errors.append(f"Field 'tldr' must be string, got {type(data[field]).__name__}")
                elif field == "tags" and not isinstance(data[field], list):
                    errors.append(f"Field 'tags' must be array, got {type(data[field]).__name__}")

        # 2. Check enabled blocks' output fields
        if enabled_blocks is not None:
            active_blocks = [b for b in all_blocks if b.get("id") in enabled_blocks]
        else:
            active_blocks = [b for b in all_blocks if b.get("enabled_by_default", False)]

        for block in active_blocks:
            output_field = block.get("output_field", {})
            key = output_field.get("key")
            if not key:
                continue

            expected_type = output_field.get("type", "string")

            if key not in data:
                if self.strictness == self.STRICTNESS_STRICT:
                    errors.append(f"Missing field from block '{block.get('id')}': {key}")
                else:
                    logger.warning(f"Missing optional field: {key}")
            elif self.strictness == self.STRICTNESS_STRICT:
                # Type validation
                actual_value = data[key]
                if expected_type == "string" and not isinstance(actual_value, str):
                    errors.append(f"Field '{key}' must be string")
                elif expected_type == "array" and not isinstance(actual_value, list):
                    errors.append(f"Field '{key}' must be array")
                elif expected_type == "object" and not isinstance(actual_value, dict):
                    errors.append(f"Field '{key}' must be object")

        is_valid = len(errors) == 0
        return is_valid, errors

    def validate_or_raise(
        self,
        data: Dict,
        template: Dict,
        enabled_blocks: List[str] = None
    ) -> Dict:
        """
        Validate and raise ValidationError if invalid.

        Returns the data if valid.
        """
        is_valid, errors = self.validate(data, template, enabled_blocks)
        if not is_valid:
            missing = [e.split(": ")[-1] for e in errors if "Missing" in e]
            raise ValidationError(
                f"Schema validation failed: {'; '.join(errors)}",
                missing_fields=missing,
                extra_info={"error_count": len(errors)}
            )
        return data

    def ensure_required_fields(self, data: Dict, template: Dict) -> Dict:
        """
        Ensure required fields exist with default values if missing.

        This is a lenient mode that fills in defaults rather than failing.
        """
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
                logger.warning(f"Added default value for missing field: {field}")

        return result

    def get_expected_fields(
        self,
        template: Dict,
        enabled_blocks: List[str] = None
    ) -> Dict[str, str]:
        """
        Get dictionary of expected fields and their types.

        Useful for debugging and documentation.
        """
        fields = {}
        locked = template.get("locked", {})
        all_blocks = template.get("optional_blocks", [])

        # Required fields
        for field in locked.get("required_fields", []):
            if field == "tldr":
                fields["tldr"] = "string (required)"
            elif field == "tags":
                fields["tags"] = "array (required)"
            else:
                fields[field] = "string (required)"

        # Block fields
        if enabled_blocks is not None:
            active_blocks = [b for b in all_blocks if b.get("id") in enabled_blocks]
        else:
            active_blocks = [b for b in all_blocks if b.get("enabled_by_default", False)]

        for block in active_blocks:
            output_field = block.get("output_field", {})
            key = output_field.get("key")
            if key:
                field_type = output_field.get("type", "string")
                fields[key] = f"{field_type} (from block: {block.get('id')})"

        return fields
