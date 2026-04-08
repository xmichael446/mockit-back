---
plan: 14-01
phase: 14-api-endpoints-delivery
status: complete
started: 2026-04-08
completed: 2026-04-08
one_liner: "Enhanced GET endpoint with AI scores array and added WebSocket ai_feedback_ready broadcast on job completion"
requirements_completed: [APID-01, APID-02, APID-03, APID-04]
key-files:
  created:
    - session/services/assessment.py
  modified:
    - session/views.py
    - session/tasks.py
    - session/tests.py
---

# Plan 14-01 Summary

## What Was Built

Enhanced the existing AI feedback endpoint and background task:

1. **GET response with AI scores** — When job is DONE, the GET endpoint now returns a `scores` array with criterion display name, band (1-9), and feedback for each of the 4 IELTS criteria. Returns `scores: null` when not DONE.

2. **WebSocket broadcast** — `run_ai_feedback()` now calls `_broadcast(session_id, "ai_feedback_ready", {job_id, session_id})` after setting job status to DONE. Uses deferred import to avoid circular imports.

3. **6 new tests** — `AIFeedbackDeliveryTests` class with tests for scores in response, scores exclusion of examiner source, broadcast on success, and no broadcast on failure.

## Self-Check: PASSED

All acceptance criteria met. 103/103 tests pass.
