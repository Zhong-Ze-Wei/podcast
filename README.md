# Podcast Manager

Local-first podcast pipeline: RSS subscriptions, audio download, transcription, and AI-assisted summaries.

> 中文说明见 [README_CN.md](./README_CN.md)。

## Quick Start

Start the backend first, then the frontend.

```powershell
git clone <repo-url>
cd podcast

cd backend
Copy-Item .env.example .env
uv sync
uv run python run.py
```

`backend/run.py` checks whether MongoDB is listening on `localhost:27017`. If not, it tries to create or start a Docker container named `podcast-mongodb` with a persistent Docker volume.

Open another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Then open:

```text
http://localhost:3000
```

## Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 18, Vite, TailwindCSS, i18next |
| Backend | Flask, MongoDB |
| Python environment | uv |
| Transcription | Official transcripts, local faster-whisper, optional WhisperX, optional AssemblyAI |
| Summaries | OpenAI-compatible LLM API |
| Tasks | ThreadPoolExecutor |

## Requirements

- Python 3.10 to 3.13. The backend `.python-version` currently pins `3.13`.
- uv 0.9+.
- Node.js 18+.
- MongoDB on port `27017`, or Docker Desktop if you want `backend/run.py` to auto-start MongoDB.

## Database

The fastest local path is to let `backend/run.py` manage MongoDB through Docker. For deployment or explicit database management, start MongoDB yourself and point the backend at it.

Manual Docker:

```powershell
docker run -d --name podcast-mongodb -p 27017:27017 -v podcast-mongodb-data:/data/db mongo:latest
```

External MongoDB:

```env
MONGO_URI=mongodb://your-mongodb-host:27017
MONGO_DB=podcast
```

For a shared or deployed instance, prefer explicit MongoDB management over relying on the backend process to create infrastructure implicitly.

## Backend

Use uv from the backend directory. Do not activate conda and a project `.venv` at the same time.

```powershell
cd backend

# Create or reuse backend/.venv from pyproject.toml
uv sync

# Run tests
uv run pytest

# Start Flask API on http://localhost:5000
uv run python run.py
```

If uv reports a cache permission error such as `failed to open file E:\uv\...`, use a project-local cache for the current shell:

```powershell
cd backend
$env:UV_CACHE_DIR = Join-Path (Get-Location) ".uv-cache"
uv sync
```

Or set a user-level cache once:

```powershell
[Environment]::SetEnvironmentVariable("UV_CACHE_DIR", "E:\ZZ's_Code\AI\podcast\backend\.uv-cache", "User")
```

If you want to inspect which Python is active:

```powershell
uv run python -c "import sys; print(sys.executable)"
```

### Dependency Management

The backend source of truth is:

```text
backend/pyproject.toml
```

`backend/requirements.txt` is only a compatibility export for older tools. Do not edit it first. Change `pyproject.toml`, then regenerate requirements when needed:

```powershell
cd backend
uv export --frozen --all-groups --no-hashes --no-emit-project --format requirements.txt --output-file requirements.txt
```

Add a runtime dependency:

```powershell
cd backend
uv add package-name
```

Add a dev dependency:

```powershell
cd backend
uv add --dev package-name
```

## Frontend

```powershell
cd frontend
npm install
npm run dev
```

The frontend development server is expected at:

```text
http://localhost:3000
```

## Environment

Copy the backend example file before first run:

```powershell
cd backend
Copy-Item .env.example .env
```

Important backend flags:

```env
MONGO_URI=mongodb://localhost:27017
MONGO_DB=podcast

AUTH_REQUIRED=0
JWT_SECRET=change-this-before-sharing

TRANSCRIPTION_DEFAULT_PROVIDER=official
TRANSCRIPTION_DEFAULT_LANGUAGE=auto
TRANSCRIPTION_AI_NORMALIZE_ENABLED=0
WHISPER_MODEL=base
WHISPER_MODEL_DIR=E:\models\tts
TORCH_HOME=E:\models\tts\torch
WHISPER_DEVICE=cpu
WHISPER_COMPUTE_TYPE=int8
WHISPERX_BATCH_SIZE=16
WHISPERX_VAD_METHOD=silero
WHISPERX_DIARIZE=0
WHISPERX_DIARIZATION_MODEL=pyannote/speaker-diarization-3.1
WHISPERX_MIN_SPEAKERS=
WHISPERX_MAX_SPEAKERS=
HF_TOKEN=
TRANSCRIPTION_CLOUD_ENABLED=0
ASSEMBLYAI_API_KEY=

AI_ANALYSIS_ENABLED=0
LLM_DEFAULT_NAME=ModelScope
LLM_PROVIDER=modelscope
LLM_API_FORMAT=openai_compatible
LLM_BASE_URL=https://api-inference.modelscope.cn/v1
LLM_API_KEY=
LLM_MODEL=deepseek-ai/DeepSeek-V4-Flash
```

AssemblyAI is installed as a backend dependency because the provider exists, but cloud transcription is still disabled unless `TRANSCRIPTION_CLOUD_ENABLED=1`.

`TRANSCRIPTION_DEFAULT_LANGUAGE=auto` keeps provider language detection enabled. For Chinese podcasts, choose `zh` in the frontend transcription panel or set the env var to `zh` to reduce language misdetection.

`TRANSCRIPTION_AI_NORMALIZE_ENABLED=0` keeps transcript post-processing local and rule-based. Set it to `1` only if you want the active LLM configuration to clean transcripts further; this consumes tokens from the configured OpenAI-compatible LLM endpoint.

Real AI API keys must stay out of Git. `.env`, `.env.*`, and `*.env` are ignored by `.gitignore`, so put local secrets in `backend/.env`:

```env
LLM_API_KEY=<your-provider-api-key>
```

You can also save provider keys from `Settings -> AI Configuration`; the backend stores them in MongoDB and the frontend only receives a masked `has_api_key` flag later. The committed `backend/.env.example` contains ModelScope defaults and no real key.

## Core Workflow

```text
RSS feed -> episode -> optional download -> transcript -> optional AI summary
```

Transcription provider rules:

- `official`: free, uses `transcript_url` when the feed exposes one.
- `local_whisper`: free except local compute, requires downloaded local audio.
- `local_whisperx`: advanced local WhisperX backend. Basic transcription runs locally. Speaker diarization can be enabled with `WHISPERX_DIARIZE=1` and a Hugging Face token accepted for the configured pyannote model; `WHISPERX_MIN_SPEAKERS` and `WHISPERX_MAX_SPEAKERS` can be left blank for automatic speaker count detection.
- `assemblyai`: paid cloud provider, requires `TRANSCRIPTION_CLOUD_ENABLED=1` and `ASSEMBLYAI_API_KEY`.
- `auto`: backend-only helper; uses official transcripts when available and does not silently fall back to paid cloud transcription.

Transcript creation accepts a provider and optional language:

```json
{
  "provider": "local_whisper",
  "language": "zh"
}
```

All transcript sources are normalized before saving. The default local rules remove unnatural spaces between Chinese characters and punctuation. If OpenCC is installed, Traditional Chinese can be converted to Simplified Chinese locally. Optional AI normalization uses the active LLM configuration and is disabled by default.

Opening an episode detail page does not automatically fetch external transcripts or start local/cloud transcription. Users must explicitly click the transcript action.

## Auth And Users

The backend supports JWT Bearer authentication. Local development keeps `AUTH_REQUIRED=0` so existing single-user workflows still run quickly. Set this when serving multiple users:

```env
AUTH_REQUIRED=1
JWT_SECRET=<strong-random-secret>
```

Existing local data can be assigned to a default admin:

```powershell
cd backend
uv run python scripts/backfill_default_owner.py
```

First registered user becomes an admin. Later users are normal users. Normal users can only access their own feeds, episodes, transcripts, summaries, tasks, and settings.

For local permission testing:

```powershell
cd backend
uv run python scripts/seed_test_users.py
```

This creates `admin@example.com`, `user1@example.com`, and `user2@example.com` with password `password123` unless `TEST_USER_PASSWORD` is set.

## Troubleshooting

- If MongoDB does not start, make sure Docker Desktop is running or start MongoDB manually.
- If port `27017` is occupied, change `MONGO_URI` to an available MongoDB instance.
- If the frontend cannot call the API, confirm the backend is running on `http://localhost:5000`; Vite proxies `/api` there.
- If `uv` reports cache permission errors, set `UV_CACHE_DIR` to a project-local directory as shown above.
- Local Whisper may download model files on first use; CPU mode is slower but has the fewest setup assumptions.

## Frontend Routes

The app supports stable browser paths for refresh, back navigation, and sharing within the same local data set:

```text
/workspace
/episodes
/episodes/<episode_id>
/feeds/<feed_id>
/favorites
/settings
```

## Useful Commands

```powershell
# Backend
cd backend
uv sync
uv run pytest
uv run python run.py

# Frontend
cd frontend
npm run build
npm run dev
```

## API Overview

Detailed API notes live in `docs/api.md`.

Current implementation status lives in `docs/implementation-status.md`.

Main modules:

- `/api/feeds`
- `/api/episodes`
- `/api/transcripts`
- `/api/summaries`
- `/api/tasks`
- `/api/settings`
- `/api/prompt-templates`
- `/api/insights`
