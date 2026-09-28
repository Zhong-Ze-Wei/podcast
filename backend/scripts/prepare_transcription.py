"""Explicit model download/preparation; never called by capability discovery."""
import argparse
import os
from pathlib import Path
import sys

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
load_dotenv(BACKEND / ".env")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--provider", choices=("local_whisper", "local_whisperx"), default="local_whisper")
    args = parser.parse_args()
    try:
        from faster_whisper.utils import download_model
    except ImportError:
        parser.error("Install the selected local-whisper or local-whisperx extra first.")
    model = os.getenv("WHISPER_MODEL", "base")
    cache = os.getenv("WHISPER_MODEL_DIR") or None
    print(f"Preparing {model}; missing model files will be downloaded.")
    path = model if Path(model).is_dir() else download_model(model, cache_dir=cache)
    if args.provider == "local_whisperx":
        from app.services.whisperx_service import get_model
        get_model(model)  # Explicitly prepares the configured VAD as well.
    print(f"Model prepared: {path}")
    print("Set TRANSCRIPTION_LOCAL_ENABLED=1 in .env and restart with the selected --extra.")


if __name__ == "__main__":
    main()
