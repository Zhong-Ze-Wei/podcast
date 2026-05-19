# -*- coding: utf-8 -*-
"""
Transcript fetcher.

Fetches existing transcript files from podcast sites and parses standard
SRT, VTT, and JSON transcript formats.
"""
import json
import logging
import re
from dataclasses import dataclass
from html import unescape
from typing import Optional, Tuple, List, Dict, Any
from urllib.parse import urlparse

import requests

logger = logging.getLogger(__name__)


@dataclass
class TranscriptFetchResult:
    text: str
    segments: List[Dict[str, Any]]
    format: str
    confidence: float = 0.0


class TranscriptFetcher:
    """Fetch and parse standard transcript files."""

    USER_AGENT = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"

    HEADERS = {
        "User-Agent": USER_AGENT,
        "Accept": "text/vtt,application/x-subrip,application/json,text/plain,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7",
    }

    SUPPORTED_FORMATS = [".srt", ".vtt", ".json"]

    @classmethod
    def fetch_transcript(cls, url: str, timeout: int = 30) -> Tuple[Optional[str], Optional[str]]:
        """
        Fetch transcript content.

        Returns:
            (transcript_text, error_message)
        """
        result, error = cls.fetch_transcript_result(url, timeout=timeout)
        if error:
            return None, error
        return result.text if result else None, None

    @classmethod
    def fetch_transcript_result(cls, url: str, timeout: int = 30) -> Tuple[Optional[TranscriptFetchResult], Optional[str]]:
        """Fetch transcript content with best-effort structured segments."""
        if not url:
            return None, "No transcript URL provided"

        try:
            response = requests.get(url, headers=cls.HEADERS, timeout=timeout)
            response.raise_for_status()

            content_type = response.headers.get("Content-Type", "")
            transcript_format = cls._detect_format(url, content_type, response.text)

            result = None
            if transcript_format == "srt":
                text = cls._parse_srt(response.text)
                result = cls._result_from_text(text, "srt", 0.6)
            elif transcript_format == "vtt":
                text = cls._parse_vtt(response.text)
                result = cls._result_from_text(text, "vtt", 0.6)
            elif transcript_format == "json":
                text = cls._parse_json_transcript(response.text)
                result = cls._result_from_text(text, "json", 0.6)
            elif transcript_format == "html":
                result = cls._parse_html_transcript_result(response.text)
            else:
                return None, "Could not determine transcript format. Supported formats are SRT, VTT, JSON, and transcript HTML pages."

            if result and result.text and result.text.strip():
                result.text = result.text.strip()
                return result, None
            return None, "Transcript content too short or empty"

        except requests.exceptions.RequestException as e:
            logger.exception(f"Failed to fetch transcript: {url}")
            return None, f"Failed to fetch transcript: {str(e)}"
        except Exception as e:
            logger.exception(f"Error parsing transcript: {url}")
            return None, f"Error parsing transcript: {str(e)}"

    @classmethod
    def _detect_format(cls, url: str, content_type: str = "", content: str = "") -> Optional[str]:
        """Detect transcript format from URL, Content-Type, then body prefix."""
        url_lower = (url or "").lower()
        path_lower = urlparse(url_lower).path
        normalized_content_type = (content_type or "").split(";")[0].strip().lower()

        if path_lower.endswith(".srt") or ".srt" in url_lower:
            return "srt"
        if path_lower.endswith(".vtt") or ".vtt" in url_lower:
            return "vtt"
        if path_lower.endswith(".json") or ".json" in url_lower:
            return "json"

        if normalized_content_type in {"text/vtt", "text/webvtt"}:
            return "vtt"
        if normalized_content_type in {
            "application/x-subrip",
            "application/srt",
            "text/srt",
            "text/x-srt",
        }:
            return "srt"
        if normalized_content_type in {
            "application/json",
            "application/feed+json",
            "application/transcript+json",
        }:
            return "json"
        if normalized_content_type in {"text/html", "application/xhtml+xml"}:
            return "html" if cls._looks_like_transcript_html(content) else None

        return cls._sniff_format(content)

    @staticmethod
    def _sniff_format(content: str) -> Optional[str]:
        """Sniff SRT/VTT/JSON from the first few lines."""
        if not content:
            return None

        stripped = content.lstrip("\ufeff\r\n\t ")
        if not stripped:
            return None

        if stripped.startswith("{") or stripped.startswith("["):
            try:
                json.loads(stripped)
                return "json"
            except json.JSONDecodeError:
                return None

        first_lines = "\n".join(stripped.splitlines()[:8])
        if first_lines.startswith("WEBVTT"):
            return "vtt"

        timestamp_pattern = r"\d{2}:\d{2}:\d{2}[,.]\d{3}\s*-->\s*\d{2}:\d{2}:\d{2}[,.]\d{3}"
        if re.search(timestamp_pattern, first_lines):
            if "," in first_lines:
                return "srt"
            return "vtt"

        lowered = stripped[:500].lower()
        if "<html" in lowered or "<!doctype html" in lowered or "<article" in lowered:
            return "html" if TranscriptFetcher._looks_like_transcript_html(content) else None

        return None

    @staticmethod
    def _looks_like_transcript_html(content: str) -> bool:
        if not content:
            return False

        html = re.sub(r"(?is)<head[^>]*>.*?</head>", " ", content)
        html = re.sub(r"(?is)<(script|style|noscript|svg)[^>]*>.*?</\1>", " ", html)
        text = re.sub(r"<[^>]+>", " ", html)
        text = unescape(text)
        normalized = re.sub(r"\s+", " ", text).strip().lower().replace("\\/", "/")
        normalized_without_urls = re.sub(r"https?://\S+", " ", normalized)
        head = normalized_without_urls[:5000]

        if (
            "this is a transcript" in head
            or re.search(r"\b(podcast|episode|interview)\s+transcript\b", head)
            or re.search(r"\btranscript\s+(of|for)\b", head)
        ):
            return True

        timestamp_count = len(re.findall(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", normalized_without_urls[:20000]))
        speaker_count = len(
            re.findall(r"\b(host|guest|speaker|interviewer|interviewee)\s*:", normalized_without_urls[:20000])
        )
        return timestamp_count >= 5 or speaker_count >= 5

    @staticmethod
    def _looks_like_transcript_text(text: str) -> bool:
        if not text:
            return False
        normalized = re.sub(r"\s+", " ", text).strip().lower()
        head = normalized[:5000]
        if (
            "this is a transcript" in head
            or re.search(r"\b(podcast|episode|interview)\s+transcript\b", head)
            or re.search(r"\btranscript\s+(of|for)\b", head)
        ):
            return True
        if len(normalized) < 5000:
            return False
        timestamp_count = len(re.findall(r"\b\d{1,2}:\d{2}(?::\d{2})?\b", normalized[:20000]))
        speaker_count = len(
            re.findall(r"\b(host|guest|speaker|interviewer|interviewee)\s*:", normalized[:20000])
        )
        return timestamp_count >= 5 or speaker_count >= 5

    @classmethod
    def _parse_srt(cls, content: str) -> Optional[str]:
        """Parse SRT captions into plain text."""
        lines = []
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.isdigit():
                continue
            if "-->" in line:
                continue
            lines.append(line)
        return " ".join(lines)

    @classmethod
    def _parse_vtt(cls, content: str) -> Optional[str]:
        """Parse WebVTT captions into plain text."""
        lines = []
        for line in content.split("\n"):
            line = line.strip()
            if not line or line.startswith("WEBVTT") or line.startswith("NOTE"):
                continue
            if "-->" in line:
                continue
            line = re.sub(r"<[^>]+>", "", line)
            if line:
                lines.append(line)
        return " ".join(lines)

    @classmethod
    def _parse_json_transcript(cls, content: str) -> Optional[str]:
        """Parse Podcasting 2.0-style JSON transcripts."""
        try:
            data = json.loads(content)

            segments = []

            if isinstance(data, dict) and "segments" in data:
                for seg in data["segments"]:
                    if isinstance(seg, dict) and "text" in seg:
                        segments.append(seg["text"])
            elif isinstance(data, list):
                for item in data:
                    if isinstance(item, dict) and "text" in item:
                        segments.append(item["text"])
            elif isinstance(data, dict) and "transcript" in data:
                return data["transcript"]

            if segments:
                return " ".join(segments)

        except json.JSONDecodeError:
            pass

        return None

    @classmethod
    def _result_from_text(cls, text: Optional[str], transcript_format: str, confidence: float) -> Optional[TranscriptFetchResult]:
        if not text:
            return None
        return TranscriptFetchResult(
            text=text,
            segments=cls._segments_from_plain_text(text),
            format=transcript_format,
            confidence=confidence,
        )

    @staticmethod
    def _segments_from_plain_text(text: str) -> List[Dict[str, Any]]:
        if not text:
            return []
        segments = []
        for paragraph in text.split("\n\n"):
            normalized = " ".join(paragraph.split())
            if normalized:
                segments.append({"text": normalized, "time": ""})
        if segments:
            return segments
        normalized = " ".join(text.split())
        return [{"text": normalized, "time": ""}] if normalized else []

    @classmethod
    def _parse_html_transcript_result(cls, content: str) -> Optional[TranscriptFetchResult]:
        lines = cls._html_transcript_lines(content)
        if not lines:
            return None

        segments = cls._segments_from_lines(lines)
        if len(segments) >= 2:
            return TranscriptFetchResult(
                text=cls._text_from_segments(segments),
                segments=segments,
                format="html",
                confidence=0.9,
            )

        compacted = cls._compact_speaker_timestamp_lines(lines)
        if compacted:
            return TranscriptFetchResult(
                text=compacted,
                segments=cls._segments_from_plain_text(compacted),
                format="html",
                confidence=0.7,
            )

        result = cls._plain_text_from_lines(lines)
        if len(result) < 20 or not cls._looks_like_transcript_text(result):
            return None
        return TranscriptFetchResult(
            text=result,
            segments=cls._segments_from_plain_text(result),
            format="html",
            confidence=0.4,
        )

    @classmethod
    def _parse_html_transcript(cls, content: str) -> Optional[str]:
        """Parse transcript-like HTML pages into plain text."""
        result = cls._parse_html_transcript_result(content)
        return result.text if result else None

    @classmethod
    def _html_transcript_lines(cls, content: str) -> List[str]:
        if not content or not cls._looks_like_transcript_html(content):
            return []

        html = re.sub(r"(?is)<(script|style|noscript|svg|nav|header|footer|aside)[^>]*>.*?</\1>", " ", content)
        article_match = re.search(r"(?is)<article[^>]*>(.*?)</article>", html)
        main_match = re.search(r"(?is)<main[^>]*>(.*?)</main>", html)
        if article_match:
            html = article_match.group(1)
        elif main_match:
            html = main_match.group(1)

        html = re.sub(r"(?i)<br\s*/?>", "\n", html)
        html = re.sub(r"(?i)</(p|div|li|h[1-6]|section|tr)>", "\n", html)
        text = re.sub(r"<[^>]+>", " ", html)
        text = unescape(text)
        lines = []
        for raw_line in text.splitlines():
            line = re.sub(r"\s+", " ", raw_line).strip()
            if not line:
                continue
            if len(line) < 3:
                continue
            if re.fullmatch(r"\[[^\]]+\]", line):
                continue
            lines.append(line)
        return lines

    @classmethod
    def _segments_from_lines(cls, lines: List[str]) -> List[Dict[str, Any]]:
        segments = []
        idx = 0
        while idx < len(lines):
            segment, next_idx = cls._segment_at(lines, idx)
            if segment:
                segments.append(segment)
                idx = next_idx
            else:
                idx += 1
        return segments

    @classmethod
    def _segment_at(cls, lines: List[str], idx: int):
        line = lines[idx]

        inline = cls._parse_inline_segment(line)
        if inline:
            return inline, idx + 1

        speaker_timestamp = cls._parse_speaker_timestamp_line(line)
        if speaker_timestamp and idx + 1 < len(lines):
            speaker, timestamp = speaker_timestamp
            speech_lines, next_idx = cls._collect_speech_lines(lines, idx + 1)
            speech = " ".join(speech_lines).strip()
            if speech:
                return cls._make_segment(speech, timestamp, speaker), next_idx

        if cls._is_timestamp_only(line) and idx > 0:
            speaker = lines[idx - 1]
            speech_lines, next_idx = cls._collect_speech_lines(lines, idx + 1)
            speech = " ".join(speech_lines).strip()
            if speaker and speech:
                return cls._make_segment(speech, line, speaker), next_idx

        return None, idx + 1

    @classmethod
    def _collect_speech_lines(cls, lines: List[str], start_idx: int):
        collected = []
        idx = start_idx
        while idx < len(lines):
            line = lines[idx]
            if cls._is_timestamp_only(line) or cls._parse_inline_segment(line) or cls._parse_speaker_timestamp_line(line):
                break
            collected.append(line)
            idx += 1

        while collected and cls._looks_like_section_heading(collected[-1]):
            collected.pop()

        return collected, idx

    @classmethod
    def _parse_inline_segment(cls, line: str) -> Optional[Dict[str, Any]]:
        patterns = [
            r"^\[?(?P<timestamp>\d{1,2}:\d{2}(?::\d{2})?)\]?\s+(?P<speaker>[^:]{1,80}):\s+(?P<text>.+)$",
            r"^\[?(?P<timestamp>\d{1,2}:\d{2}(?::\d{2})?)\]?\s+(?P<text>.+)$",
        ]
        for pattern in patterns:
            match = re.match(pattern, line)
            if match:
                groups = match.groupdict()
                if cls._looks_like_section_heading(groups.get("text", "")):
                    return None
                return cls._make_segment(
                    groups.get("text", ""),
                    groups["timestamp"],
                    groups.get("speaker"),
                )
        return None

    @classmethod
    def _plain_text_from_lines(cls, lines: List[str]) -> str:
        normalized_lines = []
        for line in lines:
            inline = cls._parse_inline_segment(line)
            if inline:
                prefix = f"{inline['speaker']}: " if inline.get("speaker") else ""
                normalized_lines.append(f"{prefix}{inline['text']}")
            else:
                normalized_lines.append(line)
        return "\n\n".join(normalized_lines)

    @staticmethod
    def _parse_speaker_timestamp_line(line: str):
        match = re.match(r"^(?P<speaker>.+?)\s+[\[(]?(?P<timestamp>\d{1,2}:\d{2}(?::\d{2})?)[\])]?$", line)
        if not match:
            return None
        speaker = match.group("speaker").strip()
        if not speaker or len(speaker) > 80:
            return None
        return speaker, match.group("timestamp")

    @staticmethod
    def _is_timestamp_only(line: str) -> bool:
        return bool(re.match(r"^[\[(]?\d{1,2}:\d{2}(?::\d{2})?[\])]?$", line.strip()))

    @classmethod
    def _make_segment(cls, text: str, timestamp: str, speaker: Optional[str] = None) -> Dict[str, Any]:
        normalized_time = cls._normalize_timestamp(timestamp)
        segment = {
            "time": normalized_time,
            "start": cls._timestamp_to_seconds(normalized_time),
            "text": " ".join((text or "").split()),
        }
        if speaker:
            segment["speaker"] = " ".join(speaker.split())
        return segment

    @staticmethod
    def _normalize_timestamp(timestamp: str) -> str:
        timestamp = (timestamp or "").strip().strip("[]()")
        parts = timestamp.split(":")
        if len(parts) == 2:
            return f"00:{int(parts[0]):02d}:{int(parts[1]):02d}"
        if len(parts) == 3:
            return f"{int(parts[0]):02d}:{int(parts[1]):02d}:{int(parts[2]):02d}"
        return timestamp

    @staticmethod
    def _timestamp_to_seconds(timestamp: str) -> int:
        parts = [int(part) for part in timestamp.split(":")]
        if len(parts) == 3:
            return parts[0] * 3600 + parts[1] * 60 + parts[2]
        if len(parts) == 2:
            return parts[0] * 60 + parts[1]
        return 0

    @staticmethod
    def _text_from_segments(segments: List[Dict[str, Any]]) -> str:
        paragraphs = []
        for segment in segments:
            prefix_parts = []
            if segment.get("speaker"):
                prefix_parts.append(segment["speaker"])
            if segment.get("time"):
                prefix_parts.append(f"({segment['time']})")
            prefix = " ".join(prefix_parts)
            paragraphs.append(f"{prefix}\n{segment.get('text', '')}" if prefix else segment.get("text", ""))
        return "\n\n".join(paragraphs)

    @staticmethod
    def _compact_speaker_timestamp_lines(lines: list) -> Optional[str]:
        timestamp_re = re.compile(r"^\(?\d{1,2}:\d{2}(?::\d{2})?\)?$")
        first_timestamp = None
        for idx, line in enumerate(lines):
            if idx > 0 and timestamp_re.match(line):
                first_timestamp = idx
                break

        if first_timestamp is None:
            return None

        paragraphs = []
        idx = first_timestamp
        while idx is not None and idx < len(lines):
            if idx <= 0 or not timestamp_re.match(lines[idx]):
                idx += 1
                continue

            speaker = lines[idx - 1]
            timestamp = lines[idx]

            next_timestamp = None
            for next_idx in range(idx + 1, len(lines)):
                if timestamp_re.match(lines[next_idx]):
                    next_timestamp = next_idx
                    break

            if next_timestamp is None:
                speech_lines = lines[idx + 1 :]
            else:
                speech_lines = lines[idx + 1 : max(idx + 1, next_timestamp - 1)]
            while speech_lines and TranscriptFetcher._looks_like_section_heading(speech_lines[-1]):
                speech_lines.pop()

            speech = " ".join(speech_lines).strip()
            if speaker and speech:
                paragraphs.append(f"{speaker} {timestamp}\n{speech}")

            if next_timestamp is None:
                break
            idx = next_timestamp

        return "\n\n".join(paragraphs) if paragraphs else None

    @staticmethod
    def _looks_like_section_heading(line: str) -> bool:
        if not line or len(line) > 90:
            return False
        if re.search(r"[.!?。！？]$", line):
            return False
        if re.match(r"^[–-]", line):
            return True
        return len(line.split()) <= 8

    @classmethod
    def validate_transcript_url(cls, url: str, timeout: int = 10) -> bool:
        """Validate that the URL returns a supported transcript format."""
        if not url:
            return False

        try:
            response = requests.head(url, headers=cls.HEADERS, timeout=timeout, allow_redirects=True)
            if response.status_code >= 400:
                return False
            content_type = response.headers.get("Content-Type", "")
            transcript_format = cls._detect_format(url, content_type)
            if transcript_format and transcript_format != "html":
                return True
        except Exception:
            pass

        try:
            response = requests.get(url, headers=cls.HEADERS, timeout=timeout)
            if response.status_code >= 400:
                return False
            content_type = response.headers.get("Content-Type", "")
            transcript_format = cls._detect_format(url, content_type, response.text)
            if transcript_format == "html":
                return cls._parse_html_transcript(response.text) is not None
            return transcript_format is not None
        except Exception:
            return False
