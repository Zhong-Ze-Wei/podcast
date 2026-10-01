"""Reusable audio downloads executed synchronously inside a backend task."""
import os
from datetime import datetime
from bson import ObjectId
from flask import current_app
from ..models.episode import Episode
from .audio_storage import local_audio_path
from .youtube_service import YouTubeService
from .bilibili_service import BilibiliService


class DownloadService:
    def __init__(self, db):
        self.db = db

    def restore_episode_status(self, episode_id, error):
        oid = ObjectId(episode_id)
        episode = self.db.episodes.find_one({"_id": oid})
        if not episode:
            return
        has_audio = local_audio_path(episode, current_app.config.get("MEDIA_ROOT", ".")) is not None
        if episode.get("has_summary"):
            status = Episode.STATUS_SUMMARIZED
        elif episode.get("has_transcript"):
            status = Episode.STATUS_TRANSCRIBED
        else:
            status = Episode.STATUS_DOWNLOADED if has_audio else Episode.STATUS_NEW
        self.db.episodes.update_one({"_id": oid}, {"$set": {
            "status": status, "has_local_audio": has_audio,
            "last_download_error": str(error), "updated_at": datetime.utcnow(),
        }})

    def download(self, episode_id, progress_callback=None):
        oid = ObjectId(episode_id)
        episode = self.db.episodes.find_one({"_id": oid})
        if not episode:
            raise ValueError("Episode not found")
        guid = episode.get("guid", "")
        if guid.startswith(("youtube:", "bilibili:")):
            source, video_id = guid.split(":", 1)
            service = YouTubeService if source == "youtube" else BilibiliService
            audio_path, error = service.download_audio(video_id)
            if error:
                raise ValueError(error)
            self.db.episodes.update_one({"_id": oid}, {"$set": {
                "local_path": audio_path, "has_local_audio": True,
                "status": Episode.STATUS_DOWNLOADED, "updated_at": datetime.utcnow(),
            }})
            return {"local_path": audio_path}
        return _download_episode_sync(self.db, episode_id, progress_callback)


def _download_episode_sync(db, episode_id: str, progress_callback=None):
    """同步执行下载"""
    import os
    import requests
    from ..config import Config

    # 限制最大下载文件大小 (500MB)
    MAX_FILE_SIZE = 500 * 1024 * 1024

    oid = ObjectId(episode_id)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        raise ValueError("Episode not found")

    audio_url = episode.get("audio_url")
    if not audio_url:
        raise ValueError("No audio URL")

    if progress_callback:
        progress_callback(10)

    # 创建保存目录
    feed_id = str(episode.get("feed_id"))
    save_dir = os.path.join(current_app.config.get("MEDIA_ROOT", Config.MEDIA_ROOT), "audio", feed_id)
    os.makedirs(save_dir, exist_ok=True)

    # 生成文件名
    ext = ".mp3"
    if "m4a" in audio_url.lower():
        ext = ".m4a"
    elif "wav" in audio_url.lower():
        ext = ".wav"
    elif "ogg" in audio_url.lower():
        ext = ".ogg"

    filename = f"{episode_id}{ext}"
    filepath = os.path.join(save_dir, filename)

    # 下载文件
    # 部分 CDN（如 Acast sphinx）会拒绝 python-requests 默认 User-Agent，
    # 需要模拟标准播客客户端
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; PodcastManager/1.0; "
            "+https://github.com/podcast-manager)"
        )
    }
    response = requests.get(audio_url, stream=True, timeout=300, headers=headers)
    partial_path = filepath + ".part"
    try:
        response.raise_for_status()
        total_size = int(response.headers.get("content-length", 0))
        if total_size > MAX_FILE_SIZE:
            raise ValueError(f"File too large: {total_size / 1024 / 1024:.1f}MB (max {MAX_FILE_SIZE / 1024 / 1024}MB)")
        downloaded = 0
        with open(partial_path, "wb") as audio_file:
            for chunk in response.iter_content(chunk_size=8192):
                if not chunk:
                    continue
                downloaded += len(chunk)
                if downloaded > MAX_FILE_SIZE:
                    raise ValueError(f"Download exceeded maximum size of {MAX_FILE_SIZE / 1024 / 1024}MB")
                audio_file.write(chunk)
                if total_size > 0 and progress_callback:
                    progress_callback(min(10 + int(80 * downloaded / total_size), 90))
        os.replace(partial_path, filepath)
    finally:
        response.close()
        if os.path.exists(partial_path):
            os.remove(partial_path)

    if progress_callback:
        progress_callback(95)

    # 更新episode状态
    relative_path = os.path.join("audio", feed_id, filename)
    db.episodes.update_one(
        {"_id": oid},
        {
            "$set": {
                "status": Episode.STATUS_DOWNLOADED,
                "local_path": relative_path,
                "has_local_audio": True,
                "updated_at": datetime.utcnow(),
            }
        },
    )

    if progress_callback:
        progress_callback(100)

    return {"local_path": relative_path}

