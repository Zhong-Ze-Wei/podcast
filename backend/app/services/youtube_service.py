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

    CHANNEL_URL_PATTERN = re.compile(
        r"youtube\.com/(@[\w.-]+|channel/[\w-]+|c/[\w.-]+)"
    )

    @classmethod
    def is_channel_url(cls, url: str) -> bool:
        return bool(cls.CHANNEL_URL_PATTERN.search(url or ""))

    @classmethod
    def resolve_channel(cls, url: str) -> Tuple[Optional[dict], Optional[str]]:
        """
        解析频道主页 URL（@handle / channel/UC.. / c/..）。

        Returns:
            ({channel_id, title}, error)
        """
        from yt_dlp import YoutubeDL

        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "playlist_items": "1",
            "proxy": cls._proxy(),
        }
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(url, download=False)
        except Exception as e:
            return None, cls._classify_error(e)

        channel_id = info.get("channel_id") or info.get("id")
        if not channel_id:
            return None, "Could not resolve YouTube channel"

        # 频道头像：thumbnails 里优先取正方形，否则取最小的一张
        avatar = ""
        thumbs = [t for t in (info.get("thumbnails") or []) if t.get("url")]
        square = next((t for t in thumbs if t.get("width") == t.get("height")), None)
        avatar = (square or (min(thumbs, key=lambda t: t.get("width") or 9999) if thumbs else {}) or {}).get("url", "")

        return {
            "channel_id": channel_id,
            "title": info.get("channel") or info.get("uploader") or "",
            "avatar": avatar,
        }, None

    @classmethod
    def fetch_channel_videos(cls, channel_id: str) -> Tuple[Optional[list], Optional[str]]:
        """
        频道最新视频列表（官方 RSS，最近 15 条）。

        Returns:
            ([{video_id, title, published}], error)
        """
        import requests as _requests
        import feedparser

        try:
            resp = _requests.get(
                f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}",
                proxies={"http": cls._proxy(), "https": cls._proxy()} if cls._proxy() else None,
                timeout=15,
            )
        except _requests.RequestException as e:
            return None, f"YouTube channel RSS failed: {e}"

        feed = feedparser.parse(resp.content)
        from datetime import datetime as _dt

        videos = []
        for e in feed.entries:
            if not getattr(e, "yt_videoid", ""):
                continue
            published = None
            parsed = getattr(e, "published_parsed", None)
            if parsed:
                published = _dt(*parsed[:6])
            videos.append({
                "video_id": e.yt_videoid,
                "title": getattr(e, "title", ""),
                "published": published,
            })
        return videos, None

    # 音频直链缓存 {video_id: (url, expires_at)}——直链带签名有时效
    _stream_url_cache = {}

    @classmethod
    def resolve_stream_url(cls, video_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        解析音频直链（不下载），供在线流播放代理转发。

        Returns:
            (url, error)
        """
        import time as _time
        from yt_dlp import YoutubeDL

        cached = cls._stream_url_cache.get(video_id)
        if cached and cached[1] > _time.time():
            return cached[0], None

        opts = {
            "quiet": True,
            "no_warnings": True,
            "format": "bestaudio[ext=m4a]/bestaudio/best",
            "proxy": cls._proxy(),
        }
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={video_id}", download=False
                )
        except Exception as e:
            return None, cls._classify_error(e)

        url = (info or {}).get("url")
        if not url:
            return None, "Could not resolve audio stream URL"

        # 直链有效期通常约 6 小时，缓存 2 小时留足余量
        cls._stream_url_cache[video_id] = (url, _time.time() + 2 * 3600)
        return url, None

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

    @classmethod
    def download_audio(cls, video_id: str) -> Tuple[Optional[str], Optional[str]]:
        """
        下载视频音轨到媒体目录（m4a，不做转码——whisper 原生支持）。

        Returns:
            (本地文件绝对路径, error)
        """
        from yt_dlp import YoutubeDL
        from ..config import Config
        import os

        audio_dir = Config.AUDIO_DIR
        os.makedirs(audio_dir, exist_ok=True)
        outtmpl = os.path.join(audio_dir, f"yt_{video_id}.%(ext)s")

        opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
            "proxy": cls._proxy(),
        }
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={video_id}", download=True
                )
        except Exception as e:
            return None, cls._classify_error(e)

        path = info.get("requested_downloads", [{}])[0].get("filepath")
        return path, None

    @staticmethod
    def _classify_error(error: Exception) -> str:
        name = type(error).__name__
        message = str(error)
        if "NoTranscript" in name or "NotFound" in name:
            return "No transcript available for this video"
        if "Blocked" in name or "Request" in name:
            return f"YouTube rejected the request ({name}); check YOUTUBE_PROXY"
        # SSL 断连/超时基本是代理节点问题（Google 全域被掐），给出可操作的提示
        if "SSL" in message or "EOF" in message or "timed out" in message.lower() or "Connection" in message:
            proxy = Config.YOUTUBE_PROXY or "direct"
            return f"无法通过代理连接 YouTube（{proxy}）——请检查代理节点是否可用后再试"
        first_line = message.strip().splitlines()[0] if message.strip() else name
        return f"YouTube fetch failed: {first_line}"
