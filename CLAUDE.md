# PodMaster - 项目约束

> 给 AI 助手的规则文件。schema 细节看 `docs/database.md`，端点看 `docs/api.md`，两处与代码不一致时以代码为准并修文档。

## 技术栈
- **后端**: Python 3.13 + Flask + MongoDB + ThreadPoolExecutor（uv 管理依赖，真源 `backend/pyproject.toml`）
- **前端**: React 18 + Vite + TailwindCSS（dev 端口 3000，占用自动递增；3002 常见）
- **AI**: LLMClient 双协议（OpenAI 兼容 SDK / Anthropic HTTP）+ 本地 faster-whisper / WhisperX
- **视频源**: yt-dlp、youtube-transcript-api、curl_cffi（B站 wbi 签名 + chrome TLS 指纹绕反爬）
- **本地 AI 是可选组件**：torch/faster-whisper/whisperx 在 `local-ai` 依赖组（安装器 `setup_local_ai.py` 在仓库根目录）。**模块顶层禁止 import torch/whisper***，一律函数内懒加载；端点入口用 `is_available()` 守卫并返回 `LOCAL_AI_NOT_INSTALLED`

## 领域规则（违反会破坏已定产品决策）

- **共享库**：feeds/episodes/transcripts/summaries 全员可读，`owner_filter()` 只归档不隔离。个人状态（is_read/is_starred/play_position）一律走 `services/user_episode_state.py`，不写剧集文档
- **LLM 配置全局一套**：settings 无 per-user 键；`get_setting_model()` 不带 owner。管理端点挂 `@require_admin`
- **转写策略**：平台接口字幕自动拉；本地 WhisperX 转写一律手动触发（"立即转写"），不做任何自动排队
- **B站字幕入库前必须过四重校验 + 同订阅查重**（防串台），校验逻辑在 `bilibili_service.py`
- **订阅全局唯一**：按规范化 URL 去重（`_normalize_feed_url`）
- **认证三档**：admin / user / viewer；注册默认 pending 需审批。`<audio>` 等场景令牌走 query 参数（见 `/episodes/<id>/stream`）
- 其余数据治理决策见 `docs/database.md` 底部（弃用字段清单）

## 核心工作流

### 原子提交规则
- 每完成一个原子任务立即 commit；一个 commit 只做一件事
- message 格式: `<type>(<scope>): <描述>`，type: feat/fix/refactor/test/docs/chore
- 提交前测试必须全绿（`cd backend && uv run pytest`）；前端改动跑 `npm run build`

### TDD 迭代
写失败测试 → 最小实现 → 测试保护下重构

## 架构约束

### 后端分层
```
api/        → 薄路由层，只做参数校验和调 service
services/   → 业务逻辑，调 LLMClient / MongoDB
models/     → 纯数据模型，不含业务逻辑
core/       → 可复用的领域逻辑（如 summarization engine）
```

### AI 调用规范
- 统一通过 `LLMClient` 调用，不直接 import openai
- 每个 AI 功能是独立的 Service（如 BriefingService、SummaryService）
- 不引入中间抽象层（如 LangGraph），除非有真实需求
- 不写 placeholder / TODO — 要么实现，要么不写

### 前端
- API 调用统一在 `services/api.js`，组件不直接用 axios
- 视图组件（views/）只负责渲染，状态提升到 App.jsx

## 代码规范
- 不写 mock 数据 — 前端要么接真实 API，要么显示空状态
- 不写 try/catch 包裹不会失败的代码
- 不添加没有真实需求的防御性分支
- 函数单一职责，名称即文档

## 测试规范
- 后端测试: `pytest`，放 `backend/tests/`，命名 `test_<module>.py`
- MockDB 在 `tests/conftest.py`（支持 $in/$nin/$gte/$ne 与 upsert；新增操作符需同步扩展）
- LLM 调用用 mock；每个 API 端点至少一个集成测试

## Git 规范
- **禁止在 master 直接 commit**：所有修改先建 `<type>/<name>` 分支；合并用 `git merge --no-ff`
- 不提交 .env、.venv、node_modules、__pycache__、backups/
