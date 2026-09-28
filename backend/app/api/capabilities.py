from flask import Blueprint, current_app
from ..services.capabilities import get_capabilities
from .utils import success_response

capabilities_bp = Blueprint("capabilities", __name__)


@capabilities_bp.get("/capabilities")
def read_capabilities():
    return success_response(get_capabilities(current_app.config))
