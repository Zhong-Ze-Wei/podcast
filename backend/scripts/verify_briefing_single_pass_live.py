"""Run the actual production services against frozen samples, writing only experiment files."""
import argparse
import json
import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))
OUT = ROOT / "docs/ai/data/experiments/2026-10-03-single-pass/production"
IDS = ("ep6abbd73b347d7753e4916e7f", "ep6abbd6d4347d7753e4916e6d")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("phase", choices=("short", "long", "bundle", "bundle-fast", "cache-probe", "cache-probe-2"))
    phase = parser.parse_args().phase
    from dotenv import load_dotenv
    from flask import Flask
    from pymongo import MongoClient
    from app.config import Config
    from app.services.ai_control import is_ai_analysis_enabled
    from app.services.llm_client import get_llm_client, reading_request_options, EmptyLLMResponse
    from app.services.briefing_report_service import BriefingReportService
    from app.services.episode_analysis_service import EpisodeAnalysisService
    from app.services.briefing_modes_service import BriefingModesService
    from app.services.briefing_lab_service import read_json, write_json

    load_dotenv(ROOT / "backend/.env")
    with MongoClient(os.getenv("MONGO_URI", "mongodb://localhost:27017"), serverSelectionTimeoutMS=3000) as mongo:
        app = Flask(__name__)
        app.config.from_object(Config)
        app.db = mongo[os.getenv("MONGO_DB", "podcast")]
        with app.app_context():
            assert is_ai_analysis_enabled(), "AI disabled"
            clients = {task: get_llm_client(task=task) for task in ("summary", "briefing")}
            for client in clients.values():
                assert client.model == "DeepSeek-V4.1-Flash", "Do not substitute models"
                client.client = client.client.with_options(timeout=240, max_retries=0)

    # Construct outside Flask so neither report publication nor settings touch MongoDB.
    sources = [json.loads(line) for line in (ROOT / "docs/ai/data/2026-09/sources.jsonl").read_text(encoding="utf-8").splitlines()]
    selected = [next(source for source in sources if source["id"] == identifier) for identifier in IDS]
    report = BriefingReportService(runtime_dir=OUT, lab_runtime_dir=OUT / "lab",
        client_factory=lambda task: clients[task], corpus={"sources": selected}, owner_id="single-pass-experiment")
    assert report.store.db is None
    analysis = EpisodeAnalysisService(report)
    if phase in ("short", "long"):
        source = selected[phase == "long"]
        reading, reused = analysis.analyze(source)
        write_json(OUT / f"{phase}.json", reading)
        print(json.dumps({"phase": phase, "reused": reused, "usage": reading["usage"], "elapsed_seconds": reading["elapsed_seconds"],
                          "counts": {key: len(reading[key]) for key in ("points", "quotes", "concepts", "resources", "rejected_items")}}, ensure_ascii=False))
    elif phase == "bundle":
        assert all(analysis.exists(source) for source in selected), "Run both single analyses first"
        path = OUT / "bundle.json"
        result = read_json(path) if path.exists() else BriefingModesService(report_service=report, owner_id="single-pass-experiment").generate()
        write_json(path, result)
        print(json.dumps({mode: {"count": len(item["sections"][0]["items"]), "usage": item["usage"], "analysis": item["analysis"]}
                          for mode, item in result["reports"].items()}, ensure_ascii=False))
    elif phase == "bundle-fast":
        from app.services.briefing_modes_service import validate_compact_modes, MODE_INDEX
        bundle = read_json(OUT / "bundle.json")
        saved = bundle["reports"]["core"]
        attempt = read_json(OUT / "content-modes-v1" / saved["analysis"]["mode_audit_record"])
        path = OUT / "bundle-fast.json"
        if path.exists():
            response = read_json(path)
        else:
            response = clients["briefing"].client.chat.completions.create(model=clients["briefing"].model,
                messages=attempt["messages"], max_tokens=4096, temperature=.2, response_format={"type": "json_object"},
                extra_body={"enable_thinking": False}).model_dump(mode="json")
            write_json(path, response)
        cards = [card for source in selected for card in analysis.cards(analysis.cached(source))]
        validated = validate_compact_modes(json.loads(response["choices"][0]["message"]["content"]), list(MODE_INDEX), cards, {"sources": selected})
        write_json(OUT / "bundle-fast-validated.json", validated)
        print(json.dumps({"usage": response["usage"], "finish_reason": response["choices"][0]["finish_reason"],
                          "counts": {key: len(validated[key]["items"]) for key in MODE_INDEX},
                          "rejected": {key: len(validated[key].get("rejected_items", [])) for key in MODE_INDEX}}, ensure_ascii=False))
    else:
        bundle = read_json(OUT / "bundle.json")
        saved = bundle["reports"]["core"]
        attempt = read_json(OUT / "content-modes-v1" / saved["analysis"]["mode_audit_record"])
        task = ('只返回输入材料的节目数量，格式 {"count":数字}。' if phase == "cache-probe" else
                '只返回输入材料中是否有单篇解读，格式 {"has_readings":true或false}。')
        messages = attempt["messages"][:2] + [{"role": "user", "content": task}]
        path = OUT / f"{phase}.json"
        if path.exists():
            result = read_json(path)
        else:
            try:
                result = clients["briefing"].chat(messages, json_mode=True, max_tokens=1024, temperature=.2,
                                                 **reading_request_options(clients["briefing"].model))
            except EmptyLLMResponse as error:
                # 缓存探测仍保留用量；不为获取一个数字重复付费。
                result = error.response
        result["prefix_messages"] = messages[:2]
        write_json(path, result)
        print(json.dumps({key: result[key] for key in ("usage", "elapsed_seconds", "finish_reason", "content")}, ensure_ascii=False))


if __name__ == "__main__":
    main()
