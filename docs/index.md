# Podcast Manager - 项目文档索引

> 文档更新日期：2026-05-20

## 文档目录

| 文档 | 说明 |
|------|------|
| [PRD - 产品需求文档](./prd.md) | 产品定位、用户故事、功能规格、已知问题 |
| [前端报告](./frontend.md) | 技术栈、组件架构、视图层、状态管理、已知问题 |
| [后端报告](./backend.md) | Flask 应用架构、API 层、服务层、已知问题 |
| [数据库报告](./database.md) | MongoDB 集合设计、字段说明、索引策略 |
| [数据流转报告](./data-flow.md) | 核心业务流程、数据生命周期、时序图 |
| [API 接口文档](./api.md) | 当前后端 API、请求体、错误码、任务返回字段 |
| [当前实现状态](./implementation-status.md) | 当前模块、组件、路由、仍需关注的问题 |
| [LLM 配置 UI Demo](./llm-config-ui-demos.html) | LLM API 端点设置页的 6 种 UI 策略 |

## 快速入门

```bash
# 后端
cd backend
uv sync
uv run python run.py   # http://localhost:5000

# 前端
cd frontend
npm run dev            # http://localhost:3000
```

## 项目一句话简介

播客管理应用，核心流程：**RSS 订阅 → 音频下载 → 转录（官方字幕 / 本地 Whisper / WhisperX / AssemblyAI）→ 统一文本后处理 → AI 摘要生成（可配置模板）→ 阅读/播放**。
