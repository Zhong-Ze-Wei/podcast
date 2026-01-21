# -*- coding: utf-8 -*-
"""
Transcripts API

转录管理接口
"""
from flask import Blueprint, request
from bson import ObjectId
from bson.errors import InvalidId
from datetime import datetime

from ..models.episode import Episode
from ..models.transcript import Transcript
from ..services.task_queue import task_queue
from ..services.transcript_fetcher import TranscriptFetcher
from .utils import success_response, error_response

transcripts_bp = Blueprint("transcripts", __name__)


def get_db():
    from .. import get_db as _get_db
    return _get_db()


@transcripts_bp.route("/<episode_id>", methods=["GET"])
def get_transcript(episode_id):
    """获取单集转录"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    transcript = db.transcripts.find_one({"episode_id": oid})
    if not transcript:
        return error_response("Transcript not found", "TRANSCRIPT_NOT_FOUND", 404)

    return success_response(Transcript.to_response(transcript))


@transcripts_bp.route("/<episode_id>", methods=["POST"])
def create_transcript(episode_id):
    """创建转录任务 (异步)"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    # 检查是否可以转录
    episode_status = episode.get("status", "new")
    if not Episode.can_transcribe(episode_status):
        # 提供更详细的错误信息
        if episode_status == Episode.STATUS_NEW:
            return error_response(
                "Audio needs to be downloaded first",
                "AUDIO_NOT_DOWNLOADED",
                400
            )
        elif episode_status in [Episode.STATUS_TRANSCRIBING]:
            return error_response(
                "Episode is already being transcribed",
                "ALREADY_TRANSCRIBING",
                400
            )
        elif episode_status in [Episode.STATUS_TRANSCRIBED, Episode.STATUS_SUMMARIZING, Episode.STATUS_SUMMARIZED]:
            return error_response(
                "Episode already has a transcript",
                "ALREADY_TRANSCRIBED",
                400
            )
        else:
            return error_response(
                "Episode cannot be transcribed in current state",
                "INVALID_STATE",
                400
            )

    # 检查是否有进行中的任务
    existing_task = db.tasks.find_one({
        "episode_id": str(oid),
        "task_type": "transcribe",
        "status": {"$in": ["pending", "processing"]}
    })
    if existing_task:
        return error_response(
            "Transcribe task already in progress",
            "TASK_IN_PROGRESS",
            409
        )

    # 提交转录任务
    def do_transcribe(progress_callback=None):
        return _transcribe_sync(str(oid), progress_callback)

    task_id = task_queue.submit(
        task_type="transcribe",
        func=do_transcribe,
        episode_id=str(oid)
    )

    # 更新状态为转录中
    db.episodes.update_one(
        {"_id": oid},
        {"$set": {"status": Episode.STATUS_TRANSCRIBING}}
    )

    return success_response({
        "task_id": task_id,
        "status": "queued"
    })


def _download_official_transcript(url: str, progress_callback=None):
    """
    下载官方字幕

    Returns:
        (text, segments, source) 或 None
    """
    if progress_callback:
        progress_callback(20)

    text, error = TranscriptFetcher.fetch_transcript(url)

    if progress_callback:
        progress_callback(60)

    if text:
        # 将文本分段（按段落或句号分割）
        segments = []
        paragraphs = text.split('\n\n')
        for para in paragraphs:
            if para.strip():
                segments.append({"text": para.strip(), "time": ""})

        source = "official"
        if ".srt" in url:
            source = "official_srt"
        elif ".vtt" in url:
            source = "official_vtt"
        elif ".json" in url:
            source = "official_json"

        return text, segments, source

    return None


def _save_transcript(db, episode_oid, episode, text, segments, source):
    """保存转录到数据库"""
    transcript_doc = Transcript.create(
        episode_id=episode_oid,
        text=text,
        segments=segments,
        language=episode.get("language", ""),
        model=source
    )

    existing = db.transcripts.find_one({"episode_id": episode_oid})
    if existing:
        db.transcripts.update_one(
            {"episode_id": episode_oid},
            {"$set": {
                "text": text,
                "segments": segments,
                "model": source,
                "updated_at": datetime.utcnow()
            }}
        )
    else:
        db.transcripts.insert_one(transcript_doc)

    # 更新 episode 状态
    db.episodes.update_one(
        {"_id": episode_oid},
        {"$set": {
            "status": Episode.STATUS_TRANSCRIBED,
            "has_transcript": True,
            "updated_at": datetime.utcnow()
        }}
    )


def _transcribe_sync(episode_id: str, progress_callback=None):
    """同步执行转录"""
    import os
    from ..config import Config

    db = get_db()
    oid = ObjectId(episode_id)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        raise ValueError("Episode not found")

    if progress_callback:
        progress_callback(10)

    # 优先尝试下载官方字幕
    transcript_url = episode.get("transcript_url")
    if transcript_url:
        result = _download_official_transcript(transcript_url, progress_callback)
        if result:
            transcript_text, segments, source = result
            _save_transcript(db, oid, episode, transcript_text, segments, source)
            if progress_callback:
                progress_callback(100)
            return {"text_length": len(transcript_text), "source": source}

    # 无官方字幕，检查音频文件准备 AI 转录
    local_path = episode.get("local_path")
    if not local_path:
        raise ValueError("No official transcript and audio not downloaded")

    audio_path = os.path.join(Config.MEDIA_ROOT, local_path)
    if not os.path.exists(audio_path):
        raise ValueError("Audio file not found")

    if progress_callback:
        progress_callback(20)

    # 使用 Faster-Whisper 进行 AI 转录
    from ..services.whisper_service import transcribe_audio, is_available

    if not is_available():
        raise RuntimeError("Whisper not available. Install: pip install faster-whisper")

    # 创建进度回调包装器（将Whisper的进度映射到20-90区间）
    def whisper_progress(pct):
        if progress_callback:
            # 映射 10-95 到 20-90
            mapped = 20 + int((pct - 10) * 70 / 85)
            progress_callback(min(mapped, 90))

    transcript_text, segments, detected_lang = transcribe_audio(
        audio_path,
        model_name="small",  # 使用small模型，平衡速度和质量
        progress_callback=whisper_progress
    )

    if progress_callback:
        progress_callback(90)

    # 保存转录
    _save_transcript(db, oid, episode, transcript_text, segments, "whisper-small")

    if progress_callback:
        progress_callback(100)

    return {"text_length": len(transcript_text), "source": "whisper-small", "language": detected_lang}


@transcripts_bp.route("/<episode_id>", methods=["DELETE"])
def delete_transcript(episode_id):
    """删除转录"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    result = db.transcripts.delete_one({"episode_id": oid})
    if result.deleted_count == 0:
        return error_response("Transcript not found", "TRANSCRIPT_NOT_FOUND", 404)

    # 如果状态是transcribed，回退到downloaded
    if episode.get("status") == Episode.STATUS_TRANSCRIBED:
        db.episodes.update_one(
            {"_id": oid},
            {"$set": {"status": Episode.STATUS_DOWNLOADED}}
        )

    return success_response(message="Transcript deleted successfully")


@transcripts_bp.route("/<episode_id>/fetch", methods=["POST"])
def fetch_external_transcript(episode_id):
    """从外部URL获取转录"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    # 获取转录URL
    transcript_url = episode.get("transcript_url")
    if not transcript_url:
        return error_response("No transcript URL available for this episode", "NO_TRANSCRIPT_URL", 400)

    # 抓取转录
    text, error = TranscriptFetcher.fetch_transcript(transcript_url)
    if error:
        return error_response(error, "FETCH_FAILED", 400)

    # 保存转录
    transcript_doc = Transcript.create(
        episode_id=oid,
        text=text,
        segments=[],
        language=episode.get("language", ""),
        source="external",
        model="fetched"
    )

    # 检查是否已存在
    existing = db.transcripts.find_one({"episode_id": oid})
    if existing:
        db.transcripts.update_one(
            {"episode_id": oid},
            {"$set": {
                "text": text,
                "segments": [],
                "source": "external",
                "model": "fetched",
                "updated_at": datetime.utcnow()
            }}
        )
    else:
        db.transcripts.insert_one(transcript_doc)

    # 更新episode状态
    db.episodes.update_one(
        {"_id": oid},
        {"$set": {
            "status": Episode.STATUS_TRANSCRIBED,
            "has_transcript": True,
            "updated_at": datetime.utcnow()
        }}
    )

    return success_response({
        "text_length": len(text),
        "source": "external",
        "transcript_url": transcript_url
    }, "Transcript fetched successfully")


@transcripts_bp.route("/<episode_id>/check-external", methods=["GET"])
def check_external_transcript(episode_id):
    """检查是否有可用的外部转录"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
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
