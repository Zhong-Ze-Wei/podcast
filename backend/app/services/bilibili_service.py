# -*- coding: utf-8 -*-
"""
Bilibili 视频源服务

支持订阅 UP 主：wbi 签名拉取投稿列表、获取 AI 字幕（带串台校验）。
登录态由 BILI_SESSDATA 配置提供（用户从浏览器 Cookie 手动复制）。
wbi 签名算法参考公开文档 bilibili-API-collect。
"""
import hashlib
import logging
import re
import time
from typing import Optional, Tuple

from ..config import Config

logger = logging.getLogger(__name__)

# wbi mixin key 排列表（公开文档 bilibili-API-collect）
MIXIN_KEY_ENC_TAB = [
    46, 47, 18, 2, 53, 8, 23, 32, 15, 50, 10, 31, 58, 3, 45, 35, 27, 43, 5, 49,
    33, 9, 42, 19, 29, 28, 14, 39, 12, 38, 41, 13, 37, 48, 7, 16, 24, 55, 40,
    61, 26, 17, 0, 1, 60, 51, 30, 4, 22, 25, 54, 21, 56, 59, 6, 63, 57, 62, 11,
    36, 20, 34, 44, 52,
]


class BilibiliService:
    """B站 UP 主订阅与 AI 字幕获取"""

    API_BASE = "https://api.bilibili.com"
    UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

    SPACE_PATTERN = re.compile(r"space\.bilibili\.com/(\d+)")

    _wbi_key_cache = {"key": None, "fetched_at": 0}
    _buvid_cache = {"key": None, "buvid": ""}

    # ------------------------------------------------------------------
    # 基础请求（curl_cffi 函数级调用：B站封 python-requests 的 TLS 指纹，
    # 且 curl_cffi Session 在工作线程中不可用，故每次请求独立发起）
    # ------------------------------------------------------------------

    _warmed_up = False

    @classmethod
    def warmup(cls):
        """主线程触发 curl_cffi 全局初始化。

        curl_cffi 的 TLS 全局状态若首次初始化发生在工作线程，
        之后所有子线程请求都会拿到空响应；必须在主线程先发一次请求。
        """
        if cls._warmed_up:
            return
        cls._warmed_up = True
        try:
            from curl_cffi import requests as curl_requests

            curl_requests.get("https://www.bilibili.com/", impersonate="chrome", timeout=5)
        except Exception as e:
            logger.warning(f"Bilibili curl_cffi warmup failed: {e}")

    @classmethod
    def _cookies(cls) -> dict:
        sd = Config.BILI_SESSDATA
        cookies = {"SESSDATA": sd} if sd else {}
        if cls._buvid_cache["key"] == sd and cls._buvid_cache["buvid"]:
            cookies["buvid3"] = cls._buvid_cache["buvid"]
            return cookies

        try:
            from curl_cffi import requests as curl_requests

            warm = curl_requests.get("https://www.bilibili.com/", impersonate="chrome", timeout=10)
            buvid = warm.cookies.get("buvid3") or ""
        except Exception:
            buvid = ""
        cls._buvid_cache = {"key": sd, "buvid": buvid}
        if buvid:
            cookies["buvid3"] = buvid
        return cookies

    @classmethod
    def _fetch_json(cls, url: str, params: dict = None, referer: str = "https://www.bilibili.com/"):
        from curl_cffi import requests as curl_requests

        return curl_requests.get(
            url, params=params, impersonate="chrome",
            cookies=cls._cookies(), headers={"Referer": referer}, timeout=15,
        )

    @classmethod
    def _get(cls, path: str, params: dict = None, referer: str = "https://www.bilibili.com/") -> Tuple[Optional[dict], Optional[str]]:
        try:
            resp = cls._fetch_json(f"{cls.API_BASE}{path}", params=params, referer=referer)
            data = resp.json()
        except Exception as e:
            return None, f"Bilibili request failed: {e}"

        if data.get("code") != 0:
            code = data.get("code")
            if code == -101:
                return None, "Bilibili login required (check BILI_SESSDATA)"
            if code == -403:
                return None, "Bilibili access denied (-403); SESSDATA may be expired"
            return None, f"Bilibili API error {code}: {data.get('message', '')}"
        return data.get("data"), None

    # ------------------------------------------------------------------
    # wbi 签名
    # ------------------------------------------------------------------

    @classmethod
    def _get_mixin_key(cls) -> Optional[str]:
        if not Config.BILI_SESSDATA:
            return None
        cached = cls._wbi_key_cache
        if cached["key"] and time.time() - cached["fetched_at"] < 3600:
            return cached["key"]

        data, error = cls._get("/x/web-interface/nav")
        if error or not data:
            logger.warning(f"Failed to fetch wbi keys: {error}")
            return None

        img_key = (data.get("wbi_img", {}).get("img_url", "").rsplit("/", 1)[-1].split(".")[0])
        sub_key = (data.get("wbi_img", {}).get("sub_url", "").rsplit("/", 1)[-1].split(".")[0])
        raw = img_key + sub_key
        mixin_key = "".join(raw[i] for i in MIXIN_KEY_ENC_TAB)[:32]
        cls._wbi_key_cache = {"key": mixin_key, "fetched_at": time.time()}
        return mixin_key

    @classmethod
    def _wbi_sign(cls, params: dict) -> Optional[dict]:
        mixin_key = cls._get_mixin_key()
        if not mixin_key:
            return None
        signed = dict(params)
        signed["wts"] = int(time.time())
        pairs = []
        for k in sorted(signed):
            value = re.sub("[!'()*]", "", str(signed[k]))
            pairs.append(f"{k}={value}")
        signed["w_rid"] = hashlib.md5(("&".join(pairs) + mixin_key).encode()).hexdigest()
        return signed

    # ------------------------------------------------------------------
    # 订阅能力
    # ------------------------------------------------------------------

    @classmethod
    def extract_space_id(cls, url: str) -> Optional[str]:
        m = cls.SPACE_PATTERN.search(url or "")
        return m.group(1) if m else None

    @classmethod
    def fetch_uploader_info(cls, mid: str) -> Tuple[Optional[dict], Optional[str]]:
        """UP 主公开信息（无需登录）"""
        data, error = cls._get("/x/web-interface/card", {"mid": mid, "photo": "false"})
        if error:
            return None, error
        card = data.get("card", {})
        return {
            "mid": mid,
            "name": card.get("name", ""),
            "sign": card.get("sign", ""),
            "face": card.get("face", ""),
        }, None

    @classmethod
    def fetch_uploader_videos(cls, mid: str, ps: int = 30) -> Tuple[Optional[list], Optional[str]]:
        """UP 主最新投稿列表（需 wbi 签名 + SESSDATA）"""
        signed = cls._wbi_sign({
            "mid": mid, "ps": ps, "pn": 1,
            "order": "pubdate", "platform": "web", "web_location": "1550101",
        })
        if not signed:
            return None, "Bilibili login required (check BILI_SESSDATA)"

        data, error = cls._get(
            "/x/space/wbi/arc/search", signed,
            referer=f"https://space.bilibili.com/{mid}/video",
        )
        if error:
            return None, error

        vlist = data.get("list", {}).get("vlist", [])
        videos = [{
            "bvid": v["bvid"],
            "title": v["title"],
            "published": v.get("created"),
            "duration": cls._parse_length(v.get("length", "")),
            "description": v.get("description", ""),
            "cover": v.get("pic", ""),
        } for v in vlist]
        return videos, None

    @classmethod
    def fetch_video_meta(cls, bvid: str) -> Tuple[Optional[dict], Optional[str]]:
        """视频元数据（公开，含 aid/cid）"""
        data, error = cls._get("/x/web-interface/view", {"bvid": bvid})
        if error:
            return None, error
        return {
            "aid": data["aid"],
            "cid": data["cid"],
            "bvid": bvid,
            "title": data.get("title", bvid),
            "duration": int(data.get("duration") or 0),
            "cover": data.get("pic", ""),
            "uploader": data.get("owner", {}).get("name", ""),
        }, None

    @classmethod
    def fetch_ai_subtitle(cls, bvid: str, title: str = "") -> Tuple[Optional[dict], Optional[str]]:
        """
        获取视频 AI 中文字幕（需 SESSDATA）。

        内置串台校验（B站 AI 字幕系统存在字幕关联错乱，实测同 UP 主
        多个视频返回同一份字幕、或返回完全不相关内容）：
        1. 时间轴不得超过视频时长 5%，行密度不低于每 60 秒 1 行
        2. 字幕与标题的词窗命中率不低于 18%（词窗过少时跳过）
        """
        meta, error = cls.fetch_video_meta(bvid)
        if error:
            return None, error
        duration = meta["duration"]

        # 用官方播放器同款的 wbi 签名接口：旧 player/v2 返回脏缓存（实测串台）
        signed = cls._wbi_sign({"aid": meta["aid"], "cid": meta["cid"]})
        if not signed:
            return None, "Bilibili login required (check BILI_SESSDATA)"
        data, error = cls._get("/x/player/wbi/v2", signed)
        if error:
            return None, error

        subtitles = (data.get("subtitle") or {}).get("subtitles") or []
        zh = next((s for s in subtitles if s.get("lan") == "ai-zh"), None)
        if not zh:
            return None, "No AI subtitle available"

        url = zh.get("subtitle_url", "")
        if url.startswith("//"):
            url = "https:" + url
        try:
            from curl_cffi import requests as curl_requests

            resp = curl_requests.get(
                url, impersonate="chrome",
                headers={"Referer": "https://www.bilibili.com/"}, timeout=15,
            )
            doc = resp.json()
        except Exception as e:
            return None, f"Subtitle download failed: {e}"

        lines = doc.get("body") or []
        if not lines:
            return None, "AI subtitle is empty"

        # 校验一：时间轴越界、行密度或行均字数异常（串台字幕常为短视频内容，
        # 每行仅一两个字、总行数撑不满长视频时长）
        max_to = max((l.get("to", 0) for l in lines), default=0)
        if duration and max_to > duration * 1.05:
            return None, "AI subtitle rejected: timeline exceeds video duration (mismatched subtitle)"
        if duration and len(lines) < duration / 60:
            return None, "AI subtitle rejected: too sparse (possible mismatched subtitle)"
        avg_chars = sum(len(str(l.get("content", ""))) for l in lines) / max(len(lines), 1)
        if avg_chars < 2:
            return None, "AI subtitle rejected: lines too short (possible mismatched subtitle)"

        segments = [{"start": float(l["from"]), "end": float(l["to"]), "text": str(l["content"]).strip()}
                    for l in lines if str(l.get("content", "")).strip()]
        text = " ".join(s["text"] for s in segments)

        # 校验二：标题词窗命中率（正常剧集实测 ≥30%，串台 ≤14%，阈值取 18%）
        windows = cls._title_windows(title)
        if len(windows) >= 6:
            hits = sum(1 for w in windows if w in text)
            if hits / len(windows) < 0.18:
                return None, "AI subtitle rejected: content does not match video title (mismatched subtitle)"

        return {"text": text, "segments": segments, "language": "zh"}, None

    @staticmethod
    def _title_windows(title: str) -> set:
        """标题清洗后提取 3/2 字滑窗词组，用于字幕内容相关性校验"""
        clean = re.sub(r"[｜|【】「」·:：,，。!！?？\s0-9a-zA-Z]+", "", title or "")
        windows = set()
        for n in (3, 2):
            for i in range(len(clean) - n + 1):
                windows.add(clean[i:i + n])
        return windows

    @classmethod
    def download_audio(cls, bvid: str) -> Tuple[Optional[str], Optional[str]]:
        """
        下载视频音轨到媒体目录（m4a，直连不走代理）。

        Returns:
            (本地文件绝对路径, error)
        """
        from yt_dlp import YoutubeDL
        from ..config import Config
        import os

        audio_dir = Config.AUDIO_DIR
        os.makedirs(audio_dir, exist_ok=True)
        outtmpl = os.path.join(audio_dir, f"bili_{bvid}.%(ext)s")

        opts = {
            "format": "bestaudio/best",
            "outtmpl": outtmpl,
            "quiet": True,
            "no_warnings": True,
            "noplaylist": True,
        }
        try:
            with YoutubeDL(opts) as ydl:
                info = ydl.extract_info(f"https://www.bilibili.com/video/{bvid}", download=True)
        except Exception as e:
            first_line = str(e).strip().splitlines()[0] if str(e).strip() else str(e)
            return None, f"Bilibili audio download failed: {first_line}"

        path = info.get("requested_downloads", [{}])[0].get("filepath")
        return path, None

    @staticmethod
    def _parse_length(length: str) -> int:
        """'HH:MM:SS' 或 'MM:SS' 转秒"""
        parts = (length or "").split(":")
        try:
            return sum(int(p) * 60 ** i for i, p in enumerate(reversed(parts)))
        except ValueError:
            return 0
