# 后端报告

> 基于 `backend/app/` 实际代码整理
> 文档日期：2026-05-16

---

## 1. 技术栈

| 依赖 | 版本 | 用途 |
|------|------|------|
| Python | 3.12 | 运行时 |
| Flask | ≥2.3 | Web 框架 |
| flask-cors | ≥4.0 | 跨域支持（限 localhost:3000）|
| pymongo | ≥4.5 | MongoDB 驱动 |
| feedparser | ≥6.0 | RSS 解析 |
| requests | ≥2.31 | HTTP 请求（RSS 拉取）|
| openai | ≥1.0 | OpenAI 兼容 LLM 调用 |
| tavily-python | ≥0.5 | Tavily 搜索（已集成，待使用）|
| python-dotenv | ≥1.0 | 环境变量加载 |
| markdown + weasyprint | ≥3.5 / ≥60 | PDF 导出（简报功能）|
| pytest | ≥8.0 | 测试框架 |

**运行端口**：`http://localhost:5000`

---

## 2. 应用架构

```
backend/
├── run.py                      # 入口：创建 Flask app 并启动
├── app/
│   ├── __init__.py             # 应用工厂：create_app()，注册蓝图、索引、任务队列、自动刷新
│   ├── config.py               # 配置管理（开发/生产）
│   ├── api/                    # 薄路由层
│   ├── services/               # 业务逻辑层
│   ├── models/                 # 数据模型层（纯文档结构）
│   └── core/                   # 可复用领域逻辑
└── tests/                      # pytest 测试
```

### 分层职责

```
api/      → 参数校验 + 调 service → 返回 JSON
services/ → 业务逻辑 + LLM 调用 + MongoDB 操作
models/   → 文档结构定义 + to_response() 格式转换
core/     → 可复用领域逻辑（SummarizationEngine）
```

---

## 3. 应用工厂（`__init__.py`）

`create_app()` 执行以下操作（按顺序）：

1. 加载 `Config`，初始化媒体目录
2. 注册 CORS（仅允许 `localhost:3000`）
3. 创建 `MongoClient`，挂到 `app.db`
4. `ensure_indexes(db)` — 创建所有集合索引
5. `task_queue.set_db(app.db)` — 任务队列注入数据库
6. `start_auto_refresher(app.db, interval_hours=1, stale_threshold_hours=6)` — 启动后台刷新线程
7. 注册 9 个蓝图
8. 注册 404 / 500 错误处理器

---

## 4. API 层（`app/api/`）

所有 API 使用统一响应格式（`api/utils.py`）：

```python
# 成功
{"success": true, "data": {...}}
# 错误
{"success": false, "message": "...", "error_code": "..."}
```

| 文件 | 蓝图前缀 | 说明 |
|------|----------|------|
| `feeds.py` | `/api/feeds` | 订阅源 CRUD、刷新、标星、收藏、获取单集 |
| `episodes.py` | `/api/episodes` | 单集列表、详情、更新、下载、标星、已读 |
| `transcripts.py` | `/api/transcripts` | 转录 CRUD、抓取官方字幕、检查外部字幕 |
| `summaries.py` | `/api/summaries` | 摘要生成/获取/翻译/删除、模板列表 |
| `tasks.py` | `/api/tasks` | 任务列表、状态、取消 |
| `stats.py` | `/api` | `/api/stats` 统计信息 |
| `settings.py` | `/api/settings` | LLM 配置 + Tavily 配置 |
| `prompt_templates.py` | `/api/prompt-templates` | 模板 CRUD、复制、blocks、parameters、初始化 |
| `insights.py` | `/api/insights` | AI 简报生成、获取、PDF 导出 |

---

## 5. 服务层（`app/services/`）

### 5.1 RSSService

- 使用 `requests` 模拟浏览器 User-Agent 拉取 RSS
- 解析 Feed 元信息（title / image / author / language）
- 解析单集信息（guid / audio_url / duration / transcript_url / chapters_url）
- 支持 Podcasting 2.0 扩展字段（章节、官方字幕）
- 内置摘要清理（截断广告链接）和 transcript_url 推断（如 lexfridman.com 模式）

### 5.2 TaskQueue

- 基于 `ThreadPoolExecutor`（默认 3 个 Worker）
- 任务提交后内存 + MongoDB 双写，保证重启后状态可查
- 任务执行时通过 `progress_callback` 回调更新进度（0-100）
- 取消仅支持 `pending` 状态

任务类型：`download` / `transcribe` / `summarize` / `refresh`

### 5.3 LLMClient

- 封装 `openai.OpenAI`，支持任意 OpenAI 兼容 API
- `chat()` — 普通聊天
- `chat_json()` — 强制 JSON 输出并解析，自动清理 markdown code block 包装

**配置优先级**：数据库 `settings` 中激活的 LLM 配置 > 环境变量

### 5.4 SummaryService

入口 Facade，路由两种摘要路径：

```
template_name 存在 → SummarizationEngine (v3, 基于 PromptTemplate)
template_name 不存在 → Legacy PromptRouter (v2, general/investment)
```

旧类型到新模板映射：`general → learning`，`investment → investment`

### 5.5 AutoRefresher

- 后台线程，每 `interval_hours` 小时检查一次
- 刷新条件：`last_checked` 超过 `stale_threshold_hours`（默认 6 小时）
- 通过 `RSSService` 拉取新单集，去重（guid 唯一索引）

### 5.6 TranscriptFetcher

- 解析多种字幕格式：SRT / VTT / JSON
- 先尝试 RSS 中的 `transcript_url`，再 AssemblyAI

### 5.7 BriefingService

- 基于当天已摘要单集生成综合 Markdown 报告
- 按日期缓存到 `briefings` 集合（unique 索引：date）
- 支持 force 参数覆盖缓存

### 5.8 TavilyService

- 封装 Tavily 搜索 API
- 已集成但尚未在主流程中使用（无前端触发入口）

---

## 6. 核心领域逻辑（`app/core/`）

### SummarizationEngine

```
输入：transcript + template_name + enabled_blocks + params
  ↓
1. 从 MongoDB 加载 PromptTemplate
2. PromptBuilder 动态拼装 system_prompt + user_prompt
3. 调 LLMClient.chat_json()（JSON 模式）
4. SchemaValidator 校验输出结构
5. 校验失败：追加纠错 Hint 重试（最多 MAX_RETRIES=2 次）
6. 最终仍不合格：lenient 模式填充默认值
7. 写入 MongoDB summaries 集合（upsert）
8. 更新 Episode 状态为 summarized
```

### PromptBuilder

- 从 `PromptTemplate.locked.system_prompt` 提取系统指令
- 动态追加 `optional_blocks` 中已启用 block 的 `prompt_fragment`
- 根据 `parameters` 值替换模板变量（如 length=long → "请提供详细分析"）

### SchemaValidator

- 按 PromptTemplate 中 `locked.required_fields` 和 `optional_blocks.output_field` 定义校验
- 支持 strict / normal / lenient 三种校验级别
- lenient 模式：缺失字段填充空字符串或空数组

---

## 7. 配置（`app/config.py`）

| 配置项 | 默认值 | 环境变量 |
|--------|--------|----------|
| MONGO_URI | mongodb://localhost:27017 | MONGO_URI |
| MONGO_DB | podcast | MONGO_DB |
| MEDIA_ROOT | backend/media | MEDIA_ROOT |
| TASK_WORKERS | 3 | TASK_WORKERS |
| RSS_TIMEOUT | 30s | RSS_TIMEOUT |
| LLM_BASE_URL | "" | LLM_BASE_URL |
| LLM_API_KEY | "" | LLM_API_KEY |
| LLM_MODEL | "" | LLM_MODEL |
| LLM_MAX_TOKENS | 4096 | LLM_MAX_TOKENS |
| LLM_TEMPERATURE | 0.2 | LLM_TEMPERATURE |
| SUMMARY_MAX_INPUT_CHARS | 100000 | SUMMARY_MAX_INPUT_CHARS |

---

## 8. 测试

测试位置：`backend/tests/`

| 文件 | 说明 |
|------|------|
| `conftest.py` | pytest fixtures（mock db / mock llm）|
| `test_infrastructure.py` | 基础设施测试（配置、客户端初始化）|
| `test_summary_flow.py` | 摘要生成流程集成测试 |

运行：
```bash
cd backend
python -m pytest tests/ -v
```

---

## 9. 已知问题

| 问题 | 位置 | 描述 |
|------|------|------|
| insights API 计划文档过时 | `plan.md` | 标注为 placeholder，实际已完整实现（含 PDF 导出）|
| Tavily 配置无 UI | `settings.py` | 后端接口存在（GET/PUT/test），前端 UI 未实现 |
| summarize 旧新 API 双路径 | `summary_service.py` | v2 legacy 路径和 v3 engine 路径同时存在，维护成本高 |
| AssemblyAI Key 无 UI 管理 | `transcript_fetcher.py` | 只能通过 `.env` 配置 |
| 无 Dockerfile | 根目录 | README 要求 MongoDB，但无容器化方案 |
| LLM 客户端线程安全 | `llm_client.py` | `get_llm_client()` 每次新建实例，高并发下重复连接 MongoDB 取配置 |
