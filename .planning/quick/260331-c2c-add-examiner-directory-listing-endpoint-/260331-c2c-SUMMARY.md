---
phase: quick
plan: 260331-c2c
subsystem: main/profiles
tags: [api, profiles, pagination, filtering, listing]
dependency_graph:
  requires: []
  provides: [GET /api/profiles/examiners/]
  affects: [main/views.py, main/urls.py, MockIT/settings.py, docs/api/profiles.md]
tech_stack:
  added: []
  patterns: [ListAPIView for paginated list, manual query param filtering in get_queryset]
key_files:
  created: []
  modified:
    - MockIT/settings.py
    - main/views.py
    - main/urls.py
    - main/tests.py
    - docs/api/profiles.md
decisions:
  - Used ListAPIView (not APIView) for native DRF pagination support — only place in codebase where generics is appropriate
  - Manual query param parsing in get_queryset() (no django-filter dependency)
  - Default ordering by pk for stable/predictable results when no ordering param given
metrics:
  duration: ~10 minutes
  completed_at: "2026-03-31T03:47:36Z"
  tasks_completed: 2
  files_modified: 5
---

# Quick Task 260331-c2c: Add Examiner Directory Listing Endpoint Summary

**One-liner:** Paginated GET /api/profiles/examiners/ with is_verified filter and completed_session_count ordering using ExaminerProfilePublicSerializer (phone hidden).

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add pagination config, ExaminerDirectoryView, and URL route | 009f8d0 | MockIT/settings.py, main/views.py, main/urls.py, main/tests.py |
| 2 | Document the endpoint in docs/api/profiles.md | b803f04 | docs/api/profiles.md |

## What Was Built

- `ExaminerDirectoryView` (ListAPIView) registered at `GET /api/profiles/examiners/`
- Pagination: DRF `PageNumberPagination`, page size 20, returns `count/next/previous/results`
- Filtering: `?is_verified=true` or `?is_verified=false` via manual query param parsing
- Ordering: `?ordering=completed_session_count` (asc) or `?ordering=-completed_session_count` (desc)
- Uses `ExaminerProfilePublicSerializer` — phone field is never exposed
- 7 tests added covering all behaviors including auth, filtering, ordering, and phone hiding
- Full documentation added to `docs/api/profiles.md`

## Decisions Made

- **ListAPIView instead of APIView:** The only view in main/ using DRF generics — necessary because APIView has no pagination support built-in. All other views remain APIView.
- **No django-filter:** Manual `get_queryset()` override keeps dependencies lean.
- **Default ordering by pk:** Ensures stable, consistent pagination when no ordering param is provided.

## Deviations from Plan

None — plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

Files exist:
- main/views.py contains ExaminerDirectoryView: FOUND
- main/urls.py contains profiles/examiners/: FOUND
- docs/api/profiles.md contains GET /api/profiles/examiners/: FOUND

Commits exist:
- 009f8d0: FOUND
- b803f04: FOUND

Tests: 7/7 pass, 30/30 total main tests pass.
