# API 接口文档

> 从 `backend/app/api/` 源码自动提取，共 58 个路由，12 个蓝图。

---

## 通用

**Base URL**: `http://localhost:5000/api`

**认证**: 大部分端点需要 `Authorization: Bearer <JWT>` header。

**响应格式**:
```json
{ "success": true, "data": { ... } }
{ "success": false, "error": "错误信息" }
```

**分页参数** (GET 列表端点): `page` (默认 1), `per_page` (默认 20)

---

## Auth — `/api/auth`

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| POST | `/auth/register` | 注册。首个用户自动 admin | 无 |
| POST | `/auth/login` | 登录，返回 JWT | 无 |
| GET | `/auth/me` | 获取当前用户信息 | 需要 |

### POST /auth/register
```json
{ "email": "user@example.com", "password": "至少8位", "username": "可选" }
→ 201 { "data": { "user": {...}, "token": "jwt..." } }
```

### POST /auth/login
```json
{ "email": "user@example.com", "password": "密码" }
→ 200 { "data": { "user": {...}, "token": "jwt..." } }
```

---

## Admin — `/api/admin`

| 方法 | 路径 | 说明 | 认证 |
|------|------|------|------|
| GET | `/admin/users` | 列出所有用户 | admin |
| PATCH | `/admin/users/<id>` | 更新用户 status/role | admin |
| GET | `/admin/tasks` | 按状态统计任务数 | admin |
| GET | `/admin/health` | 健康检查 (MongoDB + 集合计数) | admin |

### PATCH /admin/users/<id>
```json
{ "status": "active|disabled", "role": "user|admin" }
```

---

## Feeds — `/api/feeds`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/feeds` | 列表。筛选: `status`, `is_starred`, `is_favorite` |
| GET | `/feeds/<id>` | 单个详情 |
| POST | `/feeds` | 添加 RSS 订阅。自动解析 + 创建 episodes |
| PUT | `/feeds/<id>` | 更新 tags/status/note |
| DELETE | `/feeds/<id>` | 删除 feed + 关联 episodes/transcripts/summaries |
| POST | `/feeds/<id>/refresh` | 刷新 RSS (异步任务) |
| POST | `/feeds/<id>/star` | 切换星标。body: `{ "starred": bool }` |
| POST | `/feeds/<id>/favorite` | 切换收藏。body: `{ "favorite": bool }` |
| GET | `/feeds/<id>/episodes` | 该 feed 下的 episodes |

### POST /feeds
```json
{ "rss_url": "https://example.com/feed.xml", "tags": ["tech"] }
→ 201 { "data": { "feed": {...}, "message": "..." } }
```

---

## Episodes — `/api/episodes`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/episodes` | 全局列表。筛选: `status`, `is_read`, `is_starred`, `feed_id`, `has_transcript`, `has_summary` |
| GET | `/episodes/<id>` | 单个详情 (含 feed_title) |
| PUT | `/episodes/<id>` | 更新 is_read/is_starred/play_position |
| POST | `/episodes/<id>/star` | 切换星标 |
| POST | `/episodes/<id>/read` | 切换已读 |
| POST | `/episodes/<id>/download` | 下载音频 (异步, 最大 500MB) |

---

## Transcripts — `/api/transcripts`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/transcripts/<episode_id>` | 获取转录 |
| POST | `/transcripts/<episode_id>` | 创建转录任务 (异步) |
| DELETE | `/transcripts/<episode_id>` | 删除转录 |
| POST | `/transcripts/<episode_id>/fetch` | 从外部 URL 拉取转录 |
| GET | `/transcripts/<episode_id>/check-external` | 检查是否有外部转录源 |

### POST /transcripts/<episode_id>
```json
{ "provider": "auto|official|local_whisper|local_whisperx|assemblyai", "language": "auto" }
→ 200 { "data": { "task_id": "...", "provider": "...", "language": "..." } }
```

---

## Summaries — `/api/summaries`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/summaries/<episode_id>` | 获取摘要 |
| POST | `/summaries/<episode_id>` | 生成摘要 (异步)。自动翻译 |
| POST | `/summaries/<episode_id>/translate` | 翻译摘要为中文 (异步) |
| DELETE | `/summaries/<episode_id>` | 删除摘要 |
| GET | `/summaries/templates` | 列出可用模板 |

### POST /summaries/<episode_id>
```json
{
  "template_name": "learning",
  "enabled_blocks": ["key_points", "quotes"],
  "params": { "length": "long", "language": "zh" },
  "force": false
}
```

---

## Tasks — `/api/tasks`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/tasks` | 任务列表。筛选: `status`, `type`, `episode_id`, `feed_id` |
| GET | `/tasks/<id>` | 任务状态 (含 episode/feed 元数据) |
| POST | `/tasks/<id>/cancel` | 取消 pending 任务 |

### Task 响应结构
```json
{
  "id": "uuid",
  "type": "download|transcribe|summarize|translate|refresh",
  "status": "pending|processing|completed|failed",
  "progress": 0-100,
  "episode_id": "...", "episode_title": "...",
  "feed_id": "...", "feed_title": "...",
  "result": {}, "error_message": null,
  "created_at": "...", "completed_at": "..."
}
```

---

## Settings — `/api/settings`

### LLM 配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/settings/llm` | 获取 providers + models + routes |
| PUT | `/settings/llm` | 保存 LLM 配置 |
| PUT | `/settings/llm/active` | 设置活动配置 (旧版) |
| POST | `/settings/llm/test` | 测试连接 |

### GET /settings/llm 响应
```json
{
  "providers": [{ "id": "modelscope", "name": "ModelScope", "api_format": "openai_compatible", "base_url": "...", "has_api_key": true, "enabled": true }],
  "models": [{ "id": "modelscope-deepseek-v4-flash", "provider_id": "modelscope", "model": "deepseek-ai/DeepSeek-V4-Flash", "enabled": true }],
  "default_model_id": "modelscope-deepseek-v4-flash",
  "task_routes": { "summary": "model-id", "briefing": "model-id", "transcript_normalize": "model-id" }
}
```

> `api_key` 字段始终返回空字符串，用 `has_api_key` 标记是否已存储。

### Tavily 搜索配置

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/settings/tavily` | 获取 Tavily 配置 |
| PUT | `/settings/tavily` | 保存 Tavily 配置 |
| POST | `/settings/tavily/test` | 测试连接 |

### 搜索提示词

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/settings/prompts/search-query` | 获取自定义搜索片段 |
| PUT | `/settings/prompts/search-query` | 保存自定义搜索片段 |

---

## Prompt Templates — `/api/prompt-templates`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/prompt-templates/` | 列出模板 |
| GET | `/prompt-templates/<id>` | 单个模板 |
| POST | `/prompt-templates/` | 创建模板 |
| PUT | `/prompt-templates/<id>` | 更新模板 (系统模板不可改) |
| POST | `/prompt-templates/<id>/duplicate` | 复制模板 |
| DELETE | `/prompt-templates/<id>` | 删除模板 (系统模板不可删) |
| GET | `/prompt-templates/<id>/blocks` | 获取可选 blocks |
| GET | `/prompt-templates/<id>/parameters` | 获取参数定义 |
| POST | `/prompt-templates/init` | 初始化系统默认模板 (幂等) |

---

## Insights — `/api/insights`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/insights/briefing` | 获取今日 AI 简报 (有缓存则不调用 LLM) |
| POST | `/insights/briefing` | 强制重新生成简报 |
| GET | `/insights/briefing/export` | 导出 PDF |

---

## Stats — `/api`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/stats` | 系统统计: feeds/episodes/tasks 计数 |

---

## Media — `/api/media`

| 方法 | 路径 | 说明 |
|------|------|------|
| GET | `/media/<path:filename>` | 提供本地音频文件，支持条件缓存 |
