# Podcast Manager

本地优先的播客处理工作台：RSS 订阅、音频下载、转录、AI 摘要和回看管理。

> English version: [README.md](./README.md)

## 快速启动

先启动后端，再启动前端。

```powershell
git clone <repo-url>
cd podcast

cd backend
Copy-Item .env.example .env
uv sync
uv run python run.py
```

`backend/run.py` 会检查 `localhost:27017` 是否已有 MongoDB。如果没有，它会尝试通过 Docker 创建或启动名为 `podcast-mongodb` 的容器，并使用 Docker volume 持久化数据。

另开一个终端：

```powershell
cd frontend
npm install
npm run dev
```

然后打开：

```text
http://localhost:3000
```

## 技术栈

| 层级 | 技术 |
| --- | --- |
| 前端 | React 18, Vite, TailwindCSS, i18next |
| 后端 | Flask, MongoDB |
| Python 环境 | uv |
| 转录 | 官方字幕、本地 faster-whisper、可选 WhisperX、可选 AssemblyAI |
| 摘要 | OpenAI-compatible LLM API |
| 任务 | ThreadPoolExecutor |

## 环境要求

- Python 3.10 到 3.13，当前后端 `.python-version` 固定为 `3.13`。
- uv 0.9+。
- Node.js 18+。
- MongoDB 监听 `27017`，或者安装 Docker Desktop 让 `backend/run.py` 自动启动 MongoDB。

## 数据库启动策略

本地开发最快方式：直接运行后端，让 `backend/run.py` 自动管理 MongoDB Docker 容器。

如果你希望手动管理数据库，可以自己启动 MongoDB：

```powershell
docker run -d --name podcast-mongodb -p 27017:27017 -v podcast-mongodb-data:/data/db mongo:latest
```

如果部署到服务器或使用外部 MongoDB，修改 `backend/.env`：

```env
MONGO_URI=mongodb://your-mongodb-host:27017
MONGO_DB=podcast
```

部署环境建议显式管理 MongoDB，不要依赖后端进程隐式创建基础设施。

## 后端

在 `backend` 目录使用 uv。不要同时激活 conda 和项目 `.venv`。

```powershell
cd backend

# 根据 pyproject.toml 创建或复用 backend/.venv
uv sync

# 运行测试
uv run pytest

# 启动 Flask API: http://localhost:5000
uv run python run.py
```

如果 uv 出现缓存权限错误，例如 `failed to open file E:\uv\...`，当前 shell 可以使用项目内缓存：

```powershell
cd backend
$env:UV_CACHE_DIR = Join-Path (Get-Location) ".uv-cache"
uv sync
```

## 前端

```powershell
cd frontend
npm install
npm run dev
```

前端开发地址：

```text
http://localhost:3000
```

Vite 会把 `/api` 请求代理到：

```text
http://localhost:5000
```

## 配置

第一次运行前复制环境变量样例：

```powershell
cd backend
Copy-Item .env.example .env
```

常用配置：

```env
MONGO_URI=mongodb://localhost:27017
MONGO_DB=podcast

AUTH_REQUIRED=0
JWT_SECRET=change-this-before-sharing

TRANSCRIPTION_DEFAULT_PROVIDER=official
TRANSCRIPTION_DEFAULT_LANGUAGE=auto
TRANSCRIPTION_AI_NORMALIZE_ENABLED=0
WHISPER_MODEL=base
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8

TRANSCRIPTION_CLOUD_ENABLED=0
ASSEMBLYAI_API_KEY=

AI_ANALYSIS_ENABLED=0
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
```

默认配置尽量保持低门槛：

- CPU 转录：`WHISPER_DEVICE=cpu`
- 云端转录关闭：`TRANSCRIPTION_CLOUD_ENABLED=0`
- AI 摘要关闭：`AI_ANALYSIS_ENABLED=0`

需要 CUDA、WhisperX、AssemblyAI 或 LLM 摘要时，再单独开启相关配置。

## 核心流程

```text
RSS 订阅 -> 单集 -> 下载音频 -> 转录 -> AI 摘要 -> 阅读/播放
```

转录 provider：

- `official`：优先使用 RSS 或站点提供的官方字幕。
- `local_whisper`：使用本地 faster-whisper，需要本地音频。
- `local_whisperx`：使用本地 WhisperX，可扩展说话人分离。
- `assemblyai`：付费云端转录，需要 `TRANSCRIPTION_CLOUD_ENABLED=1` 和 `ASSEMBLYAI_API_KEY`。
- `auto`：后端辅助模式，有官方字幕时使用官方字幕，不会自动 fallback 到付费云端。

创建转录任务时可以指定语言：

```json
{
  "provider": "local_whisper",
  "language": "zh"
}
```

所有转录保存前会做统一后处理：清理中文之间不自然的空格、清理中文标点空格，并可选使用 AI 做进一步规范化。

进入单集详情页不会自动抓取外部字幕，也不会自动开始本地或云端转录。必须用户手动点击转录操作。

## 账号与权限

后端支持 JWT Bearer 认证。本地开发默认：

```env
AUTH_REQUIRED=0
```

这样可以保持单用户开发流程足够快。此时前端会显示一个本地默认账号：

```text
local@podcast.local / admin / 本地默认用户
```

这个账号不需要注册，也不需要密码，适合本机 demo 和早期开发。

如果要给多用户使用，改成：

```env
AUTH_REQUIRED=1
JWT_SECRET=<strong-random-secret>
```

第一位注册用户会成为管理员，后续注册用户是普通用户。

也就是说：如果你清空数据库并开启 `AUTH_REQUIRED=1`，第一次在登录页点击“注册”创建的账号就是管理员账号。不是系统预置了一个隐藏管理员。

普通用户只能访问自己的：

- feeds
- episodes
- transcripts
- summaries
- tasks
- settings

已有本地数据可以迁移到默认管理员：

```powershell
cd backend
uv run python scripts/backfill_default_owner.py
```

## 本地权限测试账号

快速创建管理员和两个普通用户：

```powershell
cd backend
uv run python scripts/seed_test_users.py
```

默认创建：

```text
admin@example.com / password123
user1@example.com / password123
user2@example.com / password123
```

测试重点：

- `user1` 添加的订阅，`user2` 看不到。
- `user1` 的单集链接，`user2` 不能直接访问。
- 普通用户不能访问管理员接口。
- 管理员可以查看用户列表和系统概况。

## 前端路由

应用支持稳定路径，方便刷新、浏览器后退和复制链接：

```text
/workspace
/episodes
/episodes/<episode_id>
/feeds/<feed_id>
/favorites
/settings
```

注意：当前这些链接仍然依赖同一套后端数据和权限。公开分享链接后续应单独设计为 `/share/:token`。

## 常用命令

```powershell
# 后端
cd backend
uv sync
uv run pytest
uv run python run.py

# 前端
cd frontend
npm run build
npm run dev
```

## 常见问题

- MongoDB 没启动：确认 Docker Desktop 正在运行，或手动启动 MongoDB。
- `27017` 端口被占用：修改 `MONGO_URI` 指向可用 MongoDB。
- 前端接口失败：确认后端运行在 `http://localhost:5000`，前端 `/api` 会代理到这里。
- uv 缓存权限错误：设置 `UV_CACHE_DIR` 到项目内目录。
- 本地 Whisper 第一次慢：首次使用可能下载模型，CPU 模式最稳但速度较慢。

## 文档

- API 文档：[docs/api.md](./docs/api.md)
- 当前实现状态：[docs/implementation-status.md](./docs/implementation-status.md)
- 短期路线图：[docs/roadmap.md](./docs/roadmap.md)
