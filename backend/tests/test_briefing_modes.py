"""不同内容模式必须使用全篇证据，保留真实资料身份、标签及导出隔离。"""
from copy import deepcopy

import pytest

from app.api import briefing_reports as api
from app.services.briefing_modes_service import BriefingModesService, MODES, validate_mode
from app.services.briefing_reading_service import BriefingReadingService
from app.services.briefing_report_service import BriefingReportService
from app.services.briefing_report_pdf import _candidates, _document
from tests.auth_helpers import add_user, auth_headers, make_auth_app
from tests.test_briefing_reading import make_service


def modes_service(tmp_path, owner_id=None):
    reading = make_service(tmp_path, owner_id)
    return BriefingModesService(report_service=reading.report_service, owner_id=owner_id)


def results(cards):
    return {
        "core": {"items": [{"title": "工程需要理解系统", "text": "节目区分了系统判断与代码生产，两者不能只按代码数量衡量。", "evidence_ids": [cards[0]["id"]], "topic_tags": ["编程"]}]},
        "quotes": {"items": [{"candidate_id": cards[0]["id"], "quote": cards[0]["quote"], "translation": "", "brief": "谈软件工程的重点。", "topic_tags": ["编程"]}]},
        "connections": {"items": [{"title": "判断要贴近实际工作", "text": "一期强调系统判断，另一期强调真实流程中的测量；这里是互补视角。", "evidence_ids": [cards[0]["id"], cards[1]["id"]], "relation": "complementary", "topic_tags": ["编程"]}]},
        "concepts": {"items": []}, "resources": {"items": []},
    }


def test_core_keeps_exact_source_evidence_and_tags_not_model_source_fields(tmp_path):
    service = modes_service(tmp_path)
    corpus, cards, _ = service._material()
    data = results(cards)["core"]
    data["items"][0].update(source_id="invented", start=9999)
    item = validate_mode(data, "core", cards, corpus)["items"][0]
    assert item["kind"] == "insight"
    assert item["source_id"] == cards[0]["source_id"]
    assert item["start"] == cards[0]["start"]
    assert item["evidence"][0]["quote"] == cards[0]["quote"]
    assert item["topic_tags"] == ["编程"]


def test_connection_requires_two_sources_and_valid_relation(tmp_path):
    service = modes_service(tmp_path)
    corpus, cards, _ = service._material()
    data = results(cards)["connections"]
    data["items"][0]["evidence_ids"] = [cards[0]["id"]]
    with pytest.raises(ValueError, match="两个不同节目"):
        validate_mode(data, "connections", cards, corpus)
    data["items"][0]["evidence_ids"] = [cards[0]["id"], cards[1]["id"]]
    data["items"][0]["relation"] = "mutually-proven"
    with pytest.raises(ValueError, match="关系"):
        validate_mode(data, "connections", cards, corpus)


def test_core_cannot_blend_two_programmes_into_one_programme_summary(tmp_path):
    service = modes_service(tmp_path)
    corpus, cards, _ = service._material()
    data = results(cards)["core"]
    data["items"][0]["evidence_ids"] = [cards[0]["id"], cards[1]["id"]]
    with pytest.raises(ValueError, match="同一期"):
        validate_mode(data, "core", cards, corpus)


def test_core_does_not_allow_multiple_points_to_displace_other_programmes(tmp_path):
    service = modes_service(tmp_path)
    corpus, cards, _ = service._material()
    other = {**cards[0], "id": "other-evidence-from-same-episode"}
    data = results(cards)["core"]
    second = deepcopy(data["items"][0])
    second["evidence_ids"] = [other["id"]]
    data["items"].append(second)
    with pytest.raises(ValueError, match="每期至多一条"):
        validate_mode(data, "core", [*cards, other], corpus)


def test_quote_mode_rejects_rewrite_and_retains_only_actual_original(tmp_path):
    service = modes_service(tmp_path)
    corpus, cards, _ = service._material()
    data = results(cards)["quotes"]
    data["items"][0]["quote"] = "工程工作的重点在于生产更多的代码，从而完全取代人类。"
    with pytest.raises(ValueError, match="逐字连续"):
        validate_mode(data, "quotes", cards, corpus)
    data = results(cards)["quotes"]
    item = validate_mode(data, "quotes", cards, corpus)["items"][0]
    assert item["title"] == ""
    assert item["quote"] in corpus["sources"][0]["full_text"]


@pytest.mark.parametrize("tag", [[], ["技术"], ["AI", "AI"], ["AI", "商业", "管理"]])
def test_topic_tags_use_closed_nonduplicated_content_vocabulary(tmp_path, tag):
    service = modes_service(tmp_path)
    corpus, cards, _ = service._material()
    data = results(cards)["core"]
    data["items"][0]["topic_tags"] = tag
    with pytest.raises(ValueError, match="主题标签"):
        validate_mode(data, "core", cards, corpus)


def test_resource_and_concept_types_cannot_be_invented_from_quote_candidate(tmp_path):
    service = modes_service(tmp_path)
    corpus, cards, _ = service._material()
    value = {"candidate_id": cards[0]["id"], "title": "不存在的资料", "text": "这是一份资料。", "topic_tags": ["编程"]}
    for mode in ("concepts", "resources"):
        with pytest.raises(ValueError, match="对应类型"):
            validate_mode({"items": [value]}, mode, cards, corpus)


def test_resource_keeps_extracted_name_link_and_relation(tmp_path):
    service = modes_service(tmp_path)
    corpus, cards, _ = service._material()
    resource = {**cards[0], "id": "actual-resource", "kind": "resource", "title": "真实书名", "original_title": "真实书名", "url": "", "resource_kind": "book", "relation": "mentioned"}
    value = {"candidate_id": resource["id"], "title": "模型想改成另一份书", "text": "节目用这本书说明方法。", "topic_tags": ["管理"], "url": "https://invented.example", "relation": "recommended"}
    item = validate_mode({"items": [value]}, "resources", [resource], corpus)["items"][0]
    assert item["title"] == "真实书名"
    assert item["url"] == ""
    assert item["relation"] == "mentioned"
    assert item["evidence"][0]["quote"] == resource["quote"]


@pytest.mark.parametrize("mode", ["quotes", "concepts", "resources"])
def test_candidate_ids_do_not_attach_favourites_to_a_different_episode(tmp_path, mode):
    service = modes_service(tmp_path)
    corpus, cards, _ = service._material()
    candidate = deepcopy(cards[0])
    if mode == "quotes":
        data = results(cards)[mode]
    else:
        candidate.update(kind="concept" if mode == "concepts" else "resource", title="正文中的完整名称" * 10)
        data = {"items": [{"candidate_id": candidate["id"], "text": "解释这条正文材料。", "topic_tags": ["编程"]}]}
    original = validate_mode(data, mode, [candidate], corpus)["items"][0]
    assert original["candidate_id"] == original["original_id"] == candidate["id"]
    candidate["id"] = "renumbered-candidate"
    data["items"][0]["candidate_id"] = candidate["id"]
    reordered = validate_mode(data, mode, [candidate], corpus)["items"][0]
    assert original["id"] == reordered["id"]
    candidate["episode_id"] = "another-episode-using-the-same-candidate-number"
    changed = validate_mode(data, mode, [candidate], corpus)["items"][0]
    assert original["id"] != changed["id"]


def test_all_modes_use_distinct_actual_prompts_and_can_be_empty(tmp_path, monkeypatch):
    service = modes_service(tmp_path)
    corpus, cards, payload = service._material()
    prompts = []

    def model(system, prompt, validator, **kwargs):
        prompts.append(system)
        assert "full_text_chunks" in prompt
        assert "evidence_candidates" in prompt
        return validator({"items": []}), {"model": "configured", "usage": {"total": 20}}

    monkeypatch.setattr(service.report_service.lab, "_model_call", model)
    generated = service.generate()["reports"]
    assert set(generated) == {mode["id"] for mode in MODES}
    assert len(set(prompts)) == 5
    assert all(report["coverage"]["sources"] == 3 for report in generated.values())
    snapshot = service.snapshot()
    assert snapshot["reports"]["core"]["mode"] == "core"
    assert snapshot["mode_prompts"]["core"]["prompt"] == generated["core"]["prompt"]
    assert "single_readings" in payload


def test_private_mode_export_is_owner_filtered_and_does_not_modify_editions(tmp_path, monkeypatch):
    service = modes_service(tmp_path, "owner-a")
    _, cards, _ = service._material()
    before = service.reading_service.edition()
    monkeypatch.setattr(service.report_service.lab, "_model_call", lambda system, prompt, validator, **kwargs: (validator(results(cards)["core"]), {"model": "configured", "usage": {"total": 20}}))
    report = service.generate("core")["reports"]["core"]
    assert service.report_service.report(report["id"])["mode"] == "core"
    other_report = BriefingReportService(service.report_service.root, lab_runtime_dir=service.report_service.lab.root, owner_id="owner-b")
    other = BriefingModesService(report_service=other_report, owner_id="owner-b")
    assert other_report.report(report["id"]) is None
    assert all(item is None for item in other.snapshot()["reports"].values())
    assert service.reading_service.edition() == before
    assert service.report("../../lab/corpus") is None


def test_mode_pdf_selects_insights_and_keeps_other_programme_attribution(tmp_path):
    service = modes_service(tmp_path)
    corpus, cards, _ = service._material()
    item = validate_mode(results(cards)["connections"], "connections", cards, corpus)["items"][0]
    report = {"id": "a" * 32, "mode": "connections", "mode_report": True, "variant": "overview", "title": "共性与分歧", "generated_at": "2026-10-01T00:00:00+00:00", "sources": service.report_service._metadata(corpus), "sections": [{"items": [item]}]}
    assert _candidates(report, 1)[1] == [item]
    html = _document(report, [[[item], []]], 1, 0, "http://localhost:3002")
    assert "共性与分歧" in html
    assert "互补 · AI 比较" in html
    assert "节目1" in html and "节目2" in html
    assert "episode-1?t=10" in html and "episode-2?t=20" in html


def test_connection_ids_are_stable_across_reordering_and_changed_for_different_evidence(tmp_path):
    service = modes_service(tmp_path)
    corpus, cards, _ = service._material()
    value = results(cards)["connections"]
    first = validate_mode(value, "connections", cards, corpus)["items"][0]
    value["items"][0]["evidence_ids"].reverse()
    reordered = validate_mode(value, "connections", cards, corpus)["items"][0]
    assert first["id"] == reordered["id"]
    value["items"][0]["evidence_ids"] = [cards[0]["id"], cards[2]["id"]]
    changed = validate_mode(value, "connections", cards, corpus)["items"][0]
    assert changed["id"] != first["id"]


def test_quote_mode_does_not_treat_full_text_claim_fragment_as_complete_quote(tmp_path):
    service = modes_service(tmp_path)
    corpus, cards, _ = service._material()
    cards[0]["kind"] = "claim"
    with pytest.raises(ValueError, match="quote候选"):
        validate_mode(results(cards)["quotes"], "quotes", cards, corpus)


def test_selected_english_evidence_can_add_translation_but_cannot_rebind_original(tmp_path):
    service = modes_service(tmp_path)
    corpus, cards, _ = service._material()
    english = {**cards[0], "quote": "Software engineering means understanding a complete system.", "translation": ""}
    data = results(cards)["core"]
    data["items"][0]["evidence_translations"] = {english["id"]: "软件工程意味着理解一个完整的系统。"}
    item = validate_mode(data, "core", [english], corpus)["items"][0]
    assert item["evidence"][0]["quote"] == english["quote"]
    assert item["evidence"][0]["translation"] == "软件工程意味着理解一个完整的系统。"
    data["items"][0].pop("evidence_translations")
    with pytest.raises(ValueError, match="非空忠实中文译文"):
        validate_mode(data, "core", [english], corpus)
    data["items"][0]["evidence_translations"] = {"another-episode": "错误引用的译文"}
    with pytest.raises(ValueError, match="本条已选"):
        validate_mode(data, "core", [english], corpus)


@pytest.fixture
def client():
    app = make_auth_app((api.briefing_reports_bp, "/api/briefing-reports"))
    user = add_user(app.db, "content-modes@example.com")
    return app.test_client(), auth_headers(user), str(user["_id"])


def test_modes_get_is_read_only(client, monkeypatch):
    http, headers, _ = client

    class Snapshot:
        def __init__(self, **kwargs):
            pass

        def snapshot(self, topic=None):
            return {"reports": {}, "topic": topic}

    monkeypatch.setattr(api, "BriefingModesService", Snapshot)
    assert http.get("/api/briefing-reports/modes?topic=商业", headers=headers).get_json()["data"]["topic"] == "商业"


@pytest.mark.parametrize("options,code", [({"mode": "layout"}, "INVALID_MODE"), ({"topic": "x" * 121}, "INVALID_TOPIC")])
def test_invalid_mode_options_do_not_start_service_or_task(client, monkeypatch, options, code):
    http, headers, _ = client
    monkeypatch.setattr(api, "is_ai_analysis_enabled", lambda: True)
    monkeypatch.setattr(api, "BriefingModesService", lambda **kwargs: pytest.fail("Must reject before reading"))
    response = http.post("/api/briefing-reports/modes/generate", headers=headers, json=options)
    assert response.status_code == 400 and response.get_json()["error_code"] == code


def test_disabled_ai_blocks_new_content_modes(client, monkeypatch):
    http, headers, _ = client
    monkeypatch.setattr(api, "is_ai_analysis_enabled", lambda: False)
    monkeypatch.setattr(api, "BriefingModesService", lambda **kwargs: pytest.fail("Must not start work"))
    assert http.post("/api/briefing-reports/modes/generate", headers=headers, json={"mode": "all"}).status_code == 423
