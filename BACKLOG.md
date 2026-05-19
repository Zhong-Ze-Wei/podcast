# 想去修改的内容 — 评估与规划

> 基于代码阅读 + 行业调研，2026-05-16

---

## Q1：官方字幕获取策略 & 其他可获取的内容维度

### 当前实现现状

**字幕抓取逻辑分布在两个地方：**
- `rss_service.py:_extract_transcript_url()` — RSS 解析阶段提取 transcript_url，有 Lex Fridman 专属推断逻辑
- `transcript_fetcher.py:TranscriptFetcher` — 实际抓取，支持 SRT / VTT / JSON 三种格式
- **URL 必须以 `.srt` / `.vtt` / `.json` 结尾才能识别**，否则直接拒绝（硬匹配后缀名，很脆弱）

### 更好的字幕获取策略（建议）

| 策略 | 成本 | 质量 | 适用场景 | 如何实现 |
|------|------|------|----------|----------|
| Podcasting 2.0 `podcast:transcript` 标签 | 免费 | 高（官方） | 已支持 Podcasting 2.0 的播客 | 已实现，可扩展格式支持 |
| HTML 页面字幕推断（多站点模式） | 免费 | 高 | Lex Fridman / Huberman / Bankless 等 | 在 `_extract_transcript_url` 里扩充站点规则 |
| Content-Type 嗅探替代后缀名匹配 | 免费 | — | 所有 URL | 改 `TranscriptFetcher` 的判断逻辑 |
| YouTube 字幕提取（yt-dlp） | 免费 | 中 | 有 YouTube 版的播客 | `yt-dlp --write-sub --skip-download <url>` |
| AssemblyAI 云端转录 | $0.37/hr | 最高 | 无任何字幕来源时 | 已实现 |
| faster-whisper 本地转录 | 电费 | 高 | 隐私敏感/大批量 | 用 faster-whisper 替代 AssemblyAI，config.WHISPER_MODEL 已预留 |

**优先推荐：**
1. 修复 `TranscriptFetcher` 的格式判断（改用 Content-Type + 内容嗅探，而非后缀名）
2. 扩充站点推断规则（Huberman Lab、Tim Ferriss、My First Million 等有规律的站点）

### 除字幕外，还可以获取的内容维度

| 维度 | RSS 字段 | 当前状态 | 价值 |
|------|----------|----------|------|
| 章节信息 | `podcast:chapters` JSON URL | 字段已存（`chapters_url`），**未在 UI 显示** | 导航/时间戳 |
| Show Notes 书目/链接 | `content` HTML 解析 | 存了原始内容，只是纯文本展示 | 书单/工具推荐 |
| 嘉宾信息 | 标题解析（`-` / `|` 分割） | 极简，只从标题猜 | 嘉宾背景预填 |
| 说话人分离段落 | AssemblyAI `segments` | 已存数据库，前端也渲染了 | 区分主播/嘉宾发言 |

**最值得做的：章节数据已经在 `episodes.chapters_url` 里，只差前端展示和使用。**

---

## Q2 + Q3：转录策略的代码实现和维护路径

### 代码入口总览

```
POST /api/transcripts/<episode_id>
  → backend/app/api/transcripts.py               ← 路由层
     → backend/app/services/transcript_fetcher.py  ← 策略1：官方字幕
     → backend/app/services/whisper_service.py     ← 策略2：AssemblyAI
  → TaskQueue.submit("transcribe", ...)            ← 异步执行
```

### 两条策略的代码位置

**策略 1：官方字幕（免费、快速）**
- URL 来源：RSS 解析时写入 `episodes.transcript_url`，逻辑在 `rss_service.py:_extract_transcript_url()`
- 检测：`GET /api/transcripts/<id>/check-external` → `transcripts.py`
- 抓取解析：`TranscriptFetcher.fetch_transcript()` 在 `transcript_fetcher.py`
- 支持格式：SRT（`_parse_srt`）/ VTT（`_parse_vtt`）/ JSON（`_parse_json_transcript`）
- **如何维护**：
  - 新增站点规则 → 加到 `rss_service.py:_extract_transcript_url()`
  - 新增字幕格式 → 加到 `TranscriptFetcher` 的 parse 方法

**策略 2：AssemblyAI 云端转录（付费、最高质量）**
- 代码：`backend/app/services/whisper_service.py`（名叫 whisper 但实际用 AssemblyAI）
- API Key：`.env` 文件中的 `ASSEMBLYAI_API_KEY`，**无 UI 管理入口**
- 特性：说话人分离、实体识别、自动章节
- **如何维护**：更换 API Key 改 `.env`；前端显示费用估算在 `EpisodeDetailView.jsx:estimateCost`

**策略 3：本地 Whisper（未实现，已预留）**
- `config.py` 中 `WHISPER_MODEL = os.getenv("WHISPER_MODEL", "base")` 说明规划过
- 推荐用 `faster-whisper`（比官方 Whisper 快 4x，支持 GPU）
- 实现路径：在 `whisper_service.py` 里加新函数，在 `transcripts.py` 里加路由判断

### 维护原则

三种策略统一通过 `POST /api/transcripts/<episode_id>` 入口，按优先级路由：
```
有 transcript_url → 官方字幕（TranscriptFetcher）
无 transcript_url，有本地 Whisper 配置 → 本地转录
都没有 → AssemblyAI（whisper_service.py）
```
新增策略只需实现 `fetch_xxx(episode, progress_callback) → (text, segments)`，加到路由判断即可。

---

## Q4：删除转录结果，前端 UI 有没有实现？

**没有。**

`transcriptsApi.delete` 在 `api.js` 里定义了，但 `EpisodeDetailView.jsx` 里没有任何删除转录的按钮。

用户目前无法通过 UI 删除已有转录，只能通过 API 工具直接调用。

**需要加的：** 在转录 tab 右上角加"删除并重新转录"按钮，调用 `transcriptsApi.delete` 后再调 `transcriptsApi.create`。

---

## Q5：模板化摘要，前端 UI 是否实现？

**模板选择已实现，Block 级别的用户选择 UI 未实现。**

**已实现：**
- `EpisodeDetailView.jsx` 第 464 行：模板选择按钮组（动态从 DB 拉取）
- 切换模板 → 自动按 `enabled_by_default` 初始化 blocks → 请求对应摘要
- 模板管理 UI：`SettingsView` → `PromptTemplatesPanel`（可查看/创建/复制）

**代码存在但未渲染：**
- `toggleBlock()` 函数（第 256 行）和 `enabledBlocks` 状态存在
- 但整个 JSX 里没有一个 Block 切换按钮的渲染
- 用户只能看到"选哪个模板"，看不到"模板里有哪些 Blocks 可以开关"

**结论：** 模板切换完整，Block 粒度控制是半成品，有逻辑无 UI。

---

## Q6：摘要代码复杂度 — 前端 + 后端 + 模板管理

### 后端（7 个文件，双路径）

```
api/summaries.py                              ← 入口路由（薄）
  → services/summary_service.py               ← Facade，路由 v2/v3
      ├─ v3 路径（模板引擎，新）：
      │   core/summarization/engine.py        ← 主引擎：加载模板→构建 prompt→LLM→校验→存库
      │   core/summarization/prompt_builder.py      ← 动态拼装 system+user prompt + blocks
      │   core/summarization/schema_validator.py    ← 输出校验（最多重试2次）
      │   core/summarization/defaults/templates.py  ← 5个系统模板 + 19种 block 定义
      └─ v2 路径（兼容旧版）：
          services/prompts/base.py / general.py / investment.py / translate.py
```

**双路径切换逻辑**（`summary_service.py`）：
- 请求的 `template_name` 在数据库存在 → v3 引擎
- 不存在 → 降级到 v2 legacy prompts
- `general` 自动映射到 `learning` 模板

### 前端

```
EpisodeDetailView.jsx               ← 核心视图（约840行）
  状态：templates, selectedTemplate, enabledBlocks, summary
  操作：handleTemplateChange, generateSummary, toggleBlock（未渲染）
  展示：20+ 个摘要字段按条件渲染（tldr / key_points / investment_signals / ...）

services/api.js
  → summariesApi（get/create/translate/delete/getTemplates）
  → promptTemplatesApi（完整 CRUD）

views/settings/PromptTemplatesPanel.jsx    ← 模板管理 UI
```

### Prompt 模板在哪里维护

| 方式 | 位置 | 说明 |
|------|------|------|
| 系统模板初始化 | `backend/app/core/summarization/defaults/templates.py` | 改后需调 `POST /api/prompt-templates/init` 重新初始化 |
| 前端可视化管理 | 设置 → Prompt 模板面板 | 用户自定义模板可增删改，系统模板只读 |

---

## Q7：初始化模板是否合理？

### 5 个系统模板的设计

| 模板 | 场景 | 默认开启 Blocks |
|------|------|-----------------|
| learning | 通用学习笔记 | key_points, key_concepts, action_items |
| investment | 财经投资 | investment_signals, mentioned_tickers, market_insights, risk_alerts |
| tech | 技术产品 | technologies, product_insights, tech_trends |
| startup | 创业商业 | business_model, growth_tactics, lessons_learned |
| interview | 访谈故事 | guest_background, key_quotes, life_lessons, controversial_views |

### 合理的地方
- 场景覆盖有代表性
- investment 有专属 system_prompt（金融分析师角色）
- 用户可复制系统模板后自定义，系统模板不可破坏

### 不合理/值得改的地方

1. **所有模板共用同一个 COMMON_USER_PROMPT** — 只靠 blocks 区分，没有针对不同类型优化 prompt 结构
2. **investment 有专用 system_prompt，其他没有** — tech/startup/interview 也应该有专属角色描述，现在不一致
3. **language 参数默认 `en`** — 对中文用户不友好，应默认 `zh`
4. **19个 blocks 大多数默认关闭** — 用户根本不知道有什么可以开，发现成本高
5. **没有"中文播客"专用模板** — 中英文播客分析场景差异较大

---

## Q8：摘要块设计的本质问题与建议

### 用户的核心诉求

> "一次性说清楚我需要什么摘要，以后就用这套方法复用"

这是**个人意图的持久化复用**问题。模板设计的方向是对的，但当前实现有几个结构性问题：

### 当前策略的问题

**问题 1：用"菜单选项"代替"用户意图"**
- 用户需要在 5 个模板里选，再（理论上）勾选 Blocks
- 真实需求往往是："帮我提炼这期里提到的所有书" 或 "告诉我这个 CEO 对 AI 的真实判断"
- 这种颗粒度的意图无法映射到现有模板

**问题 2：结构固定，无法表达负向约束**
- 无法说"我不需要嘉宾介绍，直接给要点"
- 无法说"只关心商业模式，其他都省略"

**问题 3：翻译是独立步骤**
- 用户需要等英文生成，再点翻译，两步
- 可以在模板参数里把 language 默认设为中文，直接一步出中文

**问题 4：输出结构与前端显示绑定太紧**
- `EpisodeDetailView.jsx` 里 20+ 个字段的渲染是硬编码的 if/else
- 新增一种摘要结构，前端要同步改渲染代码

### 建议的改进路径

**短期（低改动成本）：**
- 把 Block 选择 UI 渲染出来（代码已有，只缺 JSX 渲染）
- 把 language 参数默认改为中文（直接出中文，不需要二次翻译）
- 在生成按钮附近加"自定义说明"输入框，用户写额外要求追加到 prompt 末尾

**中期：**
- 支持"从当次生成保存为个人配方"：用户满意某次摘要后，一键把当次 template+blocks+params 保存为自定义模板

**长期（设计思路变化）：**
- 从"选模板"变成"描述意图"：用户写自然语言描述"我是做 VC 的，关注创始人判断框架"，系统自动生成并持久化 prompt 配置

---

## Q9：AI 简报内容合理性 & 代码实现

### 实现状态：完整实现

| 组件 | 文件 | 状态 |
|------|------|------|
| 后端服务 | `services/briefing_service.py` | 已实现 |
| 提示词 | `services/briefing_prompts.py` | 已实现 |
| API 路由 | `api/insights.py` | 已实现（含 PDF 导出）|
| 前端视图 | `views/AIBriefingView.jsx` | 已实现 |
| 数据缓存 | MongoDB `briefings` 集合 | 已实现 |

### 简报的数据来源逻辑

```
_collect_recent_episodes(days=7)
  → 取所有 active feeds 的最近30集（按 published 排序）
  → 批量查 summaries → 有 AI 摘要用 content；没有用 RSS summary 降级
  → 发给 LLM，输出 JSON（hotTopics / newConcepts / trends / recommended / markdownReport）
  → 写入 briefings 集合（upsert by date，同一天复用）
```

### 合理性评估

**合理的：**
- hotTopics 的跨播客交叉分析是真正有价值的功能点
- markdownReport + PDF 双输出格式实用
- relatedEpisodes 直接关联单集 id，前端可跳转
- 降级策略合理（AI 摘要 → RSS summary → 标题）

**有问题的：**

1. **数据采集没按 `has_summary` 过滤** — 很多 RSS summary 只有几十字，用这种数据生成的简报质量差。应优先选 `has_summary=true` 的单集。
2. **trends.change 是 LLM 虚构** — 提示词注释说"基于提及频度估算"，没有历史数据支撑，LLM 会编造数值。
3. **keyQuotes 可能不真实** — 从压缩后的 RSS 摘要里"提取"的引述不是原话。
4. **命名混乱** — 前端 `res.briefing.briefing` 才是数据（MongoDB doc 有 `briefing` 字段存 LLM JSON），双层 briefing 命名让人困惑。
5. **7天窗口固定** — 无法参数化，用户无法调整。

---

## Q10：哪些是数据库，哪些是缓存，哪些是重载

### 数据库（MongoDB 永久存储）

| 集合 | 性质 |
|------|------|
| feeds / episodes / transcripts | 核心业务数据 |
| summaries | 生成结果（`force=false` 时复用 = 应用层缓存策略）|
| tasks | 任务状态（历史记录无 TTL 清理）|
| settings | LLM 配置 |
| prompt_templates | 模板定义 |
| **briefings** | **应用层缓存** — 按日期 upsert，同一天不重复生成 |

### 内存缓存（重启丢失）

| 对象 | 位置 | 说明 |
|------|------|------|
| `TaskQueue.tasks` dict | `services/task_queue.py` | 任务内存副本，重启后从 DB 恢复 |
| MongoDB 连接池 | pymongo 内部 | 无需手动管理 |

> 项目**没有** Redis、HTTP 缓存、Service Worker 等缓存层。所有"缓存"本质是 MongoDB 里的 upsert 策略。

### 用户触发的重载

| 操作 | 触发位置 | 重载范围 |
|------|----------|----------|
| `loadData()` | 页面初始化/操作完成后 | feeds + episodes(500) + workspace episodes |
| 简报 force=True | AIBriefingView 刷新按钮 | 覆盖当天 briefings 缓存 |
| 摘要 force=True | **无前端入口**（API 支持但未透出）| 覆盖对应 summary |
| feed refresh | 手动刷新/自动刷新（后台每小时）| 重新拉 RSS |

---

## Q11：重新生成，前端支持吗？

| 功能 | 前端支持 | 位置 |
|------|----------|------|
| 简报重新生成 | ✅ 已实现 | `AIBriefingView.jsx` 右上角 RefreshCw 按钮 → `insightsApi.regenerateBriefing()` |
| 摘要重新生成 | 半实现 | 点 Sparkles 按钮会调生成接口，但未传 `force=true`，已有摘要时直接返回缓存（不会重新生成）|
| 转录重新生成 | ❌ 未实现 | 无删除/重新生成按钮 |

---

## Q12：PDF 导出，前端有没有？

**有，已实现。**

- `AIBriefingView.jsx` 第 127 行：Download 图标按钮 → `insightsApi.exportPdf()`
- `api.js:insightsApi.exportPdf()` — 创建隐藏 `<a>` 标签直接触发文件下载
- 后端 `insights.py:export_briefing_pdf()` — weasyprint 把 `markdownReport` 渲染成 PDF

**问题：** 若简报的 `markdownReport` 字段为空，PDF 接口返回 404，但前端无提示，下载静默失败。

---

## Q13：LLM 配置 — 前端现状 & 通用包方案

### 当前前端实现（已完整）

`settings/LlmConfigPanel.jsx`：
- 最多 5 个配置，每个含：名称 / Base URL / API Key / Model / Max Tokens / Temperature
- 激活切换 / 连接测试 / 保存
- API Key 已保存显示 "(saved)" 占位符

**缺失的：**
- 没有 Provider 预设列表（用户需要手动填写 base_url，不知道各家地址）
- 没有 Model 选择器（需要手动输入模型名称字符串）
- 没有 Tavily / AssemblyAI Key 的配置 UI

### 主流 OpenAI 兼容提供商（可直接通过 base_url 接入）

| 提供商 | base_url |
|--------|----------|
| OpenAI | `https://api.openai.com/v1` |
| DeepSeek | `https://api.deepseek.com/v1` |
| SiliconFlow（硅基流动）| `https://api.siliconflow.cn/v1` |
| 阿里云百炼（Qwen）| `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| Moonshot（Kimi）| `https://api.moonshot.cn/v1` |
| 腾讯混元 | `https://api.hunyuan.cloud.tencent.com/v1` |
| Groq（推理快）| `https://api.groq.com/openai/v1` |
| Together.ai | `https://api.together.xyz/v1` |
| OpenRouter（聚合路由）| `https://openrouter.ai/api/v1` |

### 通用包方案

**LiteLLM（最推荐）**
- 部署一个 LiteLLM 代理实例，前端只配一个 base_url，后端通过 LiteLLM 路由到任意 LLM（含 Anthropic、Gemini 等非 OpenAI 格式的）
- 部署：`docker run -p 4000:4000 ghcr.io/berriai/litellm:main`
- 接入后 `LLMClient.py` **不需要任何改动**，只需把 base_url 换成 LiteLLM 地址
- 官网：litellm.ai

**OpenRouter（无需部署）**
- 一个 API Key 可以调用 100+ 家模型
- base_url = `https://openrouter.ai/api/v1`，model = `anthropic/claude-3-5-sonnet` 等格式
- 缺点：数据经过第三方，隐私场景不适合

**建议改进：** 在 `LlmConfigPanel` 里加一个 Provider 下拉预设，选择提供商后自动填入 base_url，用户只需填 API Key 和 Model 名称。

---

## 优先级总结 & 待办清单

### 高优先级（影响核心体验）

| # | 问题 | 文件位置 | 改动量 |
|---|------|----------|--------|
| 1 | 摘要 Block 选择 UI 未渲染 | `EpisodeDetailView.jsx` | 小，代码逻辑已有 |
| 2 | 删除转录 / 重新转录按钮缺失 | `EpisodeDetailView.jsx` | 小 |
| 3 | 简报采集不过滤质量差的 RSS summary | `briefing_service.py` | 小 |
| 4 | LLM 配置无 Provider 预设，用户体验差 | `LlmConfigPanel.jsx` | 中 |

### 中优先级（完整性）

| # | 问题 | 文件位置 | 改动量 |
|---|------|----------|--------|
| 5 | AssemblyAI Key 无 UI 配置 | `SettingsView` 新增面板 | 中 |
| 6 | 章节数据已存但未展示 | `EpisodeDetailView` 新增 tab | 中 |
| 7 | 摘要 language 默认应为中文 | `templates.py` 改 default | 极小 |
| 8 | PDF 下载静默失败无提示 | `AIBriefingView.jsx` | 小 |
| 9 | 摘要"强制重新生成"按钮缺失 | `EpisodeDetailView.jsx` | 小 |
| 10 | `TranscriptFetcher` 后缀名匹配太脆弱 | `transcript_fetcher.py` | 中 |

### 低优先级（体验优化）

| # | 问题 | 文件位置 | 改动量 |
|---|------|----------|--------|
| 11 | 本地 Whisper 支持（faster-whisper）| `whisper_service.py` | 大 |
| 12 | YouTube 字幕提取（yt-dlp）| `transcript_fetcher.py` | 中 |
| 13 | 简报 trends 用真实历史数据 | `briefing_service.py` 加历史对比 | 大 |
| 14 | 摘要"描述意图 → 自动生成配方"体验 | 全栈 | 大 |
| 15 | tasks 集合加 TTL 索引防数据膨胀 | `__init__.py:ensure_indexes` | 极小 |
# Phase 1 execution status - 2026-05-17

Status: completed for the first stabilization pass. Phase 2 has not started.

Completed items:
- Removed unused legacy frontend views: `LlmSettingsView.jsx`, `DownloadedView.jsx`, `TranscribedView.jsx`.
- Removed debug `console.log` output and unused local state from active views.
- Added `local_audio_url` to episode responses when a downloaded local audio file exists.
- Added `/api/media/<path>` serving for local media so the Vite `/api` proxy can play local audio.
- Updated frontend playback to prefer `local_audio_url`, with remote `audio_url` fallback on local playback failure.
- Updated `TranscriptFetcher` to detect SRT/VTT/JSON by URL, `Content-Type`, and body sniffing.
- Classified RSS fetch failures for 404/410, SSL certificate errors, timeout, HTTP 5xx, and feed parse errors.
- Added MongoDB TTL index on `tasks.completed_at` with 7-day expiry. Running/pending tasks are not deleted because they do not have a date value in `completed_at`.

Database note:
- No manual migration is required. MongoDB creates the TTL index during app startup.
- Existing completed/failed tasks with a valid `completed_at` date become eligible for TTL cleanup after 7 days.
- Tasks without `completed_at`, including pending/processing tasks, are unaffected.

---
