"""Reserve a shared episode before publishing a processing task."""
from contextlib import contextmanager
from datetime import datetime
from threading import RLock
from flask import current_app
from ..models.episode import Episode
from .audio_storage import local_audio_path

# One executor process shares this short lock for submission and final artifact edits.
_submission_lock = RLock()
OPERATIONS = {
    "download": (Episode.STATUS_DOWNLOADING, "last_download_error"),
    "transcribe": (Episode.STATUS_TRANSCRIBING, "last_transcript_error"),
    "summarize": (Episode.STATUS_SUMMARIZING, "last_summary_error"),
    "translate": (Episode.STATUS_SUMMARIZING, "last_summary_error"),
}


class ProcessingConflict(Exception):
    pass


class ProcessingSubmissionFailed(Exception):
    pass


class EpisodeProcessingService:
    def __init__(self, db, queue):
        self.db = db
        self.queue = queue

    def active_task_id(self, episode_id, task_type, dedup_key):
        with _submission_lock:
            active = self.db.tasks.find_one({
                "episode_id": str(episode_id),
                "task_type": {"$in": list(OPERATIONS)},
                "status": {"$in": ["pending", "processing"]},
            })
            if not active:
                return None
            if active.get("dedup_key") == dedup_key or (task_type == "download" and active.get("task_type") == "download"):
                return active["task_id"]
            raise ProcessingConflict("Episode is being processed")

    @contextmanager
    def edit_artifacts(self, episode_id):
        """Serialize only the final resource write, never remote fetching."""
        with _submission_lock:
            active = self.db.tasks.find_one({
                "episode_id": str(episode_id),
                "task_type": {"$in": list(OPERATIONS)},
                "status": {"$in": ["pending", "processing"]},
            })
            episode = self.db.episodes.find_one({"_id": episode_id})
            if not episode or active or episode.get("status") in Episode.PROCESSING_STATUSES:
                raise ProcessingConflict("Episode is being processed or changed before this operation")
            yield episode

    def submit(self, episode, task_type, dedup_key, func, owner_id, on_failure=None):
        with _submission_lock:
            existing = self.active_task_id(episode["_id"], task_type, dedup_key)
            if existing:
                return existing
            if episode.get("status") in Episode.PROCESSING_STATUSES:
                raise ProcessingConflict("Episode is being processed")
            processing_status, error_field = OPERATIONS[task_type]
            reserved_at = datetime.utcnow()
            original = {"_id": episode["_id"], "status": episode.get("status"), "updated_at": episode.get("updated_at")}
            reservation = self.db.episodes.update_one(original, {"$set": {
                "status": processing_status, error_field: None, "updated_at": reserved_at,
            }})
            if not reservation.matched_count:
                raise ProcessingConflict("Episode changed before submission; retry the operation")
            try:
                return self.queue.submit_unique(
                    task_type=task_type, func=func, dedup_key=dedup_key,
                    episode_id=str(episode["_id"]), owner_id=owner_id, on_failure=on_failure,
                )
            except Exception as error:
                self.restore_status(episode["_id"], task_type, error, reserved_at)
                raise ProcessingSubmissionFailed("Task could not be submitted; retry the operation") from error

    def restore_status(self, episode_id, task_type, error, reserved_at=None):
        episode = self.db.episodes.find_one({"_id": episode_id})
        if not episode:
            return
        processing_status, error_field = OPERATIONS[task_type]
        if episode.get("has_summary"):
            status = Episode.STATUS_SUMMARIZED
        elif episode.get("has_transcript"):
            status = Episode.STATUS_TRANSCRIBED
        elif local_audio_path(episode, current_app.config.get("MEDIA_ROOT", ".")):
            status = Episode.STATUS_DOWNLOADED
        else:
            status = Episode.STATUS_NEW
        query = {"_id": episode_id}
        if reserved_at is not None:
            query.update(status=processing_status, updated_at=reserved_at)
        self.db.episodes.update_one(query, {"$set": {
            "status": status, error_field: str(error) if error is not None else None, "updated_at": datetime.utcnow(),
        }})
