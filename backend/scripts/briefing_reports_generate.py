"""专项抽取真实文稿，生成五种共享播客报告；断点继续不会重做已完成片段。"""
import argparse
import json
import sys
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND / ".env")
sys.path.insert(0, str(BACKEND))

from app.services.briefing_report_service import BriefingReportService, VARIANTS


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--variant", choices=["all", *[item["id"] for item in VARIANTS]], default="all")
    parser.add_argument("--topic", default="")
    parser.add_argument("--extract-only", action="store_true")
    parser.add_argument("--web-enabled", action="store_true", help="补充已查阅的节目背景；应用内生成另支持已配置的实时搜索")
    args = parser.parse_args()
    service = BriefingReportService()
    progress = lambda value: print(json.dumps({"progress": value}, ensure_ascii=False), flush=True)
    if args.extract_only:
        service.extract(progress)
        return
    result = service.generate(variant=args.variant, topic=args.topic, web_enabled=args.web_enabled, progress_callback=progress)
    for report in result["reports"]:
        print(json.dumps({"variant": report["variant"], "report_id": report["id"], "title": report["title"], "cards": sum(len(section["items"]) for section in report["sections"]), "coverage": report["coverage"], "model": report["model"]}, ensure_ascii=False), flush=True)
    print(json.dumps({"extraction": result["extraction"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
