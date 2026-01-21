# Podcast Manager API 接口文档

> 前端开发者接口规范 v1.0

---

## 基础信息

| 项目 | 值 |
|------|-----|
| Base URL | `http://localhost:5000/api` |
| 协议 | HTTP/HTTPS |
| 数据格式 | JSON |
| 编码 | UTF-8 |
| 认证 | 暂无 (后续支持JWT) |

---

## 请求规范

### Headers

```http
Content-Type: application/json
Accept: application/json
```

### 分页参数

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| page | int | 1 | 页码 |
| per_page | int | 20 | 每页数量 (最大100) |

### 筛选参数

| 参数 | 类型 | 说明 |
|------|------|------|
| status | string | 状态筛选 |
| is_starred | boolean | 是否已标星 |
| is_favorite | boolean | 是否已收藏 |
| feed_id | string | 按订阅源筛选 |

---

## 响应规范

### 成功响应

```json
{
  "success": true,
  "data": { ... },
  "message": null
}
```

### 列表响应 (带分页)

```json
{
  "success": true,
  "data": [ ... ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 100,
    "pages": 5,
    "has_next": true,
    "has_prev": false
  }
}
```

### 错误响应

```json
{
  "success": false,
  "data": null,
  "message": "Error description",
  "error_code": "ERROR_CODE"
}
```

### HTTP 状态码

| 状态码 | 说明 |
|--------|------|
| 200 | 成功 |
| 201 | 创建成功 |
| 400 | 请求参数错误 |
| 404 | 资源不存在 |
| 409 | 冲突 (任务进行中/已完成) |
| 500 | 服务器错误 |

---

## 错误码列表

| 错误码 | 说明 |
|--------|------|
| FEED_NOT_FOUND | 订阅源不存在 |
| EPISODE_NOT_FOUND | 单集不存在 |
| TASK_NOT_FOUND | 任务不存在 |
| INVALID_RSS_URL | 无效的RSS地址 |
| RSS_PARSE_ERROR | RSS解析失败 |
| TASK_IN_PROGRESS | 任务正在进行中 |
| ALREADY_COMPLETED | 任务已完成 |
| DOWNLOAD_FAILED | 下载失败 |
| TRANSCRIBE_FAILED | 转录失败 |

---

## API 端点

---

### Feeds (订阅源)

#### 获取订阅列表

```http
GET /api/feeds
```

**Query 参数:**
| 参数 | 类型 | 说明 |
|------|------|------|
| page | int | 页码 |
| per_page | int | 每页数量 |
| status | string | active / paused / error |
| is_starred | boolean | 是否标星 |

**响应:**
```json
{
  "success": true,
  "data": [
    {
      "id": "65a1b2c3d4e5f6789",
      "title": "Lex Fridman Podcast",
      "rss_url": "https://lexfridman.com/feed/podcast/",
      "website": "https://lexfridman.com",
      "image": "https://...",
      "description": "Conversations about...",
      "author": "Lex Fridman",
      "language": "en",
      "status": "active",
      "is_starred": false,
      "is_favorite": false,
      "tags": ["AI", "Tech"],
      "episode_count": 450,
      "unread_count": 5,
      "last_checked": "2024-01-15T10:30:00Z",
      "last_updated": "2024-01-15T08:00:00Z",
      "created_at": "2024-01-01T00:00:00Z"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 3,
    "pages": 1
  }
}
```

---

#### 获取单个订阅详情

```http
GET /api/feeds/:id
```

**路径参数:**
| 参数 | 类型 | 说明 |
|------|------|------|
| id | string | 订阅ID |

**响应:**
```json
{
  "success": true,
  "data": {
    "id": "65a1b2c3d4e5f6789",
    "title": "Lex Fridman Podcast",
    "rss_url": "https://lexfridman.com/feed/podcast/",
    "website": "https://lexfridman.com",
    "image": "https://...",
    "description": "Conversations about...",
    "author": "Lex Fridman",
    "language": "en",
    "status": "active",
    "is_starred": false,
    "is_favorite": false,
    "tags": ["AI", "Tech"],
    "episode_count": 450,
    "unread_count": 5,
    "last_checked": "2024-01-15T10:30:00Z",
    "last_updated": "2024-01-15T08:00:00Z",
    "created_at": "2024-01-01T00:00:00Z"
  }
}
```

---

#### 添加订阅

```http
POST /api/feeds
```

**请求体:**
```json
{
  "rss_url": "https://lexfridman.com/feed/podcast/",
  "tags": ["AI", "Tech"]  // 可选
}
```

**响应:**
```json
{
  "success": true,
  "data": {
    "id": "65a1b2c3d4e5f6789",
    "title": "Lex Fridman Podcast",
    "rss_url": "https://lexfridman.com/feed/podcast/",
    "status": "active",
    "episode_count": 450
  },
  "message": "Feed added successfully"
}
```

**错误响应:**
```json
{
  "success": false,
  "message": "Invalid RSS URL",
  "error_code": "INVALID_RSS_URL"
}
```

---

#### 更新订阅

```http
PUT /api/feeds/:id
```

**请求体:**
```json
{
  "tags": ["AI", "Interview"],
  "status": "paused"
}
```

**响应:**
```json
{
  "success": true,
  "data": {
    "id": "65a1b2c3d4e5f6789",
    "tags": ["AI", "Interview"],
    "status": "paused"
  }
}
```

---

#### 删除订阅

```http
DELETE /api/feeds/:id
```

**响应:**
```json
{
  "success": true,
  "message": "Feed deleted successfully"
}
```

---

#### 刷新订阅 (异步)

```http
POST /api/feeds/:id/refresh
```

**响应:**
```json
{
  "success": true,
  "data": {
    "task_id": "abc123-def456",
    "status": "queued"
  }
}
```

---

#### 标星/取消标星

```http
POST /api/feeds/:id/star
```

**请求体:**
```json
{
  "starred": true
}
```

**响应:**
```json
{
  "success": true,
  "data": {
    "id": "65a1b2c3d4e5f6789",
    "is_starred": true
  }
}
```

---

#### 收藏/取消收藏

```http
POST /api/feeds/:id/favorite
```

**请求体:**
```json
{
  "favorite": true
}
```

---

### Episodes (单集)

#### 获取单集列表

```http
GET /api/episodes
```

**Query 参数:**
| 参数 | 类型 | 说明 |
|------|------|------|
| page | int | 页码 |
| per_page | int | 每页数量 |
| feed_id | string | 按订阅源筛选 |
| status | string | new / downloaded / transcribed / summarized |
| is_read | boolean | 是否已读 |
| is_starred | boolean | 是否标星 |

**响应:**
```json
{
  "success": true,
  "data": [
    {
      "id": "65b2c3d4e5f67890",
      "feed_id": "65a1b2c3d4e5f6789",
      "feed_title": "Lex Fridman Podcast",
      "guid": "unique-episode-id",
      "title": "#400 - Elon Musk",
      "description": "Conversation with Elon...",
      "link": "https://...",
      "published": "2024-01-10T12:00:00Z",
      "audio_url": "https://...",
      "duration": 10800,
      "duration_formatted": "3:00:00",
      "status": "new",
      "is_read": false,
      "is_starred": false,
      "is_favorite": false,
      "has_transcript": false,
      "has_summary": false,
      "created_at": "2024-01-10T12:30:00Z"
    }
  ],
  "pagination": { ... }
}
```

---

#### 获取某订阅的单集列表

```http
GET /api/feeds/:id/episodes
```

参数和响应同上。

---

#### 获取单集详情

```http
GET /api/episodes/:id
```

**响应:**
```json
{
  "success": true,
  "data": {
    "id": "65b2c3d4e5f67890",
    "feed_id": "65a1b2c3d4e5f6789",
    "feed_title": "Lex Fridman Podcast",
    "title": "#400 - Elon Musk",
    "description": "Conversation with Elon...",
    "link": "https://...",
    "published": "2024-01-10T12:00:00Z",
    "audio_url": "https://...",
    "audio_type": "audio/mpeg",
    "audio_size": 54321000,
    "duration": 10800,
    "duration_formatted": "3:00:00",
    "status": "transcribed",
    "is_read": true,
    "is_starred": false,
    "play_position": 3600,
    "has_transcript": true,
    "has_summary": false
  }
}
```

---

#### 下载音频 (异步)

```http
POST /api/episodes/:id/download
```

**响应 (成功):**
```json
{
  "success": true,
  "data": {
    "task_id": "abc123-def456",
    "status": "queued"
  }
}
```

**响应 (已在下载中):**
```json
{
  "success": false,
  "message": "Task already in progress",
  "error_code": "TASK_IN_PROGRESS"
}
```
HTTP 状态码: 409

---

#### 标记已读

```http
PUT /api/episodes/:id/read
```

**请求体:**
```json
{
  "read": true
}
```

---

#### 更新播放进度

```http
PUT /api/episodes/:id/position
```

**请求体:**
```json
{
  "position": 3600
}
```

---

### Transcripts (转录)

#### 获取转录内容

```http
GET /api/episodes/:id/transcript
```

**响应 (有转录):**
```json
{
  "success": true,
  "data": {
    "episode_id": "65b2c3d4e5f67890",
    "text": "Full transcript text...",
    "segments": [
      { "start": 0.0, "end": 5.2, "text": "Hello and welcome...", "speaker": "A" },
      { "start": 5.2, "end": 10.1, "text": "Today we have...", "speaker": "B" }
    ],
    "speakers": ["A", "B"],
    "chapters": [
      {
        "start": 0.0,
        "end": 300.5,
        "headline": "Introduction",
        "summary": "The host introduces the guest..."
      }
    ],
    "entities": [
      { "text": "OpenAI", "entity_type": "organization" },
      { "text": "Elon Musk", "entity_type": "person" }
    ],
    "language": "en",
    "word_count": 15000,
    "duration": 3600000,
    "source": "assemblyai",
    "created_at": "2024-01-11T10:00:00Z"
  }
}
```

**字段说明:**

| 字段 | 类型 | 说明 |
|------|------|------|
| segments[].speaker | string | 说话人标签 (A/B/C...)，AssemblyAI转录时有此字段 |
| speakers | array | 检测到的说话人列表 |
| chapters | array | 自动生成的章节 (AssemblyAI) |
| entities | array | 识别的实体 (人名、公司等) |
| source | string | 转录来源: assemblyai, whisper, official |

**响应 (无转录):**
```json
{
  "success": true,
  "data": null
}
```

---

#### 触发转录 (异步)

```http
POST /api/episodes/:id/transcribe
```

**响应:**
```json
{
  "success": true,
  "data": {
    "task_id": "xyz789-abc123",
    "status": "queued"
  }
}
```

---

### Summaries (摘要)

#### 获取摘要

```http
GET /api/episodes/:id/summary
```

**响应:**
```json
{
  "success": true,
  "data": {
    "episode_id": "65b2c3d4e5f67890",
    "tldr": "Elon Musk discusses AI safety, Mars colonization, and the future of Tesla.",
    "key_points": [
      { "point": "AI needs regulation", "timestamp": "00:15:23" },
      { "point": "SpaceX aims for Mars by 2030", "timestamp": "01:02:45" },
      { "point": "Tesla FSD progress", "timestamp": "02:15:10" }
    ],
    "why_it_matters": "Industry impact analysis...",
    "tags": ["AI", "SpaceX", "Tesla"],
    "tldr_zh": "马斯克讨论了AI安全、火星殖民和特斯拉的未来。",
    "key_points_zh": ["AI需要监管", "SpaceX计划2030年登陆火星", "特斯拉FSD进展"],
    "created_at": "2024-01-11T12:00:00Z"
  }
}
```

---

#### 触发摘要生成 (异步)

```http
POST /api/episodes/:id/summarize
```

**响应:**
```json
{
  "success": true,
  "data": {
    "task_id": "sum123-abc456",
    "status": "queued"
  }
}
```

---

### Tasks (异步任务)

#### 获取任务状态

```http
GET /api/tasks/:task_id
```

**响应 (进行中):**
```json
{
  "success": true,
  "data": {
    "task_id": "abc123-def456",
    "task_type": "download",
    "status": "processing",
    "progress": 45,
    "episode_id": "65b2c3d4e5f67890",
    "created_at": "2024-01-15T10:00:00Z",
    "started_at": "2024-01-15T10:00:05Z"
  }
}
```

**响应 (完成):**
```json
{
  "success": true,
  "data": {
    "task_id": "abc123-def456",
    "task_type": "download",
    "status": "completed",
    "progress": 100,
    "result": {
      "audio_path": "/media/audio/feed123/ep456.mp3",
      "file_size": 54321000
    },
    "completed_at": "2024-01-15T10:01:30Z"
  }
}
```

**响应 (失败):**
```json
{
  "success": true,
  "data": {
    "task_id": "abc123-def456",
    "task_type": "download",
    "status": "failed",
    "error_message": "Connection timeout",
    "completed_at": "2024-01-15T10:01:30Z"
  }
}
```

---

#### 获取任务列表

```http
GET /api/tasks
```

**Query 参数:**
| 参数 | 类型 | 说明 |
|------|------|------|
| status | string | pending / processing / completed / failed |
| task_type | string | download / transcribe / summarize / refresh |

---

### 统计与搜索

#### 获取统计信息

```http
GET /api/stats
```

**响应:**
```json
{
  "success": true,
  "data": {
    "total_feeds": 10,
    "total_episodes": 500,
    "unread_episodes": 25,
    "transcribed_episodes": 100,
    "summarized_episodes": 50,
    "starred_feeds": 3,
    "starred_episodes": 15
  }
}
```

---

#### 搜索

```http
GET /api/search?q=AI
```

**Query 参数:**
| 参数 | 类型 | 说明 |
|------|------|------|
| q | string | 搜索关键词 |
| type | string | feed / episode / all |

**响应:**
```json
{
  "success": true,
  "data": {
    "feeds": [
      { "id": "...", "title": "AI Podcast", "match": "title" }
    ],
    "episodes": [
      { "id": "...", "title": "Discussing AI Safety", "match": "title" }
    ]
  }
}
```

---

## 前端轮询示例

对于异步任务，前端需要轮询获取状态：

```javascript
async function executeAsyncTask(apiCall) {
  // 1. 发起任务请求
  const response = await apiCall();
  const { task_id } = response.data;

  // 2. 轮询状态
  while (true) {
    await sleep(2000); // 每2秒查询一次

    const statusRes = await fetch(`/api/tasks/${task_id}`);
    const status = await statusRes.json();

    // 3. 回调进度 (可选)
    onProgress?.(status.data.progress);

    // 4. 检查完成状态
    if (status.data.status === 'completed') {
      return status.data.result;
    }
    if (status.data.status === 'failed') {
      throw new Error(status.data.error_message);
    }
  }
}

// 使用示例
const result = await executeAsyncTask(() =>
  fetch('/api/episodes/123/download', { method: 'POST' })
);
```

---

## 数据类型说明

### 日期时间

所有日期时间字段使用 ISO 8601 格式：
```
2024-01-15T10:30:00Z
```

### ID

所有ID字段为 MongoDB ObjectId 的字符串形式：
```
65a1b2c3d4e5f6789012
```

### Duration

- `duration`: 秒数 (int)
- `duration_formatted`: 格式化字符串 "H:MM:SS" 或 "MM:SS"

### Status 枚举

**Feed.status:**
- `active` - 正常
- `paused` - 已暂停
- `error` - 错误

**Episode.status:**
- `new` - 新建
- `downloading` - 下载中
- `downloaded` - 已下载
- `transcribing` - 转录中
- `transcribed` - 已转录
- `summarizing` - 摘要中
- `summarized` - 已摘要
- `error` - 错误

**Episode.transcript_source:** (新增)
- `assemblyai` - AssemblyAI云端转录 (带说话人分离)
- `whisper` - 本地Whisper转录
- `official` - 官方字幕
- `manual` - 手动上传

**Task.status:**
- `pending` - 等待中
- `processing` - 处理中
- `completed` - 已完成
- `failed` - 失败

---

## CORS 配置

后端已启用CORS，允许所有来源访问：

```python
Access-Control-Allow-Origin: *
Access-Control-Allow-Methods: GET, POST, PUT, DELETE, OPTIONS
Access-Control-Allow-Headers: Content-Type, Authorization
```

---

## 版本信息

| 版本 | 日期 | 说明 |
|------|------|------|
| v1.0 | 2024-01 | 初始版本 |
| v1.1 | 2025-01 | 添加AssemblyAI转录支持，segments增加speaker字段，新增chapters/entities/speakers字段 |
