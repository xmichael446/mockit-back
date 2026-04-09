---
phase: 16-gemini-assessment-service
plan: "01"
subsystem: session/services/assessment
tags: [gemini, pydantic, ielts, assessment, audio, tdd]
dependency_graph:
  requires: [phase-15 google-genai install, SessionRecording model, AIFeedbackJob model]
  provides: [assess_session tuple return, IELTSAssessment Pydantic schema, Gemini audio pipeline]
  affects: [session/tasks.py (Phase 17 update), AssessmentServiceTests]
tech_stack:
  added: []
  patterns:
    - Gemini Files API upload + generate_content with structured output
    - Pydantic BaseModel with Field(ge=1, le=9) for band validation
    - Safety filter check via FinishReason.STOP comparison
    - Transient error retry (503/429) with exponential backoff
key_files:
  created: []
  modified:
    - session/services/assessment.py
    - session/tests.py
decisions:
  - "assess_session returns tuple(list[dict], str) — architecturally clean; tasks.py update deferred to Phase 17"
  - "Pydantic models at module-level (safe for import); genai/types/settings imports deferred inside function body"
  - "SYSTEM_PROMPT expanded with audio-specific PR section covering intonation, stress, connected speech, rhythm"
  - "Test setUp creates temp file within MEDIA_ROOT to satisfy Django safe_join check on audio_file.path"
metrics:
  duration_seconds: 358
  completed_date: "2026-04-09"
  tasks_completed: 2
  tasks_total: 2
  files_changed: 2
---

# Phase 16 Plan 01: Gemini Assessment Service Summary

**One-liner:** Replaced Claude tool_use pipeline with single Gemini Pro audio call using Pydantic structured output and audio-specific IELTS pronunciation instructions.

## What Was Built

- **`session/services/assessment.py`** — Full rewrite replacing Claude API + tool_use with Gemini Pro:
  - `CriterionAssessment` and `IELTSAssessment` Pydantic models with `Field(ge=1, le=9)` band validation
  - Expanded `SYSTEM_PROMPT` with audio-specific pronunciation assessment instructions (intonation patterns, stress placement, connected speech, rhythm and pacing)
  - `assess_session(job) -> tuple[list[dict], str]` — uploads audio via Files API, calls `generate_content` with `response_schema=IELTSAssessment`, checks safety filters, parses with `model_validate_json`, returns `(scores, transcript)` tuple
  - Missing audio file guard, safety filter check (FinishReason.STOP), transient retry loop (503/429)
  - Zero anthropic/tool_use references remain

- **`session/tests.py`** — `AssessmentServiceTests` class fully replaced with 7 Gemini-aware tests:
  - `test_calls_gemini_with_audio` — verifies files.upload and generate_content called
  - `test_returns_four_criteria_and_transcript` — verifies tuple return shape
  - `test_raises_on_safety_block` — verifies RuntimeError on FinishReason.SAFETY
  - `test_raises_on_missing_audio_file` — verifies early guard before upload
  - `test_raises_on_pydantic_validation_error` — verifies band=0 raises RuntimeError
  - `test_system_prompt_completeness` — verifies all 4 criteria + audio keywords
  - `test_builds_question_context` — verifies session questions in prompt contents

## Commits

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Rewrite assessment.py | b8210a8 | session/services/assessment.py |
| 2 | Replace AssessmentServiceTests | 69e03a5 | session/tests.py |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Django safe_join blocks /tmp/ absolute paths in FileField.path**
- **Found during:** Task 2 test execution
- **Issue:** `SessionRecording.audio_file.path` calls `safe_join(MEDIA_ROOT, name)` which raises `SuspiciousFileOperation` when `name` is an absolute `/tmp/` path
- **Fix:** Changed setUp to create temp file inside `settings.MEDIA_ROOT` using `tempfile.NamedTemporaryFile(dir=settings.MEDIA_ROOT)` and storing the relative path in `audio_file.name`
- **Files modified:** session/tests.py (setUp only)
- **Commit:** 69e03a5

## Known Stubs

None — assessment.py is fully wired to the Gemini API. tasks.py still calls `assess_session(job)` and treats the return as a plain list (not a tuple), which will fail at runtime until Phase 17 updates tasks.py. This is an intentional scope boundary documented in the plan.

## Test Results

```
Ran 7 tests in 8.274s
OK
```

All 7 `AssessmentServiceTests` pass. `AIFeedbackTaskTests` mock return values will need updating in Phase 17 (known, expected).

## Self-Check: PASSED

- session/services/assessment.py: FOUND
- session/tests.py: FOUND (modified)
- Commit b8210a8: FOUND
- Commit 69e03a5: FOUND
