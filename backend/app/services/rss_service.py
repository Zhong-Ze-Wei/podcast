# -*- coding: utf-8 -*-
"""
RSS解析服务

负责解析RSS Feed，提取播客和单集信息
"""
import feedparser
import requests
import re
from datetime import datetime
from typing import Tuple, Optional
from email.utils import parsedate_to_datetime
import logging

logger = logging.getLogger(__name__)


class RSSService:
    """RSS解析服务"""

    # 模拟浏览器的User-Agent
    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    # 请求头
    HEADERS = {
        "User-Agent": USER_AGENT,
        "Accept": "application/rss+xml, application/xml, text/xml, */*",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
        "Accept-Encoding": "gzip, deflate",
        "Connection": "keep-alive",
    }

    @classmethod
    def parse_feed(cls, rss_url: str, timeout: int = 30) -> Tuple[Optional[dict], Optional[str]]:
        """
        解析RSS Feed

        Args:
            rss_url: RSS地址
            timeout: 超时时间(秒)

        Returns:
            (feed_info, error_message)
            成功返回 (feed_info, None)
            失败返回 (None, error_message)
        """
        try:
            # 使用requests获取RSS内容 (更好的浏览器模拟)
            response = requests.get(rss_url, headers=cls.HEADERS, timeout=timeout)
            response.raise_for_status()

            # 解析RSS内容
            feed = feedparser.parse(response.content)

            # 检查解析错误
            if feed.bozo and not feed.entries:
                error = str(feed.bozo_exception) if hasattr(feed, "bozo_exception") else "Unknown parse error"
                return None, f"RSS parse error: {error}"

            # 检查是否有内容
            if not feed.feed.get("title") and not feed.entries:
                return None, "Invalid RSS feed: no title or entries found"

            # 提取Feed信息
            feed_info = cls._extract_feed_info(feed)
            feed_info["rss_url"] = rss_url

            # 提取Episodes
            episodes = cls._extract_episodes(feed)
            feed_info["episodes"] = episodes
            feed_info["episode_count"] = len(episodes)

            return feed_info, None

        except Exception as e:
            logger.exception(f"Failed to parse RSS: {rss_url}")
            return None, f"Failed to parse RSS: {str(e)}"

    @classmethod
    def _extract_feed_info(cls, feed) -> dict:
        """提取Feed基本信息"""
        f = feed.feed

        # 提取图片
        image = None
        if f.get("image"):
            if isinstance(f["image"], dict):
                image = f["image"].get("href") or f["image"].get("url")
            else:
                image = str(f["image"])

        # iTunes图片 (通常是高清)
        if not image and f.get("itunes_image"):
            if isinstance(f["itunes_image"], dict):
                image = f["itunes_image"].get("href")
            else:
                image = str(f["itunes_image"])

        return {
            "title": f.get("title", ""),
            "website": f.get("link", ""),
            "description": cls._clean_html(f.get("description", "") or f.get("subtitle", "")),
            "author": f.get("author", "") or f.get("itunes_author", ""),
            "language": f.get("language", ""),
            "image": image or "",
            "generator": f.get("generator", ""),
        }

    @classmethod
    def _extract_episodes(cls, feed) -> list:
        """提取所有单集信息"""
        episodes = []

        for entry in feed.entries:
            episode = cls._extract_episode(entry)
            if episode and episode.get("audio_url"):
                episodes.append(episode)

        return episodes

    @classmethod
    def _extract_episode(cls, entry) -> Optional[dict]:
        """提取单个Episode信息"""
        # 获取guid
        guid = entry.get("id") or entry.get("guid") or entry.get("link")
        if not guid:
            return None

        # 获取音频URL (从enclosures)
        audio_url = None
        audio_type = "audio/mpeg"
        audio_size = 0

        if hasattr(entry, "enclosures") and entry.enclosures:
            for enc in entry.enclosures:
                enc_type = enc.get("type", "")
                if enc_type.startswith("audio/") or enc.get("href", "").endswith((".mp3", ".m4a", ".wav", ".ogg")):
                    audio_url = enc.get("href") or enc.get("url")
                    audio_type = enc_type or "audio/mpeg"
                    audio_size = int(enc.get("length", 0) or 0)
                    break

        # 如果没有enclosure，尝试其他来源
        if not audio_url:
            # 尝试media_content
            if hasattr(entry, "media_content") and entry.media_content:
                for media in entry.media_content:
                    if media.get("type", "").startswith("audio/"):
                        audio_url = media.get("url")
                        audio_type = media.get("type", "audio/mpeg")
                        break

        # 解析发布时间
        published = None
        if entry.get("published_parsed"):
            try:
                published = datetime(*entry.published_parsed[:6])
            except Exception:
                pass
        elif entry.get("published"):
            try:
                published = parsedate_to_datetime(entry.published)
            except Exception:
                pass

        # 解析时长
        duration = cls._parse_duration(
            entry.get("itunes_duration") or
            entry.get("duration") or
            entry.get("itunes:duration")
        )

        # 提取图片
        image = None
        if entry.get("image"):
            if isinstance(entry["image"], dict):
                image = entry["image"].get("href")
            else:
                image = str(entry["image"])

        # 提取完整内容 (content字段通常包含更详细的HTML)
        content = None
        if hasattr(entry, "content") and entry.content:
            content = cls._clean_html(entry.content[0].value)

        # 简短摘要 (清理广告链接等)
        summary = cls._clean_summary(entry.get("summary", "") or entry.get("description", ""))

        # 章节信息 (Podcasting 2.0)
        chapters_url = None
        if entry.get("podcast_chapters"):
            chapters_url = entry["podcast_chapters"].get("url") if isinstance(entry["podcast_chapters"], dict) else entry["podcast_chapters"]

        # 转录链接 (Podcasting 2.0)
        transcript_url = None
        if entry.get("podcast_transcript"):
            transcript_url = entry["podcast_transcript"].get("url") if isinstance(entry["podcast_transcript"], dict) else entry["podcast_transcript"]

        # 如果没有标准转录链接，尝试从description/summary中提取
        if not transcript_url:
            raw_desc = entry.get("summary", "") or entry.get("description", "")
            transcript_url = cls._extract_transcript_url(raw_desc, entry.get("link", ""))

        return {
            "guid": guid,
            "title": entry.get("title", ""),
            "summary": summary,
            "content": content,
            "link": entry.get("link", ""),
            "published": published,
            "audio_url": audio_url,
            "audio_type": audio_type,
            "audio_size": audio_size,
            "duration": duration,
            "image": image,
            "chapters_url": chapters_url,
            "transcript_url": transcript_url,
        }

    @staticmethod
    def _parse_duration(duration_str) -> int:
        """
        解析时长字符串为秒数

        支持格式:
        - 纯数字: "3600" -> 3600秒
        - MM:SS: "45:30" -> 2730秒
        - HH:MM:SS: "1:30:00" -> 5400秒
        """
        if not duration_str:
            return 0

        duration_str = str(duration_str).strip()

        # 纯数字
        if duration_str.isdigit():
            return int(duration_str)

        # 带冒号的格式
        if ":" in duration_str:
            parts = duration_str.split(":")
            try:
                if len(parts) == 2:
                    return int(parts[0]) * 60 + int(parts[1])
                elif len(parts) == 3:
                    return int(parts[0]) * 3600 + int(parts[1]) * 60 + int(parts[2])
            except ValueError:
                pass

        return 0

    @staticmethod
    def _clean_html(text: str) -> str:
        """清理HTML标签"""
        if not text:
            return ""
        # 移除HTML标签
        clean = re.sub(r"<[^>]+>", "", text)
        # 清理多余空白
        clean = re.sub(r"\s+", " ", clean)
        return clean.strip()

    @classmethod
    def _clean_summary(cls, text: str) -> str:
        """清理摘要内容，移除广告链接等杂项"""
        if not text:
            return ""

        # 先清理HTML
        clean = cls._clean_html(text)

        # 常见的分隔标记，在这些之后的内容通常是广告/链接
        cutoff_markers = [
            "Thank you for listening",
            "Check out our sponsors",
            "See below for timestamps",
            "SPONSORS:",
            "OUTLINE:",
            "EPISODE LINKS:",
            "CONTACT",
            "Transcript:",
            "https://",
            "http://",
        ]

        # 找到最早的分隔点
        min_pos = len(clean)
        for marker in cutoff_markers:
            pos = clean.find(marker)
            if pos > 50 and pos < min_pos:  # 至少保留50个字符
                min_pos = pos

        # 截断并清理
        result = clean[:min_pos].strip()

        # 移除末尾不完整的句子
        if result and result[-1] not in ".!?":
            last_period = max(result.rfind("."), result.rfind("!"), result.rfind("?"))
            if last_period > len(result) // 2:
                result = result[:last_period + 1]

        return result

    @classmethod
    def _extract_transcript_url(cls, html_content: str, episode_link: str) -> Optional[str]:
        """
        从HTML内容中提取转录链接

        支持多种模式:
        1. 明确的Transcript标签后跟链接: <b>Transcript:</b> <a href="...">
        2. 包含transcript的链接: href="...transcript..."
        3. 基于episode链接推测: {episode_link}-transcript
        """
        if not html_content:
            return None

        # 模式1: 查找 Transcript: 后面的链接
        transcript_patterns = [
            r'[Tt]ranscript[:\s]*</[^>]+>\s*<a[^>]+href=["\']([^"\']+)["\']',
            r'[Tt]ranscript[:\s]*<a[^>]+href=["\']([^"\']+)["\']',
            r'<a[^>]+href=["\']([^"\']*transcript[^"\']*)["\'][^>]*>',
        ]

        for pattern in transcript_patterns:
            match = re.search(pattern, html_content, re.IGNORECASE)
            if match:
                url = match.group(1)
                if url.startswith("http"):
                    return url

        # 模式2: 基于episode链接推测 (适用于lexfridman.com等)
        if episode_link and "lexfridman.com" in episode_link:
            # https://lexfridman.com/paul-rosolie-3 -> https://lexfridman.com/paul-rosolie-3-transcript
            if not episode_link.endswith("-transcript"):
                return episode_link.rstrip("/") + "-transcript"

        return None

    @classmethod
    def validate_url(cls, url: str) -> bool:
        """验证URL格式"""
        if not url:
            return False
        return url.startswith("http://") or url.startswith("https://")
