"""播客内容报告：异步生成、来源可追溯与固定版式导出。"""
from copy import deepcopy
from pathlib import Path

from flask import Blueprint, Response, current_app, request, send_file
from urllib.parse import urlsplit
from pymongo.errors import PyMongoError

from .decorators import current_owner_id, require_auth, require_role
from .utils import error_response, success_response, get_pagination_params, paginated_response
from ..services.ai_control import AI_DISABLED_MESSAGE, is_ai_analysis_enabled
from ..services.briefing_report_service import BriefingReportService, INTERESTS, VARIANTS
from ..services.briefing_reading_service import BriefingReadingService, _selected_quote_time
from ..services.briefing_modes_service import BriefingModesService, MODE_INDEX
from ..services.briefing_scope_service import BriefingScopeService, validate_interests
from ..services.briefing_lab_service import corpus_id, quote_offset
from ..services.task_queue import task_queue
from ..services.briefing_task_service import submit_report_task
from ..services.briefing_favorites import BriefingFavorites, valid_item_id


briefing_reports_bp = Blueprint("briefing_reports", __name__)


def _scope_service(owner_id):
    report = BriefingReportService(owner_id=owner_id)
    return BriefingScopeService(current_app.db, report, owner_id)


def _report_store(owner_id):
    return BriefingReportService(owner_id=owner_id).store


def _report_filters():
    filters = {key: request.args.get(key) for key in ("period_type", "period_start", "mode")}
    if filters["period_type"] is not None and filters["period_type"] not in ("week", "month"):
        return None, error_response("周期请选择周或月", "INVALID_PERIOD", 400)
    if filters["mode"] is not None and filters["mode"] not in MODE_INDEX:
        return None, error_response("内容模式无效", "INVALID_MODE", 400)
    if filters["period_start"] is not None:
        from datetime import date
        try:
            parsed = date.fromisoformat(filters["period_start"])
            if parsed.isoformat() != filters["period_start"]:
                raise ValueError("日期格式无效")
        except ValueError:
            return None, error_response("周期日期须为 YYYY-MM-DD", "INVALID_PERIOD", 400)
    return filters, None


@briefing_reports_bp.route("/reports", methods=["GET"])
@require_auth
def report_history():
    filters, error = _report_filters()
    if error is not None:
        return error
    page, per_page = get_pagination_params()
    try:
        reports, total = _report_store(current_owner_id()).history(page, per_page, **filters)
    except PyMongoError:
        return error_response("报告历史暂时无法读取", "REPORT_STORAGE_UNAVAILABLE", 503)
    return paginated_response(reports, page, per_page, total)


@briefing_reports_bp.route("/reports/<report_id>", methods=["GET"])
@require_auth
def saved_report(report_id):
    report = _report_store(current_owner_id()).report(report_id)
    if report is None:
        return error_response("报告不存在", "REPORT_NOT_FOUND", 404)
    return success_response(report)


def _favorites_service():
    owner_id = current_owner_id()
    return BriefingFavorites(current_app.db, _report_store(owner_id), owner_id)


@briefing_reports_bp.route("/favorites", methods=["GET"])
@require_auth
def favorites():
    filters, error = _report_filters()
    if error is not None:
        return error
    page, per_page = get_pagination_params()
    try:
        rows, total = _favorites_service().list(page, per_page, **filters)
    except PyMongoError:
        return error_response("简报收藏暂时无法读取", "FAVORITES_STORAGE_UNAVAILABLE", 503)
    return paginated_response(rows, page, per_page, total)


@briefing_reports_bp.route("/favorites/<item_id>", methods=["PUT", "DELETE"])
@require_role("user", "admin")
def favorite(item_id):
    if not valid_item_id(item_id):
        return error_response("条目编号无效", "INVALID_ITEM_ID", 400)
    options = request.get_json(silent=True) if request.method == "PUT" else None
    if request.method == "PUT" and (not isinstance(options, dict) or not isinstance(options.get("report_id"), str)):
        return error_response("请提供报告编号", "INVALID_REPORT_ID", 400)
    try:
        service = _favorites_service()
        result = service.delete(item_id) if request.method == "DELETE" else service.save(item_id, options["report_id"])
    except PyMongoError:
        return error_response("简报收藏暂时无法保存", "FAVORITES_STORAGE_UNAVAILABLE", 503)
    if result is None:
        return error_response("报告条目不存在", "ITEM_NOT_FOUND", 404)
    return success_response(result)


@briefing_reports_bp.route("/favorites/import", methods=["POST"])
@require_role("user", "admin")
def import_favorites():
    options = request.get_json(silent=True)
    if not isinstance(options, dict):
        return error_response("请求必须是 JSON 对象", "INVALID_JSON", 400)
    try:
        result = _favorites_service().import_ids(options.get("ids"))
    except ValueError as error:
        return error_response(str(error), "INVALID_FAVORITES", 400)
    except PyMongoError:
        return error_response("旧收藏暂时无法迁移", "FAVORITES_STORAGE_UNAVAILABLE", 503)
    return success_response(result)


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
        if "layout" in options:
            values["layout"] = options["layout"]
        if "materials_layout" in options:
            values["materials_layout"] = options["materials_layout"]
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
@require_role("user", "admin")
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
    kwargs = {"mode": mode, "topic": topic.strip(), "report_context": {"kind": "modes", "mode": mode}}
    if scope is not None:
        kwargs["scope"] = scope
        kwargs["report_period"] = scope["period"]
    task_id = submit_report_task(task_queue, func=service.generate, owner_id=owner_id, **kwargs)
    if task_id is None:
        return error_response("该周期已有简报正在生成" if scope is not None else "已有简报正在生成", "REPORT_TASK_ACTIVE", 409)
    return success_response({"task_id": task_id, "status": "queued"}, status_code=202)


@briefing_reports_bp.route("/edition", methods=["GET"])
@require_auth
def edition():
    return success_response(BriefingReadingService(owner_id=current_owner_id()).edition())


@briefing_reports_bp.route("/edition/generate", methods=["POST"])
@require_role("user", "admin")
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
    task_id = submit_report_task(task_queue, func=service.generate_edition, owner_id=owner_id, topic=topic.strip(), report_context={"kind": "edition"})
    if task_id is None:
        return error_response("已有精选或单篇解读正在生成", "REPORT_TASK_ACTIVE", 409)
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
    # 旧片段式解读仍可查看，但不能冒认为新全文分析缓存。
    reused["legacy"] = True
    result["legacy_reading"] = reused


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
@require_role("user", "admin")
def generate_reading(source_id):
    if not is_ai_analysis_enabled():
        return error_response(AI_DISABLED_MESSAGE, "AI_ANALYSIS_DISABLED", 423)
    options = {}
    if request.content_length:
        options = request.get_json(silent=True)
        if not isinstance(options, dict):
            return error_response("请求必须是 JSON 对象", "INVALID_JSON", 400)
    owner_id = current_owner_id()
    service = _reading_service(source_id)
    source = next((item for item in service.report_service.corpus()["sources"] if item["id"] == source_id), None) if service is not None else None
    if source is None:
        return error_response("文稿不存在", "SOURCE_NOT_FOUND", 404)
    kwargs = {"source_id": source_id, "episode_id": source.get("episode_id"), "feed_id": source.get("feed_id"),
              "report_context": {"kind": "reading", "source_id": source_id,
                                 "source_title": source["title"], "feed_title": source.get("feed", "")}}
    if "period_type" in options or "period_start" in options:
        scope_service = _scope_service(owner_id)
        try:
            scope = scope_service.collect(options.get("period_type", "week"), options.get("period_start"))
        except ValueError as error:
            return error_response(str(error), "INVALID_PERIOD", 400)
        if not scope_service.source_within_period(source, scope["period"]):
            return error_response("文稿不属于所选周期", "SOURCE_OUTSIDE_PERIOD", 400)
        kwargs["report_period"] = scope["period"]
    task_id = submit_report_task(task_queue, func=service.generate_reading, owner_id=owner_id, **kwargs)
    if task_id is None:
        return error_response("已有精选或单篇解读正在生成", "REPORT_TASK_ACTIVE", 409)
    return success_response({"task_id": task_id, "status": "queued"}, status_code=202)


@briefing_reports_bp.route("", methods=["GET"])
@require_auth
def snapshot():
    return success_response(BriefingReportService(owner_id=current_owner_id()).snapshot())


@briefing_reports_bp.route("/generate", methods=["POST"])
@require_role("user", "admin")
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
    task_id = submit_report_task(task_queue, func=service.generate, owner_id=owner_id, report_context={"kind": "legacy"}, variant=variant, topic=topic.strip(), interests=list(dict.fromkeys(interests)), web_enabled=web_enabled)
    if task_id is None:
        return error_response("已有报告正在生成", "REPORT_TASK_ACTIVE", 409)
    return success_response({"task_id": task_id, "status": "queued"}, status_code=202)


@briefing_reports_bp.route("/tasks/<task_id>", methods=["GET"])
@require_auth
def task_status(task_id):
    task = task_queue.get_status(task_id)
    if task is None or task.get("task_type") != "briefing-report" or task.get("owner_id") != current_owner_id():
        return error_response("任务不存在", "TASK_NOT_FOUND", 404)
    return success_response({"task_id": task_id, "status": task["status"], "progress": task.get("progress", 0), "progress_message": task.get("progress_message"), "error": task.get("error_message"), "result": task.get("result"), "period": task.get("report_period")})


def _export_options(report_id):
    pages = request.args.get("pages", "all")
    if pages not in ("all", "1", "2"):
        return None, None, error_response("请选择完整导出、一页或两页", "INVALID_PAGE_COUNT", 400)
    report = BriefingReportService(owner_id=current_owner_id()).report(report_id)
    if report is None:
        return None, None, error_response("报告不存在", "REPORT_NOT_FOUND", 404)
    return report, pages if pages == "all" else int(pages), None


def _export_density():
    density = request.args.get("density", "comfortable")
    if density not in ("comfortable", "compact"):
        return None, error_response("导出密度请选择舒适或紧凑", "INVALID_REPORT_DENSITY", 400)
    return density, None


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
    density, error = _export_density()
    if error is not None:
        return error
    report, pages, error = _export_options(report_id)
    if error is not None:
        return error
    from ..services.briefing_report_pdf import render_report_html
    try:
        html = render_report_html(report, pages=pages, base_url=_app_base_url(), style=style, density=density)
    except RuntimeError as error:
        return error_response(str(error), "REPORT_EXPORT_FAILED", 503)
    return Response(html, mimetype="text/html", headers={"Cache-Control": "private, no-store"})


@briefing_reports_bp.route("/reports/<report_id>/pdf", methods=["GET"])
@require_auth
def report_pdf(report_id):
    style, error = _export_style()
    if error is not None:
        return error
    density, error = _export_density()
    if error is not None:
        return error
    report, pages, error = _export_options(report_id)
    if error is not None:
        return error
    from ..services.briefing_report_pdf import create_report_pdf
    try:
        pdf = create_report_pdf(report, pages=pages, base_url=_app_base_url(), style=style, density=density)
    except RuntimeError as error:
        return error_response(str(error), "REPORT_EXPORT_FAILED", 503)
    export_name = report.get("mode") or report.get("variant", "report")
    style_name = f"-{style}" if style != "legacy" else ""
    page_name = "full" if pages == "all" else f"{pages}p"
    return Response(pdf, mimetype="application/pdf", headers={"Content-Disposition": f'attachment; filename="PodMaster-{export_name}{style_name}-{page_name}.pdf"', "Cache-Control": "private, no-store"})


@briefing_reports_bp.route("/reading/<source_id>/translate-evidence", methods=["POST"])
@require_auth
def translate_reading_evidence(source_id):
    """原文依据按需中译：evidence 是逐字原话（多为英文），这里批量翻译并按引文哈希缓存，不动版本化报告。"""
    import hashlib
    from datetime import datetime

    from .. import get_db as _get_db
    from ..services.llm_client import get_llm_client

    if not is_ai_analysis_enabled():
        return error_response(AI_DISABLED_MESSAGE, "AI_ANALYSIS_DISABLED", 423)
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        return error_response("请求必须是 JSON 对象", "INVALID_JSON", 400)
    raw = payload.get("quotes")
    if not isinstance(raw, list) or not raw:
        return error_response("quotes 不能为空", "INVALID_QUOTES", 400)

    def quote_hash(text):
        return hashlib.md5(text.encode("utf-8", "ignore")).hexdigest()

    valid = [
        {"id": str(item.get("id", "")), "quote": str(item.get("quote", "")).strip()}
        for item in raw
        if isinstance(item, dict) and str(item.get("quote", "")).strip()
    ][:20]
    if not valid:
        return error_response("没有可翻译的引文", "INVALID_QUOTES", 400)

    db = _get_db()
    owner_id = current_owner_id()
    hashes = [quote_hash(item["quote"]) for item in valid]
    translations = {
        doc["quote_hash"]: doc["zh"]
        for doc in db.evidence_translations.find(
            {"owner_id": owner_id, "quote_hash": {"$in": hashes}}, {"quote_hash": 1, "zh": 1}
        )
    }

    missing = [item for item in valid if quote_hash(item["quote"]) not in translations]
    if missing:
        llm = get_llm_client(task="briefing")
        result = llm.chat_json(
            messages=[
                {"role": "system", "content": "你是字幕翻译。把每条播客原话忠实翻译成简洁中文，保留人名与技术名词，不加解释。只返回JSON。"},
                {"role": "user", "content": "逐条翻译下面引文，返回 {\"items\":[{\"i\":<序号>,\"zh\":\"译文\"}]}：\n"
                 + "\n".join(f"{i}. {item['quote'][:600]}" for i, item in enumerate(missing))},
            ],
            temperature=0.2,
            max_tokens=4000,
        )
        items = (result.get("data") or {}).get("items") or []
        now = datetime.utcnow()
        new_docs = []
        for i, item in enumerate(missing):
            zh = next((str(entry.get("zh", "")).strip() for entry in items if entry.get("i") == i), "")
            if not zh:
                continue
            translations[quote_hash(item["quote"])] = zh
            new_docs.append({"owner_id": owner_id, "quote_hash": quote_hash(item["quote"]), "zh": zh, "created_at": now})
        if new_docs:
            try:
                db.evidence_translations.insert_many(new_docs)
            except Exception:
                pass  # 缓存写失败不影响本次返回

    return success_response({
        "translations": {item["id"]: translations[quote_hash(item["quote"])] for item in valid
                         if quote_hash(item["quote"]) in translations}
    })
