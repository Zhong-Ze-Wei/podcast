# ADR-006: YouTube 字幕抓取——不可行路线与现行策略

**状态**: 已实施（2026-10 实测收敛）

**背景**: 订阅的 YouTube 频道需要字幕（timedtext）供 AI 简报/摘要使用。YouTube 对数据中心 IP 有多层反爬，实测一台本地机器 + Clash 代理的场景下踩遍了所有坑。本 ADR 记录结论，避免重复走死路。

## 不可行路线（都实测过，别再试）

| 路线 | 结果 | 死因 |
|---|---|---|
| 免费代理池 | 500 个审计样本 0 可用 | 全是数据中心 IP，全部撞 bot 墙 |
| youtube-transcript-api 直连 | 不可用 | requests 的 TLS 指纹被识别掐线 |
| watch 页签名 URL 直拉 timedtext | 拿到 URL 也白搭 | ASR 轨道被 `exp=xpe` 毒化：带参数返回 200 空体，剥掉参数 404 |
| 公共 Invidious 实例 | 列表能出、正文全空 | 同样被上游空响应卡死 |
| PO Token（bgutil 服务） | 单独无效 | 解决的是播放流风控，不解 IP 信誉 bot 墙 |
| 直连 innertube API 换客户端 | 404 | 手写客户端版本串会过期，追不动 |
| 多路并发抓取 | 更快耗尽配额 | timedtext 限流按 IP 也按视频算；**对同一视频反复重试会加深它自身的限流** |

## 现行策略（实测可行）

1. **三层降级链**：youtube-transcript-api → curl_cffi 伪装 Chrome 拉 watch 页 → yt-dlp
2. **yt-dlp 层的关键配方**：登录态 Cookie（`YOUTUBE_COOKIES`，Netscape cookies.txt）+ `player_client=mweb` + `ignore_no_formats_error`——同时绕过 bot 墙和 `exp=xpe`
3. **串行低速**：单出口、每集间隔 5-8 秒；每成功约 4 集主动轮换 Clash 出口（摊薄单 IP 配额）
4. **429 处理**：换出口、直接下一集，**绝不立刻重试原视频**（见上表最后一条）
5. **错误要分清**："元数据里有字幕轨但没下到文件" = 限流；"元数据里就没有轨" = 频道主真没开字幕（永久跳过，不重试）
6. **自动补捞**：每 30 分钟扫 8 集，跳过已确认无字幕的

**配置**: `backend/.env` 的 `YOUTUBE_PROXY`（Clash 专用端口）、`CLASH_API_URL/SECRET`（轮换出口用）、`YOUTUBE_COOKIES`（F12 复制整段 Cookie 请求头；等同账号凭证，已 gitignore）

**取舍**:
- 选了：慢而稳。每天自动啃一点，配额冷却了自然收
- 成本：Cookie 有账号风险（建议小号）；单账号单出口吞吐有限
- 工具：`backend/scripts/backfill_with_cookies.py` 手动补存量
