# -*- coding: utf-8 -*-
"""
Transcripts API

转录管理接口
"""
import os

from flask import Blueprint, current_app, request
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime

from ..models.episode import Episode
from ..models.transcript import Transcript, to_bson_safe
from ..services.task_queue import task_queue
from ..services.episode_processing_service import EpisodeProcessingService, ProcessingConflict, ProcessingSubmissionFailed
from ..services.transcription_service import (
    TranscriptionService,
    _transcribe_video_sync as _run_video_transcription,
    _transcribe_with_assemblyai as _run_assemblyai,
    TRANSCRIPTION_PROVIDER_AUTO,
    TRANSCRIPTION_PROVIDER_OFFICIAL,
    TRANSCRIPTION_PROVIDER_LOCAL_WHISPER,
    TRANSCRIPTION_PROVIDER_LOCAL_WHISPERX,
    TRANSCRIPTION_PROVIDER_ASSEMBLYAI,
    TRANSCRIPTION_PROVIDER_MANUAL,
    SUPPORTED_TRANSCRIPTION_PROVIDERS,
    SUPPORTED_TRANSCRIPTION_LANGUAGES,
    CLOUD_TRANSCRIPTION_DISABLED_MESSAGE,
    _get_requested_provider,
    _get_requested_language,
    _resolve_transcription_provider,
    LOCAL_AI_INSTALL_HINT,
    _local_ai_available,
    _is_cloud_transcription_enabled,
    _get_local_audio_path,
    _download_official_transcript,
    _build_plain_text_segments,
    _should_ai_normalize_transcript,
    _save_transcript,
)

from ..services.youtube_service import YouTubeService
from ..services.bilibili_service import BilibiliService
from ..services.transcript_fetcher import TranscriptFetcher
from ..services.transcript_postprocessor import normalize_transcript
from .utils import success_response, error_response
from .decorators import require_role, current_owner_id, owner_filter, require_auth

transcripts_bp = Blueprint("transcripts", __name__)






def get_db():
    from .. import get_db as _get_db
    return _get_db()
















@transcripts_bp.route("/<episode_id>", methods=["GET"])
@require_auth
def get_transcript(episode_id):
    """获取单集转录"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one(owner_filter({"_id": oid}))
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    transcript = db.transcripts.find_one(owner_filter({"episode_id": oid}))
    if not transcript:
        return error_response("Transcript not found", "TRANSCRIPT_NOT_FOUND", 404)

    return success_response(Transcript.to_response(transcript))


@transcripts_bp.route("/<episode_id>", methods=["POST"])
@require_role("user", "admin")
def create_transcript(episode_id):
    """创建转录任务 (异步) - 使用AssemblyAI直接转录音频URL"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one(owner_filter({"_id": oid}))
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    payload = request.get_json(silent=True) or {}
    requested_provider = _get_requested_provider(payload)
    if not requested_provider:
        return error_response(
            "Unsupported transcription provider",
            "UNSUPPORTED_TRANSCRIPTION_PROVIDER",
            400
        )

    requested_language = _get_requested_language(payload)
    if requested_language is None and str(payload.get("language", "auto")).strip().lower() not in {"", "auto"}:
        return error_response(
            "Unsupported transcription language",
            "UNSUPPORTED_TRANSCRIPTION_LANGUAGE",
            400
        )

    download_if_needed = payload.get("download_if_needed", False)
    if not isinstance(download_if_needed, bool):
        return error_response("download_if_needed must be boolean", "INVALID_DOWNLOAD_IF_NEEDED", 400)

    provider = _resolve_transcription_provider(requested_provider, episode)
    if not provider:
        return error_response(
            "No official transcript is available. Choose local_whisper or assemblyai explicitly.",
            "TRANSCRIPTION_PROVIDER_REQUIRED",
            400
        )
    if provider == TRANSCRIPTION_PROVIDER_MANUAL:
        return error_response(
            "Manual transcripts are not available from this endpoint yet.",
            "MANUAL_TRANSCRIPT_REQUIRED",
            400
        )
    if provider == TRANSCRIPTION_PROVIDER_OFFICIAL and not episode.get("transcript_url"):
        return error_response(
            "No official transcript URL available for this episode",
            "NO_TRANSCRIPT_URL",
            400
        )
    if provider in {TRANSCRIPTION_PROVIDER_LOCAL_WHISPER, TRANSCRIPTION_PROVIDER_LOCAL_WHISPERX}:
        if not _local_ai_available(provider):
            return error_response(LOCAL_AI_INSTALL_HINT, "LOCAL_AI_NOT_INSTALLED", 400)
        if not _get_local_audio_path(episode) and not download_if_needed:
            return error_response(
                "Local audio file not found for this episode",
                "LOCAL_AUDIO_NOT_FOUND",
                400
            )
    if provider in {TRANSCRIPTION_PROVIDER_LOCAL_WHISPER, TRANSCRIPTION_PROVIDER_LOCAL_WHISPERX} and download_if_needed:
        if not _get_local_audio_path(episode) and not episode.get("audio_url") and not episode.get("guid", "").startswith(("youtube:", "bilibili:")):
            return error_response("No downloadable audio available", "NO_AUDIO_URL", 400)
    if provider == TRANSCRIPTION_PROVIDER_ASSEMBLYAI:
        if not _is_cloud_transcription_enabled():
            return error_response(
                CLOUD_TRANSCRIPTION_DISABLED_MESSAGE,
                "CLOUD_TRANSCRIPTION_DISABLED",
                423
            )
        if not episode.get("audio_url"):
            return error_response(
                "No audio URL available for this episode",
                "NO_AUDIO_URL",
                400
            )

    episode_status = episode.get("status", "new")
    dedup_key = f"transcribe:{oid}:{provider}:{requested_language or 'auto'}"
    processing = EpisodeProcessingService(db, task_queue)
    try:
        existing = processing.active_task_id(oid, "transcribe", dedup_key)
    except ProcessingConflict as error:
        return error_response(str(error), "TASK_IN_PROGRESS", 409)
    if existing:
        return success_response({"task_id": existing, "status": "queued", "provider": provider, "language": requested_language or "auto"})
    if episode.get("has_transcript") or episode_status in [Episode.STATUS_TRANSCRIBED, Episode.STATUS_SUMMARIZING, Episode.STATUS_SUMMARIZED]:
        return error_response("Episode already has a transcript", "ALREADY_TRANSCRIBED", 400)

    # 提交转录任务
    def do_transcribe(progress_callback=None):
        return TranscriptionService(db).run(
            str(oid),
            provider=provider,
            language=requested_language,
            download_if_needed=download_if_needed,
            progress_callback=progress_callback,
        )

    def rollback_episode_status(error):
        TranscriptionService(db).restore_episode_status(str(oid), error)


    try:
        task_id = processing.submit(
            episode, "transcribe", dedup_key, do_transcribe, current_owner_id(),
            on_failure=rollback_episode_status,
        )
    except ProcessingConflict as error:
        return error_response(str(error), "TASK_IN_PROGRESS", 409)
    except ProcessingSubmissionFailed as error:
        return error_response(str(error), "TASK_SUBMIT_FAILED", 503)

    return success_response({
        "task_id": task_id,
        "status": "queued",
        "provider": provider,
        "language": requested_language or "auto"
    })


@transcripts_bp.route("/<episode_id>/fetch-video-audio", methods=["POST"])
@require_role("user", "admin")
def transcribe_video_episode(episode_id):
    """
    视频剧集"立即转写"：yt-dlp 下载音轨 → 本地 Whisper 转写。

    适用于无字幕/字幕被禁用/字幕被串台校验拒收的 YouTube / B站剧集。
    """
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one(owner_filter({"_id": oid}))
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    from ..services import whisperx_service

    if not whisperx_service.is_available():
        return error_response(LOCAL_AI_INSTALL_HINT, "LOCAL_AI_NOT_INSTALLED", 400)

    guid = episode.get("guid", "")
    if guid.startswith("youtube:"):
        service, vid = YouTubeService, guid.replace("youtube:", "")
    elif guid.startswith("bilibili:"):
        service, vid = BilibiliService, guid.replace("bilibili:", "")
    else:
        return error_response(
            "Episode is not a video episode", "NOT_VIDEO_EPISODE", 400
        )

    processing = EpisodeProcessingService(db, task_queue)
    dedup_key = f"transcribe:{oid}:local_whisperx:auto"
    try:
        existing = processing.active_task_id(oid, "transcribe", dedup_key)
    except ProcessingConflict as error:
        return error_response(str(error), "TASK_IN_PROGRESS", 409)
    if existing:
        return success_response({"task_id": existing, "status": "queued"})
    if db.transcripts.find_one({"episode_id": oid}):
        return error_response("Episode already has a transcript", "ALREADY_TRANSCRIBED", 400)

    def do_fetch_and_transcribe(progress_callback=None):
        return _transcribe_video_sync(str(oid), service, vid, progress_callback)

    try:
        task_id = processing.submit(
            episode, "transcribe", dedup_key, do_fetch_and_transcribe, current_owner_id(),
            on_failure=lambda error: TranscriptionService(db).restore_episode_status(str(oid), error),
        )
    except ProcessingConflict as error:
        return error_response(str(error), "TASK_IN_PROGRESS", 409)
    except ProcessingSubmissionFailed as error:
        return error_response(str(error), "TASK_SUBMIT_FAILED", 503)
    return success_response({"task_id": task_id, "status": "queued"})


def _transcribe_video_sync(episode_id, service, vid, progress_callback=None):
    return _run_video_transcription(get_db(), episode_id, service, vid, progress_callback)










def _transcribe_sync(episode_id, provider=TRANSCRIPTION_PROVIDER_AUTO, language=None, progress_callback=None):
    return TranscriptionService(get_db()).run(episode_id, provider, language, progress_callback=progress_callback)


def _transcribe_with_assemblyai(audio_url, episode_oid, episode, progress_callback=None, language=None):
    return _run_assemblyai(get_db(), audio_url, episode_oid, episode, progress_callback, language)


@transcripts_bp.route("/<episode_id>", methods=["DELETE"])
@require_role("user", "admin")
def delete_transcript(episode_id):
    """删除转录"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one(owner_filter({"_id": oid}))
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    processing = EpisodeProcessingService(db, task_queue)
    try:
        with processing.edit_artifacts(oid):
            result = db.transcripts.delete_one(owner_filter({"episode_id": oid}))
            if result.deleted_count == 0:
                return error_response("Transcript not found", "TRANSCRIPT_NOT_FOUND", 404)
            db.episodes.update_one({"_id": oid}, {"$set": {"has_transcript": False}})
            processing.restore_status(oid, "transcribe", None)
    except ProcessingConflict as error:
        return error_response(str(error), "TASK_IN_PROGRESS", 409)

    return success_response(message="Transcript deleted successfully")


@transcripts_bp.route("/<episode_id>/fetch", methods=["POST"])
@require_role("user", "admin")
def fetch_external_transcript(episode_id):
    """从外部URL获取转录"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one(owner_filter({"_id": oid}))
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    # 获取转录URL
    transcript_url = episode.get("transcript_url")
    if not transcript_url:
        return error_response("No transcript URL available for this episode", "NO_TRANSCRIPT_URL", 400)

    # 抓取转录
    result, error = TranscriptFetcher.fetch_transcript_result(transcript_url)
    if error:
        return error_response(error, "FETCH_FAILED", 400)
    text = result.text if result else ""
    segments = result.segments or _build_plain_text_segments(text)

    # Network fetching finishes before the short shared resource-write lock.
    processing = EpisodeProcessingService(db, task_queue)
    try:
        with processing.edit_artifacts(oid) as current:
            _save_transcript(db, oid, current, text, segments, source="external", model="fetched")
            processing.restore_status(oid, "transcribe", None)
    except ProcessingConflict as error:
        return error_response(str(error), "TASK_IN_PROGRESS", 409)

    return success_response({
        "text_length": len(text),
        "source": "external",
        "transcript_url": transcript_url
    }, "Transcript fetched successfully")


@transcripts_bp.route("/<episode_id>/check-external", methods=["GET"])
@require_auth
def check_external_transcript(episode_id):
    """检查是否有可用的外部转录"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one(owner_filter({"_id": oid}))
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    transcript_url = episode.get("transcript_url")
    if not transcript_url:
        return success_response({
            "has_external_transcript": False,
            "transcript_url": None
        })

    # 验证URL是否可访问
    is_valid = TranscriptFetcher.validate_transcript_url(transcript_url)

    return success_response({
        "has_external_transcript": is_valid,
        "transcript_url": transcript_url if is_valid else None
    })
