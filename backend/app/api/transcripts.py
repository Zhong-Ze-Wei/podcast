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
    """创建转录任务 (异步) - 使用AssemblyAI直接转录音频URL"""
    db = get_db()

    try:
        oid = ObjectId(episode_id)
    except InvalidId:
        return error_response("Invalid episode ID", "INVALID_ID", 400)

    episode = db.episodes.find_one({"_id": oid})
    if not episode:
        return error_response("Episode not found", "EPISODE_NOT_FOUND", 404)

    # 检查是否已经在转录或已完成
    episode_status = episode.get("status", "new")
    if episode_status == Episode.STATUS_TRANSCRIBING:
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

    # 检查是否有音频URL
    audio_url = episode.get("audio_url")
    if not audio_url:
        return error_response(
            "No audio URL available for this episode",
            "NO_AUDIO_URL",
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
    """同步执行转录 - 使用AssemblyAI直接处理音频URL"""
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

    # 使用 AssemblyAI 直接转录音频URL
    audio_url = episode.get("audio_url")
    if not audio_url:
        raise ValueError("No audio URL available")

    if progress_callback:
        progress_callback(20)

    # 调用 AssemblyAI
    result = _transcribe_with_assemblyai(audio_url, oid, episode, progress_callback)

    if progress_callback:
        progress_callback(100)

    return result


def _transcribe_with_assemblyai(audio_url: str, episode_oid, episode: dict, progress_callback=None):
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

    # 配置转录
    config = aai.TranscriptionConfig(
        speaker_labels=True,      # 说话人分离
        auto_chapters=True,       # 自动章节
        entity_detection=True,    # 实体识别
    )

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
    db = get_db()
    transcript_doc = {
        "episode_id": episode_oid,
        "text": transcript.text,
        "segments": segments,
        "chapters": chapters,
        "entities": list({e["text"]: e for e in entities}.values())[:50],  # 去重，最多50个
        "speakers": speakers,
        "language": getattr(transcript, 'language_code', None) or getattr(transcript, 'language', 'en'),
        "duration": transcript.audio_duration,
        "source": "assemblyai",
        "created_at": datetime.utcnow(),
        "updated_at": datetime.utcnow()
    }

    # 检查是否已存在
    existing = db.transcripts.find_one({"episode_id": episode_oid})
    if existing:
        db.transcripts.update_one(
            {"episode_id": episode_oid},
            {"$set": transcript_doc}
        )
    else:
        db.transcripts.insert_one(transcript_doc)

    # 更新 episode 状态
    db.episodes.update_one(
        {"_id": episode_oid},
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
