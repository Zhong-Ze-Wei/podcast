# 项目待办 (Backlog)

> 记录已调研、未实施的事项。每项包含背景、结论与待办拆解，实施后移入对应文档。

---

## 1. 视频源接入：YouTube / Bilibili 字幕与音频

**调研日期**: 2026-09-27（本机实测）
**目标**: 订阅管线支持视频源——YouTube / B站 URL → 字幕或音频 → 现有 transcript / Whisper 管线 → 摘要，复用播客处理链路。

### 实测结论

#### YouTube — 可行，双路径打通

| 路径 | 实测结果 |
|------|----------|
| `youtube-transcript-api` | 样本视频 `vif8NQcjVf0`（Lex × Jensen Huang）：手动英文字幕 2110 段 / 12.6 万字符 / 带时间戳，另有自动字幕与俄语翻译版可选 |
| `yt-dlp --write-subs` | 同一视频下载 189KB 标准 VTT，内容一致，可作为备用路径 |

- VTT 是 `transcript_fetcher.py` 已支持的格式，字幕无需下载音频即可直接进管线
- 前置条件：需代理（本机 `127.0.0.1:7890` 实测可用）；YouTube 官方 Data API 的 `captions.download` 仅限视频上传者本人使用，社区库方案是实际可行路线
- 已知限制（来自 `youtube-transcript-api` README 声明）：云服务器 IP 会被 YouTube 拒绝（本地运行无此问题）；cookie 认证当前失效，年龄受限视频拿不到

#### Bilibili — 字幕基本不可得，音频兜底可行

- **无登录实测**（热门榜 4 个真实视频：`BV1HRa46AER2` / `BV17WhX6KEWn` / `BV1LxaP69EJy` / `BV1ZfhD6XEGk`）：全部仅有弹幕 XML，无 CC 字幕、无 AI 字幕；其中 1 个触发风控（报 "deleted or geo-restricted"）
- **带登录 cookie**：AI 字幕理论上可见，本轮**未验证**——Edge 运行中锁定 cookie 数据库（yt-dlp 已知问题 #7271）。需导出 B站 cookies.txt 后复测
- **音频流下载**：实测成功（`bestaudio` m4a，速度正常）→ 本地 Whisper 转写是唯一可 100% 覆盖视频的路线

### 工程要点

- 依赖已装入后端 venv：`yt-dlp 2026.08.19`、`youtube-transcript-api`（**未写入 pyproject.toml**，正式集成时固化版本）
- 系统无独立 ffmpeg：yt-dlp 的 m4a→mp3 转码会失败；Whisper 管线使用 `imageio_ffmpeg` 自带二进制，且 faster-whisper 原生支持 m4a——集成时**跳过转码直接用 m4a**
- B站接口走 wbi 签名（yt-dlp 日志实测可见 `Downloading wbi sign`），登录态由浏览器 cookie 提供
- 实测样本产物：`labs/subtitle-probe/`（B站 m4a 音频 + YouTube VTT 字幕）

### 待办拆解

- [ ] **P0 · YouTube 源适配器**：URL → `youtube-transcript-api` 取字幕 → transcript 管线；取不到时回退 `yt-dlp` 下音频 → Whisper
- [ ] **P1 · B站音频路径**：URL → `yt-dlp bestaudio` → Whisper 转写（主路径）
- [ ] **P2 · B站 AI 字幕复测**：拿到 cookies.txt 后验证 AI 字幕覆盖率与内容质量，再决定是否实现"字幕优先"路径
- [ ] **P2 · Feed 模型扩展**：`feed.type = rss | youtube | bilibili`，episode 增加视频元数据字段（bv 号 / video id / UP 主）

---

## 2. Lex Fridman RSS 缺失时长字段

**诊断日期**: 2026-09-27

- 实时拉取该 feed（503 条），恰好 55 条无 `itunes:duration`，且这些条目的 enclosure length 均为 5242880（整 5MB 占位值）；数据库中 55 个零时长剧集与之完全吻合
- **结论**: 源数据缺失，非解析 bug；`_parse_duration` 对存在的时长（含 `HH:MM:SS`）全部解析正确
- 待办：
  - [ ] 下载完成后用实际音频探测时长（faster-whisper 转写结果自带 duration）回填 `episode.duration`
  - [ ] 前端对零时长显示 "—" 而非 "00:00"
