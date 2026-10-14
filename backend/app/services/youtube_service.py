# -*- coding: utf-8 -*-
"""
YouTube 视频源服务

从 YouTube URL 获取视频元数据与字幕，供视频导入管线使用。
字幕走 youtube-transcript-api（不下载视频）；元数据走 yt-dlp。
"""
import logging
import re
from datetime import datetime
from typing import Optional, Tuple
from urllib.parse import unquote, urlparse
from requests import Session

from ..config import Config

logger = logging.getLogger(__name__)


class _TranscriptSession(Session):
    """字幕库没有默认超时，限制代理连接和响应的等待时间。"""
    def request(self, method, url, **kwargs):
        kwargs.setdefault("timeout", (5, 20))
        return super().request(method, url, **kwargs)


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
        parts = urlparse(url or "")
        return parts.hostname in {"youtube.com", "www.youtube.com", "m.youtube.com"} and bool(
            re.fullmatch(r"/(?:@[^/]+|channel/[\w-]+|c/[^/]+|user/[^/]+)(?:/(?:videos|shorts|streams|featured))?/?", unquote(parts.path))
        )

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
            "extract_flat": True,
            "socket_timeout": 15,
            "retries": 1,
            "extractor_retries": 1,
            "proxy": cls._proxy(),
        }
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(unquote(url), download=False, process=False)
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
            ([{video_id, title, published, thumbnail, author}], error)
        """
        import requests as _requests
        import feedparser

        try:
            resp = _requests.get(
                f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}",
                proxies={"http": cls._proxy(), "https": cls._proxy()} if cls._proxy() else None,
                timeout=15,
            )
            resp.raise_for_status()
        except _requests.RequestException as e:
            logger.warning("YouTube channel RSS failed for %s: %s; using uploads playlist", channel_id, e)
            return cls._fetch_channel_uploads(channel_id)

        feed = feedparser.parse(resp.content)
        if not feed.version:
            return cls._fetch_channel_uploads(channel_id)
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
                "thumbnail": (e.get("media_thumbnail") or [{}])[0].get("url", ""),
                "author": e.get("author", ""),
            })
        return videos, None

    @classmethod
    def _fetch_channel_uploads(cls, channel_id: str) -> Tuple[Optional[list], Optional[str]]:
        """RSS 失效时只取上传列表，不逐条解析视频或字幕。"""
        from yt_dlp import YoutubeDL

        opts = {
            "quiet": True, "no_warnings": True, "skip_download": True,
            "extract_flat": True, "playlistend": 15, "socket_timeout": 15,
            "retries": 1, "extractor_retries": 1, "proxy": cls._proxy(),
        }
        try:
            with YoutubeDL(opts) as ydl:
                playlist = ydl.extract_info(
                    f"https://www.youtube.com/playlist?list=UU{channel_id[2:]}", download=False,
                )
                videos = []
                for entry in playlist["entries"]:
                    if not entry:
                        continue
                    timestamp = entry.get("timestamp") or entry.get("release_timestamp")
                    published = datetime.utcfromtimestamp(timestamp) if timestamp else None
                    if not published and entry.get("upload_date"):
                        published = datetime.strptime(entry["upload_date"], "%Y%m%d")
                    videos.append({
                        "video_id": entry["id"], "title": entry.get("title", ""),
                        "published": published,
                        "duration": entry.get("duration") or 0,
                        "thumbnail": (entry.get("thumbnails") or [{}])[-1].get("url", ""),
                        "author": entry.get("channel") or entry.get("uploader", ""),
                    })
                return videos, None
        except Exception as error:
            return None, f"YouTube channel videos failed: {cls._classify_error(error)}"


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
    def _yt_cookie_header(cls) -> Optional[str]:
        cookie = (getattr(Config, "YOUTUBE_COOKIES", "") or "").strip()
        return cookie or None

    @classmethod
    def _write_cookiefile(cls, directory: str) -> Optional[str]:
        """登录态 Cookie 请求头 → Netscape cookies.txt（yt-dlp 用）。

        只投给 .youtube.com 域；过期时间写远期，让所有条目都按持久 Cookie 处理。
        """
        import os

        cookie = cls._yt_cookie_header()
        if not cookie:
            return None
        path = os.path.join(directory, "youtube_cookies.txt")
        lines = ["# Netscape HTTP Cookie File"]
        for item in cookie.split(";"):
            item = item.strip()
            if "=" not in item:
                continue
            name, _, value = item.partition("=")
            lines.append(
                f".youtube.com\tTRUE\t/\tTRUE\t1893456000\t{name.strip()}\t{value.strip()}"
            )
        with open(path, "w", encoding="utf-8") as fh:
            fh.write("\n".join(lines) + "\n")
        return path

    @classmethod
    def fetch_transcript(cls, video_id: str, proxy: str = None) -> Tuple[Optional[dict], Optional[str]]:
        """
        获取视频字幕（优先手动字幕，其次自动字幕）。
        proxy 可指定本机代理端口（并发通道各绑不同出口用）；缺省用 YOUTUBE_PROXY。

        Returns:
            ({text, segments, language}, error)
            segments 与 Whisper 转录结果同构: [{start, end, text}]
        """
        from youtube_transcript_api import YouTubeTranscriptApi
        from youtube_transcript_api.proxies import GenericProxyConfig
        from requests.adapters import HTTPAdapter
        from urllib3.util.retry import Retry

        proxy = proxy or cls._proxy()
        with _TranscriptSession() as session:
            # 字幕请求可重试一次网络断连或 5xx；403/429 不重复打同一个代理。
            retries = Retry(total=1, backoff_factor=0.5, status_forcelist=(500, 502, 503, 504),
                            allowed_methods={"GET", "POST"}, respect_retry_after_header=False,
                            raise_on_status=False)
            session.mount("https://", HTTPAdapter(max_retries=retries))
            session.mount("http://", HTTPAdapter(max_retries=retries))
            api = YouTubeTranscriptApi(
                http_client=session,
                proxy_config=GenericProxyConfig(http_url=proxy, https_url=proxy) if proxy else None,
            )
            try:
                transcript = api.fetch(video_id, languages=["en", "zh-Hans", "zh-Hant", "zh"])
            except Exception as error:
                message = cls._classify_error(error)
                transcript = None  # 主路径失败置空；下方轮换重试成功时会重新赋值
                logger.warning("YouTube transcript fetch failed for %s: %s; trying watchpage fallback", video_id, message)
                fallback, fallback_error = cls._fetch_transcript_watchpage(video_id, proxy=proxy)
                if not fallback:
                    fallback, yt_err = cls._fetch_transcript_ytdlp(video_id, proxy=proxy)
                    fallback_error = fallback_error if fallback else (yt_err or fallback_error)
                if fallback:
                    return fallback, None
                # 连接被掐/限流：轮换 Clash 出口节点换 IP 再试一轮（仅默认代理通道才自动轮换；并发通道由调用方管理节点）
                combined = f"{message}; {fallback_error or ''}"
                if proxy is None and any(token in combined for token in ("无法连接", "Too Many", "429", "timed out")):
                    from ..services import clash_service
                    if clash_service.available():
                        switched = clash_service.rotate_next()
                        if switched:
                            logger.info("YouTube 字幕已换出口节点（%s），重试 %s", switched, video_id)
                            try:
                                transcript = api.fetch(video_id, languages=["en", "zh-Hans", "zh-Hant", "zh"])
                            except Exception:
                                transcript = None
                            if transcript is None:
                                fallback, _ = cls._fetch_transcript_ytdlp(video_id, proxy=proxy)
                                if fallback:
                                    return fallback, None
                            else:
                                pass  # 主库重试成功，落到下方统一转换
                        else:
                            pass
                    else:
                        pass
                if transcript is None:
                    return None, fallback_error or message

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
    def _fetch_transcript_ytdlp(cls, video_id: str, proxy: str = None) -> Tuple[Optional[dict], Optional[str]]:
        """备用字幕路径：yt-dlp 直接下载 VTT 再解析。youtube-transcript-api 的请求会被网络掐断（TLS 指纹），这条路实测可通。"""
        import glob
        import os
        import re
        import tempfile
        from yt_dlp import YoutubeDL

        with tempfile.TemporaryDirectory() as tmp:
            cookie_path = cls._write_cookiefile(tmp)
            opts = {
                "quiet": True, "no_warnings": True, "noprogress": True, "skip_download": True,
                "writesubtitles": True, "writeautomaticsub": True,
                "subtitleslangs": ["en", "zh-Hans", "zh-Hant", "zh"],
                "subtitlesformat": "vtt",
                "proxy": proxy or cls._proxy(),
                "cookiefile": cookie_path,
                # 只取字幕不取流，无可用格式不算失败；带登录态时 mweb 客户端可绕过
                # "Sign in to confirm you're not a bot" 与 ASR 轨 exp=xpe 空响应
                "ignore_no_formats_error": True,
                "outtmpl": os.path.join(tmp, "%(id)s.%(ext)s"),
            }
            if cookie_path:
                opts["extractor_args"] = {"youtube": {"player_client": ["mweb"]}}
            info = None
            try:
                with YoutubeDL(opts) as ydl:
                    info = ydl.extract_info(f"https://www.youtube.com/watch?v={video_id}", download=True)
            except Exception as error:
                message = str(error)
                if "429" in message or "Too Many" in message:
                    return None, "Subtitle download throttled (429)"
                return None, cls._classify_error(error)
            files = glob.glob(os.path.join(tmp, "*.vtt"))
            if not files:
                # 元数据里有字幕轨却没下到文件 → timedtext 下载被限流，不是真没字幕
                if (info or {}).get("automatic_captions") or (info or {}).get("subtitles"):
                    return None, "Subtitle download throttled (429)"
                return None, "No subtitles available for this video"

            def lang_rank(path):
                name = os.path.basename(path)
                for rank, tag in enumerate(("en", "zh-Hans", "zh-Hant", "zh")):
                    if f".{tag}." in name:
                        return rank
                return 99

            files.sort(key=lang_rank)
            vtt_path = files[0]
            language_match = re.search(r"\.([a-zA-Z-]+)\.vtt$", os.path.basename(vtt_path))
            with open(vtt_path, encoding="utf-8", errors="ignore") as fh:
                segments = cls._parse_vtt_segments(fh.read())
            if not segments:
                return None, "Transcript is empty"
            text = " ".join(s["text"] for s in segments)
            return {
                "text": text,
                "segments": segments,
                "language": language_match.group(1) if language_match else "en",
            }, None

    @staticmethod
    def _parse_vtt_segments(content: str) -> list:
        """VTT → [{start, end, text}]：cue 时间轴转秒，去掉 <c> 等内联标签，空行分隔的正文合并为一条。"""
        import re

        cue_pattern = re.compile(
            r"(\d{2}):(\d{2}):(\d{2})[.,]\d{3}\s*-->\s*(\d{2}):(\d{2}):(\d{2})[.,]\d{3}[^\n]*\n((?:(?!\n\n).)*)",
            re.S,
        )
        segments = []
        for m in cue_pattern.finditer(content):
            start = int(m.group(1)) * 3600 + int(m.group(2)) * 60 + int(m.group(3))
            end = int(m.group(4)) * 3600 + int(m.group(5)) * 60 + int(m.group(6))
            lines = [re.sub(r"<[^>]+>", "", line).strip() for line in m.group(7).strip().splitlines()]
            text = " ".join(line for line in lines if line)
            if text:
                segments.append({"start": start, "end": end, "text": text})
        return segments

    @classmethod
    def watchpage_reachable(cls) -> bool:
        """轻量探针：watch 页经默认代理是否可达（补捞前探路用）"""
        from curl_cffi import requests as _creq

        proxy = cls._proxy()
        proxies = {"http": proxy, "https": proxy} if proxy else None
        try:
            resp = _creq.get("https://www.youtube.com/robots.txt",
                             impersonate="chrome", proxies=proxies, timeout=8)
            return resp.status_code == 200
        except Exception:
            return False

    @classmethod
    def _fetch_transcript_watchpage(cls, video_id: str, proxy: str = None) -> Tuple[Optional[dict], Optional[str]]:
        """
        第三层字幕路径：curl_cffi 拉完整 watch 页（chrome 指纹可过 TLS 墙），
        从内嵌的 ytInitialPlayerResponse 取带签名的 timedtext 地址再拉 json3。
        签名约 6 小时有效，取到后立即使用。
        """
        import json as _json
        import re as _re
        from curl_cffi import requests as _creq

        proxies = {"http": proxy or cls._proxy(), "https": proxy or cls._proxy()} if (proxy or cls._proxy()) else None
        cookie = cls._yt_cookie_header()
        headers = {"Cookie": cookie} if cookie else None
        try:
            page = _creq.get(
                f"https://www.youtube.com/watch?v={video_id}",
                impersonate="chrome", proxies=proxies, headers=headers, timeout=25,
            )
        except Exception as error:
            return None, cls._classify_error(error)
        if page.status_code != 200 or "ytInitialPlayerResponse" not in page.text:
            return None, "Watch page unavailable"

        match = _re.search(r"ytInitialPlayerResponse\s*=\s*(\{.+?\});", page.text)
        if not match:
            return None, "No player response in watch page"
        try:
            player = _json.loads(match.group(1))
        except _json.JSONDecodeError:
            return None, "Player response parse error"
        tracks = (((player.get("captions") or {}).get("playerCaptionsTracklistRenderer") or {}).get("captionTracks")) or []
        if not tracks:
            return None, "No subtitles available for this video"

        lang_priority = ["en", "zh-Hans", "zh-Hant", "zh"]
        track = next((t for t in tracks if t.get("languageCode") in lang_priority), tracks[0])
        base_url = track.get("baseUrl", "")
        language = track.get("languageCode", "en")

        for url in (base_url, _re.sub(r"[&?]exp=xpe", "", base_url)):
            if not url:
                continue
            try:
                resp = _creq.get(url + "&fmt=json3", impersonate="chrome",
                                 proxies=proxies, headers=headers, timeout=20)
                if resp.status_code != 200 or not resp.text.strip():
                    continue
                segments = cls._parse_json3_segments(resp.text)
                if segments:
                    return {"text": " ".join(s["text"] for s in segments),
                            "segments": segments, "language": language}, None
            except Exception:
                continue
        return None, "Caption track download failed"

    @staticmethod
    def _parse_json3_segments(body: str) -> list:
        """YouTube json3 字幕 → [{start, end, text}]"""
        import json as _json

        try:
            data = _json.loads(body)
        except _json.JSONDecodeError:
            return []
        segments = []
        for event in data.get("events", []):
            start_ms = event.get("tStartMs")
            if start_ms is None:
                continue
            text = "".join(seg.get("utf8", "") for seg in event.get("segs", [])).strip()
            if not text:
                continue
            segments.append({
                "start": int(start_ms / 1000),
                "end": int((start_ms + event.get("dDurationMs", 0)) / 1000),
                "text": text,
            })
        return segments

    @classmethod
    def fetch_metadata(cls, video_id: str) -> Tuple[Optional[dict], Optional[str]]:
        """
        获取视频元数据（标题、时长、作者、封面、真实发布日期和简介）。

        Returns:
            ({title, duration, uploader, thumbnail, published, description}, error)
        """
        from yt_dlp import YoutubeDL

        opts = {
            "quiet": True,
            "no_warnings": True,
            "skip_download": True,
            "proxy": cls._proxy(),
            "socket_timeout": 15,
            "retries": 1,
            "extractor_retries": 1,
        }

        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(
                    f"https://www.youtube.com/watch?v={video_id}", download=False
                )
        except Exception as e:
            return None, cls._classify_error(e)

        timestamp = info.get("timestamp") or info.get("release_timestamp")
        published = datetime.utcfromtimestamp(timestamp) if timestamp else None
        if not published and info.get("upload_date"):
            published = datetime.strptime(info["upload_date"], "%Y%m%d")

        return {
            "title": info.get("title") or video_id,
            "duration": int(info.get("duration") or 0),
            "uploader": info.get("uploader") or "",
            "thumbnail": info.get("thumbnail") or "",
            "published": published,
            "description": info.get("description") or "",
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
        known_errors = {
            "TranscriptsDisabled": "YouTube 暂未返回该视频的字幕（可能未生成或已禁用），可稍后重试或使用本地转写。",
            "NoTranscriptFound": "该视频没有可获取的中英文字幕，可使用本地转写。",
            "VideoUnavailable": "该 YouTube 视频已删除、设为私密或无法访问。",
            "InvalidVideoId": "YouTube 视频 ID 无效。",
            "AgeRestricted": "该 YouTube 视频有年龄限制，当前字幕接口无法访问。",
            "RequestBlocked": "YouTube 暂时限制了字幕请求，请稍后重试或切换代理节点。",
            "IpBlocked": "YouTube 暂时限制了当前代理的访问，请稍后重试或切换代理节点。",
            "PoTokenRequired": "YouTube 要求额外的视频访问验证，当前字幕接口无法获取此视频。",
        }
        if name in known_errors:
            return known_errors[name]
        # 字幕库的第一行只是通用开头；真正的原因放在 cause 中。
        message = getattr(error, "cause", None) or str(error)
        if Config.YOUTUBE_PROXY:
            message = message.replace(Config.YOUTUBE_PROXY, "<configured proxy>")
        if "NoTranscript" in name or "NotFound" in name:
            return "No transcript available for this video"
        # SSL 断连/超时基本是代理节点问题（Google 全域被掐），给出可操作的提示
        if "SSL" in message or "EOF" in message or "timed out" in message.lower() or "Connection" in message or name in {"ConnectionError", "ProxyError", "ReadTimeout", "ConnectTimeout"}:
            return "无法连接 YouTube，请检查代理节点或网络后重试。"
        detail = " ".join(message.split()) or name
        return f"YouTube 获取失败（{name}）：{detail}"

def persist_transcript(db, episode: dict, transcript: dict) -> bool:
    """把抓到的 YouTube 字幕落库（幂等：已有 transcript 则跳过）——刷新补捞与手动补捞共用。"""
    from datetime import datetime as _dt

    from ..models.episode import Episode
    from ..models.transcript import Transcript

    updates = {"has_transcript": True, "transcript_source": "youtube",
               "transcript_fetch_error": None, "updated_at": _dt.utcnow()}
    if episode.get("status") not in (Episode.STATUS_SUMMARIZED, Episode.STATUS_SUMMARIZING):
        updates["status"] = Episode.STATUS_TRANSCRIBED
    if db.transcripts.find_one({"episode_id": episode["_id"]}):
        # 字幕已在库但剧集标记缺失（历史残留）：补标记即可，否则会被反复判缺、反复重抓
        db.episodes.update_one({"_id": episode["_id"], "has_transcript": {"$ne": True}}, {"$set": updates})
        return False
    db.transcripts.insert_one(Transcript.create(
        episode_id=episode["_id"], owner_id=episode.get("owner_id"),
        text=transcript["text"], segments=transcript["segments"],
        language=transcript.get("language", ""), source="youtube", model=""))
    db.episodes.update_one({"_id": episode["_id"]}, {"$set": updates})
    return True
