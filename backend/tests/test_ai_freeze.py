from bson import ObjectId
from flask import Flask

from app.api import insights, summaries


def make_app(enabled=False):
    app = Flask(__name__)
    app.config["AI_ANALYSIS_ENABLED"] = enabled
    return app


def test_create_summary_is_blocked_when_ai_analysis_is_disabled(monkeypatch):
    app = make_app(enabled=False)
    monkeypatch.setattr(summaries, "get_db", lambda: (_ for _ in ()).throw(AssertionError("db should not be used")))

    with app.test_request_context(f"/api/summaries/{ObjectId()}", method="POST", json={}):
        response, status_code = summaries.create_summary(str(ObjectId()))

    assert status_code == 423
    assert response.get_json()["error_code"] == "AI_ANALYSIS_DISABLED"


def test_translate_summary_is_blocked_when_ai_analysis_is_disabled(monkeypatch):
    app = make_app(enabled=False)
    monkeypatch.setattr(summaries, "get_db", lambda: (_ for _ in ()).throw(AssertionError("db should not be used")))

    with app.test_request_context(f"/api/summaries/{ObjectId()}/translate", method="POST", json={}):
        response, status_code = summaries.translate_summary(str(ObjectId()))

    assert status_code == 423
    assert response.get_json()["error_code"] == "AI_ANALYSIS_DISABLED"


def test_get_briefing_returns_cached_briefing_when_ai_analysis_is_disabled(monkeypatch):
    app = make_app(enabled=False)
    cached = {"date": "2026-05-17", "briefing": {"summary": {"totalEpisodes": 1}}}

    class FakeService:
        def get_cached(self, strategy="summary", days=7):
            return cached

        def get_or_generate(self, force=False, strategy="summary", days=7):
            raise AssertionError("generation should not be used")

    monkeypatch.setattr(insights, "get_briefing_service", lambda: FakeService())

    with app.test_request_context("/api/insights/briefing", method="GET"):
        response = insights.get_briefing()

    data = response.get_json()
    assert data["success"] is True
    assert data["briefing"] == cached
    assert data["cached"] is True


def test_get_briefing_does_not_generate_when_ai_analysis_is_disabled(monkeypatch):
    app = make_app(enabled=False)

    class FakeService:
        def get_cached(self, strategy="summary", days=7):
            return None

        def get_or_generate(self, force=False, strategy="summary", days=7):
            raise AssertionError("generation should not be used")

    monkeypatch.setattr(insights, "get_briefing_service", lambda: FakeService())

    with app.test_request_context("/api/insights/briefing", method="GET"):
        response = insights.get_briefing()

    data = response.get_json()
    assert data["success"] is True
    assert data["briefing"] is None
    assert data["ai_analysis_enabled"] is False


def test_regenerate_briefing_is_blocked_when_ai_analysis_is_disabled(monkeypatch):
    app = make_app(enabled=False)
    monkeypatch.setattr(insights, "get_briefing_service", lambda: (_ for _ in ()).throw(AssertionError("service should not be used")))

    with app.test_request_context("/api/insights/briefing", method="POST"):
        response = insights.regenerate_briefing()

    assert response[1] == 423
    assert response[0].get_json()["error_code"] == "AI_ANALYSIS_DISABLED"
