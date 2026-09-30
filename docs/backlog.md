# 项目待办 (Backlog)

> 只收"已调研、未实施"的事项与产品决策记录；完成的移入正式文档（架构/数据库/API），此处仅留一行索引。调研数据有复用价值的整段保留。

---

## 1. 视频源接入（2026-09-27/28 调研，主体已实施）

已上线（细节见[架构概览](./architecture.md)）：三源订阅分流、YouTube 字幕、B站 wbi + AI 字幕（四重校验防串台）、手动"立即转写"（WhisperX）、来源徽标、无字幕人话原因、任务进度人话化、刷新节流 2.5s（实测 1.2s 仍偶发触发 B站风控）。

**产品决策（定稿，不再重议）**：接口捞字幕全自动；本地转写一律手动（算力由人控制）。"发布超 3 天无字幕自动进转写队列"的提议已被此决策否决。

### 仍待做

- [ ] **P2 · B站视频在线播放**：复用 YouTube 流代理思路（`resolve_stream_url` + Range 透传），B站 dash 音频流需带 Referer。改动集中在 `youtube_service` 旁新增 bilibili 对应方法 + `_proxy_stream` 支持
- [ ] **P2 · WhisperX 分人转写开关**：导入时可选"强制 WhisperX 说话人分离"（依赖已装好：`WHISPERX_DIARIZE` + `HF_TOKEN`）
- [ ] **P3 · 订阅列表源类型徽标**：Sidebar 订阅项区分 RSS / YouTube / B站图标（剧集卡片的平台图标兜底已做，订阅列表未做）

### 调研存档：实测数据（2026-09-27）

- **YouTube**：`youtube-transcript-api` 样本视频 2110 段手动字幕 / 12.6 万字符；yt-dlp VTT 备用路径一致。官方 Data API `captions.download` 仅限上传者本人，社区库是实际路线。云服务器 IP 会被 YouTube 拒（本地运行无此问题）
- **B站**：无登录时热门榜视频普遍无字幕可拉；登录（SESSDATA）后技术路径全通（`player/wbi/v2`）。AI 字幕质量两极：正确时 3861 段/4.5 万字秒级零成本，但旧 `player/v2` 接口有系统性串台（28 集中招，已清洗+接口切换）；字幕异步生成，新视频当天普遍没有
- **工程要点**：yt-dlp 的 m4a→mp3 转码会因系统无独立 ffmpeg 失败，Whisper 管线用 `imageio_ffmpeg` 自带二进制，**跳过转码直接用 m4a**；SESSDATA 为 httpOnly，只能用户手动复制粘贴（F12 → Application → Cookies）

---

## 2. AI 播客种子频道清单（YouTube，2026-09-27 实测）

来源：[swyxio/ai-notes "Good AI Podcasts and Newsletters"](https://github.com/swyxio/ai-notes/blob/main/Resources/Good%20AI%20Podcasts%20and%20Newsletters.md)。字幕实测 4 头部频道 4/4 可拉（走代理）。

- **研究者访谈**（长视频）：Dwarkesh Patel（已订阅）、Machine Learning Street Talk、Latent Space、Cognitive Revolution、TWIML AI、Practical AI、Interconnects Audio
- **新闻/评论**：Last Week in AI、Yannic Kilcher（论文精读）、AI Brief (NLW)、AI Explained
- **公司/VC**：The DeepMind Podcast、Gradient Dissent (W&B)、Robot Brains、No Priors、Training Data (Sequoia)

注意：YouTube 手动/自动字幕均无说话人标注；要分人文稿需走 WhisperX（见上方开关待办）。

---

## 3. Lex Fridman RSS 缺失时长（2026-09-27 诊断）

源数据缺失：503 条中 55 条无 `itunes:duration` 且 enclosure length 均为 5MB 占位值，非解析 bug。

- [ ] 下载/转写完成后用实际时长回填 `episode.duration`（whisperx 结果自带 duration）
- [ ] 前端对零时长显示 "—" 而非 "00:00"

---

## 4. 数据治理后续（2026-09-30 评审产出）

已完成（决策记录见[数据库设计·数据治理决策](./database.md#数据治理决策)）：重复订阅合并 + 入口 URL 去重、个人状态按用户隔离（user_episode_states）、settings 遗留清理、文档治理章节。动库前已有全量 mongodump（`backups/`，不入 Git）。

- [ ] **P1 · 定时备份**：mongodump 挂 Windows 计划任务，每日一份留 7 天。B站字幕等 AI 产物不可再生（SESSDATA 失效后拉不回来），值得自动化
- [ ] **P2 · 时区统一**：全库 naive `utcnow()`（Python 已 DeprecationWarning，测试里 250+ 条警告），新代码用 timezone-aware，存量随迭代迁移
- [ ] **P2 · check_error 错误码化**：现为英文自由文本 + 前端人话映射（`_humanize_subtitle_error` 已做一半），理想形态后端存错误码、文案归 i18n
