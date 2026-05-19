# Podcast Manager

Local-first podcast pipeline: RSS subscriptions, audio download, transcription, and AI-assisted summaries.

## Stack

| Layer | Technology |
| --- | --- |
| Frontend | React 18, Vite, TailwindCSS, i18next |
| Backend | Flask, MongoDB |
| Python environment | uv |
| Transcription | Official transcripts, local faster-whisper, optional AssemblyAI |
| Summaries | OpenAI-compatible LLM API |
| Tasks | ThreadPoolExecutor |

## Requirements

- Python 3.10 to 3.13. The backend `.python-version` currently pins `3.13`.
- uv 0.9+.
- Node.js 18+.
- MongoDB on port `27017`, or Docker Desktop if you want `backend/run.py` to auto-start MongoDB.

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

TRANSCRIPTION_DEFAULT_PROVIDER=official
WHISPER_MODEL=base
WHISPER_MODEL_DIR=E:\models\tts
TORCH_HOME=E:\models\tts\torch
WHISPER_DEVICE=cuda
WHISPER_COMPUTE_TYPE=float16
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
LLM_BASE_URL=
LLM_API_KEY=
LLM_MODEL=
```

AssemblyAI is installed as a backend dependency because the provider exists, but cloud transcription is still disabled unless `TRANSCRIPTION_CLOUD_ENABLED=1`.

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

Detailed API notes live in `api.md`.

Main modules:

- `/api/feeds`
- `/api/episodes`
- `/api/transcripts`
- `/api/summaries`
- `/api/tasks`
- `/api/settings`
- `/api/prompt-templates`
- `/api/insights`
