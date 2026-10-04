# PodMaster

**Subscriptions, listening and AI analysis in one workbench.**

PodMaster is a local-first podcast and video subscription tool. Paste an RSS feed, YouTube channel or Bilibili creator URL to manage episodes, follow updates, listen and read transcripts. Save episode analyses and reuse them in weekly and monthly briefings shaped by your interests.

**[Live product tour](https://zhong-ze-wei.github.io/podcast/)** · **[Quick start](#quick-start)** · **[Product guide](./docs/product-showcase.md)** · [Documentation](./docs/index.md) · [中文](./README.md)

[![PodMaster product tour: subscriptions, listening and AI briefings. Click to open the live showcase](https://zhong-ze-wei.github.io/podcast/assets/product-preview.jpg)](https://zhong-ze-wei.github.io/podcast/)

**Click the image to explore the live showcase.** It includes product explanations, actual application screenshots and interactive listening and AI briefing demos, including on mobile. The demo uses sample content and simulated playback; real subscriptions, audio and AI analysis require the local application.

## Inside the app

### Subscriptions & listening

Follow recent updates, save episodes and listen alongside transcripts. The bottom player supports play/pause, seeking, skip controls and volume.

[![PodMaster listening interface with transcript and bottom player. Click to try the online demo](https://zhong-ze-wei.github.io/podcast/assets/listening.jpg)](https://zhong-ze-wei.github.io/podcast/#demo)

### AI analysis & briefings

Keep summaries, topics, quotations, concepts and methods from complete transcripts. Weekly and monthly briefings reuse saved episode analyses to compare common ground and differences. Save ideas, revisit their sources and export complete reports to PDF.

[![PodMaster AI briefing with takeaways, quotations and episode sources. Click to view the showcase](https://zhong-ze-wei.github.io/podcast/assets/briefing.jpg)](https://zhong-ze-wei.github.io/podcast/#screenshots)

Screenshots show the actual application with illustrative data. [Try the online demo](https://zhong-ze-wei.github.io/podcast/#demo) · [Tour & demo guide](./docs/product-showcase.md).

## Features

- Detect RSS feeds, YouTube channels and Bilibili creator pages from subscription URLs.
- Follow recent updates; opening a source clears its unseen-update indicator.
- Fetch available platform transcripts, with manual local transcription when needed.
- Save episode summaries, topics, quotations, concepts and methods; choose templates for summaries.
- Use your interests to select material for weekly and monthly briefings, reusing saved episode analyses.
- Share a library while keeping read states, favorites and listening positions per user. Chinese / English UI.

## Quick start

Install Git, Python (3.13 recommended), [uv](https://docs.astral.sh/uv/) and Node.js 18+. Use an existing local MongoDB instance, or start Docker Desktop so the backend can create its database container.

The following commands use PowerShell:

```powershell
git clone https://github.com/Zhong-Ze-Wei/podcast.git
cd podcast
```

**Terminal 1: start the backend from the repository root.**

```powershell
cd backend
Copy-Item .env.example .env   # First run only; skip if .env already exists
uv sync
uv run python run.py
```

The backend listens on `http://localhost:5000`. If MongoDB is not listening locally on port `27017`, the startup script tries to create or start the Docker container `podcast-mongodb`.

**Terminal 2: open another terminal at the repository root and start the frontend.**

```powershell
cd frontend
npm install
npm run dev
```

Open **http://localhost:3000**. If occupied, use the address printed by Vite. The frontend proxies `/api` to the backend.

After starting the frontend, open the **[interactive product demo](http://localhost:3000/product/index.html)**. For a standalone preview, download the repository and open the [static product page](./frontend/public/product/index.html) directly; no backend is needed.

### First use

1. Paste a subscription URL and wait for episodes to sync.
2. Open an episode to listen and read its transcript; transcribe manually when needed.
3. Enable AI and configure the model service in settings to generate an episode analysis or summary.
4. Choose interests and a weekly or monthly period in AI Briefing.

When login is enabled, the first registered user becomes admin; later registrations require approval. The admin maintains the shared model service configuration. See the [full setup guide](./docs/getting-started.md) for accounts, proxies, transcripts and model settings (Chinese).

### Optional local transcription

Run from the **repository root** to install Whisper / WhisperX components:

```powershell
python setup_local_ai.py
```

The installer selects GPU or CPU dependencies for your machine. Local transcription components are not required to read existing transcripts or use a remote model service. [Installation details](./docs/getting-started.md#本地转写组件可选加载).

## Documentation

| Topic | Link |
| --- | --- |
| Product overview, screenshots and demo | [Product tour](./docs/product-showcase.md) |
| Setup, configuration and troubleshooting | [Getting started](./docs/getting-started.md) |
| Weekly / monthly briefings and reading layouts | [Content reports](./docs/briefing-reports.md) |
| Transcripts, transcription, summaries and model configuration | [AI features](./docs/ai-features.md) |
| Architecture, data flow and permissions | [Architecture](./docs/architecture.md) |
| APIs and database | [API](./docs/api.md) · [Database](./docs/database.md) |
| AI algorithms and experiments | [AI research](./docs/ai/README.md) |
| Documentation map, decisions and backlog | [Docs map](./docs/index.md) · [Decisions](./docs/decisions/) · [Backlog](./docs/backlog.md) |

Detailed documentation is currently in Chinese.

## Stack & development

React 18, Vite, TailwindCSS and i18next on the frontend; Flask, MongoDB and a background task queue on the backend. RSS, YouTube and Bilibili ingestion. OpenAI-compatible and Anthropic model protocols, with optional faster-whisper / WhisperX transcription.

Frontend checks, from `frontend`:

```powershell
npm test
npm run build
```

Backend tests, from `backend`:

```powershell
uv run pytest
```
