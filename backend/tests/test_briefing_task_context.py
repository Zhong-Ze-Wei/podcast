"""任务恢复使用后端声明的类型与来源，周期关联必须核对真实材料。"""
from datetime import datetime, timezone

import pytest

from app.api import briefing_reports as api
from app.services.briefing_reading_service import BriefingReadingService
from tests.test_briefing_scope import client, add_episode, TEXT
from tests.test_briefing_auto_reporter import setup


@pytest.fixture
def queued(client, monkeypatch):
    app, http, headers, service = client
    episode, _ = add_episode(app.db, datetime(2026, 9, 29), "context-source", TEXT)
    calls = []
    monkeypatch.setattr(api, "is_ai_analysis_enabled", lambda: True)
    monkeypatch.setattr(api, "BriefingReportService", lambda **kwargs: service.report_service)
    monkeypatch.setattr(api.task_queue, "get_all_tasks", lambda **kwargs: [])
    monkeypatch.setattr(api.task_queue, "submit", lambda **kwargs: calls.append(kwargs) or "context-task")
    monkeypatch.setattr(service.report_service.lab, "_model_call", lambda *args, **kwargs: pytest.fail("POST must only queue work"))
    return app, http, headers, service, "ep" + str(episode["_id"]), calls


def test_mode_generation_records_server_declared_context(queued):
    app, http, headers, service, sid, calls = queued
    response = http.post("/api/briefing-reports/modes/generate", headers=headers, json={
        "mode": "quotes", "period_type": "month", "period_start": "2026-09-01",
        "report_context": {"kind": "reading", "source_id": "invented"},
    })
    assert response.status_code == 202
    assert calls[0]["report_context"] == {"kind": "modes", "mode": "quotes"}
    assert calls[0]["report_period"]["start"] == "2026-09-01"


@pytest.mark.parametrize("body", [None, {}])
def test_reading_without_period_keeps_legacy_api_and_declares_source(queued, body):
    app, http, headers, service, sid, calls = queued
    response = http.post("/api/briefing-reports/reading/" + sid + "/generate", headers=headers, json=body)
    assert response.status_code == 202
    assert calls[0]["report_context"] == {"kind": "reading", "source_id": sid,
                                          "source_title": "context-source", "feed_title": "节目"}
    assert "report_period" not in calls[0]
    assert calls[0]["source_id"] == sid


def test_reading_records_only_a_period_containing_its_actual_source(queued):
    app, http, headers, service, sid, calls = queued
    response = http.post("/api/briefing-reports/reading/" + sid + "/generate", headers=headers,
                         json={"period_type": "week", "period_start": "2026-09-29"})
    assert response.status_code == 202
    assert calls[0]["report_context"] == {"kind": "reading", "source_id": sid,
                                          "source_title": "context-source", "feed_title": "节目"}
    assert calls[0]["report_period"]["type"] == "week"
    assert calls[0]["report_period"]["start"] == "2026-09-28"


@pytest.mark.parametrize("body", [
    {"period_type": "year"}, {"period_type": "month", "period_start": "2026-99-99"},
    {"period_type": "month", "period_start": "2026-10-01"}, [],
])
def test_invalid_or_unrelated_reading_period_cannot_queue_work(queued, body):
    app, http, headers, service, sid, calls = queued
    response = http.post("/api/briefing-reports/reading/" + sid + "/generate", headers=headers, json=body)
    assert response.status_code == 400
    assert calls == []


@pytest.mark.parametrize("path,kind", [("/edition/generate", "edition"), ("/generate", "legacy")])
def test_nonperiod_generation_declares_context_without_inventing_a_period(queued, monkeypatch, path, kind):
    app, http, headers, service, sid, calls = queued
    source = service.source(sid)
    service.report_service._corpus = {"sources": [source]}
    monkeypatch.setattr(api, "BriefingReadingService", lambda **kwargs: BriefingReadingService(owner_id=service.owner_id, report_service=service.report_service))
    response = http.post("/api/briefing-reports" + path, headers=headers, json={})
    assert response.status_code == 202
    assert calls[0]["report_context"] == {"kind": kind}
    assert "report_period" not in calls[0]


def test_automatic_mode_generation_records_the_same_context(setup):
    db, user, reporter, queue, generated, modes = setup
    task_id, = reporter.check_due(datetime(2026, 10, 4, 16, 5, tzinfo=timezone.utc))
    assert queue.tasks[task_id]["report_context"] == {"kind": "modes", "mode": "all"}
    assert queue.tasks[task_id]["report_period"]["start"] == "2026-09-28"


def test_reading_period_accepts_actual_source_even_when_corpus_dedup_chooses_new_alias(queued):
    app, http, headers, service, sid, calls = queued
    add_episode(app.db, datetime(2026, 9, 30), "context-source", TEXT,
                feed=app.db.feeds._data[0], owner_id=service.owner_id)
    response = http.post("/api/briefing-reports/reading/" + sid + "/generate", headers=headers,
                         json={"period_type": "week", "period_start": "2026-09-28"})
    assert response.status_code == 202
    assert calls[0]["report_context"]["source_id"] == sid
    assert calls[0]["report_period"]["start"] == "2026-09-28"


def test_reading_without_publication_cannot_claim_a_period(queued):
    app, http, headers, service, sid, calls = queued
    app.db.episodes._data[0]["published"] = None
    response = http.post("/api/briefing-reports/reading/" + sid + "/generate", headers=headers,
                         json={"period_type": "week", "period_start": "2026-09-28"})
    assert response.status_code == 400
    assert response.get_json()["error_code"] == "SOURCE_OUTSIDE_PERIOD"
    assert calls == []
