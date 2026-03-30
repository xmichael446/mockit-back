---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Profiles & Scheduling
status: defining_requirements
last_updated: "2026-03-30"
progress:
  total_phases: 0
  completed_phases: 0
  total_plans: 0
  completed_plans: 0
---

# State

## Current Position

Phase: Not started (defining requirements)
Plan: —
Status: Defining requirements
Last activity: 2026-03-30 — Milestone v1.2 started

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-30)

**Core value:** Examiners can conduct a complete, real-time IELTS Speaking mock exam with a candidate -- from invite through scoring -- with minimal friction.
**Current focus:** Defining requirements for v1.2
**Current milestone:** v1.2 Profiles & Scheduling

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

- [Phase 01]: Use os.environ[] fail-fast for all secrets (no .get() defaults)
- [Phase 01]: Used ScopedRateThrottle as default class with per-view throttle_scope (views without scope are unaffected)
- [Phase 02]: Used SQLite settings_test.py for test runner (local PG is v13, Django 5.2 needs v14+)
- [Phase 02]: Changed invite_token max_length 9->8 to match new xxx-yyyy format
- [Phase 02]: ValidationError from model methods propagates through DRF -- no try/except needed in views
- [Phase 02]: Broadcast calls placed after transaction.atomic block to prevent stale events on rollback
- [Phase 03-01]: Email send returns bool rather than raising -- callers decide how to surface failure
- [Phase 03]: Used Python logging %s formatting for proper lazy evaluation in audit log calls

### Quick Tasks Completed

| # | Description | Date | Commit | Status | Directory |
|---|-------------|------|--------|--------|-----------|
| 260327-qez | Update API docs with all error messages and scenarios | 2026-03-27 | dae4515 | Verified | [260327-qez-update-the-api-docs-to-include-all-the-p](./quick/260327-qez-update-the-api-docs-to-include-all-the-p/) |
| 260327-qsl | Add error response format documentation to Global Errors section | 2026-03-27 | cb6e9ce | Verified | [260327-qsl-include-error-response-format-as-well-in](./quick/260327-qsl-include-error-response-format-as-well-in/) |
| 260330-dz6 | Rework session scheduling: enforce scheduled_at guard + 30-min invite expiry | 2026-03-30 | 656fa37 | Verified | [260330-dz6-rework-session-scheduling-enforce-schedu](./quick/260330-dz6-rework-session-scheduling-enforce-schedu/) |
| 260330-e53 | Extract API docs into multiple shorter files | 2026-03-30 | c051353 | Completed | [260330-e53-extract-api-docs-into-multiple-shorter-f](./quick/260330-e53-extract-api-docs-into-multiple-shorter-f/) |

Last activity: 2026-03-30 - Completed quick task 260330-e53: Extract API docs into multiple shorter files

## Session Continuity

Next action: Run `/gsd:plan-phase 1` to plan Phase 1: Security Hardening
