# 快速启动

> 从 `pyproject.toml`、`package.json`、`config.py` 源码提取。

---

## 环境要求

- Python 3.10–3.13
- Node.js 18+
- MongoDB 6+
- (可选) NVIDIA GPU + CUDA 12.8 用于本地转录

---

## 后端

```bash
cd backend

# 安装依赖 (使用 uv)
uv sync

# 配置环境变量
cp .env.example .env
# 编辑 .env，填入:
#   MONGO_URI=mongodb://localhost:27017/podcast
#   JWT_SECRET=你的密钥
#   LLM_API_KEY=你的 AI API 密钥 (可选，也可在界面配置)

# 启动
uv run python run.py
# → http://localhost:5000
```

## 前端

```bash
cd frontend

# 安装依赖
npm install

# 开发模式
npm run dev
# → http://localhost:3000 (代理到后端 5000)

# 构建
npm run build
```

---

## 配置变量

| 变量 | 默认值 | 说明 |
|------|--------|------|
| `MONGO_URI` | `mongodb://localhost:27017/podcast` | MongoDB 连接 |
| `JWT_SECRET` | — | JWT 签名密钥 (必填) |
| `SECRET_KEY` | — | `JWT_SECRET` 的降级回退 |
| `MEDIA_ROOT` | `./media` | 音频文件存储目录 |
| `LLM_BASE_URL` | `https://api-inference.modelscope.cn/v1` | 默认 LLM 端点 |
| `LLM_API_KEY` | `""` | 默认 LLM 密钥 |
| `LLM_MODEL` | `deepseek-ai/DeepSeek-V4-Flash` | 默认模型 |
| `AI_ANALYSIS_ENABLED` | `true` | AI 功能总开关 |

> LLM 配置优先使用界面配置 (存 MongoDB)，环境变量仅作兜底。

---

## 首次使用

1. 启动后端 + 前端
2. 打开 `http://localhost:3000`
3. 注册账号 (首个用户自动成为 admin)
4. 在设置页面配置 AI 服务商和 API Key
5. 添加 RSS 订阅源
6. 下载单集 → 转录 → AI 摘要

---

## 测试

```bash
cd backend
uv run pytest tests/ -v           # 全部测试
uv run pytest tests/test_feeds_api.py -v  # 单个模块
```

---

## 关键依赖

### 后端

| 包 | 用途 |
|----|------|
| Flask | Web 框架 |
| pymongo | MongoDB |
| openai | OpenAI 兼容 API |
| feedparser | RSS 解析 |
| faster-whisper | 本地转录 |
| whisperx | 高级本地转录 |
| assemblyai | 云端转录 |
| weasyprint | PDF 导出 |
| tavily-python | Web 搜索 |

### 前端

| 包 | 用途 |
|----|------|
| react | UI |
| axios | HTTP |
| tailwindcss | 样式 |
| lucide-react | 图标 |
| i18next | 国际化 |
