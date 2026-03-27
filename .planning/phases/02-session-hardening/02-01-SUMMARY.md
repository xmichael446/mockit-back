---
phase: 02-session-hardening
plan: 01
subsystem: api
tags: [django, state-machine, secrets, validation, session-lifecycle]

# Dependency graph
requires: []
provides:
  - "State machine guard methods (can_start, can_end, can_join, can_ask_question, can_start_part, can_end_part, can_accept_invite)"
  - "State machine transition methods (start, end, assert_in_progress)"
  - "Cryptographically secure invite token (xxx-yyyy letter-only format via secrets module)"
  - "MockPreset immutability (save/delete blocked when sessions exist)"
affects: [02-session-hardening]

# Tech tracking
tech-stack:
  added: [secrets]
  patterns: [state-machine-guards, state-machine-transitions, model-save-override-immutability]

key-files:
  created: [session/migrations/0009_alter_ieltsmocksession_invite_token.py, MockIT/settings_test.py]
  modified: [session/models.py, session/tests.py]

key-decisions:
  - "Used SQLite settings_test.py for test runner since dev PostgreSQL is v13 (Django 5.2 requires v14+)"
  - "Changed invite_token max_length from 9 to 8 to match new xxx-yyyy format (was xxxx-xxxx)"

patterns-established:
  - "State machine pattern: can_X() guard returns bool, X() transition raises ValidationError on invalid state"
  - "Preset immutability via save/delete override checking self.sessions.exists()"
  - "Test settings module (MockIT/settings_test.py) for SQLite-based test execution"

requirements-completed: [REF-01, REF-03, EDGE-04]

# Metrics
duration: 5min
completed: 2026-03-27
---

# Phase 02 Plan 01: Session State Machine Summary

**State machine with 7 guard + 3 transition methods on IELTSMockSession, secrets-based invite token (xxx-yyyy), and MockPreset immutability via save/delete overrides**

## Performance

- **Duration:** 5 min
- **Started:** 2026-03-27T00:53:04Z
- **Completed:** 2026-03-27T00:58:06Z
- **Tasks:** 1 (TDD: RED + GREEN)
- **Files modified:** 4

## Accomplishments
- Added 7 guard methods (can_start, can_end, can_join, can_ask_question, can_start_part, can_end_part, can_accept_invite) to IELTSMockSession
- Added 3 transition/assertion methods (start, end, assert_in_progress) with ValidationError on invalid state
- Replaced random.choices() with secrets.choice() for invite token generation (xxx-yyyy letter-only format)
- Added save()/delete() overrides to MockPreset blocking mutation when sessions exist
- Created 23 unit tests across 3 test classes, all passing

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Failing tests** - `4f71945` (test)
2. **Task 1 (GREEN): Implementation** - `b86e44a` (feat)

_TDD task with RED/GREEN commits._

## Files Created/Modified
- `session/models.py` - State machine methods, secure invite token, preset immutability
- `session/tests.py` - 23 unit tests (SessionStateMachineTests, InviteTokenTests, PresetImmutabilityTests)
- `session/migrations/0009_alter_ieltsmocksession_invite_token.py` - invite_token max_length 9 -> 8
- `MockIT/settings_test.py` - SQLite test settings for test runner

## Decisions Made
- Used SQLite via settings_test.py for running tests since local PostgreSQL is v13 and Django 5.2 requires v14+
- Changed invite_token max_length from 9 to 8 to match new xxx-yyyy format (3+1+4=8 chars)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Created SQLite test settings module**
- **Found during:** Task 1 RED phase (test execution)
- **Issue:** Local PostgreSQL is v13.23; Django 5.2 requires v14+. Tests cannot run against local DB.
- **Fix:** Created MockIT/settings_test.py with SQLite in-memory database for test execution
- **Files modified:** MockIT/settings_test.py
- **Verification:** All 23 tests pass with DJANGO_SETTINGS_MODULE=MockIT.settings_test
- **Committed in:** 4f71945 (RED phase commit)

**2. [Rule 1 - Bug] Updated invite_token max_length**
- **Found during:** Task 1 GREEN phase
- **Issue:** Token format changed from xxxx-xxxx (9 chars) to xxx-yyyy (8 chars), but max_length was still 9
- **Fix:** Changed max_length=9 to max_length=8, created migration
- **Files modified:** session/models.py, session/migrations/0009_alter_ieltsmocksession_invite_token.py
- **Verification:** Migration applies cleanly, tests pass
- **Committed in:** b86e44a (GREEN phase commit)

---

**Total deviations:** 2 auto-fixed (1 blocking, 1 bug)
**Impact on plan:** Both fixes necessary for correctness. No scope creep.

## Issues Encountered
- PostgreSQL v13 incompatible with Django 5.2 -- resolved by creating SQLite test settings
- PostgreSQL credentials not set up on local machine -- bypassed via SQLite approach

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- State machine foundation complete -- Plan 02 can now refactor views.py to use these guard/transition methods
- All 23 tests passing as regression safety net for Plan 02 refactoring

---
*Phase: 02-session-hardening*
*Completed: 2026-03-27*
