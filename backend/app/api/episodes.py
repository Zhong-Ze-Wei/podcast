# -*- coding: utf-8 -*-
"""
Episodes API

单集管理接口
"""
from flask import Blueprint, request
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime

from ..models.episode import Episode
from ..models.feed import Feed
from ..services.task_queue import task_queue
from .utils import (
    success_response,
    error_response,
    paginated_response,
    get_pagination_params,
    get_bool_param
)

episodes_bp = Blueprint("episodes", __name__)


def get_db():
    from .. import get_db as _get_db
    return _get_db()


@episodes_bp.route("", methods=["GET"])
def list_episodes():
    """获取单集列表 (全局)"""
    db = get_db()
    page, per_page = get_pagination_params()

    # 构建查询条件
    query = {}

    status = request.args.get("status")
    if status:
        query["status"] = status

    is_read = get_bool_param("is_read")
    if is_read is not None:
        query["is_read"] = is_read

    is_starred = get_bool_param("is_starred")
    if is_starred is not None:
        query["is_starred"] = is_starred

    feed_id = request.args.get("feed_id")
    if feed_id:
        try:
            query["feed_id"] = ObjectId(feed_id)
        except InvalidId:
            pass

    # 查询
    total = db.episodes.count_documents(query)
    skip = (page - 1) * per_page

    episodes = list(
        db.episodes.find(query)
        .sort("published", -1)
        .skip(skip)
        .limit(per_page)
    )

    # 获取feed标题映射
    feed_ids = list(set(ep.get("feed_id") for ep in episodes if ep.get("feed_id")))
    feeds = {f["_id"]: f for f in db.feeds.find({"_id": {"$in": feed_ids}})}

    # 添加feed_title
    for ep in episodes:
        feed = feeds.get(ep.get("feed_id"))
        ep["feed_title"] = feed.get("title", "") if feed else ""

    data = [Episode.to_response(ep, include_feed_title=True) for ep in episodes]

    return paginated_response(data, page, per_page, total)


@episodes_bp.route("/<episode_id>", methods=["GET"])
def get_episode(episode_id):
    """获取单集详情"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    # 获取feed标题
    feed = db.feeds.find_one({"_id": episode.get("feed_id")})
    episode["feed_title"] = feed.get("title", "") if feed else ""

    return success_response(Episode.to_response(episode, include_feed_title=True))


@episodes_bp.route("/<episode_id>", methods=["PUT"])
def update_episode(episode_id):
    """更新单集"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    data = request.get_json() or {}

    # 允许更新的字段
    update_fields = {}
    allowed_fields = ["is_read", "is_starred", "play_position"]

    for field in allowed_fields:
        if field in data:
            update_fields[field] = data[field]

    if update_fields:
        update_fields["updated_at"] = datetime.utcnow()
        db.episodes.update_one({"_id": oid}, {"$set": update_fields})

        # 如果更新了is_read，同步更新feed的未读计数
        if "is_read" in update_fields:
            feed_id = episode.get("feed_id")
            if feed_id:
                unread_count = db.episodes.count_documents({
                    "feed_id": feed_id,
                    "is_read": False
                })
                db.feeds.update_one(
                    {"_id": feed_id},
                    {"$set": {"unread_count": unread_count}}
                )

    # 返回更新后的episode
    updated = db.episodes.find_one({"_id": oid})
    feed = db.feeds.find_one({"_id": updated.get("feed_id")})
    updated["feed_title"] = feed.get("title", "") if feed else ""

    return success_response(Episode.to_response(updated, include_feed_title=True))


@episodes_bp.route("/<episode_id>/star", methods=["POST"])
def star_episode(episode_id):
    """标星/取消标星"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    data = request.get_json() or {}
    starred = data.get("starred", not episode.get("is_starred", False))

    db.episodes.update_one(
        {"_id": oid},
        {"$set": {"is_starred": starred, "updated_at": datetime.utcnow()}}
    )

    return success_response({"id": episode_id, "is_starred": starred})


@episodes_bp.route("/<episode_id>/read", methods=["POST"])
def mark_read(episode_id):
    """标记已读/未读"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    data = request.get_json() or {}
    is_read = data.get("is_read", not episode.get("is_read", False))

    db.episodes.update_one(
        {"_id": oid},
        {"$set": {"is_read": is_read, "updated_at": datetime.utcnow()}}
    )

    # 更新feed未读计数
    feed_id = episode.get("feed_id")
    if feed_id:
        unread_count = db.episodes.count_documents({
            "feed_id": feed_id,
            "is_read": False
        })
        db.feeds.update_one(
            {"_id": feed_id},
            {"$set": {"unread_count": unread_count}}
        )

    return success_response({"id": episode_id, "is_read": is_read})


@episodes_bp.route("/<episode_id>/download", methods=["POST"])
def download_episode(episode_id):
    """下载单集音频 (异步)"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    # 检查是否可以下载
    episode_status = episode.get("status", "new")
    if not Episode.can_download(episode_status):
        # 如果已经下载过，返回更友好的提示
        if episode_status in [Episode.STATUS_DOWNLOADED, Episode.STATUS_TRANSCRIBED,
                              Episode.STATUS_TRANSCRIBING, Episode.STATUS_SUMMARIZED,
                              Episode.STATUS_SUMMARIZING]:
            return error_response(
                "Episode already downloaded",
                "ALREADY_DOWNLOADED",
                400
            )
        elif episode_status == Episode.STATUS_DOWNLOADING:
            return error_response(
                "Episode is currently downloading",
                "ALREADY_DOWNLOADING",
                400
            )
        else:
            return error_response(
                "Episode cannot be downloaded in current state",
                "INVALID_STATE",
                400
            )

    # 检查是否有进行中的任务
    existing_task = db.tasks.find_one({
        "episode_id": str(oid),
        "task_type": "download",
        "status": {"$in": ["pending", "processing"]}
    })
    if existing_task:
        return error_response(
            "Download task already in progress",
            "TASK_IN_PROGRESS",
            409
        )

    # 提交下载任务
    def do_download(progress_callback=None):
        return _download_episode_sync(str(oid), progress_callback)

    task_id = task_queue.submit(
        task_type="download",
        func=do_download,
        episode_id=str(oid)
    )

    # 更新状态为下载中
    db.episodes.update_one(
        {"_id": oid},
        {"$set": {"status": Episode.STATUS_DOWNLOADING}}
    )

    return success_response({
        "task_id": task_id,
        "status": "queued"
    })


def _download_episode_sync(episode_id: str, progress_callback=None):
    """同步执行下载"""
    import os
    import requests
    from ..config import Config

    db = get_db()
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
    save_dir = os.path.join(Config.MEDIA_ROOT, "audio", feed_id)
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
    response = requests.get(audio_url, stream=True, timeout=300)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))
    downloaded = 0

    with open(filepath, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0 and progress_callback:
                    progress = 10 + int(80 * downloaded / total_size)
                    progress_callback(min(progress, 90))

    if progress_callback:
        progress_callback(95)

    # 更新episode状态
    relative_path = os.path.join("audio", feed_id, filename)
    db.episodes.update_one(
        {"_id": oid},
        {"$set": {
            "status": Episode.STATUS_DOWNLOADED,
            "local_path": relative_path,
            "updated_at": datetime.utcnow()
        }}
    )

    if progress_callback:
        progress_callback(100)

    return {"local_path": relative_path}
