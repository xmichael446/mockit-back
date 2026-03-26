# State

## Current Position

Phase: Not started (defining requirements)
Plan: --
Status: Defining requirements
Last activity: 2026-03-27 -- Milestone v1.1 started

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-27)

**Core value:** Examiners can conduct a complete, real-time IELTS Speaking mock exam with a candidate -- from invite through scoring -- with minimal friction.
**Current focus:** v1.1 Clean-up, Security & Edge Cases

## Accumulated Context

- Brownfield project: codebase fully mapped in .planning/codebase/
- Zero test coverage -- all changes require careful manual verification
- session/views.py (1031 lines) is the largest and most fragile file
- Hardcoded secrets in settings.py are the most critical security issue
