#!/usr/bin/env bash
# 在 Mac 上恢复 Windows 导出的迁移包（export-windows.sh 的产物）。
#
#   git clone <repo> podcast && cd podcast
#   cp -r /path/to/podcast-migration ~/podcast-migration
#   bash scripts/migrate/restore-mac.sh ~/podcast-migration
#
# 前置：已安装 Docker Desktop（Apple Silicon 用 arm64 镜像，compose 会自动重建）。
set -euo pipefail
cd "$(dirname "$0")/../.."

SRC="${1:?用法: restore-mac.sh <迁移包目录>}"
SRC="${SRC%/}"

echo "==> 0/6 校验迁移包完整性"
(cd "$SRC" && shasum -a 256 -c SHA256SUMS.txt)

echo "==> 1/6 安装 .env（密钥不进 Git，单独携带）"
cp "$SRC/env.dotenv" backend/.env
chmod 600 backend/.env

echo "==> 2/6 还原媒体与简报文件"
tar -xzf "$SRC/media.tar.gz" -C backend
tar -xzf "$SRC/runtime.tar.gz" -C backend

echo "==> 3/6 启动 MongoDB 并等待就绪"
docker compose up -d mongo
for i in $(seq 1 30); do
  docker exec podcast-mongo mongosh --quiet --eval "db.adminCommand('ping').ok" >/dev/null 2>&1 && break
  sleep 2
done

echo "==> 4/6 导入数据库"
docker run --rm --network podcast_default \
  -v "$(cd "$SRC" && pwd)/db:/dump:ro" mongo:8 \
  mongorestore --host mongo --gzip --archive=/dump/podcast.archive.gz --drop

echo "==> 5/6 重建并启动全部服务（arm64 重新构建，不复制 Windows 镜像）"
docker compose up -d --build

echo "==> 6/6 等待健康检查"
for i in $(seq 1 30); do
  B=$(docker inspect podcast-backend --format '{{.State.Health.Status}}' 2>/dev/null || echo starting)
  [ "$B" = "healthy" ] && break
  sleep 4
done
docker compose ps

echo
echo "打开 http://127.0.0.1:3000 验证。"
echo "注意 .env 里 YOUTUBE_PROXY / CLASH_API_URL 指向 host.docker.internal:7890，"
echo "Mac 上需运行本机代理（任意端口改 .env 即可），否则 YouTube 抓取会失败。"
