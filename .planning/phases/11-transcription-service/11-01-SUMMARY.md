---
phase: 11-transcription-service
plan: 01
subsystem: api
tags: [faster-whisper, whisper, transcription, speech-to-text, django, django-q2, aifeedbackjob]

# Dependency graph
requires:
  - phase: 10-data-models-task-infrastructure
    provides: AIFeedbackJob model, run_ai_feedback task skeleton, django-q2 infrastructure
provides:
  - faster-whisper==1.2.1 installed and in requirements.txt
  - AIFeedbackJob.transcript TextField with migration 0011
  - WHISPER_MODEL_SIZE setting with env override and "base" default
  - transcribe_session(job) function in session/services/transcription.py
affects: [11-02-background-task-integration, 12-claude-api-scoring]

# Tech tracking
tech-stack:
  added: [faster-whisper==1.2.1, ctranslate2 (transitive), PyAV (transitive)]
  patterns: [lazy WhisperModel import inside service function, initial_prompt from SessionQuestion texts, single-pass generator consumption]

key-files:
  created:
    - session/services/transcription.py
    - session/migrations/0011_add_transcript_to_aifeedbackjob.py
  modified:
    - requirements.txt
    - session/models.py
    - MockIT/settings.py

key-decisions:
  - "Plain text transcript format (no speaker labels) — diarization not available; Phase 12 Claude API can interpret context"
  - "Lazy WhisperModel instantiation inside function — avoids import-time cost and startup delay; matches deferred-import pattern"
  - "initial_prompt built from all SessionQuestion texts across all parts with select_related to avoid N+1"

patterns-established:
  - "Lazy service import: WhisperModel imported inside transcribe_session() to prevent startup cost"
  - "Single-pass generator: segments consumed once into list to prevent generator exhaustion"
  - "Validation chain: recording existence -> file path -> file on disk -> raises RuntimeError for each"

requirements-completed: [TRNS-02, TRNS-03, TRNS-04]

# Metrics
duration: 25min
completed: 2026-04-07
---

# Phase 11 Plan 01: Transcription Service Infrastructure Summary

**faster-whisper CPU transcription service with lazy WhisperModel loading, initial_prompt from SessionQuestion context, and AIFeedbackJob.transcript storage**

## Performance

- **Duration:** ~25 min
- **Started:** 2026-04-07T19:14:57Z
- **Completed:** 2026-04-07T19:35:00Z
- **Tasks:** 2
- **Files modified:** 5 (created 2, modified 3)

## Accomplishments
- Installed faster-whisper==1.2.1 with all transitive deps (ctranslate2, PyAV for webm support)
- Added AIFeedbackJob.transcript TextField and applied migration 0011
- Added WHISPER_MODEL_SIZE Django setting with env override and "base" default
- Created transcribe_session(job) service function with full validation chain and plain-text output
- 70 existing tests still pass with no regressions

## Task Commits

Each task was committed atomically:

1. **Task 1: Install faster-whisper and add transcript field + setting** - `a0d1709` (feat)
2. **Task 2: Create transcription service module** - `2e8c172` (feat)

## Files Created/Modified
- `requirements.txt` - Added faster-whisper==1.2.1
- `session/models.py` - Added transcript = models.TextField(null=True, blank=True) to AIFeedbackJob
- `session/migrations/0011_add_transcript_to_aifeedbackjob.py` - Auto-generated migration
- `MockIT/settings.py` - Added WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base")
- `session/services/transcription.py` - New transcribe_session(job) service function

## Decisions Made
- Plain text transcript (no Examiner:/Candidate: speaker labels) — diarization unavailable in faster-whisper alone; Claude API in Phase 12 can interpret based on question context
- WhisperModel loaded lazily inside the function, not at module import — matches existing deferred-import pattern from Phase 10 (AIFeedbackJob import in tasks.py)
- initial_prompt uses all SessionQuestion texts ordered by part then question order, using select_related to avoid N+1

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- Worktree branch was behind the milestone branch (gsd/v1.3-ai-feedback-assessment) — Phase 10 changes were not present. Resolved by merging milestone branch into worktree branch before executing.
- pip default was Python 2.7 on the machine; resolved by using /home/xmichael446/.pyenv/versions/3.11.9/bin/pip
- PostgreSQL 13 is installed (Django 5.2 requires 14+); resolved by using DJANGO_SETTINGS_MODULE=MockIT.settings_test for migration generation and test runs

## User Setup Required
None - no external service configuration required. Note: faster-whisper downloads model weights from HuggingFace on first use (~150MB for "base"). Pre-download recommended on deployment server:
```bash
python3 -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu')"
```

## Next Phase Readiness
- transcribe_session(job) is ready to be called from run_ai_feedback() task in Plan 02
- AIFeedbackJob.transcript field exists and migration is applied
- Plan 02 can wire transcription into the background task by importing from session.services.transcription

---
*Phase: 11-transcription-service*
*Completed: 2026-04-07*
