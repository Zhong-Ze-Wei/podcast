"""验证报告的真实出处、专项缓存、五版编排与私有导出边界。"""
import json

import pytest

from app.api import briefing_reports as api
from app.services.briefing_lab_service import corpus_id, split_text, write_json
from app.services.briefing_report_service import BriefingReportService, validate_extraction
from tests.auth_helpers import add_user, auth_headers, make_auth_app


TEXT = "Agent harness means the tools and environment around a model. The speaker recommends the Example Guide for testing."


def source(source_id="S01", episode_id="episode-1"):
    return {"id": source_id, "episode_id": episode_id, "title": "Tools around a model", "feed": "Example podcast", "published": "2026-09-29T09:00:00+00:00", "duration": 45, "source_type": "youtube", "material_type": "full_transcript", "full_text": TEXT, "segments": [{"text": TEXT, "start": 12, "end": 40}], "original_url": "https://www.youtube.com/watch?v=example"}


def extraction():
    return {"summary": "工具与环境的作用", "concepts": [{"title": "模型外围工具（harness）", "original_term": "harness", "text": "模型之外的工具和环境。", "context": "在讨论如何使用模型。", "quote": "Agent harness means the tools and environment around a model."}], "quotes": [{"title": "模型之外的环境", "text": "", "quote": "Agent harness means the tools and environment around a model.", "translation": "Harness 指模型周围的工具和环境。", "context": "讨论模型的工作环境。"}], "resources": [{"title": "Example Guide", "original_title": "Example Guide", "text": "节目用它介绍测试。", "quote": "The speaker recommends the Example Guide for testing.", "resource_kind": "book", "relation": "recommended", "url": "https://invented.example/guide"}], "backgrounds": []}


def create_service(tmp_path, owner_id=None):
    lab = tmp_path / "lab"
    lab.mkdir(exist_ok=True)
    write_json(lab / "corpus.json", {"sources": [source()], "generated_at": "2026-10-01T00:00:00+00:00", "diagnostics": {}})
    return BriefingReportService(tmp_path / "reports", lab_runtime_dir=lab, owner_id=owner_id)


def save_notes(service):
    material = service.corpus()["sources"][0]
    chunk = split_text(material["full_text"])[0]
    note = {"source_id": material["id"], "chunk_id": chunk["id"], "version": 1, **validate_extraction(extraction(), chunk), "usage": {"prompt": 100, "completion": 200, "total": 300}, "model": "real-configured-model", "elapsed_seconds": 1}
    write_json(service._chunk_path(material, chunk), note)


def test_extraction_rejects_rewritten_quotes_and_nonexistent_named_resources():
    chunk = {"start": 12000, "text": TEXT}
    fake = extraction()
    fake["quotes"][0]["quote"] = "The model can work without tools or environment."
    with pytest.raises(ValueError, match="引文不在"):
        validate_extraction(fake, chunk)
    missing = extraction()
    missing["resources"][0]["original_title"] = "A Guide Never Mentioned"
    with pytest.raises(ValueError, match="资料原名"):
        validate_extraction(missing, chunk)


def test_unverified_resource_links_and_speakers_are_omitted():
    value = extraction()
    value["quotes"][0].update(speaker="Unstated Guest", speaker_evidence="Agent harness means the tools and environment around a model.")
    result = validate_extraction(value, {"start": 12000, "text": TEXT})

    assert result["resources"][0]["url"] == ""
    assert result["resources"][0]["relation"] == "recommended"
    assert result["quotes"][0]["speaker"] == ""
    assert result["quotes"][0]["offset"] == 12000


def test_cached_extraction_yields_five_content_layouts_with_original_sources_and_time(tmp_path, monkeypatch):
    service = create_service(tmp_path)
    save_notes(service)
    monkeypatch.setattr(service.lab, "_model_call", lambda *args, **kwargs: pytest.fail("Cached content must not call the model again"))
    result = service.generate()

    assert {report["variant"] for report in result["reports"]} == {"overview", "episodes", "concepts", "quotes", "resources"}
    assert result["extraction"]["completed_chunks"] == 1
    assert result["extraction"]["usage"]["total"] == 300
    for report in result["reports"]:
        assert report["corpus_id"] == corpus_id(service.corpus())
        assert report["coverage"] == {"sources": 1, "chunks": 1, "characters": len(TEXT)}
        assert report["usage"]["total"] == 0  # Five layouts share one paid extraction.
        for section in report["sections"]:
            for card in section["items"]:
                for leaf in card.get("children", [card]):
                    assert leaf["episode_id"] == "episode-1"
                    assert leaf["source_id"] == "S01"
                    assert leaf["quote"] in TEXT
                    assert (leaf["start"], leaf["end"]) == (12, 40)
    episode = next(report for report in result["reports"] if report["variant"] == "episodes")
    assert {card["kind"] for card in episode["sections"][0]["items"][0]["children"]} == {"concept", "quote", "resource"}


def test_personal_reports_are_private_and_path_traversal_cannot_reach_files(tmp_path):
    service = create_service(tmp_path, "owner-a")
    save_notes(service)
    report = service.generate("quotes")["reports"][0]
    other = BriefingReportService(service.root, lab_runtime_dir=service.lab.root, owner_id="owner-b")

    assert service.report(report["id"])["id"] == report["id"]
    assert other.report(report["id"]) is None
    assert other.snapshot()["reports"] == []
    assert service.report("../corpus") is None
    assert service.report("../../lab/corpus.json") is None


def test_material_change_during_extraction_cannot_save_mixed_report(tmp_path, monkeypatch):
    service = create_service(tmp_path)

    def changed(progress_callback=None):
        corpus = service.corpus()
        corpus["sources"][0]["full_text"] += " Changed material."
        write_json(service.lab.root / "corpus.json", corpus)
        return []

    monkeypatch.setattr(service, "extract", changed)
    with pytest.raises(ValueError, match="同一批"):
        service.generate()
    assert not (service.root / "reports").exists()


def test_read_only_snapshot_does_not_trigger_extraction(tmp_path, monkeypatch):
    service = create_service(tmp_path)
    monkeypatch.setattr(service, "extract", lambda *args, **kwargs: pytest.fail("Reading must stay read-only"))
    snapshot = service.snapshot()

    assert snapshot["extraction"]["status"] == "not_started"
    assert snapshot["corpus"]["characters"] == len(TEXT)
    assert "full_text" not in snapshot["corpus"]["sources"][0]
    assert snapshot["diagnostics"]["search_mode"] == "disabled"


@pytest.fixture
def client():
    app = make_auth_app((api.briefing_reports_bp, "/api/briefing-reports"))
    user = add_user(app.db, "report-user@example.com")
    return app.test_client(), auth_headers(user), str(user["_id"])


def test_disabled_ai_blocks_generation_before_service_or_queue(client, monkeypatch):
    http, headers, _ = client
    monkeypatch.setattr(api, "is_ai_analysis_enabled", lambda: False)
    monkeypatch.setattr(api, "BriefingReportService", lambda **kwargs: pytest.fail("Must not start work"))
    response = http.post("/api/briefing-reports/generate", headers=headers, json={"variant": "all"})
    assert response.status_code == 423


@pytest.mark.parametrize("options,error", [
    ({"variant": "generic-answer"}, "INVALID_VARIANT"),
    ({"topic": "x" * 121}, "INVALID_TOPIC"),
    ({"interests": []}, "INVALID_INTERESTS"),
    ({"interests": ["made-up"]}, "INVALID_INTERESTS"),
    ({"web_enabled": "false"}, "INVALID_WEB_OPTION"),
])
def test_invalid_report_controls_are_rejected(client, monkeypatch, options, error):
    http, headers, _ = client
    monkeypatch.setattr(api, "is_ai_analysis_enabled", lambda: True)
    monkeypatch.setattr(api, "BriefingReportService", lambda **kwargs: pytest.fail("Must not start work"))
    response = http.post("/api/briefing-reports/generate", headers=headers, json=options)
    assert response.status_code == 400
    assert response.get_json()["error_code"] == error


def test_export_requires_owned_saved_report_and_exact_page_count(client, monkeypatch):
    http, headers, _ = client

    class HiddenReport:
        def __init__(self, **kwargs):
            pass

        def report(self, report_id):
            return None

    monkeypatch.setattr(api, "BriefingReportService", HiddenReport)
    bad_page = http.get("/api/briefing-reports/reports/hidden/html?pages=3", headers=headers)
    hidden = http.get("/api/briefing-reports/reports/hidden/pdf?pages=2", headers=headers)
    assert bad_page.status_code == 400
    assert hidden.status_code == 404


def test_other_owner_task_cannot_be_read(client, monkeypatch):
    http, headers, _ = client

    class PrivateTask:
        def get_status(self, task_id):
            return {"task_type": "briefing-report", "owner_id": "other", "status": "completed", "result": {"private": "report"}}

    monkeypatch.setattr(api, "task_queue", PrivateTask())
    response = http.get("/api/briefing-reports/tasks/other", headers=headers)
    assert response.status_code == 404


def test_export_links_use_frontend_origin_from_referer(client):
    http, _, _ = client
    with http.application.test_request_context("/api/briefing-reports/reports/example/pdf", base_url="http://localhost:5000", headers={"Referer": "http://localhost:3002/briefing-lab"}):
        assert api._app_base_url() == "http://localhost:3002"


def test_saved_official_background_is_labeled_external_and_book_link_does_not_change_relation(tmp_path):
    service = create_service(tmp_path)
    save_notes(service)
    write_json(service.lab.root / "report-web-context.json", {"sources": [
        {"id": "RW01", "source_id": "S01", "kind": "background", "title": "Official guest", "text": "官方页面介绍这位嘉宾的身份。", "url": "https://official.example/guest", "publisher": "Official site", "accessed_at": "2026-10-01", "reading_scope": "身份介绍"},
        {"id": "RW03", "source_id": "S01", "kind": "resource_resolution", "resource_title": "Example Guide", "url": "https://publisher.example/guide", "publisher": "Publisher", "accessed_at": "2026-10-01"},
    ]})

    report = service.generate("resources", web_enabled=True)["reports"][0]
    resource = report["sections"][0]["items"][0]
    background = report["sections"][-1]["items"][0]
    assert report["web_mode"] == "saved_primary_source_notes"
    assert resource["relation"] == "recommended"
    assert resource["url"] == "https://publisher.example/guide"
    assert resource["link_relation"] == "source_link_resolution"
    assert background["relation"] == "external"
    assert background["quote"] == ""
    assert background["start"] is None
    assert service.generate("resources", web_enabled=False)["reports"][0]["web_mode"] == "disabled"


def test_user_generation_queues_once_and_preserves_topic_and_selected_interests(client, monkeypatch):
    http, headers, owner_id = client
    submitted = []

    class AvailableService:
        def __init__(self, owner_id=None):
            self.owner_id = owner_id

        def corpus(self):
            return {"sources": [source()]}

        def generate(self, **kwargs):
            pytest.fail("HTTP request must queue, not call model inline")

    class Queue:
        def get_all_tasks(self, task_type=None):
            return []

        def submit(self, **kwargs):
            submitted.append(kwargs)
            return "queued-report"

    monkeypatch.setattr(api, "is_ai_analysis_enabled", lambda: True)
    monkeypatch.setattr(api, "BriefingReportService", AvailableService)
    monkeypatch.setattr(api, "task_queue", Queue())
    response = http.post("/api/briefing-reports/generate", headers=headers, json={"variant": "all", "topic": "  历史  ", "interests": ["quotes", "quotes", "backgrounds"], "web_enabled": True})

    assert response.status_code == 202
    assert submitted[0]["owner_id"] == owner_id
    assert submitted[0]["func"].__self__.owner_id == owner_id
    assert submitted[0]["topic"] == "历史"
    assert submitted[0]["interests"] == ["quotes", "backgrounds"]
    assert submitted[0]["web_enabled"] is True


def test_transcript_cache_reuse_binds_evidence_to_current_batch_source_id(tmp_path, monkeypatch):
    service = create_service(tmp_path)
    save_notes(service)
    corpus = service.corpus()
    corpus["sources"] = [source("S02", "different-episode")]
    write_json(service.lab.root / "corpus.json", corpus)
    monkeypatch.setattr(service.lab, "_model_call", lambda *args, **kwargs: pytest.fail("Identical transcript should reuse cached extraction"))

    report = service.generate("concepts")["reports"][0]
    card = report["sections"][0]["items"][0]
    assert card["source_id"] == "S02"
    assert card["episode_id"] == "different-episode"
    assert card["id"].startswith("S02-")


def test_identical_transcript_in_two_episodes_keeps_each_source_and_counts_shared_usage_once(tmp_path):
    service = create_service(tmp_path)
    save_notes(service)
    corpus = service.corpus()
    corpus["sources"].append(source("S02", "second-episode"))
    write_json(service.lab.root / "corpus.json", corpus)

    result = service.generate("episodes")
    episodes = result["reports"][0]["sections"][0]["items"]
    assert [(card["source_id"], card["episode_id"]) for card in episodes] == [("S01", "episode-1"), ("S02", "second-episode")]
    assert result["extraction"]["completed_chunks"] == 2
    assert result["extraction"]["usage"]["total"] == 300


@pytest.mark.parametrize("variant,interests", [
    ("concepts", ["quotes"]), ("quotes", ["concepts"]), ("resources", ["quotes"]),
])
def test_specialized_report_respects_unchecked_content_kinds(tmp_path, variant, interests):
    service = create_service(tmp_path)
    save_notes(service)
    report = service.generate(variant, interests=interests)["reports"][0]
    assert all(section["items"] == [] for section in report["sections"])


def test_ai_keyword_does_not_match_unrelated_guest_paine_by_partial_spelling(tmp_path):
    service = create_service(tmp_path)
    save_notes(service)
    corpus = service.corpus()
    corpus["sources"][0]["title"] = "Sarah Paine on World War I"
    write_json(service.lab.root / "corpus.json", corpus)

    report = service.generate("quotes", topic="AI")["reports"][0]
    assert report["sections"][0]["items"] == []


@pytest.mark.parametrize("format,renderer", [("html", "render_report_html"), ("pdf", "create_report_pdf")])
def test_actual_export_failure_returns_readable_error_instead_of_html_500(client, monkeypatch, format, renderer):
    from app.services import briefing_report_pdf
    http, headers, _ = client

    class AvailableReport:
        def __init__(self, **kwargs):
            pass

        def report(self, report_id):
            return {"id": report_id, "variant": "quotes"}

    def print_failure(*args, **kwargs):
        raise RuntimeError("打印服务未找到Chrome")

    monkeypatch.setattr(api, "BriefingReportService", AvailableReport)
    monkeypatch.setattr(briefing_report_pdf, renderer, print_failure)
    response = http.get(f"/api/briefing-reports/reports/saved/{format}?pages=1", headers=headers)
    assert response.status_code == 503
    assert response.get_json()["error_code"] == "REPORT_EXPORT_FAILED"
    assert response.get_json()["message"] == "打印服务未找到Chrome"
