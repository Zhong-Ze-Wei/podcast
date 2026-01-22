# -*- coding: utf-8 -*-
"""
Prompt Templates API

CRUD operations for prompt templates.
Provides endpoints for template management in the settings UI.
"""
from flask import Blueprint, request
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime
import logging

from ..models.prompt_template import PromptTemplate, PromptTemplateModel
from .utils import success_response, error_response

logger = logging.getLogger(__name__)
prompt_templates_bp = Blueprint("prompt_templates", __name__)


def get_db():
    from .. import get_db as _get_db
    return _get_db()


@prompt_templates_bp.route("/", methods=["GET"])
def list_templates():
    """
    List all active templates.

    Query Params:
        - include_system: Include system templates (default: true)
    """
    db = get_db()
    model = PromptTemplateModel(db)

    include_system = request.args.get("include_system", "true").lower() == "true"

    if include_system:
        templates = model.find_all_active()
    else:
        templates = list(db.prompt_templates.find({
            "is_active": True,
            "is_system": False
        }).sort("name", 1))

    return success_response({
        "templates": [PromptTemplate.to_list_response(t) for t in templates],
        "total": len(templates)
    })


@prompt_templates_bp.route("/<template_id>", methods=["GET"])
def get_template(template_id):
    """Get a single template by ID or name"""
    db = get_db()
    model = PromptTemplateModel(db)

    # Try by ID first
    template = model.find_by_id(template_id)

    # If not found, try by name
    if not template:
        template = model.find_by_name(template_id)

    if not template:
        return error_response("Template not found", "TEMPLATE_NOT_FOUND", 404)

    return success_response(PromptTemplate.to_response(template))


@prompt_templates_bp.route("/", methods=["POST"])
def create_template():
    """
    Create a new template.

    Request Body:
        - name: Unique template name
        - display_name: Display name
        - description: Template description
        - optional_blocks: List of optional block configurations
        - parameters: Parameter definitions
        - user_prompt_template: User prompt template string
    """
    db = get_db()
    model = PromptTemplateModel(db)

    data = request.get_json()
    if not data:
        return error_response("Request body required", "INVALID_REQUEST", 400)

    name = data.get("name")
    if not name:
        return error_response("Template name is required", "MISSING_NAME", 400)

    # Check if name exists
    existing = model.find_by_name(name)
    if existing:
        return error_response(f"Template name '{name}' already exists", "NAME_EXISTS", 409)

    # Create template document
    from ..core.summarization.defaults.templates import COMMON_LOCKED, COMMON_USER_PROMPT, COMMON_PARAMETERS

    template_doc = PromptTemplate.create_document(
        name=name,
        display_name=data.get("display_name", name),
        description=data.get("description", ""),
        locked=data.get("locked", COMMON_LOCKED),
        optional_blocks=data.get("optional_blocks", []),
        parameters=data.get("parameters", COMMON_PARAMETERS),
        user_prompt_template=data.get("user_prompt_template", COMMON_USER_PROMPT),
        is_system=False,  # User-created templates are never system templates
        is_active=True
    )

    template_id = model.create(template_doc)
    template = model.find_by_id(str(template_id))

    logger.info(f"Created template: {name}")

    return success_response(
        PromptTemplate.to_response(template),
        status=201
    )


@prompt_templates_bp.route("/<template_id>", methods=["PUT"])
def update_template(template_id):
    """
    Update a template.

    System templates cannot be modified.

    Request Body:
        - display_name: Display name
        - description: Description
        - optional_blocks: Optional blocks configuration
        - parameters: Parameters configuration
    """
    db = get_db()
    model = PromptTemplateModel(db)

    template = model.find_by_id(template_id)
    if not template:
        return error_response("Template not found", "TEMPLATE_NOT_FOUND", 404)

    if template.get("is_system"):
        return error_response(
            "System templates cannot be modified. Please duplicate it first.",
            "SYSTEM_TEMPLATE_PROTECTED",
            403
        )

    data = request.get_json()
    if not data:
        return error_response("Request body required", "INVALID_REQUEST", 400)

    # Build update document (only allowed fields)
    updates = {}
    allowed_fields = [
        "display_name",
        "description",
        "optional_blocks",
        "parameters",
        "user_prompt_template",
        "is_active"
    ]

    for field in allowed_fields:
        if field in data:
            updates[field] = data[field]

    if not updates:
        return error_response("No valid fields to update", "NO_UPDATES", 400)

    success = model.update(template_id, updates)
    if not success:
        return error_response("Failed to update template", "UPDATE_FAILED", 500)

    updated = model.find_by_id(template_id)
    logger.info(f"Updated template: {template_id}")

    return success_response(PromptTemplate.to_response(updated))


@prompt_templates_bp.route("/<template_id>/duplicate", methods=["POST"])
def duplicate_template(template_id):
    """
    Duplicate a template.

    This is the only way to "modify" system templates.

    Request Body:
        - name: New template name (required)
        - display_name: New display name
    """
    db = get_db()
    model = PromptTemplateModel(db)

    template = model.find_by_id(template_id)
    if not template:
        # Try by name
        template = model.find_by_name(template_id)

    if not template:
        return error_response("Template not found", "TEMPLATE_NOT_FOUND", 404)

    data = request.get_json() or {}
    new_name = data.get("name")
    if not new_name:
        return error_response("New template name is required", "MISSING_NAME", 400)

    new_display_name = data.get("display_name", f"{template.get('display_name', '')} (Copy)")

    new_id = model.duplicate(str(template["_id"]), new_name, new_display_name)
    if not new_id:
        return error_response(
            f"Failed to duplicate. Name '{new_name}' may already exist.",
            "DUPLICATE_FAILED",
            409
        )

    new_template = model.find_by_id(str(new_id))
    logger.info(f"Duplicated template {template_id} as {new_name}")

    return success_response(
        PromptTemplate.to_response(new_template),
        status=201
    )


@prompt_templates_bp.route("/<template_id>", methods=["DELETE"])
def delete_template(template_id):
    """
    Delete a template.

    System templates cannot be deleted.
    """
    db = get_db()
    model = PromptTemplateModel(db)

    template = model.find_by_id(template_id)
    if not template:
        return error_response("Template not found", "TEMPLATE_NOT_FOUND", 404)

    if template.get("is_system"):
        return error_response(
            "System templates cannot be deleted",
            "SYSTEM_TEMPLATE_PROTECTED",
            403
        )

    success = model.delete(template_id)
    if not success:
        return error_response("Failed to delete template", "DELETE_FAILED", 500)

    logger.info(f"Deleted template: {template_id}")

    return success_response(message="Template deleted successfully")


@prompt_templates_bp.route("/<template_id>/blocks", methods=["GET"])
def get_template_blocks(template_id):
    """
    Get available blocks for a template.

    Useful for the UI to show block selection.
    """
    db = get_db()
    model = PromptTemplateModel(db)

    template = model.find_by_id(template_id)
    if not template:
        template = model.find_by_name(template_id)

    if not template:
        return error_response("Template not found", "TEMPLATE_NOT_FOUND", 404)

    blocks = template.get("optional_blocks", [])

    return success_response({
        "template_name": template.get("name"),
        "blocks": [
            {
                "id": b.get("id"),
                "name": b.get("name"),
                "name_zh": b.get("name_zh"),
                "enabled_by_default": b.get("enabled_by_default", False),
                "order": b.get("order", 0)
            }
            for b in sorted(blocks, key=lambda x: x.get("order", 0))
        ]
    })


@prompt_templates_bp.route("/<template_id>/parameters", methods=["GET"])
def get_template_parameters(template_id):
    """
    Get parameters for a template.

    Useful for the UI to show parameter inputs.
    """
    db = get_db()
    model = PromptTemplateModel(db)

    template = model.find_by_id(template_id)
    if not template:
        template = model.find_by_name(template_id)

    if not template:
        return error_response("Template not found", "TEMPLATE_NOT_FOUND", 404)

    parameters = template.get("parameters", {})

    return success_response({
        "template_name": template.get("name"),
        "parameters": parameters
    })


@prompt_templates_bp.route("/init", methods=["POST"])
def init_templates():
    """
    Initialize default templates.

    This will insert system templates if they don't exist.
    Useful for first-time setup or resetting to defaults.
    """
    db = get_db()

    from ..core.summarization.defaults import get_default_templates

    templates = get_default_templates()
    inserted = 0
    skipped = 0

    for template_data in templates:
        name = template_data["name"]

        # Check if exists
        existing = db.prompt_templates.find_one({"name": name})
        if existing:
            skipped += 1
            continue

        # Add timestamps
        now = datetime.utcnow()
        template_data["created_at"] = now
        template_data["updated_at"] = now
        template_data["version"] = 1

        db.prompt_templates.insert_one(template_data)
        inserted += 1
        logger.info(f"Inserted template: {name}")

    # Ensure indexes
    model = PromptTemplateModel(db)
    model.ensure_indexes()

    return success_response({
        "inserted": inserted,
        "skipped": skipped,
        "total": len(templates)
    })
