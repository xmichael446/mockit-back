---
phase: 04-profiles
plan: 02
subsystem: api
tags: [django, drf, profiles, serializers, views, url-patterns, cross-app-integration]

# Dependency graph
requires:
  - phase: 04-profiles plan 01
    provides: ExaminerProfile, CandidateProfile, ExaminerCredential, ScoreHistory models and signals

provides:
  - Profile REST API endpoints (examiner/candidate, own/public)
  - ExaminerCredential create/update endpoint
  - Cross-app wiring: completed_session_count atomic increment on session end
  - Cross-app wiring: ScoreHistory append on result release
  - 23 passing unit/API tests for all profile endpoints

affects:
  - scheduling phase (will use ExaminerProfile.completed_session_count)
  - frontend API documentation
  - any phase referencing candidate score history

# Tech tracking
tech-stack:
  added: []
  patterns:
    - "Public vs detail serializer split: DetailSerializer includes sensitive fields (phone), PublicSerializer excludes them"
    - "Role-based view access: _is_examiner()/_is_candidate() guards returning 404 (not 403) for role mismatch"
    - "F() expression for atomic field increment in cross-app integration"
    - "get_or_create() pattern for idempotent score history and credential upsert"

key-files:
  created: []
  modified:
    - main/serializers.py
    - main/views.py
    - main/urls.py
    - main/tests.py
    - session/views.py

key-decisions:
  - "Role mismatch on /me/ endpoints returns 404 (not 403) to avoid disclosing role information"
  - "is_verified=True required for examiner test users due to IsEmailVerified global permission"
  - "ScoreHistory uses get_or_create() to be idempotent (double-release safe)"
  - "CandidateProfile.DoesNotExist silently skipped for guest candidates without profiles"

patterns-established:
  - "Detail serializer shows phone (owner-facing), public serializer hides phone (world-facing)"
  - "read_only_fields on is_verified and completed_session_count enforces admin-only mutation"
  - "validate_target_speaking_score/validate_current_speaking_score enforce 0.5 step increments"

requirements-completed: [EXAM-01, EXAM-02, EXAM-03, EXAM-04, EXAM-05, EXAM-06, STUD-01, STUD-02, STUD-04]

# Metrics
duration: 22min
completed: 2026-03-30
---

# Phase 04 Plan 02: Profile API Summary

**Profile CRUD endpoints with public/private serializer split, credential management, atomic session count increment, and score history wiring**

## Performance

- **Duration:** 22 min
- **Started:** 2026-03-30T06:00:00Z
- **Completed:** 2026-03-30T06:21:49Z
- **Tasks:** 2
- **Files modified:** 5

## Accomplishments
- 5 new profile API endpoints registered: examiner/me/, examiner/<id>/, examiner/me/credential/, candidate/me/, candidate/<id>/
- Public examiner profile hides phone field; detail profile shows it; is_verified/completed_session_count read-only
- Cross-app integration: session end atomically increments ExaminerProfile.completed_session_count via F() expression
- Cross-app integration: result release appends ScoreHistory record for candidate via get_or_create()
- 23 tests pass (17 new API tests + 6 existing signal/phone tests)

## Task Commits

Each task was committed atomically:

1. **Task 1: Create profile serializers, views, and URL patterns** - `bb79fe1` (feat)
2. **Task 2: Wire cross-app integration and add comprehensive API tests** - `2fd0d24` (feat)

**Plan metadata:** (pending)

## Files Created/Modified
- `main/serializers.py` - Added 7 new serializers: UserNestedSerializer, ExaminerCredentialSerializer, ExaminerProfileDetailSerializer, ExaminerProfilePublicSerializer, ScoreHistorySerializer, CandidateProfileDetailSerializer, CandidateProfilePublicSerializer
- `main/views.py` - Added 5 new APIView classes with role guards and MultiPartParser support
- `main/urls.py` - Added 5 profile URL patterns under /api/profiles/
- `main/tests.py` - Added 5 test classes covering all profile endpoints (17 new tests)
- `session/views.py` - Added F() increment in EndSessionView, ScoreHistory append in ReleaseResultView

## Decisions Made
- Role mismatch on /me/ endpoints returns 404 (not 403) to avoid disclosing role information
- ScoreHistory uses get_or_create() to be idempotent — double-release does not create duplicate records
- CandidateProfile.DoesNotExist silently skipped (guest candidates pre-Phase 4 have no profile)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Test users missing is_verified=True for examiner role**
- **Found during:** Task 2 (running test suite)
- **Issue:** All test API calls to examiner profile endpoints returned 403 — IsEmailVerified global permission requires examiners to have is_verified=True, but create_user() defaults to False
- **Fix:** Added is_verified=True to all examiner user creation in test setUp methods
- **Files modified:** main/tests.py
- **Verification:** All 23 tests pass
- **Committed in:** 2fd0d24 (Task 2 commit)

---

**Total deviations:** 1 auto-fixed (1 bug)
**Impact on plan:** Auto-fix necessary for tests to function correctly. No scope creep.

## Issues Encountered
- Pre-existing session test failures (5 tests in session.tests.SessionStateMachineTests) due to `scheduled_at=None` TypeError in session/models.py — verified pre-existing before this plan's changes, out of scope.

## Known Stubs
None — all profile endpoints return real data from the database.

## User Setup Required
None — no external service configuration required.

## Next Phase Readiness
- All profile API endpoints functional and tested
- Cross-app wiring in place for session count and score history
- Ready for Phase 05 (scheduling) which will extend ExaminerProfile with availability slots
- No blockers

---
*Phase: 04-profiles*
*Completed: 2026-03-30*
