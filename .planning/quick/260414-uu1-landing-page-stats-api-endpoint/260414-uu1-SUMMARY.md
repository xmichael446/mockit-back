---
phase: quick-260414-uu1
plan: 01
subsystem: session
tags: [api, public-endpoint, landing-page, stats]
requires: []
provides:
  - "GET /api/landing/ public aggregate stats endpoint"
affects:
  - "session/views.py (+ LandingStatsView)"
  - "session/urls.py (+ /api/landing/ route)"
tech-stack:
  added: []
  patterns:
    - "APIView with authentication_classes=[] + AllowAny (mirrors SharedSessionDetailView)"
key-files:
  created:
    - docs/api/landing.md
  modified:
    - session/views.py
    - session/urls.py
    - session/tests.py
    - docs/api/index.md
decisions:
  - "Used hand-built dict (no DRF serializer) — 3 ints, serializer adds noise without value"
  - "No caching, no ViewSet, no pagination — per plan's explicit locked constraints"
  - "Route placed at top of urlpatterns (above `sessions/...`) so it isn't buried"
metrics:
  duration: "~5m 40s"
  completed: "2026-04-14T17:21:05Z"
  tasks: 2
  tests_added: 3
  tests_passing: "3/3 LandingStatsViewTests + 104/104 session suite"
---

# Quick Task 260414-uu1: Landing Page Stats API Endpoint Summary

**One-liner:** Public `GET /api/landing/` endpoint returning `sessions_completed` / `questions_in_bank` / `topics_covered` as three live integer counts, with no auth, no serializer, no caching.

## What was built

A single `APIView` subclass (`LandingStatsView`) registered at `/api/landing/` that runs three `.count()` queries and returns them as a flat JSON object. Mirrors the pre-existing `SharedSessionDetailView` public-endpoint pattern (`authentication_classes = []`, `permission_classes = [AllowAny]`).

## Files Changed

| File | Change | Lines |
|------|--------|-------|
| `session/tests.py` | Added `LandingStatsViewTests` class (3 tests) | +79 |
| `session/views.py` | Added `LandingStatsView` + imported `Topic` | +21 / ~1 |
| `session/urls.py` | Imported `LandingStatsView`, added route at top | +4 |
| `docs/api/landing.md` | **New** endpoint doc | +25 |
| `docs/api/index.md` | Added landing.md row to Sections table | +1 |

## Commits (task-atomic, TDD cycle)

| # | Hash | Type | Message |
|---|------|------|---------|
| 1 | `bbd1bdd` | test | add failing tests for LandingStatsView (RED) |
| 2 | `de72114` | feat | add LandingStatsView public endpoint (GREEN) |
| 3 | `310caa8` | docs | document GET /api/landing/ endpoint |

## Test Results

```
DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test session.tests.LandingStatsViewTests -v 2
...
test_counts_are_correct ... ok
test_is_publicly_accessible_without_auth ... ok
test_returns_200_and_exact_shape ... ok
----------------------------------------------------------------------
Ran 3 tests in 5.271s
OK
```

Full regression check:

```
DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test session
Ran 104 tests in 157.781s
OK
```

No regressions.

## Live endpoint example

With a dev server running (`python manage.py runserver`) the endpoint behaves as documented:

```bash
$ curl -i http://localhost:8000/api/landing/
HTTP/1.1 200 OK
Content-Type: application/json

{"sessions_completed": 142, "questions_in_bank": 317, "topics_covered": 48}
```

No `Authorization` header sent; response is the exact three-field shape with no extras. (Live cURL not run in this environment — shape verified via the `test_counts_are_correct` assertion on `resp.json()`.)

## Deviations from Plan

None. The plan executed exactly as written. The fallback branches noted in the plan (extra model fields for `IELTSMockSession` / `Topic` / `Question`) were not needed — `invite_expires_at` and `scheduled_at` are both nullable on `IELTSMockSession`, and `Topic`/`Question` constructors accepted the exact kwargs the plan suggested.

One cosmetic addition: test-only topic slugs/names were prefixed with `landing_` / `landing-` (e.g. `landing-family`) to avoid any chance of clashing with future fixtures that might seed similarly-named topics; this does not change any assertion or behavior.

## Authentication gates

None. Endpoint is intentionally unauthenticated — that's the whole point.

## Known Stubs

None. Every field the endpoint returns is wired to a real `QuerySet.count()` call.

## Verification against success criteria

- [x] Unauthenticated `GET /api/landing/` returns 200 with flat JSON, exact keys `sessions_completed` / `questions_in_bank` / `topics_covered`, integer values.
- [x] `sessions_completed` filters on `SessionStatus.COMPLETED` only (IN_PROGRESS / SCHEDULED excluded — proven by `test_counts_are_correct`).
- [x] View explicitly sets `authentication_classes = []` and `permission_classes = [AllowAny]`.
- [x] Lives in `session/views.py` + `session/urls.py`; root `MockIT/urls.py` required no changes (already includes `session.urls` under `/api/`).
- [x] Django tests cover shape, counts, public access.
- [x] Docs updated: `docs/api/landing.md` created and linked from `docs/api/index.md`.
- [x] No serializer, no ViewSet, no caching, no pagination introduced.

## Self-Check: PASSED

- FOUND: session/views.py (LandingStatsView class present at module scope)
- FOUND: session/urls.py (path `landing/` registered)
- FOUND: session/tests.py (LandingStatsViewTests class, 3 tests, all pass)
- FOUND: docs/api/landing.md
- FOUND: docs/api/index.md (contains link to landing.md)
- FOUND commit bbd1bdd (test RED)
- FOUND commit de72114 (feat GREEN)
- FOUND commit 310caa8 (docs)
