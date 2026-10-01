"""Usage: python scripts/reconcile_audio_metadata.py [--apply] [--media-root PATH]."""
import argparse
import json
import sys
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))
load_dotenv(BACKEND_DIR / ".env")
from app.config import Config
from app.services.audio_metadata_service import reconcile_local_audio


def main():
    parser = argparse.ArgumentParser(description="Check audio flags; --apply writes reconciled availability.")
    parser.add_argument("--apply", action="store_true")
    parser.add_argument("--media-root", default=Config.MEDIA_ROOT)
    args = parser.parse_args()
    with MongoClient(Config.MONGO_URI) as client:
        result = reconcile_local_audio(client[Config.MONGO_DB], args.media_root, dry_run=not args.apply)
    print(json.dumps(result, ensure_ascii=False))


if __name__ == "__main__":
    main()
