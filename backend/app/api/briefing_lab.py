"""五种真实正文简报的只读展示与异步生成接口。"""
from flask import Blueprint, request

from .decorators import current_owner_id, require_auth
from .utils import error_response, success_response
from ..services.ai_control import AI_DISABLED_MESSAGE, is_ai_analysis_enabled
from ..services.briefing_lab_service import BriefingLabService, STRATEGY_INSTRUCTIONS
from ..services.task_queue import task_queue


briefing_lab_bp = Blueprint("briefing_lab", __name__)


@briefing_lab_bp.route("", methods=["GET"])
@require_auth
def snapshot():
    return success_response(BriefingLabService(owner_id=current_owner_id()).snapshot())


@briefing_lab_bp.route("/sources/<source_id>", methods=["GET"])
@require_auth
def source(source_id):
    result = BriefingLabService().source(source_id)
    if result is None:
        return error_response("该来源不在当前材料集中", "SOURCE_NOT_FOUND", 404)
    return success_response(result)


@briefing_lab_bp.route("/run", methods=["POST"])
@require_auth
def run():
    if not is_ai_analysis_enabled():
        return error_response(AI_DISABLED_MESSAGE, "AI_ANALYSIS_DISABLED", 423)
    options = request.get_json(silent=True)
    if not isinstance(options, dict):
        return error_response("请求必须是 JSON 对象", "INVALID_JSON", 400)
    strategy = options.get("strategy")
    focus = options.get("focus", "Agent开发与产品落地")
    web_enabled = options.get("web_enabled", False)
    if not isinstance(strategy, str) or strategy not in STRATEGY_INSTRUCTIONS:
        return error_response("请选择一种有效的分析策略", "INVALID_STRATEGY", 400)
    if not isinstance(focus, str) or not focus.strip() or len(focus) > 1000:
        return error_response("研究问题需要填写，最多1000字", "INVALID_FOCUS", 400)
    if not isinstance(web_enabled, bool):
        return error_response("联网选项必须是布尔值", "INVALID_WEB_OPTION", 400)
    if not BriefingLabService().corpus()["sources"]:
        return error_response("还没有可分析的完整正文", "CORPUS_UNAVAILABLE", 409)
    owner_id = current_owner_id()
    for task in task_queue.get_all_tasks(task_type="briefing-lab"):
        if task.get("owner_id") == owner_id and task["status"] in ("pending", "processing"):
            return error_response("已有简报任务正在生成，请等待完成", "LAB_TASK_ACTIVE", 409)
    service = BriefingLabService(owner_id=owner_id)
    task_id = task_queue.submit(task_type="briefing-lab", func=service.generate, owner_id=owner_id, strategy=strategy, focus=focus.strip(), web_enabled=web_enabled)
    return success_response({"task_id": task_id, "status": "queued"}, status_code=202)


@briefing_lab_bp.route("/tasks/<task_id>", methods=["GET"])
@require_auth
def task_status(task_id):
    task = task_queue.get_status(task_id)
    if task is None or task.get("task_type") != "briefing-lab" or task.get("owner_id") != current_owner_id():
        return error_response("任务不存在", "TASK_NOT_FOUND", 404)
    return success_response({"task_id": task_id, "status": task["status"], "progress": task.get("progress", 0), "progress_message": task.get("progress_message"), "error": task.get("error_message"), "result": task.get("result")})
