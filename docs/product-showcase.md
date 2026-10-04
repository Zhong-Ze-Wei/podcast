# 静态产品介绍页

页面源码：[`frontend/public/product/index.html`](../frontend/public/product/index.html)。样式和交互分别在同目录的 `style.css`、`demo.js`，截图与 SVG 在 `assets/`。

## 本地预览

前端已经运行时，直接访问 **http://localhost:3000/product/index.html**。端口被占用时，使用 Vite 实际启动端口。

也可以直接用浏览器打开该 HTML 文件。页面只使用相对路径的本地资源，没有外部字体、CDN、登录、后端接口或 AI 调用依赖。

单独提供静态服务：

```powershell
python -m http.server 3008 --directory frontend/public/product
```

然后打开 http://localhost:3008/。

## 演示内容

- 五个栏目：核心提要、原话精选、共性与分歧、新词与方法、提到的资料。
- 周报/月报切换：展示同一批已保存单篇分析的复用方式。
- 纸面、双栏、便笺三种演示阅读风格。
- 收藏状态与计数，切换栏目后仍保留本次演示会话的收藏。
- 原话依据卡组：邻卡、前后按钮、方向键、鼠标拖动、手机横滑；首尾停止。
- 应用截图切换与放大，中英文切换，动效暂停与系统减少动态效果偏好。

互动区域中的节目、资料和引文均为演示样例，不是实际节目的分析结论。收藏只保留在当前页面会话，不写入用户账号。

三张 `1600 × 1000` 截图来自项目实际 React 界面，使用本地 UI fixture 加演示数据：`briefing.jpg` 为 AI 简报，`library.jpg` 为订阅库，`analysis.jpg` 为传统模式的单篇 AI 解读。演示封面为项目自带 SVG，不依赖远程节目封面。重新拍摄时替换对应 JPG 即可。

## GitHub Pages

工作流在 [`.github/workflows/product-pages.yml`](../.github/workflows/product-pages.yml)。仅发布 `frontend/public/product` 目录；运行方式为手动触发。

1. 将页面与工作流提交到仓库默认分支。
2. 在仓库 **Settings → Pages → Build and deployment → Source** 选择 **GitHub Actions**。
3. 在 **Actions → Publish product page → Run workflow**，选择默认分支运行。
4. 等待工作流成功，查看部署给出的实际地址。此仓库预期地址为 **https://zhong-ze-wei.github.io/podcast/**。

本地完成页面并不等于已上线，发布状态以工作流结果为准。工作流上传静态文件，无需安装应用依赖或启动后端。动作版本与权限参考 [GitHub Pages 官方工作流说明](https://docs.github.com/en/pages/getting-started-with-github-pages/using-custom-workflows-with-github-pages)。

页面不假定站点部署在域名根目录，相对资源路径可用于仓库子路径或其他静态托管服务。
