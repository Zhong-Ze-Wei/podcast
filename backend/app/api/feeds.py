# -*- coding: utf-8 -*-
"""
Feeds API

订阅源管理接口
"""

import logging

from flask import Blueprint, request

import os
import requests as http_requests

from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime

from ..models.feed import Feed
from ..models.episode import Episode
from ..models.transcript import Transcript
from ..services.rss_service import RSSService
from ..services.task_queue import task_queue
from ..services.youtube_service import YouTubeService
from ..services.bilibili_service import BilibiliService
from .utils import (
    success_response,
    error_response,
    paginated_response,
    get_pagination_params,
    get_bool_param,
)
from .decorators import validate_object_id
from .decorators import current_owner_id, owner_filter, require_auth

logger = logging.getLogger(__name__)

feeds_bp = Blueprint("feeds", __name__)


def _build_episode_doc(feed_id, ep_info, owner_id=None):
    """从 RSS 解析结果构造 Episode 文档（owner_id 继承自 feed，可能为 None=本地单用户）"""
    return Episode.create(
        feed_id=feed_id,
        owner_id=owner_id,
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
        transcript_url=ep_info.get("transcript_url"),
    )


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

    feeds = list(db.feeds.find(query).sort("created_at", -1).skip(skip).limit(per_page))

    # 转换响应格式
    data = [Feed.to_response(f) for f in feeds]

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

    return success_response(Feed.to_response(feed))


@feeds_bp.route("", methods=["POST"])
@require_auth
def create_feed():
    """添加新订阅（自动识别：RSS / YouTube 频道 / B站 UP 主）"""
    db = get_db()
    data = request.get_json() or {}

    rss_url = data.get("rss_url", "").strip()
    if not rss_url:
        return error_response("RSS URL is required", "MISSING_RSS_URL", 400)

    owner_id = current_owner_id()

    space_id = BilibiliService.extract_space_id(rss_url)
    if space_id:
        return _create_bilibili_feed(db, rss_url, space_id, owner_id, data)

    if YouTubeService.is_channel_url(rss_url):
        return _create_youtube_channel_feed(db, rss_url, owner_id, data)

    if not Feed.validate_rss_url(rss_url):
        return error_response("Invalid RSS URL", "INVALID_RSS_URL", 400)

    # 检查是否已存在
    existing = db.feeds.find_one({"owner_id": owner_id, "rss_url": rss_url})
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
    return success_response(Feed.to_response(feed_doc), "Feed added successfully", 201)


def _queue_initial_refresh(feed_id, owner_id):
    """订阅创建后异步拉取首批视频（复用刷新管线）"""

    def do_refresh(progress_callback=None):
        return _refresh_feed_sync(str(feed_id), progress_callback)

    task_queue.submit(task_type="refresh", func=do_refresh, feed_id=str(feed_id), owner_id=owner_id)


def _persist_feed_icon(feed_id, url, referer=None, proxy=None, filename=None):
    """
    下载图片到 media/covers 并返回本地 API 路径（已存在则跳过下载）。

    B站/YouTube 图源有防盗链或需代理，浏览器直连加载不可靠，统一落地本地。
    """
    from ..config import Config

    try:
        covers_dir = Config.COVERS_DIR
        os.makedirs(covers_dir, exist_ok=True)
        filename = filename or f"feed_{feed_id}.jpg"
        local_path = os.path.join(covers_dir, filename)
        if os.path.exists(local_path):
            return f"/api/media/covers/{filename}"

        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
        }
        if referer:
            headers["Referer"] = referer
        proxies = {"http": proxy, "https": proxy} if proxy else None
        resp = http_requests.get(url, headers=headers, proxies=proxies, timeout=15)
        resp.raise_for_status()

        with open(local_path, "wb") as f:
            f.write(resp.content)
        return f"/api/media/covers/{filename}"
    except Exception:
        return None


def _create_youtube_channel_feed(db, url, owner_id, data):
    """订阅 YouTube 频道：解析频道 → 建 feed → 后台拉首批视频"""
    existing = db.feeds.find_one({"owner_id": owner_id, "rss_url": url})
    if existing:
        return error_response("Feed already exists", "FEED_EXISTS", 409)

    channel, error = YouTubeService.resolve_channel(url)
    if error:
        return error_response(error, "YOUTUBE_CHANNEL_RESOLVE_FAILED", 400)

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

    if channel.get("avatar"):
        local_icon = _persist_feed_icon(
            result.inserted_id, channel["avatar"], proxy=YouTubeService._proxy()
        )
        if local_icon:
            db.feeds.update_one({"_id": result.inserted_id}, {"$set": {"image": local_icon}})
            feed_doc["image"] = local_icon

    _queue_initial_refresh(result.inserted_id, owner_id)
    return success_response(Feed.to_response(feed_doc), "YouTube channel subscribed", 201)


def _create_bilibili_feed(db, url, space_id, owner_id, data):
    """订阅 B站 UP 主：拉 UP 主信息 → 建 feed → 后台拉首批视频"""
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

    if uploader.get("face"):
        local_icon = _persist_feed_icon(
            result.inserted_id, uploader["face"],
            referer="https://space.bilibili.com/",
        )
        if local_icon:
            db.feeds.update_one({"_id": result.inserted_id}, {"$set": {"image": local_icon}})
            feed_doc["image"] = local_icon

    _queue_initial_refresh(result.inserted_id, owner_id)
    return success_response(Feed.to_response(feed_doc), "Bilibili uploader subscribed", 201)


@feeds_bp.route("/<feed_id>", methods=["PUT"])
@require_auth
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
@require_auth
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

    # 删除相关的episodes, transcripts, summaries
    owner_id = current_owner_id()
    episode_ids = [ep["_id"] for ep in db.episodes.find({"owner_id": owner_id, "feed_id": oid}, {"_id": 1})]

    if episode_ids:
        db.transcripts.delete_many({"owner_id": owner_id, "episode_id": {"$in": episode_ids}})
        db.summaries.delete_many({"owner_id": owner_id, "episode_id": {"$in": episode_ids}})
        db.episodes.delete_many({"owner_id": owner_id, "feed_id": oid})

    # 删除Feed
    db.feeds.delete_one(owner_filter({"_id": oid}))

    return success_response(message="Feed deleted successfully")


@feeds_bp.route("/<feed_id>/refresh", methods=["POST"])
@require_auth
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

    task_id = task_queue.submit(task_type="refresh", func=do_refresh, feed_id=str(oid), owner_id=current_owner_id())

    return success_response({"task_id": task_id, "status": "queued"})


def _refresh_feed_sync(feed_id: str, progress_callback=None):
    """同步执行Feed刷新（按类型分发：RSS / YouTube 频道 / B站 UP 主）"""
    db = get_db()
    oid = ObjectId(feed_id)

    feed = db.feeds.find_one({"_id": oid})
    if not feed:
        raise ValueError("Feed not found")

    feed_type = feed.get("type") or Feed.TYPE_RSS
    if feed_type == Feed.TYPE_YOUTUBE:
        return _refresh_youtube_channel_feed(db, feed, progress_callback)
    if feed_type == Feed.TYPE_BILIBILI:
        return _refresh_bilibili_feed(db, feed, progress_callback)

    if progress_callback:
        progress_callback(10)

    # 解析RSS
    feed_info, error = RSSService.parse_feed(feed["rss_url"])
    if error:
        db.feeds.update_one(
            {"_id": oid},
            {
                "$set": {
                    "status": Feed.STATUS_ERROR,
                    "check_error": error,
                    "last_checked": datetime.utcnow(),
                }
            },
        )
        raise ValueError(error)

    if progress_callback:
        progress_callback(50)

    # 获取已有的guid列表
    owner_id = feed.get("owner_id")
    existing_guids = set(
        ep["guid"] for ep in db.episodes.find({"owner_id": owner_id, "feed_id": oid}, {"guid": 1})
    )

    # 插入新Episodes
    new_episodes = []
    episodes = feed_info.get("episodes", [])

    for ep_info in episodes:
        if ep_info["guid"] not in existing_guids:
            new_episodes.append(_build_episode_doc(oid, ep_info, owner_id=feed.get("owner_id")))

    if new_episodes:
        db.episodes.insert_many(new_episodes)

    if progress_callback:
        progress_callback(90)

    # 更新Feed状态
    total_count = db.episodes.count_documents({"owner_id": owner_id, "feed_id": oid})
    unread_count = db.episodes.count_documents({"owner_id": owner_id, "feed_id": oid, "is_read": False})

    db.feeds.update_one(
        {"_id": oid},
        {
            "$set": {
                "status": Feed.STATUS_ACTIVE,
                "check_error": None,
                "last_checked": datetime.utcnow(),
                "last_updated": datetime.utcnow()
                if new_episodes
                else feed.get("last_updated"),
                "episode_count": total_count,
                "unread_count": unread_count,
            }
        },
    )

    if progress_callback:
        progress_callback(100)

    return {"new_episodes": len(new_episodes), "total_episodes": total_count}


def _upsert_video_episode(db, feed, guid, title, *, duration=0, link="", image="",
                          author="", published=None, audio_type="video/youtube",
                          transcript=None, transcript_source=None):
    """
    插入视频 episode（含可选 transcript）。

    返回 'created'（新建）/ 'backfilled'（已存在但补上了 transcript）/ None。
    """
    existing = db.episodes.find_one({"owner_id": feed.get("owner_id"), "guid": guid})
    if existing:
        # 已入库但缺字幕的剧集：补上 transcript（AI 字幕是异步生成的，首轮常拿不到）
        if transcript and not db.transcripts.find_one({"episode_id": existing["_id"]}):
            db.transcripts.insert_one(Transcript.create(
                episode_id=existing["_id"],
                owner_id=feed.get("owner_id"),
                text=transcript["text"],
                segments=transcript["segments"],
                language=transcript.get("language", ""),
                source=transcript_source,
                model=transcript.get("model", ""),
            ))
            db.episodes.update_one(
                {"_id": existing["_id"]},
                {"$set": {"status": Episode.STATUS_TRANSCRIBED}},
            )
            return "backfilled"
        return None

    episode_doc = Episode.create(
        feed_id=feed["_id"],
        owner_id=feed.get("owner_id"),
        guid=guid,
        title=title,
        link=link,
        published=published or datetime.utcnow(),
        duration=duration,
        image=image,
        audio_type=audio_type,
    )
    if transcript:
        episode_doc["status"] = Episode.STATUS_TRANSCRIBED
    if author:
        episode_doc["author"] = author
    result = db.episodes.insert_one(episode_doc)

    if transcript:
        db.transcripts.insert_one(Transcript.create(
            episode_id=result.inserted_id,
            owner_id=feed.get("owner_id"),
            text=transcript["text"],
            segments=transcript["segments"],
            language=transcript.get("language", ""),
            source=transcript_source,
            model=transcript.get("model", ""),
        ))
    return "created"


def _refresh_youtube_channel_feed(db, feed, progress_callback=None):
    """YouTube 频道刷新：RSS 拉最新 15 条 → 新视频拉字幕"""
    if progress_callback:
        progress_callback(10)

    import time as _time

    videos, error = YouTubeService.fetch_channel_videos(feed.get("channel_ref"))
    if error:
        db.feeds.update_one({"_id": feed["_id"]}, {"$set": {
            "status": Feed.STATUS_ERROR, "check_error": error, "last_checked": datetime.utcnow(),
        }})
        raise ValueError(error)

    if progress_callback:
        progress_callback(30)

    owner_id = feed.get("owner_id")
    # 只跳过已有 transcript 的剧集；缺字幕的重试（AI 字幕异步生成）
    existing_guids = set(
        ep["guid"] for ep in db.episodes.find({"owner_id": owner_id, "feed_id": feed["_id"]}, {"guid": 1})
        if db.transcripts.find_one({"episode_id": ep["_id"]})
    )

    new_count, transcript_count, failed = 0, 0, 0
    for i, video in enumerate(videos):
        guid = f"youtube:{video['video_id']}"
        if guid in existing_guids:
            continue

        _time.sleep(2.5)  # YouTube 连续大量请求同样会被限流，逐个节流（2.5s，实测 1.2s 仍偶发触发风控）

        metadata, meta_error = YouTubeService.fetch_metadata(video["video_id"])
        title = (metadata or {}).get("title") or video["title"]
        duration = (metadata or {}).get("duration") or 0

        # 剧集封面落地本地（ytimg 国内浏览器直连不稳）
        local_thumb = None
        if (metadata or {}).get("thumbnail"):
            local_thumb = _persist_feed_icon(
                None, metadata["thumbnail"],
                proxy=YouTubeService._proxy(),
                filename=f"yt_{video['video_id']}.jpg",
            )

        transcript, tr_error = YouTubeService.fetch_transcript(video["video_id"])
        if transcript:
            transcript["model"] = "youtube-transcript-api"

        created = _upsert_video_episode(
            db, feed, guid, title,
            duration=duration,
            link=f"https://www.youtube.com/watch?v={video['video_id']}",
            image=local_thumb or (metadata or {}).get("thumbnail", ""),
            author=(metadata or {}).get("uploader", ""),
            published=video.get("published"),
            transcript=transcript,
            transcript_source=Transcript.SOURCE_YOUTUBE,
        )
        if created == "created":
            new_count += 1
            if transcript:
                transcript_count += 1
            else:
                failed += 1
        elif created == "backfilled":
            transcript_count += 1
        if progress_callback:
            progress_callback((30 + int(60 * (i + 1) / max(len(videos), 1)), f"拉取字幕 {i + 1}/{len(videos)}"))

    total = db.episodes.count_documents({"owner_id": owner_id, "feed_id": feed["_id"]})
    db.feeds.update_one({"_id": feed["_id"]}, {"$set": {
        "status": Feed.STATUS_ACTIVE,
        "check_error": None,
        "last_checked": datetime.utcnow(),
        "last_updated": datetime.utcnow() if new_count else feed.get("last_updated"),
        "episode_count": total,
    }})
    if progress_callback:
        progress_callback((100, f"完成：新增 {new_count} 集 / 字幕 {transcript_count} 条"))

    return {"new_episodes": new_count, "new_transcripts": transcript_count,
            "transcript_failures": failed, "total_episodes": total}


def _refresh_bilibili_feed(db, feed, progress_callback=None):
    """B站 UP 主刷新：wbi 拉投稿列表 → 新视频拉 AI 字幕"""
    if progress_callback:
        progress_callback(10)

    videos, error = BilibiliService.fetch_uploader_videos(feed.get("channel_ref"))
    if error:
        db.feeds.update_one({"_id": feed["_id"]}, {"$set": {
            "status": Feed.STATUS_ERROR, "check_error": error, "last_checked": datetime.utcnow(),
        }})
        raise ValueError(error)

    if progress_callback:
        progress_callback(30)

    owner_id = feed.get("owner_id")
    # 只跳过已有 transcript 的剧集；缺字幕的重试（AI 字幕异步生成）
    existing_guids = set(
        ep["guid"] for ep in db.episodes.find({"owner_id": owner_id, "feed_id": feed["_id"]}, {"guid": 1})
        if db.transcripts.find_one({"episode_id": ep["_id"]})
    )

    new_count, transcript_count, failed = 0, 0, 0
    for i, video in enumerate(videos):
        guid = f"bilibili:{video['bvid']}"
        if guid in existing_guids:
            continue

    new_count, transcript_count, failed = 0, 0, 0
    # 同订阅字幕查重：B站串台时多个视频会返回同一份字幕
    import hashlib as _hashlib
    import time as _time
    existing_text_keys = set(
        _hashlib.md5(tr["text"][:300].encode("utf-8", "ignore")).hexdigest()
        for tr in db.transcripts.find({"owner_id": owner_id}, {"text": 1})
        if tr.get("text")
    )
    for i, video in enumerate(videos):
        guid = f"bilibili:{video['bvid']}"
        if guid in existing_guids:
            continue

        _time.sleep(2.5)  # B站连续大量请求会触发瞬时风控，逐个节流（2.5s，实测 1.2s 仍偶发触发风控）

        published = None
        if video.get("published"):
            published = datetime.utcfromtimestamp(video["published"])

        transcript, tr_error = BilibiliService.fetch_ai_subtitle(video["bvid"], title=video.get("title", ""))
        if transcript:
            text_key = _hashlib.md5(transcript["text"][:300].encode("utf-8", "ignore")).hexdigest()
            if text_key in existing_text_keys:
                transcript, tr_error = None, "AI subtitle rejected: duplicate of another episode (mismatched subtitle)"
            else:
                existing_text_keys.add(text_key)
                transcript["model"] = "bili-ai-subtitle"

        created = _upsert_video_episode(
            db, feed, guid, video["title"],
            duration=video.get("duration") or 0,
            link=f"https://www.bilibili.com/video/{video['bvid']}",
            image=video.get("cover", ""),
            author=feed.get("title", ""),
            published=published,
            audio_type="video/bilibili",
            transcript=transcript,
            transcript_source=Transcript.SOURCE_BILIBILI,
        )
        if created == "created":
            new_count += 1
            if transcript:
                transcript_count += 1
            else:
                failed += 1
        elif created == "backfilled":
            transcript_count += 1
        if progress_callback:
            progress_callback((30 + int(60 * (i + 1) / max(len(videos), 1)), f"拉取字幕 {i + 1}/{len(videos)}"))

    total = db.episodes.count_documents({"owner_id": owner_id, "feed_id": feed["_id"]})
    db.feeds.update_one({"_id": feed["_id"]}, {"$set": {
        "status": Feed.STATUS_ACTIVE,
        "check_error": None,
        "last_checked": datetime.utcnow(),
        "last_updated": datetime.utcnow() if new_count else feed.get("last_updated"),
        "episode_count": total,
    }})
    if progress_callback:
        progress_callback((100, f"完成：新增 {new_count} 集 / 字幕 {transcript_count} 条"))

    return {"new_episodes": new_count, "new_transcripts": transcript_count,
            "transcript_failures": failed, "total_episodes": total}


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

    # 构建查询条件
    query = owner_filter({"feed_id": oid})

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
        db.episodes.find(query).sort("published", -1).skip(skip).limit(per_page)
    )

    # 添加feed_title并转换响应格式
    for ep in episodes:
        ep["feed_title"] = feed.get("title", "")

    data = [Episode.to_response(ep, include_feed_title=True) for ep in episodes]

    return paginated_response(data, page, per_page, total)
