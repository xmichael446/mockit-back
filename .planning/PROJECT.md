# MockIT

## What This Is

An IELTS Speaking mock exam platform where examiners conduct live sessions with candidates over video. Examiners ask questions from a curated question bank in real-time, then score candidates across four IELTS criteria (FC, GRA, LR, PR) with results released to candidates after the session.

## Core Value

Examiners can conduct a complete, real-time IELTS Speaking mock exam with a candidate — from invite through scoring — with minimal friction.

## Current Milestone: v1.1 Clean-up, Security & Edge Cases

**Goal:** Harden the codebase for production readiness — fix security vulnerabilities, handle edge cases, and refactor fragile patterns.

**Target features:**
- Move all secrets to environment variables
- Fix CORS, DEBUG, and auth security gaps
- Add rate limiting to critical endpoints
- Refactor repeated status checks into a state machine
- Handle edge cases in scoring, transactions, and email delivery
- Strengthen invite token generation
- Add audit logging for critical operations

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

### Active

<!-- Current scope. Building toward these. -->

- [ ] Secrets moved to environment variables (.env)
- [ ] DEBUG controlled by environment variable
- [ ] CORS restricted to allowed origins
- [ ] Stronger invite token generation (secrets module)
- [ ] Rate limiting on auth and invite endpoints
- [ ] Session status state machine (centralized validation)
- [ ] Transaction management for multi-step operations
- [ ] Scoring validation (require all 4 criteria before release)
- [ ] Email delivery error handling
- [ ] Audit logging for critical actions
- [ ] Preset immutability after session creation

### Out of Scope

<!-- Explicit boundaries. Includes reasoning to prevent re-adding. -->

- Integration/unit test suite — deferred to dedicated testing milestone
- Redis channel layer migration — infrastructure change, separate milestone
- OAuth/social login — email/password sufficient for now
- Mobile app — web-first platform
- WebSocket header-based auth migration — breaking change, requires frontend coordination

## Context

- Backend only (Django/DRF). Frontend is a separate React/TypeScript app.
- Deployed at mockit.live, backend at mi-back.xmichael446.com
- 100ms for video rooms, Resend for transactional email
- InMemoryChannelLayer in dev, Redis planned for production
- Zero test coverage currently — all changes must be careful and manually verified
- session/views.py is 1031 lines with scattered status checks

## Constraints

- **Stack**: Django 5.2 + DRF + Channels 4.x — no framework changes
- **Backward compat**: REST API and WebSocket event contracts must not break
- **No tests yet**: Changes must be self-evidently correct; no regression suite to catch issues
- **Frontend dependency**: Any API contract changes need frontend coordination

## Key Decisions

<!-- Decisions that constrain future work. Add throughout project lifecycle. -->

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Defer test suite to separate milestone | Focus this milestone purely on hardening; tests are a large effort | -- Pending |
| Keep WebSocket token in query param | Header-based auth requires frontend changes; document as future work | -- Pending |

## Evolution

This document evolves at phase transitions and milestone boundaries.

**After each phase transition** (via `/gsd:transition`):
1. Requirements invalidated? -> Move to Out of Scope with reason
2. Requirements validated? -> Move to Validated with phase reference
3. New requirements emerged? -> Add to Active
4. Decisions to log? -> Add to Key Decisions
5. "What This Is" still accurate? -> Update if drifted

**After each milestone** (via `/gsd:complete-milestone`):
1. Full review of all sections
2. Core Value check — still the right priority?
3. Audit Out of Scope — reasons still valid?
4. Update Context with current state

---
*Last updated: 2026-03-27 after milestone v1.1 initialization*
