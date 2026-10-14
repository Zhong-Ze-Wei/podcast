"""Transcription providers and their backend-owned download dependency."""
import os
from datetime import datetime
from bson import ObjectId
from flask import current_app
from ..models.episode import Episode
from ..models.transcript import Transcript, to_bson_safe
from .transcript_fetcher import TranscriptFetcher
from .transcript_postprocessor import normalize_transcript
from .download_service import DownloadService
from .audio_storage import local_audio_path


class TranscriptionService:
    def __init__(self, db):
        self.db = db

    def run(self, episode_id, provider, language=None, download_if_needed=False, progress_callback=None):
        episode = self.db.episodes.find_one({"_id": ObjectId(episode_id)})
        if not episode:
            raise ValueError("Episode not found")
        local_provider = provider in {TRANSCRIPTION_PROVIDER_LOCAL_WHISPER, TRANSCRIPTION_PROVIDER_LOCAL_WHISPERX}
        needs_download = local_provider and not _get_local_audio_path(episode)
        if needs_download:
            if not download_if_needed:
                raise ValueError("Local audio file not found")
            if progress_callback:
                progress_callback((0, "正在下载转写所需音频"))
            def downloading(value):
                percent = value[0] if isinstance(value, tuple) else value
                progress_callback((int(percent * 0.3), "正在下载转写所需音频"))
            DownloadService(self.db).download(episode_id, downloading if progress_callback else None)
        self.db.episodes.update_one({"_id": ObjectId(episode_id)}, {"$set": {"status": Episode.STATUS_TRANSCRIBING}})
        def transcribing(value):
            percent = value[0] if isinstance(value, tuple) else value
            progress_callback((30 + int(percent * 0.7) if needs_download else percent, "正在转写音频"))
        return _transcribe_sync(self.db, episode_id, provider, language, transcribing if progress_callback else None)

    def restore_episode_status(self, episode_id, error):
        oid = ObjectId(episode_id)
        episode = self.db.episodes.find_one({"_id": oid})
        if not episode:
            return
        if episode.get("has_summary"):
            status = Episode.STATUS_SUMMARIZED
        elif episode.get("has_transcript"):
            status = Episode.STATUS_TRANSCRIBED
        elif _get_local_audio_path(episode):
            status = Episode.STATUS_DOWNLOADED
        else:
            status = Episode.STATUS_NEW
        self.db.episodes.update_one({"_id": oid}, {"$set": {
            "status": status, "last_transcript_error": str(error), "updated_at": datetime.utcnow(),
        }})


TRANSCRIPTION_PROVIDER_AUTO = "auto"


TRANSCRIPTION_PROVIDER_OFFICIAL = "official"


TRANSCRIPTION_PROVIDER_LOCAL_WHISPER = "local_whisper"


TRANSCRIPTION_PROVIDER_LOCAL_WHISPERX = "local_whisperx"


TRANSCRIPTION_PROVIDER_ASSEMBLYAI = "assemblyai"


TRANSCRIPTION_PROVIDER_MANUAL = "manual"


SUPPORTED_TRANSCRIPTION_PROVIDERS = {
    TRANSCRIPTION_PROVIDER_AUTO,
    TRANSCRIPTION_PROVIDER_OFFICIAL,
    TRANSCRIPTION_PROVIDER_LOCAL_WHISPER,
    TRANSCRIPTION_PROVIDER_LOCAL_WHISPERX,
    TRANSCRIPTION_PROVIDER_ASSEMBLYAI,
    TRANSCRIPTION_PROVIDER_MANUAL,
}


SUPPORTED_TRANSCRIPTION_LANGUAGES = {
    "auto",
    "zh",
    "en",
    "en_us",
    "en_uk",
    "ja",
    "ko",
    "es",
    "fr",
    "de",
}


CLOUD_TRANSCRIPTION_DISABLED_MESSAGE = (
    "Cloud transcription is disabled. Set TRANSCRIPTION_CLOUD_ENABLED=1 to enable AssemblyAI."
)


def _get_requested_provider(payload=None):
    payload = payload or {}
    provider = payload.get("provider") or current_app.config.get(
        "TRANSCRIPTION_DEFAULT_PROVIDER",
        TRANSCRIPTION_PROVIDER_OFFICIAL,
    )
    provider = str(provider).strip().lower()
    if provider not in SUPPORTED_TRANSCRIPTION_PROVIDERS:
        return None
    return provider


def _get_requested_language(payload=None):
    payload = payload or {}
    language = payload.get("language") or current_app.config.get(
        "TRANSCRIPTION_DEFAULT_LANGUAGE",
        "auto",
    )
    language = str(language or "auto").strip().lower().replace("-", "_")
    if not language:
        language = "auto"
    if language not in SUPPORTED_TRANSCRIPTION_LANGUAGES:
        return None
    return None if language == "auto" else language


def _resolve_transcription_provider(provider, episode):
    if provider == TRANSCRIPTION_PROVIDER_AUTO:
        if episode.get("transcript_url"):
            return TRANSCRIPTION_PROVIDER_OFFICIAL
        return None
    return provider


LOCAL_AI_INSTALL_HINT = (
    "本地转写组件未安装：在仓库根目录运行 python setup_local_ai.py，"
    "脚本会按机器配置（Windows/macOS/Linux、有无 NVIDIA GPU）自动选择合适版本（约 1-3GB）"
)


def _local_ai_available(provider: str) -> bool:
    from ..services import whisper_service, whisperx_service

    if provider == TRANSCRIPTION_PROVIDER_LOCAL_WHISPER:
        return whisper_service.is_available()
    if provider == TRANSCRIPTION_PROVIDER_LOCAL_WHISPERX:
        return whisperx_service.is_available()
    return True


def _is_cloud_transcription_enabled():
    return bool(current_app.config.get("TRANSCRIPTION_CLOUD_ENABLED", False))


def _get_local_audio_path(episode):
    return local_audio_path(episode, current_app.config.get("MEDIA_ROOT", "."))


def _transcribe_video_sync(db, episode_id, service, vid, progress_callback=None):
    """下载视频音轨并本地转写（复用现有 _transcribe_sync）。

    转写结果为空时（无人声视频，如纯音乐画面）清理空 transcript、
    回退状态并打 no_speech 标记，避免摘要管线与自动兜底反复尝试。
    """
    oid = ObjectId(episode_id)

    if progress_callback:
        progress_callback(5)

    audio_path, error = service.download_audio(vid)
    if error:
        raise ValueError(error)
    if progress_callback:
        progress_callback(20)

    db.episodes.update_one(
        {"_id": oid},
        {"$set": {"local_path": audio_path, "updated_at": datetime.utcnow()}},
    )

    provider = TRANSCRIPTION_PROVIDER_LOCAL_WHISPERX
    result = _transcribe_sync(
        db, episode_id,
        provider=provider,
        language=None,
        progress_callback=lambda p: progress_callback(20 + int(p * 0.8)) if progress_callback else None,
    )

    transcript = db.transcripts.find_one({"episode_id": oid})
    if transcript and not (transcript.get("text") or "").strip():
        db.transcripts.delete_one({"_id": transcript["_id"]})
        db.episodes.update_one(
            {"_id": oid},
            {"$set": {"status": Episode.STATUS_NEW, "no_speech": True, "updated_at": datetime.utcnow()}},
        )
        return {"no_speech": True}
    return result


def _download_official_transcript(url: str, progress_callback=None):
    """
    下载官方字幕

    Returns:
        (text, segments, source) 或 None
    """
    if progress_callback:
        progress_callback(20)

    result, error = TranscriptFetcher.fetch_transcript_result(url)

    if progress_callback:
        progress_callback(60)

    if error:
        raise ValueError(f"Official transcript could not be fetched: {error}")

    text = result.text if result else None
    if text:
        # 将文本分段（按段落或句号分割）
        segments = result.segments or _build_plain_text_segments(text)

        source = "official"
        if ".srt" in url:
            source = "official_srt"
        elif ".vtt" in url:
            source = "official_vtt"
        elif ".json" in url:
            source = "official_json"

        return text, segments, source

    return None


def _build_plain_text_segments(text: str):
    """Build display-friendly segments from fetched transcript text."""
    if not text:
        return []

    segments = []
    for paragraph in text.split("\n\n"):
        normalized = " ".join(paragraph.split())
        if normalized:
            segments.append({"text": normalized, "time": ""})

    if len(segments) > 1:
        return segments

    return [{"text": " ".join(text.split()), "time": ""}] if text.strip() else []


def _should_ai_normalize_transcript():
    return bool(current_app.config.get("TRANSCRIPTION_AI_NORMALIZE_ENABLED", False))


def _save_transcript(db, episode_oid, episode, text, segments, source, language=None, model=None):
    """保存转录到数据库"""
    text, segments, postprocess = normalize_transcript(
        text=text,
        segments=segments,
        language=language or episode.get("language", ""),
        use_ai=_should_ai_normalize_transcript(),
    )

    transcript_doc = Transcript.create(
        episode_id=episode_oid,
        owner_id=episode.get("owner_id"),
        text=text,
        segments=segments,
        language=language or episode.get("language", ""),
        source=source,
        model=model or source
    )
    transcript_doc["postprocess"] = to_bson_safe(postprocess)

    owner_id = episode.get("owner_id")
    existing = db.transcripts.find_one({"owner_id": owner_id, "episode_id": episode_oid})
    if existing:
        db.transcripts.update_one(
            {"owner_id": owner_id, "episode_id": episode_oid},
            {"$set": {
                "text": text,
                "segments": to_bson_safe(segments),
                "source": source,
                "model": model or source,
                "language": language or episode.get("language", ""),
                "postprocess": to_bson_safe(postprocess),
                "updated_at": datetime.utcnow()
            }}
        )
    else:
        db.transcripts.insert_one(transcript_doc)

    # 更新 episode 状态
    db.episodes.update_one(
        {"_id": episode_oid, "owner_id": owner_id},
        {"$set": {
            "status": Episode.STATUS_TRANSCRIBED,
            "has_transcript": True,
            "transcript_source": source,
            "updated_at": datetime.utcnow()
        }}
    )


def _transcribe_sync(db, episode_id: str, provider=TRANSCRIPTION_PROVIDER_AUTO, language=None, progress_callback=None):
    """同步执行指定 provider 的转录。"""
    oid = ObjectId(episode_id)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        raise ValueError("Episode not found")

    provider = _resolve_transcription_provider(provider, episode)
    if not provider:
        raise ValueError("No transcription provider selected")

    if progress_callback:
        progress_callback(10)

    # 优先尝试下载官方字幕
    transcript_url = episode.get("transcript_url")
    if provider == TRANSCRIPTION_PROVIDER_OFFICIAL:
        if not transcript_url:
            raise ValueError("No official transcript URL available")
        result = _download_official_transcript(transcript_url, progress_callback)
        if result:
            transcript_text, segments, source = result
            _save_transcript(db, oid, episode, transcript_text, segments, source)
            if progress_callback:
                progress_callback(100)
            return {"text_length": len(transcript_text), "source": source}
        raise ValueError("Official transcript could not be fetched")

    if provider == TRANSCRIPTION_PROVIDER_LOCAL_WHISPER:
        from ..services.whisper_service import transcribe_audio

        local_audio_path = _get_local_audio_path(episode)
        if not local_audio_path:
            raise ValueError("Local audio file not found")

        if progress_callback:
            progress_callback(20)

        model_name = current_app.config.get("WHISPER_MODEL", "base")
        transcript_text, segments, language = transcribe_audio(
            local_audio_path,
            model_name=model_name,
            language=language,
            progress_callback=progress_callback,
        )
        device = current_app.config.get("WHISPER_DEVICE", "cpu")
        compute_type = current_app.config.get("WHISPER_COMPUTE_TYPE", "int8")
        model = f"faster-whisper:{model_name}:{device}:{compute_type}"
        _save_transcript(
            db,
            oid,
            episode,
            transcript_text,
            segments,
            TRANSCRIPTION_PROVIDER_LOCAL_WHISPER,
            language=language,
            model=model,
        )
        if progress_callback:
            progress_callback(100)
        return {
            "text_length": len(transcript_text),
            "source": TRANSCRIPTION_PROVIDER_LOCAL_WHISPER,
            "model": model,
            "language": language,
        }

    if provider == TRANSCRIPTION_PROVIDER_LOCAL_WHISPERX:
        from ..services.whisperx_service import transcribe_audio

        local_audio_path = _get_local_audio_path(episode)
        if not local_audio_path:
            raise ValueError("Local audio file not found")

        if progress_callback:
            progress_callback(20)

        model_name = current_app.config.get("WHISPER_MODEL", "base")
        transcript_text, segments, language = transcribe_audio(
            local_audio_path,
            model_name=model_name,
            language=language,
            progress_callback=progress_callback,
        )
        device = current_app.config.get("WHISPER_DEVICE", "cpu")
        compute_type = current_app.config.get("WHISPER_COMPUTE_TYPE", "int8")
        model = f"whisperx:{model_name}:{device}:{compute_type}"
        _save_transcript(
            db,
            oid,
            episode,
            transcript_text,
            segments,
            TRANSCRIPTION_PROVIDER_LOCAL_WHISPERX,
            language=language,
            model=model,
        )
        if progress_callback:
            progress_callback(100)
        return {
            "text_length": len(transcript_text),
            "source": TRANSCRIPTION_PROVIDER_LOCAL_WHISPERX,
            "model": model,
            "language": language,
        }

    if provider != TRANSCRIPTION_PROVIDER_ASSEMBLYAI:
        raise ValueError(f"Unsupported transcription provider: {provider}")

    if not _is_cloud_transcription_enabled():
        raise RuntimeError(CLOUD_TRANSCRIPTION_DISABLED_MESSAGE)

    # 使用 AssemblyAI 直接转录音频URL
    audio_url = episode.get("audio_url")
    if not audio_url:
        raise ValueError("No audio URL available")

    if progress_callback:
        progress_callback(20)

    # 调用 AssemblyAI
    result = _transcribe_with_assemblyai(db, audio_url, oid, episode, progress_callback, language=language)

    if progress_callback:
        progress_callback(100)

    return result


def _transcribe_with_assemblyai(db, audio_url: str, episode_oid, episode: dict, progress_callback=None, language=None):
    """使用 AssemblyAI 进行转录（带说话人分离）"""
    import os
    import assemblyai as aai
    from dotenv import load_dotenv

    # 加载环境变量
    env_path = os.path.join(os.path.dirname(__file__), '..', '..', '..', '.env')
    load_dotenv(env_path)

    api_key = os.getenv('ASSEMBLYAI_API_KEY')
    if not api_key:
        raise RuntimeError("ASSEMBLYAI_API_KEY not configured in .env")

    aai.settings.api_key = api_key

    if progress_callback:
        progress_callback(30)

    config_kwargs = {
        "speech_models": ["universal-3-pro", "universal-2"],
        "speaker_labels": True,
    }
    if language:
        config_kwargs["language_code"] = language
        if language.startswith("en"):
            config_kwargs["auto_chapters"] = True
            config_kwargs["entity_detection"] = True
    else:
        config_kwargs["language_detection"] = True
        config_kwargs["auto_chapters"] = True
        config_kwargs["entity_detection"] = True

    config = aai.TranscriptionConfig(**config_kwargs)

    # 执行转录
    transcriber = aai.Transcriber()
    transcript = transcriber.transcribe(audio_url, config=config)

    if transcript.status == aai.TranscriptStatus.error:
        raise RuntimeError(f"AssemblyAI error: {transcript.error}")

    if progress_callback:
        progress_callback(80)

    # 构建 segments (带说话人标签)
    segments = []
    for u in transcript.utterances:
        segments.append({
            "start": u.start / 1000,  # ms -> seconds
            "end": u.end / 1000,
            "speaker": u.speaker,
            "text": u.text
        })

    # 构建 chapters
    chapters = []
    if transcript.chapters:
        for ch in transcript.chapters:
            chapters.append({
                "start": ch.start / 1000,
                "end": ch.end / 1000,
                "headline": ch.headline,
                "summary": ch.summary
            })

    # 构建 entities
    entities = []
    if transcript.entities:
        for ent in transcript.entities:
            entities.append({
                "text": ent.text,
                "entity_type": ent.entity_type.value if hasattr(ent.entity_type, 'value') else str(ent.entity_type)
            })

    speakers = list(set(u.speaker for u in transcript.utterances))

    # 保存到数据库
    transcript_doc = to_bson_safe({
        "episode_id": episode_oid,
        "owner_id": episode.get("owner_id"),
        "text": transcript.text,
        "segments": segments,
        "chapters": chapters,
        "entities": list({e["text"]: e for e in entities}.values())[:50],  # 去重，最多50个
        "speakers": speakers,
        "language": getattr(transcript, 'language_code', None) or getattr(transcript, 'language', language or 'en'),
        "duration": transcript.audio_duration,
        "source": "assemblyai",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    })

    transcript_doc["text"], transcript_doc["segments"], postprocess = normalize_transcript(
        text=transcript_doc.get("text", ""),
        segments=transcript_doc.get("segments", []),
        language=transcript_doc.get("language", ""),
        use_ai=_should_ai_normalize_transcript(),
    )
    transcript_doc["postprocess"] = to_bson_safe(postprocess)

    # 检查是否已存在
    existing = db.transcripts.find_one({"owner_id": episode.get("owner_id"), "episode_id": episode_oid})
    if existing:
        db.transcripts.update_one(
            {"owner_id": episode.get("owner_id"), "episode_id": episode_oid},
            {"$set": transcript_doc}
        )
    else:
        db.transcripts.insert_one(transcript_doc)

    # 更新 episode 状态
    db.episodes.update_one(
        {"_id": episode_oid, "owner_id": episode.get("owner_id")},
        {"$set": {
            "status": Episode.STATUS_TRANSCRIBED,
            "has_transcript": True,
            "transcript_source": "assemblyai",
            "updated_at": datetime.utcnow()
        }}
    )

    return {
        "text_length": len(transcript.text),
        "source": "assemblyai",
        "speakers": len(speakers),
        "chapters": len(chapters)
    }

