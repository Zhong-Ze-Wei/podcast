# API 接口文档

> 从 `backend/app/api/` 源码提取：12 个蓝图 64 个路由 + media。字段与权限以代码为准；本文档是查阅真源，不是教程。

## 通用约定

**Base URL**: `http://localhost:5000/api`

**认证**: `Authorization: Bearer <JWT>`（有效期默认 168 小时，`JWT_EXPIRES_HOURS` 可改）。例外：`/episodes/<id>/stream` 供 `<audio>` 标签使用，无法带请求头，令牌从 query 参数取：`?token=<JWT>`。

**角色**: `admin` > `user` > `viewer`。注册默认 `pending`，需 admin 批准才能登录（403 `ACCOUNT_PENDING`）。首个注册用户自动 `admin`。

**响应格式**:

```json
{ "success": true,  "data": { ... }, "message": "..." }
{ "success": false, "data": null, "message": "错误信息", "error_code": "ERROR_CODE" }
```

**分页**: GET 列表端点支持 `page`（默认 1）/ `per_page`（默认 20）。

**任务型端点**（刷新/下载/转写/摘要/翻译）均为异步：立即返回 `task_id`，进度查 `/tasks`，`progress_message` 为人话进度（"频道名 · 拉取字幕 2/25"）。

---

## Auth — `/api/auth`（3 路由）

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/auth/register` | 注册；返回的用户 status=pending | 公开 |
| POST | `/auth/login` | 登录；pending/disabled 拒绝（403） | 公开 |
| GET | `/auth/me` | 当前用户信息（含 role） | 登录 |

```json
// POST /auth/register
{ "email": "user@example.com", "password": "至少8位" }
→ 201 { "data": { "user": {...}, "token": "jwt..." } }
```

## Admin — `/api/admin`（4 路由，全部 admin）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/admin/users` | 用户列表（含 pending） |
| PATCH | `/admin/users/<id>` | 更新 status: `pending/active/disabled`、role: `admin/user/viewer` |
| GET | `/admin/tasks` | 按状态统计任务数 |
| GET | `/admin/health` | MongoDB 状态 + 集合计数 |

## Feeds — `/api/feeds`（9 路由）

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/feeds` | 列表；筛选 `status` `is_starred` `is_favorite`；`unread_count` 按当前用户实时计算 | 登录 |
| GET | `/feeds/<id>` | 详情 | 登录 |
| POST | `/feeds` | 添加订阅，自动识别类型（RSS / YouTube 频道页 / B站空间页）；按规范化 URL 全局去重，重复返回 409 `FEED_EXISTS` | user+ |
| PUT | `/feeds/<id>` | 更新 tags/status/note | user+ |
| DELETE | `/feeds/<id>` | 删除订阅 + 关联 episodes/transcripts/summaries | user+ |
| POST | `/feeds/<id>/refresh` | 刷新（异步，按 type 三路分流） | user+ |
| POST | `/feeds/<id>/star` | `{ "starred": bool }` | 登录 |
| POST | `/feeds/<id>/favorite` | `{ "favorite": bool }` | 登录 |
| GET | `/feeds/<id>/episodes` | 该订阅剧集列表；筛选同 episodes | 登录 |

```json
// POST /feeds —— 三种地址等价支持
{ "rss_url": "https://lexfridman.com/feed/podcast/" }
{ "rss_url": "https://www.youtube.com/@DwarkeshPatel" }
{ "rss_url": "https://space.bilibili.com/508452265" }
→ 201 { "data": { "feed": { "type": "youtube|bilibili|rss", ... } } }
```

## Episodes — `/api/episodes`（7 路由）

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/episodes` | 全局列表；筛选 `status`（逗号分隔多值）`is_read` `is_starred` `feed_id` `has_transcript` `has_summary`；is_read/is_starred 按当前用户的个人状态过滤 | 登录 |
| GET | `/episodes/<id>` | 详情（含 feed_title；个人状态已合并进响应） | 登录 |
| PUT | `/episodes/<id>` | 写个人状态 `{is_read, is_starred, play_position}`（存 user_episode_states，不影响他人） | user+ |
| POST | `/episodes/<id>/star` | 切换加星（个人） | user+ |
| POST | `/episodes/<id>/read` | 切换已读（个人） | user+ |
| POST | `/episodes/<id>/download` | 下载音频（异步，上限 500MB） | 登录 |
| GET | `/episodes/<id>/stream` | 在线音频流：YouTube 剧集实时代理音频直链（透传 Range，不落盘）；RSS 剧集 302 到原地址。**令牌走 query：`?token=`** | 登录（含 viewer） |

## Transcripts — `/api/transcripts`（6 路由）

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/transcripts/<episode_id>` | 获取转录 | 登录 |
| POST | `/transcripts/<episode_id>` | 创建转录任务（异步） | 登录 |
| DELETE | `/transcripts/<episode_id>` | 删除转录 | 登录 |
| POST | `/transcripts/<episode_id>/fetch` | 从 transcript_url 拉取外部转录 | 登录 |
| GET | `/transcripts/<episode_id>/check-external` | 检查外部转录源 | 登录 |
| POST | `/transcripts/<episode_id>/fetch-video-audio` | **"立即转写"**：下载视频音频 → WhisperX 本地转写（异步；纯音乐等无人声结果会清空转录并打 no_speech 标记）。组件未装时 400 `LOCAL_AI_NOT_INSTALLED` | user+ |

```json
// POST /transcripts/<episode_id>
{ "provider": "auto|official|local_whisper|local_whisperx|assemblyai", "language": "auto" }
→ 200 { "data": { "task_id": "...", "provider": "...", "language": "..." } }
```

## Summaries — `/api/summaries`（5 路由）

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/summaries/<episode_id>` | 获取摘要 | 登录 |
| POST | `/summaries/<episode_id>` | 生成摘要（异步，模板+参数；AI 冻结时 423） | 登录 |
| POST | `/summaries/<episode_id>/translate` | 翻译为中文（异步） | 登录 |
| DELETE | `/summaries/<episode_id>` | 删除摘要 | user+ |
| GET | `/summaries/templates` | 可用模板列表 | 登录 |

```json
// POST /summaries/<episode_id>
{
  "template_name": "learning",
  "enabled_blocks": ["key_points", "quotes"],
  "params": { "length": "long", "language": "zh" },
  "force": false
}
```

## Tasks — `/api/tasks`（3 路由）

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/tasks` | 任务列表；筛选 `status` `type` `episode_id` `feed_id` | 登录 |
| GET | `/tasks/<id>` | 任务详情（含 episode/feed 标题元数据） | 登录 |
| POST | `/tasks/<id>/cancel` | 取消 pending 任务 | 登录 |

```json
// Task 结构
{
  "id": "uuid", "type": "download|transcribe|summarize|translate|refresh",
  "status": "pending|processing|completed|failed",
  "progress": 42, "progress_message": "硅谷101 · 拉取字幕 2/25",
  "result": {}, "error_message": null,
  "episode_id": "...", "episode_title": "...", "feed_id": "...", "feed_title": "..."
}
```

completed 任务 7 天 TTL 自动清理；后端重启会把孤儿 running 任务标记为"请重试"。

## Settings — `/api/settings`（13 路由）

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET / PUT | `/settings/llm` | 全局 LLM 配置（providers + models + routes） | admin |
| PUT | `/settings/llm/active` | 旧版活动配置切换 | admin |
| POST | `/settings/llm/test` | 测试连接（body 传待测配置） | admin |
| POST | `/settings/llm/fetch-models` | 从服务商拉取模型列表 | admin |
| GET / PUT | `/settings/tavily` | Tavily 搜索配置 | admin |
| POST | `/settings/tavily/test` | 测试 Tavily | admin |
| GET / PUT | `/settings/prompts/search-query` | 自定义搜索片段 | admin |
| GET / PUT | `/settings/ai-analysis` | AI 功能总开关 `{enabled}` | admin |
| GET | `/settings/bilibili-status` | B站登录态（实时校验 SESSDATA 有效性） | 登录 |

```json
// GET /settings/llm
{
  "providers": [{ "id": "...", "name": "...", "api_format": "openai_compatible|anthropic_messages",
                  "base_url": "...", "has_api_key": true, "enabled": true }],
  "models": [{ "id": "...", "provider_id": "...", "model": "...", "enabled": true }],
  "default_model_id": "...",
  "task_routes": { "summary": "model-id", "briefing": "model-id", "transcript_normalize": "model-id" }
}
```

`api_key` 读时始终为空，以 `has_api_key` 标记；写入空值不覆盖已有密钥。

## Prompt Templates — `/api/prompt-templates`（9 路由）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/prompt-templates/` | 列出模板（无尾斜杠同样命中，strict_slashes 关闭） |
| GET / PUT | `/prompt-templates/<id>` | 详情 / 更新（系统模板不可改） |
| POST | `/prompt-templates/` | 创建 |
| POST | `/prompt-templates/<id>/duplicate` | 复制 |
| DELETE | `/prompt-templates/<id>` | 删除（系统模板不可删） |
| GET | `/prompt-templates/<id>/blocks` | 可选块 |
| GET | `/prompt-templates/<id>/parameters` | 参数定义 |
| POST | `/prompt-templates/init` | 初始化系统模板（幂等） |

## Insights — `/api/insights`（3 路由）

三端点均需登录，支持 `strategy`（默认 `summary`：摘要聚合 / `transcript` 文稿直析 / `metadata` 元数据雷达）与 `days`（时间窗口 1-30，默认 7）参数。缓存按 `date + strategy + days` 独立。

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/insights/briefing` | 今日简报（无缓存自动生成） | 登录 |
| POST | `/insights/briefing` | 强制重新生成 | 登录 |
| GET | `/insights/briefing/count` | 窗口内剧集统计（滑块预览用）：`{total, with_transcript, with_summary}`，零 LLM | 登录 |
| GET | `/insights/briefing/export` | 导出 PDF | 登录 |

## 内容报告 — `/api/briefing-reports`（11 路由）

前端 `/briefing` 使用五种不同内容模式，视觉风格独立切换，单篇解读仍留在AI模式；左侧导航保持原样。读取不触发 LLM，生成复用已校验的全文阅读与抽取记录。旧分类报告和原话精选接口保留兼容。

| 方法 | 路径 | 作用 | 权限 |
| --- | --- | --- | --- |
| GET | `/briefing-reports/modes` | 五种模式的已保存报告、实际提示词模板、输入说明与材料；读取不调用模型 | 登录 |
| POST | `/briefing-reports/modes/generate` | 生成当前模式或全部模式，返回 task_id；尊重AI总开关 | 登录 |
| GET | `/briefing-reports/edition` | 最近可见的原话精选与材料元信息，不调用模型 | 登录 |
| POST | `/briefing-reports/edition/generate` | 按可选主题生成少量精选；返回 task_id | 登录 |
| GET | `/briefing-reports/reading/<source_id>` | 已保存单篇解读、真实材料、已有候选 | 登录 |
| POST | `/briefing-reports/reading/<source_id>/generate` | 按需生成这期的短解读，返回 task_id | 登录 |
| GET | `/briefing-reports` | 材料、抽取覆盖、本人及共享报告、检索配置状态 | 登录 |
| POST | `/briefing-reports/generate` | 提交生成任务，返回 202 与 task_id；尊重 AI 总开关 | 登录 |
| GET | `/briefing-reports/tasks/<task_id>` | 本人的报告任务状态、进度和结果 | 登录 |
| GET | `/briefing-reports/reports/<report_id>/html?pages=1` | 固定版式预览；pages 只允许 1 或 2 | 登录 |
| GET | `/briefing-reports/reports/<report_id>/pdf?pages=2` | 下载与预览一致的一／两页 PDF | 登录 |

生成请求：`{variant: "all" | "overview" | "episodes" | "concepts" | "quotes" | "resources", topic: "可选关键词，最多120字", interests: ["concepts", "quotes", "resources", "backgrounds"], web_enabled: false}`。关注项至少一项；同账号已有报告任务未结束时返回 409。

模式生成请求为 `{mode: "core" | "quotes" | "connections" | "concepts" | "resources" | "all", topic: "可选主题，最多120字"}`。五种模式分别对应核心提要、原话精选、共性与分歧、新词与方法、提到的资料；使用独立生成模板与缓存，缓存位于 `content-modes-v1/reports`。GET 可用 `?topic=` 精确读取该生成主题的已保存结果；默认返回各模式最近可见结果。风格和即时标签筛选只属于前端，不改变取材与模型调用。生成完成的任务结果为 `reports` 映射，每份report.id均可通过上述HTML/PDF端点导出。

兼容的精选请求仍只有 `{topic: "可选主题，最多120字"}`。响应 `edition` 包含已定位的精选原话和最多两条有两篇以上证据的AI归纳；同一份 edition.id 可直接走上述HTML/PDF导出。单篇响应 `reading` 包含一句takeaway、最多三条points及真实提及资料，未生成时为null。个人结果与任务按owner隔离，公共CLI结果可共享；单篇与旧精选缓存位于 `reading-v1/editions` 和 `reading-v1/sources`。生成失败不替换旧缓存。

报告与任务按 owner 隔离，共享 CLI 报告可读取；报告绑定材料指纹。报告存在本机 `backend/.runtime/briefing-reports/`，抽取缓存按正文指纹复用并重新绑定节目。导出失效报告返回 404，页数无效返回 400；Chrome 启动／排版失败返回 503 `REPORT_EXPORT_FAILED`。正文内的网页内容和来源按字段转义，模型不生成 HTML/CSS。

PDF 的应用内链接取当前前端访问来源，形如 `/episodes/<id>?t=<seconds>`，同时保留可用的公开原节目／资料链接。`web_mode` 明确区分实时检索、已有资料、关闭与无结果。具体边界见 [内容报告](./briefing-reports.md)。

## Briefing Lab — `/api/briefing-lab`（4 路由，保留兼容）

正文简报实验页使用固定材料快照。读取不会触发 LLM；五种策略为 `daily`、`focus`、`debate`、`actions`、`research`。

| 方法 | 路径 | 说明 | 权限 |
| --- | --- | --- | --- |
| GET | `/briefing-lab` | 材料元信息、实际覆盖、诊断、当前用户结果及共享实验结果 | 登录 |
| GET | `/briefing-lab/sources/<source_id>` | 当前材料的完整原文、字幕段、逐篇分析 | 登录 |
| POST | `/briefing-lab/run` | 异步提交分析，返回 202 和 task_id；尊重全局 AI 开关 | 登录 |
| GET | `/briefing-lab/tasks/<task_id>` | 本人的任务状态、进度、错误及结果 | 登录 |

生成参数：`{strategy, focus, web_enabled}`；focus 默认“Agent开发与产品落地”，最多1000字，web_enabled 为布尔值。已有个人任务运行时返回409；正文材料尚未采集时返回409；AI冻结时返回423。

`web_mode` 区分 `disabled`、`live_search`、`saved_primary_source_notes`、`unavailable`。正文及运行结果保存在本机 `backend/.runtime/briefing-lab/`；结果绑定内容指纹，个人问题结果按 owner 隔离，公共实验结果共享。响应中的 `run.usage` 只计该版综合；`analysis.usage` 为已缓存全文阅读记录。

## Video Import — `/api/video-import`（1 路由）

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| POST | `/video-import/youtube` | 单个 YouTube 视频 URL 直接导入（建 feed + episode + transcript） | 登录 |

## Stats — `/api`（1 路由）

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/stats` | 统计：feeds / episodes（未读按当前用户计）/ tasks | 登录 |

## Media（非蓝图，app/__init__.py 注册）

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/api/media/<path:filename>` | 本地音频/图片文件，7 天浏览器缓存 |
