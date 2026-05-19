# Phase 1 execution status - 2026-05-17

Status: completed for the first stabilization pass. Phase 2 has not started.

Completed items:
- Removed unused legacy frontend views: `LlmSettingsView.jsx`, `DownloadedView.jsx`, `TranscribedView.jsx`.
- Removed debug `console.log` output and unused local state from active views.
- Added `local_audio_url` to episode responses when a downloaded local audio file exists.
- Added `/api/media/<path>` serving for local media so the Vite `/api` proxy can play local audio.
- Updated frontend playback to prefer `local_audio_url`, with remote `audio_url` fallback on local playback failure.
- Updated `TranscriptFetcher` to detect SRT/VTT/JSON by URL, `Content-Type`, and body sniffing.
- Classified RSS fetch failures for 404/410, SSL certificate errors, timeout, HTTP 5xx, and feed parse errors.
- Added MongoDB TTL index on `tasks.completed_at` with 7-day expiry. Running/pending tasks are not deleted because they do not have a date value in `completed_at`.

Database note:
- No manual migration is required. MongoDB creates the TTL index during app startup.
- Existing completed/failed tasks with a valid `completed_at` date become eligible for TTL cleanup after 7 days.
- Tasks without `completed_at`, including pending/processing tasks, are unaffected.
