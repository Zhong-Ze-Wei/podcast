# 产品说明与交互演示

PodMaster 是一个本地优先的播客与视频订阅工作台，把 RSS 播客、YouTube 频道和 B 站 UP 主的内容汇入同一个库。从订阅和收听开始，也可以进一步用 AI 理解内容、保留观点、整理周报与月报。

**[项目首页与截图](../README.md)** · **[快速启动指南](./getting-started.md)** · **[本地交互演示](http://localhost:3000/product/index.html#demo)** · [完整文档](./index.md)

## 两个使用视角

- **订阅与收听**：粘贴来源链接，等待同步节目，在最近更新里查看新内容；选择节目收听、调整进度和音量、阅读完整文稿。喜欢的节目、已读状态和收听进度按用户保留。
- **AI 解读与简报**：从完整文稿中保存摘要、议题、原话、新词和方法。单篇分析保存后，周报与月报继续复用，再围绕关注话题整理共性与分歧。观点可以收藏，报告可以导出 PDF。

两个视角共用订阅、文稿与已保存的单篇分析。没有字幕时，本地转写由用户手动触发；使用 AI 需要在应用设置中配置模型服务。

## 本地预览

前端已经运行时，直接访问 **http://localhost:3000/product/index.html**。端口被占用时，使用 Vite 实际启动端口。

也可以直接用浏览器打开该 HTML 文件。页面只使用相对路径的本地资源，没有外部字体、CDN、登录、后端接口或 AI 调用依赖。

单独提供静态服务：

```powershell
python -m http.server 3008 --directory frontend/public/product
```

然后打开 http://localhost:3008/。

## 演示内容

- 默认展示「订阅与收听」，可切换到「AI 解读与简报」；首页与产品思路并列呈现两个视角。
- 快速订阅：填入 RSS、YouTube 频道、B 站 UP 主地址示例，预览来源识别和加入演示库；重复地址不重复添加。YouTube 视频页与 B 站视频页会提示使用频道或 UP 主地址。
- 传统工作台：选择订阅源、自动清除该源的未查看提示；筛选最近 7 天的节目，选择节目并预览文稿。
- 模拟播放器：播放/暂停、进度拖动、后退 15 秒、前进 30 秒、音量滑杆；切换节目后本次会话的进度保留。切到 AI 视角或隐藏页面时暂停模拟计时。
- 五个栏目：核心提要、原话精选、共性与分歧、新词与方法、提到的资料。
- 周报/月报切换：展示同一批已保存单篇分析的复用方式。
- 纸面、双栏、便笺三种演示阅读风格。
- 收藏状态与计数，切换栏目后仍保留本次演示会话的收藏。
- 原话依据卡组：邻卡、前后按钮、方向键、鼠标拖动、手机横滑；首尾停止。
- 应用截图切换与放大，中英文切换，动效暂停与系统减少动态效果偏好。

互动区域中的节目、资料、地址和引文均为演示样例，不是实际节目的分析结论。订阅、未查看状态、收听进度和收藏只保留在当前页面会话，不写入用户账号。播放器模拟进度，不播放真实音频；音量滑杆只预览控件。RSS 在本页仅按地址演示，真正订阅时由应用读取并校验源。

四张 `1600 × 1000` 截图来自项目实际 React 界面，使用本地 UI fixture 加演示数据：`listening.jpg` 为节目文稿和底部播放器，`library.jpg` 为订阅库，`analysis.jpg` 为单篇 AI 解读，`briefing.jpg` 为 AI 简报。演示封面为项目自带 SVG，不依赖远程节目封面。重新拍摄时替换对应 JPG 即可。

## GitHub Pages

工作流在 [`.github/workflows/product-pages.yml`](../.github/workflows/product-pages.yml)。仅发布 `frontend/public/product` 目录；运行方式为手动触发。

1. 将页面与工作流提交到仓库默认分支。
2. 在仓库 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。
3. 在 **Actions → Publish product page → Run workflow**，选择默认分支运行。
4. 等待工作流成功，查看部署给出的实际地址。此仓库预期地址为 **https://zhong-ze-wei.github.io/podcast/**。

本地完成页面并不等于已上线，发布状态以工作流结果为准。工作流上传静态文件，无需安装应用依赖或启动后端。动作版本与权限参考 [GitHub Pages 官方工作流说明](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)。

页面不假定站点部署在域名根目录，相对资源路径可用于仓库子路径或其他静态托管服务。

## 页面维护

页面源码：[`frontend/public/product/index.html`](../frontend/public/product/index.html)。样式和交互分别在同目录的 `style.css`、`demo.js`，截图与 SVG 在 `assets/`。
