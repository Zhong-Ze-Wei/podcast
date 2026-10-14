"""共享全文分析的复用、完整性、恢复与真实证据边界。所有模型调用均mock。"""
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from datetime import datetime
import json
from threading import Event
from types import SimpleNamespace

import pytest

from app.services import episode_analysis_service as module
from app.services.briefing_modes_service import BriefingModesService, validate_mode
from app.services.briefing_reading_service import BriefingReadingService
from app.services.episode_analysis_service import EpisodeAnalysisService, validate_episode_analysis
from tests.test_briefing_scope import TEXT, add_episode, scope_service


def analysis_result(quote=TEXT):
    return {"takeaway": "评估模型不能脱离真实使用情境。", "points": [
        {"title": "评估与情境", "meaning": "用实际任务判断推理能力。", "boundary": "取决于使用情境。", "quote": quote,
         "translation": "", "brief": "讨论模型评估。", "speaker": "虚构嘉宾"}],
        "quotes": [{"quote": quote, "translation": "", "brief": "讨论模型评估。"}], "concepts": [], "resources": []}


def setup_service(tmp_path):
    scope = scope_service(tmp_path)
    add_episode(scope.db, datetime(2026, 9, 29), "OpenAI经营", TEXT)
    scope.report_service.lab.client_factory = lambda **kwargs: SimpleNamespace(model="mock-model", base_url="https://test.invalid", api_format="openai_compatible")
    corpus = scope.collect("month", "2026-09-01")["corpus"]
    scope.report_service._corpus = corpus
    return scope, corpus["sources"][0], EpisodeAnalysisService(scope.report_service)


def mock_analysis(monkeypatch, scope, result=None):
    calls = []
    def model(system, prompt, validator, **kwargs):
        calls.append((system, prompt, kwargs))
        return validator(deepcopy(result or analysis_result())), {"model": "mock-model", "usage": {"prompt": 20, "completion": 10, "total": 30}}
    monkeypatch.setattr(scope.report_service.lab, "_model_call", model)
    return calls


def test_cache_identity_tracks_flash_reading_effort(tmp_path):
    scope, source, service = setup_service(tmp_path)
    scope.report_service.lab.client_factory = lambda **kwargs: SimpleNamespace(
        model="DeepSeek-V4.1-Flash", base_url="https://test.invalid", api_format="openai_compatible")
    assert service.identity(source)["configuration"]["reasoning_effort"] == "low"


def test_single_week_month_share_one_record_and_read_is_free(tmp_path, monkeypatch):
    scope, source, service = setup_service(tmp_path)
    calls = mock_analysis(monkeypatch, scope)
    reading = BriefingReadingService(report_service=scope.report_service)
    assert reading.reading(source["id"])["reading"] is None
    first = reading.generate_reading(source["id"])["reading"]
    assert len(calls) == 1
    for period in ("week", "month"):
        collected = scope.collect(period, "2026-09-29", ["AI产业经营"])
        scope.report_service._corpus = collected["corpus"]
        modes = BriefingModesService(report_service=scope.report_service, scope_service=scope)
        _, _, payload = modes._episode_material()
        assert payload["analysis"]["reused_episodes"] == 1
        assert payload["single_readings"][0]["takeaway"] == first["takeaway"]
    assert reading.reading(source["id"])["reading"]["id"] == first["id"]
    assert len(calls) == 1


def test_text_prompt_version_and_model_invalidate_cache(tmp_path, monkeypatch):
    scope, source, service = setup_service(tmp_path)
    calls = mock_analysis(monkeypatch, scope)
    first, _ = service.analyze(source)
    assert service.cached({**source, "full_text": source["full_text"] + "尾部新增。"}) is None
    monkeypatch.setattr(module, "ANALYSIS_VERSION", module.ANALYSIS_VERSION + 1)
    assert service.cached(source) is None
    second, _ = service.analyze(source)
    assert first["id"] != second["id"]
    scope.report_service.lab.client_factory = lambda **kwargs: SimpleNamespace(model="changed", base_url="https://test.invalid", api_format="openai_compatible")
    assert service.cached(source) is None
    assert len(calls) == 2


def test_parallel_single_and_period_requests_call_model_once(tmp_path, monkeypatch):
    scope, source, service = setup_service(tmp_path)
    entered, release = Event(), Event()
    calls = []
    def model(system, prompt, validator, **kwargs):
        calls.append(prompt)
        entered.set()
        assert release.wait(3)
        return validator(analysis_result()), {"model": "mock-model", "usage": {"total": 30}}
    monkeypatch.setattr(scope.report_service.lab, "_model_call", model)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(service.analyze, source)
        assert entered.wait(3)
        second = pool.submit(EpisodeAnalysisService(scope.report_service).analyze, source)
        release.set()
        a, b = first.result(), second.result()
    assert a[0]["id"] == b[0]["id"] and {a[1], b[1]} == {True, False}
    assert len(calls) == 1


def test_failed_episode_does_not_discard_success_and_retry_only_fills_gap(tmp_path, monkeypatch):
    scope, source, service = setup_service(tmp_path)
    other_text = "第二期讨论采用工具前应测量真实工作流程的效果。"
    add_episode(scope.db, datetime(2026, 9, 30), "算力设备", other_text)
    scope.report_service._corpus = scope.collect("month", "2026-09-01")["corpus"]
    calls = []
    def model(system, prompt, validator, **kwargs):
        calls.append(prompt)
        if other_text in prompt:
            raise ValueError("临时服务错误")
        return validator(analysis_result()), {"model": "mock-model", "usage": {}}
    monkeypatch.setattr(scope.report_service.lab, "_model_call", model)
    modes = BriefingModesService(report_service=scope.report_service, scope_service=scope)
    corpus, _, payload = modes._episode_material()
    assert len(corpus["sources"]) == 1 and payload["analysis"]["partial"] is True
    assert payload["analysis"]["failed_episodes"][0]["error"] == "临时服务错误"
    retry_calls = mock_analysis(monkeypatch, scope, analysis_result(other_text))
    corpus, _, payload = modes._episode_material()
    assert len(corpus["sources"]) == 2 and not payload["analysis"]["partial"]
    assert payload["analysis"]["reused_episodes"] == 1
    assert len(calls) == 2 and len(retry_calls) == 1


def test_entire_150k_text_sent_once_and_text_evidence_needs_no_audio(tmp_path, monkeypatch):
    scope, source, service = setup_service(tmp_path)
    source["full_text"] = "开头。" + "背景材料。" * 25000 + TEXT + "结尾不会被截掉。"
    source["segments"] = []
    calls = mock_analysis(monkeypatch, scope)
    reading, reused = service.analyze(source)
    assert not reused and len(calls) == 1
    paragraphs = module.source_paragraphs(source["full_text"])
    assert "".join(item["text"] for item in paragraphs) == source["full_text"]
    assert all(f"[{item['id']}] {item['text']}" in calls[0][1] for item in paragraphs)
    assert "结尾不会被截掉。" in calls[0][1]
    assert reading["points"][0]["quote"]["start"] is None
    cards = service.cards(reading)
    result = validate_mode({"items": [{"title": "评估要结合情境", "text": "节目强调真实使用条件。", "evidence_ids": [cards[0]["id"]]}]}, "core", cards, {"sources": [source]})
    assert result["items"][0]["evidence"][0]["offset"] > 100000


def test_over_budget_is_explicit_and_never_silently_truncated(tmp_path, monkeypatch):
    scope, source, service = setup_service(tmp_path)
    calls = mock_analysis(monkeypatch, scope)
    monkeypatch.setenv("EPISODE_ANALYSIS_MAX_INPUT_CHARS", "10")
    with pytest.raises(ValueError, match="未截断、未调用模型"):
        service.analyze(source)
    assert calls == [] and service.cached(source) is None


def test_resource_and_method_identity_survive_cache_rebinding(tmp_path, monkeypatch):
    scope, source, service = setup_service(tmp_path)
    source["full_text"] += "节目提到真实工作评估指南，使用它构建任务。"
    data = analysis_result()
    data["concepts"] = [{"title": "方法：真实任务评估", "original_term": "", "text": "将模型放进实际情境。", "quote": TEXT}]
    data["resources"] = [{"title": "真实工作评估指南", "original_title": "真实工作评估指南", "text": "用来构建任务。", "quote": "节目提到真实工作评估指南，使用它构建任务。", "resource_kind": "article", "relation": "mentioned", "url": "https://invented.invalid"}]
    mock_analysis(monkeypatch, scope, data)
    service.analyze(source)
    rebound = service.cached({**source, "id": "ep" + "b" * 24, "episode_id": "b" * 24})
    assert rebound["resources"][0]["title"] == "真实工作评估指南"
    assert rebound["resources"][0]["text"] == "用来构建任务。"
    assert rebound["resources"][0]["url"] == ""
    assert rebound["concepts"][0]["original_term"] == ""
    assert rebound["points"][0]["quote"]["speaker"] == ""


def test_invented_quotes_and_named_concepts_are_rejected(tmp_path):
    scope, source, service = setup_service(tmp_path)
    data = analysis_result("完全不存在于这期节目中的一段原话。")
    with pytest.raises(ValueError, match="不在对应正文"):
        validate_episode_analysis(data, source)
    data = analysis_result()
    data["concepts"] = [{"title": "不存在术语", "original_term": "不存在术语", "text": "编造的说明。", "quote": TEXT}]
    with pytest.raises(ValueError, match="原名必须出现在文稿"):
        validate_episode_analysis(data, source)


def test_selection_key_changes_with_analysis_policy_not_api_secret(tmp_path, monkeypatch):
    scope, source, service = setup_service(tmp_path)
    first = scope.collect("month", "2026-09-01")["selection_key"]
    monkeypatch.setattr(module, "ANALYSIS_VERSION", module.ANALYSIS_VERSION + 1)
    assert scope.collect("month", "2026-09-01")["selection_key"] != first


def test_interest_questions_accept_200_characters(tmp_path):
    scope = scope_service(tmp_path)
    label = "我关心人工智能应用落地时的组织与经营问题。" * 7
    assert len(label) > 30
    assert scope.save_preferences([{"label": label, "enabled": True}])["interests"][0]["label"] == label


def test_only_included_episode_without_text_yields_empty_report_not_failed_analysis(tmp_path, monkeypatch):
    scope, source, service = setup_service(tmp_path)
    missing, _ = add_episode(scope.db, datetime(2026, 9, 30), "AI算力设备", None)
    def model(system, prompt, validator, **kwargs):
        assert "节目标题与已有简介" in prompt
        items = json.loads(prompt.split("节目标题与已有简介：\n")[1])
        return validator({"decisions": [{"id": item["id"], "decision": "include" if item["id"] == str(missing["_id"]) else "exclude",
                                        "topics": [], "reason": "依据标题判断范围。"} for item in items]}), {"usage": {}}
    monkeypatch.setattr(scope.report_service.lab, "_model_call", model)
    modes = BriefingModesService(report_service=scope.report_service, scope_service=scope)
    generated = modes.generate(scope=scope.collect("month", "2026-09-01"))
    assert all(report["coverage"]["sources"] == 0 for report in generated["reports"].values())
    assert not service.root.exists()


def test_period_generation_uses_compact_analysis_and_second_period_never_reads_full_text_again(tmp_path, monkeypatch):
    scope, source, service = setup_service(tmp_path)
    calls = []
    def model(system, prompt, validator, **kwargs):
        calls.append((system, prompt))
        if "节目标题与已有简介" in prompt:
            items = json.loads(prompt.split("节目标题与已有简介：\n")[1])
            value = {"decisions": [{"id": item["id"], "decision": "include", "topics": ["AI"], "reason": "AI企业的经营也属于关注范围。"} for item in items]}
        elif "以下为完整文稿" in prompt:
            value = analysis_result()
        else:
            assert "single_readings" in prompt and "topics" in prompt and "boundary" in prompt
            assert "以下为完整文稿" not in prompt
            value = {mode: [] for mode in ("core", "quotes", "connections", "concepts", "resources")}
        return validator(value), {"model": "mock-model", "usage": {"total": 1}}
    monkeypatch.setattr(scope.report_service.lab, "_model_call", model)
    modes = BriefingModesService(report_service=scope.report_service, scope_service=scope)
    for period in ("week", "month"):
        generated = modes.generate(scope=scope.collect(period, "2026-09-29", ["AI"]))
        assert set(generated["reports"]) == {"core", "quotes", "connections", "concepts", "resources"}
    assert sum("以下为完整文稿" in prompt for _, prompt in calls) == 1
    assert sum("节目标题与已有简介" in prompt for _, prompt in calls) == 1
    assert len(calls) == 4  # 初筛一次、单篇一次、周报/月报各一次汇总。
    assert sum(report["usage"]["total"] for report in generated["reports"].values()) == 1
    assert all(report["analysis"]["reused_episodes"] == 1 for report in generated["reports"].values())


def test_previews_do_not_initialize_settings_or_call_model(tmp_path, monkeypatch):
    scope = scope_service(tmp_path)
    add_episode(scope.db, datetime(2026, 9, 29), "AI企业", TEXT)
    monkeypatch.setattr(scope.report_service.lab, "_model_call", lambda *args, **kwargs: pytest.fail("Preview must not generate"))
    before = deepcopy(scope.db.settings._data)
    scope.collect("month", "2026-09-01")
    assert scope.db.settings._data == before


def test_quote_cannot_merge_host_and_guest_into_one_speaker(tmp_path):
    scope, source, service = setup_service(tmp_path)
    question = "为什么评估人工智能时不能只看排行榜？"
    source["full_text"] = question + " " + TEXT
    source["segments"] = [{"text": question, "speaker": "主持人", "start": 0, "end": 5}, {"text": TEXT, "speaker": "嘉宾", "start": 6, "end": 20}]
    data = analysis_result()
    data["quotes"][0]["quote"] = source["full_text"]
    with pytest.raises(ValueError, match="不同说话人"):
        validate_episode_analysis(data, source)


def test_same_full_text_cannot_be_used_as_two_independent_comparison_sources(tmp_path):
    scope, source, service = setup_service(tmp_path)
    other = {**source, "id": "ep" + "b" * 24, "episode_id": "b" * 24}
    a = validate_episode_analysis(analysis_result(), source)["points"][0]["quote"]
    b = validate_episode_analysis(analysis_result(), other)["points"][0]["quote"]
    with pytest.raises(ValueError, match="重复订阅"):
        validate_mode({"items": [{"title": "伪共同点", "text": "不能把同一内容当作交叉印证。", "evidence_ids": [a["id"], b["id"]], "relation": "commonality"}]},
                      "connections", [a, b], {"sources": [source, other]})


def test_default_route_sentinel_uses_actual_default_model_not_a_model_named_default(tmp_path):
    from app.models.setting import SettingModel
    scope = scope_service(tmp_path)
    settings = SettingModel(scope.db)
    settings.set(settings.KEY_LLM_PROVIDERS, [{"id": "provider", "base_url": "https://test.invalid", "enabled": True}])
    settings.set(settings.KEY_LLM_MODELS, [{"id": model_id, "model": model_id.upper(), "provider_id": "provider"} for model_id in ("default", "chosen", "changed")])
    settings.set(settings.KEY_LLM_DEFAULT_MODEL, "chosen")
    settings.set(settings.KEY_LLM_TASK_ROUTES, {"summary": "default"})
    analysis = EpisodeAnalysisService(scope.report_service)
    assert analysis.configuration()["model"] == "CHOSEN"
    settings.set(settings.KEY_LLM_DEFAULT_MODEL, "changed")
    assert analysis.configuration()["model"] == "CHANGED"


def test_later_speaker_metadata_excludes_invalid_quote_without_blocking_saved_analysis(tmp_path, monkeypatch):
    scope, source, service = setup_service(tmp_path)
    question = "为什么评估人工智能时不能只看排行榜？"
    source["full_text"] = question + " " + TEXT
    source["segments"] = []
    data = analysis_result()
    data["quotes"][0]["quote"] = source["full_text"]
    calls = mock_analysis(monkeypatch, scope, data)
    original, _ = service.analyze(source)
    source["segments"] = [{"text": question, "speaker": "主持人", "start": 0, "end": 5}, {"text": TEXT, "speaker": "嘉宾", "start": 6, "end": 20}]
    cached = service.cached(source)
    assert cached["id"] == original["id"] and cached["points"]
    assert cached["quotes"] == [] and cached["excluded_quote_count"] == 1
    returned, reused = service.analyze(source)
    assert reused and returned["excluded_quote_count"] == 1
    assert len(calls) == 1


def test_paragraph_references_keep_all_evidence_and_rebind_to_duplicate_subscription(tmp_path, monkeypatch):
    scope, source, service = setup_service(tmp_path)
    source["full_text"] = ("训练要根据实际任务判断模型效果。" * 45) + "另一个议题是部署成本与能源效率。" * 45
    source["segments"] = []
    data = analysis_result()
    data["points"] = [{"title": "真实任务与成本", "meaning": "既要测量任务效果，也要关注部署成本。", "refs": ["P001", "P002"]}]
    data["quotes"] = []
    calls = mock_analysis(monkeypatch, scope, data)
    reading, _ = service.analyze(source)
    evidence = reading["points"][0]["quote"]
    assert evidence["evidence_type"] == "paragraph"
    assert evidence["supporting_references"][0]["ref"] == "P002"
    for ref in [evidence, *evidence["supporting_references"]]:
        assert source["full_text"][ref["offset"]:ref["offset"] + len(ref["quote"])] == ref["quote"]
    other = {**source, "id": "ep" + "b" * 24, "episode_id": "b" * 24}
    rebound = service.cached(other)
    assert rebound["points"][0]["quote"]["id"] != evidence["id"]
    assert rebound["points"][0]["quote"]["supporting_references"][0]["source_id"] == other["id"]
    assert len(calls) == 1


def test_bad_item_does_not_retry_whole_episode_or_discard_good_topics(tmp_path, monkeypatch):
    scope, source, service = setup_service(tmp_path)
    data = analysis_result()
    data["points"].append({"title": "不存在依据", "meaning": "不应保留", "refs": ["P999"]})
    calls = mock_analysis(monkeypatch, scope, data)
    reading, _ = service.analyze(source)
    assert len(reading["points"]) == 1
    assert len(reading["rejected_items"]) == 1
    assert calls[0][2]["max_attempts"] == 1
    assert service.cached(source)["rejected_items"] == reading["rejected_items"]


def test_unique_comma_difference_uses_actual_original_and_never_guesses_words(tmp_path):
    _, source, _ = setup_service(tmp_path)
    source["full_text"] = "Uh except our layers are so big they cannot fit inside a GPU."
    source["segments"] = []
    value = {"quote": source["full_text"].replace("Uh except", "Uh, except"), "translation": "层太大，无法放入单个GPU。"}
    evidence = module._quote(value, source, "claim")
    assert evidence["quote"] == source["full_text"] and evidence["quote_repaired"]
    with pytest.raises(ValueError):
        module._quote({**value, "quote": value["quote"].replace("big", "small")}, source, "claim")
    with pytest.raises(ValueError):
        module._quote(value, {**source, "full_text": source["full_text"] * 2}, "claim")
    with pytest.raises(ValueError):
        module._recover_comma_difference("The total was 1,000 credits.", "The total was 1000 credits.")


def test_long_episode_can_have_more_than_twelve_topics(tmp_path):
    _, source, _ = setup_service(tmp_path)
    data = analysis_result()
    data["points"] = [{"title": f"议题{index}", "meaning": "具体理由。" * 60, "refs": ["P001"]} for index in range(16)]
    result = validate_episode_analysis(data, source)
    assert len(result["points"]) == 16
