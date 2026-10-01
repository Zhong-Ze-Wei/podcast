"""Business guarantees for full-text analysis, evidence, and safe lab controls."""
import json

import pytest

from app.api import briefing_lab as lab_api
from app.models.setting import SettingModel
from app.services.briefing_lab_service import (
    BriefingLabService,
    corpus_id,
    locate_time,
    split_text,
    validate_chunk,
    validate_result,
)
from tests.auth_helpers import add_user, auth_headers, make_auth_app


def source_document(text="The source explicitly explains the limits of autonomous agents."):
    return {
        "id": "S01",
        "episode_id": "episode-1",
        "guid": "youtube:source-1",
        "title": "Agent limits",
        "feed": "Research podcast",
        "published": "2026-09-29T09:00:00+00:00",
        "duration": 10800,
        "material_type": "full_transcript",
        "full_text": text,
        "char_count": len(text),
        "segments": [{"start": 0, "end": 10, "text": text}],
    }


def save_corpus(directory, sources):
    data = {"generated_at": "2026-10-01T01:00:00+00:00", "sources": sources, "diagnostics": {}}
    (directory / "corpus.json").write_text(json.dumps(data), encoding="utf-8")
    return data


def no_model_calls(**kwargs):
    raise AssertionError("A read-only operation must not instantiate an LLM client")


def test_long_podcast_analysis_preserves_every_character_and_final_conclusion():
    text = "Opening context. " + "技术条件与限制。原始 English text. " * 9000 + "FINAL CONCLUSION: deployment remains conditional."
    chunks = split_text(text)

    assert len(chunks) > 10
    assert "".join(chunk["text"] for chunk in chunks) == text
    assert chunks[0]["start"] == 0
    assert chunks[-1]["end"] == len(text)
    assert chunks[-1]["text"].endswith("deployment remains conditional.")
    assert all(left["end"] == right["start"] for left, right in zip(chunks, chunks[1:]))


def test_rephrased_model_claim_cannot_be_presented_as_a_verbatim_quote():
    chunk = {"id": "C001", "start": 12000, "text": "The system requires human approval before deployment."}
    fake_quote = {"summary": "Needs approval", "claims": [{"title": "Approval", "body": "A human reviews deployment.", "quote": "The system deploys safely without any human approval."}]}

    with pytest.raises(ValueError, match="引文不在"):
        validate_chunk(fake_quote, chunk)


def test_quote_whitespace_normalization_retains_exact_source_and_absolute_offset():
    chunk = {"id": "C003", "start": 24000, "text": "Introduction. Agents need\n human approval before deployment."}
    data = {"summary": "Approval is required", "claims": [{"title": "Approval", "body": "Deployment is conditional.", "quote": "Agents need human approval before deployment."}]}
    validated = validate_chunk(data, chunk)

    claim = validated["claims"][0]
    assert claim["quote"] == "Agents need\n human approval before deployment."
    assert claim["offset"] == 24000 + chunk["text"].index("Agents")


def test_quote_spanning_multiple_caption_segments_ends_at_last_segment():
    segments = [
        {"start": 0, "end": 3, "text": "Plan the task."},
        {"start": 10, "end": 13, "text": "Review the changes."},
        {"start": 20, "end": 24, "text": "Deploy only after approval."},
    ]
    text = " ".join(segment["text"] for segment in segments)
    source = {"full_text": text, "segments": segments}
    quote = "changes. Deploy only after approval."

    assert locate_time(source, text.index(quote), quote) == (10, 24)


def test_transcript_header_offset_is_remapped_to_caption_text_for_audio_time():
    segments = [
        {"start": 0, "end": 4, "text": "Opening discussion."},
        {"start": 40, "end": 44, "text": "Review requires a human."},
        {"start": 60, "end": 66, "text": "Deployment waits for approval."},
    ]
    text = "Transcript provided by the publisher. Speaker labels and editorial information.\n\n" + " ".join(segment["text"] for segment in segments)
    source = {"full_text": text, "segments": segments}
    quote = "Review requires a human. Deployment waits for approval."

    assert text.index(quote) > len(" ".join(segment["text"] for segment in segments))
    assert locate_time(source, text.index(quote), quote) == (40, 66)


def test_editorial_text_without_matching_audio_has_no_invented_timestamp():
    segments = [{"start": 12, "end": 16, "text": "The guest describes the deployment limits."}]
    quote = "Editorial note: this transcript was corrected after publication."
    text = quote + "\n\n" + segments[0]["text"]
    source = {"full_text": text, "segments": segments}

    assert locate_time(source, text.index(quote), quote) == (None, None)


def briefing_result(evidence_ids=None, external_ids=None):
    return {
        "title": "Deployment needs a review gate",
        "subtitle": "Research synthesis",
        "overview": "The supplied source describes a limited claim.",
        "sections": [{"title": "Supported findings", "items": [{
            "title": "Approval gate", "body": "Human approval is a deployment condition.",
            "type": "observation", "source_ids": ["S01"],
            "evidence_ids": ["S01-C001-E01"] if evidence_ids is None else evidence_ids,
            "external_ids": [] if external_ids is None else external_ids,
        }]}],
        "recommendations": [{"source_id": "S01", "reason": "Read the limitations."}],
        "open_questions": ["When can human review be removed?"],
    }


def test_every_published_finding_is_attached_to_real_source_evidence():
    evidence = {"id": "S01-C001-E01", "source_id": "S01", "quote": "The source explicitly explains the limits", "offset": 0, "start": 0, "end": 10}
    data = validate_result(briefing_result(), [source_document()], {evidence["id"]: evidence}, [])
    item = data["sections"][0]["items"][0]

    assert item["source_ids"] == ["S01"]
    assert item["evidence"] == [evidence]
    assert item["external_links"] == []


@pytest.mark.parametrize("evidence_ids,external_ids,error", [
    (["S99-C001-E01"], [], "未提供的原文证据"),
    ([], ["W99"], "未取得的网络来源"),
    ([], [], "至少一个已有证据"),
])
def test_hallucinated_or_missing_evidence_cannot_be_saved(evidence_ids, external_ids, error):
    with pytest.raises(ValueError, match=error):
        validate_result(briefing_result(evidence_ids, external_ids), [source_document()], {}, [])


def test_reading_snapshot_and_source_never_starts_analysis(tmp_path):
    source = source_document("Long source paragraph. " * 1000)
    save_corpus(tmp_path, [source])
    service = BriefingLabService(tmp_path, client_factory=no_model_calls)

    snapshot = service.snapshot()
    detail = service.source("S01")

    assert snapshot["corpus"]["total_chars"] == len(source["full_text"])
    assert snapshot["corpus"]["sources"][0]["analyzed_chunks"] == 0
    assert "full_text" not in snapshot["corpus"]["sources"][0]
    assert detail["full_text"] == source["full_text"]
    assert detail["analysis"]["chunks"] == []
    assert service.source("S99") is None


def test_old_runs_disappear_when_source_text_changes(tmp_path):
    old_corpus = save_corpus(tmp_path, [source_document()])
    run_dir = tmp_path / "runs"
    run_dir.mkdir()
    (run_dir / "old.json").write_text(json.dumps({"id": "old-run", "corpus_id": corpus_id(old_corpus), "generated_at": "2026-09-30T12:00:00+00:00"}), encoding="utf-8")
    save_corpus(tmp_path, [source_document("A revised transcript changes the actual source evidence.")])

    snapshot = BriefingLabService(tmp_path, client_factory=no_model_calls).snapshot()

    assert snapshot["runs"] == []


def test_personal_question_runs_are_private_while_shared_demo_and_full_text_remain_shared(tmp_path):
    corpus = save_corpus(tmp_path, [source_document()])
    run_dir = tmp_path / "runs"
    run_dir.mkdir()
    for run_id, owner_id in (("shared-demo", None), ("owner-a-question", "owner-a"), ("owner-b-question", "owner-b")):
        (run_dir / f"{run_id}.json").write_text(json.dumps({
            "id": run_id, "owner_id": owner_id, "corpus_id": corpus_id(corpus),
            "focus": run_id, "generated_at": "2026-10-01T01:00:00+00:00",
        }), encoding="utf-8")
    service_a = BriefingLabService(tmp_path, client_factory=no_model_calls, owner_id="owner-a")
    service_b = BriefingLabService(tmp_path, client_factory=no_model_calls, owner_id="owner-b")
    shared_service = BriefingLabService(tmp_path, client_factory=no_model_calls)

    assert {run["id"] for run in service_a.snapshot()["runs"]} == {"shared-demo", "owner-a-question"}
    assert {run["id"] for run in service_b.snapshot()["runs"]} == {"shared-demo", "owner-b-question"}
    assert {run["id"] for run in shared_service.snapshot()["runs"]} == {"shared-demo"}
    assert service_a.source("S01") == service_b.source("S01")


def test_new_personal_question_run_persists_owner_and_cannot_be_read_by_another_owner(tmp_path, monkeypatch):
    save_corpus(tmp_path, [source_document()])
    service = BriefingLabService(tmp_path, client_factory=no_model_calls, owner_id="owner-a")
    evidence = {"id": "S01-C001-E01", "source_id": "S01", "quote": "The source explicitly explains the limits", "offset": 0, "start": 0, "end": 10}
    notes = [{"overview": "The source describes limits.", "claims": [{"title": "Limits", "body": "Scope is limited.", "evidence": evidence}], "questions": [], "chunks": [{}]}]
    monkeypatch.setattr(service, "analyze_sources", lambda progress_callback=None: notes)

    def model_call(system, prompt, validator, **kwargs):
        return validator(briefing_result()), {"model": "unit-test-model", "usage": {"prompt": 0, "completion": 0, "total": 0}, "elapsed_seconds": 0}

    monkeypatch.setattr(service, "_model_call", model_call)
    run = service.generate("focus", focus="A personal deployment question")
    persisted = json.loads((tmp_path / "runs" / f"{run['id']}.json").read_text(encoding="utf-8"))

    assert run["owner_id"] == "owner-a"
    assert persisted["owner_id"] == "owner-a"
    assert [item["id"] for item in service.snapshot()["runs"]] == [run["id"]]
    assert BriefingLabService(tmp_path, client_factory=no_model_calls, owner_id="owner-b").snapshot()["runs"] == []


def test_material_changed_during_analysis_cannot_produce_a_mixed_batch(tmp_path, monkeypatch):
    save_corpus(tmp_path, [source_document()])
    service = BriefingLabService(tmp_path, client_factory=no_model_calls)

    def analyze_changed_material(progress_callback=None):
        save_corpus(tmp_path, [source_document("Newly captured source replaces the old material.")])
        return []

    monkeypatch.setattr(service, "analyze_sources", analyze_changed_material)

    with pytest.raises(ValueError, match="同一批材料"):
        service.generate("daily")
    assert not (tmp_path / "runs").exists()


@pytest.fixture
def lab_client():
    app = make_auth_app((lab_api.briefing_lab_bp, "/api/briefing-lab"))
    user = add_user(app.db, "lab-user@example.com")
    return app.test_client(), auth_headers(user), str(user["_id"])


def test_ai_freeze_blocks_new_lab_generation_before_any_model_or_task(lab_client, monkeypatch):
    client, headers, _ = lab_client
    monkeypatch.setattr(lab_api, "is_ai_analysis_enabled", lambda: False)
    monkeypatch.setattr(lab_api, "BriefingLabService", no_model_calls)

    response = client.post("/api/briefing-lab/run", headers=headers, json={"strategy": "daily"})

    assert response.status_code == 423
    assert response.get_json()["error_code"] == "AI_ANALYSIS_DISABLED"


@pytest.mark.parametrize("options,error", [
    ({"strategy": "invented"}, "INVALID_STRATEGY"),
    ({"strategy": "daily", "focus": "   "}, "INVALID_FOCUS"),
    ({"strategy": "daily", "focus": "x" * 1001}, "INVALID_FOCUS"),
    ({"strategy": "daily", "web_enabled": "false"}, "INVALID_WEB_OPTION"),
])
def test_invalid_controls_are_rejected_before_queueing(lab_client, monkeypatch, options, error):
    client, headers, _ = lab_client
    monkeypatch.setattr(lab_api, "is_ai_analysis_enabled", lambda: True)
    monkeypatch.setattr(lab_api, "BriefingLabService", no_model_calls)

    response = client.post("/api/briefing-lab/run", headers=headers, json=options)

    assert response.status_code == 400
    assert response.get_json()["error_code"] == error


class AvailableService:
    def __init__(self, owner_id=None):
        self.owner_id = owner_id

    def snapshot(self):
        return {"owner_id": self.owner_id, "runs": []}

    def corpus(self):
        return {"sources": [source_document()]}

    def generate(self, **kwargs):
        raise AssertionError("The HTTP request must queue generation, not run it inline")


class CapturingQueue:
    def __init__(self, tasks=None):
        self.tasks = tasks or []
        self.submitted = []

    def get_all_tasks(self, task_type=None):
        return self.tasks

    def get_status(self, task_id):
        return next((task for task in self.tasks if task["task_id"] == task_id), None)

    def submit(self, **kwargs):
        self.submitted.append(kwargs)
        return "queued-lab-task"


def test_lab_generation_is_queued_with_normalized_question_and_explicit_web_choice(lab_client, monkeypatch):
    client, headers, owner_id = lab_client
    queue = CapturingQueue()
    monkeypatch.setattr(lab_api, "is_ai_analysis_enabled", lambda: True)
    monkeypatch.setattr(lab_api, "BriefingLabService", AvailableService)
    monkeypatch.setattr(lab_api, "task_queue", queue)

    response = client.post("/api/briefing-lab/run", headers=headers, json={"strategy": "focus", "focus": "  Where are the deployment limits?  ", "web_enabled": True})

    assert response.status_code == 202
    assert response.get_json()["data"]["task_id"] == "queued-lab-task"
    assert queue.submitted[0]["owner_id"] == owner_id
    assert queue.submitted[0]["func"].__self__.owner_id == owner_id
    assert queue.submitted[0]["focus"] == "Where are the deployment limits?"
    assert queue.submitted[0]["web_enabled"] is True


def test_duplicate_generation_and_other_users_task_access_are_blocked(lab_client, monkeypatch):
    client, headers, owner_id = lab_client
    queue = CapturingQueue([
        {"task_id": "own-running", "owner_id": owner_id, "task_type": "briefing-lab", "status": "processing"},
        {"task_id": "other-private", "owner_id": "another-user", "task_type": "briefing-lab", "status": "completed", "result": {"private": "result"}},
    ])
    monkeypatch.setattr(lab_api, "is_ai_analysis_enabled", lambda: True)
    monkeypatch.setattr(lab_api, "BriefingLabService", AvailableService)
    monkeypatch.setattr(lab_api, "task_queue", queue)

    duplicate = client.post("/api/briefing-lab/run", headers=headers, json={"strategy": "daily"})
    private = client.get("/api/briefing-lab/tasks/other-private", headers=headers)

    assert duplicate.status_code == 409
    assert duplicate.get_json()["error_code"] == "LAB_TASK_ACTIVE"
    assert private.status_code == 404
    assert queue.submitted == []


def test_snapshot_api_passes_authenticated_owner_to_result_filter(lab_client, monkeypatch):
    client, headers, owner_id = lab_client
    monkeypatch.setattr(lab_api, "BriefingLabService", AvailableService)

    response = client.get("/api/briefing-lab", headers=headers)

    assert response.status_code == 200
    assert response.get_json()["data"]["owner_id"] == owner_id


@pytest.mark.parametrize("config", [
    {"enabled": False, "api_keys": ["fake-disabled-key"]},
    {"enabled": True, "api_keys": []},
])
def test_disabled_live_search_uses_saved_primary_notes_without_mongo_or_network(tmp_path, monkeypatch, config):
    app = make_auth_app()
    app.db.settings.insert_one({"key": SettingModel.KEY_TAVILY_CONFIG, "value": config})
    saved = [{"id": "W01", "title": "Saved primary source", "url": "https://docs.example.org/agents", "text": "A previously read official source note."}]
    (tmp_path / "web-context.json").write_text(json.dumps({"sources": saved}), encoding="utf-8")
    monkeypatch.setattr("pymongo.MongoClient", no_model_calls)
    monkeypatch.setattr("tavily.TavilyClient", no_model_calls)
    service = BriefingLabService(tmp_path, client_factory=no_model_calls)

    with app.app_context():
        sources, mode = service.external_sources("Deployment review gates")

    assert mode == "saved_primary_source_notes"
    assert sources == saved


def test_configured_live_search_uses_key_and_domain_filters_and_sends_only_focus(tmp_path, monkeypatch):
    app = make_auth_app()
    configured_key = "fake-configured-tavily-key"
    app.db.settings.insert_one({"key": SettingModel.KEY_TAVILY_CONFIG, "value": {
        "enabled": True, "api_keys": [configured_key, "fake-second-key"],
        "search_depth": "advanced", "max_results": 12,
        "include_domains": ["docs.example.org", "papers.example.org"],
        "exclude_domains": ["ads.example.org"],
    }})
    save_corpus(tmp_path, [source_document("PRIVATE_SOURCE_TEXT_MUST_NOT_BE_SENT_TO_SEARCH " * 1000)])
    monkeypatch.setenv("TAVILY_KEYS", '["fake-environment-key-that-must-not-override-settings"]')
    monkeypatch.setattr("pymongo.MongoClient", no_model_calls)
    calls = []

    class SearchClient:
        def __init__(self, api_key):
            assert api_key == configured_key

        def search(self, **kwargs):
            calls.append(kwargs)
            return {"results": [{"title": "Official agents documentation", "url": "https://docs.example.org/agents", "published_date": "2026-09-30", "content": "Primary search excerpt. " * 100}]}

    monkeypatch.setattr("tavily.TavilyClient", SearchClient)
    focus = "Which deployment steps still need human review?"
    with app.app_context():
        sources, mode = BriefingLabService(tmp_path, client_factory=no_model_calls).external_sources(focus)

    assert mode == "live_search"
    assert calls == [{"query": focus, "search_depth": "advanced", "max_results": 8, "include_raw_content": False, "include_domains": ["docs.example.org", "papers.example.org"], "exclude_domains": ["ads.example.org"]}]
    assert "PRIVATE_SOURCE_TEXT" not in json.dumps(calls)
    assert sources[0]["published_at"] == "2026-09-30"
    assert len(sources[0]["snippet"]) == 1200
    assert len(sources[0]["text"]) == 1800
    assert "未取得全文" in sources[0]["relation"]


def test_environment_tavily_keys_are_supported_when_global_setting_is_absent(tmp_path, monkeypatch):
    app = make_auth_app()
    monkeypatch.setenv("TAVILY_KEYS", '["fake-env-key"]')
    monkeypatch.setenv("TAVILY_SEARCH_DEPTH", "basic")
    monkeypatch.setenv("TAVILY_MAX_RESULTS", "3")
    monkeypatch.setattr("pymongo.MongoClient", no_model_calls)
    calls = []

    class SearchClient:
        def __init__(self, api_key):
            assert api_key == "fake-env-key"

        def search(self, **kwargs):
            calls.append(kwargs)
            return {"results": []}

    monkeypatch.setattr("tavily.TavilyClient", SearchClient)
    with app.app_context():
        sources, mode = BriefingLabService(tmp_path, client_factory=no_model_calls).external_sources("Agent review gates")

    assert sources == []
    assert mode == "live_search"
    assert calls[0]["query"] == "Agent review gates"
    assert calls[0]["max_results"] == 3
