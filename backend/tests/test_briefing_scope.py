"""日历周期、真实正文前置筛选与按账号偏好，不能串旧样本或伪造相关性。"""
import json
from datetime import date, datetime
from copy import deepcopy

import pytest

from app.api import briefing_reports as api
from app.services.briefing_lab_service import split_text, write_json
from app.services.briefing_modes_service import BriefingModesService
from app.services.briefing_report_service import BriefingReportService, source_metadata
from app.services.briefing_scope_service import BriefingScopeService, calendar_period, validate_screening, screening_schema
from app.services.briefing_lab_service import ModelValidationError
from tests.auth_helpers import add_user, auth_headers, make_auth_app
from tests.conftest import MockDB


TEXT = "节目讨论大语言模型的推理能力，评估不能脱离具体使用情境。"


def add_episode(db, published, guid, text=None, feed=None, **options):
    if feed is None:
        feed = {"title": "节目", "type": "rss"}
        db.feeds.insert_one(feed)
    episode = {"feed_id": feed["_id"], "guid": guid, "published": published, "title": guid,
               "owner_id": options.pop("owner_id", "legacy"), **options}
    db.episodes.insert_one(episode)
    if text is not None:
        db.transcripts.insert_one({"episode_id": episode["_id"], "text": text, "segments": [{"start": 10, "end": 20, "text": text}], "source": "test"})
    return episode, feed


def scope_service(tmp_path, db=None, owner=None):
    db = db or MockDB()
    owner = owner or str(add_user(db, "scope@example.com")["_id"])
    report = BriefingReportService(tmp_path / "reports", lab_runtime_dir=tmp_path / "lab", owner_id=owner)
    report._metadata = lambda corpus: [source_metadata(item) for item in corpus["sources"]]
    return BriefingScopeService(db, report, owner)


def test_week_month_are_hong_kong_calendar_intervals_not_rolling_days():
    week = calendar_period("week", "2027-01-01", today=date(2027, 1, 1))
    assert (week["start"], week["end"]) == ("2026-12-28", "2027-01-04")
    assert week["is_current"] and not week["is_complete"]
    month = calendar_period("month", "2028-02-16", today=date(2028, 3, 1))
    assert (month["start"], month["end"]) == ("2028-02-01", "2028-03-01")
    assert month["is_complete"]


def test_period_boundaries_use_hong_kong_even_when_database_dates_are_naive_utc(tmp_path):
    service = scope_service(tmp_path)
    db = service.db
    _, feed = add_episode(db, datetime(2026, 9, 27, 15, 59), "before-week", TEXT)
    add_episode(db, datetime(2026, 9, 27, 16), "week-start", TEXT, feed)
    add_episode(db, datetime(2026, 9, 30, 15, 59), "last-september", TEXT, feed)
    add_episode(db, datetime(2026, 9, 30, 16), "october-start", TEXT, feed)
    add_episode(db, datetime(2026, 10, 4, 16), "next-week", TEXT, feed)
    assert service.collect("week", "2026-09-28")["period"]["total_count"] == 3
    october = service.collect("month", "2026-10-01")
    assert october["period"]["total_count"] == 2
    assert all(item["published_at"].startswith("2026-10") for item in october["materials"])
    chip = next(item for item in october["periods"] if item["start"] == "2026-10-01")
    assert chip["total_count"] == chip["transcript_count"] == 2


def test_guid_dedup_uses_actual_transcript_and_excludes_orphaned_feed(tmp_path):
    service = scope_service(tmp_path)
    db = service.db
    _, feed = add_episode(db, datetime(2026, 9, 29), "duplicate", None, has_transcript=True)
    actual, _ = add_episode(db, datetime(2026, 9, 29), "duplicate", TEXT, feed, has_transcript=False)
    add_episode(db, datetime(2026, 9, 30), "missing-text", None, feed, has_transcript=True)
    orphan, orphan_feed = add_episode(db, datetime(2026, 9, 30), "orphan", TEXT)
    db.feeds.delete_one({"_id": orphan_feed["_id"]})
    scope = service.collect("week", "2026-09-28")
    assert scope["period"]["total_count"] == 2
    assert scope["period"]["transcript_count"] == 1
    assert scope["period"]["selected_count"] is None
    assert scope["corpus"]["sources"][0]["episode_id"] == str(actual["_id"])
    assert len(scope["materials"]) == 2 and len(scope["corpus"]["sources"]) == 1


def test_same_guid_text_copy_outside_period_does_not_change_material_publish_date(tmp_path):
    service = scope_service(tmp_path)
    inside, feed = add_episode(service.db, datetime(2026, 9, 29), "same-guid", None)
    outside, _ = add_episode(service.db, datetime(2026, 9, 20), "same-guid", TEXT, feed)
    scope = service.collect("week", "2026-09-28")
    source = scope["corpus"]["sources"][0]
    assert source["episode_id"] == str(inside["_id"])
    assert source["published"].startswith("2026-09-29")
    assert source["acquisition"]["transcript_episode_id"] == str(outside["_id"])
    assert service.source(source["id"])["full_text"] == TEXT
    assert service.source("ep../../lab/corpus") is None


def test_same_rss_guid_from_different_subscriptions_keeps_both_actual_bodies(tmp_path):
    service = scope_service(tmp_path)
    a = {"title": "订阅A", "type": "rss", "rss_url": "https://a.example/rss"}
    b = {"title": "订阅B", "type": "rss", "rss_url": "https://b.example/rss"}
    service.db.feeds.insert_one(a)
    service.db.feeds.insert_one(b)
    first, _ = add_episode(service.db, datetime(2026, 9, 29), "episode-1", TEXT, a)
    other_text = "另一份节目讨论细胞研究，内容属于另一频道而不是大语言模型。"
    second, _ = add_episode(service.db, datetime(2026, 9, 29), "episode-1", other_text, b)
    scope = service.collect("week", "2026-09-28")
    assert scope["period"]["total_count"] == scope["period"]["transcript_count"] == 2
    assert {item["full_text"] for item in scope["corpus"]["sources"]} == {TEXT, other_text}
    assert service.source(f"ep{first['_id']}")["full_text"] == TEXT
    assert service.source(f"ep{second['_id']}")["full_text"] == other_text


def test_missing_rss_body_cannot_borrow_same_guid_from_another_subscription(tmp_path):
    service = scope_service(tmp_path)
    a = {"title": "订阅A", "type": "rss", "rss_url": "https://a.example/rss"}
    b = {"title": "订阅B", "type": "rss", "rss_url": "https://b.example/rss"}
    service.db.feeds.insert_one(a)
    service.db.feeds.insert_one(b)
    missing, _ = add_episode(service.db, datetime(2026, 9, 29), "episode-1", None, a)
    add_episode(service.db, datetime(2026, 9, 29), "episode-1", TEXT, b)
    scope = service.collect("week", "2026-09-28")
    assert scope["period"]["total_count"] == 2 and scope["period"]["transcript_count"] == 1
    material = next(item for item in scope["materials"] if item["episode_id"] == str(missing["_id"]))
    assert material["has_transcript"] is False and material["source_id"] is None
    assert service.source(f"ep{missing['_id']}") is None


def test_duplicate_normalized_rss_subscriptions_can_share_same_episode_transcript(tmp_path):
    service = scope_service(tmp_path)
    a = {"title": "节目旧订阅", "type": "rss", "rss_url": "https://EXAMPLE.com/rss/?utm_source=old"}
    b = {"title": "节目新订阅", "type": "rss", "rss_url": "https://example.com/rss"}
    service.db.feeds.insert_one(a)
    service.db.feeds.insert_one(b)
    missing, _ = add_episode(service.db, datetime(2026, 9, 29), "episode-1", None, a)
    saved, _ = add_episode(service.db, datetime(2026, 9, 29), "episode-1", TEXT, b)
    scope = service.collect("week", "2026-09-28")
    assert scope["period"]["total_count"] == scope["period"]["transcript_count"] == 1
    source = service.source(f"ep{missing['_id']}")
    assert source["full_text"] == TEXT
    assert source["episode_id"] == str(missing["_id"])
    assert source["acquisition"]["transcript_episode_id"] == str(saved["_id"])


@pytest.mark.parametrize("guid", ["youtube:Abc123_-XYZ", "bilibili:BV1234567890"])
def test_standard_video_ids_are_global_content_identity(guid, tmp_path):
    service = scope_service(tmp_path)
    missing, _ = add_episode(service.db, datetime(2026, 9, 29), guid, None)
    add_episode(service.db, datetime(2026, 9, 29), guid, TEXT)
    scope = service.collect("week", "2026-09-28")
    assert scope["period"]["total_count"] == scope["period"]["transcript_count"] == 1
    assert service.source(f"ep{missing['_id']}")["full_text"] == TEXT


def test_selection_key_changes_with_period_interests_body_and_available_material(tmp_path):
    service = scope_service(tmp_path)
    episode, feed = add_episode(service.db, datetime(2026, 9, 29), "actual", TEXT)
    original = service.collect("week", "2026-09-28", ["AI", "LLM"])
    assert original["selection_key"] == service.collect("week", "2026-09-28", ["LLM", "ai"])["selection_key"]
    assert original["selection_key"] != service.collect("month", "2026-09-01", ["AI", "LLM"])["selection_key"]
    assert original["selection_key"] != service.collect("week", "2026-09-28", ["科学"])["selection_key"]
    service.db.transcripts.update_one({"episode_id": episode["_id"]}, {"$set": {"text": TEXT + "新增加一段正文。"}})
    assert original["selection_key"] != service.collect("week", "2026-09-28", ["AI", "LLM"])["selection_key"]
    add_episode(service.db, datetime(2026, 9, 30), "new-without-body", None, feed)
    assert original["selection_key"] != service.collect("week", "2026-09-28", ["AI", "LLM"])["selection_key"]


def test_screening_requires_actual_quote_and_requested_topic():
    chunk = split_text(TEXT)[0]
    good = {"matches": [{"topic": "LLM", "reason": "讨论模型推理与实际评估。", "quote": TEXT}]}
    assert validate_screening(good, chunk, ["LLM"])["matches"][0]["offset"] == 0
    bad = deepcopy(good)
    bad["matches"][0]["quote"] = "节目说明大模型一定能取代全部人类工作。"
    with pytest.raises(ValueError, match="不在对应正文"):
        validate_screening(bad, chunk, ["LLM"])
    with pytest.raises(ValueError, match="实际关注"):
        validate_screening(good, chunk, ["科学"])


@pytest.mark.parametrize("value,message", [
    ({"topics": []}, "必须包含matches"),
    ({"matches": "AI"}, "必须是数组"),
    ({"matches": [{}, {}, {}]}, "返回3条"),
])
def test_screening_contract_reports_the_specific_structure_failure(value, message):
    with pytest.raises(ValueError, match=message):
        validate_screening(value, split_text(TEXT)[0], ["AI", "LLM"])


def test_failed_screening_records_both_responses_without_caching_a_result(tmp_path, monkeypatch):
    service = scope_service(tmp_path)
    add_episode(service.db, datetime(2026, 9, 29), "schema-failure", TEXT)
    source = service.collect("week", "2026-09-28", ["LLM"])["corpus"]["sources"][0]
    attempts = [{"content": '{"topics":[]}', "error": "缺少matches"}, {"content": '{"matches":"LLM"}', "error": "matches不是数组"}]

    def fail(system, prompt, validator, **kwargs):
        assert kwargs["response_schema"] == screening_schema(["LLM"])
        raise ModelValidationError("模型结果未通过依据校验：matches不是数组", attempts)

    monkeypatch.setattr(service.report_service.lab, "_model_call", fail)
    with pytest.raises(ValueError, match="正文筛选失败.*C001"):
        service._screen_source(source, ["LLM"])
    path = service._screen_path(source, ["LLM"])
    failure = json.loads((path / "C001.failure.json").read_text(encoding="utf-8"))
    assert failure["attempts"] == attempts
    assert failure["source_id"] == source["id"]
    assert not (path / "result.json").exists()


def test_screening_reads_tail_and_reuses_body_cache_with_correct_episode_binding(tmp_path, monkeypatch):
    service = scope_service(tmp_path)
    long_text = "这个片段讲的是历史过程。" * 1100 + TEXT
    episode, feed = add_episode(service.db, datetime(2026, 9, 29), "long", long_text)
    scope = service.collect("week", "2026-09-28", ["LLM"])
    calls = []

    def model(system, prompt, validator, **kwargs):
        calls.append(prompt)
        matches = [{"topic": "LLM", "reason": "尾部讨论大语言模型的推理评估。", "quote": TEXT}] if TEXT in prompt else []
        return validator({"matches": matches}), {"usage": {"total": 1}}

    monkeypatch.setattr(service.report_service.lab, "_model_call", model)
    screened = service.screen(scope)
    assert len(calls) == len(split_text(long_text)) > 1
    assert screened["period"]["selected_count"] == 1
    old_source = screened["corpus"]["sources"][0]
    alternative = {**old_source, "id": "ep" + "a" * 24, "episode_id": "a" * 24, "segments": [{"start": 500, "end": 550, "text": long_text}]}
    rebound = service.cached_screening(alternative, ["llm"])
    assert rebound["topic_tags"] == ["llm"]
    assert rebound["evidence"][0]["source_id"] == alternative["id"]
    assert rebound["evidence"][0]["episode_id"] == alternative["episode_id"]
    assert rebound["evidence"][0]["start"] == 500
    service.screen(scope)
    assert len(calls) == len(split_text(long_text))


def test_no_match_creates_scoped_empty_reports_without_falling_back_to_sample(tmp_path, monkeypatch):
    service = scope_service(tmp_path)
    add_episode(service.db, datetime(2026, 9, 29), "history", TEXT)
    scope = service.collect("week", "2026-09-28", ["历史"])
    monkeypatch.setattr(service.report_service.lab, "_model_call", lambda system, prompt, validator, **kwargs: (validator({"matches": []}), {"usage": {"total": 1}}))
    modes = BriefingModesService(owner_id=service.owner_id, report_service=service.report_service, scope_service=service)
    generated = modes.generate(scope=scope)
    assert all(not report["sections"][0]["items"] for report in generated["reports"].values())
    current = service.collect("week", "2026-09-28", ["历史"])
    snapshot = modes.snapshot(scope=current)
    assert all(report is not None for report in snapshot["reports"].values())
    assert snapshot["period"]["selected_count"] == 0
    assert all(report is None for report in modes.snapshot()["reports"].values())
    other = service.collect("week", "2026-09-28", ["科学"])
    assert all(report is None for report in modes.snapshot(scope=other)["reports"].values())


@pytest.fixture
def client(tmp_path, monkeypatch):
    app = make_auth_app((api.briefing_reports_bp, "/api/briefing-reports"))
    user = add_user(app.db, "period-api@example.com")
    owner = str(user["_id"])
    service = scope_service(tmp_path, app.db, owner)
    monkeypatch.setattr(api, "_scope_service", lambda current_owner: scope_service(tmp_path, app.db, current_owner))
    return app, app.test_client(), auth_headers(user), service


def test_preview_is_read_only_and_preferences_are_per_account(client, monkeypatch):
    app, http, headers, service = client
    add_episode(app.db, datetime(2026, 9, 29), "actual", TEXT)
    monkeypatch.setattr(service.report_service.lab, "_model_call", lambda *args, **kwargs: pytest.fail("GET must never call LLM"))
    before = app.db.users.find_one({"_id": app.db.users._data[0]["_id"]})
    response = http.get("/api/briefing-reports/modes?period_type=week&period_start=2026-09-28", headers=headers)
    assert response.status_code == 200
    data = response.get_json()["data"]
    assert data["period"]["total_count"] == data["period"]["transcript_count"] == 1
    assert data["screening"]["status"] == "not_started"
    assert before == app.db.users.find_one({"_id": before["_id"]})
    tags = [{"label": "科学", "enabled": True}, {"label": "AI", "enabled": False}]
    assert http.put("/api/briefing-reports/preferences", headers=headers, json={"interests": tags}).get_json()["data"]["interests"] == tags
    other = add_user(app.db, "other-period-api@example.com")
    assert http.get("/api/briefing-reports/preferences", headers=auth_headers(other)).get_json()["data"]["interests"][0]["label"] == "AI"
    assert http.get("/api/briefing-reports/modes?period_type=week&period_start=2026-09-28", headers=headers).get_json()["data"]["interests"] == ["科学"]


@pytest.mark.parametrize("body", [None, {"interests": ["AI"]}, {"interests": [{"label": "AI", "enabled": True}, {"label": "ai", "enabled": True}]}])
def test_invalid_preferences_do_not_write_account(client, body):
    app, http, headers, service = client
    response = http.put("/api/briefing-reports/preferences", headers=headers, json=body)
    assert response.status_code == 400
    assert "briefing_interests" not in app.db.users._data[0]


def test_generation_queues_frozen_scope_and_active_interests_not_inline_model(client, monkeypatch):
    app, http, headers, service = client
    add_episode(app.db, datetime(2026, 9, 29), "actual", TEXT)
    monkeypatch.setattr(api, "is_ai_analysis_enabled", lambda: True)
    captured = {}
    monkeypatch.setattr(api.task_queue, "get_all_tasks", lambda **kwargs: [])
    monkeypatch.setattr(api.task_queue, "submit", lambda **kwargs: captured.update(kwargs) or "test-scope-task")
    response = http.post("/api/briefing-reports/modes/generate", headers=headers,
                         json={"mode": "core", "period_type": "week", "period_start": "2026-09-28", "interests": ["LLM"]})
    assert response.status_code == 202
    assert captured["owner_id"] == service.owner_id
    assert captured["scope"]["interests"] == ["LLM"]
    assert captured["scope"]["period"]["total_count"] == 1
    assert captured["scope"]["corpus"]["sources"][0]["full_text"] == TEXT
    assert captured["report_period"] == captured["scope"]["period"]


@pytest.mark.parametrize("active_period,active_owner,status,expected", [
    ({"type": "month", "start": "2026-10-01"}, "same", "processing", 202),
    ({"type": "week", "start": "2026-09-28"}, "same", "pending", 202),
    ({"type": "month", "start": "2026-09-01"}, "same", "processing", 409),
    ({"type": "month", "start": "2026-09-01"}, "same", "pending", 409),
    ({"type": "month", "start": "2026-09-01"}, "same", "failed", 202),
    ({"type": "month", "start": "2026-09-01"}, "other", "processing", 202),
    (None, "same", "processing", 409),
])
def test_other_period_generation_does_not_block_september(client, monkeypatch, active_period, active_owner, status, expected):
    app, http, headers, service = client
    add_episode(app.db, datetime(2026, 9, 29), "september", TEXT)
    monkeypatch.setattr(api, "is_ai_analysis_enabled", lambda: True)
    active_task = {"owner_id": service.owner_id if active_owner == "same" else "other-owner", "status": status}
    if active_period is not None:
        active_task["report_period"] = active_period
    monkeypatch.setattr(api.task_queue, "get_all_tasks", lambda **kwargs: [active_task])
    submitted = []
    monkeypatch.setattr(api.task_queue, "submit", lambda **kwargs: submitted.append(kwargs) or "september-task")
    response = http.post("/api/briefing-reports/modes/generate", headers=headers,
                         json={"mode": "core", "period_type": "month", "period_start": "2026-09-01"})
    assert response.status_code == expected
    assert len(submitted) == (1 if expected == 202 else 0)
    if submitted:
        assert submitted[0]["scope"]["period"]["start"] == "2026-09-01"


def test_october_generation_preserves_september_reports_and_fingerprint(tmp_path, monkeypatch):
    service = scope_service(tmp_path)
    add_episode(service.db, datetime(2026, 9, 29), "september", TEXT)
    monkeypatch.setattr(service.report_service.lab, "_model_call", lambda system, prompt, validator, **kwargs: (validator({"matches": []}), {"usage": {"total": 1}}))
    modes = BriefingModesService(owner_id=service.owner_id, report_service=service.report_service, scope_service=service)
    september = service.collect("month", "2026-09-01", ["历史"])
    september_reports = modes.generate(scope=september)["reports"]
    files = {report["id"]: (modes.root / "reports" / f"{report['id']}.json").read_bytes() for report in september_reports.values()}
    add_episode(service.db, datetime(2026, 10, 1), "october", "这是十月的节目正文，讨论完全不同的内容。")
    october = service.collect("month", "2026-10-01", ["历史"])
    october_reports = modes.generate(scope=october)["reports"]
    unchanged = service.collect("month", "2026-09-01", ["历史"])
    assert unchanged["selection_key"] == september["selection_key"] != october["selection_key"]
    assert {report["id"] for report in september_reports.values()}.isdisjoint(report["id"] for report in october_reports.values())
    for mode, report in modes.snapshot(scope=unchanged)["reports"].items():
        assert report["id"] == september_reports[mode]["id"]
        assert (modes.root / "reports" / f"{report['id']}.json").read_bytes() == files[report["id"]]


def test_scoped_validation_and_no_text_do_not_create_task(client, monkeypatch):
    app, http, headers, service = client
    monkeypatch.setattr(api, "is_ai_analysis_enabled", lambda: True)
    monkeypatch.setattr(api.task_queue, "submit", lambda **kwargs: pytest.fail("Invalid requests must not queue work"))
    assert http.get("/api/briefing-reports/modes?period_type=year", headers=headers).status_code == 400
    assert http.post("/api/briefing-reports/modes/generate", headers=headers, json={"period_type": "week", "period_start": "invalid"}).status_code == 400
    assert http.post("/api/briefing-reports/modes/generate", headers=headers, json={"period_type": "week", "period_start": ["2026-09-28"]}).status_code == 400
    assert http.post("/api/briefing-reports/modes/generate", headers=headers, json={"period_type": "week", "period_start": "2026-09-28"}).status_code == 409


def test_stable_source_endpoint_returns_actual_body_and_cannot_escape_paths(client, monkeypatch):
    app, http, headers, service = client
    episode, _ = add_episode(app.db, datetime(2026, 9, 29), "AI title is not body", TEXT)
    monkeypatch.setattr(api, "BriefingReportService", lambda **kwargs: service.report_service)
    sid = f"ep{episode['_id']}"
    response = http.get(f"/api/briefing-reports/sources/{sid}", headers=headers)
    assert response.status_code == 200
    assert response.get_json()["data"]["full_text"] == TEXT
    assert response.get_json()["data"]["episode_id"] == str(episode["_id"])
    assert http.get("/api/briefing-reports/sources/epinvalid", headers=headers).status_code == 404
    reading = http.get(f"/api/briefing-reports/reading/{sid}", headers=headers)
    assert reading.status_code == 200
    assert reading.get_json()["data"]["source"]["id"] == sid


def test_dynamic_single_reading_generation_queues_real_episode_source(client, monkeypatch):
    app, http, headers, service = client
    episode, _ = add_episode(app.db, datetime(2026, 9, 29), "single", TEXT)
    monkeypatch.setattr(api, "BriefingReportService", lambda **kwargs: service.report_service)
    monkeypatch.setattr(api, "is_ai_analysis_enabled", lambda: True)
    monkeypatch.setattr(api.task_queue, "get_all_tasks", lambda **kwargs: [])
    captured = {}
    monkeypatch.setattr(api.task_queue, "submit", lambda **kwargs: captured.update(kwargs) or "reading-task")
    sid = f"ep{episode['_id']}"
    response = http.post(f"/api/briefing-reports/reading/{sid}/generate", headers=headers, json={})
    assert response.status_code == 202
    assert captured["source_id"] == sid
    assert captured["func"].__self__.report_service.corpus()["sources"][0]["full_text"] == TEXT


def test_legacy_single_reading_rebinds_every_quote_and_alias_when_same_text_has_new_segment_times(tmp_path):
    from app.services.briefing_lab_service import corpus_id
    from app.services.briefing_reading_service import BriefingReadingService
    service = scope_service(tmp_path)
    episode, _ = add_episode(service.db, datetime(2026, 9, 29), "same", TEXT)
    source = service.source(f"ep{episode['_id']}")
    source["segments"] = [{"text": TEXT, "start": 500, "end": 520}]
    old = {**source, "id": "S01", "episode_id": "old-episode", "segments": [{"text": TEXT, "start": 10, "end": 20}]}
    legacy = {"sources": [old]}
    write_json(service.report_service.lab.root / "corpus.json", legacy)
    service.report_service._corpus = {"sources": [source]}
    reading = BriefingReadingService(owner_id=service.owner_id, report_service=service.report_service)
    old_quote = {"id": "S01-C001-quote-01", "candidate_id": "S01-C001-quote-01", "source_id": "S01", "episode_id": "old-episode", "quote": TEXT, "offset": 0, "start": 10, "end": 20}
    cached = {"id": "a" * 32, "owner_id": service.owner_id, "corpus_id": corpus_id(legacy), "source_id": "S01", "generated_at": "2026-10-01T00:00:00+00:00",
              "points": [{"quote": deepcopy(old_quote), "source_id": "S01", "start": 10}], "resources": [deepcopy(old_quote)], "core_evidence": [deepcopy(old_quote)]}
    path = reading.root / "sources" / (cached["id"] + ".json")
    write_json(path, cached)
    result = {"reading": None, "source": source_metadata(source)}
    api._reuse_existing_reading(reading, result, source["id"])
    updated = result["reading"]
    all_quotes = [updated["points"][0]["quote"], *updated["resources"], *updated["core_evidence"]]
    assert all(quote["start"] == 500 and quote["end"] == 520 for quote in all_quotes)
    assert all(quote["source_id"] == source["id"] and quote["episode_id"] == source["episode_id"] for quote in all_quotes)
    assert all(quote["candidate_id"].startswith(source["id"] + "-") for quote in all_quotes)
    assert updated["points"][0]["start"] == 500 and updated["points"][0]["source_id"] == source["id"]
    assert updated["points"][0]["episode_id"] == source["episode_id"]
    from app.services.briefing_lab_service import read_json
    assert read_json(path) == cached


@pytest.mark.parametrize("format,renderer", [("html", "render_report_html"), ("pdf", "create_report_pdf")])
def test_pdf_style_is_validated_and_forwarded_without_changing_report(client, monkeypatch, format, renderer):
    from app.services import briefing_report_pdf
    app, http, headers, service = client
    report = {"id": "a" * 32, "variant": "overview", "mode": "core"}
    monkeypatch.setattr(service.report_service, "report", lambda report_id: report)
    monkeypatch.setattr(api, "BriefingReportService", lambda **kwargs: service.report_service)
    captured = {}
    monkeypatch.setattr(briefing_report_pdf, renderer, lambda value, **kwargs: captured.update(kwargs) or ("<html>paper</html>" if format == "html" else b"%PDF-test"))
    assert http.get(f"/api/briefing-reports/reports/{report['id']}/{format}?style=unknown", headers=headers).status_code == 400
    assert not captured
    response = http.get(f"/api/briefing-reports/reports/{report['id']}/{format}?pages=2&style=newspaper", headers=headers)
    assert response.status_code == 200
    assert captured["style"] == "newspaper" and captured["pages"] == 2
    assert report == {"id": "a" * 32, "variant": "overview", "mode": "core"}


def test_reading_theme_is_public_fixed_css(client):
    app, http, headers, service = client
    response = http.get("/api/briefing-reports/reading-theme.css")
    assert response.status_code == 200
    assert response.mimetype == "text/css"
    assert ".br-layout-paper" in response.get_data(as_text=True)
    assert "body.report-style-newspaper" in response.get_data(as_text=True)


def test_auto_period_preference_can_change_independently_and_is_preserved_on_tag_edit(client):
    app, http, headers, service = client
    initial = http.get("/api/briefing-reports/preferences", headers=headers).get_json()["data"]
    assert initial["auto_period"] is None
    enabled = http.put("/api/briefing-reports/preferences", headers=headers, json={"auto_period": "week"})
    assert enabled.status_code == 200 and enabled.get_json()["data"]["auto_period"] == "week"
    assert enabled.get_json()["data"]["interests"] == initial["interests"]
    tags = [{"label": "历史", "enabled": True}]
    changed = http.put("/api/briefing-reports/preferences", headers=headers, json={"interests": tags}).get_json()["data"]
    assert changed["interests"] == tags and changed["auto_period"] == "week"
    assert changed["auto_enabled_at"] == enabled.get_json()["data"]["auto_enabled_at"]
    assert changed["auto_enabled_at"] is not None
    assert http.put("/api/briefing-reports/preferences", headers=headers, json={"auto_period": "daily"}).status_code == 400
    assert service.preferences()["auto_period"] == "week"
    assert http.put("/api/briefing-reports/preferences", headers=headers, json={"auto_period": None}).get_json()["data"]["auto_period"] is None
