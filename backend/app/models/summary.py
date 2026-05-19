# -*- coding: utf-8 -*-
"""
Summary 数据模型

统一的 v3 摘要模型，动态 blocks 展开。
"""
from typing import Dict, Any, Optional, List


class Summary:
    """摘要结果模型"""

    @staticmethod
    def to_response(doc: dict, template: dict = None) -> Optional[dict]:
        """
        转换为 API 响应格式。

        动态从 content 中展开 enabled_blocks 对应的字段，
        不再硬编码每个 block 字段。
        """
        if not doc:
            return None

        content = doc.get("content", {})
        content_zh = doc.get("content_zh", {})

        response = {
            "id": str(doc["_id"]),
            "episode_id": str(doc["episode_id"]) if doc.get("episode_id") else None,
            "template_name": doc.get("template_name", ""),
            "version": doc.get("version", "v3"),
            "tldr": doc.get("tldr", ""),
            "tldr_zh": content_zh.get("tldr", ""),
            "tags": doc.get("tags", []),
            "content": content,
            "content_zh": content_zh,
            "has_translation": bool(content_zh),
            "model": doc.get("model", ""),
            "tokens_used": doc.get("tokens_used", {}),
            "created_at": doc.get("created_at").isoformat() + "Z"
            if doc.get("created_at") else None,
            "translated_at": doc.get("translated_at").isoformat() + "Z"
            if doc.get("translated_at") else None,
        }

        # 动态展开 blocks 字段到顶层
        enabled_blocks = doc.get("enabled_blocks", [])
        if enabled_blocks and template:
            optional_blocks = template.get("optional_blocks", [])
            blocks_map = {b.get("id"): b for b in optional_blocks}

            blocks = []
            for block_id in enabled_blocks:
                block_def = blocks_map.get(block_id)
                if not block_def:
                    continue

                output_field = block_def.get("output_field", {})
                key = output_field.get("key")
                if not key:
                    continue

                value = content.get(key)
                if value is None:
                    continue

                # 展开到顶层（兼容前端现有渲染）
                response[key] = value

                # 构建 blocks 数组（供新版前端使用）
                blocks.append({
                    "id": block_id,
                    "title": block_def.get("name", ""),
                    "title_zh": block_def.get("name_zh", ""),
                    "type": _infer_block_type(output_field),
                    "content": value,
                })

            response["blocks"] = blocks
        elif enabled_blocks:
            # 无 template 信息时，直接展开 content 中存在的字段
            for key, value in content.items():
                if key in ("tldr", "tags"):
                    continue
                if value is not None and value != "" and value != []:
                    response[key] = value

        return response


def _infer_block_type(output_field: dict) -> str:
    """从 output_field 定义推断前端渲染类型"""
    field_type = output_field.get("type", "string")
    items = output_field.get("items")

    if field_type == "string":
        return "text"
    elif field_type == "array":
        if isinstance(items, dict):
            # 有子结构：投资信号、引用、概念等
            if "type" in items and "target" in items:
                return "signals"
            elif "speaker" in items:
                return "quotes"
            elif "concept" in items:
                return "concepts"
            return "objects"
        return "list"
    elif field_type == "object":
        return "object"
    return "text"
