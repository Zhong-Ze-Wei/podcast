# -*- coding: utf-8 -*-
"""
转录抓取服务

从播客网站抓取已有的转录文本
支持标准格式：SRT、VTT、JSON (Podcasting 2.0)
"""
import requests
import re
from typing import Optional, Tuple
import logging
import json

logger = logging.getLogger(__name__)


class TranscriptFetcher:
    """转录抓取服务 - 仅支持标准格式"""

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    HEADERS = {
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    }

    # 支持的标准格式
    SUPPORTED_FORMATS = [".srt", ".vtt", ".json"]

    @classmethod
    def fetch_transcript(cls, url: str, timeout: int = 30) -> Tuple[Optional[str], Optional[str]]:
        """
        抓取转录内容

        Args:
            url: 转录URL
            timeout: 超时时间

        Returns:
            (transcript_text, error_message)
        """
        if not url:
            return None, "No transcript URL provided"

        # 检查是否为支持的格式
        url_lower = url.lower()
        is_supported = any(fmt in url_lower for fmt in cls.SUPPORTED_FORMATS)
        if not is_supported:
            return None, f"Unsupported transcript format. Only SRT, VTT, JSON are supported."

        try:
            response = requests.get(url, headers=cls.HEADERS, timeout=timeout)
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "").lower()

            # 根据URL或内容类型选择解析方式
            if ".srt" in url_lower or "text/srt" in content_type:
                text = cls._parse_srt(response.text)
            elif ".vtt" in url_lower or "text/vtt" in content_type:
                text = cls._parse_vtt(response.text)
            elif ".json" in url_lower or "application/json" in content_type:
                text = cls._parse_json_transcript(response.text)
            else:
                return None, "Could not determine transcript format"

            if text and len(text) > 100:
                return text.strip(), None
            else:
                return None, "Transcript content too short or empty"

        except requests.exceptions.RequestException as e:
            logger.exception(f"Failed to fetch transcript: {url}")
            return None, f"Failed to fetch transcript: {str(e)}"
        except Exception as e:
            logger.exception(f"Error parsing transcript: {url}")
            return None, f"Error parsing transcript: {str(e)}"

    @classmethod
    def _parse_srt(cls, content: str) -> Optional[str]:
        """解析 SRT 字幕格式"""
        lines = []
        for line in content.split('\n'):
            line = line.strip()
            # 跳过序号行和时间戳行
            if not line or line.isdigit():
                continue
            if '-->' in line:
                continue
            lines.append(line)
        return ' '.join(lines)

    @classmethod
    def _parse_vtt(cls, content: str) -> Optional[str]:
        """解析 WebVTT 字幕格式"""
        lines = []
        for line in content.split('\n'):
            line = line.strip()
            # 跳过 WEBVTT 头、空行、时间戳行
            if not line or line.startswith('WEBVTT') or line.startswith('NOTE'):
                continue
            if '-->' in line:
                continue
            # 移除 VTT 标签
            line = re.sub(r'<[^>]+>', '', line)
            if line:
                lines.append(line)
        return ' '.join(lines)

    @classmethod
    def _parse_json_transcript(cls, content: str) -> Optional[str]:
        """解析 JSON 格式转录 (Podcasting 2.0 标准)"""
        try:
            data = json.loads(content)

            segments = []

            # 格式1: {"segments": [{"text": "..."}]}
            if isinstance(data, dict) and "segments" in data:
                for seg in data["segments"]:
                    if isinstance(seg, dict) and "text" in seg:
                        segments.append(seg["text"])

            # 格式2: [{"text": "..."}]
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "text" in item:
                        segments.append(item["text"])

            # 格式3: {"transcript": "..."}
            elif isinstance(data, dict) and "transcript" in data:
                return data["transcript"]

            if segments:
                return ' '.join(segments)

        except json.JSONDecodeError:
            pass

        return None

    @classmethod
    def validate_transcript_url(cls, url: str, timeout: int = 10) -> bool:
        """验证转录URL是否有效且为支持的格式"""
        if not url:
            return False

        # 检查是否为支持的格式
        url_lower = url.lower()
        is_supported = any(fmt in url_lower for fmt in cls.SUPPORTED_FORMATS)
        if not is_supported:
            return False

        try:
            response = requests.head(url, headers=cls.HEADERS, timeout=timeout, allow_redirects=True)
            return response.status_code == 200
        except Exception:
            return False
