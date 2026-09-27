# -*- coding: utf-8 -*-
"""
Video Import API

视频导入接口 — 目前支持 YouTube：URL → 字幕 → episode + transcript
"""
from datetime import datetime

from flask import Blueprint, request

from ..models.episode import Episode
from ..models.feed import Feed
from ..models.transcript import Transcript
from ..services.task_queue import task_queue
from ..services.youtube_service import YouTubeService
from .decorators import require_auth, current_owner_id
from .utils import success_response, error_response

video_import_bp = Blueprint("video_import", __name__)

YOUTUBE_IMPORT_FEED_RSS = "youtube:import"


def get_db():
    from .. import get_db as _get_db

    return _get_db()


@video_import_bp.route("/youtube", methods=["POST"])
@require_auth
def import_youtube():
    """导入 YouTube 视频（异步）：拉取元数据与字幕，生成 episode"""
    data = request.get_json() or {}
    url = (data.get("url") or "").strip()

    video_id = YouTubeService.extract_video_id(url)
    if not video_id:
        return error_response(
            "Invalid YouTube URL or video ID", "INVALID_YOUTUBE_URL", 400
        )

    owner_id = current_owner_id()

    def do_import(progress_callback=None):
        return _import_youtube_sync(video_id, owner_id, progress_callback)

    task_id = task_queue.submit(
        task_type="video_import", func=do_import, owner_id=owner_id
    )
    return success_response({"task_id": task_id, "video_id": video_id, "status": "queued"})


def _import_youtube_sync(video_id: str, owner_id, progress_callback=None):
    """同步执行 YouTube 导入：元数据 + 字幕 → feed + episode + transcript"""
    db = get_db()

    if progress_callback:
        progress_callback(10)

    metadata, error = YouTubeService.fetch_metadata(video_id)
    if error:
        raise ValueError(error)
    if progress_callback:
        progress_callback(40)

    existing = db.episodes.find_one({"owner_id": owner_id, "guid": f"youtube:{video_id}"})
    if existing:
        return {
            "episode_id": str(existing["_id"]),
            "video_id": video_id,
            "already_imported": True,
        }

    transcript, error = YouTubeService.fetch_transcript(video_id)
    if error:
        raise ValueError(error)
    if progress_callback:
        progress_callback(70)

    feed = db.feeds.find_one({"owner_id": owner_id, "rss_url": YOUTUBE_IMPORT_FEED_RSS})
    if not feed:
        feed_doc = Feed.create(
            rss_url=YOUTUBE_IMPORT_FEED_RSS,
            owner_id=owner_id,
            title="YouTube 导入",
            website="https://www.youtube.com",
            description="手动导入的 YouTube 视频",
        )
        feed_doc["last_checked"] = datetime.utcnow()
        feed_doc["episode_count"] = 0
        feed_doc["unread_count"] = 0
        result = db.feeds.insert_one(feed_doc)
        feed = {"_id": result.inserted_id}

    episode_doc = Episode.create(
        feed_id=feed["_id"],
        owner_id=owner_id,
        guid=f"youtube:{video_id}",
        title=metadata["title"],
        link=f"https://www.youtube.com/watch?v={video_id}",
        published=datetime.utcnow(),
        duration=metadata["duration"],
        image=metadata.get("thumbnail"),
        audio_type="video/youtube",
    )
    episode_doc["status"] = Episode.STATUS_TRANSCRIBED
    episode_doc["author"] = metadata.get("uploader")
    episode_result = db.episodes.insert_one(episode_doc)

    transcript_doc = Transcript.create(
        episode_id=episode_result.inserted_id,
        owner_id=owner_id,
        text=transcript["text"],
        segments=transcript["segments"],
        language=transcript["language"],
        source=Transcript.SOURCE_YOUTUBE,
        model="youtube-transcript-api",
    )
    db.transcripts.insert_one(transcript_doc)

    db.feeds.update_one(
        {"_id": feed["_id"]},
        {"$set": {"episode_count": db.episodes.count_documents({"feed_id": feed["_id"], "owner_id": owner_id})}},
    )
    if progress_callback:
        progress_callback(100)

    return {
        "episode_id": str(episode_result.inserted_id),
        "video_id": video_id,
        "title": metadata["title"],
        "already_imported": False,
    }
