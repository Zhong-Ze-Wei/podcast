# -*- coding: utf-8 -*-
"""
Feeds API

订阅源管理接口
"""

import logging
from urllib.parse import unquote, urlparse

from flask import Blueprint, current_app, request


from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime

from ..models.feed import Feed
from ..models.episode import Episode
from ..models.transcript import Transcript
from ..services.feed_sync_service import (
    FeedSyncService, _build_episode_doc, _persist_feed_icon, _upsert_video_episode,
    _refresh_youtube_channel_feed, _refresh_bilibili_feed,
)
from ..services.episode_query_service import EpisodeQueryService
from ..services.feed_identity import normalize_feed_url as _normalize_feed_url
from ..services.ai_control import is_ai_analysis_enabled
from ..services.rss_service import RSSService
from ..services.task_queue import task_queue
from ..services.trash_service import restore_feed_content, trash_feed_content
from ..services.youtube_service import YouTubeService
from ..services.bilibili_service import BilibiliService
from ..services.user_episode_state import episode_ids_with, user_filter_condition, unread_count
from ..services.user_feed_state import get_states as get_feed_states, latest_episode_id, has_unseen_updates, record_view
from .utils import (
    success_response,
    error_response,
    paginated_response,
    get_pagination_params,
    get_bool_param,
)
from .decorators import validate_object_id
from .decorators import current_owner_id, current_user, owner_filter, require_auth, require_role

logger = logging.getLogger(__name__)

feeds_bp = Blueprint("feeds", __name__)




def get_db():
    from .. import get_db as _get_db

    return _get_db()


@feeds_bp.route("", methods=["GET"])
@require_auth
def list_feeds():
    """获取订阅列表"""
    db = get_db()
    page, per_page = get_pagination_params()

    # 构建查询条件
    query = owner_filter()

    status = request.args.get("status")
    if status:
        query["status"] = status

    is_starred = get_bool_param("is_starred")
    if is_starred is not None:
        query["is_starred"] = is_starred

    is_favorite = get_bool_param("is_favorite")
    if is_favorite is not None:
        query["is_favorite"] = is_favorite

    # 查询
    total = db.feeds.count_documents(query)
    skip = (page - 1) * per_page

    feeds = list(db.feeds.find(query).sort([("created_at", -1), ("_id", -1)]).skip(skip).limit(per_page))

    # 转换响应格式；未读数按当前用户计算（已读状态按用户隔离）
    user_id = current_user()["id"]
    read_ids = episode_ids_with(db, user_id, "is_read")
    feed_states = get_feed_states(db, user_id, [feed["_id"] for feed in feeds])
    data = []
    for f in feeds:
        resp = Feed.to_response(f)
        resp["unread_count"] = db.episodes.count_documents(
            {"feed_id": f["_id"], "_id": {"$nin": read_ids}}
        )
        resp["has_unseen_updates"] = has_unseen_updates(latest_episode_id(db, f["_id"]), feed_states.get(f["_id"]))
        data.append(resp)

    return paginated_response(data, page, per_page, total)


@feeds_bp.route("/<feed_id>", methods=["GET"])
@validate_object_id("feed_id")
@require_auth
def get_feed(feed_id):
    """获取单个订阅详情"""
    db = get_db()

    feed = db.feeds.find_one(owner_filter({"_id": feed_id}))
    if not feed:
        return error_response("Feed not found", "FEED_NOT_FOUND", 404)

    response = Feed.to_response(feed)
    user_id = current_user()["id"]
    response["unread_count"] = unread_count(db, user_id, feed_id)
    response["has_unseen_updates"] = has_unseen_updates(latest_episode_id(db, feed_id), get_feed_states(db, user_id, [feed_id]).get(feed_id))
    return success_response(response)


@feeds_bp.route("/<feed_id>/view", methods=["POST"])
@validate_object_id("feed_id")
@require_auth
def view_feed(feed_id):
    """订阅列表成功加载后，自动确认当前用户看过的更新版本。"""
    db = get_db()
    if not db.feeds.find_one(owner_filter({"_id": feed_id})):
        return error_response("Feed not found", "FEED_NOT_FOUND", 404)
    data = request.get_json() or {}
    snapshot = data.get("latest_episode_id")
    if not isinstance(snapshot, str) or not ObjectId.is_valid(snapshot):
        return error_response("Invalid episode snapshot", "INVALID_EPISODE_SNAPSHOT", 400)
    seen_id = ObjectId(snapshot)
    if not db.episodes.find_one({"_id": seen_id, "feed_id": feed_id}, {"_id": 1}):
        return error_response("Episode snapshot not found in this feed", "EPISODE_SNAPSHOT_NOT_FOUND", 404)
    unseen = record_view(db, current_user()["id"], feed_id, seen_id)
    return success_response({"feed_id": str(feed_id), "has_unseen_updates": unseen})


@feeds_bp.route("", methods=["POST"])
@require_role("user", "admin")
def create_feed():
    """添加新订阅（自动识别：RSS / YouTube 频道 / B站 UP 主）"""
    db = get_db()
    data = request.get_json() or {}

    rss_url = data.get("rss_url", "").strip()
    if not rss_url:
        return error_response("RSS URL is required", "MISSING_RSS_URL", 400)

    owner_id = current_owner_id()

    if data.get("asynchronous") is True:
        if not Feed.validate_rss_url(rss_url):
            return error_response("Invalid RSS URL", "INVALID_RSS_URL", 400)
        for existing in db.feeds.find({}):
            if _normalize_feed_url(existing.get("rss_url") or "") == _normalize_feed_url(rss_url):
                return success_response(Feed.to_response(existing), "Feed already subscribed", 200)
        return _queue_feed_creation(db, rss_url, owner_id, data)

    return _create_feed_sync(db, rss_url, owner_id, data)


def _queue_feed_creation(db, url, owner_id, data):
    """HTTP 只排队；频道识别、订阅保存和首轮更新在后台完成。"""
    title = unquote(urlparse(url).path).strip("/") or urlparse(url).hostname

    def create(progress_callback=None):
        progress_callback((10, "正在识别订阅来源"))
        response = _create_feed_sync(db, url, owner_id, data, progress_callback)
        payload = response[0].get_json() if isinstance(response, tuple) else response.get_json()
        if not payload.get("success"):
            raise ValueError(payload["message"])
        progress_callback((100, "订阅已添加，正在后台更新节目"))
        return payload["data"]

    task_id = task_queue.submit_unique(
        "subscribe", create, owner_id=owner_id,
        dedup_key=f"subscribe:{owner_id}:{_normalize_feed_url(url)}",
        report_context={"kind": "subscription", "feed_title": title, "url": url},
    )
    return success_response({"task_id": task_id, "type": "subscribe", "status": "pending", "progress": 0,
                             "feed_title": title, "report_context": {"kind": "subscription", "url": url}},
                            "Subscription queued", 202)


def _create_feed_sync(db, rss_url, owner_id, data, progress_callback=None):

    # 共享库：订阅全局唯一，按规范化 URL 去重（同一来源不允许重复添加）
    normalized = _normalize_feed_url(rss_url)
    for existing in db.feeds.find({}, {"rss_url": 1, "title": 1}):
        if _normalize_feed_url(existing.get("rss_url") or "") == normalized:
            return error_response(
                f"Feed already exists: {existing.get('title', '')}", "FEED_EXISTS", 409
            )

    space_id = BilibiliService.extract_space_id(rss_url)
    if space_id:
        return _create_bilibili_feed(db, rss_url, space_id, owner_id, data)

    if YouTubeService.is_channel_url(rss_url):
        return _create_youtube_channel_feed(db, rss_url, owner_id, data, progress_callback)

    if not Feed.validate_rss_url(rss_url):
        return error_response("Invalid RSS URL", "INVALID_RSS_URL", 400)

    # 解析RSS
    feed_info, error = RSSService.parse_feed(rss_url)
    if error:
        return error_response(error, "RSS_PARSE_ERROR", 400)

    # 创建Feed文档
    episodes = feed_info.pop("episodes", [])
    tags = data.get("tags", [])

    feed_doc = Feed.create(
        rss_url=rss_url,
        owner_id=owner_id,
        title=feed_info.get("title"),
        website=feed_info.get("website"),
        image=feed_info.get("image"),
        description=feed_info.get("description"),
        author=feed_info.get("author"),
        language=feed_info.get("language"),
        tags=tags,
    )
    feed_doc["last_checked"] = datetime.utcnow()
    feed_doc["episode_count"] = len(episodes)
    feed_doc["unread_count"] = len(episodes)

    # 插入Feed
    result = db.feeds.insert_one(feed_doc)
    feed_id = result.inserted_id

    # 插入Episodes
    if episodes:
        episode_docs = [_build_episode_doc(feed_id, ep, owner_id=owner_id) for ep in episodes]
        if episode_docs:
            db.episodes.insert_many(episode_docs)

    # 获取并返回创建的Feed
    feed_doc["_id"] = feed_id
    # 垃圾箱里同源的历史剧集（含字幕/摘要）自动捞回
    restore_feed_content(db, feed_doc)
    return success_response(Feed.to_response(feed_doc), "Feed added successfully", 201)


def _queue_initial_refresh(feed_id, owner_id):
    """订阅创建后异步拉取首批视频（复用刷新管线）"""

    def do_refresh(progress_callback=None):
        return _refresh_feed_sync(str(feed_id), progress_callback)

    task_queue.submit_unique(task_type="refresh", func=do_refresh, feed_id=str(feed_id), owner_id=owner_id, dedup_key=f"refresh:{feed_id}")




def _create_youtube_channel_feed(db, url, owner_id, data, progress_callback=None):
    """订阅 YouTube 频道：解析频道 → 建 feed → 后台拉首批视频"""
    existing = db.feeds.find_one({"owner_id": owner_id, "rss_url": url})
    if existing:
        return error_response("Feed already exists", "FEED_EXISTS", 409)

    channel, error = YouTubeService.resolve_channel(url)
    if error:
        return error_response(error, "YOUTUBE_CHANNEL_RESOLVE_FAILED", 400)

    existing = db.feeds.find_one({"type": Feed.TYPE_YOUTUBE, "channel_ref": channel["channel_id"]})
    if existing:
        if data.get("asynchronous") is True:
            return success_response(Feed.to_response(existing), "Feed already subscribed", 200)
        return error_response("Feed already exists", "FEED_EXISTS", 409)

    feed_doc = Feed.create(
        rss_url=url,
        owner_id=owner_id,
        type=Feed.TYPE_YOUTUBE,
        channel_ref=channel["channel_id"],
        title=channel["title"] or url,
        website=f"https://www.youtube.com/channel/{channel['channel_id']}",
        description=f"YouTube 频道订阅 ({channel['channel_id']})",
        tags=data.get("tags", []),
    )
    feed_doc["last_checked"] = None
    result = db.feeds.insert_one(feed_doc)
    feed_doc["_id"] = result.inserted_id

    # 垃圾箱里同源的历史剧集（含字幕/摘要）自动捞回
    restore_feed_content(db, feed_doc)

    if progress_callback:
        progress_callback((70, "订阅已保存，正在获取频道封面"))

    _queue_initial_refresh(result.inserted_id, owner_id)

    if channel.get("avatar"):
        local_icon = _persist_feed_icon(
            result.inserted_id, channel["avatar"], proxy=YouTubeService._proxy()
        )
        if local_icon:
            db.feeds.update_one({"_id": result.inserted_id}, {"$set": {"image": local_icon}})
            feed_doc["image"] = local_icon

    return success_response(Feed.to_response(feed_doc), "YouTube channel subscribed", 201)


def _create_bilibili_feed(db, url, space_id, owner_id, data):
    """订阅 B站 UP 主；自动更新暂停，节目可手动刷新。"""
    existing = db.feeds.find_one({"owner_id": owner_id, "rss_url": url})
    if existing:
        return error_response("Feed already exists", "FEED_EXISTS", 409)

    uploader, error = BilibiliService.fetch_uploader_info(space_id)
    if error:
        return error_response(error, "BILIBILI_UPLOADER_FETCH_FAILED", 400)

    feed_doc = Feed.create(
        rss_url=url,
        owner_id=owner_id,
        type=Feed.TYPE_BILIBILI,
        channel_ref=space_id,
        title=uploader["name"] or url,
        website=f"https://space.bilibili.com/{space_id}",
        image=uploader.get("face", ""),
        description=uploader.get("sign", ""),
        tags=data.get("tags", []),
    )
    feed_doc["last_checked"] = None
    result = db.feeds.insert_one(feed_doc)
    feed_doc["_id"] = result.inserted_id

    # 垃圾箱里同源的历史剧集（含字幕/摘要）自动捞回
    restore_feed_content(db, feed_doc)

    if uploader.get("face"):
        local_icon = _persist_feed_icon(
            result.inserted_id, uploader["face"],
            referer="https://space.bilibili.com/",
        )
        if local_icon:
            db.feeds.update_one({"_id": result.inserted_id}, {"$set": {"image": local_icon}})
            feed_doc["image"] = local_icon

    return success_response(Feed.to_response(feed_doc), "Bilibili uploader subscribed", 201)


@feeds_bp.route("/<feed_id>", methods=["PUT"])
@require_role("user", "admin")
def update_feed(feed_id):
    """更新订阅"""
    db = get_db()

    try:
        oid = ObjectId(feed_id)
    except InvalidId:
        return error_response("Invalid feed ID", "INVALID_ID", 400)

    feed = db.feeds.find_one(owner_filter({"_id": oid}))
    if not feed:
        return error_response("Feed not found", "FEED_NOT_FOUND", 404)

    data = request.get_json() or {}

    # 允许更新的字段
    update_fields = {}
    allowed_fields = ["tags", "status", "note"]

    for field in allowed_fields:
        if field in data:
            update_fields[field] = data[field]

    if update_fields:
        update_fields["updated_at"] = datetime.utcnow()
        db.feeds.update_one(owner_filter({"_id": oid}), {"$set": update_fields})

    # 返回更新后的Feed
    updated_feed = db.feeds.find_one(owner_filter({"_id": oid}))
    return success_response(Feed.to_response(updated_feed))


@feeds_bp.route("/<feed_id>", methods=["DELETE"])
@require_role("user", "admin")
def delete_feed(feed_id):
    """删除订阅"""
    db = get_db()

    try:
        oid = ObjectId(feed_id)
    except InvalidId:
        return error_response("Invalid feed ID", "INVALID_ID", 400)

    feed = db.feeds.find_one(owner_filter({"_id": oid}))
    if not feed:
        return error_response("Feed not found", "FEED_NOT_FOUND", 404)

    # 剧集及附属数据（字幕/摘要/个人状态）整体进垃圾箱：
    # 保留期内重新订阅同一来源可自动捞回，过期由后台定期物理清除
    trashed = trash_feed_content(db, feed)

    # 删除Feed
    db.feeds.delete_one(owner_filter({"_id": oid}))

    return success_response({"trashed_episodes": trashed}, "Feed deleted successfully")


@feeds_bp.route("/<feed_id>/refresh", methods=["POST"])
@require_role("user", "admin")
def refresh_feed(feed_id):
    """刷新订阅 (异步)"""
    db = get_db()

    try:
        oid = ObjectId(feed_id)
    except InvalidId:
        return error_response("Invalid feed ID", "INVALID_ID", 400)

    feed = db.feeds.find_one(owner_filter({"_id": oid}))
    if not feed:
        return error_response("Feed not found", "FEED_NOT_FOUND", 404)

    # 提交异步任务
    def do_refresh(progress_callback=None):
        return _refresh_feed_sync(str(oid), progress_callback)

    task_id = task_queue.submit_unique(task_type="refresh", func=do_refresh, feed_id=str(oid), owner_id=current_owner_id(), dedup_key=f"refresh:{oid}")

    return success_response({"task_id": task_id, "status": "queued"})


def _refresh_feed_sync(feed_id: str, progress_callback=None):
    """Compatibility entry point; the service owns the refresh workflow."""
    return FeedSyncService(get_db(), queue=task_queue).refresh(feed_id, progress_callback)















@feeds_bp.route("/<feed_id>/star", methods=["POST"])
@require_auth
def star_feed(feed_id):
    """标星/取消标星"""
    db = get_db()

    try:
        oid = ObjectId(feed_id)
    except InvalidId:
        return error_response("Invalid feed ID", "INVALID_ID", 400)

    feed = db.feeds.find_one(owner_filter({"_id": oid}))
    if not feed:
        return error_response("Feed not found", "FEED_NOT_FOUND", 404)

    data = request.get_json() or {}
    starred = data.get("starred", not feed.get("is_starred", False))

    db.feeds.update_one(
        owner_filter({"_id": oid}), {"$set": {"is_starred": starred, "updated_at": datetime.utcnow()}}
    )

    return success_response({"id": feed_id, "is_starred": starred})


@feeds_bp.route("/<feed_id>/favorite", methods=["POST"])
@require_auth
def favorite_feed(feed_id):
    """收藏/取消收藏"""
    db = get_db()

    try:
        oid = ObjectId(feed_id)
    except InvalidId:
        return error_response("Invalid feed ID", "INVALID_ID", 400)

    feed = db.feeds.find_one(owner_filter({"_id": oid}))
    if not feed:
        return error_response("Feed not found", "FEED_NOT_FOUND", 404)

    data = request.get_json() or {}
    favorite = data.get("favorite", not feed.get("is_favorite", False))

    db.feeds.update_one(
        owner_filter({"_id": oid}),
        {"$set": {"is_favorite": favorite, "updated_at": datetime.utcnow()}},
    )

    return success_response({"id": feed_id, "is_favorite": favorite})


@feeds_bp.route("/<feed_id>/episodes", methods=["GET"])
@require_auth
def list_feed_episodes(feed_id):
    """获取某订阅的单集列表"""
    db = get_db()

    try:
        oid = ObjectId(feed_id)
    except InvalidId:
        return error_response("Invalid feed ID", "INVALID_ID", 400)

    feed = db.feeds.find_one(owner_filter({"_id": oid}))
    if not feed:
        return error_response("Feed not found", "FEED_NOT_FOUND", 404)

    page, per_page = get_pagination_params()

    snapshot = latest_episode_id(db, oid)
    service = EpisodeQueryService(db, current_app.config.get("MEDIA_ROOT", "."),
                                  current_app.config.get("TRANSCRIPTION_CLOUD_ENABLED", False), is_ai_analysis_enabled(),
                                  current_user()["role"] in {"user", "admin"})
    try:
        data, total = service.list(current_user()["id"], request.args, page, per_page, oid)
    except ValueError as error:
        return error_response(str(error), "INVALID_QUERY", 400)
    return paginated_response(data, page, per_page, total, meta={"latest_episode_id": str(snapshot) if snapshot else None})
