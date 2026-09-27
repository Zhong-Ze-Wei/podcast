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

#### Bilibili — 登录后 AI 字幕可用但有质量风险，音频兜底仍为主路径

- **无登录实测**（热门榜 4 个真实视频：`BV1HRa46AER2` / `BV17WhX6KEWn` / `BV1LxaP69EJy` / `BV1ZfhD6XEGk`）：全部仅有弹幕 XML，无 CC 字幕、无 AI 字幕；其中 1 个触发风控（报 "deleted or geo-restricted"）
- **登录后实测**（2026-09-27，浏览器登录态下于 bilibili.com 页面上下文调用）：
  - 技术路径全通：`x/web-interface/view` 拿 aid/cid → `x/player/v2`（无需 wbi 签名）拿 AI 字幕列表 → `subtitle_url` 带 `Referer: bilibili.com` 从服务端下载 JSON（`{body: [{from, to, content}]}` 格式，与 transcript segments 可直接映射）
  - 覆盖率：热门榜 7/7 有效视频有 `ai-zh` AI 中文字幕（部分还带 ai-en/ai-ja 翻译）
  - **质量风险一：内容串台**。实锤 1 例——"溶酶体"科普视频（456s）返回了股票行情口播字幕，且字幕时间轴达 518s 超出视频时长（`last.from > 视频时长` 可作为检测特征）
  - **质量风险二：可见性不稳定**。同一视频两次查询 `player/v2`，一次返回 ai-zh、一次为空
  - **质量风险三：密度不稳**。296s 视频仅 31 行字幕（约 9.5s/行），偏稀疏
- **音频流下载**：实测成功（`bestaudio` m4a，速度正常）→ 本地 Whisper 转写仍是唯一可 100% 覆盖且内容必然正确的路线
- **登录态获取**：`SESSDATA`（鉴权核心 cookie）为 httpOnly，页面 JS 无法读取，不能从浏览器自动导出；集成时需用户在设置页手动粘贴 SESSDATA，或提供 cookies.txt
- **集成策略结论**：AI 字幕作快路径（拿到且通过时间轴/密度校验即免转写），失败或可疑时回退 yt-dlp 音频 + Whisper

### 工程要点

- 依赖已装入后端 venv：`yt-dlp 2026.08.19`、`youtube-transcript-api`（**未写入 pyproject.toml**，正式集成时固化版本）
- 系统无独立 ffmpeg：yt-dlp 的 m4a→mp3 转码会失败；Whisper 管线使用 `imageio_ffmpeg` 自带二进制，且 faster-whisper 原生支持 m4a——集成时**跳过转码直接用 m4a**
- B站接口走 wbi 签名（yt-dlp 日志实测可见 `Downloading wbi sign`），登录态由浏览器 cookie 提供
- 实测样本产物：`labs/subtitle-probe/`（B站 m4a 音频 + YouTube VTT 字幕）

### 待办拆解

- [x] **P0 · YouTube 源适配器**（已完成，2026-09-27）：`POST /api/video-import/youtube`，URL → 字幕 → 自动建"YouTube 导入"feed + episode（状态 transcribed）+ transcript；端到端实测真实视频成功（2110 段 / 2.3 万词）
- [x] **P1 · 频道订阅**（已完成，2026-09-27）：粘贴 YouTube 频道页 / B站空间页地址即可订阅，复用现有添加订阅与刷新入口；实测 Dwarkesh 频道首批 15 视频 15/15 带字幕。B站需在 `.env` 配置 `BILI_SESSDATA` 后刷新
- [ ] **P2 · B站补拉字幕**：刷新时对已入库但无 transcript 的 episode 重试 AI 字幕（AI 字幕是异步生成的，发布当天常拿不到；实测首轮 30 投稿 17 条有字幕）
- [ ] **P2 · B站字幕失败兜底**：无 AI 字幕或校验拒收的视频，下载音频走 Whisper 转写（`yt-dlp bestaudio`）
- [ ] **P2 · WhisperX 分人转写开关**：YouTube/B站导入支持"强制 WhisperX 说话人分离"模式
- [ ] **P3 · 前端展示优化**：订阅列表区分源类型徽标（RSS / YouTube / B站）

---

## 2. AI 播客种子频道清单（YouTube）

**来源**: [swyxio/ai-notes "Good AI Podcasts and Newsletters"](https://github.com/swyxio/ai-notes/blob/main/Resources/Good%20AI%20Podcasts%20and%20Newsletters.md)（Latent Space 创始人维护，Andrew Chen / Lex Fridman 公开推荐），交叉参考 2026 年多个工程师向榜单。
**字幕实测**: 2026-09-27，四个头部频道最新一期 4/4 有英文字幕（youtube-transcript-api，走代理）。

### 研究者访谈（长视频，字幕实测标注）

- Dwarkesh Patel Podcast — **手动字幕实测 ✓**（1.4 万词/期；swyx 评："The new Lex Fridman"）
- Machine Learning Street Talk (Tim Scarfe) — **手动字幕实测 ✓**（2.6 万词/期，safety/哲学向深技术访谈）
- Latent Space (swyx) — **自动字幕实测 ✓**（2.9 万词/期，AI 工程向）
- Cognitive Revolution (Nathan Labenz) — **自动字幕实测 ✓**（2.6 万词/期）
- The Gradient Podcast / TWIML AI (Sam Charrington) / Practical AI / Deep Papers (Arize) / Interconnects Audio (Nathan Lambert)

### 新闻 / 评论频道（YouTube）

- Last Week in AI、Yannic Kilcher（论文精读）、Sasha Rush（srush_nlp）、AI Brief (NLW)、AI Explained、ThursdAI

### 公司 / VC 播客

- The DeepMind Podcast、Gradient Dissent (W&B)、Robot Brains (Pieter Abbeel)、High Agency (Raza Habib)
- No Priors (Sarah Guo & Elad Gil)、Training Data (Sequoia)、Unsupervised Learning (Redpoint)

### 字幕与说话人分离的现状

- YouTube 手动/自动字幕均为**纯文本 + 时间戳，不带说话人标注**
- 需要"分人"文稿时走本地 WhisperX：`whisperx_service.py` 已支持 pyannote 说话人分离（`.env` 中 `WHISPERX_DIARIZE=1` 已启用，HF_TOKEN 已配置），依赖已全部安装
- 待办：[ ] "YouTube 导入优先字幕、可选强制 WhisperX 分人转写"的模式开关

---

## 3. Lex Fridman RSS 缺失时长字段

**诊断日期**: 2026-09-27

- 实时拉取该 feed（503 条），恰好 55 条无 `itunes:duration`，且这些条目的 enclosure length 均为 5242880（整 5MB 占位值）；数据库中 55 个零时长剧集与之完全吻合
- **结论**: 源数据缺失，非解析 bug；`_parse_duration` 对存在的时长（含 `HH:MM:SS`）全部解析正确
- 待办：
  - [ ] 下载完成后用实际音频探测时长（faster-whisper 转写结果自带 duration）回填 `episode.duration`
  - [ ] 前端对零时长显示 "—" 而非 "00:00"
