# Podcast Manager - 当前实现状态

> 从根目录 `plan.md` 迁移并重写，更新于 2026-05-20。

## 后端

| 模块 | 文件 | 状态 |
| --- | --- | --- |
| Feeds API | `backend/app/api/feeds.py` | 已实现 |
| Episodes API | `backend/app/api/episodes.py` | 已实现 |
| Transcripts API | `backend/app/api/transcripts.py` | 已实现，支持官方字幕、本地 Whisper、WhisperX、AssemblyAI |
| Summaries API | `backend/app/api/summaries.py` | 已实现，基于模板引擎 |
| Tasks API | `backend/app/api/tasks.py` | 已实现，支持任务历史目标信息 |
| Settings API | `backend/app/api/settings.py` | 已实现，包含 LLM/Tavily 配置 |
| Prompt Templates API | `backend/app/api/prompt_templates.py` | 已实现 |
| Insights API | `backend/app/api/insights.py` | 已实现，含简报和 PDF 导出 |

## 服务层

| 服务 | 文件 | 说明 |
| --- | --- | --- |
| RSS Service | `services/rss_service.py` | RSS 解析、Feed 元数据、字幕 URL 提取 |
| Task Queue | `services/task_queue.py` | 线程池异步任务，支持重启后恢复中断任务 |
| Transcript Fetcher | `services/transcript_fetcher.py` | 官方/外部字幕抓取与解析 |
| Whisper Service | `services/whisper_service.py` | 本地 faster-whisper 转录 |
| WhisperX Service | `services/whisperx_service.py` | 可选 WhisperX 转录与说话人分离扩展 |
| Transcript Postprocessor | `services/transcript_postprocessor.py` | 转录文本统一后处理，清理中文空格，可选 AI 规范化 |
| Summary Service | `services/summary_service.py` | 摘要生成、摘要翻译 facade |
| LLM Client | `services/llm_client.py` | OpenAI-compatible LLM 客户端 |
| Briefing Service | `services/briefing_service.py` | 聚合近期单集并生成简报 |

## 数据模型

| 模型 | 文件 | 说明 |
| --- | --- | --- |
| Feed | `models/feed.py` | 订阅源 |
| Episode | `models/episode.py` | 单集、音频状态、处理状态 |
| Transcript | `models/transcript.py` | 转录文本、分段、来源、后处理元信息 |
| Summary | `models/summary.py` | 模板化摘要 |
| Task | `models/task.py` | 异步任务记录 |
| Setting | `models/setting.py` | LLM/Tavily 等配置 |
| Prompt Template | `models/prompt_template.py` | 摘要模板 |

## 前端

| 组件 | 文件 | 状态 |
| --- | --- | --- |
| App | `frontend/src/App.jsx` | 管理主状态，支持 `/episodes/:id`、`/feeds/:id` 等深链接 |
| Sidebar | `components/layout/Sidebar.jsx` | 侧边栏导航、订阅列表 |
| WorkspaceView | `components/views/WorkspaceView.jsx` | 工作台，展示下载/转录/摘要相关单集 |
| FeedDetailView | `components/views/FeedDetailView.jsx` | 订阅详情 |
| EpisodeDetailView | `components/views/EpisodeDetailView.jsx` | 单集详情、转录、摘要 |
| FavoritesView | `components/views/FavoritesView.jsx` | 标星单集 |
| SettingsView | `components/views/SettingsView.jsx` | 设置页，承载 LLM、模板、应用设置 |
| LlmConfigPanel | `components/views/settings/LlmConfigPanel.jsx` | LLM OpenAI-compatible endpoint 配置 |
| AppSettingsPanel | `components/views/settings/AppSettingsPanel.jsx` | 自动刷新、任务面板、历史窗口等偏好 |
| PromptTemplatesPanel | `components/views/settings/PromptTemplatesPanel.jsx` | 模板管理 |
| TaskPanel | `components/tasks/TaskPanel.jsx` | 右下角浮动任务中心，支持历史和跳转 |
| ViewToolbar | `components/common/ViewToolbar.jsx` | 列表视图统一 sticky 工具条 |

## 路由与链接

当前前端没有引入 React Router，而是使用浏览器 History API 做低成本深链接：

```text
/workspace
/episodes
/episodes/:episodeId
/feeds/:feedId
/favorites
/settings
```

这些路径支持刷新、复制链接和浏览器后退。

## 仍需关注

- LLM API Key 目前在 MongoDB 明文保存；上线前应迁移到环境变量、加密存储或 secret manager。
- 公开分享链接还未实现；当前深链接仍假设访问者拥有同一套本地数据。
- 多用户隔离未实现；如果后续上线，需要引入用户身份和 `owner_id` 数据隔离。
- 摘要 block 级别选择已有部分状态逻辑，但 UI 还可以继续完善。
- 导出能力还不完整，摘要/转录面向用户的导出入口仍可加强。
