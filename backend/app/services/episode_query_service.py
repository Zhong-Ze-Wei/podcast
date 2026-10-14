"""Episode queries and read models shared by library, workspace and feed views."""
import os
import re
from datetime import datetime, timedelta, timezone
from importlib.util import find_spec
from urllib.parse import quote
from ..models.episode import Episode
from .audio_storage import local_audio_path
from .user_episode_state import user_filter_condition, get_states, apply_to_response


SORTS = {
    "published_desc": [("published", -1), ("_id", -1)],
    "published_asc": [("published", 1), ("_id", 1)],
    "title_asc": [("title", 1), ("_id", 1)],
}
ACTIVE_STATUSES = ["pending", "processing"]


def _bool_filter(params, name):
    value = params.get(name)
    if value is None:
        return None
    value = str(value).lower()
    if value in {"true", "1", "yes"}:
        return True
    if value in {"false", "0", "no"}:
        return False
    raise ValueError(f"Invalid boolean filter: {name}")


def _audio_filter(value):
    if value:
        return {"$or": [
            {"has_local_audio": True},
            {"has_local_audio": {"$exists": False}, "local_path": {"$exists": True, "$nin": [None, ""]}},
            {"has_local_audio": {"$exists": False}, "audio_path": {"$exists": True, "$nin": [None, ""]}},
        ]}
    return {"$or": [
        {"has_local_audio": False},
        {"has_local_audio": {"$exists": False}, "local_path": {"$in": [None, ""]}, "audio_path": {"$in": [None, ""]}},
    ]}


class EpisodeQueryService:
    def __init__(self, db, media_root, cloud_enabled=False, ai_enabled=False, can_process=True):
        self.db = db
        self.media_root = media_root
        self.cloud_enabled = cloud_enabled
        self.ai_enabled = ai_enabled
        self.can_process = can_process
        # 浏览页面只检查组件是否安装；提交转录时再验证实际运行环境。
        self.local_providers = {
            "local_whisper": find_spec("faster_whisper") is not None,
            "local_whisperx": find_spec("whisperx") is not None,
        }

    def list(self, user_id, params, page, per_page, feed_id=None):
        sort_name = params.get("sort", "published_desc")
        if sort_name not in SORTS:
            raise ValueError("Unsupported episode sort")
        conditions = []
        if feed_id is not None:
            conditions.append({"feed_id": feed_id})
        days = params.get("days")
        if days is not None:
            try:
                days = int(days)
            except (TypeError, ValueError):
                raise ValueError("days must be an integer between 1 and 3650")
            if not 1 <= days <= 3650:
                raise ValueError("days must be an integer between 1 and 3650")
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            conditions.append({"published": {"$gte": now - timedelta(days=days), "$lte": now}})
        status = params.get("status")
        statuses = [value.strip() for value in status.split(",") if value.strip()] if status else []
        if statuses:
            conditions.append({"status": {"$in": statuses}})
        states = user_filter_condition(self.db, user_id, _bool_filter(params, "is_read"), _bool_filter(params, "is_starred"))
        if states:
            conditions.append(states)
        for name in ("has_transcript", "has_summary"):
            value = _bool_filter(params, name)
            if value is not None:
                conditions.append({name: True if value else {"$ne": True}})
        has_text = _bool_filter(params, "has_transcript_or_summary")
        if has_text is True:
            conditions.append({"$or": [{"has_transcript": True}, {"has_summary": True}]})
        elif has_text is False:
            conditions.extend([{"has_transcript": {"$ne": True}}, {"has_summary": {"$ne": True}}])
        audio = _bool_filter(params, "has_local_audio")
        if audio is not None:
            conditions.append(_audio_filter(audio))
        processed = _bool_filter(params, "processed")
        if processed is True:
            conditions.append({"$or": [_audio_filter(True), {"has_transcript": True}, {"has_summary": True}]})
        elif processed is False:
            conditions.extend([_audio_filter(False), {"has_transcript": {"$ne": True}}, {"has_summary": {"$ne": True}}])
        text = params.get("q", "").strip()
        if text:
            conditions.append({"$or": [{field: {"$regex": re.escape(text), "$options": "i"}} for field in ("title", "summary", "description")]})
        query = {"$and": conditions} if conditions else {}
        total = self.db.episodes.count_documents(query)
        documents = list(self.db.episodes.find(query, {"content": 0}).sort(SORTS[sort_name]).skip((page - 1) * per_page).limit(per_page))
        return self.responses(documents, user_id, lightweight=True), total

    def responses(self, documents, user_id, lightweight=False):
        ids = [doc["_id"] for doc in documents]
        states = get_states(self.db, user_id, ids)
        feeds = {doc["_id"]: doc for doc in self.db.feeds.find({"_id": {"$in": list({doc["feed_id"] for doc in documents if doc.get("feed_id")})}}, {"title": 1})}
        tasks = {}
        for task in self.db.tasks.find({"episode_id": {"$in": [str(value) for value in ids]}, "status": {"$in": ACTIVE_STATUSES}, "task_type": {"$in": ["download", "transcribe", "summarize", "translate"]}}, {"task_id": 1, "episode_id": 1, "task_type": 1, "status": 1, "progress": 1, "progress_message": 1}):
            tasks.setdefault(task["episode_id"], []).append({key: task.get(key) for key in ("task_id", "task_type", "status", "progress", "progress_message")})
        result = []
        for doc in documents:
            feed = feeds.get(doc.get("feed_id"))
            if feed:
                doc["feed_title"] = feed.get("title", "")
            response = apply_to_response(Episode.to_response(doc, include_feed_title=True), states.get(doc["_id"]))
            path = local_audio_path(doc, self.media_root)
            artifacts = {"local_audio": path is not None, "transcript": bool(doc.get("has_transcript")), "summary": bool(doc.get("has_summary"))}
            if path:
                relative_path = os.path.relpath(path, self.media_root)
                response["local_audio_url"] = "/api/media/" + "/".join(quote(part) for part in relative_path.split(os.sep))
            else:
                response["local_audio_url"] = None
            active = tasks.get(str(doc["_id"]), [])
            providers = self._providers(doc, artifacts["local_audio"])
            response.update(artifacts=artifacts, active_tasks=active, actions=self._actions(doc, artifacts, active, providers), transcription_providers=providers)
            if lightweight:
                response.pop("content", None)
            result.append(response)
        return result

    def _providers(self, episode, has_audio):
        downloadable = bool(episode.get("audio_url") or episode.get("guid", "").startswith(("youtube:", "bilibili:")))
        providers = []
        for provider in ("official", "local_whisper", "local_whisperx", "assemblyai"):
            reason = None
            if provider == "official" and not episode.get("transcript_url"):
                reason = "NO_TRANSCRIPT_URL"
            elif provider in self.local_providers:
                if not self.local_providers[provider]:
                    reason = "LOCAL_AI_NOT_INSTALLED"
                elif not has_audio and not downloadable:
                    reason = "NO_AUDIO_URL"
            elif provider == "assemblyai":
                if not self.cloud_enabled:
                    reason = "CLOUD_TRANSCRIPTION_DISABLED"
                elif not episode.get("audio_url"):
                    reason = "NO_AUDIO_URL"
            if not self.can_process:
                reason = "ROLE_DENIED"
            providers.append({"id": provider, "available": reason is None, "reason_code": reason, "download_required": provider in self.local_providers and reason is None and not has_audio})
        return providers

    def _actions(self, episode, artifacts, tasks, providers):
        if not self.can_process:
            return {name: {"allowed": False, "reason_code": "ROLE_DENIED"} for name in ("download", "transcribe", "summarize")}
        busy = bool(tasks) or episode.get("status") in Episode.PROCESSING_STATUSES
        downloadable = bool(episode.get("audio_url") or episode.get("guid", "").startswith(("youtube:", "bilibili:")))
        download_reason = None
        if artifacts["local_audio"]:
            download_reason = "ALREADY_DOWNLOADED"
        elif busy:
            download_reason = "TASK_IN_PROGRESS"
        elif not downloadable:
            download_reason = "NO_AUDIO_URL"
        transcribe_reason = None
        if artifacts["transcript"]:
            transcribe_reason = "ALREADY_TRANSCRIBED"
        elif busy:
            transcribe_reason = "TASK_IN_PROGRESS"
        elif not any(provider["available"] for provider in providers):
            transcribe_reason = "NO_TRANSCRIPTION_PROVIDER"
        summary_reason = None
        if busy:
            summary_reason = "TASK_IN_PROGRESS"
        elif not self.ai_enabled:
            summary_reason = "AI_ANALYSIS_DISABLED"
        elif not artifacts["transcript"]:
            summary_reason = "TRANSCRIPT_NOT_FOUND"
        return {name: {"allowed": reason is None, "reason_code": reason} for name, reason in (("download", download_reason), ("transcribe", transcribe_reason), ("summarize", summary_reason))}
