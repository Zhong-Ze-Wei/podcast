# Transcription Strategy Plan

## Current Goal

Make transcription provider choice explicit and reversible before rebuilding the larger AI pipeline.

## Providers

| Provider | Cost | Input | Status | Notes |
| --- | --- | --- | --- | --- |
| `official` | Free | `transcript_url` | Active | Preferred when the RSS/feed exposes subtitles. |
| `local_whisper` | Free except local compute | downloaded local audio | Active | Uses `faster-whisper` through `backend/app/services/whisper_service.py`. |
| `assemblyai` | Paid | remote `audio_url` | Gated | Requires `TRANSCRIPTION_CLOUD_ENABLED=1`. Never used as silent fallback. |
| `manual` | Free | user-provided text | Reserved | UI/backend name is reserved, import flow is not implemented yet. |
| `auto` | Depends on resolved provider | episode metadata | Backend only | Resolves to `official` when subtitles exist; otherwise asks the caller to choose. |

## Runtime Rules

1. Do not silently call paid transcription.
2. Official subtitles are the first choice when available.
3. Local Whisper requires a downloaded local audio file.
4. AssemblyAI requires explicit environment opt-in.
5. Manual import should be implemented as a separate flow, not mixed with queued provider transcription.

## UI Direction

Episode detail should show a compact provider selector in the transcript empty state:

1. Official subtitles
2. Local Whisper
3. AssemblyAI cloud
4. Manual import, disabled until implemented

The action button should submit the selected provider to `POST /api/transcripts/:episodeId`.

## Next Steps

1. Add manual transcript import.
2. Add local Whisper model selection and queue capacity controls.
3. Add provider-specific task metadata and logs.
4. Add transcript quality fields such as language, model, elapsed time, and confidence when available.
