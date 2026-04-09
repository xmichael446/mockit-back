# Milestones

## v1.4 AI Assessment Rebuild (Gemini Audio) (Shipped: 2026-04-09)

**Phases completed:** 3 phases, 3 plans, 6 tasks

**Key accomplishments:**

- google-genai SDK installed, faster-whisper/anthropic removed, GEMINI_API_KEY fail-fast configured, and end-to-end webm smoke test script created for Gemini Files API verification
- One-liner:
- Single Gemini pipeline wired in tasks.py (tuple unpack), all test mocks updated from anthropic/faster-whisper to Gemini patterns, and transcription.py deleted to complete the v1.4 migration.

---

## v1.3 AI Feedback & Assessment (Shipped: 2026-04-08)

**Phases completed:** 5 phases, 10 plans, 11 tasks

**Key accomplishments:**

- ScoreSource enum and source field added to CriterionScore, compute_overall_band updated to filter EXAMINER-only, and AIFeedbackJob model created for async job lifecycle tracking
- One-liner:
- faster-whisper CPU transcription service with lazy WhisperModel loading, initial_prompt from SessionQuestion context, and AIFeedbackJob.transcript storage
- transcribe_session() wired into run_ai_feedback background task with 7 mocked tests verifying TRNS-01 through TRNS-04
- HTTP trigger surface for examiner-initiated AI feedback: POST returns 202+job_id, GET returns transcript/status, with ownership, status, and duplicate-job guards
- Claude API assessment service using forced tool_use to produce IELTS band scores (1-9) and 3-4 sentence feedback for all four speaking criteria (FC, GRA, LR, PR)
- run_ai_feedback task wired to Claude API assessment service via bulk_create of 4 AI CriterionScore records, with 13 new tests covering score creation, feedback storage, error paths, and question context building
- One-liner:

---

## v1.2 Profiles & Scheduling (Shipped: 2026-03-30)

**Phases completed:** 6 phases, 9 plans, 17 tasks

**Key accomplishments:**

- Four Django profile models (ExaminerProfile, CandidateProfile, ExaminerCredential, ScoreHistory) with Uzbekistan phone validation, auto-creation via post_save signal, admin registration, and 6 passing tests
- Profile CRUD endpoints with public/private serializer split, credential management, atomic session count increment, and score history wiring
- AvailabilitySlot and BlockedDate models with compute_available_slots() and is_currently_available() service functions — 11 unit tests passing via TDD
- 6 REST endpoints for examiner availability management with DRF serializers, ownership enforcement, and 32 scheduling tests (all passing)
- SessionRequest model with PENDING/ACCEPTED/REJECTED/CANCELLED state machine (6 transition methods), migration, and availability service extended to mark ACCEPTED requests as booked slots
- Session request endpoints with atomic accept (select_for_update), slot validation, role guards, and 16 integration tests covering all flows
- CandidateProfile.current_speaking_score auto-updated to overall_band on every result release via 2-line addition inside existing try/except block in ReleaseResultView.post()
- Three Resend-pattern notification functions wired into session request lifecycle (new request to examiner, accepted/rejected to candidate)
- REST API documentation for all v1.2 endpoints: profiles (8 endpoints), availability/blocked-dates (9 endpoints), and session requests (5 endpoints) added to docs/api/ with full request/response schemas and error scenarios

---

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
