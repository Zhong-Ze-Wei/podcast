# Podcast Manager 操作管线完整文档

## 一、系统架构概览

```
浏览器 (React 18 + Vite + TailwindCSS)
  │
  │ axios 调用 /api/*
  ▼
Flask 后端 (Blueprints 路由层)
  │
  ├── api/*      → 薄路由层，只做参数校验
  ├── services/* → 业务逻辑（调 LLM / MongoDB）
  ├── models/*   → 纯数据模型
  └── core/*     → 可复用领域逻辑（SummarizationEngine）
  │
  │── MongoDB (pymongo)
  │── LLMClient (OpenAI 兼容 API)
  │── AssemblyAI (语音转录)
  │── feedparser (RSS 解析)
  │
  后台服务:
  - AutoRefresher: 守护线程，每1小时自动刷新过期订阅源
  - TaskQueue: 线程池(3 worker)，处理异步任务
```

---

## 二、前端视图与按钮操作全图

### 2.1 侧边栏 (Sidebar)

| 按钮/操作 | 真实作用 | 后端调用链路 |
|---|---|---|
| **Add Feed（添加订阅源）** | 输入 RSS URL，解析并保存为订阅源 | `POST /api/feeds` → `rss_service.add_feed()` → feedparser 解析 RSS → 保存 feed + episodes 到 MongoDB |
| **Delete Feed（删除订阅源）** | 删除订阅源及其所有剧集、文稿、摘要 | `DELETE /api/feeds/<id>` → `rss_service.delete_feed()` → 级联删除 episodes、transcripts、summaries |
| **Refresh Feed（刷新订阅源）** | 重新拉取 RSS 源，获取新剧集 | `POST /api/feeds/<id>/refresh` → TaskQueue 异步执行 → `rss_service.refresh_feed()` → feedparser 重新解析 |
| **Star Feed（收藏订阅源）** | 切换订阅源的收藏状态 | `PUT /api/feeds/<id>/favorite` → 切换 `is_favorite` 字段 |
| **点击订阅源** | 进入该订阅源的详情视图 | `GET /api/feeds/<id>/episodes` → 加载该源下所有剧集 |
| **导航按钮** | 切换视图：工作区 / 订阅列表 / 收藏 / 设置 | 纯前端状态切换，无 API 调用 |
| **视图模式切换** | 切换传统列表 / AI 简报模式 | 纯前端状态切换，无 API 调用 |

---

### 2.2 工作区视图 (WorkspaceView)

展示所有已完成转录或摘要的剧集，即「已处理」的内容。

| 按钮/操作 | 真实作用 | 后端调用链路 |
|---|---|---|
| **Tab 筛选**（全部/已转录/已摘要） | 客户端过滤，按处理状态分类显示 | 无 API 调用，纯前端过滤 `workspaceEpisodes` 数组 |
| **点击剧集卡片** | 进入剧集详情视图 | 无 API 调用，纯前端 `setView('detail')` |
| **播放按钮** | 播放该剧集音频 | 无 API 调用，设置 `currentPlaying` 状态 → 优先使用本地音频，失败回退远程 URL |
| **收藏按钮** | 收藏/取消收藏剧集 | `PUT /api/episodes/<id>/star` → 切换 `is_starred` 字段（乐观更新） |

---

### 2.3 订阅源详情视图 (FeedDetailView)

展示某个订阅源的信息及其下所有剧集。

| 按钮/操作 | 真实作用 | 后端调用链路 |
|---|---|---|
| **刷新按钮** | 重新拉取 RSS 源 | `POST /api/feeds/<id>/refresh` → TaskQueue 异步执行 `rss_service.refresh_feed()` |
| **播放最新** | 播放该源最新一期剧集 | 无 API 调用，直接设置 `currentPlaying` |
| **访问网站** | 在新标签页打开订阅源官网 | 无 API 调用，`window.open(feed.website)` |
| **点击剧集** | 进入剧集详情视图 | 无 API 调用，纯前端导航 |
| **收藏剧集** | 收藏/取消收藏 | `PUT /api/episodes/<id>/star` |
| **网格/列表切换** | 切换剧集显示模式 | 无 API 调用，纯前端状态 |
| **返回按钮** | 回到订阅列表 | 无 API 调用，`setView('list')` |

---

### 2.4 剧集详情视图 (EpisodeDetailView) — 核心视图

这是最复杂的视图，包含3个标签页，是 AI 功能的主要入口。

#### 文稿标签 (Transcript Tab)

| 按钮/操作 | 真实作用 | 后端调用链路 |
|---|---|---|
| **自动获取外部文稿** | 页面加载时，如果剧集有 `transcript_url`，自动拉取 | `POST /api/transcripts/<id>/fetch_external` → `TranscriptFetcher` 拉取 SRT/VTT/JSON → 解析为分段文本 |
| **Request Transcript（请求转录）** | 通过 AssemblyAI 云端语音转录 | `POST /api/transcripts/<id>` → TaskQueue 异步 → 下载音频 → 提交 AssemblyAI（带说话人分离）→ 轮询等待完成 → 保存文稿 |
| **Check External（检查外部文稿）** | 检查 RSS 源是否包含 Podcasting 2.0 文稿链接 | `GET /api/transcripts/<id>/check_external` → 检查 `transcript_url` 字段是否存在 |
| **删除文稿** | 删除已存在的转录文稿 | `DELETE /api/transcripts/<id>` → 从 MongoDB 删除 transcript 文档 |

**转录路由逻辑：**
1. 如果剧集有 `transcript_url`（Podcasting 2.0 标签）→ 直接用 `TranscriptFetcher` 拉取
2. 否则 → 使用 AssemblyAI 云端转录（带说话人分离）

#### 摘要标签 (Summary Tab)

| 按钮/操作 | 真实作用 | 后端调用链路 |
|---|---|---|
| **Generate Summary（生成摘要）** | 基于模板 + 转录文稿，调用 LLM 生成结构化摘要 | `POST /api/summaries/<id>` → TaskQueue 异步 → SummarizationEngine v3：加载模板 → 过滤启用的 block → 构建 prompt → LLM 调用 → 解析响应 → 存储到 MongoDB |
| **Block 开关** | 切换摘要模板中各模块的启用/禁用 | 纯前端状态，影响下次生成时包含哪些 block |
| **Auto-translate（自动翻译）** | 调用 LLM 翻译已生成的摘要 | `POST /api/summaries/<id>/translate` → TaskQueue 异步 → LLM 翻译摘要文本 |
| **模板选择器** | 选择不同摘要模板查看 | `GET /api/summaries/<id>?template_name=xxx` → 获取对应模板的摘要结果 |

**摘要生成流程（v3 引擎）：**
1. 从 `prompt_templates` 集合加载模板
2. 过滤模板中 `is_enabled=True` 的 block
3. 构建 prompt：系统提示 + 启用的 block + 转录分段
4. 调用 LLM 生成
5. 解析响应，存入 `summaries` 集合
6. 如果 `auto_translate=True`，链式触发翻译任务

#### 信息标签 (Info Tab)
- 纯展示：剧集元数据、音频 URL、订阅源信息、发布日期
- 无交互按钮

#### 音频控制

| 按钮/操作 | 真实作用 |
|---|---|
| **播放按钮** | 设置 `currentPlaying` → 优先使用 `local_audio_url`（本地），失败回退 `audio_url`（远程） |
| **进度保存** | 每30秒自动保存播放位置 + 暂停/切换时保存 → `PUT /api/episodes/<id>` 更新 `play_position` |
| **恢复播放** | 从上次播放位置继续 → 读取 `episode.play_position` |

---

### 2.5 AI 简报视图 (AIBriefingView)

基于所有已处理剧集，由 LLM 生成每日播客简报。

| 按钮/操作 | 真实作用 | 后端调用链路 |
|---|---|---|
| **加载简报** | 页面加载时获取今日缓存的简报 | `GET /api/insights/briefing` → 按日期查询 MongoDB 缓存 |
| **重新生成** | 收集近期剧集，调用 LLM 生成新简报 | `POST /api/insights/briefing/regenerate` → 收集近期剧集（优先已摘要的）→ 格式化为条目 → LLM 生成结构化 JSON → 缓存到 MongoDB |
| **导出 PDF** | 将简报导出为 PDF 文件 | `POST /api/insights/briefing/export-pdf` → 后端从 markdown 报告生成 PDF |
| **点击推荐剧集** | 进入该剧集详情 | 无 API 调用，纯前端导航 |

**AI 简报输出结构：**
- `hotTopics` — 热门话题
- `newConcepts` — 新概念
- `trends` — 趋势分析
- `recommended` — 推荐剧集
- `summary` — 总体摘要
- `markdownReport` — 完整 Markdown 报告

---

### 2.6 收藏视图 (FavoritesView)

| 按钮/操作 | 真实作用 | 后端调用链路 |
|---|---|---|
| **查看收藏** | 页面加载时过滤已收藏剧集 | 无 API 调用，纯前端过滤 `episodes` 数组中 `is_starred=True` 的项 |
| **取消收藏** | 取消剧集收藏 | `PUT /api/episodes/<id>/star` → 切换 `is_starred`（乐观更新） |
| **播放/点击** | 播放或进入详情 | 同其他视图 |

---

### 2.7 设置视图 (SettingsView)

#### LLM 配置面板 (LlmConfigPanel)

| 按钮/操作 | 真实作用 | 后端调用链路 |
|---|---|---|
| **加载配置列表** | 获取所有 LLM 配置（最多5个） | `GET /api/settings/llm` → 返回 MongoDB 中的配置列表 |
| **添加配置** | 新增一个 LLM 服务商配置 | `POST /api/settings/llm` → 创建配置文档（base_url、api_key、model 等） |
| **保存配置** | 修改已有配置 | `PUT /api/settings/llm/<id>` → 更新配置字段 |
| **删除配置** | 删除配置 | `DELETE /api/settings/llm/<id>` |
| **测试连接** | 验证 LLM 配置是否可用 | `POST /api/settings/llm/<id>/test` → 实际调用 LLM：发送测试 prompt → 返回成功/失败 |
| **服务商预设** | 选择预设服务商（支持9家） | 无 API 调用，纯前端自动填充 `base_url` 和模型名 |

#### 提示词模板面板 (PromptTemplatesPanel)

| 按钮/操作 | 真实作用 | 后端调用链路 |
|---|---|---|
| **加载模板列表** | 获取所有摘要模板 | `GET /api/prompt-templates` → 返回模板列表（系统模板标记 `is_system=True`） |
| **创建模板** | 新建自定义摘要模板 | `POST /api/prompt-templates` → 创建模板文档（含 blocks 和 parameters） |
| **保存模板** | 修改已有模板 | `PUT /api/prompt-templates/<id>` → 更新模板（系统模板禁止修改） |
| **复制模板** | 克隆一个模板 | `POST /api/prompt-templates/<id>/duplicate` → 复制为新模板 |
| **删除模板** | 删除自定义模板 | `DELETE /api/prompt-templates/<id>`（系统模板禁止删除） |
| **Block 开关** | 切换模板中各模块启用/禁用 | `PUT /api/prompt-templates/<id>/blocks` → 切换 `is_enabled` |
| **参数编辑** | 修改模板参数 | `PUT /api/prompt-templates/<id>/parameters` → 更新参数值 |

---

## 三、AI/LLM 调用点汇总

系统中共有 **4 个** LLM 调用点：

| 调用点 | 触发按钮 | 调用方式 | 输入 | 输出 |
|---|---|---|---|---|
| 摘要生成 | Generate Summary | `LLMClient.chat()` | 转录文稿 + 模板 prompt | 结构化摘要文本 |
| 摘要翻译 | Auto-translate 开关 | `LLMClient.chat()` | 摘要文本 + 目标语言 | 翻译后的摘要 |
| AI 简报 | Regenerate | `LLMClient.chat_json()` | 近期剧集条目 | JSON（热门话题/趋势/推荐等） |
| 连接测试 | Test 按钮 | `LLMClient.chat()` | 测试 prompt | 成功/失败 |

---

## 四、异步任务流程

```
用户点击按钮（如「生成摘要」）
  │
  ▼
前端调用 API（如 POST /api/summaries/<id>）
  │
  ▼
API 路由通过 TaskQueue 创建异步任务:
  task_id = task_queue.enqueue(task_type, target_id, func, args)
  │
  ▼
TaskQueue (ThreadPoolExecutor, 3 workers):
  1. 创建任务文档（status: pending）
  2. 提交到线程池
  3. 更新状态: pending → running
  4. 执行实际函数
  5. 更新状态: running → completed（或 failed）
  │
  ▼
前端轮询:
  - TaskPanel 组件定期 GET /api/tasks
  - 显示进度条和状态
  - 完成后触发 loadData() 刷新界面
```

**任务类型：**
- `refresh_feed` — RSS 重新解析
- `download_audio` — 音频文件下载
- `transcribe` — AssemblyAI 转录
- `summary` — LLM 摘要生成
- `translate_summary` — LLM 翻译

**自动清理：** MongoDB TTL 索引，已完成任务 7 天后自动删除。

---

## 五、后台服务

| 服务 | 作用 | 运行方式 |
|---|---|---|
| **AutoRefresher** | 自动刷新过期订阅源 | 守护线程，每1小时检查一次。条件：status 非 paused 且 last_fetched 超过6小时 |
| **音频播放位置保存** | 每30秒 + 暂停/切换时保存 | 前端定时器 + 事件监听 |

---

## 六、数据流向图

```
RSS URL
  │
  ▼ (feedparser)
Feed + Episodes → MongoDB
  │
  ├── Episode.transcript_url?
  │     │
  │     ├── YES → TranscriptFetcher → Transcript (SRT/VTT/JSON → segments)
  │     │
  │     └── NO  → AssemblyAI (音频下载 → 云端转录 → 带说话人分段)
  │
  ▼
Transcript (分段文本)
  │
  ▼ (模板 + prompt 构建)
SummarizationEngine v3 → LLM → Summary (结构化摘要)
  │
  ├── auto_translate? → LLM → 翻译后摘要
  │
  ▼
BriefingService → 收集近期摘要/剧集 → LLM → AI 简报
  │
  ▼
导出 PDF
```

---

*文档生成时间：2026-05-17*
*基于项目当前 master 分支代码分析*
