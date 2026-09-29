# -*- coding: utf-8 -*-
"""
Episodes API

单集管理接口
"""

import os

import requests

from flask import Blueprint, request, current_app, redirect
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime

from ..models.episode import Episode
from ..models.feed import Feed
from ..services.task_queue import task_queue
from ..services.user_episode_state import (
    apply_to_response,
    get_states,
    upsert,
    user_filter_condition,
)
from ..services.youtube_service import YouTubeService
from .utils import (
    success_response,
    error_response,
    paginated_response,
    get_pagination_params,
    get_bool_param,
)
from .decorators import require_role, current_owner_id, current_user, owner_filter, require_auth

episodes_bp = Blueprint("episodes", __name__)


def get_db():
    from .. import get_db as _get_db

    return _get_db()


def _local_audio_file_exists(episode):
    local_path = episode.get("local_path") or episode.get("audio_path")
    if not local_path:
        return False

    media_root = os.path.abspath(current_app.config.get("MEDIA_ROOT", "."))
    candidate = local_path if os.path.isabs(local_path) else os.path.join(media_root, local_path)
    candidate = os.path.abspath(candidate)

    try:
        if os.path.commonpath([media_root, candidate]) != media_root:
            return False
    except ValueError:
        return False

    return os.path.isfile(candidate)


@episodes_bp.route("", methods=["GET"])
@require_auth
def list_episodes():
    """获取单集列表 (全局)"""
    db = get_db()
    page, per_page = get_pagination_params()

    # 构建查询条件
    query = owner_filter()

    # 支持多个状态值 (用逗号分隔: status=transcribing,transcribed)
    status = request.args.get("status")
    if status:
        status_query = _episode_status_query(status)
        if status_query is not None:
            query["status"] = status_query

    # 已读/加星是用户个人状态（存 user_episode_states），转为 _id 条件过滤
    user = current_user()
    state_condition = user_filter_condition(
        db,
        user["id"],
        is_read=get_bool_param("is_read"),
        is_starred=get_bool_param("is_starred"),
    )
    if state_condition:
        query.update(state_condition)

    feed_id = request.args.get("feed_id")
    if feed_id:
        try:
            query["feed_id"] = ObjectId(feed_id)
        except InvalidId:
            pass

    # 转录/摘要筛选
    has_transcript = get_bool_param("has_transcript")
    if has_transcript is not None:
        query["has_transcript"] = has_transcript

    has_summary = get_bool_param("has_summary")
    if has_summary is not None:
        query["has_summary"] = has_summary

    # 查询
    total = db.episodes.count_documents(query)
    skip = (page - 1) * per_page

    episodes = list(
        db.episodes.find(query).sort("published", -1).skip(skip).limit(per_page)
    )

    # 获取feed标题映射
    feed_ids = list(set(ep.get("feed_id") for ep in episodes if ep.get("feed_id")))
    feeds = {f["_id"]: f for f in db.feeds.find(owner_filter({"_id": {"$in": feed_ids}}))}

    # 添加feed_title
    for ep in episodes:
        feed = feeds.get(ep.get("feed_id"))
        ep["feed_title"] = feed.get("title", "") if feed else ""

    states = get_states(db, user["id"], [ep["_id"] for ep in episodes])
    data = [
        apply_to_response(Episode.to_response(ep, include_feed_title=True), states.get(ep["_id"]))
        for ep in episodes
    ]

    return paginated_response(data, page, per_page, total)


@episodes_bp.route("/<episode_id>", methods=["GET"])
@require_auth
def get_episode(episode_id):
    """获取单集详情"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one(owner_filter({"_id": oid}))
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    # 获取feed标题
    feed = db.feeds.find_one(owner_filter({"_id": episode.get("feed_id")}))
    episode["feed_title"] = feed.get("title", "") if feed else ""

    user_id = current_user()["id"]
    state = get_states(db, user_id, [oid]).get(oid)
    return success_response(apply_to_response(Episode.to_response(episode, include_feed_title=True), state))


@episodes_bp.route("/<episode_id>", methods=["PUT"])
@require_role("user", "admin")
def update_episode(episode_id):
    """更新单集（个人状态：已读/加星/播放进度，按用户隔离）"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one(owner_filter({"_id": oid}))
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    data = request.get_json() or {}

    # 个人状态只写 user_episode_states，不再动剧集文档
    user_id = current_user()["id"]
    upsert(db, user_id, oid, data)

    updated = db.episodes.find_one(owner_filter({"_id": oid}))
    feed = db.feeds.find_one(owner_filter({"_id": updated.get("feed_id")}))
    updated["feed_title"] = feed.get("title", "") if feed else ""

    state = get_states(db, user_id, [oid]).get(oid)
    return success_response(apply_to_response(Episode.to_response(updated, include_feed_title=True), state))


@episodes_bp.route("/<episode_id>/star", methods=["POST"])
@require_role("user", "admin")
def star_episode(episode_id):
    """标星/取消标星（按用户隔离）"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one(owner_filter({"_id": oid}))
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    data = request.get_json() or {}
    user_id = current_user()["id"]
    current_state = get_states(db, user_id, [oid]).get(oid) or {}
    starred = data.get("starred", not current_state.get("is_starred", False))

    upsert(db, user_id, oid, {"is_starred": starred})

    return success_response({"id": episode_id, "is_starred": starred})


@episodes_bp.route("/<episode_id>/read", methods=["POST"])
@require_role("user", "admin")
def mark_read(episode_id):
    """标记已读/未读（按用户隔离）"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one(owner_filter({"_id": oid}))
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    data = request.get_json() or {}
    user_id = current_user()["id"]
    current_state = get_states(db, user_id, [oid]).get(oid) or {}
    is_read = data.get("is_read", not current_state.get("is_read", False))

    upsert(db, user_id, oid, {"is_read": is_read})

    return success_response({"id": episode_id, "is_read": is_read})


def _proxy_stream(url, use_proxy=False):
    """转发上游音频流给浏览器，透传 Range 请求头实现进度拖动"""
    headers = {}
    if request.headers.get("Range"):
        headers["Range"] = request.headers["Range"]
    proxies = None
    if use_proxy:
        proxy = YouTubeService._proxy()
        if proxy:
            proxies = {"http": proxy, "https": proxy}

    upstream = requests.get(url, headers=headers, proxies=proxies, stream=True, timeout=20)

    passthrough = {}
    for name in ("Content-Type", "Content-Length", "Content-Range", "Accept-Ranges"):
        if upstream.headers.get(name):
            passthrough[name] = upstream.headers[name]

    def generate():
        try:
            for chunk in upstream.iter_content(chunk_size=64 * 1024):
                yield chunk
        finally:
            upstream.close()

    return current_app.response_class(
        generate(), status=upstream.status_code, headers=passthrough
    )


@episodes_bp.route("/<episode_id>/stream", methods=["GET"])
def stream_episode_audio(episode_id):
    """音频流：供 <audio> 标签直接播放（标签带不了 Authorization 头，令牌从 query 取）。
    YouTube 剧集实时解析音频直链后代理转发，不落盘；RSS 剧集 302 到原地址。"""
    from ..services.jwt_auth import verify_token

    token = request.args.get("token", "")
    payload = verify_token(token, current_app.config.get("JWT_SECRET", ""))
    if not payload:
        return error_response("Authentication required", "AUTH_REQUIRED", 401)

    db = get_db()
    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one(owner_filter({"_id": oid}))
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    audio_type = episode.get("audio_type") or ""
    if audio_type.startswith("video/youtube"):
        guid = episode.get("guid") or ""
        video_id = guid.split(":", 1)[1] if guid.startswith("youtube:") else ""
        if not video_id:
            return error_response("Episode has no YouTube video id", "NO_VIDEO_ID", 404)
        stream_url, error = YouTubeService.resolve_stream_url(video_id)
        if error:
            return error_response(error, "STREAM_RESOLVE_FAILED", 502)
        return _proxy_stream(stream_url, use_proxy=True)

    if episode.get("audio_url"):
        return redirect(episode["audio_url"])

    return error_response("No playable audio for this episode", "NO_AUDIO", 404)


@episodes_bp.route("/<episode_id>/download", methods=["POST"])
@require_auth
def download_episode(episode_id):
    """下载单集音频 (异步)"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one(owner_filter({"_id": oid}))
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    # 检查是否可以下载
    episode_status = episode.get("status", "new")
    can_redownload_missing_file = (
        episode_status in [
            Episode.STATUS_DOWNLOADED,
            Episode.STATUS_TRANSCRIBED,
            Episode.STATUS_SUMMARIZED,
        ]
        and not _local_audio_file_exists(episode)
    )
    if not Episode.can_download(episode_status) and not can_redownload_missing_file:
        # 如果已经下载过，返回更友好的提示
        if episode_status in [
            Episode.STATUS_DOWNLOADED,
            Episode.STATUS_TRANSCRIBED,
            Episode.STATUS_TRANSCRIBING,
            Episode.STATUS_SUMMARIZED,
            Episode.STATUS_SUMMARIZING,
        ]:
            return error_response(
                "Episode already downloaded", "ALREADY_DOWNLOADED", 400
            )
        elif episode_status == Episode.STATUS_DOWNLOADING:
            return error_response(
                "Episode is currently downloading", "ALREADY_DOWNLOADING", 400
            )
        else:
            return error_response(
                "Episode cannot be downloaded in current state", "INVALID_STATE", 400
            )

    # 检查是否有进行中的任务
    existing_task = db.tasks.find_one(
        {
            "episode_id": str(oid),
            "owner_id": current_owner_id(),
            "task_type": "download",
            "status": {"$in": ["pending", "processing"]},
        }
    )
    if existing_task:
        return error_response(
            "Download task already in progress", "TASK_IN_PROGRESS", 409
        )

    # 提交下载任务
    def do_download(progress_callback=None):
        return _download_episode_sync(str(oid), progress_callback)

    task_id = task_queue.submit(
        task_type="download", func=do_download, episode_id=str(oid), owner_id=current_owner_id()
    )

    # 更新状态为下载中
    db.episodes.update_one(
        owner_filter({"_id": oid}), {"$set": {"status": Episode.STATUS_DOWNLOADING}}
    )

    return success_response({"task_id": task_id, "status": "queued"})


def _download_episode_sync(episode_id: str, progress_callback=None):
    """同步执行下载"""
    import os
    import requests
    from ..config import Config

    # 限制最大下载文件大小 (500MB)
    MAX_FILE_SIZE = 500 * 1024 * 1024

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
    # 部分 CDN（如 Acast sphinx）会拒绝 python-requests 默认 User-Agent，
    # 需要模拟标准播客客户端
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (compatible; PodcastManager/1.0; "
            "+https://github.com/podcast-manager)"
        )
    }
    response = requests.get(audio_url, stream=True, timeout=300, headers=headers)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))

    # 检查文件大小限制
    if total_size > MAX_FILE_SIZE:
        raise ValueError(
            f"File too large: {total_size / 1024 / 1024:.1f}MB (max {MAX_FILE_SIZE / 1024 / 1024}MB)"
        )

    downloaded = 0

    with open(filepath, "wb") as f:
        for chunk in response.iter_content(chunk_size=8192):
            if chunk:
                f.write(chunk)
                downloaded += len(chunk)

                # 实时检查大小限制
                if downloaded > MAX_FILE_SIZE:
                    os.remove(filepath)
                    raise ValueError(
                        f"Download exceeded maximum size of {MAX_FILE_SIZE / 1024 / 1024}MB"
                    )

                if total_size > 0 and progress_callback:
                    progress = 10 + int(80 * downloaded / total_size)
                    progress_callback(min(progress, 90))

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
                "updated_at": datetime.utcnow(),
            }
        },
    )

    if progress_callback:
        progress_callback(100)

    return {"local_path": relative_path}


def _episode_status_query(status: str):
    statuses = [item.strip() for item in status.split(",") if item.strip()]
    if not statuses:
        return None
    if len(statuses) > 1:
        return {"$in": statuses}
    return statuses[0]
