---
phase: quick-260402-f0h
plan: 01
subsystem: session
tags: [share, cancel, public-api, session-lifecycle]
dependency_graph:
  requires: []
  provides: [SessionShare model, share endpoints, cancel endpoint, public shared view]
  affects: [session/models.py, session/serializers.py, session/views.py, session/urls.py]
tech_stack:
  added: []
  patterns: [AllowAny public endpoint, get_or_create idempotency, model transition guard pattern]
key_files:
  created:
    - session/migrations/0009_sessionshare.py
  modified:
    - session/models.py
    - session/serializers.py
    - session/views.py
    - session/urls.py
    - session/tests.py
decisions:
  - cancel() sets invite_expires_at to now() rather than clearing invite_token (avoids unique constraint collision on multiple cancellations)
  - SharedSessionDetailView uses authentication_classes=[] and permission_classes=[AllowAny] for unauthenticated access
  - SessionShare is a separate model (not a field on IELTSMockSession) to keep share lifecycle separate
  - SharedCriterionScoreSerializer explicitly excludes feedback field rather than using exclude= on Meta
metrics:
  duration_minutes: 12
  completed_date: "2026-04-02"
  tasks_completed: 3
  files_changed: 5
---

# Quick Task 260402-f0h: Shareable Recordings and Cancellable Sessions Summary

**One-liner:** SessionShare model with public share links (recording + band scores, no feedback) and examiner cancel flow with WS broadcast and max_sessions exclusion.

## What Was Built

**SessionShare model** (`session/models.py`): OneToOne to IELTSMockSession, share_token (reuses `_generate_invite_token`), created_by, created_at. Single share per session.

**Cancel logic** (`session/models.py`): `can_cancel()` guard (SCHEDULED + no candidate), `cancel()` transition sets status=CANCELLED and expires invite_expires_at immediately (avoids touching unique invite_token).

**SharedCriterionScoreSerializer** (`session/serializers.py`): criterion, criterion_label, band only — feedback field intentionally excluded.

**SharedSessionSerializer** (`session/serializers.py`): Serializes recording (via existing SessionRecordingSerializer, strips notes), scores, overall_band, examiner profile (ExaminerProfilePublicSerializer), candidate profile (CandidateProfilePublicSerializer).

**CreateShareView** (`POST /api/sessions/<pk>/share/`): Auth required, participant only, released result required, idempotent via get_or_create. Returns 201 on first create, 200 on subsequent calls with same token.

**SharedSessionDetailView** (`GET /api/sessions/shared/<share_token>/`): No auth (`AllowAny`), returns curated session data without feedback or notes.

**CancelSessionView** (`POST /api/sessions/<pk>/cancel/`): Examiner only, calls model's `cancel()` (ValidationError on invalid state), broadcasts `session.cancelled`, returns 200.

**max_sessions fix** (`session/views.py` line 129): `exclude(status=SessionStatus.CANCELLED)` added to session count query.

## Tasks

| Task | Description | Commit |
|------|-------------|--------|
| 1 | SessionShare model, cancel logic, migration | 2384a2c |
| 2 | Serializers, views, URLs, max_sessions fix | e341ff3 |
| 3 | Tests (19 new tests, all passing) | 9f7cae5 |

## Test Results

19 new tests across 4 test classes — all pass:
- `TestCreateShare` (5 tests): create/idempotency/403/400
- `TestSharedSessionDetail` (6 tests): public access, scores no feedback, 404
- `TestCancelSession` (6 tests): cancel flow, broadcast, invite expiry, guard failures
- `TestMaxSessionsExcludesCancelled` (2 tests): cancelled excluded, limit still enforced

Note: 5 pre-existing test failures in `SessionStateMachineTests` (unrelated to this task — `can_start()` null check on `scheduled_at=None`). These failures pre-date this quick task.

## Deviations from Plan

**None — plan executed exactly as written.**

The cancel() implementation used `invite_expires_at = timezone.now()` as specified in the revised plan notes, rather than clearing the invite_token (which would conflict with `unique=True` on multiple cancellations).

## Known Stubs

None — all endpoints are fully wired. The recording field in SharedSessionSerializer returns None when no recording exists, which is correct behavior for sessions without recordings.

## Self-Check: PASSED

- session/migrations/0009_sessionshare.py: exists
- session/models.py: SessionShare class exists, can_cancel/cancel methods exist
- session/serializers.py: SharedCriterionScoreSerializer and SharedSessionSerializer exist
- session/views.py: CreateShareView, SharedSessionDetailView, CancelSessionView exist
- session/urls.py: 24 URL patterns loaded (was 21 before)
- All 19 new tests pass
