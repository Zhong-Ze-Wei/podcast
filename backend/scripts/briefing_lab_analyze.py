"""使用项目当前配置的LLM跑真实材料实验；缓存逐段分析，支持断点重跑。"""
import argparse
import json
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from dotenv import load_dotenv

BACKEND = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND / ".env")
sys.path.insert(0, str(BACKEND))

from app.services.briefing_lab_service import BriefingLabService, STRATEGIES


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--notes-only", action="store_true")
    parser.add_argument("--strategy", choices=[s["id"] for s in STRATEGIES])
    parser.add_argument("--focus", default="Agent开发与产品落地")
    args = parser.parse_args()
    service = BriefingLabService()
    service.analyze_sources(lambda progress: print(json.dumps({"progress": progress}, ensure_ascii=False), flush=True))
    if args.notes_only:
        return
    strategies = [args.strategy] if args.strategy else [s["id"] for s in STRATEGIES]
    with ThreadPoolExecutor(max_workers=2) as pool:
        jobs = {pool.submit(service.generate, strategy, args.focus, strategy == "research"): strategy for strategy in strategies}
        for future in as_completed(jobs):
            run = future.result()
            print(json.dumps({"strategy": jobs[future], "run_id": run["id"], "title": run["result"]["title"], "model": run["model"], "usage": run["usage"]}, ensure_ascii=False), flush=True)


if __name__ == "__main__":
    main()
