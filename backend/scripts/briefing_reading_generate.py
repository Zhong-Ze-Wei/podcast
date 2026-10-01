"""对已取得的真实文稿精选一次原话，并按需生成共享单篇解读。"""
import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND / ".env")
sys.path.insert(0, str(BACKEND))

from app.services.briefing_reading_service import BriefingReadingService


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--topic", default="")
    parser.add_argument("--source", nargs="*", help="如 S01 S02 S08；不传时仅生成精选")
    parser.add_argument("--all-readings", action="store_true")
    parser.add_argument("--readings-only", action="store_true")
    args = parser.parse_args()
    service = BriefingReadingService()
    progress = lambda value: print(json.dumps({"progress": value}, ensure_ascii=False), flush=True)
    if not args.readings_only:
        result = service.generate_edition(topic=args.topic, progress_callback=progress)
        edition = result["edition"]
        print(json.dumps({"edition_id": edition["id"], "items": edition["sections"][0]["items"], "threads": edition["threads"], "usage": edition["usage"]}, ensure_ascii=False), flush=True)
    source_ids = [source["id"] for source in service.report_service.corpus()["sources"]] if args.all_readings else args.source or []
    for source_id in source_ids:
        result = service.generate_reading(source_id, progress_callback=progress)
        reading = result["reading"]
        print(json.dumps({"source_id": source_id, "reading_id": reading["id"], "takeaway": reading["takeaway"], "points": reading["points"], "usage": reading["usage"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
