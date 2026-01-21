# -*- coding: utf-8 -*-
"""
Feeds API

订阅源管理接口
"""
from flask import Blueprint, request
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime

from ..models.feed import Feed
from ..models.episode import Episode
from ..services.rss_service import RSSService
from ..services.task_queue import task_queue
from .utils import (
    success_response,
    error_response,
    paginated_response,
    get_pagination_params,
    get_bool_param
)

feeds_bp = Blueprint("feeds", __name__)


def get_db():
    from .. import get_db as _get_db
    return _get_db()


@feeds_bp.route("", methods=["GET"])
def list_feeds():
    """获取订阅列表"""
    db = get_db()
    page, per_page = get_pagination_params()

    # 构建查询条件
    query = {}

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

    feeds = list(
        db.feeds.find(query)
        .sort("created_at", -1)
        .skip(skip)
        .limit(per_page)
    )

    # 转换响应格式
    data = [Feed.to_response(f) for f in feeds]

    return paginated_response(data, page, per_page, total)


@feeds_bp.route("/<feed_id>", methods=["GET"])
def get_feed(feed_id):
    """获取单个订阅详情"""
    db = get_db()

    try:
        oid = ObjectId(feed_id)
    except InvalidId:
        return error_response("Invalid feed ID", "INVALID_ID", 400)

    feed = db.feeds.find_one({"_id": oid})
    if not feed:
        return error_response("Feed not found", "FEED_NOT_FOUND", 404)

    return success_response(Feed.to_response(feed))


@feeds_bp.route("", methods=["POST"])
def create_feed():
    """添加新订阅"""
    db = get_db()
    data = request.get_json() or {}

    rss_url = data.get("rss_url", "").strip()
    if not rss_url:
        return error_response("RSS URL is required", "MISSING_RSS_URL", 400)

    if not Feed.validate_rss_url(rss_url):
        return error_response("Invalid RSS URL", "INVALID_RSS_URL", 400)

    # 检查是否已存在
    existing = db.feeds.find_one({"rss_url": rss_url})
    if existing:
        return error_response("Feed already exists", "FEED_EXISTS", 409)

    # 解析RSS
    feed_info, error = RSSService.parse_feed(rss_url)
    if error:
        return error_response(error, "RSS_PARSE_ERROR", 400)

    # 创建Feed文档
    episodes = feed_info.pop("episodes", [])
    tags = data.get("tags", [])

    feed_doc = Feed.create(
        rss_url=rss_url,
        title=feed_info.get("title"),
        website=feed_info.get("website"),
        image=feed_info.get("image"),
        description=feed_info.get("description"),
        author=feed_info.get("author"),
        language=feed_info.get("language"),
        tags=tags
    )
    feed_doc["last_checked"] = datetime.utcnow()
    feed_doc["episode_count"] = len(episodes)
    feed_doc["unread_count"] = len(episodes)

    # 插入Feed
    result = db.feeds.insert_one(feed_doc)
    feed_id = result.inserted_id

    # 插入Episodes
    if episodes:
        episode_docs = []
        for ep_info in episodes:
            ep_doc = Episode.create(
                feed_id=feed_id,
                guid=ep_info["guid"],
                title=ep_info["title"],
                summary=ep_info.get("summary"),
                content=ep_info.get("content"),
                link=ep_info.get("link"),
                published=ep_info.get("published"),
                audio_url=ep_info.get("audio_url"),
                audio_type=ep_info.get("audio_type"),
                audio_size=ep_info.get("audio_size"),
                duration=ep_info.get("duration", 0),
                image=ep_info.get("image"),
                chapters_url=ep_info.get("chapters_url"),
                transcript_url=ep_info.get("transcript_url")
            )
            episode_docs.append(ep_doc)

        if episode_docs:
            db.episodes.insert_many(episode_docs)

    # 获取并返回创建的Feed
    feed_doc["_id"] = feed_id
    return success_response(
        Feed.to_response(feed_doc),
        "Feed added successfully",
        201
    )


@feeds_bp.route("/<feed_id>", methods=["PUT"])
def update_feed(feed_id):
    """更新订阅"""
    db = get_db()

    try:
        oid = ObjectId(feed_id)
    except InvalidId:
        return error_response("Invalid feed ID", "INVALID_ID", 400)

    feed = db.feeds.find_one({"_id": oid})
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
        db.feeds.update_one({"_id": oid}, {"$set": update_fields})

    # 返回更新后的Feed
    updated_feed = db.feeds.find_one({"_id": oid})
    return success_response(Feed.to_response(updated_feed))


@feeds_bp.route("/<feed_id>", methods=["DELETE"])
def delete_feed(feed_id):
    """删除订阅"""
    db = get_db()

    try:
        oid = ObjectId(feed_id)
    except InvalidId:
        return error_response("Invalid feed ID", "INVALID_ID", 400)

    feed = db.feeds.find_one({"_id": oid})
    if not feed:
        return error_response("Feed not found", "FEED_NOT_FOUND", 404)

    # 删除相关的episodes, transcripts, summaries
    episode_ids = [ep["_id"] for ep in db.episodes.find({"feed_id": oid}, {"_id": 1})]

    if episode_ids:
        db.transcripts.delete_many({"episode_id": {"$in": episode_ids}})
        db.summaries.delete_many({"episode_id": {"$in": episode_ids}})
        db.episodes.delete_many({"feed_id": oid})

    # 删除Feed
    db.feeds.delete_one({"_id": oid})

    return success_response(message="Feed deleted successfully")


@feeds_bp.route("/<feed_id>/refresh", methods=["POST"])
def refresh_feed(feed_id):
    """刷新订阅 (异步)"""
    db = get_db()

    try:
        oid = ObjectId(feed_id)
    except InvalidId:
        return error_response("Invalid feed ID", "INVALID_ID", 400)

    feed = db.feeds.find_one({"_id": oid})
    if not feed:
        return error_response("Feed not found", "FEED_NOT_FOUND", 404)

    # 提交异步任务
    def do_refresh(progress_callback=None):
        return _refresh_feed_sync(str(oid), progress_callback)

    task_id = task_queue.submit(
        task_type="refresh",
        func=do_refresh,
        feed_id=str(oid)
    )

    return success_response({
        "task_id": task_id,
        "status": "queued"
    })


def _refresh_feed_sync(feed_id: str, progress_callback=None):
    """同步执行Feed刷新"""
    db = get_db()
    oid = ObjectId(feed_id)

    feed = db.feeds.find_one({"_id": oid})
    if not feed:
        raise ValueError("Feed not found")

    if progress_callback:
        progress_callback(10)

    # 解析RSS
    feed_info, error = RSSService.parse_feed(feed["rss_url"])
    if error:
        db.feeds.update_one(
            {"_id": oid},
            {"$set": {
                "status": Feed.STATUS_ERROR,
                "check_error": error,
                "last_checked": datetime.utcnow()
            }}
        )
        raise ValueError(error)

    if progress_callback:
        progress_callback(50)

    # 获取已有的guid列表
    existing_guids = set(
        ep["guid"] for ep in db.episodes.find({"feed_id": oid}, {"guid": 1})
    )

    # 插入新Episodes
    new_episodes = []
    episodes = feed_info.get("episodes", [])

    for ep_info in episodes:
        if ep_info["guid"] not in existing_guids:
            ep_doc = Episode.create(
                feed_id=oid,
                guid=ep_info["guid"],
                title=ep_info["title"],
                summary=ep_info.get("summary"),
                content=ep_info.get("content"),
                link=ep_info.get("link"),
                published=ep_info.get("published"),
                audio_url=ep_info.get("audio_url"),
                audio_type=ep_info.get("audio_type"),
                audio_size=ep_info.get("audio_size"),
                duration=ep_info.get("duration", 0),
                image=ep_info.get("image"),
                chapters_url=ep_info.get("chapters_url"),
                transcript_url=ep_info.get("transcript_url")
            )
            new_episodes.append(ep_doc)

    if new_episodes:
        db.episodes.insert_many(new_episodes)

    if progress_callback:
        progress_callback(90)

    # 更新Feed状态
    total_count = db.episodes.count_documents({"feed_id": oid})
    unread_count = db.episodes.count_documents({"feed_id": oid, "is_read": False})

    db.feeds.update_one(
        {"_id": oid},
        {"$set": {
            "status": Feed.STATUS_ACTIVE,
            "check_error": None,
            "last_checked": datetime.utcnow(),
            "last_updated": datetime.utcnow() if new_episodes else feed.get("last_updated"),
            "episode_count": total_count,
            "unread_count": unread_count
        }}
    )

    if progress_callback:
        progress_callback(100)

    return {
        "new_episodes": len(new_episodes),
        "total_episodes": total_count
    }


@feeds_bp.route("/<feed_id>/star", methods=["POST"])
def star_feed(feed_id):
    """标星/取消标星"""
    db = get_db()

    try:
        oid = ObjectId(feed_id)
    except InvalidId:
        return error_response("Invalid feed ID", "INVALID_ID", 400)

    feed = db.feeds.find_one({"_id": oid})
    if not feed:
        return error_response("Feed not found", "FEED_NOT_FOUND", 404)

    data = request.get_json() or {}
    starred = data.get("starred", not feed.get("is_starred", False))

    db.feeds.update_one(
        {"_id": oid},
        {"$set": {"is_starred": starred, "updated_at": datetime.utcnow()}}
    )

    return success_response({"id": feed_id, "is_starred": starred})


@feeds_bp.route("/<feed_id>/favorite", methods=["POST"])
def favorite_feed(feed_id):
    """收藏/取消收藏"""
    db = get_db()

    try:
        oid = ObjectId(feed_id)
    except InvalidId:
        return error_response("Invalid feed ID", "INVALID_ID", 400)

    feed = db.feeds.find_one({"_id": oid})
    if not feed:
        return error_response("Feed not found", "FEED_NOT_FOUND", 404)

    data = request.get_json() or {}
    favorite = data.get("favorite", not feed.get("is_favorite", False))

    db.feeds.update_one(
        {"_id": oid},
        {"$set": {"is_favorite": favorite, "updated_at": datetime.utcnow()}}
    )

    return success_response({"id": feed_id, "is_favorite": favorite})


@feeds_bp.route("/<feed_id>/episodes", methods=["GET"])
def list_feed_episodes(feed_id):
    """获取某订阅的单集列表"""
    db = get_db()

    try:
        oid = ObjectId(feed_id)
    except InvalidId:
        return error_response("Invalid feed ID", "INVALID_ID", 400)

    feed = db.feeds.find_one({"_id": oid})
    if not feed:
        return error_response("Feed not found", "FEED_NOT_FOUND", 404)

    page, per_page = get_pagination_params()

    # 构建查询条件
    query = {"feed_id": oid}

    status = request.args.get("status")
    if status:
        query["status"] = status

    is_read = get_bool_param("is_read")
    if is_read is not None:
        query["is_read"] = is_read

    is_starred = get_bool_param("is_starred")
    if is_starred is not None:
        query["is_starred"] = is_starred

    # 查询
    total = db.episodes.count_documents(query)
    skip = (page - 1) * per_page

    episodes = list(
        db.episodes.find(query)
        .sort("published", -1)
        .skip(skip)
        .limit(per_page)
    )

    # 添加feed_title并转换响应格式
    for ep in episodes:
        ep["feed_title"] = feed.get("title", "")

    data = [Episode.to_response(ep, include_feed_title=True) for ep in episodes]

    return paginated_response(data, page, per_page, total)
