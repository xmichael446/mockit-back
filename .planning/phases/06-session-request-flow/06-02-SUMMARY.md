---
phase: 06-session-request-flow
plan: 02
subsystem: api
tags: [django, drf, session-request, scheduling, select_for_update, transaction]

# Dependency graph
requires:
  - phase: 06-01
    provides: SessionRequest model with state machine, AvailabilitySlot, compute_available_slots

provides:
  - SessionRequestSerializer and SessionRequestRejectSerializer
  - SessionRequestListCreateView (GET + POST with slot validation and duplicate check)
  - AcceptRequestView (atomic IELTSMockSession creation with select_for_update)
  - RejectRequestView (requires rejection_comment)
  - CancelRequestView (both candidate and examiner)
  - 4 URL patterns under /api/scheduling/requests/
  - 16 integration tests covering all endpoints and edge cases

affects:
  - docs
  - frontend-api-client

# Tech tracking
tech-stack:
  added: []
  patterns:
    - select_for_update + transaction.atomic for double-booking prevention
    - _broadcast called after transaction.atomic block (v1.1 discipline)
    - Slot availability validated via compute_available_slots before booking

key-files:
  created: []
  modified:
    - scheduling/serializers.py
    - scheduling/views.py
    - scheduling/urls.py
    - scheduling/tests.py

key-decisions:
  - "select_for_update on SessionRequest accept path prevents double-booking under concurrent requests"
  - "_broadcast called after transaction.atomic block to prevent stale WebSocket events on rollback"
  - "_validate_slot_available uses compute_available_slots to check slot status before creating request"
  - "Duplicate request check: filters on PENDING+ACCEPTED status for same slot+date+candidate+examiner"

patterns-established:
  - "Session request submit: validate slot -> check duplicate -> save with injected candidate/examiner FKs"
  - "Accept flow: select_for_update in atomic block -> create IELTSMockSession -> broadcast outside block"

requirements-completed:
  - REQ-01
  - REQ-03
  - REQ-04
  - REQ-06
  - REQ-07

# Metrics
duration: 11min
completed: 2026-03-30
---

# Phase 06 Plan 02: Session Request API Summary

**Session request endpoints with atomic accept (select_for_update), slot validation, role guards, and 16 integration tests covering all flows**

## Performance

- **Duration:** 11 min
- **Started:** 2026-03-30T08:40:35Z
- **Completed:** 2026-03-30T08:51:22Z
- **Tasks:** 2
- **Files modified:** 4

## Accomplishments

- Built all 4 view classes with correct role enforcement (candidate-only submit, examiner-only accept/reject, both-role cancel)
- Implemented atomic accept with `select_for_update()` + `transaction.atomic()` preventing double-booking under concurrency
- Added `_validate_slot_available()` helper using `compute_available_slots` to validate slot status before booking
- Created 16 integration tests covering all endpoints, edge cases, and role-based access control

## Task Commits

Each task was committed atomically:

1. **Task 1: Serializers, view classes, and URL patterns** - `cb31ed8` (feat)
2. **Task 2: Integration tests for all session request endpoints** - `5b1834d` (test)

**Plan metadata:** (pending)

## Files Created/Modified

- `scheduling/serializers.py` - Added SessionRequestSerializer (with weekday and past-date validation) and SessionRequestRejectSerializer
- `scheduling/views.py` - Added _is_candidate, _validate_slot_available helpers; SessionRequestListCreateView, AcceptRequestView, RejectRequestView, CancelRequestView
- `scheduling/urls.py` - Wired 4 request URL patterns under requests/
- `scheduling/tests.py` - Added TestSessionRequestAPI with 16 integration tests

## Decisions Made

- `select_for_update()` inside `transaction.atomic()` on accept path — prevents concurrent accept race condition
- `_broadcast` called after the atomic block exits — consistent with v1.1 discipline, no stale events on rollback
- `_validate_slot_available` calls `compute_available_slots` for full slot status check (blocked, booked, available)
- Duplicate request guard uses `status__in=[PENDING, ACCEPTED]` filter — cancelled/rejected requests don't block re-booking

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

- 5 pre-existing failures in `session.tests` (`SessionStateMachineTests`, `SessionStartTransactionTests`) due to `can_start()` checking `timezone.now() >= self.scheduled_at` when `scheduled_at` is `None`. These were failing before this plan and are out of scope. Deferred to `deferred-items.md`.

## Known Stubs

None - all views wire live data from the database.

## Next Phase Readiness

- Session request flow is complete: candidates can book, examiners can accept/reject/cancel
- AcceptRequestView creates `IELTSMockSession` with correct `scheduled_at` and broadcasts `session_request.accepted`
- 62 scheduling tests pass; full project test suite has 5 pre-existing session failures (not caused by this plan)

---
*Phase: 06-session-request-flow*
*Completed: 2026-03-30*
