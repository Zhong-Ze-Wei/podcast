# API 接口文档

> 从 `backend/app/api/` 源码提取：14 个蓝图 88 个路由声明 + media。字段与权限以代码为准；本文档是查阅真源，不是教程。

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

## Feeds — `/api/feeds`（10 路由）

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/feeds` | 列表；筛选 `status` `is_starred` `is_favorite`；`unread_count` 按当前用户实时计算 | 登录 |
| GET | `/feeds/<id>` | 详情 | 登录 |
| POST | `/feeds` | 添加订阅，自动识别类型（RSS / YouTube 频道页 / B站空间页）；按规范化 URL 全局去重，重复返回 409 `FEED_EXISTS` | user+ |
| PUT | `/feeds/<id>` | 更新 tags/status/note | user+ |
| DELETE | `/feeds/<id>` | 删除订阅 + 关联 episodes/transcripts/summaries | user+ |
| POST | `/feeds/<id>/refresh` | 刷新（异步，按 type 三路分流） | user+ |
| POST | `/feeds/<id>/view` | 页面成功加载后自动提交 `{latest_episode_id}`，确认当前用户看过的更新版本；返回 `feed_id`、`has_unseen_updates` | 登录（含 viewer） |
| POST | `/feeds/<id>/star` | `{ "starred": bool }` | 登录 |
| POST | `/feeds/<id>/favorite` | `{ "favorite": bool }` | 登录 |
| GET | `/feeds/<id>/episodes` | 该订阅剧集列表；筛选同 episodes；`meta.latest_episode_id` 是本次加载的更新版本 | 登录 |

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
| POST | `/episodes/<id>/read` | 详情成功打开后自动提交 `{ "is_read": true }` 保存个人已读；返回状态及订阅当前用户的 `unread_count` | 登录（含 viewer） |
| POST | `/episodes/<id>/download` | 下载音频（异步，上限 500MB） | user+ |
| GET | `/episodes/<id>/stream` | 在线音频流：YouTube 剧集实时代理音频直链（透传 Range，不落盘）；RSS 剧集 302 到原地址。**令牌走 query：`?token=`** | 登录（含 viewer） |

`GET /episodes` 与 `GET /feeds/<id>/episodes` 共用后端查询：`q` 搜索标题与简述，`sort` 为 `published_desc`（默认）/`published_asc`/`title_asc`，同值按 `_id` 稳定排序。`processed=true` 选已有音频、文稿或摘要的加工结果；可进一步筛选 `has_local_audio`、`has_transcript`、`has_summary`、个人已读和加星状态。列表省略大字段 `content`，完整内容从详情读取。

`days=N` 按节目发布时间查询最近 N × 24 小时（1–3650 天，排除未来和缺日期的节目），先筛选后分页。最近更新页默认 7 天，可叠加搜索、排序及 `is_read=true/false`。`has_transcript_or_summary=true` 是工作台“转录”分类的条件：文稿和摘要节目都包含；“摘要”分类仍只用 `has_summary=true`。单集已读状态保存在 `user_episode_states`，按用户隔离，成功打开详情后自动记录。

订阅旁的紫点表示“这个订阅有新入库的节目，当前用户还没有进去查看”，使用 `has_unseen_updates`，与单集未读数量无关。点击订阅后，只有当前页面的列表成功加载才提交 `/view`；失败、离开页面后的迟到响应、后台订阅查询不会记录查看。个人更新版本保存在 `user_feed_states`，用入库 ObjectId 比较，补录旧节目也会重新亮点。确认使用加载时的版本，更新记录只前进，避免加载期间新入库的内容被误清除。界面不提供手工标记按钮，也不显示新增数量。

节目响应包含 `artifacts`（local_audio/transcript/summary）、`active_tasks`、`actions`（download/transcribe/summarize 的 allowed/reason_code）和 `transcription_providers`（id/available/reason_code/download_required）。能力由后端根据角色、实际产物、任务与配置计算；POST 时重新校验。`local_audio_url` 只在持久目录内存在可用音频时返回。

## Transcripts — `/api/transcripts`（6 路由）

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/transcripts/<episode_id>` | 获取转录 | 登录 |
| POST | `/transcripts/<episode_id>` | 创建转录任务（异步） | user+ |
| DELETE | `/transcripts/<episode_id>` | 删除转录 | user+ |
| POST | `/transcripts/<episode_id>/fetch` | 从 transcript_url 拉取外部转录 | user+ |
| GET | `/transcripts/<episode_id>/check-external` | 检查外部转录源 | 登录 |
| POST | `/transcripts/<episode_id>/fetch-video-audio` | **"立即转写"**：下载视频音频 → WhisperX 本地转写（异步；纯音乐等无人声结果会清空转录并打 no_speech 标记）。组件未装时 400 `LOCAL_AI_NOT_INSTALLED` | user+ |

```json
// POST /transcripts/<episode_id>
{ "provider": "auto|official|local_whisper|local_whisperx|assemblyai", "language": "auto", "download_if_needed": true }
→ 200 { "data": { "task_id": "...", "provider": "...", "language": "..." } }
```

`download_if_needed` 须为布尔值；为true时后端同一任务同步下载、转录、保存，返回的task_id跟踪整条管线。已有音频复用，下载失败不进入转录，转录失败保留已下载音频；前端不编排两个任务。

## Summaries — `/api/summaries`（5 路由）

| 方法 | 路径 | 说明 | 权限 |
|------|------|------|------|
| GET | `/summaries/<episode_id>` | 获取摘要 | 登录 |
| POST | `/summaries/<episode_id>` | 生成摘要（异步，模板+参数；AI 冻结时 423） | user+ |
| POST | `/summaries/<episode_id>/translate` | 翻译为中文（异步） | user+ |
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
| GET | `/tasks` | 分页任务列表；筛选 `status` `type` `episode_id` `feed_id` `period_type` `period_start` | 登录 |
| GET | `/tasks/<id>` | 任务详情（含 episode/feed 标题元数据） | 登录 |
| POST | `/tasks/<id>/cancel` | 真实取消本进程排队任务；重复取消幂等，运行中返回CANNOT_CANCEL | user+，提交者 |

```json
// Task 结构
{
  "id": "uuid", "type": "download|transcribe|summarize|translate|refresh",
  "status": "pending|processing|completed|failed|cancelled", "can_cancel": false,
  "report_period": { "type": "month", "start": "2026-10-01" },
  "report_context": { "kind": "modes", "mode": "all" },
  "progress": 42, "progress_message": "硅谷101 · 拉取字幕 2/25",
  "result": {}, "error_message": null,
  "episode_id": "...", "episode_title": "...", "feed_id": "...", "feed_title": "..."
}
```

completed 任务 7 天 TTL 自动清理；后端重启会把孤儿 running 任务标记为"请重试"。

共享内容任务全员可读，briefing-report/briefing-lab仅本人可读，数据库回退读取也验证归属。`can_cancel` 结合真实Future、请求角色与提交者；写接口再次校验，不能以展示能力代替权限判断。

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

## 内容报告 — `/api/briefing-reports`

前端 `/briefing` 使用五种不同内容模式，视觉风格独立切换，单篇解读仍留在AI模式；左侧导航保持原样。读取不触发 LLM，生成复用已校验的全文阅读与抽取记录。旧分类报告和原话精选接口保留兼容。

| 方法 | 路径 | 作用 | 权限 |
| --- | --- | --- | --- |
| GET | `/briefing-reports/modes` | 五种模式的已保存报告、实际提示词模板、输入说明与材料；读取不调用模型 | 登录 |
| POST | `/briefing-reports/modes/generate` | 初筛→共享单篇分析→生成当前/全部模式，返回 task_id；尊重AI总开关 | user+ |
| GET | `/briefing-reports/preferences` | 当前账号的关注话题与自动周报／月报设置；首次读取只返回默认值 | 登录 |
| PUT | `/briefing-reports/preferences` | 保存关注话题、启用状态、自动报告周期与阅读layout白名单 | 登录 |
| GET | `/briefing-reports/reports` | 完整报告历史分页；可筛选period_type/period_start/mode，不重新生成 | 登录 |
| GET | `/briefing-reports/reports/<report_id>` | 读取可见的不可变报告正文 | 登录 |
| GET | `/briefing-reports/favorites` | 当前用户跨周期收藏快照分页，可选周期/模式筛选 | 登录 |
| PUT | `/briefing-reports/favorites/<item_id>` | `{report_id}`：后端提取可信条目快照，重复收藏幂等 | user+ |
| DELETE | `/briefing-reports/favorites/<item_id>` | 取消自己的条目收藏，幂等 | user+ |
| POST | `/briefing-reports/favorites/import` | `{ids:[...]}`：最多500个旧ID，返回imported与unresolved；歧义不会误迁移 | user+ |
| GET | `/briefing-reports/sources/<source_id>` | 完整文稿、字幕与已有分析，支持稳定节目编号及旧快照编号 | 登录 |
| GET | `/briefing-reports/reading-theme.css` | 网页与PDF共用的纸面／报刊阅读主题，不包含账号数据 | 公开 |
| GET | `/briefing-reports/edition` | 最近可见的原话精选与材料元信息，不调用模型 | 登录 |
| POST | `/briefing-reports/edition/generate` | 按可选主题生成少量精选；返回 task_id | 登录 |
| GET | `/briefing-reports/reading/<source_id>` | 已保存单篇解读、真实材料、已有候选 | 登录 |
| POST | `/briefing-reports/reading/<source_id>/generate` | 按需生成或复用这期全文解读，返回 task_id | user+ |
| GET | `/briefing-reports` | 材料、抽取覆盖、本人及共享报告、检索配置状态 | 登录 |
| POST | `/briefing-reports/generate` | 提交生成任务，返回 202 与 task_id；尊重 AI 总开关 | 登录 |
| GET | `/briefing-reports/tasks/<task_id>` | 本人的报告任务状态、进度和结果 | 登录 |
| GET | `/briefing-reports/reports/<report_id>/html?pages=all&style=paper&density=comfortable` | 完整内容预览；style支持paper/newspaper/legacy，density支持comfortable/compact | 登录 |
| GET | `/briefing-reports/reports/<report_id>/pdf?pages=all&style=newspaper&density=compact` | 默认完整自动分页PDF，保留pages=1/2精选兼容 | 登录 |

生成请求：`{variant: "all" | "overview" | "episodes" | "concepts" | "quotes" | "resources", topic: "可选关键词，最多120字", interests: ["concepts", "quotes", "resources", "backgrounds"], web_enabled: false}`。关注项至少一项；同账号已有报告任务未结束时返回 409。

当前模式读取使用 `?period_type=week|month&period_start=YYYY-MM-DD`。按香港自然周／月的节目发布时间取材，按规范化订阅身份和guid去重（标准视频编号可跨同内容订阅识别）；不同RSS的相同guid不合并。响应包含 `period`、日期列表 `periods`、全部材料 `materials`、账号 `preferences` 与五种 `reports`。`total_count` 为总节目数，`transcript_count` 为实际有正文的数量；`selected_count` 在完整正文筛选完成前为null。无对应范围的报告时返回null，不借用其他日期结果。无周期参数的旧GET继续读取固定十篇对照样本。

模式生成请求为 `{mode: "core" | "quotes" | "connections" | "concepts" | "resources" | "all", period_type: "week" | "month", period_start: "YYYY-MM-DD", interests: ["AI", "AI如何改变团队分工"], topic: "可选主题，最多120字"}`。interests中每项最多200字，省略时使用账号启用的关注问题；空列表不限制题材，但仍规避纯广告。标题与已有简介每20期一批初筛，不确定时保留；入选且有正文的节目逐篇完整分析，再使用单篇摘要与证据生成五种内容模式。报告按账号、周期、关注组合、正文与分析版本隔离，位于 `content-modes-v1/reports`。返回 `reports` 映射，report.id可导出HTML/PDF；阅读风格只影响展示，不触发分析。

偏好PUT为 `{interests: [{label: "AI", enabled: true}], auto_period: null | "week" | "month", layout: "paper"}`；最多12个不重复话题，名称1–30字，省略字段保留原值。layout限定为space/large/list/columns/paper/newspaper/notes。自动报告从启用后的周期开始，香港时间周一／月初00:05后检查最近结束周期，按最新关注生成五种模式。同周期已有完整结果不重复调用；自动任务持久去重，失败间隔一小时、最多三次，人工生成入口仍可重试。关闭账号自动生成或全局AI开关会阻止新工作；服务重启后补最近符合条件的已结束周期，不批量补历史。后台服务必须运行，运行记录在 `briefing_auto_runs`，生成过程使用既有 `briefing-report` 队列。

单篇生成可携带 `{period_type,period_start}`，后端验证来源真实发布时间落入该自然周期后才登记任务周期；不信任浏览器为来源贴的周期标签。省略周期保留旧接口行为。手动与自动任务登记 `report_context.kind`（modes/reading/edition/legacy），reading含source_id，modes含mode，供页面刷新后恢复正确任务。

动态来源编号为 `ep` 加节目ObjectId，单篇与文稿接口仍支持旧Sxx编号。旧单篇解读仅在guid和完整正文逐字一致时复用，并在响应中重新绑定当前节目编号，不覆盖旧文稿。

实际节目使用稳定 `ep<episode_id>` 来源编号。单篇响应 `reading` 含takeaway、1–12条points（回答/条件/原话依据）、quotes、concepts、resources、topics及analysis_key/version；未生成时为null。单篇与周/月共享 `episode-analysis/<key>.json`，按正文hash、prompt/schema版本与模型配置缓存，不受周期或兴趣影响。引用保留offset，start/end可以为空。旧片段结果单独放在legacy_reading，不能当新缓存使用。modes快照的episode_analysis显示已分析数量，materials.analysis_status显示逐篇状态；报告analysis记录总数、完成/复用/新分析数及failed_episodes。

兼容的精选请求仍只有 `{topic: "可选主题，最多120字"}`，edition返回原话与跨篇AI归纳，保留 `reading-v1/editions`、旧Sxx的 `reading-v1/sources`。个人报告和任务按owner隔离；共享全文缓存须通过可见节目来源访问。生成失败不替换成功缓存。

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
