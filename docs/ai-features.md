# AI 功能

> 从 `services/llm_client.py`、`core/summarization/`、`services/briefing_service.py` 源码提取。

---

## LLM 客户端

**文件**: `services/llm_client.py` (309 行)

统一入口，支持双协议：

| 协议 | 实现 | SDK |
|------|------|-----|
| `openai_compatible` | `openai.OpenAI` SDK | openai 包 |
| `anthropic_messages` | `requests.post` HTTP | requests 包 |

### 核心方法

```python
chat(messages, model, max_tokens, temperature, json_mode) → dict
chat_json(messages, model, max_tokens, temperature) → dict  # 自动解析 JSON，清理 markdown 代码块
```

### 配置获取链 (`get_llm_client()`)

```
1. Flask 上下文 → get_db() → SettingModel.get_active_llm_config()
2. Flask 不可用 → 直连 MongoDB
3. 数据库无配置 → 环境变量 (LLM_BASE_URL, LLM_API_KEY, LLM_MODEL)
```

---

## LLM 配置系统

**文件**: `models/setting.py` (449 行)

三层分离：

```
llm_providers  → 服务商 [{ id, name, api_format, base_url, api_key, enabled }]
llm_models     → 模型   [{ id, provider_id, model, enabled, supports_streaming }]
llm_task_routes → 路由  { summary: model_id, briefing: model_id, transcript_normalize: model_id }
```

- **API Key 安全**: 读取返回空 + `has_api_key` 标记；写入时空值不覆盖已有密钥
- **旧格式兼容**: `_legacy_configs_to_split()` 自动迁移
- **默认配置**: ModelScope + DeepSeek V4 Flash

---

## 摘要引擎

**文件**: `core/summarization/engine.py` (386 行)

```
summarize_episode(episode_id, template_name, enabled_blocks)
  ├─ 加载 episode + transcript
  ├─ 加载模板 → PromptBuilder.build() 构建提示词
  ├─ _call_with_retry() — 最多 3 次
  │   ├─ llm.chat_json() — 调用 LLM
  │   └─ SchemaValidator.validate() — 校验输出
  │       ├─ 通过 → 返回
  │       └─ 失败 → 附加修正提示，重试
  │           └─ 最终兜底 → ensure_required_fields()
  ├─ 保存到 summaries 集合
  └─ 更新 episode.has_summary = True
```

### 模板系统

- 存储在 `prompt_templates` 集合
- 每个模板: system_prompt + required_blocks + optional_blocks + parameters
- 支持参数化: `{length}`, `{guest}` 等

---

## AI 简报

**文件**: `services/briefing_service.py` (266 行) + `services/briefing_prompts.py` (140 行)

### 数据收集策略

```
_collect_recent_episodes(days=7)
  ├─ 优先取 has_summary=True 的 episodes (AI 摘要质量高)
  │   └─ 足够 5 条 → 直接使用
  │   └─ 不足 → 补充未摘要的 episodes
  └─ 批量获取 summaries，拼接 summary_content
```

### 简报输出结构

```json
{
  "summary": { "totalEpisodes", "totalDuration", "keyInsights", "newConcepts" },
  "hotTopics": [{ "title", "mentions", "sentiment", "keyQuotes", "relatedEpisodes" }],
  "newConcepts": [{ "concept", "explanation", "complexity" }],
  "trends": { "topics": [{ "name", "change", "trend" }] },
  "recommended": [{ "id", "title", "reason" }],
  "markdownReport": "# 🎙️ 播客今日洞察 ..."
}
```

### 缓存

- 按天缓存到 `briefings` 集合，键为 UTC `YYYY-MM-DD`
- `force=True` 强制重新生成

### 已知限制

| 限制 | 影响 |
|------|------|
| 时间范围硬编码 7 天 | 不支持自定义 |
| 无 owner_id 过滤 | 多用户场景数据混杂 |
| 单次 LLM 调用 | 无多步编排 |

---

## AI 冻结机制

**文件**: `services/ai_control.py` (12 行)

```python
AI_ANALYSIS_ENABLED = False 时:
  - 摘要生成 → 423
  - 简报重新生成 → 423
  - 简报读取 → 返回最近缓存
```

---

## 测试覆盖

| 模块 | 测试文件 | 用例数 |
|------|---------|--------|
| LLM 客户端 | `test_llm_client.py` | 2 |
| LLM 配置 | `test_settings_api.py` | 7 |
| AI 冻结 | `test_ai_freeze.py` | 5 |
| 摘要引擎 | — | 0 |
| 简报服务 | — | 0 |
