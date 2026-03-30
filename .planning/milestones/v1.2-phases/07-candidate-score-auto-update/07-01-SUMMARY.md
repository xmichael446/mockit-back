---
phase: 07-candidate-score-auto-update
plan: "01"
subsystem: api
tags: [django, drf, scoring, candidate-profile]

# Dependency graph
requires:
  - phase: 04-profiles
    provides: CandidateProfile model with current_speaking_score field, ScoreHistory model
  - phase: 04-profiles
    provides: ReleaseResultView.post() with ScoreHistory.get_or_create() block

provides:
  - CandidateProfile.current_speaking_score auto-updated on every result release
  - Test class ReleaseResultScoreUpdateTests with 4 tests covering happy path, guest candidate, no candidate, idempotent release

affects: [candidate-profile, session-release, scoring]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "current_speaking_score update inside existing try/except CandidateProfile.DoesNotExist block — no duplicate error handling"

key-files:
  created: []
  modified:
    - session/views.py
    - session/tests.py

key-decisions:
  - "Update placed inside existing try/except CandidateProfile.DoesNotExist block (lines 947-957) — guest candidates without profiles silently skipped, no new exception surface"
  - "update_fields=['current_speaking_score', 'updated_at'] used for targeted save — no full model save"

patterns-established:
  - "Score update co-located with ScoreHistory creation to keep result-release side-effects in one block"

requirements-completed: [STUD-03]

# Metrics
duration: 8min
completed: 2026-03-30
---

# Phase 07 Plan 01: Candidate Score Auto-Update Summary

**CandidateProfile.current_speaking_score auto-updated to overall_band on every result release via 2-line addition inside existing try/except block in ReleaseResultView.post()**

## Performance

- **Duration:** ~8 min
- **Started:** 2026-03-30T09:04:00Z
- **Completed:** 2026-03-30T09:08:01Z
- **Tasks:** 1 (TDD: test commit + feat commit)
- **Files modified:** 2

## Accomplishments

- Added `candidate_profile.current_speaking_score = result.overall_band` and `candidate_profile.save(update_fields=...)` inside the existing `try/except CandidateProfile.DoesNotExist` block in `ReleaseResultView.post()`
- Added `ReleaseResultScoreUpdateTests` class in `session/tests.py` with 4 tests: happy path, no candidate profile (guest), no candidate, and idempotent re-release
- All 4 new tests pass; existing release flow (ScoreHistory, broadcast, audit log) unchanged

## Task Commits

Each task was committed atomically:

1. **Task 1 (RED): Add failing tests** - `87a5df8` (test)
2. **Task 1 (GREEN): Implement score update** - `fa9b606` (feat)

_Note: TDD task has two commits (test RED → feat GREEN)_

## Files Created/Modified

- `session/views.py` — Added 2 lines inside existing try/except block: sets and saves `current_speaking_score`
- `session/tests.py` — Added imports (`CandidateProfile`, `SessionResult`, `CriterionScore`, `SpeakingCriterion`, `Decimal`) and `ReleaseResultScoreUpdateTests` class (4 tests)

## Decisions Made

- Update placed inside existing `try/except CandidateProfile.DoesNotExist` block — avoids adding a duplicate try/except and re-uses the already-fetched `candidate_profile` variable from line 948
- `update_fields=["current_speaking_score", "updated_at"]` for a targeted DB write, consistent with other `save()` calls throughout `views.py`

## Deviations from Plan

None — plan executed exactly as written.

## Issues Encountered

Pre-existing test failures in `SessionStateMachineTests` and `SessionStartTransactionTests` (5 errors) were discovered when running the full test suite. Root cause: `can_start()` in `session/models.py` performs `timezone.now() >= self.scheduled_at` but test fixtures create sessions without `scheduled_at`, causing a `TypeError`. These failures are **pre-existing and unrelated to this plan's changes**. Logged to deferred-items as out-of-scope.

## Known Stubs

None — `current_speaking_score` is wired directly from `result.overall_band` on every release.

## User Setup Required

None — no external service configuration required.

## Next Phase Readiness

- STUD-03 fulfilled: candidate's current score auto-reflects latest session result
- Phase 07 complete — all 1 plan done
- Pre-existing `can_start()` / `scheduled_at=None` bug in session state machine tests should be addressed in a future bugfix phase

---
*Phase: 07-candidate-score-auto-update*
*Completed: 2026-03-30*
