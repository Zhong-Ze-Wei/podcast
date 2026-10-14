"""Read saved episode overviews for cards without running an AI model."""
import hashlib
from .briefing_lab_service import read_json


def saved_analysis_previews(report_root, sources, owner_id=None):
    by_hash = {}
    for source in sources:
        digest = hashlib.sha256(source["full_text"].encode()).hexdigest()
        by_hash.setdefault(digest, []).append(source["id"])
    if not by_hash:
        return {}
    latest = {}
    for path in (report_root / "episode-analysis").glob("*.json"):
        record = read_json(path)
        digest = record.get("identity", {}).get("text_hash")
        if digest not in by_hash:
            continue
        text = (record.get("takeaway") or "").strip()
        if not text:
            text = "；".join(point["meaning"].strip() for point in record.get("points", [])[:2] if point.get("meaning"))
        if text and record.get("generated_at", "") >= latest.get(digest, {}).get("generated_at", ""):
            latest[digest] = {"text": text, "generated_at": record.get("generated_at", "")}
    previews = {source_id: latest[digest]["text"] for digest, ids in by_hash.items() if digest in latest for source_id in ids}
    # 旧版单篇解读使用 S01 等编号；通过稳定的节目 ID 找回已保存的导读。
    episodes = {source["episode_id"]: source for source in sources}
    legacy = {}
    for path in report_root.glob("reading-v*/sources/*.json"):
        record = read_json(path)
        episode_id = record.get("source", {}).get("episode_id")
        if episode_id not in episodes or record.get("owner_id") not in (None, owner_id):
            continue
        text = (record.get("takeaway") or "").strip()
        if text and record.get("generated_at", "") >= legacy.get(episode_id, {}).get("generated_at", ""):
            legacy[episode_id] = {"text": text, "generated_at": record.get("generated_at", "")}
    for episode_id, record in legacy.items():
        previews.setdefault(episodes[episode_id]["id"], record["text"])
    return previews
