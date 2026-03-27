---
phase: 03-data-integrity-and-observability
plan: 01
subsystem: api
tags: [django, drf, ielts-scoring, email, resend, logging]

requires:
  - phase: 02-session-hardening
    provides: "Session lifecycle with state machine and transaction management"
provides:
  - "Scoring completeness gate on result release (all 4 IELTS criteria required)"
  - "Graceful email delivery failure handling with logging"
  - "email_warning response field for frontend notification"
affects: [testing, frontend]

tech-stack:
  added: []
  patterns: ["try/except with logging for external service calls", "validation gate before state mutation"]

key-files:
  created: []
  modified:
    - session/views.py
    - main/services/email.py
    - main/views.py

key-decisions:
  - "Email send returns bool rather than raising -- callers decide how to surface failure"

patterns-established:
  - "External service calls wrapped in try/except with logger.error and bool return"
  - "Validation gates placed between fetch and mutation in views"

requirements-completed: [EDGE-02, EDGE-03]

duration: 2min
completed: 2026-03-27
---

# Phase 03 Plan 01: Scoring Completeness & Email Error Handling Summary

**Scoring completeness gate requiring all 4 IELTS criteria before result release, plus graceful email failure handling with warning responses**

## Performance

- **Duration:** 2 min
- **Started:** 2026-03-27T01:26:05Z
- **Completed:** 2026-03-27T01:28:15Z
- **Tasks:** 2
- **Files modified:** 3

## Accomplishments
- ReleaseResultView now rejects release with 400 when any of FC/GRA/LR/PR scores are missing, listing missing criteria by name
- Email service wraps resend API call in try/except, logs errors, returns bool success indicator
- RegisterView and ResendVerificationView include email_warning field when email delivery fails, while always completing the primary action

## Task Commits

Each task was committed atomically:

1. **Task 1: Add scoring completeness validation and email error handling** - `632ccbe` (feat)
2. **Task 2: Update registration and resend views to handle email warnings** - `f6abe04` (feat)

## Files Created/Modified
- `session/views.py` - Added SpeakingCriterion import and scoring completeness check in ReleaseResultView
- `main/services/email.py` - Wrapped resend call in try/except with logging, returns bool
- `main/views.py` - RegisterView and ResendVerificationView capture email result and add email_warning field

## Decisions Made
- Email send function returns bool rather than raising exceptions -- callers decide how to surface failure to the user (email_warning field)

## Deviations from Plan

None - plan executed exactly as written.

## Issues Encountered
None

## User Setup Required
None - no external service configuration required.

## Next Phase Readiness
- Scoring validation and email error handling complete
- Ready for plan 03-02 (audit logging)

---
*Phase: 03-data-integrity-and-observability*
*Completed: 2026-03-27*
