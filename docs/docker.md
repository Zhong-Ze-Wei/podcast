# 容器部署说明

## 一键启动

```bash
docker compose up -d --build
```

打开 <http://127.0.0.1:3000>。首次构建约 2-4 分钟（后端装依赖为主）。

```bash
docker compose logs -f backend   # 看后端日志
docker compose down              # 停止（数据保留）
docker compose up -d             # 再次启动
```

## 组成

| 服务 | 镜像 | 端口 | 作用 |
|---|---|---|---|
| `frontend` | nginx + 静态产物 | 3000 → 80 | 托管前端，并把 `/api` 反代到后端 |
| `backend` | python:3.13-slim | 5000（仅本机） | Flask API、抓取、字幕队列 |
| `mongo` | mongo:8 | 不对外 | 数据库 |

三个具名卷：`podcast-mongo-data`（复用旧卷）、`podcast-media`（封面/音频/临时文件）、`podcast-runtime`（简报缓存）。

## 数据

`podcast-mongo-data` 声明为 `external`，指向旧版单容器 `podcast-mongodb` 用的同名卷，
所以既有的订阅与节目数据直接可用，不需要迁移。

如果之前跑过独立的 `podcast-mongodb` 容器，先停掉它再启动 compose，否则 27017 会冲突：

```bash
docker stop podcast-mongodb
```

## 配置

后端读 `backend/.env`，compose 用 `env_file` 注入。有几点在容器里必须不同：

- `MONGO_URI` 由 compose 固定为 `mongodb://mongo:27017`，`.env` 里写 localhost 也没关系
- `YOUTUBE_PROXY` / `CLASH_API_URL` 由 compose 固定为 `host.docker.internal`：
  容器里的 `127.0.0.1` 指向容器自己，访问不到宿主上的 Clash
- `AUTH_DEV_TRUSTED_NETWORKS` 放行容器内网网段，让经 nginx 进来的请求仍按本机免登录处理

宿主的 Clash 需要允许局域网连接（否则容器访问不到 7890）。

## 不包含本地 AI

镜像里没有 torch / faster-whisper / whisperx —— 它们会把镜像撑到 12GB 以上。
平台字幕（YouTube auto-caption、B站 AI 字幕）不受影响。

需要本地 WhisperX 转写时，在宿主按 `setup_local_ai.py` 安装，并用宿主方式运行后端；
或者自行把 `requirements.docker.txt` 换回 `pyproject.toml` 的 `local-ai` 组。

## 端口冲突

5000 只绑定 `127.0.0.1`，不对外暴露。若宿主已有进程占用 5000（例如之前手动跑过 `run.py`），
容器会起不来，先结束旧进程：

```bash
netstat -ano | findstr :5000      # 找到 PID
taskkill /PID <pid> /F
```
