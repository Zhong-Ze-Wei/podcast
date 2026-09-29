# PodMaster — Local-first Podcast & Video Subscription Workbench

Subscribe to RSS podcasts, YouTube channels, and Bilibili uploaders. Auto-fetch subtitles/transcripts, transcribe on demand locally, generate AI summaries and daily briefings. One shared library for the whole family — with per-user read/star/play states.

> 中文说明：[README_CN.md](./README_CN.md)

## Understand it in 30 seconds

- **Paste any source URL** — RSS feed, `youtube.com/@channel`, or `space.bilibili.com/<mid>` — and the backend auto-detects the type.
- **Subtitles are auto-fetched** when the platform provides them (Bilibili AI subtitles pass a four-way cross-talk validation before storage). **Local WhisperX transcription is always manual** ("transcribe now" button) — compute is controlled by a human.
- **Shared library**: all members see the same feeds/episodes; read/star/play-progress states are isolated per user. Registration requires admin approval. Roles: admin / user / viewer.
- **One global LLM config**, maintained by the admin — members never store API keys.
- **YouTube episodes stream in place**: the backend proxies the audio stream (with Range support); nothing is written to disk.

## Quick start

```powershell
# Backend (auto-starts a MongoDB Docker container if needed)
cd backend
Copy-Item .env.example .env
uv sync
uv run python run.py        # → http://localhost:5000

# Frontend
cd frontend
npm install
npm run dev                 # configured port 3000; auto-increments if occupied

# Optional: local AI transcription components (torch/WhisperX, ~1-3GB,
# auto-detects CUDA vs CPU build per your machine)
python setup_local_ai.py
```

First-run walkthrough, all config vars (including `YOUTUBE_PROXY` / `BILI_SESSDATA` required for video sources in CN networks), and troubleshooting: **[docs/getting-started.md](./docs/getting-started.md)** (Chinese).

## Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 18, Vite, TailwindCSS, i18next, PWA |
| Backend | Python 3.13, Flask, ThreadPoolExecutor task queue |
| Database | MongoDB (Docker container `podcast-mongodb`) |
| Ingestion | feedparser / yt-dlp + youtube-transcript-api / curl_cffi (Bilibili wbi signing) |
| AI | OpenAI-compatible + Anthropic dual protocol; local faster-whisper / WhisperX |

## Documentation

All docs are in Chinese; the map lives in [docs/index.md](./docs/index.md).

- Getting started & config: [docs/getting-started.md](./docs/getting-started.md)
- Architecture, data flow, permissions: [docs/architecture.md](./docs/architecture.md)
- AI features & strategy: [docs/ai-features.md](./docs/ai-features.md)
- API / database (for devs & AI agents): [docs/api.md](./docs/api.md) · [docs/database.md](./docs/database.md)
- Decisions & backlog: [docs/decisions/](./docs/decisions/) · [docs/backlog.md](./docs/backlog.md)

## Useful commands

```powershell
cd backend && uv run pytest            # tests (116 cases)
cd backend && uv run python run.py     # backend
cd frontend && npm run build           # frontend build
```
