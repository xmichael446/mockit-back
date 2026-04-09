# MockIT

## What This Is

An IELTS Speaking mock exam platform where examiners conduct live sessions with candidates over video. Examiners maintain profiles with credentials, set weekly availability, and accept booking requests from candidates. Sessions are conducted with questions from a curated bank, scored across four IELTS criteria (FC, GRA, LR, PR), with results and score history tracked per candidate. AI-powered assessment via Gemini Pro provides automated band scores and pronunciation feedback from session audio.

## Core Value

Examiners can conduct a complete, real-time IELTS Speaking mock exam with a candidate — from invite through scoring — with minimal friction.

## Current State

v1.4 shipped. No active milestone — ready for next milestone planning.

## Requirements

### Validated

<!-- Shipped and confirmed valuable. -->

- Custom User model with EXAMINER/CANDIDATE/GUEST roles
- Token authentication (HTTP header + WebSocket query param)
- Question bank: Topic -> Question -> FollowUpQuestion hierarchy
- MockPreset for reusable exam templates
- Full session lifecycle: create -> invite -> start -> conduct -> score -> release
- Real-time WebSocket events via Django Channels broadcast pattern
- 100ms video room integration (create room, generate app tokens)
- Email verification via Resend
- Guest join flow (no registration required)
- IELTS band scoring with 4-criteria calculation and 0.5 rounding
- Secrets moved to environment variables (.env) — v1.1
- Rate limiting on auth and invite endpoints — v1.1
- Stronger invite token generation (secrets module) — v1.1
- Session status state machine (centralized validation) — v1.1
- Transaction management for multi-step operations — v1.1
- Scoring validation (require all 4 criteria before release) — v1.1
- Email delivery error handling — v1.1
- Audit logging for critical actions — v1.1
- Preset immutability after session creation — v1.1
- Examiner profiles with bio, credentials, verification badge, phone — v1.2
- Candidate profiles with target score, score history, auto-update — v1.2
- Examiner weekly availability (1-hour windows, blocked dates, real-time check) — v1.2
- Session request flow (submit → accept/reject → cancel) with atomic session creation — v1.2
- select_for_update double-booking prevention on accept — v1.2
- Email notifications at booking trigger points via Resend — v1.2
- Full API docs for profiles, availability, and requests — v1.2
- ScoreSource enum (EXAMINER/AI) on CriterionScore with EXAMINER-only band calculation — v1.3 Phase 10
- AIFeedbackJob model with PENDING/PROCESSING/DONE/FAILED status tracking — v1.3 Phase 10
- django-q2 background task infrastructure with ORM broker — v1.3 Phase 10
- Audio transcription via faster-whisper with SessionQuestion context — v1.3 Phase 11
- AI feedback trigger endpoint (POST 202 + GET status/transcript) — v1.3 Phase 11
- Claude API assessment with tool_use for 4-criterion IELTS scoring — v1.3 Phase 12
- AI CriterionScore bulk creation (FC, GRA, LR, PR) with actionable feedback — v1.3 Phase 12
- Monthly AI feedback limit (default 10) with select_for_update race prevention — v1.3 Phase 13
- AI feedback GET returns scores array with per-criterion band and feedback — v1.3 Phase 14
- WebSocket ai_feedback_ready event on job completion — v1.3 Phase 14
- Complete API docs for AI feedback endpoints with schemas and error scenarios — v1.3 Phase 14
- Gemini Pro direct audio assessment replacing faster-whisper + Claude pipeline — v1.4
- Audio-aware IELTS examiner system prompt (pronunciation, intonation, rhythm) — v1.4
- API contract preserved through AI pipeline rebuild (endpoints, WebSocket, monthly limits) — v1.4
- google-genai SDK replacing faster-whisper + anthropic dependencies — v1.4

### Active

<!-- No active milestone — ready for /gsd:new-milestone -->

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Integration/unit test suite — deferred to dedicated testing milestone
- Redis channel layer migration — infrastructure change, separate milestone
- OAuth/social login — email/password sufficient for now
- Mobile app — web-first platform
- WebSocket header-based auth migration — breaking change, requires frontend coordination
- DEBUG controlled by environment variable — deferred from v1.1 (SEC-03)
- CORS restricted to allowed origins — deferred from v1.1 (SEC-04)

## Context

- Backend only (Django/DRF). Frontend is a separate React/TypeScript app.
- Deployed at mockit.live, backend at mi-back.xmichael446.com
- 100ms for video rooms, Resend for transactional email
- InMemoryChannelLayer in dev, Redis planned for production
- v1.1 shipped: 3 phases, 6 plans, 10 files changed, 515 insertions
- v1.2 shipped: 6 phases, 9 plans, 62 files changed, 8008 insertions
- scheduling/ app added in v1.2 (availability, requests, email notifications)
- 89+ tests across main/ and scheduling/ apps (23 profile, 62 scheduling, 4 score update)
- session/views.py refactored — status checks centralized into model state machine
- Audit logging active via `mockit.audit` logger to console + `logs/audit.log`
- v1.3 shipped: 5 phases, 10 plans, AI feedback pipeline (faster-whisper + Claude)
- v1.4 shipped: 3 phases, 3 plans, rebuilt pipeline on Gemini Pro (8 files, 431 insertions)
- 96+ session tests (assessment, trigger, delivery — transcription tests removed with pipeline)
- django-q2 for background tasks, google-genai==1.71.0 for Gemini Pro audio assessment
- AI feedback: examiner triggers → single Gemini call (audio → scores + transcript) → WebSocket push
- Pydantic-validated structured output with Field(ge=1, le=9) band validation
- No faster-whisper or anthropic dependencies remain in codebase

## Constraints

- **Stack**: Django 5.2 + DRF + Channels 4.x — no framework changes
- **Backward compat**: REST API and WebSocket event contracts must not break
- **Growing tests**: 103+ tests from v1.3; no dedicated testing milestone yet
- **Frontend dependency**: Any API contract changes need frontend coordination

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Defer test suite to separate milestone | Focus v1.1 purely on hardening; tests are a large effort | ✓ Good — kept v1.1 focused |
| Keep WebSocket token in query param | Header-based auth requires frontend changes | — Pending |
| python-dotenv for .env loading | Lightweight, no magic, crash on missing vars | ✓ Good |
| DRF ScopedRateThrottle (no new deps) | Already in stack, differentiated rates per endpoint | ✓ Good |
| State machine on model (not separate class) | Django convention, ValidationError for DRF integration | ✓ Good |
| assert_in_progress() as blanket guard | Simpler than per-action guards; 4 specific guards left unused | ⚠️ Revisit if actions need distinct status rules |
| Python logging for audit (not DB model) | No new deps, file + console output, meets admin visibility requirement | ✓ Good |
| Profile models as OneToOne on User in main/ | Avoid circular imports, profiles are User extensions | ✓ Good — clean separation |
| scheduling/ app for availability + requests | Separate domain from session lifecycle | ✓ Good — clean boundaries |
| AvailabilitySlot FK to User (not ExaminerProfile) | Simpler FK chain, ExaminerProfile accessed separately | ✓ Good — consistent pattern |
| select_for_update on accept path | Prevent double-booking race conditions | ✓ Good — database-level safety |
| Email sends after transaction exits | Same discipline as _broadcast, prevents stale emails | ✓ Good — consistent pattern |
| django-q2 with ORM broker (no Redis) | Minimal infrastructure, sufficient for v1.3 volume | ✓ Good — no new deps needed |
| ~~faster-whisper CPU~~ → Gemini Pro audio | Direct audio assessment eliminates transcription step; enables pronunciation scoring | ✓ Good — single API call, better PR assessment |
| ~~Claude tool_use~~ → Gemini response_schema + Pydantic | Structured JSON output with schema-level validation; incompatible with function calling for audio | ✓ Good — cleaner validation, works with audio input |
| google-genai (not google-generativeai) | Official SDK, `from google import genai` import pattern | ✓ Good — correct package |
| Tuple return from assess_session | Service returns (scores, transcript); caller stores both | ✓ Good — clean separation of concerns |
| Monthly usage limit via job count query | No separate counter model needed | ✓ Good — simple, accurate |
| AI feedback as single unified endpoint | POST trigger + GET status/scores on same URL | ✓ Good — clean API surface |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition:**
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone:**
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-04-09 after v1.4 milestone shipped*
