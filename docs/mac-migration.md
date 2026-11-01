# 迁移到 Mac：完整操作手册

## 迁移什么、为什么

| 数据 | 载体 | 为什么这样迁 |
|---|---|---|
| 代码 | Git / GitHub | 版本历史、差异、可回滚；Mac 上 `git clone` 即得 |
| 依赖定义 | `pyproject.toml` + `uv.lock`（已入 Git） | 环境不可移植（Windows 二进制/绝对路径），lock 文件保证 Mac 重建时版本逐字节一致 |
| MongoDB | `mongodump` gzip 归档 | 官方工具保真（集合/索引/类型）；直接拷卷文件是 WiredTiger 内部格式，跨版本跨架构有风险 |
| `backend/media` | tar 包 | 普通文件（封面/本地音频） |
| `backend/.runtime` | tar 包 | 简报正文是文件不是数据库记录 |
| `backend/.env` | 单独拷贝 | 含 YouTube Cookie / API Key，**绝不入 Git** |

不可迁移项（按设计放弃）：
- `.venv` / `node_modules` / 镜像：平台绑定，Mac 重建（`uv sync` / `npm ci` / `compose build`）
- 本地 WhisperX 模型（`E:\models\tts`）与 `WHISUBE_DEVICE=cuda`：Mac 无 CUDA；平台字幕路径不受影响

## Windows 端（导出，做一次）

```bash
# 1. 推代码
git push origin main

# 2. 导数据包（含路径校验、mongodump、打包、校验和）
bash scripts/migrate/export-windows.sh
# 产物在 E:\podcast-migration\
```

脚本会先确认数据库无 Windows 绝对路径（`local_path` 已改写为 MEDIA_ROOT 相对路径，
跨平台通用）。若检查不过，按提示跑 `rewrite_windows_paths.py --apply`。

## 传输

把 `podcast-migration/` 整个目录拷到 Mac：U盘、AirDrop 或局域网 `scp -r`。
共约 1.2 GB（媒体占大头）。

## Mac 端（恢复）

```bash
# 0. 装 Docker Desktop + git；克隆
git clone <你的仓库地址> podcast && cd podcast

# 1. 恢复数据 + 起服务（一条命令全做完）
bash scripts/migrate/restore-mac.sh ~/podcast-migration

# 2. 验证
open http://127.0.0.1:3000
```

Apple Silicon 会自动用 arm64 基础镜像重建，无需任何改动。

## Mac 端需要手工调整的 .env 项

| 项 | 处理 | 原因 |
|---|---|---|
| `YOUTUBE_PROXY` / `CLASH_API_URL` | 指向 Mac 上的代理（`http://host.docker.internal:<port>`）或留空直连 | Mac 网络环境不同；容器内 127.0.0.1 指向自身 |
| `WHISPER_DEVICE=cuda` | 删除或注释 | Mac 无 CUDA |
| `AUTH_DEV_AUTO_LOGIN` / `AUTH_DEV_TRUSTED_NETWORKS` | 仅本机使用保留；**一旦局域网开放必须删除** | 否则内网任何设备可免登录为管理员 |
| 其余（LLM、SESSDATA、Cookie） | 原样可用 | 与平台无关 |

## 远程访问（局域网 1:1 访问）

`docker-compose.yml` 已把前端发布为 `3000:80`（全网卡），Mac 上同一局域网的
手机 / 其他电脑直接访问 `http://<Mac的IP>:3000` 即可，后端无需暴露。

开放前必做两件事：
1. 删除 `.env` 里 `AUTH_DEV_AUTO_LOGIN` 与 `AUTH_DEV_TRUSTED_NETWORKS`
   （现在信任全部私有网段，等于内网免密管理员）
2. 确认 `AUTH_REQUIRED=1`（默认已开）

仅本机自用则什么都不用改：后端只绑 `127.0.0.1`。

## 常见坑

- **`.env` 出现 `unexpected character "\ufeff"`**：Windows 记事器写入的 BOM，
  用 VS Code 重存为 UTF-8（无 BOM）
- **Mongo 起不来报 featureCompatibilityVersion**：镜像必须 >= 你数据的版本（当前 8）
- **简报正文消失**：`backend/.runtime` 是绑定挂载，克隆后若空则历史简报全空——
  务必走本手册的 tar 恢复
- **Windows 与 Mac 同时跑同一份数据**：数据在各自机器上独立，双向改会分叉；
  切换机器前重新导出/导入
