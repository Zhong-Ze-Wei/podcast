"""Source synchronization shared by HTTP endpoints and scheduled refreshes."""
import os
from datetime import datetime
import requests as http_requests
from bson import ObjectId
from ..models.feed import Feed
from ..models.episode import Episode
from ..models.transcript import Transcript
from .rss_service import RSSService
from .youtube_service import YouTubeService
from .bilibili_service import BilibiliService
from .task_queue import task_queue


class FeedSyncService:
    def __init__(self, db, queue=task_queue):
        self.db = db
        self.queue = queue

    def refresh(self, feed_id, progress_callback=None):
        return refresh_feed_sync(self.db, feed_id, progress_callback, queue=self.queue)


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


def refresh_feed_sync(db, feed_id: str, progress_callback=None, *, queue=task_queue):
    """同步执行Feed刷新（按类型分发：RSS / YouTube 频道 / B站 UP 主）"""
    oid = ObjectId(feed_id)

    feed = db.feeds.find_one({"_id": oid})
    if not feed:
        raise ValueError("Feed not found")

    feed_type = feed.get("type") or Feed.TYPE_RSS
    if feed_type == Feed.TYPE_YOUTUBE:
        return _refresh_youtube_channel_feed(db, feed, progress_callback, queue=queue)
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

    # 更新Feed状态（未读数不再落库：已读按用户隔离，列表接口实时计算）
    total_count = db.episodes.count_documents({"owner_id": owner_id, "feed_id": oid})

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
            }
        },
    )

    if progress_callback:
        progress_callback(100)

    return {"new_episodes": len(new_episodes), "total_episodes": total_count}


_TRANSLATE_SUBTITLE_ERRORS = [
    ("disabled", "YouTube 暂未返回可用字幕（未生成或已禁用），可稍后重试。"),
    ("No AI subtitle available", "B站 AI 字幕尚未生成，稍后自动重试"),
    ("No transcript available", "该视频暂无字幕"),
    ("AI subtitle rejected", "字幕未通过内容校验（与视频不符，已拒收）"),
    ("login required", "B站登录态失效，请更新 SESSDATA"),
    ("proxy", "代理不可用，请检查代理节点"),
]


def _humanize_subtitle_error(error: str) -> str:
    for key, text in _TRANSLATE_SUBTITLE_ERRORS:
        if key.lower() in (error or "").lower():
            return text
    return error or "字幕拉取失败"


def _mark_episode_subtitle_error(db, episode_id, error):
    """字幕失败原因落到剧集，供前端展示"""
    db.episodes.update_one(
        {"_id": episode_id},
        {"$set": {"transcript_fetch_error": _humanize_subtitle_error(error)}},
    )


def _clear_episode_subtitle_error(db, episode_id):
    db.episodes.update_one(
        {"_id": episode_id},
        {"$unset": {"transcript_fetch_error": ""}},
    )


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
            updates = {"has_transcript": True, "transcript_source": transcript_source}
            if existing.get("status") not in (Episode.STATUS_SUMMARIZED, Episode.STATUS_SUMMARIZING):
                updates["status"] = Episode.STATUS_TRANSCRIBED
            db.episodes.update_one({"_id": existing["_id"]}, {"$set": updates})
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
        episode_doc["has_transcript"] = True
        episode_doc["transcript_source"] = transcript_source
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


def _pending_youtube_episodes(db, feed, attempted=()):
    """只补最近 15 期的缺失文稿；本次已尝试的失败视频留待下次刷新。"""
    episodes = db.episodes.find({"feed_id": feed["_id"]}).sort("published", -1).limit(15)
    return [episode for episode in episodes
            if episode["_id"] not in attempted
            and not db.transcripts.find_one({"episode_id": episode["_id"]})]


def _refresh_youtube_channel_feed(db, feed, progress_callback=None, *, queue=task_queue):
    """先保存最近视频列表，再单独排队补元数据和文稿。"""
    if progress_callback:
        progress_callback(10)
    videos, error = YouTubeService.fetch_channel_videos(feed.get("channel_ref"))
    if error:
        db.feeds.update_one({"_id": feed["_id"]}, {"$set": {
            "status": Feed.STATUS_ERROR, "check_error": error, "last_checked": datetime.utcnow(),
        }})
        raise ValueError(error)

    new_count = 0
    for video in videos:
        created = _upsert_video_episode(
            db, feed, f"youtube:{video['video_id']}", video["title"],
            duration=video.get("duration") or 0,
            link=f"https://www.youtube.com/watch?v={video['video_id']}",
            image=video.get("thumbnail", ""),
            author=video.get("author") or feed.get("title", ""),
            published=video.get("published"),
        )
        if created == "created":
            new_count += 1

    total = db.episodes.count_documents({"feed_id": feed["_id"]})
    db.feeds.update_one({"_id": feed["_id"]}, {"$set": {
        "status": Feed.STATUS_ACTIVE,
        "check_error": None,
        "last_checked": datetime.utcnow(),
        "last_updated": datetime.utcnow() if new_count else feed.get("last_updated"),
        "episode_count": total,
    }})
    transcript_task_id = None
    if _pending_youtube_episodes(db, feed):
        transcript_task_id = queue.submit_unique(
            "fetch_transcripts",
            lambda progress_callback=None: _enrich_youtube_episodes(db, feed, progress_callback),
            dedup_key=f"youtube-transcripts:{feed['_id']}",
            feed_id=str(feed["_id"]), owner_id=feed.get("owner_id"),
        )
    if progress_callback:
        progress_callback((100, f"视频列表已更新：新增 {new_count} 期"))
    return {"new_episodes": new_count, "total_episodes": total,
            "transcript_task_id": transcript_task_id}


def _enrich_youtube_episodes(db, feed, progress_callback=None):
    """后台逐期补齐；列表同步不受字幕、封面或单期元数据失败影响。"""
    import time

    attempted = set()
    transcript_count, failed = 0, 0
    while db.feeds.find_one({"_id": feed["_id"]}):
        pending = _pending_youtube_episodes(db, feed, attempted)
        if not pending:
            break
        for episode in pending:
            # 队列等待期间，单篇导入也可能已经保存了文稿。
            if db.transcripts.find_one({"episode_id": episode["_id"]}):
                continue
            attempted.add(episode["_id"])
            video_id = episode["guid"].removeprefix("youtube:")
            time.sleep(2.5)
            if not episode.get("youtube_metadata_fetched_at"):
                metadata, _ = YouTubeService.fetch_metadata(video_id)
                if metadata:
                    thumbnail = metadata.get("thumbnail") or episode.get("image", "")
                    local_thumb = _persist_feed_icon(
                        None, thumbnail, proxy=YouTubeService._proxy(),
                        filename=f"yt_{video_id}.jpg",
                    ) if thumbnail else None
                    updates = {
                        "title": metadata.get("title") or episode["title"],
                        "duration": metadata.get("duration") or episode.get("duration", 0),
                        "author": metadata.get("uploader") or episode.get("author", ""),
                        "image": local_thumb or thumbnail,
                        "youtube_metadata_fetched_at": datetime.utcnow(),
                    }
                    db.episodes.update_one({"_id": episode["_id"]}, {"$set": updates})
            transcript, error = YouTubeService.fetch_transcript(video_id)
            # 删除订阅时不再补入文稿，避免产生孤立记录。
            if not db.episodes.find_one({"_id": episode["_id"]}):
                continue
            if transcript:
                transcript["model"] = "youtube-transcript-api"
                saved = _upsert_video_episode(
                    db, feed, episode["guid"], episode["title"],
                    transcript=transcript, transcript_source=Transcript.SOURCE_YOUTUBE,
                )
                transcript_count += int(saved == "backfilled")
                _clear_episode_subtitle_error(db, episode["_id"])
            else:
                failed += 1
                _mark_episode_subtitle_error(db, episode["_id"], error)
            if progress_callback:
                remaining = len(_pending_youtube_episodes(db, feed, attempted))
                progress_callback((int(95 * len(attempted) / (len(attempted) + remaining)),
                                   f"后台获取文稿 {len(attempted)}/{len(attempted) + remaining}"))
        # 列表刷新可以在本任务运行期间发现新视频，下一轮继续补齐。
    if progress_callback:
        progress_callback((100, f"文稿已更新：{transcript_count} 期，暂不可用 {failed} 期"))
    return {"new_transcripts": transcript_count, "transcript_failures": failed}


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
            image=(video.get("cover", "") or "") + "@480w_270h_1c.webp" if video.get("cover", "").startswith("http") else video.get("cover", ""),
            author=feed.get("title", ""),
            published=published,
            audio_type="video/bilibili",
            transcript=transcript,
            transcript_source=Transcript.SOURCE_BILIBILI,
        )
        ep_doc = db.episodes.find_one({"owner_id": owner_id, "guid": guid})
        if ep_doc:
            if tr_error:
                _mark_episode_subtitle_error(db, ep_doc["_id"], tr_error)
            elif transcript:
                _clear_episode_subtitle_error(db, ep_doc["_id"])

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
