---
phase: 13-usage-control
plan: "01"
subsystem: session
tags: [usage-control, ai-feedback, rate-limiting, transaction, select-for-update]
dependency_graph:
  requires: [12-02]
  provides: [monthly-ai-feedback-limit-enforcement]
  affects: [session/views.py, MockIT/settings.py]
tech_stack:
  added: []
  patterns: [select_for_update + transaction.atomic for race-condition-safe counting, env-override settings pattern]
key_files:
  created: []
  modified:
    - MockIT/settings.py
    - session/views.py
    - session/tests.py
decisions:
  - "Monthly limit check uses select_for_update on all examiner jobs to prevent concurrent requests bypassing limit"
  - "FAILED jobs excluded from monthly count so retries don't penalize examiner"
  - "async_task called after transaction.atomic exits to follow established broadcast discipline"
  - "Limit configurable via AI_FEEDBACK_MONTHLY_LIMIT env var (default 10)"
metrics:
  duration: "155s"
  completed: "2026-04-08"
  tasks_completed: 2
  files_modified: 3
requirements: [UCTL-01, UCTL-02, UCTL-03]
---

# Phase 13 Plan 01: Monthly AI Feedback Usage Limit Enforcement Summary

**One-liner:** Per-examiner monthly AI feedback cap (default 10) enforced with select_for_update + transaction.atomic, returning 429 when exceeded.

## Tasks Completed

| Task | Name | Commit | Files |
|------|------|--------|-------|
| 1 | Add monthly limit setting and enforce in AIFeedbackTriggerView | 0458168 | MockIT/settings.py, session/views.py |
| 2 | Add usage limit tests to AIFeedbackTriggerTests | f4a795b | session/tests.py |

## What Was Built

**Setting (MockIT/settings.py):**
- `AI_FEEDBACK_MONTHLY_LIMIT = int(os.environ.get("AI_FEEDBACK_MONTHLY_LIMIT", "10"))` added after ANTHROPIC_API_KEY line

**Usage limit enforcement (session/views.py — AIFeedbackTriggerView.post):**
- Wrapped duplicate-check + limit-check + job creation in `transaction.atomic()`
- `select_for_update()` locks all AIFeedbackJob rows for the examiner's sessions, preventing concurrent requests from both passing the limit check
- Monthly count computed from locked queryset: `created_at >= month_start` and `status != FAILED`
- Returns 429 with `"Monthly AI feedback limit reached ({limit}/{limit}). Resets next month."` when count >= limit
- `async_task` called after the `with transaction.atomic()` block exits (established broadcast/email discipline)

**Tests (session/tests.py — AIFeedbackTriggerTests):**
- `test_trigger_returns_429_when_monthly_limit_reached` — 10 DONE jobs -> 429
- `test_trigger_allows_when_under_limit` — 9 DONE jobs -> 202
- `test_trigger_excludes_failed_from_count` — 10 FAILED jobs -> 202
- `test_trigger_resets_count_each_month` — 10 DONE jobs last month -> 202
- `test_trigger_counts_across_sessions` — 5+5 DONE jobs across sessions -> 429

All 12 tests in AIFeedbackTriggerTests pass (7 existing + 5 new).

## Decisions Made

| Decision | Rationale |
|----------|-----------|
| select_for_update on all examiner jobs (not just session) | Prevents race condition where two concurrent requests both read count < limit and both create jobs |
| FAILED jobs excluded from count | Retries should not penalize the examiner for AI service failures |
| async_task after transaction | Follows established project discipline -- task runs on committed data only |
| Count computed in Python from locked queryset | Avoids second DB query; data already fetched for locking |

## Deviations from Plan

**Merge from feature branch:** Worktree was 29 commits behind `gsd/v1.3-ai-feedback-assessment` (phases 10-12 work). Performed fast-forward merge before executing plan tasks. This is a process deviation (worktree initialization), not a code deviation.

No code deviations -- plan executed exactly as written.

## Known Stubs

None.

## Self-Check: PASSED

- [x] `AI_FEEDBACK_MONTHLY_LIMIT` in MockIT/settings.py: FOUND
- [x] `select_for_update` in session/views.py: FOUND
- [x] `status=429` in session/views.py: FOUND
- [x] Commit 0458168 exists: FOUND
- [x] Commit f4a795b exists: FOUND
- [x] All 12 AIFeedbackTriggerTests pass: CONFIRMED
