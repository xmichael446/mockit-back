---
phase: 05-availability-scheduling
plan: 01
subsystem: database
tags: [django, drf, scheduling, availability, datetime, sqlite, tdd]

# Dependency graph
requires:
  - phase: 04-profiles
    provides: TimestampedModel base class, User model with EXAMINER role, test settings (settings_test.py)
  - phase: 03-session
    provides: IELTSMockSession model with SessionStatus choices and nullable scheduled_at

provides:
  - AvailabilitySlot model (recurring weekly 1-hour windows per examiner)
  - BlockedDate model (date exceptions overriding recurring schedule)
  - compute_available_slots() service: 7-day week calendar with available/booked/blocked status
  - is_currently_available() service: real-time availability check based on current UTC time
  - scheduling/migrations/0001_initial.py — DB schema for both models

affects: [05-02-api-endpoints, 06-session-requests]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "TDD with RED/GREEN/REFACTOR in Django TestCase using DJANGO_SETTINGS_MODULE=MockIT.settings_test"
    - "Service layer in scheduling/services/ — pure Python functions imported by views"
    - "datetime.combine(date, time, tzinfo=dt_timezone.utc) for aware UTC datetimes (Pitfall 1)"
    - "scheduled_at__isnull=False filter for nullable DateTimeField (Pitfall 6)"

key-files:
  created:
    - scheduling/__init__.py
    - scheduling/apps.py
    - scheduling/admin.py
    - scheduling/models.py
    - scheduling/services/__init__.py
    - scheduling/services/availability.py
    - scheduling/tests.py
    - scheduling/migrations/0001_initial.py
  modified:
    - MockIT/settings.py

key-decisions:
  - "DayOfWeek IntegerChoices uses MON=0..SUN=6 matching Python date.weekday() convention exactly"
  - "end_time not stored — always start_time + 1h (locked decision from CONTEXT.md)"
  - "blocked status takes priority over booked in compute_available_slots()"
  - "is_currently_available() uses timezone.now() for UTC-aware current time; time compared after .replace(second=0, microsecond=0) floor to minute"

patterns-established:
  - "Pattern: Use DJANGO_SETTINGS_MODULE=MockIT.settings_test for all test runs (SQLite in-memory, PG 14 not available)"
  - "Pattern: Service functions live in scheduling/services/availability.py — separate from views for testability"
  - "Pattern: datetime.combine with tzinfo=dt_timezone.utc prevents naive/aware comparison errors"

requirements-completed: [AVAIL-01, AVAIL-03, AVAIL-04, AVAIL-05]

# Metrics
duration: 15min
completed: 2026-03-30
---

# Phase 05 Plan 01: Availability Scheduling Data Layer Summary

**AvailabilitySlot and BlockedDate models with compute_available_slots() and is_currently_available() service functions — 11 unit tests passing via TDD**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-03-30T06:42:00Z
- **Completed:** 2026-03-30T06:57:00Z
- **Tasks:** 2
- **Files modified:** 9

## Accomplishments
- Scaffolded `scheduling/` Django app with `AvailabilitySlot` and `BlockedDate` models, migrations, and admin registration
- Implemented `compute_available_slots()` returning a 7-day week calendar with per-slot status (available/booked/blocked), correctly handling nullable `scheduled_at` and aware UTC datetimes
- Implemented `is_currently_available()` checking current UTC time against recurring slots, blocked dates, and session bookings
- 11 unit tests written TDD-style (RED then GREEN) — all pass in 8.8s

## Task Commits

Each task was committed atomically:

1. **Task 1: Scaffold scheduling app, models, migrations, and admin** - `c3ec827` (feat)
2. **Task 2 RED: Failing tests for service functions** - `[test commit hash]` (test)
3. **Task 2 GREEN: Implement compute_available_slots and is_currently_available** - `ea850f7` (feat)

_Note: Task 2 used TDD — test commit (RED) then implementation commit (GREEN)_

## Files Created/Modified
- `scheduling/models.py` — AvailabilitySlot (DayOfWeek MON=0..SUN=6, unique_together) and BlockedDate models
- `scheduling/services/availability.py` — compute_available_slots() and is_currently_available() functions
- `scheduling/tests.py` — TestComputeAvailableSlots (7 tests) and TestIsCurrentlyAvailable (4 tests)
- `scheduling/admin.py` — Admin registration with list_display/list_filter for both models
- `scheduling/migrations/0001_initial.py` — Initial migration for AvailabilitySlot and BlockedDate
- `MockIT/settings.py` — Added scheduling.apps.SchedulingConfig to INSTALLED_APPS

## Decisions Made
- `DayOfWeek` IntegerChoices: MON=0..SUN=6 matches Python `date.weekday()` exactly (no Sunday=0 confusion)
- No `end_time` field stored — locked decision from CONTEXT.md; end always computed as `start_time + 1h`
- Blocked status takes priority over booked: if a day is blocked, all its slots show "blocked" regardless of bookings
- `is_currently_available()` floors current time to minute precision (`replace(second=0, microsecond=0)`) for clean `<=` comparison
- `compute_available_slots()` filters `scheduled_at__isnull=False` to exclude sessions with no scheduled time (Pitfall 6 from research)

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered
- `python manage.py makemigrations` fails with PostgreSQL 13 (Django 5.2 requires PG 14) — used `DJANGO_SETTINGS_MODULE=MockIT.settings_test` for makemigrations as per established Phase 04 decision
- `showmigrations scheduling` shows `[ ]` when using default PG settings (DB not accessible) — expected behavior; migration confirmed applied with test settings

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- `scheduling/` app fully bootstrapped: models, migrations, service layer, and test infrastructure all ready
- Plan 02 can build REST API endpoints directly on top of these models and service functions
- `compute_available_slots()` and `is_currently_available()` are the two key entry points for the API views in Plan 02
- Known extension point: Phase 6's `SessionRequest` (ACCEPTED status) should also be counted as bookings in `compute_available_slots()` — documented in research Open Questions

## Self-Check: PASSED

- scheduling/models.py: FOUND
- scheduling/services/availability.py: FOUND
- scheduling/tests.py: FOUND
- scheduling/migrations/0001_initial.py: FOUND
- 05-01-SUMMARY.md: FOUND
- Commit c3ec827 (Task 1 scaffold): FOUND
- Commit ea850f7 (Task 2 implementation): FOUND
- 11/11 tests pass

---
*Phase: 05-availability-scheduling*
*Completed: 2026-03-30*
