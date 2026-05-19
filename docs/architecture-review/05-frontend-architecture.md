# 05 - 前端架构分析

> 审查日期: 2026-05-17
> 源码版本: master @ 0ed20b6

## 1. 整体架构

```
App.jsx (唯一智能组件，管理全部状态)
├── Sidebar.jsx              (布局：侧边栏，feeds 列表 + 导航)
├── WorkspaceView.jsx        (视图：工作台，已转录/已摘要 episodes)
├── FeedDetailView.jsx       (视图：订阅源详情，某 feed 下的 episodes)
├── FavoritesView.jsx        (视图：收藏夹)
├── EpisodeDetailView.jsx    (视图：episode 详情，转录+摘要)
├── AIBriefingView.jsx       (视图：AI 简报)
├── SettingsView.jsx         (视图：设置入口)
│   ├── LlmConfigPanel       (LLM 配置面板)
│   └── PromptTemplatesPanel (模板管理面板)
├── PlayerBar.jsx            (播放器底栏)
├── TaskPanel.jsx            (任务进度浮层)
├── FeedCard.jsx             (卡片：订阅源)
├── EpisodeCard.jsx          (卡片：单集)
├── StatusBadge.jsx          (通用：状态标签)
├── LanguageSwitcher.jsx     (通用：中英文切换)
├── TaskProgress.jsx         (通用：任务进度条)
└── <audio>                  (隐藏的音频元素)
```

**核心特征**: App.jsx 是唯一的"智能组件"（Smart Component），管理全部状态，子组件都是"哑组件"（Dumb Component），通过 props 接收数据和回调。

---

## 2. App.jsx 职责分析

**文件大小**: 约 449 行

### 2.1 状态变量（16 个）

| 变量 | 类型 | 用途 | 是否可下沉 |
|------|------|------|-----------|
| view | string | 当前视图名 | 否（核心路由状态） |
| previousView | string | 返回详情页前的视图 | 否（路由相关） |
| viewMode | string | 'traditional' / 'ai-briefing' | 否（全局模式） |
| activeFeed | string/null | 当前激活的 feed id | 视情况 |
| selectedFeed | object/null | 当前选中的 feed 对象 | 视情况 |
| selectedEpisode | object/null | 当前选中的 episode 对象 | 否（跨组件共享） |
| currentPlaying | object/null | 正在播放的 episode | 否（跨组件共享） |
| isPlaying | bool | 播放状态 | 否（跨组件共享） |
| feeds | array | 订阅源列表 | **可** → Sidebar 自管理 |
| episodes | array | 全局 episode 列表 | **可** → 各视图自行查询 |
| workspaceEpisodes | array | 工作台 episode 列表 | **可** → WorkspaceView 自管理 |
| feedEpisodes | array | 当前 feed 的 episodes | **可** → FeedDetailView 自管理 |
| feedEpisodesLoading | bool | feed episodes 加载状态 | **可** → FeedDetailView 自管理 |
| loading | bool | 全局加载状态 | 部分可下沉 |
| searchQuery | string | 搜索关键词 | **可** → 下沉到列表视图 |
| episodeViewMode | string | grid / list 切换 | **可** → 下沉到列表视图 |

### 2.2 应该下沉的状态

**feeds → Sidebar 自管理**:
- feeds 列表只需初始加载一次，Sidebar 可以在 mount 时自行 fetch
- App 只需提供 `onAddFeed` / `onDeleteFeed` 等事件回调来触发 Sidebar 刷新
- 好处：减少 App.jsx 约 30 行（loadData 中的 feeds 相关逻辑 + feeds state）

**workspaceEpisodes → WorkspaceView 自管理**:
- WorkspaceView 是唯一使用 workspaceEpisodes 的组件
- 可在组件内部调用 `episodesApi.listTranscribed()`
- 好处：App 不再关心工作台的数据获取

**feedEpisodes + feedEpisodesLoading → FeedDetailView 自管理**:
- 只有 FeedDetailView 使用 feedEpisodes
- App 只需传 `feedId`，FeedDetailView 自己调用 `feedsApi.getEpisodes(feedId)`
- 好处：消除 feedRequestIdRef 竞态处理逻辑（约 20 行）

### 2.3 应该独立成 Context/Hook

**播放状态 → `usePlayer` hook**:
- currentPlaying, isPlaying, audioRef, lastSavedPositionRef
- handlePlay, handlePlayPause, handleSeek, savePlayPosition
- 约 60 行逻辑，可抽取为独立 hook
- 用法: `const { currentPlaying, isPlaying, play, pause, seek } = usePlayer()`

**数据加载逻辑 → `useDataLoader` hook**:
- loadData, handleFeedClick, handleAddFeed, handleRefreshFeed, handleDeleteFeed
- 约 40 行逻辑，可抽取为独立 hook

---

## 3. EpisodeDetailView.jsx 分析

**文件大小**: 约 895 行 — **前端最大的单文件组件**

### 3.1 承担的职责

| 职责 | 大致行数 | 复杂度 |
|------|----------|--------|
| 转录加载和展示 | ~150 行 | 中 |
| 摘要加载、模板选择、Block 切换、生成 | ~120 行 | 高 |
| 任务进度轮询 | ~30 行 | 低 |
| 转录费用预估 | ~5 行 | 低 |
| 中英文切换渲染 | 散布在 ~240 行 JSX 中 | 中 |
| 删除/重新转录操作 | ~40 行 | 低 |
| 强制重新生成摘要 | ~20 行 | 低 |
| 摘要 Block 渲染（20+ 个 if 条件） | ~240 行 | **高** |

### 3.2 内部状态（15 个）

```
activeTab, transcript, summary, loading,
hasExternalTranscript, transcriptLoading, error, successMsg,
episode, localTranscribing, localSummarizing,
templates, selectedTemplate, templateBlocks, enabledBlocks,
showChinese, showTemplateOptions
```

### 3.3 摘要渲染的 if 条件分支

以下是从源码中提取的全部摘要字段渲染条件（第 570-812 行）：

```
summary.tldr                                    → 渐变背景大卡片
summary.investment_signals?.length > 0           → 带看多/看空标签的列表
summary.mentioned_tickers?.length > 0            → 蓝色圆角标签
summary.key_quotes?.length > 0                   → 引用块样式
summary.risk_alerts?.length > 0                  → 红色警告卡片
summary.key_points?.length > 0                   → 编号列表
summary.core_content                             → 纯文本段落
summary.guest_background (非空非默认文案)         → 纯文本段落
summary.unique_insights?.length > 0              → 紫色编号列表
summary.action_items?.length > 0                 → 箭头列表
summary.key_concepts?.length > 0                 → 概念卡片（含 explanation）
summary.examples?.length > 0                     → 左边框段落
summary.resources?.length > 0                    → 圆点列表
summary.tags?.length > 0                         → 标签云
```

**共 15 个条件分支**，每个有独立的样式和布局。

### 3.4 为什么难维护

1. **新增 block 必须改 3 处**: 后端模板定义 → `Summary.to_response` 展开 → 前端这里加 if 渲染
2. **中英文切换嵌套在每个 block 中**: 每个 block 都有 `showChinese && summary.content_zh?.xxx_zh ? ... : summary.xxx` 的三元判断
3. **混合了数据获取和 UI 渲染**: 模板加载、摘要生成、任务轮询和纯 UI 渲染交织在一起
4. **第 690 行残留调试代码**: `{(() => { console.log('DEBUG - summary:', summary); ... })()}` — 应清理

### 3.5 Block 选择 UI

`toggleBlock` 函数和 `enabledBlocks` 状态已实现（第 42-43 行），Block 切换按钮也已渲染（第 538-554 行）。当前存在的体验问题：
- 无法直观看出哪些 block 是默认开启的
- 切换 block 后，已生成的摘要不会自动更新（需要用户手动点击重新生成）
- 没有视觉提示告诉用户"切换后需要重新生成才生效"

---

## 4. PromptTemplatesPanel.jsx 分析

源码: `frontend/src/components/views/settings/PromptTemplatesPanel.jsx`

### 4.1 布局结构

```
PromptTemplatesPanel
├── 左栏: 模板列表
│   ├── 系统模板（只读，带锁图标）
│   └── 用户模板（可编辑/删除）
└── 右栏: 模板详情
    ├── 基本信息（name, display_name, description）
    ├── Blocks 配置（启用/禁用切换）
    ├── Parameters 配置
    └── 操作按钮（保存/复制/删除）
```

### 4.2 功能完成度

| 功能 | 状态 | 备注 |
|------|------|------|
| 模板列表展示 | 完成 | 区分系统/用户模板 |
| 模板详情查看 | 完成 | 包含 blocks 和 parameters |
| 创建用户模板 | 完成 | - |
| 编辑用户模板 | 完成 | blocks 启用/禁用 |
| 复制系统模板 | 完成 | 弹窗输入新名称 |
| 删除用户模板 | 完成 | 系统模板不可删 |
| 初始化系统模板 | 完成 | 列表为空时自动触发 |

### 4.3 体验问题

- Blocks 的启用/禁用与实际生成效果的关系对用户不直观：用户不知道关闭某个 block 后，已生成的摘要中对应字段会怎样
- 没有模板预览功能：无法在保存前看到 prompt 的完整内容
- 系统模板和用户模板的视觉区分仅靠一个锁图标，不够醒目

---

## 5. 前端 API 调用层

源码: `frontend/src/services/api.js`（148 行）

### 5.1 设计

- 使用 axios 实例，baseURL = `/api`
- 响应拦截器统一提取 `response.data`，404 降级为 `console.info`
- 所有 API 调用以对象形式导出：feedsApi, episodesApi, transcriptsApi, summariesApi, promptTemplatesApi, tasksApi, settingsApi, insightsApi, statsApi

### 5.2 特别注意

- `insightsApi.exportPdf` 不走 axios，而是直接创建 `<a>` 标签下载
- `settingsApi` 中 Tavily 相关的前端调用未包含（settings.py 中有 tavily 端点，但 api.js 中的 settingsApi 只包含 llm 相关方法）
- `episodesApi.listTranscribed` 和 `listSummarized` 是前端硬编码的状态过滤快捷方法

---

## 6. 建议拆分方案

### 6.1 EpisodeDetailView 拆分

目标：将 895 行拆为 ~200 行主组件 + 多个独立子组件/hooks。

```
EpisodeDetailView.jsx (~200 行，只做布局和组合)
├── useEpisodeDetail(episodeId)    — 数据加载 hook
│   ├── transcript 状态和加载
│   ├── summary 状态和加载
│   └── episode 状态更新
│
├── useSummary(episodeId, templateName) — 摘要相关 hook
│   ├── templates, selectedTemplate, templateBlocks, enabledBlocks
│   ├── generateSummary()
│   └── toggleBlock()
│
├── EpisodeHeader                  — 标题 + 操作按钮（返回、播放、转录、下载）
├── TranscriptPanel                — 转录 Tab 内容
│   ├── 转录加载/展示
│   ├── 转录触发/费用预估
│   └── 删除/重新转录
├── SummaryPanel                   — 摘要 Tab 内容
│   ├── TemplateSelector           — 模板选择
│   ├── BlockSelector              — Block 切换按钮组
│   ├── SummaryBlockRenderer       — 通用 block 渲染器（核心改进）
│   └── 空状态 / 生成按钮
└── EpisodeInfoTab                 — Info Tab 内容（元信息展示）
```

### 6.2 通用 SummaryBlockRenderer 设计思路

当前的问题：15 个 if 分支，每个字段独立处理。

改进方向：按数据类型通用渲染。

```jsx
// 后端返回 block 描述（需要 API 配合改动）
const blockRenderers = {
  string: (value, title) => <StringBlock title={title} text={value} />,
  list: (items, title) => <ListBlock title={title} items={items} />,
  tags: (items, title) => <TagsBlock title={title} tags={items} />,
  quotes: (items, title) => <QuotesBlock title={title} quotes={items} />,
  signals: (items, title) => <SignalsBlock title={title} signals={items} />,
  concepts: (items, title) => <ConceptsBlock title={title} concepts={items} />,
};

// 前端渲染：按 block 配置的 type 字段分发
summary.blocks.forEach(block => {
  const renderer = blockRenderers[block.type];
  if (renderer) renderer(block.data, block.title);
});
```

**注意**: 这需要后端 API 配合改动（在响应中提供 block 元信息）。如果短期无法改后端，可以前端维护一个 field-to-renderer 的映射表，至少消除 JSX 中的 15 个 if 分支。

### 6.3 独立 Hook 拆分

```
usePlayer()          — 播放状态管理（currentPlaying, isPlaying, audioRef, play, pause, seek）
                       约 60 行，从 App.jsx 抽出

useDataLoader()      — 数据加载（loadData, handleFeedClick, handleRefreshFeed）
                       约 40 行，从 App.jsx 抽出
```

---

## 7. 重构优先级

| 优先级 | 任务 | 预期收益 | 风险 |
|--------|------|----------|------|
| **P0** | EpisodeDetailView 拆分 | 降低最大单文件复杂度（895→~200行），提高可维护性 | 低（纯组件拆分，不改行为） |
| **P1** | 通用 SummaryBlockRenderer | 新增 block 不需要改前端渲染代码 | 中（需要设计 block 类型映射） |
| **P1** | usePlayer hook 独立 | 播放逻辑可复用，App.jsx 减负 | 低 |
| **P2** | useDataLoader hook 独立 | 数据加载逻辑集中管理 | 低 |
| **P2** | feeds/workspaceEpisodes/feedEpisodes 状态下沉 | App.jsx 从 16 个状态减到 ~10 个 | 中（需确认无跨组件依赖） |
| **P3** | 清理第 690 行 DEBUG 日志 | 消除生产环境无用日志输出 | 极低 |

### P0 具体步骤建议

1. 先抽 `useEpisodeDetail` hook（数据获取逻辑）
2. 抽 `TranscriptPanel` 组件（转录 Tab，约 150 行）
3. 抽 `EpisodeHeader` 组件（标题+操作按钮，约 80 行）
4. 抽 `SummaryPanel` 组件（摘要 Tab，约 300 行，包含 TemplateSelector 和 BlockSelector）
5. 主文件保留布局 + 状态组合，目标 200 行以内
6. 每步完成后确认所有功能正常再进行下一步

---

## 8. 组件行数统计

| 组件 | 行数 | 备注 |
|------|------|------|
| EpisodeDetailView.jsx | ~895 | 最大，需拆分 |
| App.jsx | ~449 | 偏大，部分状态可下沉 |
| FeedDetailView.jsx | - | 接收 props，哑组件 |
| PromptTemplatesPanel.jsx | - | 功能完整 |
| Sidebar.jsx | - | 接收 props，哑组件 |
| PlayerBar.jsx | - | 接收 props |
| AIBriefingView.jsx | - | 独立视图 |
| SettingsView.jsx | - | 设置入口容器 |

---

## 9. 技术栈与模式总结

- **状态管理**: 纯 useState + useEffect，无 Redux / Zustand / Context
- **路由**: 无 react-router，通过 view 字段手动切换组件（简易状态机）
- **国际化**: react-i18next（`useTranslation` hook）
- **样式**: TailwindCSS（原子化类名，无 CSS Modules）
- **API 调用**: axios + 统一拦截器，封装为 api.js 中的对象
- **图标**: lucide-react
- **构建**: Vite

**主要架构债务**:
1. App.jsx 是单点状态中心，16 个 state 变量
2. 无路由库，视图切换靠 if-else 链
3. EpisodeDetailView 895 行，承载了过多职责
4. 摘要渲染硬编码 15 个 if 分支，无通用渲染器
