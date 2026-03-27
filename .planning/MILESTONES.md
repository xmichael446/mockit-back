# Milestones

## v1.1 Clean-up, Security & Edge Cases (Shipped: 2026-03-27)

**Phases completed:** 3 phases, 6 plans, 11 tasks

**Key accomplishments:**

- All 10 hardcoded secrets moved to environment variables via python-dotenv with fail-fast os.environ[] loading
- DRF ScopedRateThrottle on register (10/hr), guest-join (20/hr), and accept-invite (20/hr) endpoints
- State machine with 7 guard + 3 transition methods on IELTSMockSession, secrets-based invite token (xxx-yyyy), and MockPreset immutability via save/delete overrides
- Replaced all 10 inline status checks in views.py with model state machine methods and wrapped session start in transaction.atomic() for rollback-safe room creation
- Scoring completeness gate requiring all 4 IELTS criteria before result release, plus graceful email failure handling with warning responses
- Structured audit logging for session create/start/end, result submit, and result release via mockit.audit logger to console and logs/audit.log

---

## v1.0 — Initial Platform (Pre-GSD)

**Shipped:** Before 2026-03-27 (brownfield)
**Summary:** Full IELTS Speaking mock exam platform with session lifecycle, real-time WebSocket events, 100ms video integration, and IELTS band scoring.

**Validated capabilities:**

- Custom User model (EXAMINER/CANDIDATE/GUEST roles)
- Token authentication (HTTP + WebSocket)
- Question bank hierarchy (Topic -> Question -> FollowUp)
- MockPreset templates
- Full session lifecycle (create -> invite -> start -> conduct -> score -> release)
- Real-time WebSocket broadcast events
- 100ms video room integration
- Email verification via Resend
- Guest join flow
- IELTS band scoring (4 criteria, 0.5 rounding)

**Phases:** Pre-GSD (no phase tracking)

---

## v1.1 — Clean-up, Security & Edge Cases (Current)

**Started:** 2026-03-27
**Goal:** Harden the codebase for production readiness.
**Status:** Defining requirements
