---
phase: quick
plan: 01
subsystem: docs
tags: [documentation, api, error-handling]
dependency_graph:
  requires: []
  provides: [complete-api-error-reference]
  affects: [frontend-error-handling]
tech_stack:
  added: []
  patterns: [error-block-per-endpoint, global-errors-section]
key_files:
  created: []
  modified:
    - docs/api.md
decisions:
  - "Global errors (401, 429) documented once at the top and referenced throughout to avoid repetition"
  - "Guest join endpoint documented as fully public (no auth) with its own rate limit note"
  - "Error messages taken verbatim from views.py and serializers.py to ensure accuracy"
metrics:
  duration: 8m
  completed: "2026-03-27"
  tasks_completed: 1
  files_modified: 1
---

# Phase quick Plan 01: Update API Docs with Error Responses Summary

Added comprehensive error response documentation to every endpoint in docs/api.md so frontend developers can handle all error states without reading backend code.

## What Was Done

**Global Errors section** added at the top of the file documenting 401 Unauthorized and 429 Too Many Requests with the specific rate limits for register (10/hr), guest_join (20/hr), and accept_invite (20/hr).

**POST /api/auth/guest-join/** fully documented as a new section in the Authentication block. Was previously completely absent from the API reference despite being a live endpoint. Documents: no auth required, request body (invite_token + optional first_name), success 201 response shape, rate limit, and all 4 error cases.

**Errors: block added to every REST endpoint** — 27 total — listing all possible status codes and their exact error message strings as they appear in the codebase (views.py and serializers.py).

**Guest flow added to Typical Flows** showing how a guest joins without registration.

## Commits

- `1d5eeff` — docs(quick-01): add comprehensive error responses to all API endpoints

## Deviations from Plan

None — plan executed exactly as written.

## Self-Check: PASSED

- `docs/api.md` exists and was modified
- `1d5eeff` commit exists in git log
- `grep -c "Errors:" docs/api.md` returns 27 (meets >= 27 requirement)
- POST /api/auth/guest-join/ section exists with auth, request body, success response, and errors
- Existing success response documentation preserved unchanged
