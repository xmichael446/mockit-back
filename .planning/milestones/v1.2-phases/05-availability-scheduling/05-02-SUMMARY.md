---
phase: 05-availability-scheduling
plan: "02"
subsystem: api
tags: [django, drf, scheduling, availability, rest-api]

requires:
  - phase: 05-01
    provides: AvailabilitySlot and BlockedDate models, compute_available_slots() and is_currently_available() services

provides:
  - AvailabilitySlotSerializer with start_time validation (on-the-hour, 08:00-21:00)
  - BlockedDateSerializer for blocked date CRUD
  - 6 REST API endpoints for scheduling (CRUD + computed reads)
  - URL routing at api/scheduling/ prefix wired into root URL conf
  - 22 integration tests covering happy paths, validation errors, and permission checks

affects:
  - phase 06 (session-request): will consume examiner-available-slots endpoint for booking flow

tech-stack:
  added: []
  patterns:
    - "get_object_or_404(Model, pk=pk, examiner=request.user) for ownership enforcement (baked-in access check)"
    - "IntegrityError caught in view post() for unique_together violations — returns 400"
    - "is_verified=True required on examiner test users due to IsEmailVerified default permission class"

key-files:
  created:
    - scheduling/serializers.py
    - scheduling/urls.py
  modified:
    - scheduling/views.py
    - scheduling/tests.py
    - MockIT/urls.py

key-decisions:
  - "IntegrityError on unique_together caught in view POST and returned as 400 (DRF serializer cannot validate without examiner FK at validation time)"
  - "Examiner test users need is_verified=True due to global IsEmailVerified permission class"

patterns-established:
  - "Ownership check via get_object_or_404(Model, pk=pk, examiner=request.user) — 404 on both missing and not-owned objects"

requirements-completed: [AVAIL-01, AVAIL-02, AVAIL-03, AVAIL-04, AVAIL-05]

duration: 16min
completed: "2026-03-30"
---

# Phase 05 Plan 02: Scheduling API Views, Serializers, and URL Patterns Summary

**6 REST endpoints for examiner availability management with DRF serializers, ownership enforcement, and 32 scheduling tests (all passing)**

## Performance

- **Duration:** 16 min
- **Started:** 2026-03-30T07:00:27Z
- **Completed:** 2026-03-30T07:16:27Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments

- AvailabilitySlotSerializer with `validate_start_time` rejecting non-hour times and times outside 08:00-21:00
- 6 APIView classes covering CRUD for AvailabilitySlot and BlockedDate, plus ExaminerAvailableSlotsView and ExaminerIsAvailableView
- Ownership enforced via `get_object_or_404(Model, pk=pk, examiner=request.user)` — unauthorized access returns 404 not 403
- Root URL conf updated at `api/scheduling/` prefix
- 22 new integration tests across 4 test classes (32 total in scheduling.tests, all passing)

## Task Commits

1. **Task 1: Create serializers, views, and URL patterns** - `542812d` (feat)
2. **Task 2: Integration tests for all scheduling API endpoints** - `601ffd9` (test)

**Plan metadata:** (docs commit — see final_commit below)

## Files Created/Modified

- `scheduling/serializers.py` — AvailabilitySlotSerializer (with start_time validation) and BlockedDateSerializer
- `scheduling/views.py` — 6 APIView classes for all scheduling endpoints
- `scheduling/urls.py` — URL patterns for all 6 endpoints
- `MockIT/urls.py` — Root URL conf updated with api/scheduling/ include
- `scheduling/tests.py` — 22 integration tests appended (TestAvailabilitySlotAPI, TestBlockedDateAPI, TestAvailableSlotsEndpoint, TestIsAvailableEndpoint)

## Decisions Made

- **IntegrityError caught in POST view**: DRF serializer cannot validate `unique_together` when `examiner` is not in serializer fields (injected at save time). Wrapped `serializer.save()` in `try/except IntegrityError` to return 400.
- **is_verified=True on examiner test users**: The project-wide `IsEmailVerified` permission class (default permission) requires examiners to be verified. Test users must be created with `is_verified=True`.

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] IntegrityError not caught for duplicate availability slot creation**
- **Found during:** Task 2 (integration tests)
- **Issue:** POST with duplicate (examiner, day_of_week, start_time) raised `django.db.utils.IntegrityError` (500) instead of returning 400
- **Fix:** Added `try/except IntegrityError` in `AvailabilitySlotListCreateView.post()` returning 400 with descriptive message
- **Files modified:** scheduling/views.py
- **Verification:** `test_create_duplicate_slot` passes
- **Committed in:** `601ffd9` (Task 2 commit)

**2. [Rule 2 - Missing Critical] Test users missing is_verified=True for examiner role**
- **Found during:** Task 2 (integration tests — all examiner-authenticated tests returned 403)
- **Issue:** Global `IsEmailVerified` permission requires examiners to have `is_verified=True`; test users created without it failed permission check
- **Fix:** Added `is_verified=True` to all 4 examiner `create_user()` calls in integration test setUp methods
- **Files modified:** scheduling/tests.py
- **Verification:** All 32 scheduling tests pass
- **Committed in:** `601ffd9` (Task 2 commit)

---

**Total deviations:** 2 auto-fixed (1 bug, 1 missing critical)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered

- Pre-existing failures in `session.tests` (5 errors: `TypeError: '>=' not supported between 'datetime.datetime' and 'NoneType'` in `SessionStateMachineTests`). These are out of scope — confirmed pre-existing before any changes in this plan.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- All 6 scheduling endpoints fully operational and tested
- Examiner availability data is now accessible via REST API
- Phase 06 (session-request) can use `GET /api/scheduling/examiners/<pk>/available-slots/` to show candidates available booking slots
- No blockers

## Self-Check: PASSED

- scheduling/serializers.py: FOUND
- scheduling/views.py: FOUND
- scheduling/urls.py: FOUND
- 05-02-SUMMARY.md: FOUND
- Commit 542812d: FOUND
- Commit 601ffd9: FOUND

---
*Phase: 05-availability-scheduling*
*Completed: 2026-03-30*
