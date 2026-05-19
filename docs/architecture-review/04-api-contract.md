# 04 - API 契约文档

> 审查日期: 2026-05-17
> 源码版本: master @ 0ed20b6

## 1. 概述

后端共注册 **9 个蓝图**（Blueprint），base URL = `/api`。其中 `stats` 蓝图无独立前缀（直接挂在 `/api/stats`），其余各有独立前缀。

### 统一响应格式

大部分端点使用 `utils.py` 中的辅助函数返回统一格式：

```json
// 成功（success_response）
{ "success": true, "data": {...}, "message": "..." }

// 分页（paginated_response）
{ "success": true, "data": [...], "page": 1, "per_page": 20, "total": 100 }

// 失败（error_response）
{ "success": false, "message": "...", "code": "ERROR_CODE" }
```

**例外**: `settings` 和 `insights` 蓝图直接返回 `jsonify()` 结果，未使用统一响应格式。settings 响应形如 `{ "configs": [...], "active_index": 0 }`，insights 响应格式由 `BriefingService` 决定。

---

## 2. API 总表

### 2.1 feeds（`/api/feeds`）

源码: `backend/app/api/feeds.py` | 前端调用: `frontend/src/services/api.js` -> `feedsApi`

| 方法 | 路径 | 说明 | 关键参数 |
|------|------|------|----------|
| GET | /feeds | 分页列表 | `?status=&is_starred=&is_favorite=&page=&per_page=` |
| GET | /feeds/:id | 详情 | - |
| POST | /feeds | 创建订阅 | `{ rss_url, tags }` 含 RSS 解析和 Episode 批量插入 |
| PUT | /feeds/:id | 更新 | `{ tags, status, note }` 仅允许这三个字段 |
| DELETE | /feeds/:id | 删除 | 级联删除关联的 episodes、transcripts、summaries |
| POST | /feeds/:id/refresh | 异步刷新 | 返回 `{ task_id, status: "queued" }` |
| POST | /feeds/:id/star | 标星切换 | `{ starred: bool }` 不传则 toggle |
| POST | /feeds/:id/favorite | 收藏切换 | `{ favorite: bool }` 不传则 toggle |
| GET | /feeds/:id/episodes | 按源获取单集 | `?status=&is_read=&is_starred=&page=&per_page=` |

### 2.2 episodes（`/api/episodes`）

源码: `backend/app/api/episodes.py` | 前端调用: `episodesApi`

| 方法 | 路径 | 说明 | 关键参数 |
|------|------|------|----------|
| GET | /episodes | 全局分页列表 | `?status=,transcribed&feed_id=&is_read=&is_starred=&has_transcript=&has_summary=&page=&per_page=` |
| GET | /episodes/:id | 详情 | 附带 feed_title |
| PUT | /episodes/:id | 更新 | `{ is_read, is_starred, play_position }` 更新 is_read 时同步更新 feed 的 unread_count |
| POST | /episodes/:id/star | 标星 | `{ starred: bool }` |
| POST | /episodes/:id/read | 标记已读 | `{ is_read: bool }` 同步更新 feed unread_count |
| POST | /episodes/:id/download | 异步下载 | 返回 `{ task_id, status: "queued" }`，限制 500MB |

### 2.3 transcripts（`/api/transcripts`）

源码: `backend/app/api/transcripts.py` | 前端调用: `transcriptsApi`

| 方法 | 路径 | 说明 | 关键参数 |
|------|------|------|----------|
| GET | /transcripts/:episode_id | 获取转录 | - |
| POST | /transcripts/:episode_id | 创建转录（异步） | 优先尝试官方字幕 URL，否则调用 AssemblyAI |
| DELETE | /transcripts/:episode_id | 删除转录 | 状态回退到 downloaded |
| POST | /transcripts/:episode_id/fetch | 抓取外部字幕 | 从 episode.transcript_url 获取 |
| GET | /transcripts/:episode_id/check-external | 检查外部字幕可用性 | 返回 `{ has_external_transcript, transcript_url }` |

### 2.4 summaries（`/api/summaries`）

源码: `backend/app/api/summaries.py` | 前端调用: `summariesApi`

| 方法 | 路径 | 说明 | 关键参数 |
|------|------|------|----------|
| GET | /summaries/:episode_id | 获取摘要 | `?template_name=&summary_type=` 不传则返回最新一条 |
| POST | /summaries/:episode_id | 创建摘要（异步） | 见下方详细说明 |
| POST | /summaries/:episode_id/translate | 翻译 | `{ template_name, summary_type }` |
| DELETE | /summaries/:episode_id | 删除摘要 | `?template_name=&summary_type=` 不传则删除该 episode 全部摘要 |
| GET | /summaries/templates | 获取可用模板列表 | - |
| GET | /summaries/types | legacy 类型列表 | **已废弃**，应使用 /templates |

### 2.5 prompt-templates（`/api/prompt-templates`）

源码: `backend/app/api/prompt_templates.py` | 前端调用: `promptTemplatesApi`

| 方法 | 路径 | 说明 | 关键参数 |
|------|------|------|----------|
| GET | /prompt-templates/ | 列出活跃模板 | `?include_system=true` |
| GET | /prompt-templates/:id | 详情 | 支持 id 或 name 查找 |
| POST | /prompt-templates/ | 创建用户模板 | `{ name, display_name, description, optional_blocks, parameters, user_prompt_template }` |
| PUT | /prompt-templates/:id | 更新 | 系统模板不可修改（403） |
| POST | /prompt-templates/:id/duplicate | 复制 | `{ name, display_name }` 复制系统模板的唯一方式 |
| DELETE | /prompt-templates/:id | 删除 | 系统模板不可删除（403） |
| GET | /prompt-templates/:id/blocks | 获取可选 blocks | 返回 `{ template_name, blocks: [{id, name, name_zh, enabled_by_default, order}] }` |
| GET | /prompt-templates/:id/parameters | 获取参数定义 | - |
| POST | /prompt-templates/init | 初始化系统模板 | 幂等操作，已存在的会跳过 |

### 2.6 tasks（`/api/tasks`）

源码: `backend/app/api/tasks.py` | 前端调用: `tasksApi`

| 方法 | 路径 | 说明 | 关键参数 |
|------|------|------|----------|
| GET | /tasks | 任务列表 | `?status=&type=&episode_id=&feed_id=&page=&per_page=` |
| GET | /tasks/:id | 任务详情 | 优先从内存队列取，fallback 到数据库 |
| POST | /tasks/:id/cancel | 取消任务 | 仅 pending 状态可取消 |

### 2.7 settings（`/api/settings`）

源码: `backend/app/api/settings.py` | 前端调用: `settingsApi`

| 方法 | 路径 | 说明 | 关键参数 |
|------|------|------|----------|
| GET | /settings/llm | LLM 配置列表 | api_key 不返回完整值，用 has_api_key 标记 |
| PUT | /settings/llm | 保存 LLM 配置 | `{ configs: [...], active_index }` 最多 5 个，保留未变更的 api_key |
| PUT | /settings/llm/active | 设置激活索引 | `{ index }` |
| POST | /settings/llm/test | 测试连接 | `{ base_url, api_key, model }` 失败也返回 200 + success=false |
| GET | /settings/tavily | Tavily 配置 | api_keys 用占位符 |
| PUT | /settings/tavily | 保存 Tavily 配置 | `{ enabled, api_keys, search_depth, max_results, include_domains, exclude_domains, days_back }` |
| POST | /settings/tavily/test | 测试 Tavily | `{ api_key }` |
| GET | /settings/prompts/search-query | 搜索查询片段 | - |
| PUT | /settings/prompts/search-query | 保存搜索查询片段 | `{ fragment }` |

### 2.8 insights（`/api/insights`）

源码: `backend/app/api/insights.py` | 前端调用: `insightsApi`

| 方法 | 路径 | 说明 | 关键参数 |
|------|------|------|----------|
| GET | /insights/briefing | 获取今日简报 | 有缓存则返回缓存 |
| POST | /insights/briefing | 强制重新生成 | - |
| GET | /insights/briefing/export | 导出 PDF | 直接返回 `application/pdf` 二进制流 |

### 2.9 stats（`/api/stats`）

源码: `backend/app/api/stats.py` | 前端调用: `statsApi`

| 方法 | 路径 | 说明 | 关键参数 |
|------|------|------|----------|
| GET | /stats | 统计概览 | 返回 feeds/episodes/tasks 聚合数据 |

---

## 3. 摘要 API 深度分析

摘要是系统中最复杂的 API，涉及 v2（legacy `summary_type`）和 v3（`template_name`）两套体系并存。

### 3.1 请求参数

前端创建摘要的调用（`frontend/src/services/api.js` -> `summariesApi.create`）：

```js
// v3 模板模式
{ template_name: "learning", enabled_blocks: ["core_content", "key_points"], force: false }

// v2 legacy 模式
{ summary_type: "investment", force: false }

// 不传参数 → 默认使用 "learning" 模板
{}
```

后端 `summaries.create_summary` 的参数解析逻辑（`summaries.py` 第 101-126 行）：
1. 有 `template_name` → v3 模板模式
2. 有 `summary_type` → v2 legacy 模式
3. 都没有 → 默认 `"learning"` 模板（v3）

### 3.2 响应格式

后端返回通过 `Summary.to_response()`（`models/summary.py` 第 54-139 行）处理。

v3 模板生成的 `content` 是一个 dict，`to_response` 将其字段展开到顶层响应：

**固定字段**：
- `tldr` — 太长不看（字符串）
- `tags` — 标签列表

**按 summary_type 展开的字段**（v2 legacy）：
- `investment` 类型: investment_signals, mentioned_tickers, market_insights, key_quotes, risk_alerts, investment_thesis
- `general` 类型: key_points, why_it_matters

**v3 模板通用字段**（template_name 存在或 version="v3" 时触发）：
- 核心内容: core_content, guest_background, unique_insights, action_items, key_quotes
- 学习相关: key_points, key_concepts, examples, resources
- 投资相关: investment_signals, mentioned_tickers, market_insights, risk_alerts
- 技术相关: technologies, product_insights, tech_trends
- 创业相关: business_model, growth_tactics, lessons_learned
- 访谈相关: life_lessons, controversial_views

注意：v3 分支会无条件覆盖 v2 分支已设置的同名字段（如 key_points、investment_signals），因为 v3 分支总是在 v2 之后执行。

### 3.3 前端渲染

前端 `EpisodeDetailView.jsx`（约第 570-812 行）的摘要渲染区域，每个字段用独立的 `if` 条件判断：

```jsx
{summary.tldr && <div>...</div>}
{summary.investment_signals?.length > 0 && <div>...</div>}
{summary.mentioned_tickers?.length > 0 && <div>...</div>}
{summary.key_quotes?.length > 0 && <div>...</div>}
{summary.risk_alerts?.length > 0 && <div>...</div>}
{summary.key_points?.length > 0 && <div>...</div>}
{summary.core_content && <div>...</div>}
{summary.guest_background && <div>...</div>}
{summary.unique_insights?.length > 0 && <div>...</div>}
{summary.action_items?.length > 0 && <div>...</div>}
{summary.key_concepts?.length > 0 && <div>...</div>}
{summary.examples?.length > 0 && <div>...</div>}
{summary.resources?.length > 0 && <div>...</div>}
{summary.tags?.length > 0 && <div>...</div>}
```

每个字段有独立的样式和布局逻辑（编号列表、标签式、引用块、卡片式等），总计约 240 行 JSX。

### 3.4 新增 Block 的改动面

新增一个摘要 Block（如 "questions" 问答板块），需要同时修改：

| 步骤 | 文件 | 改动内容 |
|------|------|----------|
| 1 | `backend/app/core/summarization/defaults/templates.py` | 在 optional_blocks 中定义新 block |
| 2 | `backend/app/models/summary.py` -> `to_response` | 添加 `response["questions"] = content.get("questions", [])` |
| 3 | `frontend/src/components/views/EpisodeDetailView.jsx` | 添加 `{summary.questions?.length > 0 && <div>...</div>}` 渲染逻辑 |

**问题**：改 3 个地方才能完成 1 个 block 的添加，且没有编译期保障（漏改任何一处都不会报错，只是不显示）。

### 3.5 已知问题

1. **summary_type 和 template_name 混用**: v2 用 `summary_type`，v3 用 `template_name`。查询、创建、删除都同时支持两种参数，增加维护复杂度。
2. **content 字段不透明**: 前端必须知道每个 block 的输出字段名（如 `core_content`、`key_concepts`），这些字段名是在 `to_response` 中硬编码的，无法从 API 契约中推导。
3. **v2/v3 字段覆盖**: `to_response` 中 v3 分支无条件覆盖 v2 分支的同名字段（第 103-138 行），如果同时存在 `summary_type="investment"` 和 `template_name`，investment 类型特有的字段设置会被 v3 通用设置覆盖。

### 3.6 建议

**短期**（低风险，可立即做）：
- 保持现有字段展开方式不变
- 前端实现通用的 `SummaryBlockRenderer`，按数据类型（list/string/object）自动渲染，减少手动 if 分支
- 在 `to_response` 中添加注释标注每个字段来源的 block id

**长期**（需要前后端同步改动）：
- 改成 block-based response 格式：

```json
{
  "blocks": [
    { "id": "core_content", "type": "string", "title": "核心内容", "data": "..." },
    { "id": "key_points", "type": "list", "title": "关键要点", "data": [...] },
    { "id": "investment_signals", "type": "structured_list", "title": "投资信号", "data": [...] }
  ]
}
```

- 前端按 `block.type` 通用渲染，新增 block 只需后端定义，前端无需改动
- 逐步废弃 v2 `summary_type`，统一到 `template_name`

---

## 4. 响应格式不一致问题

| 蓝图 | 响应格式 | 备注 |
|------|----------|------|
| feeds, episodes, transcripts, summaries, tasks, stats | `{ success, data, message }` | 使用 `utils.py` 辅助函数 |
| settings | 直接 `jsonify()` | 无 success 字段，如 `{ configs: [...] }` |
| insights | 由 Service 层决定 | briefing 格式取决于 BriefingService |

建议统一为 `success_response` / `error_response` 格式，或在文档中明确标注每个端点的实际响应结构。

---

## 5. 错误码汇总

| 错误码 | HTTP 状态 | 说明 | 出现端点 |
|--------|-----------|------|----------|
| MISSING_RSS_URL | 400 | RSS URL 必填 | feeds.create |
| INVALID_RSS_URL | 400 | URL 格式无效 | feeds.create |
| FEED_EXISTS | 409 | 订阅已存在 | feeds.create |
| RSS_PARSE_ERROR | 400 | RSS 解析失败 | feeds.create |
| FEED_NOT_FOUND | 404 | 订阅不存在 | feeds |
| EPISODE_NOT_FOUND | 404 | 单集不存在 | episodes, transcripts, summaries |
| TRANSCRIPT_NOT_FOUND | 404 | 转录不存在 | transcripts, summaries |
| SUMMARY_NOT_FOUND | 404 | 摘要不存在 | summaries |
| SUMMARY_EXISTS | 409 | 摘要已存在 | summaries.create |
| TASK_IN_PROGRESS | 409 | 任务进行中 | transcripts.create, summaries.create, episodes.download |
| ALREADY_TRANSCRIBING | 400 | 已在转录中 | transcripts.create |
| ALREADY_TRANSCRIBED | 400 | 已有转录 | transcripts.create |
| ALREADY_DOWNLOADED | 400 | 已下载 | episodes.download |
| ALREADY_DOWNLOADING | 400 | 下载中 | episodes.download |
| TEMPLATE_NOT_FOUND | 404 | 模板不存在 | prompt-templates |
| SYSTEM_TEMPLATE_PROTECTED | 403 | 系统模板受保护 | prompt-templates.update, delete |
| TASK_NOT_FOUND | 404 | 任务不存在 | tasks |
| CANNOT_CANCEL | 400 | 无法取消 | tasks.cancel |
