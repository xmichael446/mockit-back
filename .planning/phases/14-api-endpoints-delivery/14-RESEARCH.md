# Phase 14: API Endpoints & Delivery — Research

**Phase:** 14 - API Endpoints & Delivery
**Confidence:** HIGH
**Date:** 2026-04-08

## Key Findings

### 1. Existing Endpoint (from Phase 11 gap closure)

`AIFeedbackTriggerView` at `session/views.py:1192`:
- **POST** (line 1202): Returns 202 with `{job_id, status}`. Already handles ownership check, COMPLETED validation, duplicate prevention (409), monthly limit (429 via Phase 13). **APID-01 already satisfied.**
- **GET** (line 1251): Returns `{job_id, status, transcript, error_message}`. **APID-02 partially satisfied** (status returned). **APID-03 NOT satisfied** — missing AI scores and per-criterion feedback in response.

### 2. What GET Needs for APID-03

The GET response must include AI scores when job is DONE. Current response only has `transcript` and `error_message`. Need to add:
```python
# When job.status == DONE:
scores = CriterionScore.objects.filter(
    session_result__session=session,
    source=ScoreSource.AI
).values("criterion", "band", "feedback")
```
Return as `"scores": [{"criterion": "Fluency & Coherence", "band": 7, "feedback": "..."}]`

### 3. WebSocket Event (APID-04)

`_broadcast()` is defined in `session/views.py:92`. It sends to group `session_{session_id}` via `channel_layer.group_send`. The consumer `SessionConsumer.session_event()` forwards events as-is to WebSocket clients.

**Where to call:** In `session/tasks.py` inside `run_ai_feedback()`, after setting `job.status = DONE` and saving. Must import `_broadcast` from `session.views` using deferred import (inside the function body).

**Payload pattern** (matches existing events):
```python
_broadcast(job.session_id, "ai_feedback_ready", {"job_id": job.pk, "session_id": job.session_id})
```

**Transaction discipline note from STATE.md:** "_broadcast calls placed after transaction.atomic block". The task doesn't use `transaction.atomic()` internally (the save is a single operation), so `_broadcast` can be called immediately after `job.save()`.

### 4. API Documentation (APID-05)

`docs/api/ai-feedback.md` exists from Phase 11 but is basic. Needs:
- Complete request/response schemas for POST and GET
- Error scenario table (401, 403, 404, 409, 429)
- WebSocket event documentation
- `docs/api/index.md` already links to it

### 5. Existing Tests

`AIFeedbackTriggerTests` has 12 tests covering POST flows. GET tests exist but are basic. Need:
- Test GET returns AI scores when job is DONE
- Test GET returns no scores when job is PENDING
- Test WebSocket event sent on job completion (mock channel_layer)

## Pitfalls

1. **Circular import risk:** `_broadcast` is in `session/views.py`. Importing it in `session/tasks.py` at module level would create a circular import. Must use deferred import inside `run_ai_feedback()`.

2. **InMemoryChannelLayer in tests:** The test channel layer may not support `group_send` properly. Mock `_broadcast` in task tests rather than testing the channel layer directly.

## Validation Architecture

### Test Infrastructure
- Framework: Django TestCase
- Quick command: `python manage.py test session.tests --settings=MockIT.settings_test`
- Estimated runtime: ~15s

### Verification Map
| Requirement | Test Type | What to check |
|-------------|-----------|---------------|
| APID-01 | existing | POST 202 with job_id (already tested) |
| APID-02 | existing | GET returns status (already tested, enhance) |
| APID-03 | new | GET returns scores array when DONE |
| APID-04 | new | _broadcast called with ai_feedback_ready after DONE |
| APID-05 | manual | docs/api/ai-feedback.md has complete schemas |
