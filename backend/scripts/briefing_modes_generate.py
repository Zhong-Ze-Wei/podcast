"""从现有真实全文记录生成五种内容模式，不下载或重新转录。"""
import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND / ".env")
sys.path.insert(0, str(BACKEND))

from app.services.briefing_modes_service import BriefingModesService, MODE_INDEX


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["all", *MODE_INDEX], default="all")
    parser.add_argument("--topic", default="")
    args = parser.parse_args()
    service = BriefingModesService()
    result = service.generate(args.mode, args.topic, progress_callback=lambda value: print(json.dumps({"progress": value}, ensure_ascii=False), flush=True))
    for mode, report in result["reports"].items():
        items = report["sections"][0]["items"]
        print(json.dumps({"mode": mode, "report_id": report["id"], "count": len(items), "titles": [item.get("title") or item.get("translation") or item.get("quote") for item in items], "usage": report["usage"], "coverage": report["coverage"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
