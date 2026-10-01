"""播客内容报告：异步生成、来源可追溯与固定版式导出。"""
from copy import deepcopy
from pathlib import Path

from flask import Blueprint, Response, current_app, request, send_file
from urllib.parse import urlsplit

from .decorators import current_owner_id, require_auth
from .utils import error_response, success_response
from ..services.ai_control import AI_DISABLED_MESSAGE, is_ai_analysis_enabled
from ..services.briefing_report_service import BriefingReportService, INTERESTS, VARIANTS
from ..services.briefing_reading_service import BriefingReadingService, _selected_quote_time
from ..services.briefing_modes_service import BriefingModesService, MODE_INDEX
from ..services.briefing_scope_service import BriefingScopeService, validate_interests
from ..services.briefing_lab_service import corpus_id, quote_offset
from ..services.task_queue import task_queue


briefing_reports_bp = Blueprint("briefing_reports", __name__)


def _scope_service(owner_id):
    report = BriefingReportService(owner_id=owner_id)
    return BriefingScopeService(current_app.db, report, owner_id)


def _reading_service(source_id):
    owner_id = current_owner_id()
    report = BriefingReportService(owner_id=owner_id)
    if source_id.startswith("ep"):
        source = BriefingScopeService(current_app.db, report, owner_id).source(source_id)
        if source is None:
            return None
        report._corpus = {"sources": [source]}
    return BriefingReadingService(owner_id=owner_id, report_service=report)


@briefing_reports_bp.route("/reading-theme.css", methods=["GET"])
def reading_theme():
    return send_file(Path(__file__).resolve().parents[1] / "static" / "briefing-reading-theme.css", mimetype="text/css", max_age=3600)


@briefing_reports_bp.route("/preferences", methods=["GET", "PUT"])
@require_auth
def preferences():
    service = _scope_service(current_owner_id())
    if request.method == "GET":
        return success_response(service.preferences())
    options = request.get_json(silent=True)
    if not isinstance(options, dict):
        return error_response("请求必须是 JSON 对象", "INVALID_JSON", 400)
    try:
        values = {"interests": options.get("interests", service.preferences()["interests"])}
        if "auto_period" in options:
            values["auto_period"] = options["auto_period"]
        result = service.save_preferences(**values)
    except ValueError as error:
        return error_response(str(error), "INVALID_INTERESTS", 400)
    return success_response(result)


@briefing_reports_bp.route("/sources/<source_id>", methods=["GET"])
@require_auth
def source(source_id):
    service = _reading_service(source_id)
    if service is None:
        return error_response("文稿不存在", "SOURCE_NOT_FOUND", 404)
    source = next((item for item in service.report_service.corpus()["sources"] if item["id"] == source_id), None)
    if source is None:
        return error_response("文稿不存在", "SOURCE_NOT_FOUND", 404)
    return success_response({**source, "analysis": service.report_service.lab._source_notes(source, cached_only=True)})


def _has_active_report_task(owner_id):
    return any(task.get("owner_id") == owner_id and task["status"] in ("pending", "processing")
               for task in task_queue.get_all_tasks(task_type="briefing-report"))


@briefing_reports_bp.route("/modes", methods=["GET"])
@require_auth
def modes():
    owner_id = current_owner_id()
    if "period_type" not in request.args and "period_start" not in request.args:
        return success_response(BriefingModesService(owner_id=owner_id).snapshot(topic=request.args.get("topic")))
    scope_service = _scope_service(owner_id)
    try:
        scope = scope_service.collect(request.args.get("period_type", "week"), request.args.get("period_start"))
    except ValueError as error:
        return error_response(str(error), "INVALID_PERIOD", 400)
    service = BriefingModesService(owner_id=owner_id, report_service=scope_service.report_service, scope_service=scope_service)
    return success_response(service.snapshot(topic=request.args.get("topic"), scope=scope))


@briefing_reports_bp.route("/modes/generate", methods=["POST"])
@require_auth
def generate_modes():
    if not is_ai_analysis_enabled():
        return error_response(AI_DISABLED_MESSAGE, "AI_ANALYSIS_DISABLED", 423)
    options = request.get_json(silent=True)
    if not isinstance(options, dict):
        return error_response("请求必须是 JSON 对象", "INVALID_JSON", 400)
    mode = options.get("mode", "all")
    topic = options.get("topic", "")
    if not isinstance(mode, str) or mode not in {*MODE_INDEX, "all"}:
        return error_response("请选择有效的内容模式", "INVALID_MODE", 400)
    if not isinstance(topic, str) or len(topic) > 120:
        return error_response("主题最多120字，可以留空", "INVALID_TOPIC", 400)
    owner_id = current_owner_id()
    scope = None
    if "period_type" in options or "period_start" in options:
        scope_service = _scope_service(owner_id)
        try:
            interests = validate_interests(options["interests"]) if "interests" in options else None
            scope = scope_service.collect(options.get("period_type", "week"), options.get("period_start"), interests)
        except ValueError as error:
            return error_response(str(error), "INVALID_SCOPE", 400)
        service = BriefingModesService(owner_id=owner_id, report_service=scope_service.report_service, scope_service=scope_service)
    else:
        service = BriefingModesService(owner_id=owner_id)
    if not (scope["corpus"] if scope else service.report_service.corpus())["sources"]:
        return error_response("尚未取得完整文稿", "CORPUS_UNAVAILABLE", 409)
    if _has_active_report_task(owner_id):
        return error_response("已有简报正在生成", "REPORT_TASK_ACTIVE", 409)
    kwargs = {"mode": mode, "topic": topic.strip()}
    if scope is not None:
        kwargs["scope"] = scope
    task_id = task_queue.submit(task_type="briefing-report", func=service.generate, owner_id=owner_id, **kwargs)
    return success_response({"task_id": task_id, "status": "queued"}, status_code=202)


@briefing_reports_bp.route("/edition", methods=["GET"])
@require_auth
def edition():
    return success_response(BriefingReadingService(owner_id=current_owner_id()).edition())


@briefing_reports_bp.route("/edition/generate", methods=["POST"])
@require_auth
def generate_edition():
    if not is_ai_analysis_enabled():
        return error_response(AI_DISABLED_MESSAGE, "AI_ANALYSIS_DISABLED", 423)
    options = request.get_json(silent=True)
    if not isinstance(options, dict):
        return error_response("请求必须是 JSON 对象", "INVALID_JSON", 400)
    topic = options.get("topic", "")
    if not isinstance(topic, str) or len(topic) > 120:
        return error_response("主题最多120字，可以留空", "INVALID_TOPIC", 400)
    owner_id = current_owner_id()
    service = BriefingReadingService(owner_id=owner_id)
    if not service.report_service.corpus()["sources"]:
        return error_response("尚未取得完整文稿", "CORPUS_UNAVAILABLE", 409)
    if _has_active_report_task(owner_id):
        return error_response("已有精选或单篇解读正在生成", "REPORT_TASK_ACTIVE", 409)
    task_id = task_queue.submit(task_type="briefing-report", func=service.generate_edition, owner_id=owner_id, topic=topic.strip())
    return success_response({"task_id": task_id, "status": "queued"}, status_code=202)


@briefing_reports_bp.route("/reading/<source_id>", methods=["GET"])
@require_auth
def reading(source_id):
    service = _reading_service(source_id)
    result = service.reading(source_id) if service else None
    if result is None:
        return error_response("文稿不存在", "SOURCE_NOT_FOUND", 404)
    if source_id.startswith("ep") and result["reading"] is None:
        _reuse_existing_reading(service, result, source_id)
    return success_response(result)


def _reuse_existing_reading(service, result, source_id):
    """只在逐字正文相同时复用旧单篇解读，在响应中重新绑定稳定来源编号。"""
    source = service.report_service.corpus()["sources"][0]
    legacy_corpus = service.report_service.lab.corpus()
    legacy_source = next((item for item in legacy_corpus["sources"] if item.get("guid") == source.get("guid") and item["full_text"] == source["full_text"]), None)
    if legacy_source is None:
        return
    cached = service._latest("sources", corpus_id(legacy_corpus), source_id=legacy_source["id"])
    if cached is None:
        return
    old_id = legacy_source["id"]
    reused = deepcopy(cached)
    reused.update(source_id=source_id, corpus_id=corpus_id(service.report_service.corpus()), source=result["source"])
    for point in reused["points"]:
        _rebind_reading_evidence(point["quote"], source, old_id)
        quote = point["quote"]
        point.update(source_id=source_id, episode_id=source["episode_id"], feed=source["feed"], source_title=source["title"], start=quote["start"], end=quote["end"])
    for quote in [*reused.get("resources", []), *reused.get("core_evidence", [])]:
        _rebind_reading_evidence(quote, source, old_id)
    result["reading"] = reused


def _rebind_reading_evidence(quote, source, old_id):
    offset = quote.get("offset")
    if offset is None:
        offset, _ = quote_offset(source["full_text"], quote["quote"])
    if source["full_text"][offset:offset + len(quote["quote"])] != quote["quote"]:
        raise ValueError("旧单篇依据与当前逐字正文不一致，不能复用")
    start, end = _selected_quote_time(source, offset, quote["quote"])
    for key in ("id", "candidate_id"):
        if quote.get(key, "").startswith(old_id + "-"):
            quote[key] = source["id"] + quote[key][len(old_id):]
    quote.update(source_id=source["id"], episode_id=source["episode_id"], feed=source["feed"], source_title=source["title"],
                 offset=offset, start=start, end=end, source_url=source.get("original_url", ""))


@briefing_reports_bp.route("/reading/<source_id>/generate", methods=["POST"])
@require_auth
def generate_reading(source_id):
    if not is_ai_analysis_enabled():
        return error_response(AI_DISABLED_MESSAGE, "AI_ANALYSIS_DISABLED", 423)
    owner_id = current_owner_id()
    service = _reading_service(source_id)
    if service is None or not any(source["id"] == source_id for source in service.report_service.corpus()["sources"]):
        return error_response("文稿不存在", "SOURCE_NOT_FOUND", 404)
    if _has_active_report_task(owner_id):
        return error_response("已有精选或单篇解读正在生成", "REPORT_TASK_ACTIVE", 409)
    task_id = task_queue.submit(task_type="briefing-report", func=service.generate_reading, owner_id=owner_id, source_id=source_id)
    return success_response({"task_id": task_id, "status": "queued"}, status_code=202)


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


def _export_style():
    style = request.args.get("style", "legacy")
    if style not in ("legacy", "paper", "newspaper"):
        return None, error_response("导出风格请选择纸面或报刊", "INVALID_REPORT_STYLE", 400)
    return style, None


def _app_base_url():
    # Vite代理转发到5000，纸面节目链接仍指向用户正在使用的3002前端。
    location = urlsplit(request.referrer or request.host_url)
    return f"{location.scheme}://{location.netloc}"


@briefing_reports_bp.route("/reports/<report_id>/html", methods=["GET"])
@require_auth
def report_html(report_id):
    style, error = _export_style()
    if error is not None:
        return error
    report, pages, error = _export_options(report_id)
    if error is not None:
        return error
    from ..services.briefing_report_pdf import render_report_html
    try:
        html = render_report_html(report, pages=pages, base_url=_app_base_url(), style=style)
    except RuntimeError as error:
        return error_response(str(error), "REPORT_EXPORT_FAILED", 503)
    return Response(html, mimetype="text/html", headers={"Cache-Control": "private, no-store"})


@briefing_reports_bp.route("/reports/<report_id>/pdf", methods=["GET"])
@require_auth
def report_pdf(report_id):
    style, error = _export_style()
    if error is not None:
        return error
    report, pages, error = _export_options(report_id)
    if error is not None:
        return error
    from ..services.briefing_report_pdf import create_report_pdf
    try:
        pdf = create_report_pdf(report, pages=pages, base_url=_app_base_url(), style=style)
    except RuntimeError as error:
        return error_response(str(error), "REPORT_EXPORT_FAILED", 503)
    export_name = report.get("mode", report["variant"])
    style_name = f"-{style}" if style != "legacy" else ""
    return Response(pdf, mimetype="application/pdf", headers={"Content-Disposition": f'attachment; filename="PodMaster-{export_name}{style_name}-{pages}p.pdf"', "Cache-Control": "private, no-store"})
