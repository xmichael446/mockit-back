---
phase: quick
plan: 260327-qsl
subsystem: docs
tags: [documentation, error-handling, api, drf]
dependency_graph:
  requires: []
  provides: [error-response-format-docs]
  affects: [docs/api.md]
tech_stack:
  added: []
  patterns: []
key_files:
  created: []
  modified:
    - docs/api.md
decisions:
  - Documented Shape 3 (list errors) as triggered by model-level ValidationError, not view-level, to match actual DRF propagation behavior
metrics:
  duration: "3 minutes"
  completed: "2026-03-27"
  tasks_completed: 1
  files_modified: 1
---

# Quick Task 260327-qsl Summary

**One-liner:** Added DRF error response shape documentation (detail object, field validation, list) with client-side detection snippet to Global Errors section.

## What Was Done

Added a new `### Error Response Formats` subsection to the Global Errors section of `docs/api.md`, positioned between the rate-limit bullet list and the Authentication section.

The subsection documents all three JSON shapes DRF can return:

- **Shape 1** — `{"detail": "..."}` — from views returning `Response({"detail": "..."})` directly
- **Shape 2** — `{"field": ["error"], "non_field_errors": ["..."]}` — from serializer validation failures
- **Shape 3** — `["error string"]` — from model-level `ValidationError` propagated through DRF

Each shape includes: a JSON example, which endpoints/conditions trigger it, and a note on what to look for. A client-side detection snippet using `typeof` and `Array.isArray` is included at the end.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add error response format documentation | cb6e9ce | docs/api.md |

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- docs/api.md contains "Error Response Formats" section (1 match confirmed)
- Commit cb6e9ce exists in git history
