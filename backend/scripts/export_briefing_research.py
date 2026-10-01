"""冻结一个月的已有正文与缓存供算法实验；只读 MongoDB，不调用模型或启动应用。"""
import argparse
import csv
import hashlib
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

BACKEND = Path(__file__).resolve().parents[1]
REPOSITORY = BACKEND.parent
sys.path.insert(0, str(BACKEND))

from app.services.briefing_lab_service import CHUNK_SIZE, now_iso, split_text
from app.services.briefing_report_service import BriefingReportService
from app.services.briefing_scope_service import BriefingScopeService, _content_identity, _published, calendar_period


BASELINE_INTERESTS = ["AI", "LLM"]
EPISODE_FIELDS = [
    "source_id", "episode_id", "feed_id", "guid", "title", "feed", "source_type",
    "published_at", "body_available", "char_count", "body_sha256", "body_reference",
    "cached_screening_status", "cached_selected", "cached_topics", "cached_reason",
    "cached_evidence", "baseline_chunk_count", "duplicate_episode_ids",
    "transcript_id", "transcript_episode_id", "transcript_source", "borrowed_transcript",
]
RAW_EPISODE_FIELDS = [
    "episode_id", "canonical_source_id", "canonical_episode_id", "feed_id", "feed",
    "guid", "title", "published_at", "content_identity", "is_canonical", "has_own_body", "orphaned_feed", "in_product_corpus",
    "description", "duration", "original_url", "audio_url",
]
CACHE_FIELDS = [
    "source_id", "body_sha256", "stage", "chunk_id", "status", "cache_path",
    "cache_sha256", "cache_bytes", "model", "prompt_tokens", "completion_tokens",
    "total_tokens", "elapsed_seconds", "record_reference",
]


def _json_default(value):
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, datetime):
        return value.isoformat()
    raise TypeError(f"Cannot serialize {type(value).__name__}")


def _json(value):
    return json.dumps(value, ensure_ascii=False, default=_json_default)


def _sha(text):
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _write_jsonl(path, records):
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        for record in records:
            handle.write(_json(record) + "\n")


def _write_csv(path, fields, records):
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for record in records:
            writer.writerow({key: _json(value) if isinstance(value, (list, dict)) else value
                             for key, value in record.items()})


def _file_info(path, record_count, fields):
    content = path.read_bytes()
    return {"records": record_count, "bytes": len(content), "sha256": hashlib.sha256(content).hexdigest(),
            "fields": fields}


def _cache_snapshot(service, sources):
    """只复制已有缓存；相同物理缓存的费用不重复累计。"""
    inventory, records, observed_files = [], [], {}
    for source in sources:
        digest = _sha(source["full_text"])
        screening_root = service._screen_path(source, BASELINE_INTERESTS)
        paths = [("screening_result", "", screening_root / "result.json")]
        for chunk in split_text(source["full_text"]):
            paths.extend([
                ("screening", chunk["id"], screening_root / f"{chunk['id']}.json"),
                ("extraction", chunk["id"], service.report_service._chunk_path(source, chunk)),
                ("claims", chunk["id"], service.report_service.lab._chunk_path(source, chunk)),
            ])
            failure = screening_root / f"{chunk['id']}.failure.json"
            if failure.exists():
                paths.append(("screening_failure", chunk["id"], failure))
        for stage, chunk_id, path in paths:
            cache_root = service.report_service.lab.root if stage == "claims" else service.report_service.root
            cache_directory = "briefing-lab" if stage == "claims" else "briefing-reports"
            relative = f".runtime/{cache_directory}/{path.relative_to(cache_root).as_posix()}"
            row = {"source_id": source["id"], "body_sha256": digest, "stage": stage,
                   "chunk_id": chunk_id, "status": "missing", "cache_path": relative}
            if path.exists():
                raw = path.read_bytes()
                content = json.loads(raw)
                usage = content.get("usage", {})
                row.update(status="cached", cache_sha256=hashlib.sha256(raw).hexdigest(), cache_bytes=len(raw),
                           model=content.get("model", ""), prompt_tokens=usage.get("prompt"),
                           completion_tokens=usage.get("completion"), total_tokens=usage.get("total"),
                           elapsed_seconds=content.get("elapsed_seconds"),
                           record_reference=f"cached_records.jsonl#{source['id']}:{stage}:{chunk_id}")
                records.append({"source_id": source["id"], "body_sha256": digest, "stage": stage,
                                "chunk_id": chunk_id, "cache_path": relative, "cache_sha256": row["cache_sha256"],
                                "content": content})
                if stage in ("screening", "extraction", "claims"):
                    observed_files[str(path)] = {"stage": stage, "usage": usage,
                                                 "elapsed_seconds": content.get("elapsed_seconds")}
            inventory.append(row)
    statistics = {}
    for stage in ("screening", "extraction", "claims"):
        rows = [row for row in inventory if row["stage"] == stage]
        files = [record for record in observed_files.values() if record["stage"] == stage]
        statistics[stage] = {"expected_source_chunks": len(rows), "cached_source_chunks": sum(row["status"] == "cached" for row in rows),
                             "missing_source_chunks": sum(row["status"] == "missing" for row in rows),
                             "unique_cached_files": len(files),
                             "recorded_usage": {key: sum(record["usage"].get(key, 0) for record in files)
                                                for key in ("prompt", "completion", "total")},
                             "recorded_request_seconds_sum": round(sum(record["elapsed_seconds"] or 0 for record in files), 2)}
    return inventory, records, statistics


def export_research(service, period_start, output, source_commit):
    """保留全部材料，而非仅导出通过 AI/LLM 筛选的节目。"""
    output = Path(output)
    if output.exists():
        raise FileExistsError(f"冻结目录已存在，拒绝覆盖：{output}；请用 --output 指定新目录")
    started_at = now_iso()
    scope = service.collect("month", period_start, BASELINE_INTERESTS)
    period = scope["period"]
    feeds, groups = service._groups()
    group_by_episode = {str(episode["_id"]): copies for copies in groups.values() for episode in copies}
    canonical = {str(episode["_id"]): episode for copies in groups.values() for episode in copies}
    source_by_episode = {source["episode_id"]: source for source in scope["corpus"]["sources"]}
    episodes, raw_episodes, sources, chunks = [], [], [], []
    raw_transcripts, canonical_by_copy = {}, {}
    for material in scope["materials"]:
        episode_id = material["episode_id"]
        episode = canonical[episode_id]
        feed = feeds[episode["feed_id"]]
        source_id = f"ep{episode_id}"
        source = source_by_episode.get(episode_id)
        copies = group_by_episode[episode_id]
        digest = _sha(source["full_text"]) if source else ""
        source_chunks = split_text(source["full_text"]) if source else []
        acquisition = source["acquisition"] if source else {}
        episodes.append({"source_id": source_id, "episode_id": episode_id, "feed_id": str(feed["_id"]),
                         "guid": episode.get("guid", ""), "title": material["title"], "feed": material["feed"],
                         "source_type": feed.get("type", "rss"), "published_at": _published(episode["published"]).isoformat(),
                         "body_available": source is not None, "char_count": source["char_count"] if source else 0,
                         "body_sha256": digest, "body_reference": f"sources.jsonl#{source_id}" if source else "",
                         "cached_screening_status": "no_body" if not source else "cached" if material["selected"] is not None else "missing",
                         "cached_selected": material["selected"], "cached_topics": material["topic_tags"],
                         "cached_reason": material["relevance_reason"], "cached_evidence": material["screening_evidence"],
                         "baseline_chunk_count": len(source_chunks), "duplicate_episode_ids": [str(copy["_id"]) for copy in copies],
                         "transcript_id": acquisition.get("transcript_id", ""), "transcript_episode_id": acquisition.get("transcript_episode_id", ""),
                         "transcript_source": acquisition.get("transcript_source", ""),
                         "borrowed_transcript": bool(source and acquisition["transcript_episode_id"] != episode_id)})
        for copy in copies:
            published = _published(copy["published"]).isoformat()
            if not period["start"] <= published[:10] < period["end"]:
                continue
            canonical_by_copy[str(copy["_id"])] = (source_id, episode_id)
        if source:
            transcript = service.db.transcripts.find_one({"_id": ObjectId(acquisition["transcript_id"])})
            raw_transcripts[str(transcript["_id"])] = transcript
            sources.append({**source, "source_id": source_id, "body_sha256": digest, "raw_text": transcript["text"],
                            "raw_text_sha256": _sha(transcript["text"]), "raw_segments": transcript.get("segments", []),
                            "duplicate_episode_ids": [str(copy["_id"]) for copy in copies]})
            chunks.extend({"source_id": source_id, "episode_id": episode_id, "body_sha256": digest,
                           "chunk_id": chunk["id"], "start": chunk["start"], "end": chunk["end"], "text": chunk["text"],
                           "text_sha256": _sha(chunk["text"])} for chunk in source_chunks)
    raw_episode_by_id = {}
    for episode in service.db.episodes.find({}):
        published = _published(episode.get("published"))
        if published is None or not period["start"] <= published.date().isoformat() < period["end"]:
            continue
        episode_id = str(episode["_id"])
        raw_episode_by_id[episode_id] = episode
        feed = feeds.get(episode.get("feed_id"))
        transcripts = list(service.db.transcripts.find({"episode_id": episode["_id"]}))
        for transcript in transcripts:
            raw_transcripts[str(transcript["_id"])] = transcript
        source_id, canonical_id = canonical_by_copy.get(episode_id, ("", ""))
        raw_episodes.append({"episode_id": episode_id, "canonical_source_id": source_id, "canonical_episode_id": canonical_id,
                             "feed_id": str(episode.get("feed_id", "")), "feed": feed.get("title", "") if feed else "",
                             "guid": episode.get("guid", ""), "title": episode.get("title", ""), "published_at": published.isoformat(),
                             "content_identity": list(_content_identity(episode, feed)) if feed else [], "is_canonical": episode_id == canonical_id,
                             "has_own_body": any((item.get("text") or "").strip() for item in transcripts),
                             "orphaned_feed": feed is None, "in_product_corpus": bool(source_id),
                             "description": episode.get("description", ""), "duration": episode.get("duration", 0),
                             "original_url": episode.get("link", ""), "audio_url": episode.get("audio_url", "")})
    raw_episodes.sort(key=lambda item: item["published_at"], reverse=True)
    sources_by_transcript = {}
    for source in sources:
        sources_by_transcript.setdefault(source["acquisition"]["transcript_id"], []).append(source["id"])
    transcript_records = [{"transcript_id": str(item["_id"]), "episode_id": str(item["episode_id"]),
                           "text": item.get("text", ""), "segments": item.get("segments", []),
                           "text_sha256": _sha(item.get("text", "")),
                           "episode_in_period": str(item["episode_id"]) in raw_episode_by_id,
                           "orphaned_feed": str(item["episode_id"]) in raw_episode_by_id and raw_episode_by_id[str(item["episode_id"])].get("feed_id") not in feeds,
                           "used_by_source_ids": sources_by_transcript.get(str(item["_id"]), []),
                           **{key: item.get(key) for key in ("source", "language", "model", "created_at", "word_count")}}
                          for item in raw_transcripts.values()]
    inventory, cache_records, cache_statistics = _cache_snapshot(service, sources)
    output.mkdir(parents=True, exist_ok=False)
    tables = {"episodes.csv": (EPISODE_FIELDS, episodes), "raw_episodes.csv": (RAW_EPISODE_FIELDS, raw_episodes),
              "cache_inventory.csv": (CACHE_FIELDS, inventory)}
    documents = {"sources.jsonl": sources, "raw_transcripts.jsonl": transcript_records,
                 "baseline_chunks.jsonl": chunks, "cached_records.jsonl": cache_records}
    files = {}
    for name, (fields, rows) in tables.items():
        _write_csv(output / name, fields, rows)
        files[name] = _file_info(output / name, len(rows), fields)
    for name, rows in documents.items():
        _write_jsonl(output / name, rows)
        files[name] = _file_info(output / name, len(rows), list(rows[0]) if rows else [])
    selected_ids = {item["source_id"] for item in episodes if item["cached_selected"] is True}
    manifest = {
        "schema_version": 1, "export_started_at": started_at, "export_completed_at": now_iso(), "source_commit": source_commit,
        "period": {key: period[key] for key in ("type", "start", "end", "timezone")},
        "owner_id": service.owner_id, "baseline_interests": BASELINE_INTERESTS,
        "baseline_selection_key": scope["selection_key"], "applies_interest_filter_to_export": False,
        "counts": {"episodes": len(episodes), "raw_episode_rows": len(raw_episodes), "sources_with_body": len(sources),
                   "episodes_without_body": len(episodes) - len(sources), "raw_transcripts": len(transcript_records),
                   "orphaned_feed_episodes": sum(item["orphaned_feed"] for item in raw_episodes),
                   "orphaned_feed_transcripts_with_body": sum(item["orphaned_feed"] and bool(item["text"].strip()) for item in transcript_records),
                   "body_characters": sum(source["char_count"] for source in sources), "baseline_chunks": len(chunks),
                   "cached_selected_sources": len(selected_ids),
                   "cached_non_selected_sources": sum(item["cached_selected"] is False for item in episodes),
                   "screening_missing_sources": sum(item["cached_screening_status"] == "missing" for item in episodes),
                   "cached_selected_characters": sum(source["char_count"] for source in sources if source["id"] in selected_ids),
                   "cached_selected_chunks": sum(chunk["source_id"] in selected_ids for chunk in chunks)},
        "deduplication": "复用 BriefingScopeService.collect：视频全局编号去重；RSS 按规范化订阅 URL + guid 去重。月份内优先有正文、当前账号、较新副本；相同内容身份可借用其他副本转录，保留 acquisition 与副本 ID。现有服务共享订阅库，不仅查询 owner 的 feed。",
        "raw_collection": "raw_episodes.csv 按月份导出数据库全部原始节目，含已删除订阅的 orphaned_feed 条目；对应现有完整转录全部写入 raw_transcripts.jsonl，并标明是否属于主 sources。孤立节目不计入产品月报和主 corpus，可在实验中另行纳入。",
        "text_contract": {"full_text": "现有服务的 transcript.text.strip()，不修正 ASR、标点、字幕噪音。",
                          "raw_text": "transcript.text 原样；原始 segments 完整保留在 raw_segments 和 raw_transcripts.jsonl。",
                          "offsets": "baseline_chunks start/end 为 canonical full_text 的 Python Unicode 字符索引，左闭右开，不是 UTF-8 字节或 UTF-16 JS 索引。",
                          "normalized_segments": "sources.segments 是服务保留的 start/end/text/speaker；原始字段看 raw_segments。",
                          "no_body": "无正文只保留清单和已有原始转录，不伪造正文，不抓取、不转录。"},
        "baseline_chunking": {"implementation": "backend/app/services/briefing_lab_service.py:split_text", "limit_characters": CHUNK_SIZE,
                              "boundary": "达到上限前，从块后半段寻找最后一个 ASCII 空格；找到就在那里结束，否则硬切。无重叠、无语义或说话人识别。",
                              "purpose": "仅记录生产基线，可测试整篇、按段落、按时间或语义等其他策略。"},
        "cache_statistics": cache_statistics,
        "cache_limitations": "已有缓存来自不同运行，读取期间生产任务可能继续写入；缺失不代表从未调用。累计 token/耗时仅为保存且去重的分块记录，不是完整成本账；elapsed sum 不是并行墙钟时间。结果级 usage 不再与块级相加。原失败返回缺失不能据此推断失败原因。",
        "snapshot_limitations": "只读逐次采集，不是数据库事务快照；这些导出文件完成后冻结。运行不读取设置、密钥、密码或 token，不调用 create_app 或任何 LLM。",
        "files": files,
    }
    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--owner-id", required=True, help="只用于现有偏好/筛选缓存归属，数据遵循共享订阅库语义")
    parser.add_argument("--period-start", default="2026-09-01")
    parser.add_argument("--output", type=Path, help="默认 docs/ai/data/YYYY-MM；目录存在则拒绝覆盖")
    args = parser.parse_args()
    if not ObjectId.is_valid(args.owner_id):
        parser.error("--owner-id 必须是有效的 MongoDB ObjectId")
    period = calendar_period("month", args.period_start)
    output = args.output or REPOSITORY / "docs" / "ai" / "data" / period["start"][:7]
    if output.exists():
        parser.error(f"冻结目录已存在：{output}；请用 --output 指定新目录")
    load_dotenv(BACKEND / ".env")
    commit = subprocess.run(["git", "rev-parse", "HEAD"], cwd=REPOSITORY, check=True, capture_output=True, text=True).stdout.strip()
    with MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"), serverSelectionTimeoutMS=5000) as client:
        db = client[os.getenv("MONGO_DB", "podcast")]
        if db.users.find_one({"_id": ObjectId(args.owner_id)}, {"_id": 1}) is None:
            parser.error("指定账号不存在")
        service = BriefingScopeService(db, BriefingReportService(owner_id=args.owner_id), args.owner_id)
        manifest = export_research(service, period["start"], output, commit)
    print(_json({"output": str(output.resolve()), "counts": manifest["counts"], "cache_statistics": manifest["cache_statistics"]}))


if __name__ == "__main__":
    main()
