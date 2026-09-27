# -*- coding: utf-8 -*-
"""
YouTube 视频源服务

从 YouTube URL 获取视频元数据与字幕，供视频导入管线使用。
字幕走 youtube-transcript-api（不下载视频）；元数据走 yt-dlp。
"""
import logging
import re
from typing import Optional, Tuple

from ..config import Config

logger = logging.getLogger(__name__)


class YouTubeService:
    """YouTube 元数据与字幕获取"""

    VIDEO_ID_PATTERN = re.compile(
        r"(?:v=|youtu\.be/|shorts/|embed/|live/)([A-Za-z0-9_-]{11})|^([A-Za-z0-9_-]{11})$"
    )

    @classmethod
    def extract_video_id(cls, url_or_id: str) -> Optional[str]:
        """从 URL 或裸 id 中解析 11 位视频 id"""
        m = cls.VIDEO_ID_PATTERN.search((url_or_id or "").strip())
        if not m:
            return None
        return m.group(1) or m.group(2)

    @classmethod
    def _proxy(cls) -> Optional[str]:
        proxy = Config.YOUTUBE_PROXY
        return proxy if proxy else None

    @classmethod
    def fetch_transcript(cls, video_id: str) -> Tuple[Optional[dict], Optional[str]]:
        """
        获取视频字幕（优先手动字幕，其次自动字幕）。

        Returns:
            ({text, segments, language}, error)
            segments 与 Whisper 转录结果同构: [{start, end, text}]
        """
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api.proxies import GenericProxyConfig

        proxy = cls._proxy()
        api = YouTubeTranscriptApi(
            proxy_config=GenericProxyConfig(http_url=proxy, https_url=proxy) if proxy else None
        )

        try:
            transcript = api.fetch(video_id, languages=["en", "zh-Hans", "zh-Hant", "zh"])
        except Exception as e:
            return None, cls._classify_error(e)

        segments = [
            {"start": s.start, "end": s.start + s.duration, "text": s.text.strip()}
            for s in transcript.snippets
            if s.text.strip()
        ]
        if not segments:
            return None, "Transcript is empty"

        text = " ".join(s["text"] for s in segments)
        return {
            "text": text,
            "segments": segments,
            "language": transcript.language_code,
        }, None

    @classmethod
    def fetch_metadata(cls, video_id: str) -> Tuple[Optional[dict], Optional[str]]:
        """
        获取视频元数据（标题、时长、作者、封面）。

        Returns:
            ({title, duration, uploader, thumbnail}, error)
        """
        from yt_dlp import YoutubeDL

        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "proxy": cls._proxy(),
        }

        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={video_id}", download=False
                )
        except Exception as e:
            return None, cls._classify_error(e)

        return {
            "title": info.get("title") or video_id,
            "duration": int(info.get("duration") or 0),
            "uploader": info.get("uploader") or "",
            "thumbnail": info.get("thumbnail") or "",
        }, None

    @staticmethod
    def _classify_error(error: Exception) -> str:
        name = type(error).__name__
        if "NoTranscript" in name or "NotFound" in name:
            return "No transcript available for this video"
        if "Blocked" in name or "Request" in name:
            return f"YouTube rejected the request ({name}); check YOUTUBE_PROXY"
        message = str(error).strip().splitlines()[0] if str(error).strip() else name
        return f"YouTube fetch failed: {message}"
