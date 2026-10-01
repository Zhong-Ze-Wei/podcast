"""Collect real, deduplicated source text for the briefing strategy experiment.

Connect directly to MongoDB: importing the Flask application factory would start
the broken automatic refresher. No LLM calls, proxy changes, or full feed refresh.
"""
from __future__ import annotations

import argparse
import hashlib
import io
import json
import logging
import os
from pathlib import Path
import re
import socket
import sys
import uuid
from datetime import datetime, timezone
from urllib.parse import urljoin, urlsplit

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

from dotenv import load_dotenv
from pymongo import MongoClient
from bson import ObjectId

load_dotenv(BACKEND / ".env")

from app.models.transcript import Transcript
from app.services.bilibili_service import BilibiliService
from app.services.transcript_fetcher import TranscriptFetcher


def utc_now():
    return datetime.now(timezone.utc).isoformat()


def timestamp(value):
    if not isinstance(value, datetime):
        return None
    return value.replace(tzinfo=timezone.utc).isoformat() if value.tzinfo is None else value.isoformat()


def safe_error(error):
    message = str(error)
    for name, value in os.environ.items():
        if value and len(value) > 5 and any(part in name.upper() for part in ("KEY", "SECRET", "TOKEN", "COOKIE", "SESSDATA")):
            message = message.replace(value, "[redacted]")
    return re.sub(r"(https?://)[^/@\s]+:[^/@\s]+@", r"\1[redacted]@", message)[:800]


def proxy_label(proxy):
    parts = urlsplit(proxy)
    return f"{parts.scheme}://{parts.hostname}:{parts.port or 80}"


def tcp_probe(host, port):
    try:
        with socket.create_connection((host, port), timeout=2):
            return {"host": host, "port": port, "reachable": True}
    except OSError as error:
        return {"host": host, "port": port, "reachable": False, "error": safe_error(error)}


def normalized_segments(segments):
    result = []
    for segment in segments or []:
        if not isinstance(segment, dict) or not segment.get("text"):
            continue
        item = {"start": segment.get("start"), "end": segment.get("end"), "text": str(segment["text"])}
        if segment.get("speaker"):
            item["speaker"] = segment["speaker"]
        result.append(item)
    return result


def collect_existing(db, feeds, acquired):
    sources = []
    seen = set()
    for episode in db.episodes.find({}).sort([("published", -1), ("_id", -1)]):
        guid = episode.get("guid") or str(episode["_id"])
        if guid in seen:
            continue
        # A duplicate episode may have its transcript on another copy.
        copies = list(db.episodes.find({"guid": guid})) if episode.get("guid") else [episode]
        transcript = None
        for copy in copies:
            candidate = db.transcripts.find_one({"episode_id": copy["_id"]})
            if candidate and (candidate.get("text") or "").strip():
                episode, transcript = copy, candidate
                break
        if not transcript:
            continue
        seen.add(guid)
        feed = feeds.get(str(episode.get("feed_id")), {})
        text = transcript["text"].strip()
        sources.append({
            "id": f"S{len(sources) + 1:02d}",
            "title": episode.get("title", ""),
            "episode_id": str(episode["_id"]),
            "guid": guid,
            "feed": feed.get("title", ""),
            "published": timestamp(episode.get("published")),
            "duration": episode.get("duration", 0),
            "source_type": feed.get("type") or "rss",
            "material_type": "full_transcript",
            "full_text": text,
            "segments": normalized_segments(transcript.get("segments")),
            "char_count": len(text),
            "original_url": episode.get("link") or feed.get("website") or "",
            "acquisition": {
                "status": "fetched_and_persisted" if guid in acquired else "existing_transcript",
                "transcript_source": transcript.get("source", ""),
                "transcript_id": str(transcript["_id"]),
                "collected_at": utc_now(),
            },
        })
        if len(sources) == 10:
            break
    return sources


def write_manifest(output, manifest):
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f"{output.name}.{uuid.uuid4().hex}.tmp")
    temporary.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(output)


def write_corpus(output, sources, attempts, diagnostics):
    write_manifest(output, {
        "generated_at": utc_now(),
        "selection": "Latest 10 available real transcripts by published date, deduplicated by guid; includes full short videos.",
        "sources": sources,
        "attempts": attempts,
        "diagnostics": diagnostics,
    })


def reconcile_selected_sources(db, output):
    """Repair only the frozen ten's display flags, preserving text and work state."""
    manifest = json.loads(output.read_text(encoding="utf-8"))
    sources = manifest["sources"]
    if len(sources) != 10 or len({source["episode_id"] for source in sources}) != 10:
        raise ValueError("Flag reconciliation requires an already frozen, unique ten-source corpus.")
    validated = []
    for source in sources:
        episode_id = ObjectId(source["episode_id"])
        episode = db.episodes.find_one({"_id": episode_id})
        transcript = db.transcripts.find_one({"episode_id": episode_id})
        text = (transcript or {}).get("text") or ""
        if not episode or not text.strip() or text.strip() != source["full_text"].strip():
            raise ValueError(f"{source['id']} does not have the frozen, nonempty real transcript.")
        validated.append((source, episode_id, episode, transcript))
    records = []
    for source, episode_id, episode, transcript in validated:
        updates = {"has_transcript": True, "transcript_source": transcript.get("source", "")}
        previous_status = episode.get("status")
        # Preserve summarized/summarizing and active download/transcription work.
        if previous_status in (None, "new", "downloaded", "error"):
            updates["status"] = "transcribed"
        changed = any(episode.get(key) != value for key, value in updates.items())
        if changed:
            updates["updated_at"] = datetime.now(timezone.utc)
            db.episodes.update_one({"_id": episode_id}, {"$set": updates})
        records.append({
            "source_id": source["id"], "episode_id": str(episode_id), "title": source["title"],
            "previous_status": previous_status, "status": updates.get("status", previous_status),
            "has_transcript": True, "transcript_source": updates["transcript_source"], "changed": changed,
        })
    manifest["reconciled_existing_transcripts"] = records
    manifest["reconciled_at"] = utc_now()
    write_manifest(output, manifest)
    return records


def diagnose_youtube(feeds, diagnostics):
    import feedparser
    import requests

    configured = os.getenv("YOUTUBE_PROXY", "").strip()
    diagnostics["configured_youtube_proxy"] = proxy_label(configured) if configured else None
    diagnostics["local_proxy_ports"] = [tcp_probe("127.0.0.1", port) for port in (7890, 7891)]
    options = [configured] if configured else []
    for port in diagnostics["local_proxy_ports"]:
        proxy = f"http://127.0.0.1:{port['port']}"
        if port["reachable"] and proxy not in options:
            options.append(proxy)
    options.append(None)  # Explicit direct request, independent of system proxy.
    channels = list(dict.fromkeys(f.get("channel_ref") for f in feeds.values() if f.get("type") == "youtube" and f.get("channel_ref")))
    diagnostics["youtube_rss"] = []
    selected_proxy = None
    for proxy in options:
        if not channels:
            break
        url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channels[0]}"
        check = {"proxy": proxy_label(proxy) if proxy else "direct", "channel_id": channels[0]}
        try:
            session = requests.Session()
            session.trust_env = False
            response = session.get(url, proxies={"http": proxy, "https": proxy} if proxy else {}, timeout=12)
            parsed = feedparser.parse(response.content)
            entries = [entry for entry in parsed.entries if entry.get("yt_videoid")]
            check.update(http_status=response.status_code, entry_count=len(entries), ok=response.status_code == 200 and bool(entries))
            if entries:
                check["latest"] = [{"title": entry.get("title"), "video_id": entry.get("yt_videoid"), "published": entry.get("published")} for entry in entries[:3]]
            if check["ok"] and selected_proxy is None:
                selected_proxy = proxy
        except requests.RequestException as error:
            check.update(ok=False, error=safe_error(error))
        diagnostics["youtube_rss"].append(check)
    # No global config is changed. A reachable alternative is used only by this lab.
    diagnostics["lab_youtube_proxy"] = proxy_label(selected_proxy) if selected_proxy else None
    return selected_proxy


def fetch_youtube_transcript(video_id, proxy):
    import requests
    from youtube_transcript_api import YouTubeTranscriptApi
    from youtube_transcript_api.proxies import GenericProxyConfig

    class TimedSession(requests.Session):
        def request(self, *args, **kwargs):
            kwargs.setdefault("timeout", 12)
            return super().request(*args, **kwargs)

    session = TimedSession()
    session.trust_env = False
    api = YouTubeTranscriptApi(http_client=session, proxy_config=GenericProxyConfig(http_url=proxy, https_url=proxy) if proxy else None)
    result = api.fetch(video_id, languages=["en", "zh-Hans", "zh-Hant", "zh"])
    segments = [{"start": item.start, "end": item.start + item.duration, "text": item.text.strip()} for item in result.snippets if item.text.strip()]
    return {"text": " ".join(item["text"] for item in segments), "segments": segments, "language": result.language_code}


def fetch_linked_transcript(episode):
    """Fetch only explicit transcript links; never promote show notes to full text."""
    import requests

    url = episode.get("transcript_url")
    if not url:
        response = requests.get(episode["link"], timeout=15)
        response.raise_for_status()
        links = re.findall(r'<a\b[^>]*href=[\"\']([^\"\']+)[\"\'][^>]*>(.*?)</a>', response.text, re.IGNORECASE | re.DOTALL)
        candidates = [urljoin(response.url, href) for href, label in links if "transcript" in (href + " " + re.sub(r"<[^>]+>", "", label)).lower()]
        candidates = [link for link in candidates if not link.startswith("mailto:")]
        if not candidates:
            raise ValueError("No explicit transcript link on the episode page; show notes were excluded.")
        url = candidates[0]
    if urlsplit(url).path.lower().endswith(".txt"):
        response = requests.get(url, timeout=15)
        if response.status_code == 403:
            # The live SED transcript endpoint rejects requests' TLS fingerprint,
            # while its public Chrome response serves the complete transcript.
            from curl_cffi import requests as curl_requests
            response = curl_requests.get(url, impersonate="chrome", timeout=15)
        response.raise_for_status()
        text = response.text.strip()
        matches = list(re.finditer(r"\[(\d+:\d{2}:\d{2})\]\s+([^:\n]+):\s*", text))
        if len(text) < 1000 or len(matches) < 3:
            raise ValueError("The explicit text file lacks substantive timestamped transcript content.")
        segments = []
        for index, match in enumerate(matches):
            hours, minutes, seconds = map(int, match[1].split(":"))
            start = hours * 3600 + minutes * 60 + seconds
            end_offset = matches[index + 1].start() if index + 1 < len(matches) else len(text)
            segments.append({"start": start, "end": None, "speaker": match[2].strip(), "text": text[match.end():end_offset].strip()})
        for index in range(len(segments) - 1):
            segments[index]["end"] = segments[index + 1]["start"]
        return {"text": text, "segments": segments, "language": "en", "original_url": url}
    if urlsplit(url).path.lower().endswith(".pdf"):
        response = requests.get(url, timeout=15)
        response.raise_for_status()
        try:
            from pypdf import PdfReader
            text = "\n\n".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(response.content)).pages)
        except ImportError:
            try:
                import fitz
            except ImportError as error:
                raise RuntimeError("An explicit PDF transcript was found but no PDF text extractor is installed.") from error
            with fitz.open(stream=response.content, filetype="pdf") as document:
                text = "\n\n".join(page.get_text() for page in document)
        if len(text.strip()) < 1000:
            raise ValueError("The linked PDF did not contain a substantive transcript.")
        return {"text": text.strip(), "segments": [], "language": "en", "original_url": url}
    result, error = TranscriptFetcher.fetch_transcript_result(url, timeout=15)
    if error or not result or not result.text:
        raise ValueError(error or "The explicit transcript link did not return transcript text.")
    return {"text": result.text, "segments": result.segments, "language": "", "original_url": url}


def persist_transcript(db, episode, payload, source):
    text = (payload.get("text") or "").strip()
    if not text:
        raise ValueError("Empty transcript was rejected.")
    guid = episode.get("guid")
    episode_ids = [copy["_id"] for copy in db.episodes.find({"guid": guid})] if guid else [episode["_id"]]
    if db.transcripts.find_one({"episode_id": {"$in": episode_ids}, "text": text}):
        return False
    if db.transcripts.find_one({"episode_id": episode["_id"]}):
        return False
    exact_hash = hashlib.sha256(text.encode("utf-8")).hexdigest()
    for other in db.transcripts.find({}, {"text": 1, "episode_id": 1}):
        if other.get("episode_id") not in episode_ids and hashlib.sha256((other.get("text") or "").encode("utf-8")).hexdigest() == exact_hash:
            raise ValueError("Exact full transcript duplicate of another episode was rejected.")
    document = Transcript.create(episode["_id"], text, segments=payload.get("segments") or [], owner_id=episode.get("owner_id"), language=payload.get("language") or "", source=source, model="briefing-lab-platform-capture")
    document["acquisition"] = {"method": "briefing_lab_collect", "fetched_at": utc_now(), "original_url": payload.get("original_url") or episode.get("link")}
    db.transcripts.insert_one(document)
    updates = {"has_transcript": True, "transcript_source": source, "updated_at": datetime.now(timezone.utc)}
    if episode.get("status") not in {"summarized", "summarizing"} and not db.summaries.find_one({"episode_id": episode["_id"]}):
        updates["status"] = "transcribed"
    db.episodes.update_one({"_id": episode["_id"]}, {"$set": updates, "$unset": {"transcript_fetch_error": "", "last_transcript_error": ""}})
    return True


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--existing-only", action="store_true")
    parser.add_argument("--reconcile-flags", action="store_true", help="Repair display flags for only the already frozen ten sources; no fetching or corpus changes.")
    parser.add_argument("--max-attempts", type=int, default=15)
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")
    logging.getLogger("app.services.bilibili_service").setLevel(logging.ERROR)
    client = MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"), serverSelectionTimeoutMS=5000)
    db = client[os.getenv("MONGO_DB", "podcast")]
    output = BACKEND / ".runtime" / "briefing-lab" / "corpus.json"
    if args.reconcile_flags:
        records = reconcile_selected_sources(db, output)
        print(json.dumps({"phase": "reconciled_existing_transcripts", "selected_count": len(records), "changed_count": sum(record["changed"] for record in records), "records": records}, ensure_ascii=False), flush=True)
        client.close()
        return 0
    feeds = {str(feed["_id"]): feed for feed in db.feeds.find({})}
    acquired, attempts = set(), []
    diagnostics = {"db_counts": {name: db[name].count_documents({}) for name in ("feeds", "episodes", "transcripts")}, "network_checks_complete": False}
    sources = collect_existing(db, feeds, acquired)
    write_corpus(output, sources, attempts, diagnostics)
    print(json.dumps({"phase": "existing_corpus_ready", "path": str(output), "source_count": len(sources)}, ensure_ascii=False), flush=True)
    if not args.existing_only:
        proxy = diagnose_youtube(feeds, diagnostics)
        nav, nav_error = BilibiliService._get("/x/web-interface/nav")
        diagnostics["bilibili_login"] = {"configured": bool(os.getenv("BILI_SESSDATA", "")), "valid": bool(nav and nav.get("isLogin")), "wbi_keys_present": bool(nav and nav.get("wbi_img"))}
        if nav_error:
            diagnostics["bilibili_login"]["error"] = safe_error(nav_error)
        write_corpus(output, sources, attempts, diagnostics)
        cutoff = sources[-1]["published"] if len(sources) == 10 else None
        seen = set()
        for episode in db.episodes.find({}).sort([("published", -1), ("_id", -1)]):
            guid = episode.get("guid") or str(episode["_id"])
            if guid in seen:
                continue
            seen.add(guid)
            if cutoff and (timestamp(episode.get("published")) or "") < cutoff:
                break
            copy_ids = [copy["_id"] for copy in db.episodes.find({"guid": guid})]
            if db.transcripts.find_one({"episode_id": {"$in": copy_ids}, "text": {"$nin": [None, ""]}}):
                continue
            if len(attempts) >= min(max(args.max_attempts, 0), 15):
                break
            attempt = {"episode_id": str(episode["_id"]), "guid": guid, "title": episode.get("title"), "started_at": utc_now()}
            try:
                if guid.startswith("youtube:"):
                    payload = fetch_youtube_transcript(guid.split(":", 1)[1], proxy)
                    source = "youtube"
                elif guid.startswith("bilibili:"):
                    if not diagnostics["bilibili_login"]["valid"]:
                        attempt.update(status="blocked", error="Bilibili login is invalid; no repeated subtitle request was issued.")
                        attempts.append(attempt)
                        continue
                    payload, error = BilibiliService.fetch_ai_subtitle(guid.split(":", 1)[1], title=episode.get("title", ""))
                    if error:
                        raise ValueError(error)
                    source = "bilibili"
                else:
                    payload = fetch_linked_transcript(episode)
                    source = "external"
                persisted = persist_transcript(db, episode, payload, source)
                if persisted:
                    acquired.add(guid)
                attempt.update(status="fetched_and_persisted" if persisted else "existing_kept", char_count=len(payload["text"]), transcript_source=source)
            except Exception as error:
                attempt.update(status="failed", error=safe_error(error))
            attempts.append(attempt)
            # Freeze the initial input batch so the five LLM runs see identical
            # content. New captures remain available in MongoDB and attempts.
            write_corpus(output, sources, attempts, diagnostics)
            print(json.dumps({"phase": "capture", **attempt}, ensure_ascii=False), flush=True)
        # Probe the current YouTube subtitle path once even if all latest videos
        # already have transcripts; this probe never overwrites existing text.
        latest_youtube = next((source for source in sources if source["guid"].startswith("youtube:")), None)
        if latest_youtube:
            try:
                probe = fetch_youtube_transcript(latest_youtube["guid"].split(":", 1)[1], proxy)
                diagnostics["youtube_subtitles"] = {"ok": True, "guid": latest_youtube["guid"], "char_count": len(probe["text"]), "existing_transcript_preserved": True}
            except Exception as error:
                diagnostics["youtube_subtitles"] = {"ok": False, "guid": latest_youtube["guid"], "error": safe_error(error)}
        diagnostics["input_batch_frozen"] = True
        diagnostics["input_char_count"] = sum(source["char_count"] for source in sources)
        diagnostics["network_checks_complete"] = True
        diagnostics["completed_at"] = utc_now()
        write_corpus(output, sources, attempts, diagnostics)
    print(json.dumps({"phase": "complete", "path": str(output), "new_transcripts": len(acquired), "attempts": attempts, "diagnostics": diagnostics, "sources": [{key: source[key] for key in ("id", "title", "feed", "published", "duration", "char_count", "material_type", "acquisition")} for source in sources]}, ensure_ascii=False), flush=True)
    client.close()
    return 0 if len(sources) == 10 else 1


if __name__ == "__main__":
    raise SystemExit(main())
