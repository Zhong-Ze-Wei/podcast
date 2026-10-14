# -*- coding: utf-8 -*-
"""带登录态 Cookie 的串行补捞：吃掉存量无字幕 YouTube 剧集。

设计要点（保护账号）：
- 单通道串行（默认 YOUTUBE_PROXY 出口），不做多路并发
- 每集之间 sleep 间隔，失败也记录后继续
- 幂等：已有 transcript 的剧集跳过；每集取前重新查库确认仍缺字幕

用法: .venv/Scripts/python.exe scripts/backfill_with_cookies.py [--limit N] [--sleep S]
"""
import argparse
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from app import create_app, get_db
from app.services.youtube_service import YouTubeService, persist_transcript
from app.services import clash_service

app = create_app()

THROTTLE_TOKENS = ("429", "Too Many", "throttled", "无法连接", "timed out")


def throttled(error: str) -> bool:
    return any(token in (error or "") for token in THROTTLE_TOKENS)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="最多处理多少集，0=全部")
    parser.add_argument("--sleep", type=float, default=5.0, help="每集间隔秒数")
    args = parser.parse_args()

    with app.app_context():
        db = get_db()
        if not YouTubeService._yt_cookie_header():
            print("ABORT: YOUTUBE_COOKIES 未配置")
            return
        query = {"audio_type": "video/youtube", "has_transcript": {"$ne": True},
                 "guid": {"$regex": "^youtube:"}}
        total_stuck = db.episodes.count_documents(query)
        cursor = db.episodes.find(query).sort("published", 1)
        ok = fail = skipped = 0
        rotate_every = 4  # 每成功 N 集换一个出口，摊薄单 IP 的 timedtext 配额
        print(f"stuck episodes: {total_stuck} (limit={args.limit or 'all'})", flush=True)
        for episode in cursor:
            if args.limit and ok + fail >= args.limit:
                break
            # 取前重查：可能被自动补捞先处理掉了
            fresh = db.episodes.find_one({"_id": episode["_id"], "has_transcript": {"$ne": True}})
            if not fresh:
                skipped += 1
                continue
            video_id = episode["guid"].split(":", 1)[1]
            title = episode["title"][:50]
            result, error = YouTubeService.fetch_transcript(video_id)
            if result:
                persist_transcript(db, episode, result)
                ok += 1
                print(f"[{ok + fail}] OK   {title} | segs={len(result['segments'])}", flush=True)
                if ok % rotate_every == 0 and clash_service.available():
                    switched = clash_service.rotate_next()
                    if switched:
                        print(f"    proactive rotate -> {switched}", flush=True)
            else:
                fail += 1
                db.episodes.update_one(
                    {"_id": episode["_id"]},
                    {"$set": {"transcript_fetch_error": error[:500]}},
                )
                print(f"[{ok + fail}] FAIL {title} | {error[:100]}", flush=True)
                # 被限流时不重试原视频（会加深它的限流），换出口让下一集走新 IP
                if throttled(error) and clash_service.available():
                    switched = clash_service.rotate_next()
                    if switched:
                        print(f"    throttled -> rotate exit to {switched}, next episode", flush=True)
            time.sleep(args.sleep)
        remaining = db.episodes.count_documents(query)
        print(f"DONE ok={ok} fail={fail} skipped={skipped} remaining={remaining}", flush=True)


if __name__ == "__main__":
    main()
