# Upgrade TODO

> 基于 `UPGRADE_PLAN_FINAL.md`、`UPGRADE_ROADMAP_REVIEW.md`、`UPGRADE_ROADMAP.md` 以及当前工作区状态整理，更新于 2026-05-21。

## 执行原则

- 使用 TDD：先补会失败或能证明行为的测试，再改实现，再跑验证。
- 使用原子化 Git：每个提交只表达一个主题，例如 docs、auth、tests、frontend-login、state-refactor。
- 先稳定当前权限地基，再做前端状态管理等大重构。
- 每轮结束必须至少跑目标测试；涉及前端时必须跑 `npm run build`。

## 当前状态

Phase 0 已经完成并拆分提交：

- README / README_CN / 启动说明。
- JWT 登录、注册、当前用户接口。
- 最小管理员接口。
- `owner_id` 数据隔离。
- 前端登录页、账号页、Bearer token 接入。
- 迁移脚本和测试用户脚本。

当前工作区应保持干净。后续任务从 Phase 1 开始，逐个 API 补齐边界状态和权限隔离测试。

## Phase 0: 权限地基收口

目标：让多用户最小版本可用，并保证普通用户不能串数据。

TODO:

- [x] 补齐 `feeds` API 权限隔离测试。
- [x] 补齐 `episodes` API 权限隔离测试。
- [x] 补齐 `transcripts` API 权限隔离测试。
- [x] 补齐 `summaries` API 权限隔离测试。
- [x] 补齐 `settings` API 权限隔离测试。
- [x] 处理真实 MongoDB 集成测试：没有 MongoDB 时 skip，而不是卡住。
- [x] 跑后端目标测试。
- [x] 跑前端构建。
- [x] 拆分提交：
  - `docs: 添加中文说明和升级执行清单`
  - `feat: 添加 JWT 认证和用户数据隔离`
  - `feat: 接入前端登录和账号面板`

验收命令：

```powershell
cd backend
$env:UV_CACHE_DIR = Join-Path (Get-Location) ".uv-cache"
uv run pytest tests/test_auth_api.py tests/test_owner_isolation.py tests/test_feeds_api.py tests/test_episodes_api.py tests/test_transcripts_api.py tests/test_summaries_api.py tests/test_settings_api.py

cd ../frontend
npm run build
```

## Phase 1: API 测试补齐

目标：核心 API 的 CRUD、边界状态、权限隔离都有测试。

TODO:

- [ ] `test_feeds_api.py`
- [x] `test_episodes_api.py`
- [ ] `test_transcripts_api.py`
- [ ] `test_summaries_api.py`
- [ ] `test_settings_api.py`
- [x] `test_tasks_api.py` 扩充 owner_id 场景

重点：

- 400 / 401 / 403 / 404 / 409 都要覆盖。
- 用户隔离优先于覆盖率数字。
- 不依赖真实 MongoDB，优先使用现有 MockDB。

## Phase 2: 错误提示与 Toast

目标：用户能看到错误，而不是只在 console 里看到。

TODO:

- [ ] 新增 Toast provider 和 `useToast`。
- [ ] 新增 ToastContainer。
- [ ] 新增 ErrorBoundary。
- [ ] API 拦截器把错误转成 toast。
- [ ] 401 自动退出登录。
- [ ] 下载、转录、摘要失败时在 UI 显示后端错误消息。

验收：

- [ ] `npm run build`
- [ ] 手动触发 401 / 403 / 404 / 409，确认页面有提示。

## Phase 3: 前端状态管理重构

目标：把 `App.jsx` 从大状态中心拆成上下文和 hooks。

TODO:

- [ ] `AuthContext`
- [ ] `NavigationContext`
- [ ] `DataContext`
- [ ] `PlayerContext`
- [ ] `SettingsContext`
- [ ] `App.jsx` 降到 400 行以内。

验收：

- [ ] 登录、退出、刷新页面可用。
- [ ] 单集详情深链接可用。
- [ ] 播放器保存进度可用。
- [ ] 任务面板跳转可用。
- [ ] `npm run build`

## Phase 4: 数据库与列表性能

目标：500+ episodes 时列表和查询仍然流畅。

TODO:

- [ ] 增加 owner_id 复合索引。
- [ ] `list_episodes` 改 aggregation pipeline。
- [ ] EpisodeCard / FeedCard 加 memo。
- [ ] 图片使用 `loading="lazy"`。
- [ ] 根据实际卡顿情况决定是否引入 `react-window`。

## Phase 5: 响应式与可观测性

目标：早期用户在不同设备上可用，并且错误可追踪。

TODO:

- [ ] Sidebar 移动端 drawer。
- [ ] PlayerBar 小屏压缩布局。
- [ ] 所有触摸按钮 >= 44px。
- [ ] 后端 request_id 中间件。
- [ ] 500 错误返回 request_id。
- [ ] API 文档自动化或继续强化 `docs/api.md`。
