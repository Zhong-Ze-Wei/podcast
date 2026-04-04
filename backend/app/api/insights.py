# -*- coding: utf-8 -*-
"""
AI 紞报 API 路由
"""

from flask import Blueprint, request, jsonify, current_app, Response
from ..services.briefing_service import BriefingService

insights_bp = Blueprint("insights", __name__)


def get_briefing_service():
    """获取简报服务实例"""
    from .. import get_db
    db = get_db()
    return BriefingService(db)


@insights_bp.route("/briefing", methods=["GET"])
def get_briefing():
    """获取今日 AI 简报（有缓存则返回缓存）"""
    try:
        service = get_briefing_service()
        result = service.get_or_generate(force=False)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Failed to get briefing: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@insights_bp.route("/briefing", methods=["POST"])
def regenerate_briefing():
    """强制重新生成今日 AI 简报"""
    try:
        service = get_briefing_service()
        result = service.get_or_generate(force=True)
        return jsonify(result)
    except Exception as e:
        current_app.logger.error(f"Failed to regenerate briefing: {e}")
        return jsonify({"success": False, "error": str(e)}), 500


@insights_bp.route("/briefing/export", methods=["GET"])
def export_briefing_pdf():
    """导出今日简报为 PDF"""
    try:
        service = get_briefing_service()
        cached = service.get_cached()

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
        return Response(
            pdf_bytes,
            mimetype="application/pdf",
            headers={
                "Content-Disposition": f'attachment; filename="podcast-briefing-{date_str}.pdf"'
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
