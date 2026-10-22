# 后端镜像：Flask + 抓取/字幕/导出依赖
# 本地 AI（torch / faster-whisper / whisperx）不在镜像内，见 requirements.docker.txt 顶部说明。
FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    FLASK_HOST=0.0.0.0 \
    FLASK_PORT=5000 \
    FLASK_DEBUG=0 \
    # 容器内 Mongo 由 compose 提供，run.py 不再尝试拉起 Docker
    MONGO_MANAGED=0

# weasyprint 导出 PDF 需要的系统库
RUN apt-get update && apt-get install -y --no-install-recommends \
        libpango-1.0-0 libpangoft2-1.0-0 libcairo2 libgdk-pixbuf-2.0-0 \
        libffi-dev libjpeg62-turbo libopenjp2-7 shared-mime-info \
        ffmpeg curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.docker.txt ./
RUN pip install --no-cache-dir -r requirements.docker.txt

COPY . .

# 运行期数据落在挂载卷里，镜像内只留目录骨架
RUN mkdir -p /app/media/audio /app/media/covers /app/media/temp /app/.runtime

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=5s --start-period=40s --retries=3 \
    CMD curl -fsS http://127.0.0.1:5000/api/settings/refresh > /dev/null || exit 1

CMD ["python", "run.py"]
