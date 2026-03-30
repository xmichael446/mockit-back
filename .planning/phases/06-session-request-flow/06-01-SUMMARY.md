---
phase: 06-session-request-flow
plan: "01"
subsystem: database
tags: [django, drf, state-machine, scheduling, session-request]

# Dependency graph
requires:
  - phase: 05-availability-scheduling
    provides: AvailabilitySlot model and compute_available_slots service
provides:
  - SessionRequest model with PENDING/ACCEPTED/REJECTED/CANCELLED state machine
  - Migration 0002_sessionrequest.py for scheduling app
  - Extended compute_available_slots that marks ACCEPTED requests as booked
affects:
  - 06-02 (session request views — depends on this model and service)

# Tech tracking
tech-stack:
  added: []
  patterns:
    - DRF ValidationError raised from model state machine methods (matches session/models.py pattern)
    - accepted_booked set for O(1) slot status lookup keyed by (slot_id, date)

key-files:
  created:
    - scheduling/migrations/0002_sessionrequest.py
  modified:
    - scheduling/models.py
    - scheduling/services/availability.py
    - scheduling/tests.py

key-decisions:
  - "SessionRequest.Status uses IntegerChoices (PENDING=1, ACCEPTED=2, REJECTED=3, CANCELLED=4) matching existing SessionStatus pattern"
  - "State machine methods raise rest_framework.exceptions.ValidationError to propagate cleanly through DRF views"
  - "accepted_booked set keyed by (slot_id, requested_date) — not by datetime window — because SessionRequest stores date not datetime"

patterns-established:
  - "State machine guards (can_X) return bool; transitions (X) call guard and raise ValidationError if invalid"
  - "Availability service: blocked > booked (session) > booked (accepted request) > available — priority chain"

requirements-completed: [REQ-05, REQ-02, REQ-06]

# Metrics
duration: 12min
completed: "2026-03-30"
---

# Phase 06 Plan 01: Session Request Model & Availability Extension Summary

**SessionRequest model with PENDING/ACCEPTED/REJECTED/CANCELLED state machine (6 transition methods), migration, and availability service extended to mark ACCEPTED requests as booked slots**

## Performance

- **Duration:** ~12 min
- **Started:** 2026-03-30T08:25:43Z
- **Completed:** 2026-03-30T08:37:54Z
- **Tasks:** 2
- **Files modified:** 4 (scheduling/models.py, scheduling/migrations/0002_sessionrequest.py, scheduling/services/availability.py, scheduling/tests.py)

## Accomplishments
- SessionRequest model with complete state machine: PENDING->ACCEPTED/REJECTED/CANCELLED, ACCEPTED->CANCELLED
- Migration created and verified against test database
- compute_available_slots extended: ACCEPTED SessionRequests now mark their slot as "booked", blocked date still takes priority
- 14 new unit tests added (10 model state machine + 4 availability extension)

## Task Commits

Each task was committed atomically:

1. **Task 1: SessionRequest model with state machine + migration** - `94f2569` (feat)
2. **Task 2: Extend compute_available_slots to subtract ACCEPTED requests** - `0bb01b4` (feat)

**Plan metadata:** (docs commit — see below)

_Note: Both tasks used TDD (RED -> GREEN) pattern_

## Files Created/Modified
- `scheduling/models.py` - Added SessionRequest model with Status IntegerChoices and 6 state machine methods
- `scheduling/migrations/0002_sessionrequest.py` - Auto-generated migration for SessionRequest table
- `scheduling/services/availability.py` - Added accepted_requests query and accepted_booked set; added elif branch in status loop
- `scheduling/tests.py` - Added TestSessionRequestModel (10 tests) and TestComputeAvailableSlotsWithRequests (4 tests)

## Decisions Made
- `rest_framework.exceptions.ValidationError` used in model methods (not `django.core.exceptions.ValidationError`) — matches session/models.py pattern and propagates cleanly through DRF views
- accepted_booked set keyed by `(slot_id, date)` using `requested_date` (DateField) — SessionRequest does not store a datetime, so lookup is by slot + date pair

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
- 5 pre-existing failures in `session.tests` (SessionStateMachineTests and SessionStartTransactionTests) related to `can_start()` receiving `scheduled_at=None`. Confirmed pre-existing by stashing changes and running tests. Out of scope per deviation rules — logged here for awareness.

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- SessionRequest model and migration are complete and tested — ready for view layer (Plan 06-02)
- compute_available_slots correctly reflects ACCEPTED requests — candidate-facing availability endpoint will show accurate booking status
- Pre-existing session test failures should be investigated in a separate task (out of scope for this plan)

---
*Phase: 06-session-request-flow*
*Completed: 2026-03-30*

## Self-Check: PASSED

- FOUND: scheduling/models.py
- FOUND: scheduling/migrations/0002_sessionrequest.py
- FOUND: scheduling/services/availability.py
- FOUND: scheduling/tests.py
- FOUND: 06-01-SUMMARY.md
- FOUND commit 94f2569: feat(06-01): add SessionRequest model with state machine + migration
- FOUND commit 0bb01b4: feat(06-01): extend compute_available_slots to subtract ACCEPTED requests
