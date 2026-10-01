"""播客内容报告：异步生成、来源可追溯与固定版式导出。"""
from flask import Blueprint, Response, request
from urllib.parse import urlsplit

from .decorators import current_owner_id, require_auth
from .utils import error_response, success_response
from ..services.ai_control import AI_DISABLED_MESSAGE, is_ai_analysis_enabled
from ..services.briefing_report_service import BriefingReportService, INTERESTS, VARIANTS
from ..services.task_queue import task_queue


briefing_reports_bp = Blueprint("briefing_reports", __name__)


@briefing_reports_bp.route("", methods=["GET"])
@require_auth
def snapshot():
    return success_response(BriefingReportService(owner_id=current_owner_id()).snapshot())


@briefing_reports_bp.route("/generate", methods=["POST"])
@require_auth
def generate():
    if not is_ai_analysis_enabled():
        return error_response(AI_DISABLED_MESSAGE, "AI_ANALYSIS_DISABLED", 423)
    options = request.get_json(silent=True)
    if not isinstance(options, dict):
        return error_response("请求必须是 JSON 对象", "INVALID_JSON", 400)
    variant = options.get("variant", "all")
    topic = options.get("topic", "")
    interests = options.get("interests", list(INTERESTS))
    web_enabled = options.get("web_enabled", False)
    if not isinstance(variant, str) or variant not in {item["id"] for item in VARIANTS} | {"all"}:
        return error_response("报告版本无效", "INVALID_VARIANT", 400)
    if not isinstance(topic, str) or len(topic) > 120:
        return error_response("主题最多120字，可以留空", "INVALID_TOPIC", 400)
    if not isinstance(interests, list) or not interests or any(not isinstance(item, str) or item not in INTERESTS for item in interests):
        return error_response("请选择有效的关注项", "INVALID_INTERESTS", 400)
    if not isinstance(web_enabled, bool):
        return error_response("联网选项必须是布尔值", "INVALID_WEB_OPTION", 400)
    service = BriefingReportService(owner_id=current_owner_id())
    if not service.corpus()["sources"]:
        return error_response("尚未取得完整文稿", "CORPUS_UNAVAILABLE", 409)
    owner_id = current_owner_id()
    if any(task.get("owner_id") == owner_id and task["status"] in ("pending", "processing") for task in task_queue.get_all_tasks(task_type="briefing-report")):
        return error_response("已有报告正在生成", "REPORT_TASK_ACTIVE", 409)
    task_id = task_queue.submit(task_type="briefing-report", func=service.generate, owner_id=owner_id, variant=variant, topic=topic.strip(), interests=list(dict.fromkeys(interests)), web_enabled=web_enabled)
    return success_response({"task_id": task_id, "status": "queued"}, status_code=202)


@briefing_reports_bp.route("/tasks/<task_id>", methods=["GET"])
@require_auth
def task_status(task_id):
    task = task_queue.get_status(task_id)
    if task is None or task.get("task_type") != "briefing-report" or task.get("owner_id") != current_owner_id():
        return error_response("任务不存在", "TASK_NOT_FOUND", 404)
    return success_response({"task_id": task_id, "status": task["status"], "progress": task.get("progress", 0), "progress_message": task.get("progress_message"), "error": task.get("error_message"), "result": task.get("result")})


def _export_options(report_id):
    if request.args.get("pages", "1") not in ("1", "2"):
        return None, None, error_response("请选择一页或两页", "INVALID_PAGE_COUNT", 400)
    report = BriefingReportService(owner_id=current_owner_id()).report(report_id)
    if report is None:
        return None, None, error_response("报告不存在", "REPORT_NOT_FOUND", 404)
    return report, int(request.args.get("pages", "1")), None


def _app_base_url():
    # Vite代理转发到5000，纸面节目链接仍指向用户正在使用的3002前端。
    location = urlsplit(request.referrer or request.host_url)
    return f"{location.scheme}://{location.netloc}"


@briefing_reports_bp.route("/reports/<report_id>/html", methods=["GET"])
@require_auth
def report_html(report_id):
    report, pages, error = _export_options(report_id)
    if error is not None:
        return error
    from ..services.briefing_report_pdf import render_report_html
    try:
        html = render_report_html(report, pages=pages, base_url=_app_base_url())
    except RuntimeError as error:
        return error_response(str(error), "REPORT_EXPORT_FAILED", 503)
    return Response(html, mimetype="text/html", headers={"Cache-Control": "private, no-store"})


@briefing_reports_bp.route("/reports/<report_id>/pdf", methods=["GET"])
@require_auth
def report_pdf(report_id):
    report, pages, error = _export_options(report_id)
    if error is not None:
        return error
    from ..services.briefing_report_pdf import create_report_pdf
    try:
        pdf = create_report_pdf(report, pages=pages, base_url=_app_base_url())
    except RuntimeError as error:
        return error_response(str(error), "REPORT_EXPORT_FAILED", 503)
    return Response(pdf, mimetype="application/pdf", headers={"Content-Disposition": f'attachment; filename="PodMaster-{report["variant"]}-{pages}p.pdf"', "Cache-Control": "private, no-store"})
