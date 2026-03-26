# State

## Current Position

Phase: 1 (Security Hardening) — not started
Plan: --
Status: Roadmap defined, awaiting phase planning
Last activity: 2026-03-27 — Roadmap created for v1.1

## Progress Bar

```
[Phase 1: Security Hardening    ] [ ] Not started
[Phase 2: Session Hardening     ] [ ] Not started
[Phase 3: Data Integrity + Obs. ] [ ] Not started
```

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-27)

**Core value:** Examiners can conduct a complete, real-time IELTS Speaking mock exam with a candidate -- from invite through scoring -- with minimal friction.
**Current focus:** v1.1 Clean-up, Security & Edge Cases
**Current milestone:** v1.1

## Accumulated Context

- Brownfield project: codebase fully mapped in .planning/codebase/
- Zero test coverage -- all changes require careful manual verification
- session/views.py (1031 lines) is the largest and most fragile file
- Hardcoded secrets in settings.py are the most critical security issue
- REF-01 (state machine) is the foundational refactor for Phase 2 — other edge case fixes build on it
- Multi-step session start (status update + room creation + token generation) has no transaction wrapping
- Invite token currently uses random.choices() with ~47 bits entropy — needs secrets module

## Decisions

| Decision | Rationale |
|----------|-----------|
| Phase 1 ships SEC-01 and SEC-02 together | Both are independent security fixes with no coupling to session logic; secrets must ship first |
| Phase 2 bundles REF-01, REF-03, EDGE-01, EDGE-04 | REF-01 (state machine) is foundational; EDGE-01 (transactions) and EDGE-04 (preset immutability) touch the same session lifecycle code |
| Phase 3 handles REF-02, EDGE-02, EDGE-03 | Audit logging, scoring validation, and email error handling are data-layer concerns that don't depend on the state machine |
| Tests deferred to separate milestone | Zero coverage currently; test milestone is explicit out-of-scope for v1.1 |

## Session Continuity

Next action: Run `/gsd:plan-phase 1` to plan Phase 1: Security Hardening
