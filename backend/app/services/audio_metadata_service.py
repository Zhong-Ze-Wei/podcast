"""Reconcile indexed audio availability with the persisted media directory."""
from .audio_storage import local_audio_path


def reconcile_local_audio(db, media_root, dry_run=True):
    report = {"scanned": 0, "changed": 0, "updated": 0, "available": 0, "missing": 0, "dry_run": dry_run}
    fields = {"local_path": 1, "audio_path": 1, "has_local_audio": 1, "updated_at": 1}
    for episode in db.episodes.find({}, fields):
        report["scanned"] += 1
        available = local_audio_path(episode, media_root) is not None
        report["available"] += int(available)
        report["missing"] += int(bool(episode.get("local_path") or episode.get("audio_path")) and not available)
        if episode.get("has_local_audio") == available:
            continue
        report["changed"] += 1
        if dry_run:
            continue
        # Do not overwrite a download that changed the record during the scan.
        original = {"_id": episode["_id"], **{field: episode.get(field) for field in fields}}
        result = db.episodes.update_one(original, {"$set": {"has_local_audio": available}})
        report["updated"] += result.modified_count
    return report
