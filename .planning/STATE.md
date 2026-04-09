---
gsd_state_version: 1.0
milestone: v1.4
milestone_name: AI Assessment Rebuild (Gemini Audio)
status: verifying
stopped_at: Completed 17-01-PLAN.md
last_updated: "2026-04-09T14:19:29.010Z"
last_activity: 2026-04-09
progress:
  total_phases: 3
  completed_phases: 3
  total_plans: 3
  completed_plans: 3
---

# State

## Current Position

Phase: 17
Plan: Not started
Status: Phase complete — ready for verification
Last activity: 2026-04-09

## Project Reference

See: .planning/PROJECT.md (updated 2026-04-09)

**Core value:** Examiners can conduct a complete, real-time IELTS Speaking mock exam with a candidate -- from invite through scoring -- with minimal friction.
**Current focus:** Phase 17 — Compatibility, Cleanup & Test Update
**Current milestone:** v1.4 AI Assessment Rebuild (Gemini Audio)

## Accumulated Context

### Decisions

From v1.1 (carry-forward constraints):

- [Phase 02]: ValidationError from model methods propagates through DRF -- no try/except needed in views
- [Phase 02]: Broadcast calls placed after transaction.atomic block to prevent stale events on rollback
- [Phase 03-01]: Email send returns bool rather than raising -- callers decide how to surface failure

From v1.2 (carry-forward constraints):

- Email sends must be called after transaction exits (same discipline as _broadcast)
- select_for_update() + transaction.atomic() required for race-condition-sensitive writes
- Tests run via DJANGO_SETTINGS_MODULE=MockIT.settings_test (SQLite in-memory)

From v1.3 (carry-forward constraints):

- django-q2 with ORM broker chosen (no Redis/Celery infra needed)
- Source enum on CriterionScore; unique_together must include source field
- compute_overall_band must filter by EXAMINER source only (no regression)
- Monthly usage limit enforced with select_for_update + atomic increment
- [Phase 10]: ScoreSource enum separates examiner from AI bands; unique_together includes source; compute_overall_band filters EXAMINER only
- [Phase 10]: Deferred import of AIFeedbackJob inside task function prevents circular imports at module load time
- [Phase 10]: Q_CLUSTER sync=True in test settings enables synchronous task execution in tests without a worker process
- [Phase 11-01]: Plain text transcript format (no speaker labels) — diarization not available
- [Phase 11-01]: Lazy WhisperModel instantiation inside transcribe_session() — avoids import-time cost and startup delay
- [Phase 11-03]: GET ai-feedback endpoint accessible to both examiner and candidate so candidates can poll transcript
- [Phase 11-03]: 409 for PENDING/PROCESSING duplicate job; FAILED status allows retry — preserves audit trail of attempts
- [Phase 12-ai-assessment-service]: Integer literals in CRITERION_MAP (not SpeakingCriterion enum) to avoid AppRegistryNotReady at module import time
- [Phase 12-ai-assessment-service]: assess_session propagates anthropic exceptions to task caller — task sets FAILED status and records error_message
- [Phase 12-02]: Patch target for assess_session is session.services.assessment.assess_session (deferred import resolves from services module)
- [Phase 13-usage-control]: select_for_update on all examiner jobs prevents concurrent requests bypassing monthly AI feedback limit
- [Phase 13-usage-control]: FAILED AIFeedbackJob excluded from monthly count; async_task called after transaction.atomic exits

For v1.4:

- Package is google-genai (not google-generativeai); import is `from google import genai`
- Use gemini-2.5-pro GA model (not preview variant)
- Structured output via response_json_schema + Pydantic — NOT function calling (incompatible with audio input)
- Safety filter rejections are a new failure mode with no Claude equivalent — must be handled explicitly
- Pipeline collapses from 2 steps (transcribe → assess) to 1 step (audio → Gemini → scores + transcript)
- assessment.py is a full rewrite; transcription.py is deleted entirely
- tasks.py simplifies to a single Gemini call replacing the transcribe→assess sequence
- INFRA-03 (webm smoke test) is a hard gate before any assessment code is written
- [Phase 15-01]: google-genai==1.71.0 pinned; import is 'from google import genai' (not google-generativeai)
- [Phase 15-01]: GEMINI_API_KEY uses os.environ[] fail-fast pattern — raises KeyError at startup if absent
- [Phase 15-01]: Smoke test script generates silent webm via ffmpeg if no audio provided; time.sleep(2) after upload handles PROCESSING state
- [Phase 16]: assess_session returns tuple(list[dict], str); tasks.py update deferred to Phase 17
- [Phase 16]: Test setUp creates temp file within MEDIA_ROOT to satisfy Django safe_join
- [Phase 17]: tasks.py maintains deferred import pattern inside run_ai_feedback; assess_session unpacks tuple (scores_data, transcript)
- [Phase 17]: MOCK_ASSESSMENT_RESULT changed to tuple to mirror assess_session return; TranscriptionServiceTests deleted; no faster-whisper or anthropic references remain

### Research Flags (needs codebase check during planning)

- Confirm Gemini Files API upload lifecycle (files expire after 48h — verify if re-upload is needed per job or cached)
- Confirm exact safety filter exception type in google-genai SDK to catch in error handling
- Verify AIFeedbackJob.transcript field exists from v1.3 (it should — transcription.py wrote to it)

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-04-09T13:57:10.992Z
Stopped at: Completed 17-01-PLAN.md
Resume file: None
Next action: /gsd:plan-phase 15
