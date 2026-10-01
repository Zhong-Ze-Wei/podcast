"""Resolve a published local audio file within the configured media directory."""
import os


def local_audio_path(episode, media_root):
    local_path = episode.get("local_path") or episode.get("audio_path")
    if not local_path:
        return None

    media_root = os.path.abspath(media_root)
    candidate = local_path
    if not os.path.isabs(candidate):
        candidate = os.path.join(media_root, candidate)
    candidate = os.path.abspath(candidate)

    try:
        if os.path.commonpath([media_root, candidate]) != media_root:
            return None
    except ValueError:
        return None

    if not os.path.isfile(candidate):
        return None
    return candidate

