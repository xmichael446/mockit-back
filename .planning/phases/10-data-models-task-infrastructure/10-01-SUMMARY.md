---
phase: 10-data-models-task-infrastructure
plan: 01
subsystem: database
tags: [django, models, migrations, ielts, scoring, ai-feedback]

# Dependency graph
requires: []
provides:
  - ScoreSource IntegerChoices enum (EXAMINER=1, AI=2) in session/models.py
  - CriterionScore.source field with default ScoreSource.EXAMINER
  - unique_together constraint (session_result, criterion, source) on CriterionScore
  - compute_overall_band filtered to EXAMINER-sourced scores only
  - AIFeedbackJob model with Status choices (PENDING/PROCESSING/DONE/FAILED), FK to IELTSMockSession, error_message field
  - Migration 0010_criterionscore_source_aifeedbackjob
affects: [11-transcription-pipeline, 12-ai-feedback-generation, 13-feedback-api-endpoints, 14-websocket-events]

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "ScoreSource enum on CriterionScore separates examiner bands from AI bands"
    - "compute_overall_band always filters by ScoreSource.EXAMINER to prevent AI scores corrupting official bands"
    - "AIFeedbackJob uses IntegerChoices Status nested inside model class (same Django convention as SessionStatus)"

key-files:
  created:
    - session/migrations/0010_criterionscore_source_aifeedbackjob.py
  modified:
    - session/models.py
    - session/tests.py

key-decisions:
  - "ScoreSource enum added after SpeakingCriterion in Choices section — consistent placement with existing pattern"
  - "unique_together updated to 3-field constraint (session_result, criterion, source) — allows EXAMINER and AI scores to coexist for same criterion"
  - "compute_overall_band filters by ScoreSource.EXAMINER only — AI scores never affect official IELTS bands"

patterns-established:
  - "TDD pattern: write failing tests first, then implement, then verify all pass"
  - "AIFeedbackJob.Status as nested IntegerChoices inside model class (mirrors SessionStatus pattern)"

requirements-completed: [AIAS-01, AIAS-05, BGPR-02]

# Metrics
duration: 15min
completed: 2026-04-07
---

# Phase 10 Plan 01: Data Models & Task Infrastructure Summary

**ScoreSource enum and source field added to CriterionScore, compute_overall_band updated to filter EXAMINER-only, and AIFeedbackJob model created for async job lifecycle tracking**

## Performance

- **Duration:** ~15 min
- **Started:** 2026-04-07T17:30:00Z
- **Completed:** 2026-04-07T17:45:00Z
- **Tasks:** 1 (TDD: RED + GREEN commits)
- **Files modified:** 3

## Accomplishments
- Added `ScoreSource(IntegerChoices)` enum with `EXAMINER=1` and `AI=2` to `session/models.py`
- Added `source` field to `CriterionScore` (default `ScoreSource.EXAMINER`) and updated `unique_together` to include `source` — EXAMINER and AI scores for the same criterion can now coexist
- Updated `compute_overall_band` to filter `self.scores.filter(source=ScoreSource.EXAMINER)` — AI scores cannot corrupt official IELTS band calculation
- Created `AIFeedbackJob` model with `Status` choices (`PENDING/PROCESSING/DONE/FAILED`), FK to `IELTSMockSession`, `error_message` field, and `db_index=True` on status
- Generated migration `0010_criterionscore_source_aifeedbackjob` (AlterUniqueTogether + AddField + CreateModel)
- 18 new tests all passing: `CriterionScoreSourceTests` (9 tests) and `AIFeedbackJobTests` (9 tests)

## Task Commits

Each task was committed atomically (TDD pattern):

1. **Task 1 RED: Add failing tests for ScoreSource and AIFeedbackJob** - `120d568` (test)
2. **Task 1 GREEN: Implement ScoreSource, source field, and AIFeedbackJob** - `e0149d1` (feat)

**Plan metadata:** (docs commit follows)

_Note: TDD task has two commits — test first (RED), then implementation (GREEN)._

## Files Created/Modified
- `session/models.py` - Added ScoreSource enum, CriterionScore.source field, updated unique_together and compute_overall_band, added AIFeedbackJob model
- `session/tests.py` - Added CriterionScoreSourceTests and AIFeedbackJobTests (18 tests)
- `session/migrations/0010_criterionscore_source_aifeedbackjob.py` - Migration for source field and AIFeedbackJob model

## Decisions Made
- Placed ScoreSource enum in the Choices section of models.py alongside SpeakingCriterion and SessionStatus — keeps all enums in one discoverable block
- unique_together updated from 2-field to 3-field constraint — this is backward compatible since existing examiner scores will have source=EXAMINER (migration sets default=1)
- AIFeedbackJob Status defined as nested class inside AIFeedbackJob (same pattern as existing SessionStatus)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered

5 pre-existing test failures in `SessionStateMachineTests` and `SessionStartTransactionTests` exist before this plan (TypeError on `scheduled_at=None` in `can_start()`). These are out of scope — the plan's target tests (`CriterionScoreSourceTests`, `AIFeedbackJobTests`) all pass with no regressions.

## User Setup Required

None - no external service configuration required.

## Next Phase Readiness

- Data foundation complete: ScoreSource, CriterionScore.source, and AIFeedbackJob model are all available
- Phase 11 (transcription pipeline) can now write AI scores with `source=ScoreSource.AI` and create `AIFeedbackJob` records
- Phase 12 (AI feedback generation) can query `AIFeedbackJob` and update status as jobs progress
- Phases 13-14 can rely on `source` field to separate examiner vs AI scores in API responses

## Self-Check: PASSED

All files confirmed present. Both task commits verified (120d568, e0149d1). SUMMARY.md created.

---
*Phase: 10-data-models-task-infrastructure*
*Completed: 2026-04-07*
