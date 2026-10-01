"""精选与单篇解读必须有完整原话、正确来源及私有缓存边界。"""
from copy import deepcopy

import pytest

from app.api import briefing_reports as api
from app.services.briefing_lab_service import corpus_id, split_text, write_json
from app.services.briefing_reading_service import BriefingReadingService, selected_quote, validate_edition, validate_reading
from app.services.briefing_report_service import BriefingReportService, validate_extraction
from tests.auth_helpers import add_user, auth_headers, make_auth_app


QUOTES = ["软件工程真正的重点是理解整个系统，而不只是写出几行代码。",
          "判断工具是否好用，要把它放到自己真正关心的工作流程里去测量。",
          "我认为问题不在战略选择本身，而在高估了自己当时的管理能力。"]


def make_service(tmp_path, owner_id=None):
    corpus = {"sources": [], "diagnostics": {}, "generated_at": "2026-10-01T00:00:00+00:00"}
    for index, quote in enumerate(QUOTES, 1):
        text = f"开场介绍。{quote}然后继续谈这件事对日常工作的影响。"
        corpus["sources"].append({"id": f"S{index:02d}", "episode_id": f"episode-{index}", "feed": f"节目{index}", "title": f"具体讨论{index}",
                                  "full_text": text, "segments": [{"text": text, "start": index * 10, "end": index * 10 + 5}],
                                  "duration": 1000, "source_type": "rss", "material_type": "full_transcript", "original_url": "https://example.com/podcast"})
    lab = tmp_path / "lab"
    write_json(lab / "corpus.json", corpus)
    report = BriefingReportService(tmp_path / "reports", lab_runtime_dir=lab, owner_id=owner_id)
    for source, quote in zip(corpus["sources"], QUOTES):
        chunk = split_text(source["full_text"])[0]
        result = {"summary": "片段具体解释工作的方法。", "concepts": [], "resources": [], "backgrounds": [],
                  "quotes": [{"title": "具体观点", "text": "", "quote": quote, "translation": "", "context": "在谈实际工作。"}]}
        note = {"source_id": source["id"], "chunk_id": chunk["id"], **validate_extraction(result, chunk), "model": "configured", "usage": {"total": 3}, "version": 1}
        write_json(report._chunk_path(source, chunk), note)
    return BriefingReadingService(owner_id=owner_id, report_service=report)


def edition_result(cards):
    return {"items": [{"candidate_id": card["id"], "id": card["id"], "quote": card["quote"], "translation": "", "brief": "在谈工作判断的依据。"} for card in cards],
            "threads": [{"text": "这些判断都把注意力放在实际工作上。", "supporting_item_ids": [cards[0]["id"], cards[1]["id"]]}]}


def test_rewritten_or_joined_quote_is_rejected(tmp_path):
    service = make_service(tmp_path)
    corpus, cards, _ = service._material()
    result = edition_result(cards)
    result["items"][0]["quote"] = "软件工程真正的重点是生成更多代码，让工作效率变得更高。"
    with pytest.raises(ValueError, match="逐字连续"):
        validate_edition(result, cards, corpus)
    result["items"][0]["quote"] = "软件工程真正的重点是理解整个系统，……写出几行代码。"
    with pytest.raises(ValueError, match="逐字连续"):
        validate_edition(result, cards, corpus)


def test_shortening_cannot_drop_sentence_start_or_end(tmp_path):
    service = make_service(tmp_path)
    corpus, cards, _ = service._material()
    candidate = cards[0]
    base = {"candidate_id": candidate["id"], "brief": "在讨论软件工程。", "translation": ""}
    with pytest.raises(ValueError, match="半句话开始"):
        selected_quote({**base, "quote": "理解整个系统，而不只是写出几行代码。"}, {candidate["id"]: candidate}, {"S01": corpus["sources"][0]})
    with pytest.raises(ValueError, match="截取半句"):
        selected_quote({**base, "quote": "软件工程真正的重点是理解整个系统"}, {candidate["id"]: candidate}, {"S01": corpus["sources"][0]})


def test_complete_short_sentence_is_relocated_to_right_offset_and_time(tmp_path):
    service = make_service(tmp_path)
    corpus, cards, _ = service._material()
    source = corpus["sources"][0]
    source["full_text"] = f"节目开头。{QUOTES[0]}判断依据应当来自真实任务，不能只盯着代码的行数。"
    source["segments"] = [{"text": "节目开头。", "start": 0, "end": 5}, {"text": QUOTES[0], "start": 12, "end": 24},
                          {"text": "判断依据应当来自真实任务，不能只盯着代码的行数。", "start": 30, "end": 40}]
    candidate = {**cards[0], "quote": source["full_text"][5:], "offset": 5}
    value = {"candidate_id": candidate["id"], "quote": QUOTES[0], "brief": "讨论系统与代码的区别。", "translation": ""}
    result = selected_quote(value, {candidate["id"]: candidate}, {"S01": source})
    assert result["quote"] in source["full_text"]
    assert result["offset"] == source["full_text"].index(QUOTES[0])
    assert result["start"] == 12
    assert result["title"] == ""
    assert result["translation"] == ""


def test_common_point_requires_selected_evidence_from_two_sources(tmp_path):
    service = make_service(tmp_path)
    corpus, cards, _ = service._material()
    result = edition_result(cards)
    result["threads"][0]["supporting_item_ids"] = [cards[0]["id"], cards[0]["id"]]
    with pytest.raises(ValueError, match="两个不同节目"):
        validate_edition(result, cards, corpus)
    result["threads"][0]["supporting_item_ids"] = [cards[0]["id"], "invented-item"]
    with pytest.raises(ValueError, match="实际选中"):
        validate_edition(result, cards, corpus)


def test_edition_limits_count_context_and_same_source_monopoly(tmp_path):
    service = make_service(tmp_path)
    corpus, cards, _ = service._material()
    result = edition_result(cards)
    result["items"][0]["brief"] = "背" * 33
    with pytest.raises(ValueError, match="背景提要"):
        validate_edition(result, cards, corpus)
    result["items"] = result["items"][:2]
    with pytest.raises(ValueError, match="3–5"):
        validate_edition(result, cards, corpus)
    result = edition_result(cards)
    result["items"][2] = deepcopy(result["items"][0])
    with pytest.raises(ValueError, match="重复"):
        validate_edition(result, cards, corpus)


def test_cache_reads_never_generate_and_private_edition_is_exportable_only_by_owner(tmp_path, monkeypatch):
    service = make_service(tmp_path, "owner-a")
    corpus, cards, _ = service._material()
    calls = []

    def model(system, prompt, validator, **kwargs):
        calls.append(prompt)
        return validator(edition_result(cards)), {"usage": {"total": 500}, "model": "configured", "elapsed_seconds": 1}

    monkeypatch.setattr(service.report_service.lab, "_model_call", model)
    edition = service.generate_edition()["edition"]
    assert len(calls) == 1
    monkeypatch.setattr(service.report_service.lab, "_model_call", lambda *args, **kwargs: pytest.fail("Reading must not call AI"))
    assert service.edition()["edition"]["id"] == edition["id"]
    assert service.report_service.snapshot()["edition"]["id"] == edition["id"]
    assert service.report_service.report(edition["id"])["reading_edition"] is True
    other_report = BriefingReportService(service.report_service.root, lab_runtime_dir=service.report_service.lab.root, owner_id="owner-b")
    other = BriefingReadingService(report_service=other_report, owner_id="owner-b")
    assert other.edition()["edition"] is None
    assert other_report.report(edition["id"]) is None
    assert service.report_service.report("../../lab/corpus") is None
    assert service.reading("S01")["reading"] is None


def test_failed_regeneration_keeps_previous_cache(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    _, cards, _ = service._material()
    monkeypatch.setattr(service.report_service.lab, "_model_call", lambda system, prompt, validator, **kwargs: (validator(edition_result(cards)), {"usage": {}, "model": "configured"}))
    edition = service.generate_edition()["edition"]

    def fail(*args, **kwargs):
        raise ValueError("模型结果未通过依据校验")

    monkeypatch.setattr(service.report_service.lab, "_model_call", fail)
    with pytest.raises(ValueError):
        service.generate_edition()
    assert service.edition()["edition"]["id"] == edition["id"]


def test_single_reading_uses_own_full_notes_and_actual_resources(tmp_path, monkeypatch):
    service = make_service(tmp_path)
    _, cards, _ = service._material()
    card = cards[0]
    result = {"takeaway": "工程的重点是理解系统。", "points": [{"title": "理解系统", "meaning": "这句话把工程判断与代码生产区分开来。", "candidate_id": card["id"], "quote": card["quote"], "translation": "", "brief": "谈系统思考。"}], "resource_ids": []}
    prompts = []

    def model(system, prompt, validator, **kwargs):
        prompts.append(prompt)
        return validator(result), {"usage": {"total": 200}, "model": "configured"}

    monkeypatch.setattr(service.report_service.lab, "_model_call", model)
    reading = service.generate_reading("S01")["reading"]
    assert "片段具体解释工作的方法" in prompts[0]
    assert QUOTES[1] not in prompts[0]
    assert reading["points"][0]["quote"]["quote"] == QUOTES[0]
    assert service.reading("S01")["reading"]["id"] == reading["id"]
    assert service.reading("S02")["reading"] is None
    result["resource_ids"] = [card["id"]]
    with pytest.raises(ValueError, match="资料"):
        validate_reading(result, [card], service.report_service.corpus()["sources"][0])


def test_focused_edition_can_have_one_or_zero_matches_without_unrelated_filler(tmp_path):
    service = make_service(tmp_path)
    corpus, cards, _ = service._material()
    result = edition_result(cards)
    result["items"] = result["items"][:1]
    result["threads"] = []
    assert len(validate_edition(result, cards, corpus, topic="软件工程")["items"]) == 1
    assert validate_edition({"items": [], "threads": []}, cards, corpus, topic="没有相关内容的主题")["items"] == []


def test_reading_rejects_repeated_points_and_other_source_evidence(tmp_path):
    service = make_service(tmp_path)
    corpus, cards, _ = service._material()
    card = cards[0]
    point = {"title": "理解系统", "meaning": "工程判断超过代码生产。", "candidate_id": card["id"], "quote": card["quote"], "translation": "", "brief": "谈系统判断。"}
    with pytest.raises(ValueError, match="重复"):
        validate_reading({"takeaway": "系统判断很重要。", "points": [point, point], "resource_ids": []}, cards, corpus["sources"][0])
    other = {**point, "candidate_id": cards[1]["id"], "quote": cards[1]["quote"]}
    with pytest.raises(ValueError, match="这一期"):
        validate_reading({"takeaway": "系统判断很重要。", "points": [other], "resource_ids": []}, cards, corpus["sources"][0])


def test_short_translation_does_not_need_padding_but_is_required(tmp_path):
    service = make_service(tmp_path)
    english = "Models are grown, not designed."
    source = {"id": "S01", "full_text": english, "segments": [{"text": english, "start": 0, "end": 4}]}
    card = {"id": "S01-quote", "source_id": "S01", "quote": english, "offset": 0, "kind": "quote"}
    value = {"candidate_id": card["id"], "quote": english, "translation": "模型是长出来的，而非设计出来的。", "brief": "谈模型能力如何演进。"}
    assert selected_quote(value, {card["id"]: card}, {"S01": source})["translation"] == value["translation"]
    with pytest.raises(ValueError, match="忠实译文"):
        selected_quote({**value, "translation": ""}, {card["id"]: card}, {"S01": source})


def test_repeated_quote_after_body_header_uses_second_audio_occurrence():
    quote = "软件工程需要先理解整个系统，然后才是具体代码。"
    body = "节目介绍\n" + quote + " " + quote
    source = {"id": "S01", "full_text": body, "segments": [{"text": quote, "start": 10, "end": 20}, {"text": quote, "start": 50, "end": 60}]}
    card = {"id": "second-quote", "source_id": "S01", "quote": quote, "offset": body.rfind(quote), "kind": "quote"}
    value = {"candidate_id": card["id"], "quote": quote, "translation": "", "brief": "再次谈到系统思考。"}
    result = selected_quote(value, {card["id"]: card}, {"S01": source})
    assert result["offset"] == body.rfind(quote)
    assert (result["start"], result["end"]) == (50, 60)


@pytest.fixture
def client():
    app = make_auth_app((api.briefing_reports_bp, "/api/briefing-reports"))
    user = add_user(app.db, "reading-user@example.com")
    return app.test_client(), auth_headers(user), str(user["_id"])


@pytest.mark.parametrize("path", ["/edition/generate", "/reading/S01/generate"])
def test_ai_disabled_blocks_both_new_generation_paths(client, monkeypatch, path):
    http, headers, _ = client
    monkeypatch.setattr(api, "is_ai_analysis_enabled", lambda: False)
    monkeypatch.setattr(api, "BriefingReadingService", lambda **kwargs: pytest.fail("Must not read material or queue work"))
    response = http.post("/api/briefing-reports" + path, headers=headers, json={})
    assert response.status_code == 423


def test_new_get_endpoints_are_read_only_and_missing_source_is_404(client, monkeypatch):
    http, headers, _ = client

    class Reader:
        def __init__(self, **kwargs):
            pass

        def edition(self):
            return {"edition": None, "sources": []}

        def reading(self, source_id):
            return None

    monkeypatch.setattr(api, "BriefingReadingService", Reader)
    assert http.get("/api/briefing-reports/edition", headers=headers).get_json()["data"]["edition"] is None
    assert http.get("/api/briefing-reports/reading/missing", headers=headers).status_code == 404


def test_edition_generation_queues_topic_and_owner_without_inline_model(client, monkeypatch):
    http, headers, owner_id = client
    submitted = []

    class Reader:
        def __init__(self, **kwargs):
            self.report_service = self

        def corpus(self):
            return {"sources": [{"id": "S01"}]}

        def generate_edition(self, **kwargs):
            pytest.fail("Must queue")

    class Queue:
        def get_all_tasks(self, **kwargs):
            return []

        def submit(self, **kwargs):
            submitted.append(kwargs)
            return "queued-reading"

    monkeypatch.setattr(api, "BriefingReadingService", Reader)
    monkeypatch.setattr(api, "task_queue", Queue())
    monkeypatch.setattr(api, "is_ai_analysis_enabled", lambda: True)
    response = http.post("/api/briefing-reports/edition/generate", headers=headers, json={"topic": "  软件工程  "})
    assert response.status_code == 202
    assert submitted[0]["topic"] == "软件工程"
    assert submitted[0]["owner_id"] == owner_id
    assert submitted[0]["task_type"] == "briefing-report"
