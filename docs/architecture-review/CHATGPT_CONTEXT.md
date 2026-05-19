# AI 助手项目上下文

> 本文档供另一个 AI 助手快速理解项目全貌，2026-05-17

---

## 1. 项目一句话说明

播客 AI 阅读助手：订阅 RSS 播客 -> 下载音频 -> 转录文本 -> LLM 生成结构化摘要 -> 每日 AI 简报 -> 阅读/播放。单体应用，个人项目，当前处于可运行的 MVP 阶段。

---

## 2. 技术栈

| 层 | 技术 |
|---|------|
| 后端 | Python 3.12 + Flask + pymongo + ThreadPoolExecutor |
| 前端 | React 18.2 + Vite 5.0 + TailwindCSS 3.4 + axios + i18next |
| AI | OpenAI 兼容 API（通过 openai SDK 的 `chat.completions.create`）+ AssemblyAI（音频转录）|
| 搜索 | Tavily API（已集成 service，前端未使用）|
| PDF | weasyprint + markdown |
| 数据库 | MongoDB（pymongo 直连，无 ORM），Docker 容器化部署 |
| 媒体 | 本地文件系统（backend/media/audio/） |

启动入口 `backend/run.py` 自动管理 MongoDB Docker 容器生命周期（检测 -> 启动已有 -> 创建新的 -> 健康检查），容器名为 `podcast-mongodb`，数据持久化到 Docker Volume `podcast-mongodb-data`。

---

## 3. 核心用户流程

```
添加 RSS URL
  -> 后端 feedparser 解析获取元信息 + 单集列表
  -> 用户点击下载（异步任务，ThreadPoolExecutor）
  -> 用户点击转录（AssemblyAI API 或外部字幕抓取）
  -> 用户点击生成摘要（v3 模板引擎 / v2 legacy，异步任务）
  -> 系统自动翻译为中文（LLM 二次调用）
  -> 阅读：结构化摘要卡片 + 转录全文 + 音频播放
  -> AI 每日简报：聚合最近 7 天多播客摘要，LLM 生成每日洞察
```

Episode 生命周期严格线性推进：`new -> downloading -> downloaded -> transcribing -> transcribed -> summarizing -> summarized`，任意阶段可进入 `error`。状态守卫方法在 `Episode.can_download/can_transcribe/can_summarize`，分别只允许 `new`、`downloaded`、`transcribed` 三个状态触发下一步。

---

## 4. 目录结构

```
backend/
  run.py                    # 入口，自动管理 MongoDB Docker 容器
  app/__init__.py           # 应用工厂 create_app()，初始化 DB/索引/蓝图/自动刷新
  app/config.py             # 配置类（MongoDB/LLM/media 路径/任务线程数）
  app/api/                  # 9 个蓝图路由层
    feeds.py                # RSS 订阅 CRUD + 异步刷新 + 级联删除
    episodes.py             # 单集列表/详情/下载/标星/已读
    transcripts.py          # 转录创建/获取/删除/外部字幕抓取
    summaries.py            # 摘要创建(v2/v3双路径)/获取/翻译/删除
    tasks.py                # 任务列表/详情/取消
    settings.py             # LLM 配置管理(最多5个) + Tavily 配置
    prompt_templates.py     # Prompt 模板 CRUD + 复制 + 系统模板初始化
    insights.py             # AI 简报生成/缓存/PDF 导出
    stats.py                # 全局统计
  app/services/             # 业务逻辑层
    summary_service.py      # 摘要门面，v2/v3 路由分发
    llm_client.py           # OpenAI 兼容客户端，chat() + chat_json()
    task_queue.py           # ThreadPoolExecutor(3 workers) + 内存/MongoDB 双写
    rss_service.py          # feedparser 解析 + 转录 URL 提取
    transcript_fetcher.py   # SRT/VTT/JSON 解析（URL 后缀匹配）
    whisper_service.py      # Whisper 本地转录（备用）
    briefing_service.py     # 每日简报生成 + 按日期缓存
    briefing_prompts.py     # 简报 prompt 常量
    auto_refresher.py       # 后台守护线程，每小时检查过期 feed
    tavily_service.py       # Tavily 搜索（已集成未使用）
    prompts/                # v2 legacy prompts（base/general/investment/translate）
  app/core/summarization/   # v3 模板引擎核心
    engine.py               # SummarizationEngine（模板加载 -> prompt 拼装 -> LLM 调用 -> schema 校验 -> 重试）
    prompt_builder.py       # PromptBuilder（动态拼 system/user/blocks/schema/params）
    schema_validator.py     # SchemaValidator（strict/normal/relaxed 三级校验）
  app/models/               # 纯数据模型，不含业务逻辑
    feed.py / episode.py / summary.py / transcript.py / task.py / setting.py / prompt_template.py

frontend/
  src/App.jsx               # 主组件，17 个 useState，view 字符串条件渲染 7 个视图
  src/services/api.js        # axios 实例 + 响应拦截器 + 8 个 API 对象
  src/components/
    views/                  # 7 个视图组件
      EpisodeDetailView.jsx # 最复杂（850+ 行），承担转录/摘要/模板/任务/播放
      FeedDetailView.jsx    # 单个订阅源的单集列表
      WorkspaceView.jsx     # 已转录/已摘要的工作区
      AIBriefingView.jsx    # AI 每日简报
      SettingsView.jsx      # 设置入口
      FavoritesView.jsx     # 收藏
      settings/
        LlmConfigPanel.jsx  # LLM 配置管理（9 个 Provider 预设）
        PromptTemplatesPanel.jsx  # Prompt 模板管理（左右分栏，blocks 启用/禁用）
    layout/Sidebar.jsx      # 左侧导航栏
    player/PlayerBar.jsx    # 底部播放器
    cards/                  # FeedCard + EpisodeCard
    common/                 # TaskProgress + StatusBadge + LanguageSwitcher
    tasks/TaskPanel.jsx     # 右侧任务进度面板
```

---

## 5. 后端架构关键细节

### 5.1 应用初始化流程

`create_app()` 做了以下事情：
1. 加载配置（`get_config()` 根据环境选择 Development/Production）
2. 创建媒体目录（audio/covers/temp）
3. 启用 CORS（限制 localhost:3000）
4. 创建 MongoClient + 确保全部索引（9 个 collection，约 15 个索引）
5. 初始化全局 TaskQueue（3 worker 线程）
6. 启动 AutoRefresher 守护线程（每小时检查，6 小时未更新则刷新）
7. 注册 9 个蓝图到 `/api` 前缀下

### 5.2 摘要系统（核心业务逻辑）

摘要系统存在两套并行路径，这是当前最大的架构复杂度来源：

**v3 模板引擎（当前主力）**：
- 入口：`SummaryService.generate_summary()` -> 查找 `db.prompt_templates` 中 `name + is_active` 的模板
- 找到模板后走 `SummarizationEngine.summarize_episode()`
- 流程：加载模板 -> PromptBuilder 动态拼装 prompt（system + user + blocks + schema）-> LLM chat_json -> SchemaValidator 校验 -> 失败自动重试（最多 2 次，附带 correction hint）
- 模板结构：`locked`（系统 prompt + 必需字段）+ `optional_blocks`（18 个可选 block，每个有 prompt_fragment + output_field）+ `parameters`（length/language 等 enum 参数）
- 5 个系统模板：learning/investment/tech/startup/interview
- 用户可复制系统模板自定义，系统模板不可修改/删除

**v2 legacy（兼容路径）**：
- 条件：模板名在 `db.prompt_templates` 中不存在时回退
- 入口：`SummaryService._generate_legacy()` -> `PromptRouter.get_prompt(summary_type)` -> hardcoded prompt
- 输出格式固定，无 block 灵活性

**路由映射**（`_map_legacy_type`）：
```
general -> learning, investment -> investment, tech -> tech, startup -> startup, learning -> learning, interview -> interview
```

**数据区分**：
- v2 文档：`version="v2"`, `summary_type="general"/"investment"`, 无 `template_name` 字段
- v3 文档：`version="v3"`, `template_name="learning"/"investment"/...`, 有 `enabled_blocks` 和 `params`

### 5.3 LLM 客户端

`LLMClient` 封装 openai SDK，支持两种调用模式：
- `chat()`：返回原始 content + usage + model + elapsed_seconds
- `chat_json()`：chat() + `response_format=json_object` + 自动解析 JSON（含 markdown 代码块清理）

配置获取优先级：Flask 上下文 `get_db()` -> 直接连接 MongoDB -> 环境变量 fallback。每次调用创建新实例以保证线程安全。

### 5.4 任务队列

`TaskQueue` 基于 `ThreadPoolExecutor(max_workers=3)`，全局单例。任务状态双写到内存 dict 和 MongoDB `tasks` 集合。worker 线程通过 `app.app_context()` 访问数据库。支持 progress_callback 实时更新进度。任务类型：download/transcribe/summarize/refresh/translate。

### 5.5 AI 简报

`BriefingService` 聚合最近 7 天的单集数据（优先 AI 摘要，次选 RSS 元数据），拼接后调用 LLM 生成结构化简报。按日期缓存到 `briefings` 集合，同一天内不重复生成（除非 force）。数据收集策略：先取有 AI 摘要的单集（限 30 条），不足 5 条则补充未摘要单集。

---

## 6. 前端架构关键细节

### 6.1 状态管理

`App.jsx` 是唯一的状态中心，持有 17 个 useState：
- 导航状态：`view`(字符串), `previousView`, `viewMode`(traditional/ai-briefing)
- 数据状态：`feeds`, `episodes`, `workspaceEpisodes`, `feedEpisodes`
- 选中状态：`activeFeed`, `selectedFeed`, `selectedEpisode`
- 播放状态：`currentPlaying`, `isPlaying`
- UI 状态：`loading`, `searchQuery`, `episodeViewMode`(grid/list), `feedEpisodesLoading`

通过 `view` 字符串条件渲染 7 个视图：workspace / list / feedDetail / detail / favorites / settings / (ai-briefing 内嵌于 list)。

### 6.2 播放器

`<audio>` 元素的 src 绑定 `currentPlaying?.audio_url`（远程 URL），**未使用本地已下载的 audio_path**。播放位置通过 `episodesApi.update()` 保存到后端，每 30 秒自动保存一次，切换歌曲时也会保存。存在已知 bug：切换歌曲用 `setTimeout(100ms)` 等待 audio 元素更新。

### 6.3 API 层

`api.js` 创建 axios 实例，响应拦截器统一解包 `response.data`。404 被视为预期情况（资源尚未创建），不打印 error 日志。导出 8 个 API 对象：feedsApi/episodesApi/transcriptsApi/summariesApi/promptTemplatesApi/tasksApi/statsApi/settingsApi/insightsApi。

### 6.4 EpisodeDetailView（最复杂组件）

850+ 行的单文件组件，管理：
- 转录获取/创建/外部抓取
- 摘要生成（模板选择 + blocks 启用/禁用 + 参数配置）
- 中英文切换
- 任务进度追踪
- 音频播放控制
- 12 个独立的 useState

---

## 7. MongoDB 数据模型

| Collection | 关键字段 | 唯一索引 | 注意事项 |
|-----------|---------|---------|---------|
| feeds | rss_url, status, is_favorite | rss_url | episode_count 冗余存储 |
| episodes | feed_id, guid, status, audio_url, audio_path, play_position | (feed_id, guid) | is_starred 和 is_favorite 并存 |
| transcripts | episode_id, text, source | episode_id | source 字段区分 whisper/assemblyai/external |
| summaries | episode_id, version, summary_type(v2)/template_name(v3), content, content_zh | 无唯一索引 | 一集可有多条不同模板的摘要 |
| tasks | task_id, task_type, status, progress | task_id | 无 TTL，长期运行会膨胀 |
| settings | type, config | 无 | LLM configs 存为数组，active_index 标记当前 |
| prompt_templates | name, is_system, is_active, locked, optional_blocks, parameters | name | 系统模板不可修改/删除 |
| briefings | date, briefing, episode_count | date | 按日期唯一，同天 upsert |

### Summary 文档结构差异

v2 文档：
```json
{ "episode_id": "...", "summary_type": "general", "version": "v2", "tldr": "...", "tags": [], "content": {...}, "content_zh": {...} }
```

v3 文档：
```json
{ "episode_id": "...", "template_name": "learning", "version": "v3", "enabled_blocks": ["core_content", "key_points"], "params": {"length": "medium"}, "tldr": "...", "tags": [], "content": {...}, "content_zh": {...} }
```

`Summary.to_response()` 是前端展示的转换层，对 v2/v3 分别提取不同字段到 response 顶级。v3 路径会根据 content 中可能存在的所有 block 字段全部展平到 response 顶级（约 20 个字段），这导致响应体非常冗余。

---

## 8. API 端点总览

| 蓝图 | 路径前缀 | 核心端点 |
|-----|---------|---------|
| feeds | /api/feeds | GET / POST / DELETE /{id} /refresh /star /favorite /{id}/episodes |
| episodes | /api/episodes | GET /{id} / PUT /{id} /star /read /download |
| transcripts | /api/transcripts | GET /{episodeId} / POST /{episodeId} / DELETE /{episodeId} /fetch /check-external |
| summaries | /api/summaries | GET /{episodeId} / POST /{episodeId} / DELETE /{episodeId} /translate /templates /types |
| tasks | /api/tasks | GET / /{id} /cancel |
| settings | /api/settings | GET/PUT /llm / PUT /llm/active / POST /llm/test |
| prompt_templates | /api/prompt-templates | GET / POST /{idOrName} / PUT /{id} / DELETE /{id} /duplicate /init /blocks /parameters |
| insights | /api/insights | GET /briefing / POST /briefing / GET /briefing/export |
| stats | /api/stats | GET / |

所有端点遵循统一响应格式：`{ "success": true/false, "data": {...}, "message": "..." }`（通过 `success_response/error_response` 工具函数）。

---

## 9. 当前技术债 Top 10（按严重程度排序）

| # | 债务 | 影响 | 涉及文件 |
|---|------|------|---------|
| 1 | Summary.to_response() 硬编码所有 block 字段展平 | 新增 block 必须改此方法 + 前端 EpisodeDetailView，耦合三处 | backend/app/models/summary.py L91-138 |
| 2 | v2/v3 双路径并存 | 两套 prompt 系统、两套输出格式、API 层需同时处理 summary_type 和 template_name | backend/app/services/summary_service.py, backend/app/api/summaries.py |
| 3 | EpisodeDetailView.jsx 850+ 行 | 转录/摘要/模板/任务/播放逻辑全在一个组件，越来越难维护 | frontend/src/components/views/EpisodeDetailView.jsx |
| 4 | summary_type 与 template_name 混用 | 查询逻辑复杂，summaries.py 的 GET/POST/DELETE 都需双字段判断 | backend/app/api/summaries.py L50-66 |
| 5 | App.jsx 17 个 useState | 新功能越来越难加，状态交叉依赖多 | frontend/src/App.jsx |
| 6 | 音频播放未用本地文件 | 下载后仍播远程 audio_url，浪费带宽，离线不可用 | frontend/src/App.jsx L432 |
| 7 | TranscriptFetcher 仅 URL 后缀匹配 | 只识别 .srt/.vtt/.json 后缀，很多合法 URL 无法抓取 | backend/app/services/transcript_fetcher.py L48-50 |
| 8 | 前端分页不完整 | episodes 列表硬编码 per_page=500/1000 | frontend/src/services/api.js L59, frontend/src/App.jsx L79 |
| 9 | tasks 集合无 TTL | 长期运行数据膨胀，已完成任务永远不会自动清理 | backend/app/services/task_queue.py |
| 10 | Transcript 模型不完整 | AssemblyAI 产出的 chapters/entities/speakers 未建模 | backend/app/models/transcript.py |

---

## 10. 关键设计决策与约束

1. **统一 LLM 入口**：所有 AI 调用通过 `LLMClient`，不直接 import openai。每个 AI 功能是独立的 Service（BriefingService/SummaryService），不引入 LangChain/LangGraph。
2. **模板引擎而非硬编码 prompt**：v3 使用数据库存储的模板（locked + optional_blocks + parameters），运行时 PromptBuilder 动态拼装，支持用户自定义。
3. **异步任务不依赖 Celery/Redis**：ThreadPoolExecutor + MongoDB 双写，够用但不支持跨进程/分布式。
4. **前端不做全局状态管理库**：useState + props 传递，认为当前规模 hooks 够用。
5. **MongoDB 无 ORM**：pymongo 直连，Model 层只负责文档结构定义和 `to_response()` 格式转换。
6. **CORS 限制为 localhost**：开发环境定位，未考虑远程部署。
7. **摘要生成后自动翻译**：`_summarize_sync()` 中生成摘要后立即调用 `translate_summary()`，翻译失败不阻塞主流程。

---

## 11. 如果让 AI 改代码，安全操作清单

以下是风险最低、收益最高的改动，按优先级排序：

| 优先级 | 改动 | 涉及文件 | 风险 |
|-------|------|---------|------|
| P0 | 播放器使用本地 audio_path | App.jsx L432 | 低，只需改 src 绑定 |
| P0 | tasks 集合加 TTL 索引（如 7 天） | app/__init__.py ensure_indexes() | 低，纯数据库操作 |
| P1 | Summary.to_response() 新增 blocks 字段 | backend/app/models/summary.py | 中，需前后端同步 |
| P1 | TranscriptFetcher 加 Content-Type 嗅探 | backend/app/services/transcript_fetcher.py | 低，扩大格式识别范围 |
| P2 | EpisodeDetailView 拆分为子组件 | frontend/src/components/views/ | 中，需保证功能不变 |
| P2 | 新建 SummaryBlockRenderer 通用组件 | frontend/src/components/summary/ (新建) | 低，纯新增 |
| P3 | v2 legacy 标记为只读 | backend/app/services/summary_service.py | 低，只影响生成路径 |

---

## 12. 不建议做的事情

- **不引入 Redux/MobX**：当前 17 个 useState 虽多，但 hooks 够用，引入状态管理库的迁移成本远大于收益
- **不把 Flask 换 FastAPI**：路由层已经很薄，换框架成本高收益低
- **不上 Redis**：MongoDB upsert + 内存 dict 够用，当前并发量不需要 Redis
- **不引入 LangChain/LangGraph**：LLMClient + 模板引擎已经够灵活
- **不做微服务拆分**：个人项目单体足够，拆分后运维复杂度远大于开发收益
- **不删 v2 legacy 代码**：已有 v2 数据在数据库中，保留只读兼容更安全

---

## 13. 测试基础设施

```
backend/tests/
  conftest.py              # pytest fixtures
  test_infrastructure.py   # 基础设施测试
  test_task_queue.py       # 任务队列测试
  test_summary_flow.py     # 摘要流程测试
```

运行方式：`cd backend && python -m pytest tests/ -v`
LLM 调用用 mock，MongoDB 用 mongomock 或 mock。项目约定 TDD 流程（Red -> Green -> Refactor），但测试覆盖率目前较低。

---

## 14. 环境配置

后端通过 `.env` 文件加载配置（`dotenv`），关键环境变量：
- `MONGO_URI`：默认 mongodb://localhost:27017
- `MONGO_DB`：默认 podcast
- `LLM_BASE_URL` / `LLM_API_KEY` / `LLM_MODEL`：LLM 配置（也支持数据库配置覆盖）
- `FLASK_HOST` / `FLASK_PORT` / `FLASK_DEBUG`：Flask 配置
- `TASK_WORKERS`：线程池大小，默认 3

前端 Vite dev server 默认 localhost:3000，通过 Vite proxy 转发 /api 到后端 5000 端口。

---

## 15. 架构图（数据流）

```
用户浏览器 (localhost:3000)
    |
    | axios /api/*
    v
Flask (localhost:5000)
    |
    +-- api/feeds.py      ---> rss_service.parse_feed() ---> feedparser
    +-- api/episodes.py   ---> task_queue.submit(download)
    +-- api/transcripts.py ---> transcript_fetcher.fetch_transcript() 或 assemblyai
    +-- api/summaries.py  ---> summary_service.generate_summary()
    |                         +-> v3: SummarizationEngine -> PromptBuilder -> LLMClient -> SchemaValidator
    |                         +-> v2: PromptRouter -> LLMClient
    +-- api/insights.py   ---> briefing_service.get_or_generate() -> LLMClient
    |
    v
MongoDB (localhost:27017, Docker)
    collections: feeds / episodes / transcripts / summaries / tasks / settings / prompt_templates / briefings

ThreadPoolExecutor (3 workers)
    +-- download 任务: requests.get() -> 本地文件
    +-- transcribe 任务: assemblyai API 或外部字幕
    +-- summarize 任务: summary_service -> LLM -> 自动翻译
    +-- refresh 任务: rss_service.parse_feed() -> 增量更新 episodes

AutoRefresher (daemon thread, 1h interval)
    -> 检查 last_checked > 6h 的 feeds -> 逐个刷新
```
