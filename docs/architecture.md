# 架构概览

> 从源码实际结构提取。

---

## 技术栈

| 层 | 技术 |
|----|------|
| 前端 | React 18 + Vite + TailwindCSS |
| 后端 | Python 3.12 + Flask |
| 数据库 | MongoDB (pymongo) |
| AI | OpenAI 兼容 API + 本地 Whisper/WhisperX |
| 认证 | JWT (HS256) |
| 国际化 | i18next (中/英) |

---

## 系统分层

```
frontend/src/                    backend/app/
├── services/api.js ───────────→ api/            ← 薄路由层，参数校验
├── components/                  ├── models/      ← 纯数据模型
│   ├── views/                   ├── services/    ← 业务逻辑
│   ├── cards/                   └── core/        ← 可复用领域逻辑
│   ├── common/                      └── summarization/
│   ├── player/                          ├── engine.py
│   ├── tasks/                           ├── prompt_builder.py
│   └── layout/                          └── schema_validator.py
└── locales/
    ├── zh.json
    └── en.json
```

---

## 后端模块地图

### API 层 (12 个蓝图，58 个路由)

| 蓝图 | 前缀 | 文件 | 路由数 | 职责 |
|------|------|------|--------|------|
| auth | `/api/auth` | `auth.py` | 3 | 注册/登录/me |
| admin | `/api/admin` | `admin.py` | 4 | 用户管理/健康检查 |
| feeds | `/api/feeds` | `feeds.py` | 9 | RSS 订阅 CRUD + 刷新 + 星标 |
| episodes | `/api/episodes` | `episodes.py` | 6 | 单集列表/详情/下载/星标 |
| transcripts | `/api/transcripts` | `transcripts.py` | 5 | 转录 CRUD + 外部拉取 |
| summaries | `/api/summaries` | `summaries.py` | 5 | 摘要 CRUD + 翻译 + 模板 |
| tasks | `/api/tasks` | `tasks.py` | 3 | 任务列表/状态/取消 |
| settings | `/api/settings` | `settings.py` | 9 | LLM/Tavily/提示词配置 |
| prompt_templates | `/api/prompt-templates` | `prompt_templates.py` | 9 | 模板 CRUD + 初始化 |
| insights | `/api/insights` | `insights.py` | 3 | AI 简报 + PDF 导出 |
| stats | `/api` | `stats.py` | 1 | 系统统计 |

### 服务层 (13 个服务)

| 服务 | 文件 | 行数 | 职责 |
|------|------|------|------|
| TaskQueue | `task_queue.py` | 343 | ThreadPoolExecutor 异步任务队列 |
| RssService | `rss_service.py` | 391 | RSS 解析，提取播客/单集元数据 |
| TranscriptFetcher | `transcript_fetcher.py` | 582 | 从外部 URL 拉取 + 解析标准格式 |
| WhisperService | `whisper_service.py` | 215 | 本地 Faster-Whisper 转录 |
| WhisperXService | `whisperx_service.py` | 302 | 本地 WhisperX 转录 (词级对齐) |
| TranscriptPostprocessor | `transcript_postprocessor.py` | 181 | 所有转录后处理 |
| SummaryService | `summary_service.py` | 143 | 摘要服务 facade |
| BriefingService | `briefing_service.py` | 266 | AI 简报生成 + 缓存 |
| LLMClient | `llm_client.py` | 309 | LLM 统一调用 (OpenAI/Anthropic 双协议) |
| BriefingPrompts | `briefing_prompts.py` | 140 | 简报提示词模板 |
| JwtAuth | `jwt_auth.py` | 62 | JWT 工具 |
| AiControl | `ai_control.py` | 12 | AI 功能全局开关 |
| AutoRefresher | `auto_refresher.py` | 226 | 定时刷新 RSS |

### 核心层

| 模块 | 文件 | 行数 | 职责 |
|------|------|------|------|
| SummarizationEngine | `engine.py` | 386 | 模板化摘要：加载→构建→调用→校验→重试→保存 |
| PromptBuilder | `prompt_builder.py` | 226 | 从模板动态构建提示词 |
| SchemaValidator | `schema_validator.py` | 99 | 校验 LLM JSON 输出 |
| DefaultTemplates | `defaults/templates.py` | 519 | 系统默认模板定义 |

---

## 前端组件树

```
App.jsx (707 行) — 路由 + 全局状态 + 播放器 + 任务面板
├── Sidebar.jsx — 导航
├── AuthView.jsx — 登录/注册
├── WorkspaceView.jsx — 主工作台
├── FeedDetailView.jsx — Feed 详情
├── EpisodeDetailView.jsx — 单集详情 (1160 行，最大组件)
├── FavoritesView.jsx — 收藏
├── AIBriefingView.jsx — AI 简报
├── SettingsView.jsx — 设置容器
│   ├── LlmConfigPanel.jsx — LLM 配置 (服务商/模型/路由)
│   ├── PromptTemplatesPanel.jsx — 提示词模板管理
│   ├── AppSettingsPanel.jsx — 应用设置
│   └── AccountPanel.jsx — 账号管理
├── PlayerBar.jsx — 底部音频播放器
├── TaskPanel.jsx — 后台任务面板
└── common/
    ├── ViewToolbar.jsx
    ├── StatusBadge.jsx
    ├── TaskProgress.jsx
    └── LanguageSwitcher.jsx
```

---

## 数据流

```
RSS URL
  │
  ▼
RssService.parse() → Feed + Episodes (MongoDB)
  │
  ▼
TaskQueue.submit("download") → 本地音频文件
  │
  ▼
TaskQueue.submit("transcribe") → Transcript (Whisper/WhisperX/外部)
  │
  ▼
TaskQueue.submit("summarize") → Summary (LLM + 模板引擎)
  │
  ▼
BriefingService → 聚合 7 天 episodes → AI 简报
```

---

## 认证与数据隔离

- **JWT**: HS256，注册/登录获取 token
- **首个用户**自动成为 admin
- **owner_id**: 所有集合按 `owner_id` 字段隔离
- **API 层**: `@require_auth` 装饰器验证 token，`owner_filter()` 自动注入 owner_id

---

## 代码规模

| 模块 | 文件数 | 行数 |
|------|--------|------|
| 后端 Python | 44 | ~7,185 |
| 前端 JSX/JS/CSS | 27 | ~5,544 |
| 测试 | 24 | — |
| **总计** | **95** | **~12,729** |
