# -*- coding: utf-8 -*-
"""
Prompt Template Model

Structured prompt template for podcast summarization.
Supports locked sections, optional blocks, and parameters.
"""
from datetime import datetime
from typing import Dict, List, Any, Optional
from bson import ObjectId


class PromptTemplate:
    """Prompt Template Model"""

    COLLECTION = "prompt_templates"

    # Field definitions for optional blocks
    FIELD_TYPES = ["string", "array", "object"]

    # Parameter types
    PARAM_TYPES = ["enum", "range", "boolean"]

    @staticmethod
    def create_document(
        name: str,
        display_name: str,
        description: str,
        locked: Dict,
        optional_blocks: List[Dict],
        parameters: Dict,
        user_prompt_template: str,
        is_system: bool = False,
        is_active: bool = True,
        parent_id: ObjectId = None
    ) -> Dict:
        """Create a new template document"""
        now = datetime.utcnow()
        return {
            "name": name,
            "display_name": display_name,
            "description": description,

            # Template structure
            "locked": locked,
            "optional_blocks": optional_blocks,
            "parameters": parameters,
            "user_prompt_template": user_prompt_template,

            # Metadata
            "is_system": is_system,
            "is_active": is_active,
            "parent_id": parent_id,  # For copied templates
            "version": 1,

            "created_at": now,
            "updated_at": now
        }

    @staticmethod
    def create_locked_section(
        system_prompt: str,
        output_format_instruction: str,
        required_fields: List[str]
    ) -> Dict:
        """Create locked section (immutable by users)"""
        return {
            "system_prompt": system_prompt,
            "output_format_instruction": output_format_instruction,
            "required_fields": required_fields
        }

    @staticmethod
    def create_optional_block(
        block_id: str,
        name: str,
        name_zh: str,
        prompt_fragment: str,
        output_field: Dict,
        enabled_by_default: bool = False,
        order: int = 0
    ) -> Dict:
        """Create an optional block definition"""
        return {
            "id": block_id,
            "name": name,
            "name_zh": name_zh,
            "prompt_fragment": prompt_fragment,
            "output_field": output_field,
            "enabled_by_default": enabled_by_default,
            "order": order
        }

    @staticmethod
    def create_enum_parameter(
        name: str,
        label: str,
        label_zh: str,
        options: List[Dict],
        default: str,
        prompt_mapping: Dict[str, str]
    ) -> Dict:
        """Create an enum parameter"""
        return {
            "type": "enum",
            "name": name,
            "label": label,
            "label_zh": label_zh,
            "options": options,
            "default": default,
            "prompt_mapping": prompt_mapping
        }

    @staticmethod
    def to_response(doc: Dict) -> Dict:
        """Convert document to API response"""
        if not doc:
            return None

        return {
            "id": str(doc["_id"]),
            "name": doc.get("name"),
            "display_name": doc.get("display_name"),
            "description": doc.get("description"),
            "locked": doc.get("locked", {}),
            "optional_blocks": doc.get("optional_blocks", []),
            "parameters": doc.get("parameters", {}),
            "user_prompt_template": doc.get("user_prompt_template", ""),
            "is_system": doc.get("is_system", False),
            "is_active": doc.get("is_active", True),
            "parent_id": str(doc["parent_id"]) if doc.get("parent_id") else None,
            "version": doc.get("version", 1),
            "created_at": doc.get("created_at").isoformat() if doc.get("created_at") else None,
            "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None
        }

    @staticmethod
    def to_list_response(doc: Dict) -> Dict:
        """Convert document to list item response (lightweight)"""
        if not doc:
            return None

        return {
            "id": str(doc["_id"]),
            "name": doc.get("name"),
            "display_name": doc.get("display_name"),
            "description": doc.get("description"),
            "is_system": doc.get("is_system", False),
            "is_active": doc.get("is_active", True),
            "blocks_count": len(doc.get("optional_blocks", [])),
            "updated_at": doc.get("updated_at").isoformat() if doc.get("updated_at") else None
        }


class PromptTemplateModel:
    """Prompt Template database operations"""

    def __init__(self, db):
        self.db = db
        self.collection = db[PromptTemplate.COLLECTION]

    def find_by_name(self, name: str) -> Optional[Dict]:
        """Find template by name"""
        return self.collection.find_one({"name": name, "is_active": True})

    def find_by_id(self, template_id: str) -> Optional[Dict]:
        """Find template by ID"""
        try:
            return self.collection.find_one({"_id": ObjectId(template_id)})
        except:
            return None

    def find_all_active(self) -> List[Dict]:
        """Find all active templates"""
        return list(self.collection.find({"is_active": True}).sort("name", 1))

    def find_system_templates(self) -> List[Dict]:
        """Find system templates only"""
        return list(self.collection.find({
            "is_system": True,
            "is_active": True
        }).sort("name", 1))

    def create(self, template_doc: Dict) -> ObjectId:
        """Create a new template"""
        result = self.collection.insert_one(template_doc)
        return result.inserted_id

    def update(self, template_id: str, updates: Dict) -> bool:
        """Update a template (only non-system templates)"""
        try:
            oid = ObjectId(template_id)
        except:
            return False

        # Check if system template
        existing = self.collection.find_one({"_id": oid})
        if existing and existing.get("is_system"):
            return False  # Cannot modify system templates

        updates["updated_at"] = datetime.utcnow()
        updates["version"] = existing.get("version", 1) + 1

        result = self.collection.update_one(
            {"_id": oid},
            {"$set": updates}
        )
        return result.modified_count > 0

    def duplicate(self, template_id: str, new_name: str, new_display_name: str) -> Optional[ObjectId]:
        """Duplicate a template"""
        try:
            oid = ObjectId(template_id)
        except:
            return None

        original = self.collection.find_one({"_id": oid})
        if not original:
            return None

        # Check if name already exists
        if self.collection.find_one({"name": new_name}):
            return None

        # Create copy
        now = datetime.utcnow()
        new_doc = {
            "name": new_name,
            "display_name": new_display_name,
            "description": original.get("description", ""),
            "locked": original.get("locked", {}),
            "optional_blocks": original.get("optional_blocks", []),
            "parameters": original.get("parameters", {}),
            "user_prompt_template": original.get("user_prompt_template", ""),
            "is_system": False,  # Copies are never system templates
            "is_active": True,
            "parent_id": oid,
            "version": 1,
            "created_at": now,
            "updated_at": now
        }

        result = self.collection.insert_one(new_doc)
        return result.inserted_id

    def delete(self, template_id: str) -> bool:
        """Delete a template (only non-system templates)"""
        try:
            oid = ObjectId(template_id)
        except:
            return False

        # Check if system template
        existing = self.collection.find_one({"_id": oid})
        if existing and existing.get("is_system"):
            return False  # Cannot delete system templates

        result = self.collection.delete_one({"_id": oid})
        return result.deleted_count > 0

    def ensure_indexes(self):
        """Create indexes"""
        self.collection.create_index("name", unique=True)
        self.collection.create_index("is_active")
        self.collection.create_index("is_system")
