"""引文局部失败不丢弃其他成果；断点续跑、日志和覆盖必须一致。"""
import hashlib
import json
from copy import deepcopy

import pytest

from app.services.briefing_lab_service import BriefingLabService, analysis_coverage, split_text
from app.services.briefing_modes_service import validate_mode_items
from app.services.briefing_reading_service import BriefingReadingService
from app.services.briefing_report_pdf import _document
from tests.test_briefing_lab import source_document
from tests.test_briefing_modes import modes_service, results
from tests.test_briefing_reports import create_service, extraction, TEXT


class RecordedClient:
    def __init__(self, responses):
        self.responses = iter(responses)
        self.calls = []

    def chat(self, **kwargs):
        self.calls.append(deepcopy(kwargs))
        data = next(self.responses)
        return {"content": json.dumps(data, ensure_ascii=False), "model": "test-model",
                "usage": {"prompt": 10, "completion": 5, "total": 15}, "elapsed_seconds": 0.5}


def claim_result(quote):
    return {"summary": "文稿的具体观点", "claims": [{"title": "真实观点", "body": "正文依据", "quote": quote}], "questions": []}


@pytest.mark.parametrize("stage", ["extraction", "claims"])
def test_invalid_item_is_skipped_with_one_call_and_original_output_is_saved(tmp_path, stage):
    report = create_service(tmp_path)
    source = report.corpus()["sources"][0]
    chunk = split_text(source["full_text"])[0]
    value = extraction() if stage == "extraction" else claim_result(TEXT)
    collection = "quotes" if stage == "extraction" else "claims"
    bad = {"title": "不实引文", "body": "错误解释", "quote": "This invented quote is absent from the transcript."}
    value[collection].insert(0, bad)
    client = RecordedClient([value])
    report.lab.client_factory = lambda **kwargs: client
    note = report._extract_chunk(source, chunk) if stage == "extraction" else report.lab._analyze_chunk(source, chunk)
    cache_path = report._chunk_path(source, chunk) if stage == "extraction" else report.lab._chunk_path(source, chunk)

    assert len(client.calls) == 1
    assert note["analysis_status"] == "partial"
    assert len(note[collection]) == 1
    assert note["rejected_items"][0]["item"] == bad
    assert all(item["quote"] in TEXT for item in note[collection])
    audit = json.loads((cache_path.parent / note["audit_record"]).read_text(encoding="utf-8"))
    assert audit["status"] == "partial" and audit["context"]["stage"] == stage
    assert audit["context"]["body_sha256"] == hashlib.sha256(TEXT.encode()).hexdigest()
    assert json.loads(audit["attempts"][0]["content"])[collection][0] == bad
    assert len(audit["rejected_items"]) == 1

    # 已接受的局部缺口不反复消耗 token；保留好的条目。
    if stage == "extraction":
        report._extract_chunk(source, chunk)
    else:
        report.lab._analyze_chunk(source, chunk)
    assert len(client.calls) == 1


def test_resume_after_service_restart_only_retries_failed_chunk_and_keeps_audit_history(tmp_path):
    source = source_document("The discussion preserves important conditions. " * 300)
    chunks = split_text(source["full_text"])
    assert len(chunks) == 2
    first_client = RecordedClient([claim_result(chunks[0]["text"][:100]), {"wrong": True}, {"wrong": True}])
    first = BriefingLabService(tmp_path, client_factory=lambda **kwargs: first_client)
    notes = first._source_notes(source)["chunks"]
    assert [note["analysis_status"] for note in notes] == ["completed", "skipped"]
    assert analysis_coverage(notes, 2)["completed_chunks"] == 1
    assert notes[1]["usage"]["total"] == 30
    failure_path = first._chunk_path(source, chunks[1]).parent / notes[1]["audit_record"]
    failed = json.loads(failure_path.read_text(encoding="utf-8"))
    assert failed["status"] == "failed" and len(failed["attempts"]) == 2
    assert failed["context"]["chunk_id"] == "C002"
    first._source_notes(source, cached_only=True)
    assert len(first_client.calls) == 3

    retry_client = RecordedClient([claim_result(chunks[1]["text"][:100])])
    resumed = BriefingLabService(tmp_path, client_factory=lambda **kwargs: retry_client)
    progress = []
    recovered = resumed._source_notes(source, progress_callback=lambda note, reused: progress.append(reused))["chunks"]
    assert len(retry_client.calls) == 1 and progress == [True, False]
    assert not analysis_coverage(recovered, 2)["partial"]
    assert failure_path.exists()
    assert len(list(tmp_path.glob("notes/*/attempts/C002/*.json"))) == 2
    resumed._source_notes(source)
    assert len(retry_client.calls) == 1


def test_failed_extraction_is_retried_by_reading_material_and_never_yields_fake_cards(tmp_path):
    report = create_service(tmp_path)
    client = RecordedClient([{"wrong": True}, {"wrong": True}, extraction()])
    report.lab.client_factory = lambda **kwargs: client
    reading = BriefingReadingService(report_service=report)
    _, cards, notes = reading._material(complete=True)
    assert cards == [] and notes[0]["analysis_status"] == "skipped"
    assert report._extraction_status(report.corpus())["completed_chunks"] == 0
    _, cards, _ = reading._material(complete=False)
    assert cards == [] and len(client.calls) == 2
    _, cards, notes = reading._material(complete=True)
    assert cards and notes[0]["analysis_status"] == "completed"
    assert len(client.calls) == 3
    reading._material(complete=True)
    assert len(client.calls) == 3


def test_connection_failure_is_not_silently_treated_as_empty_evidence(tmp_path):
    report = create_service(tmp_path)

    class OfflineClient:
        def chat(self, **kwargs):
            raise ConnectionError("provider unavailable")

    report.lab.client_factory = lambda **kwargs: OfflineClient()
    source = report.corpus()["sources"][0]
    chunk = split_text(source["full_text"])[0]
    with pytest.raises(ConnectionError, match="provider unavailable"):
        report._extract_chunk(source, chunk)
    assert not report._chunk_path(source, chunk).exists()


def test_mode_keeps_good_item_while_rejecting_bad_evidence_and_duplicate_source(tmp_path):
    service = modes_service(tmp_path)
    corpus, cards, _ = service._material()
    good = results(cards)["core"]["items"][0]
    bad = {**good, "evidence_ids": ["invented"]}
    result = validate_mode_items({"items": [bad, good, good]}, "core", cards, corpus)
    assert len(result["items"]) == 1
    assert [entry["index"] for entry in result["rejected_items"]] == [0, 2]
    assert result["items"][0]["evidence"][0]["quote"] in corpus["sources"][0]["full_text"]


def test_saved_report_exposes_skipped_items_and_model_audit(tmp_path):
    service = modes_service(tmp_path)
    _, cards, _ = service._material()
    value = results(cards)["core"]
    value["items"].append({**value["items"][0], "evidence_ids": ["invented"]})
    client = RecordedClient([value])
    service.report_service.lab.client_factory = lambda **kwargs: client
    report = service.generate("core")["reports"]["core"]
    assert len(report["sections"][0]["items"]) == 1
    assert report["analysis"]["partial"]
    assert report["analysis"]["mode_rejected_items"] == 1
    audit = json.loads((service.root / report["analysis"]["mode_audit_record"]).read_text(encoding="utf-8"))
    assert audit["context"]["mode"] == "core" and len(audit["rejected_items"]) == 1
    document = _document(report, [[report["sections"][0]["items"]]], 1, 0, "", style="paper")
    assert "已跳过 1 条未通过校验的内容" in document


def test_material_reports_both_stage_coverage_and_reuses_extraction_summary_for_failed_claim(tmp_path):
    from app.services.briefing_modes_service import BriefingModesService

    report = create_service(tmp_path)
    client = RecordedClient([extraction(), {"wrong": True}, {"wrong": True}])
    report.lab.client_factory = lambda **kwargs: client
    service = BriefingModesService(report_service=report, scope_service=object())
    progress = []
    _, cards, data = service._material(progress_callback=progress.append)
    assert cards
    assert data["analysis"]["stages"]["extraction"]["completed_chunks"] == 1
    assert data["analysis"]["stages"]["claims"]["skipped_chunks"] == 1
    assert data["analysis"]["partial"] and data["analysis"]["skipped_chunks"] == 1
    assert data["full_text_chunks"][0]["summary"] == extraction()["summary"]
    assert any("观点分析 1/1" in message for _, message in progress)
    assert len(client.calls) == 3
