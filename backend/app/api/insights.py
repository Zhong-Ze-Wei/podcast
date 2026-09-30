# -*- coding: utf-8 -*-
"""
AI 简报 API 路由：三种策略（摘要聚合 / 文稿直析 / 元数据雷达），按策略独立缓存
"""

from flask import Blueprint, request, jsonify, current_app, Response
from ..services.briefing_service import (
    BriefingService,
    STRATEGIES,
    MIN_WINDOW_DAYS,
    MAX_WINDOW_DAYS,
    DEFAULT_WINDOW_DAYS,
)
from ..services.ai_control import AI_DISABLED_MESSAGE, is_ai_analysis_enabled
from .decorators import require_auth
from .utils import success_response

insights_bp = Blueprint("insights", __name__)


def get_briefing_service():
    """获取简报服务实例"""
    from .. import get_db
    db = get_db()
    return BriefingService(db)


def _requested_strategy():
    strategy = (request.args.get("strategy") or "summary").strip().lower()
    if strategy not in STRATEGIES:
        return None, jsonify({
            "success": False,
            "error_code": "INVALID_STRATEGY",
            "message": f"未知简报策略：{strategy}（可选：{'、'.join(STRATEGIES)}）",
        }), 400
    return strategy, None, None


def _requested_days():
    raw = request.args.get("days")
    if raw is None or raw == "":
        return DEFAULT_WINDOW_DAYS, None, None
    try:
        days = int(raw)
    except ValueError:
        return None, jsonify({
            "success": False,
            "error_code": "INVALID_DAYS",
            "message": f"days 必须是整数（{MIN_WINDOW_DAYS}-{MAX_WINDOW_DAYS}）",
        }), 400
    if not (MIN_WINDOW_DAYS <= days <= MAX_WINDOW_DAYS):
        return None, jsonify({
            "success": False,
            "error_code": "INVALID_DAYS",
            "message": f"days 超出范围：允许 {MIN_WINDOW_DAYS}-{MAX_WINDOW_DAYS} 天",
        }), 400
    return days, None, None


@insights_bp.route("/briefing/count", methods=["GET"])
@require_auth
def briefing_window_count():
    """窗口内剧集统计（滑块预览用）：总数 / 有文稿 / 有摘要"""
    days, error_resp, code = _requested_days()
    if error_resp:
        return error_resp, code
    try:
        service = get_briefing_service()
        return jsonify({"success": True, "data": service.window_counts(days)})
    except Exception as e:
        current_app.logger.error(f"Failed to count briefing window: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@insights_bp.route("/briefing", methods=["GET"])
@require_auth
def get_briefing():
    """获取今日 AI 简报（有缓存则返回缓存；strategy + days 决定取材路线与窗口）"""
    strategy, error_resp, code = _requested_strategy()
    if error_resp:
        return error_resp, code
    days, error_resp, code = _requested_days()
    if error_resp:
        return error_resp, code
    try:
        service = get_briefing_service()
        if not is_ai_analysis_enabled():
            cached = service.get_cached(strategy, days)
            if cached:
                return jsonify({
                    "success": True,
                    "briefing": cached,
                    "cached": True,
                    "ai_analysis_enabled": False,
                })
            return jsonify({
                "success": True,
                "briefing": None,
                "message": AI_DISABLED_MESSAGE,
                "ai_analysis_enabled": False,
            })
        result = service.get_or_generate(force=False, strategy=strategy, days=days)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Failed to get briefing: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@insights_bp.route("/briefing", methods=["POST"])
@require_auth
def regenerate_briefing():
    """强制重新生成今日 AI 简报（可指定 strategy 与 days）"""
    strategy, error_resp, code = _requested_strategy()
    if error_resp:
        return error_resp, code
    days, error_resp, code = _requested_days()
    if error_resp:
        return error_resp, code
    try:
        if not is_ai_analysis_enabled():
            return jsonify({
                "success": False,
                "error_code": "AI_ANALYSIS_DISABLED",
                "message": AI_DISABLED_MESSAGE,
            }), 423
        service = get_briefing_service()
        result = service.get_or_generate(force=True, strategy=strategy, days=days)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Failed to regenerate briefing: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@insights_bp.route("/briefing/export", methods=["GET"])
@require_auth
def export_briefing_pdf():
    """导出今日简报为 PDF（可指定 strategy 与 days）"""
    strategy, error_resp, code = _requested_strategy()
    if error_resp:
        return error_resp, code
    days, error_resp, code = _requested_days()
    if error_resp:
        return error_resp, code
    try:
        service = get_briefing_service()
        cached = service.get_cached(strategy, days)

        if not cached:
            return jsonify({"error": "暂无简报数据，请先生成简报"}), 404

        briefing = cached.get("briefing", {})
        markdown_text = briefing.get("markdownReport", "")

        if not markdown_text:
            return jsonify({"error": "简报中无 Markdown 内容"}), 404

        import markdown
        from weasyprint import HTML

        html_body = markdown.markdown(
            markdown_text,
            extensions=["tables", "fenced_code", "nl2br"],
        )

        full_html = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<style>
  body {{
    font-family: "Microsoft YaHei", "PingFang SC", "Helvetica Neue", Arial, sans-serif;
    max-width: 800px; margin: 40px auto; padding: 0 20px;
    color: #1a1a1a; line-height: 1.8; font-size: 14px;
  }}
  h1 {{ font-size: 24px; border-bottom: 2px solid #6366f1; padding-bottom: 8px; }}
  h2 {{ font-size: 18px; color: #4f46e5; margin-top: 28px; }}
  h3 {{ font-size: 15px; color: #334155; }}
  blockquote {{
    border-left: 3px solid #6366f1; margin: 12px 0; padding: 8px 16px;
    background: #f8f7ff; color: #4a4a6a; font-style: italic;
  }}
  table {{ border-collapse: collapse; width: 100%; margin: 12px 0; }}
  th, td {{ border: 1px solid #e2e8f0; padding: 8px 12px; text-align: left; }}
  th {{ background: #f1f5f9; font-weight: 600; }}
  hr {{ border: none; border-top: 1px solid #e2e8f0; margin: 24px 0; }}
  code {{ background: #f1f5f9; padding: 2px 6px; border-radius: 4px; font-size: 13px; }}
</style>
</head>
<body>{html_body}</body>
</html>"""

        pdf_bytes = HTML(string=full_html).write_pdf()

        date_str = cached.get("date", "today")
        strategy_tag = f"-{strategy}" if strategy != "summary" else ""
        days_tag = f"-{days}d" if days != 7 else ""
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="podcast-briefing-{date_str}{strategy_tag}{days_tag}.pdf"'
            },
        )

    except ImportError as e:
        current_app.logger.error(f"PDF export dependency missing: {e}")
        return jsonify({
            "error": "PDF 导出依赖未安装，请执行: pip install markdown weasyprint"
        }), 500
    except Exception as e:
        current_app.logger.error(f"Failed to export briefing PDF: {e}")
        return jsonify({"error": str(e)}), 500
