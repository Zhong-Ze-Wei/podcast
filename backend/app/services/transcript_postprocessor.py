# -*- coding: utf-8 -*-
"""Transcript post-processing shared by all transcription providers."""
import json
import logging
import re
from typing import Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)

_CJK_RE = re.compile(r"[\u3400-\u9fff]")
_CJK_SPACE_RE = re.compile(r"(?<=[\u3400-\u9fff])\s+(?=[\u3400-\u9fff])")
_SPACE_BEFORE_CJK_PUNCT_RE = re.compile(r"\s+([，。！？；：、）】》”’])")
_SPACE_AFTER_OPEN_CJK_PUNCT_RE = re.compile(r"([（【《“‘])\s+")
_SPACE_AFTER_CJK_PUNCT_RE = re.compile(r"([，。！？；：、])\s+(?=[\u3400-\u9fff])")
_MULTISPACE_RE = re.compile(r"[ \t]{2,}")


SYSTEM_PROMPT = """You normalize speech-to-text transcripts.
Return valid JSON only. Do not summarize, shorten, add facts, remove meaning, or translate non-Chinese terms unnecessarily."""

USER_PROMPT = """Clean these transcript segments.

Requirements:
1. Convert Traditional Chinese to Simplified Chinese.
2. Remove unnatural spaces between Chinese characters and Chinese punctuation.
3. Keep timestamps, speaker names, proper nouns, stock tickers, URLs, and English technical terms.
4. Preserve item count and each item id exactly.
5. Return JSON: {"items":[{"i":0,"text":"..."}]}

Items:
{items}
"""


def normalize_transcript(
    text: str,
    segments: List[Dict],
    language: Optional[str] = None,
    use_ai: bool = False,
) -> Tuple[str, List[Dict], Dict]:
    """Normalize transcript text and segment text before persistence."""
    normalized_segments = [_normalize_segment(segment) for segment in (segments or [])]
    normalized_text = _normalize_text(text or "")

    metadata = {
        "rules": ["cjk_spacing", "cjk_punctuation_spacing"],
        "ai_normalized": False,
        "language_hint": language or "",
    }

    if _should_convert_with_opencc(language, normalized_text, normalized_segments):
        normalized_text = _convert_with_opencc(normalized_text)
        normalized_segments = [
            {**segment, "text": _convert_with_opencc(segment.get("text", ""))}
            for segment in normalized_segments
        ]
        metadata["rules"].append("opencc_t2s")

    if use_ai and _looks_chinese(language, normalized_text, normalized_segments):
        try:
            normalized_segments, ai_meta = _normalize_segments_with_ai(normalized_segments)
            if normalized_segments:
                normalized_text = " ".join(
                    segment.get("text", "").strip()
                    for segment in normalized_segments
                    if segment.get("text", "").strip()
                )
            else:
                normalized_text, ai_meta = _normalize_text_with_ai(normalized_text)
            metadata.update(ai_meta)
            metadata["ai_normalized"] = True
        except Exception as exc:
            logger.warning("AI transcript normalization failed; keeping rule-normalized text: %s", exc)
            metadata["ai_error"] = str(exc)

    normalized_text = _normalize_text(normalized_text)
    normalized_segments = [_normalize_segment(segment) for segment in normalized_segments]
    return normalized_text, normalized_segments, metadata


def _normalize_segment(segment: Dict) -> Dict:
    normalized = dict(segment or {})
    normalized["text"] = _normalize_text(str(normalized.get("text", "")))
    return normalized


def _normalize_text(text: str) -> str:
    if not text:
        return ""
    text = _CJK_SPACE_RE.sub("", text)
    text = _SPACE_BEFORE_CJK_PUNCT_RE.sub(r"\1", text)
    text = _SPACE_AFTER_OPEN_CJK_PUNCT_RE.sub(r"\1", text)
    text = _SPACE_AFTER_CJK_PUNCT_RE.sub(r"\1", text)
    text = _MULTISPACE_RE.sub(" ", text)
    return text.strip()


def _looks_chinese(language: Optional[str], text: str, segments: List[Dict]) -> bool:
    if language and str(language).lower().startswith("zh"):
        return True
    sample = text or " ".join(segment.get("text", "") for segment in segments[:20])
    return bool(_CJK_RE.search(sample))


def _should_convert_with_opencc(language: Optional[str], text: str, segments: List[Dict]) -> bool:
    return _looks_chinese(language, text, segments)


def _convert_with_opencc(text: str) -> str:
    if not text:
        return text
    try:
        from opencc import OpenCC

        return OpenCC("t2s").convert(text)
    except Exception:
        return text


def _normalize_segments_with_ai(segments: List[Dict]) -> Tuple[List[Dict], Dict]:
    if not segments:
        return [], {"ai_model": "", "ai_usage": {"prompt": 0, "completion": 0, "total": 0}}

    from app.services.llm_client import get_llm_client

    llm = get_llm_client(task="transcript_normalize")
    result_segments = [dict(segment) for segment in segments]
    usage_total = {"prompt": 0, "completion": 0, "total": 0}
    model = ""

    for chunk in _chunk_segment_items(result_segments):
        payload = json.dumps(chunk, ensure_ascii=False)
        result = llm.chat_json(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": USER_PROMPT.format(items=payload)},
            ],
            temperature=0,
        )
        model = result.get("model") or model
        usage = result.get("usage") or {}
        for key in usage_total:
            usage_total[key] += int(usage.get(key, 0) or 0)

        returned_items = result.get("data", {}).get("items", [])
        text_by_index = {
            int(item["i"]): _normalize_text(str(item.get("text", "")))
            for item in returned_items
            if isinstance(item, dict) and "i" in item
        }
        for item in chunk:
            index = item["i"]
            if index in text_by_index:
                result_segments[index]["text"] = text_by_index[index]

    return result_segments, {"ai_model": model, "ai_usage": usage_total}


def _normalize_text_with_ai(text: str) -> Tuple[str, Dict]:
    if not text:
        return "", {"ai_model": "", "ai_usage": {"prompt": 0, "completion": 0, "total": 0}}
    segments = [{"text": text}]
    normalized, metadata = _normalize_segments_with_ai(segments)
    return normalized[0].get("text", "") if normalized else text, metadata


def _chunk_segment_items(segments: List[Dict], max_chars: int = 7000):
    chunk = []
    char_count = 0
    for index, segment in enumerate(segments):
        text = segment.get("text", "")
        item = {"i": index, "text": text}
        item_size = len(text) + 20
        if chunk and char_count + item_size > max_chars:
            yield chunk
            chunk = []
            char_count = 0
        chunk.append(item)
        char_count += item_size
    if chunk:
        yield chunk
