# 前端报告

> 基于 `frontend/src/` 实际代码整理
> 文档日期：2026-05-16

---

## 1. 技术栈

| 依赖 | 版本 | 用途 |
|------|------|------|
| React | 18.2 | 核心 UI 框架 |
| Vite | 5.0 | 构建工具 / 开发服务器 |
| TailwindCSS | 3.4 | 原子化 CSS |
| axios | 1.6 | HTTP 请求 |
| i18next + react-i18next | 25.x / 16.x | 国际化（中/英） |
| i18next-browser-languagedetector | 8.x | 自动检测浏览器语言 |
| lucide-react | 0.300 | 图标库 |

**开发端口**：`http://localhost:3000`
**代理配置**：vite.config.js 将 `/api` 代理到 `http://localhost:5000`

---

## 2. 目录结构

```
frontend/src/
├── App.jsx                        # 应用根组件，全局状态管理
├── main.jsx                       # 入口，挂载 i18n
├── i18n.js                        # i18next 配置
├── index.css                      # 全局样式（含自定义滚动条）
├── locales/
│   ├── zh.json                    # 中文文案
│   └── en.json                    # 英文文案
├── services/
│   └── api.js                     # 所有后端 API 调用封装
├── utils/
│   └── helpers.js                 # 工具函数（decodeHtmlEntities 等）
└── components/
    ├── layout/
    │   └── Sidebar.jsx            # 左侧导航栏 + 订阅列表
    ├── player/
    │   └── PlayerBar.jsx          # 底部音频播放器
    ├── tasks/
    │   └── TaskPanel.jsx          # 任务进度浮层面板
    ├── cards/
    │   ├── FeedCard.jsx           # 订阅源卡片
    │   └── EpisodeCard.jsx        # 单集卡片
    ├── common/
    │   ├── StatusBadge.jsx        # 状态徽章
    │   ├── LanguageSwitcher.jsx   # 语言切换按钮
    │   └── TaskProgress.jsx       # 任务进度条
    └── views/
        ├── WorkspaceView.jsx      # 工作台：已处理单集
        ├── FeedDetailView.jsx     # 订阅源详情 + 单集列表
        ├── EpisodeDetailView.jsx  # 单集详情、转录、摘要
        ├── FavoritesView.jsx      # 收藏列表
        ├── DownloadedView.jsx     # 已下载列表
        ├── TranscribedView.jsx    # 已转录列表
        ├── AIBriefingView.jsx     # AI 简报面板
        ├── LlmSettingsView.jsx    # LLM 设置（遗留，已被 SettingsView 替代）
        ├── SettingsView.jsx       # 设置主视图（含子面板路由）
        └── settings/
            ├── LlmConfigPanel.jsx         # LLM 多配置管理面板
            └── PromptTemplatesPanel.jsx   # Prompt 模板管理面板
```

---

## 3. 状态管理

前端**无独立状态管理库**（无 Redux/Zustand），全部状态提升至 `App.jsx`。

### App.jsx 核心状态

| 状态变量 | 类型 | 说明 |
|----------|------|------|
| `view` | string | 当前视图：`list / feedDetail / detail / workspace / settings / favorites` |
| `viewMode` | string | 主区模式：`traditional / ai-briefing` |
| `feeds` | array | 所有订阅源列表 |
| `episodes` | array | 所有单集列表（最多 500 条） |
| `workspaceEpisodes` | array | 已处理单集（转录/摘要状态） |
| `feedEpisodes` | array | 当前选中订阅源的单集 |
| `selectedFeed` | object | 当前选中的订阅源 |
| `selectedEpisode` | object | 当前选中的单集 |
| `currentPlaying` | object | 当前播放的单集 |
| `isPlaying` | boolean | 播放状态 |

### 数据加载策略

- 应用启动时 `loadData()` 并行请求：feeds 列表、episodes 列表（500 条）、已处理单集
- 切换订阅源时实时请求该 Feed 的单集（`feedsApi.getEpisodes`），使用请求 ID 防止竞态
- 任务完成后触发 `loadData()` 刷新全局状态

---

## 4. 视图路由

路由通过 `view` 状态字符串切换，无 React Router，全部条件渲染在 `App.jsx` 中。

| view 值 | 渲染组件 | 触发时机 |
|---------|----------|----------|
| `list` | FeedCard 列表 / EpisodeCard 列表 | 默认首页（但实际初始值为 workspace）|
| `workspace` | WorkspaceView | Sidebar 点击"工作台" |
| `feedDetail` | FeedDetailView | 点击订阅源卡片 |
| `detail` | EpisodeDetailView | 点击单集卡片 |
| `favorites` | FavoritesView | Sidebar 点击"收藏" |
| `settings` | SettingsView | Sidebar 点击"设置" |
| `list`（ai-briefing 模式）| AIBriefingView | viewMode='ai-briefing' 时 |

---

## 5. API 服务层（services/api.js）

所有 HTTP 请求通过 axios 实例统一管理，Base URL 为 `/api`。

**响应拦截器**：
- 404 作为正常情况处理（资源未创建），仅打 `console.info`
- 其他错误打 `console.error` 并 reject

已封装的 API 模块：

| 模块 | 方法数 | 覆盖端点 |
|------|--------|----------|
| `feedsApi` | 9 | feeds CRUD、刷新、标星、收藏、获取单集 |
| `episodesApi` | 8 | episodes 列表、详情、更新、标星、已读、下载 |
| `transcriptsApi` | 5 | 获取、创建、删除、抓取官方字幕、检查外部字幕 |
| `summariesApi` | 6 | 获取、创建、翻译、删除、获取类型/模板列表 |
| `promptTemplatesApi` | 9 | 模板 CRUD、复制、获取 blocks/parameters、初始化 |
| `tasksApi` | 3 | 列表、获取、取消 |
| `statsApi` | 1 | 统计信息 |
| `settingsApi` | 4 | LLM 配置 CRUD、连接测试 |
| `insightsApi` | 3 | 获取简报、重新生成、PDF 导出 |

---

## 6. 播放器实现

- `<audio>` 元素由 `App.jsx` 持有 ref（`audioRef`），挂载为隐藏元素
- `PlayerBar` 通过 props 接收 `audioRef`，读取 `currentTime` / `duration` 做进度展示
- 播放位置每 30 秒自动保存到后端（`episodesApi.update`），变化 < 5 秒不写入
- 切换单集时先保存当前位置，新单集恢复上次进度

---

## 7. 国际化

- 语言文件：`src/locales/zh.json`、`src/locales/en.json`
- 检测顺序：localStorage → 浏览器语言 → 默认 `zh`
- 语言切换后保存到 localStorage，页面无需刷新

---

## 8. 已知问题

| 问题 | 位置 | 描述 |
|------|------|------|
| 大量数据性能风险 | `api.js` listTranscribed | `per_page=1000` 一次性拉取，数据量大时响应慢 |
| 本地音频无法播放 | `PlayerBar.jsx` | 播放器 `src` 始终用 `audio_url`（远程），下载到本地的 `audio_path` 未使用 |
| 前端搜索仅过滤内存数据 | `App.jsx` filteredEpisodes | 搜索只在已加载的 500 条内过滤，无后端搜索 |
| LlmSettingsView 遗留 | `views/LlmSettingsView.jsx` | 疑似被 `SettingsView` + `LlmConfigPanel` 替代，但文件仍存在 |
| PromptTemplatesPanel 位置 | `plan.md` 标注为 tasks/ 路径 | 实际在 `views/settings/` 路径，plan.md 描述有误 |
| AIBriefingView 与 insightsApi 对接 | `AIBriefingView.jsx` | 需核查是否完整使用 `insightsApi` 所有方法 |
