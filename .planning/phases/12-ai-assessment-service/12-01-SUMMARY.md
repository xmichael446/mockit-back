---
phase: 12-ai-assessment-service
plan: "01"
subsystem: api
tags: [anthropic, claude, ielts, assessment, tool-use, django, python]

# Dependency graph
requires:
  - phase: 11-transcription-service
    provides: AIFeedbackJob model with transcript field; session/services/ pattern; deferred import convention
  - phase: 10-ai-feedback-foundation
    provides: SpeakingCriterion enum (FC=1, GRA=2, LR=3, PR=4); CriterionScore model; ScoreSource.AI enum
provides:
  - assess_session(job) function returning 4 criterion dicts with band and feedback
  - CRITERION_MAP, REQUIRED_KEYS, TOOL_DEFINITION, SYSTEM_PROMPT constants
  - anthropic SDK v0.91.0 dependency installed and in requirements.txt
  - ANTHROPIC_API_KEY setting in Django settings with safe os.environ.get default
affects:
  - 12-02 (task integration — calls assess_session after transcription)
  - 13+ (any phase consuming CriterionScore with source=AI)

# Tech tracking
tech-stack:
  added:
    - anthropic==0.91.0 (official Anthropic Python SDK; synchronous client)
  patterns:
    - Deferred import of anthropic inside assess_session() — avoids module-level startup cost (follows transcription.py convention)
    - Forced tool_use with tool_choice={"type":"tool","name":"submit_ielts_assessment"} for schema-validated structured output
    - All-or-nothing validation — raise RuntimeError if any of 4 criteria missing (no partial saves)
    - Module-level integer constants for CRITERION_MAP (no Django ORM import at module level)

key-files:
  created:
    - session/services/assessment.py
  modified:
    - requirements.txt
    - MockIT/settings.py

key-decisions:
  - "Use integer literals in CRITERION_MAP instead of SpeakingCriterion enum to avoid AppRegistryNotReady at module import time"
  - "ANTHROPIC_API_KEY uses os.environ.get() with empty string default — safe for dev/test environments without the key set"
  - "assess_session propagates anthropic exceptions upward — task caller sets FAILED status"
  - "max_tokens=1024 for Claude API call (sufficient for 4 criteria + feedback)"

patterns-established:
  - "Pattern: Deferred import of external service SDK inside function body (import anthropic inside assess_session)"
  - "Pattern: Module-level constants use plain integers for Django model choices to avoid ORM import at startup"
  - "Pattern: All-or-nothing validation before any DB writes (REQUIRED_KEYS check before bulk_create)"

requirements-completed:
  - AIAS-02
  - AIAS-03
  - AIAS-04

# Metrics
duration: 5min
completed: "2026-04-08"
---

# Phase 12 Plan 01: AI Assessment Service Summary

**Claude API assessment service using forced tool_use to produce IELTS band scores (1-9) and 3-4 sentence feedback for all four speaking criteria (FC, GRA, LR, PR)**

## Performance

- **Duration:** 5 min
- **Started:** 2026-04-08T05:25:56Z
- **Completed:** 2026-04-08T05:31:08Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments

- Created `session/services/assessment.py` (249 lines) with `assess_session(job)` function that calls Claude claude-sonnet-4-20250514 via forced `tool_use` and returns validated criterion dicts
- Installed `anthropic==0.91.0` SDK and added it to `requirements.txt`
- Added `ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")` to `MockIT/settings.py` with safe empty-string default

## Task Commits

1. **Task 1: Install anthropic SDK and add ANTHROPIC_API_KEY setting** - `8e3d34a` (chore)
2. **Task 2: Create assessment service module** - `a908a20` (feat)

**Plan metadata:** (included in final commit)

## Files Created/Modified

- `session/services/assessment.py` - Claude API assessment service with assess_session(), CRITERION_MAP, REQUIRED_KEYS, TOOL_DEFINITION, SYSTEM_PROMPT
- `requirements.txt` - Added anthropic==0.91.0
- `MockIT/settings.py` - Added ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")

## Decisions Made

- Used integer literals (1, 2, 3, 4) in `CRITERION_MAP` instead of `SpeakingCriterion.FC` etc. to avoid `AppRegistryNotReady` error at module import time — importing from `session.models` at module level triggers Django ORM initialization before apps are ready
- `ANTHROPIC_API_KEY` uses `os.environ.get()` with empty string default (not `os.environ[]`) — the key is only needed when AI feedback tasks run, not on every Django startup; this matches the plan requirement and mirrors `WHISPER_MODEL_SIZE` pattern
- `assess_session` does not catch `anthropic.*` exceptions — they propagate to the task's outer `except Exception` block where `job.status = FAILED` and `error_message` are set

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Removed module-level SpeakingCriterion import**
- **Found during:** Task 2 (Create assessment service module)
- **Issue:** Original implementation imported `from session.models import SpeakingCriterion` at module level, causing `django.core.exceptions.AppRegistryNotReady` when the module is imported before Django setup completes
- **Fix:** Replaced `SpeakingCriterion.FC/GRA/LR/PR` with integer literals (1, 2, 3, 4) in `CRITERION_MAP` with comments referencing the enum values. The research file's example code already used integer literals — following that pattern.
- **Files modified:** session/services/assessment.py
- **Verification:** `python3 -c "from session.services.assessment import assess_session, CRITERION_MAP, REQUIRED_KEYS, TOOL_DEFINITION, SYSTEM_PROMPT; print('OK')"` succeeds without Django setup
- **Committed in:** a908a20 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug fix — module-level ORM import)
**Impact on plan:** Fix was necessary for correctness — the module must be importable without Django setup to match project convention. Integer literals produce identical runtime values to the enum.

## Issues Encountered

- Worktree branch was 23 commits behind `gsd/v1.3-ai-feedback-assessment` milestone branch (missing Phase 10/11 work). Resolved via fast-forward merge before starting task execution.
- System `pip` resolves to Python 2.7 pip; used `python3 -m pip install` to install anthropic SDK correctly.

## User Setup Required

Environment variable required before AI feedback tasks run:

```bash
# Add to .env
ANTHROPIC_API_KEY=sk-ant-...
```

The Django setting uses `os.environ.get("ANTHROPIC_API_KEY", "")` — Django startup will not fail if the key is absent, but `assess_session()` will raise `anthropic.AuthenticationError` when called without a valid key.

## Next Phase Readiness

- `assess_session(job)` is ready to be called from `run_ai_feedback()` task in Phase 12 Plan 02
- Phase 12-02 will: call `assess_session(job)` after transcription, `get_or_create` SessionResult, then `bulk_create` four CriterionScore records with `source=ScoreSource.AI`
- No blockers for 12-02

---
*Phase: 12-ai-assessment-service*
*Completed: 2026-04-08*
