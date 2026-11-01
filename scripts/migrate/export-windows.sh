#!/usr/bin/env bash
# 导出全部迁移数据到 OUT_DIR（默认 E:\podcast-migration）。
# 在 Windows 上运行；产物拷到 Mac 后由 restore-mac.sh 恢复。
#
#   cd podcast && bash scripts/migrate/export-windows.sh
#
# 产物：
#   db/podcast.archive.gz   MongoDB 全库（mongodump gzip）
#   media.tar.gz            backend/media   （封面 + 本地音频）
#   runtime.tar.gz          backend/.runtime（简报正文等文件数据）
#   env.dotenv              backend/.env    （密钥，勿入 Git）
#   SHA256SUMS.txt          校验和，Mac 端恢复前先校验
set -euo pipefail
cd "$(dirname "$0")/../.."

OUT="${1:-/e/podcast-migration}"
NETWORK="podcast_default"

echo "==> 输出目录: $OUT"
mkdir -p "$OUT/db"

echo "==> 0/5 确认数据库里没有绝对路径（有则先跑 rewrite_windows_paths.py --apply）"
ABS=$(docker exec podcast-mongo mongosh --quiet --eval \
  'db.getSiblingDB("podcast").episodes.countDocuments({$or:[{local_path:{$regex:"^[A-Z]:"}},{audio_path:{$regex:"^[A-Z]:"}}]})')
if [ "$ABS" != "0" ]; then
  echo "    仍有 $ABS 条绝对路径，中止。请先执行："
  echo "    docker exec -i podcast-backend python - < scripts/migrate/rewrite_windows_paths.py --apply"
  exit 1
fi

echo "==> 1/5 导出 MongoDB"
MSYS_NO_PATHCONV=1 docker run --rm --network "$NETWORK" \
  -v "$(cygpath -w "$OUT"):/out" mongo:8 \
  mongodump --host mongo --db podcast --gzip --archive=/out/db/podcast.archive.gz

echo "==> 2/5 打包 media（约 1GB，需要几分钟）"
tar -czf "$OUT/media.tar.gz" -C backend media

echo "==> 3/5 打包 runtime（简报正文）"
tar -czf "$OUT/runtime.tar.gz" -C backend .runtime

echo "==> 4/5 复制 .env"
cp backend/.env "$OUT/env.dotenv"
chmod 600 "$OUT/env.dotenv" 2>/dev/null || true

echo "==> 5/5 生成校验和"
cd "$OUT" && sha256sum db/podcast.archive.gz media.tar.gz runtime.tar.gz env.dotenv > SHA256SUMS.txt

echo
echo "完成。产物清单："
ls -lh "$OUT"
echo
echo "把整个 $OUT 目录拷到 Mac（U盘 / AirDrop / 局域网 scp），"
echo "然后按 docs/mac-migration.md 执行 restore-mac.sh。"
