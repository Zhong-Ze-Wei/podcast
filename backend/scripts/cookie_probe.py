# -*- coding: utf-8 -*-
"""单集验证：YOUTUBE_COOKIES 是否击穿 bot 验证墙。用法: .venv/Scripts/python.exe scripts/cookie_probe.py [video_id]"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), ".env"))

from app.config import Config
from app import create_app
from app.services.youtube_service import YouTubeService

app = create_app()


def main():
    video_id = sys.argv[1] if len(sys.argv) > 1 else None
    if not video_id:
        with app.app_context():
            from app import get_db
            db = get_db()
            stuck = db.episodes.find_one(
                {"audio_type": "video/youtube", "has_transcript": {"$ne": True},
                 "guid": {"$regex": "^youtube:"}},
                sort=[("published", -1)],
            )
        if not stuck:
            print("NO_STUCK_EPISODE")
            return
        video_id = stuck["guid"].split(":", 1)[1]
        print(f"probe episode: {stuck['title'][:60]} | video_id={video_id}")

    print(f"cookies configured: {bool(YouTubeService._yt_cookie_header())}, proxy={Config.YOUTUBE_PROXY or 'direct'}")
    result, error = YouTubeService.fetch_transcript(video_id)
    if result:
        segs = result["segments"]
        print(f"OK lang={result['language']} segments={len(segs)} chars={len(result['text'])}")
        print("head:", result["text"][:120].replace("\n", " "))
    else:
        print(f"FAIL: {error}")


if __name__ == "__main__":
    main()
