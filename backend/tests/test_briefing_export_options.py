"""完整导出通过 HTTP 保留全部内容和密度选项。"""
import pytest

from app.api import briefing_reports as api
from app.services import briefing_report_pdf as pdf
from tests.auth_helpers import add_user, auth_headers, make_auth_app


@pytest.fixture
def client(monkeypatch):
    app = make_auth_app((api.briefing_reports_bp, "/api/briefing-reports"))
    user = add_user(app.db, "full-export@example.com")

    class Reports:
        def __init__(self, **kwargs):
            pass

        def report(self, report_id):
            return {"id": report_id, "mode": "core", "sections": []}

    monkeypatch.setattr(api, "BriefingReportService", Reports)
    return app.test_client(), auth_headers(user)


@pytest.mark.parametrize("kind", ["html", "pdf"])
def test_export_defaults_to_full_content_and_supports_compact(client, monkeypatch, kind):
    http, headers = client
    received = []

    def render(report, **options):
        received.append(options)
        return "<html>全部内容</html>" if kind == "html" else b"%PDF-fixture"

    monkeypatch.setattr(pdf, "render_report_html" if kind == "html" else "create_report_pdf", render)
    response = http.get(f"/api/briefing-reports/reports/example/{kind}?density=compact", headers=headers)
    assert response.status_code == 200
    assert received[0]["pages"] == "all"
    assert received[0]["density"] == "compact"
    if kind == "pdf":
        assert "core-full.pdf" in response.headers["Content-Disposition"]
    assert response.headers["Cache-Control"] == "private, no-store"


@pytest.mark.parametrize("kind", ["html", "pdf"])
def test_invalid_density_rejected_before_rendering(client, monkeypatch, kind):
    http, headers = client
    monkeypatch.setattr(pdf, "render_report_html", lambda *args, **kwargs: pytest.fail("Invalid options must not render"))
    monkeypatch.setattr(pdf, "create_report_pdf", lambda *args, **kwargs: pytest.fail("Invalid options must not render"))
    response = http.get(f"/api/briefing-reports/reports/example/{kind}?density=tiny", headers=headers)
    assert response.status_code == 400


def test_legacy_page_selection_is_preserved(client, monkeypatch):
    http, headers = client
    received = []
    monkeypatch.setattr(pdf, "render_report_html", lambda report, **options: received.append(options) or "<html></html>")
    response = http.get("/api/briefing-reports/reports/example/html?pages=2&style=paper", headers=headers)
    assert response.status_code == 200
    assert received[0]["pages"] == 2
    assert received[0]["style"] == "paper"
