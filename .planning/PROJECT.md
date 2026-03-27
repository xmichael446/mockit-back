# MockIT

## What This Is

An IELTS Speaking mock exam platform where examiners conduct live sessions with candidates over video. Examiners ask questions from a curated question bank in real-time, then score candidates across four IELTS criteria (FC, GRA, LR, PR) with results released to candidates after the session.

## Core Value

Examiners can conduct a complete, real-time IELTS Speaking mock exam with a candidate — from invite through scoring — with minimal friction.

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

### Active

<!-- Next milestone scope. -->

_(No active requirements — define with `/gsd:new-milestone`)_

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
- session/views.py refactored — status checks centralized into model state machine
- 26 unit tests added in v1.1 (session state machine, invite token, preset immutability, transaction rollback)
- Audit logging active via `mockit.audit` logger to console + `logs/audit.log`

## Constraints

- **Stack**: Django 5.2 + DRF + Channels 4.x — no framework changes
- **Backward compat**: REST API and WebSocket event contracts must not break
- **Limited tests**: 26 tests from v1.1; no comprehensive regression suite yet
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
*Last updated: 2026-03-27 after v1.1 milestone completion*
