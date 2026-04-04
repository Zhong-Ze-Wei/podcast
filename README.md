# Podcast Manager

播客管理应用：RSS 订阅 → 音频转录 → AI 摘要生成

## 技术栈

| 层 | 技术 |
|---|------|
| 前端 | React 18 + Vite + TailwindCSS + i18next |
| 后端 | Flask + MongoDB |
| 转录 | AssemblyAI (云端，说话人分离) / 官方字幕抓取 |
| 摘要 | LLM API (OpenAI 兼容) |
| 异步任务 | ThreadPoolExecutor |

## 快速启动

### 环境要求

- Python 3.10+ (推荐 3.13)
- UV (Python 包管理器) - [安装指南](https://docs.astral.sh/uv/getting-started/installation/)
- Node.js 18+
- MongoDB (端口 27017)

### 后端

```powershell
cd backend

# 激活已有的 UV 虚拟环境
.venv\Scripts\activate

# 安装/更新依赖（依赖变更时执行）
uv pip install -r requirements.txt

# 启动服务
python run.py                    # 默认 http://localhost:5000
```

### 前端

```bash
cd frontend
npm install
npm run dev                      # 默认 http://localhost:3000
```

## 核心功能

- RSS 订阅管理（支持 Podcasting 2.0：官方字幕、章节）
- AssemblyAI 云端转录（说话人分离、实体识别、自动章节）
- AI 摘要生成（支持多种模板：通用/投资/学习等）
- 多 LLM 配置管理（可配置最多 5 个 LLM 并切换）
- 异步任务队列（下载、转录、摘要）
- 中英文界面切换

## API 端点概览

| 模块 | 端点 | 说明 |
|------|------|------|
| Feeds | `/api/feeds` | 订阅源 CRUD、刷新、标星、收藏 |
| Episodes | `/api/episodes` | 单集列表、详情、下载、标星、已读 |
| Transcripts | `/api/transcripts` | 转录 CRUD、抓取官方字幕 |
| Summaries | `/api/summaries` | 摘要 CRUD、翻译、模板 |
| Tasks | `/api/tasks` | 任务列表、状态查询、取消 |
| Stats | `/api/stats` | 统计信息 |
| Settings | `/api/settings` | LLM 配置管理 |
| Prompt Templates | `/api/prompt-templates` | 摘要模板管理 |

详细 API 文档见 [`api.md`](./api.md)

## 数据库集合

| 集合 | 说明 |
|------|------|
| feeds | 订阅源 |
| episodes | 单集 |
| transcripts | 转录文本 |
| summaries | AI 摘要 |
| tasks | 异步任务 |
| settings | 应用设置 (LLM 配置) |
| prompt_templates | 摘要模板 |

## Episode 状态流转

```
new → downloading → downloaded → transcribing → transcribed → summarizing → summarized
                              ↓
                        官方字幕 (transcript_url)
```

## 开发进度

详见 [`plan.md`](./plan.md)
