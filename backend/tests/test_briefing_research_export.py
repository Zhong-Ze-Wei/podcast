"""研究快照保留全量正文、原始时间段和冻结指纹，不调用生产分析流程。"""
import csv
import hashlib
import json
from datetime import datetime

import pytest

from scripts.export_briefing_research import export_research
from app.services.briefing_lab_service import write_json
from tests.test_briefing_scope import add_episode, scope_service


def read_jsonl(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def read_csv(path):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def test_export_keeps_non_matching_and_missing_body_without_calling_models(tmp_path, monkeypatch):
    service = scope_service(tmp_path)
    _, feed = add_episode(service.db, datetime(2026, 9, 1), "AI单集", "大语言模型训练与推理是不同的工作，不能只看模型排名。")
    add_episode(service.db, datetime(2026, 9, 20), "不相关", "细胞每天都在更新，这期播客介绍溶酶体的研究历史。", feed)
    add_episode(service.db, datetime(2026, 9, 25), "没有正文", None, feed)
    add_episode(service.db, datetime(2026, 9, 30, 16), "香港十月", "不属于九月。", feed)
    sources = service.collect("month", "2026-09-01")["corpus"]["sources"]
    for source in sources:
        selected = source["title"] == "AI单集"
        write_json(service._screen_path(source, ["AI", "LLM"]) / "result.json",
                   {"selected": selected, "topic_tags": [], "evidence": [], "relevance_reason": "", "chunks": 1})
    def forbidden(*args, **kwargs):
        raise AssertionError("导出不应调用模型")
    monkeypatch.setattr(service.report_service.lab, "_model_call", forbidden)
    monkeypatch.setattr(service, "screen", forbidden)
    output = tmp_path / "snapshot"
    manifest = export_research(service, "2026-09-01", output, "test-commit")
    rows = read_csv(output / "episodes.csv")
    assert {row["title"] for row in rows} == {"AI单集", "不相关", "没有正文"}
    assert len(read_jsonl(output / "sources.jsonl")) == 2
    assert next(row for row in rows if row["title"] == "不相关")["cached_selected"] == "False"
    missing = next(row for row in rows if row["title"] == "没有正文")
    assert missing["body_reference"] == "" and missing["body_available"] == "False"
    assert manifest["applies_interest_filter_to_export"] is False
    assert manifest["counts"]["cached_selected_sources"] == 1
    assert manifest["counts"]["cached_non_selected_sources"] == 1
    assert manifest["counts"]["episodes_without_body"] == 1


def test_long_raw_unicode_body_segments_and_csv_newlines_round_trip(tmp_path):
    service = scope_service(tmp_path)
    raw_text = " \n" + ('字幕原话, "SVG" 🙂\n另一个段落。' * 3500) + " \n"
    title = '原话, "引用"\n第二行'
    episode, _ = add_episode(service.db, datetime(2026, 9, 29), title, raw_text)
    segments = [{"start": 1.25, "end": 100, "text": raw_text, "speaker": "甲", "confidence": 0.75},
                {"start": 100, "end": 101, "text": "", "original_extra": {"x": "字幕噪音"}}]
    service.db.transcripts.update_one({"episode_id": episode["_id"]}, {"$set": {"segments": segments}})
    output = tmp_path / "snapshot"
    manifest = export_research(service, "2026-09-01", output, "test-commit")
    source = read_jsonl(output / "sources.jsonl")[0]
    assert len(source["full_text"]) > 32767
    assert source["raw_text"] == raw_text
    assert source["full_text"] == raw_text.strip()
    assert source["raw_segments"] == segments
    transcript = read_jsonl(output / "raw_transcripts.jsonl")[0]
    assert transcript["text"] == raw_text and transcript["segments"] == segments
    assert read_csv(output / "episodes.csv")[0]["title"] == title
    chunks = read_jsonl(output / "baseline_chunks.jsonl")
    assert "".join(chunk["text"] for chunk in chunks) == source["full_text"]
    assert chunks[0]["start"] == 0 and chunks[-1]["end"] == len(source["full_text"])
    for index, chunk in enumerate(chunks):
        assert chunk["text"] == source["full_text"][chunk["start"]:chunk["end"]]
        assert chunk["text_sha256"] == hashlib.sha256(chunk["text"].encode()).hexdigest()
        if index:
            assert chunk["start"] == chunks[index - 1]["end"]
    assert manifest["counts"]["body_characters"] == len(source["full_text"])


def test_duplicate_subscription_provenance_records_borrowed_body(tmp_path):
    service = scope_service(tmp_path)
    inside, feed = add_episode(service.db, datetime(2026, 9, 1), "same-guid", None)
    duplicate, _ = add_episode(service.db, datetime(2026, 9, 2), "same-guid", None, feed)
    outside, _ = add_episode(service.db, datetime(2026, 8, 20), "same-guid", "跨期副本已有文稿，九月只读取这份现有全文。", feed)
    other, _ = add_episode(service.db, datetime(2026, 9, 3), "same-guid", "不同订阅的相同guid应该保留自己的正文。")
    output = tmp_path / "snapshot"
    manifest = export_research(service, "2026-09-01", output, "test-commit")
    rows = read_csv(output / "episodes.csv")
    borrowed = next(row for row in rows if row["borrowed_transcript"] == "True")
    assert borrowed["episode_id"] == str(duplicate["_id"])
    assert borrowed["transcript_episode_id"] == str(outside["_id"])
    assert set(json.loads(borrowed["duplicate_episode_ids"])) == {str(inside["_id"]), str(duplicate["_id"]), str(outside["_id"])}
    assert manifest["counts"]["episodes"] == 2 and manifest["counts"]["raw_episode_rows"] == 3
    assert {row["episode_id"] for row in read_csv(output / "raw_episodes.csv")} == {str(inside["_id"]), str(duplicate["_id"]), str(other["_id"])}
    assert str(outside["_id"]) in {record["episode_id"] for record in read_jsonl(output / "raw_transcripts.jsonl")}


def test_deleted_feed_episode_and_raw_body_remain_available_outside_main_corpus(tmp_path):
    service = scope_service(tmp_path)
    add_episode(service.db, datetime(2026, 9, 3), "可见节目", "有效订阅的正文保留在主材料集。")
    orphan, deleted_feed = add_episode(service.db, datetime(2026, 9, 4), "孤立节目", "已删除订阅的正文也不能从全库九月快照漏掉。")
    service.db.feeds.delete_one({"_id": deleted_feed["_id"]})
    output = tmp_path / "snapshot"
    manifest = export_research(service, "2026-09-01", output, "test-commit")
    assert manifest["counts"]["episodes"] == 1
    assert manifest["counts"]["raw_episode_rows"] == 2
    assert manifest["counts"]["orphaned_feed_episodes"] == 1
    assert manifest["counts"]["orphaned_feed_transcripts_with_body"] == 1
    raw_episode = next(row for row in read_csv(output / "raw_episodes.csv") if row["episode_id"] == str(orphan["_id"]))
    assert raw_episode["orphaned_feed"] == "True" and raw_episode["in_product_corpus"] == "False"
    raw_transcript = next(row for row in read_jsonl(output / "raw_transcripts.jsonl") if row["episode_id"] == str(orphan["_id"]))
    assert raw_transcript["orphaned_feed"] and raw_transcript["used_by_source_ids"] == []
    assert raw_transcript["text"] == "已删除订阅的正文也不能从全库九月快照漏掉。"


def test_cache_inventory_does_not_create_missing_notes_or_double_count_shared_usage(tmp_path):
    service = scope_service(tmp_path)
    body = "这两期恰好保存了相同全文，缓存按正文哈希共享。"
    add_episode(service.db, datetime(2026, 9, 2), "one", body)
    add_episode(service.db, datetime(2026, 9, 3), "two", body)
    source = service.collect("month", "2026-09-01")["corpus"]["sources"][0]
    chunk = {"id": "C001"}
    note = {"summary": "已有摘要", "quotes": [], "model": "cached-model", "elapsed_seconds": 2.5,
            "usage": {"prompt": 10, "completion": 2, "total": 12}}
    write_json(service.report_service._chunk_path(source, chunk), note)
    output = tmp_path / "snapshot"
    manifest = export_research(service, "2026-09-01", output, "test-commit")
    cache = manifest["cache_statistics"]["extraction"]
    assert cache["cached_source_chunks"] == 2 and cache["unique_cached_files"] == 1
    assert cache["recorded_usage"]["total"] == 12 and cache["recorded_request_seconds_sum"] == 2.5
    assert manifest["cache_statistics"]["claims"]["missing_source_chunks"] == 2
    assert not service.report_service.lab._chunk_path(source, chunk).exists()
    assert all(record["content"] == note for record in read_jsonl(output / "cached_records.jsonl"))


def test_manifest_hashes_counts_and_existing_snapshot_refuses_overwrite(tmp_path):
    service = scope_service(tmp_path)
    add_episode(service.db, datetime(2026, 9, 2), "one", "研究用正文完整保留，不截断任何句子。")
    output = tmp_path / "snapshot"
    manifest = export_research(service, "2026-09-01", output, "test-commit")
    assert json.loads((output / "manifest.json").read_text(encoding="utf-8")) == manifest
    for name, info in manifest["files"].items():
        content = (output / name).read_bytes()
        assert info["bytes"] == len(content)
        assert info["sha256"] == hashlib.sha256(content).hexdigest()
        records = read_csv(output / name) if name.endswith(".csv") else read_jsonl(output / name)
        assert info["records"] == len(records)
    before = (output / "manifest.json").read_bytes()
    with pytest.raises(FileExistsError, match="拒绝覆盖"):
        export_research(service, "2026-09-01", output, "another-commit")
    assert (output / "manifest.json").read_bytes() == before
