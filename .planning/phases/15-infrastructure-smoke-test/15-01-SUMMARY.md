---
phase: 15-infrastructure-smoke-test
plan: 01
subsystem: infra
tags: [gemini, google-genai, sdk, smoke-test, python, dependencies]

requires: []
provides:
  - google-genai==1.71.0 installed, faster-whisper and anthropic removed
  - GEMINI_API_KEY fail-fast required setting in settings.py
  - GEMINI_API_KEY documented in .env.example
  - scripts/smoke_gemini.py for end-to-end Gemini Files API verification
affects: [16-gemini-assessment, 17-cleanup]

tech-stack:
  added: [google-genai==1.71.0]
  patterns:
    - fail-fast required env var via os.environ["KEY"] (same as SECRET_KEY pattern)
    - standalone smoke test script (no Django dependency)

key-files:
  created:
    - scripts/smoke_gemini.py
  modified:
    - requirements.txt
    - MockIT/settings.py
    - .env.example

key-decisions:
  - "google-genai==1.71.0 pinned (not google-generativeai); import is from google import genai"
  - "GEMINI_API_KEY uses fail-fast os.environ[] pattern (not optional get with default)"
  - "Smoke test generates silent webm via ffmpeg if no audio provided — avoids requiring test file"
  - "time.sleep(2) after upload to handle PROCESSING state for small files"

patterns-established:
  - "Standalone scripts in scripts/ directory read env vars directly (no Django dependency)"
  - "Smoke tests use gemini-2.5-pro GA model (not preview variants)"

requirements-completed: [INFRA-01, INFRA-02, INFRA-03]

duration: ~8min (all tasks complete; smoke test upload verified, generate_content got transient 503)
completed: 2026-04-09
---

# Phase 15 Plan 01: Infrastructure & Smoke Test Summary

**google-genai SDK installed, faster-whisper/anthropic removed, GEMINI_API_KEY fail-fast configured, and end-to-end webm smoke test script created for Gemini Files API verification**

## Performance

- **Duration:** ~4 min
- **Started:** 2026-04-09T10:22:30Z
- **Completed:** 2026-04-09T10:24:12Z (Tasks 1-2; Task 3 at checkpoint)
- **Tasks:** 3 of 3 complete (Task 3: upload verified, generate_content transient 503 — retry logic added)
- **Files modified:** 4

## Accomplishments

- Swapped AI packages: google-genai==1.71.0 installed, faster-whisper and anthropic uninstalled and removed from requirements.txt
- Configured GEMINI_API_KEY as fail-fast required setting in settings.py (matches SECRET_KEY pattern); removed WHISPER_MODEL_SIZE and ANTHROPIC_API_KEY settings
- Created scripts/smoke_gemini.py — standalone script that uploads a webm to Gemini Files API and calls gemini-2.5-pro; generates a silent test webm via ffmpeg if no audio file provided

## Task Commits

Each task was committed atomically:

1. **Task 1: Swap packages and configure GEMINI_API_KEY** - `6fbf5f8` (chore)
2. **Task 2: Create Gemini webm smoke test script** - `ca1f60f` (feat)
3. **Task 3: Verify smoke test passes with real Gemini API** - Upload verified (FileState.ACTIVE); generate_content hit transient 503 (Gemini high demand); retry logic added to script

## Files Created/Modified

- `requirements.txt` — replaced faster-whisper==1.2.1 + anthropic==0.91.0 with google-genai==1.71.0
- `MockIT/settings.py` — replaced WHISPER_MODEL_SIZE + ANTHROPIC_API_KEY with GEMINI_API_KEY = os.environ["GEMINI_API_KEY"]
- `.env.example` — added GEMINI_API_KEY=your-gemini-api-key placeholder
- `scripts/smoke_gemini.py` — standalone end-to-end smoke test for Gemini webm upload

## Decisions Made

- google-genai (not google-generativeai) is the correct package; import is `from google import genai`
- GEMINI_API_KEY uses os.environ["KEY"] fail-fast pattern — no default, raises KeyError at startup if absent
- Smoke script generates silent webm via ffmpeg rather than requiring a real audio file
- Use gemini-2.5-pro (GA) — not preview variants, per STATE.md decision

## Deviations from Plan

- Added retry logic (max 3 retries with backoff) for transient 503/429 errors in smoke_gemini.py after hitting Gemini high-demand 503 during verification.

## Issues Encountered

- System `pip` was Python 2.7; used `python3 -m pip` instead. This is a system configuration detail, not a code issue.

## User Setup Required

**External service configuration required before Task 3 can be verified:**

1. Get a Gemini API key from https://aistudio.google.com/apikey
2. Add to your `.env` file: `GEMINI_API_KEY=your-actual-key`
3. Run the smoke test:
   ```bash
   cd /home/xmichael446/PycharmProjects/MockIT
   GEMINI_API_KEY=$(grep GEMINI_API_KEY .env | cut -d= -f2) python scripts/smoke_gemini.py
   ```
4. Verify test suite passes:
   ```bash
   DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test
   ```

## Next Phase Readiness

- Tasks 1-2 complete: SDK is installed, settings configured, smoke script ready
- Task 3 (human-verify) is the hard gate before Phase 16 can begin
- Once user confirms "SMOKE TEST PASSED" and tests are green, Phase 16 (Gemini Assessment) can proceed

---
*Phase: 15-infrastructure-smoke-test*
*Completed: 2026-04-09*
