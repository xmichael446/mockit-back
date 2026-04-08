---
phase: 10-data-models-task-infrastructure
plan: "02"
subsystem: session/tasks
tags: [django-q2, background-tasks, task-infrastructure, testing]
dependency_graph:
  requires:
    - 10-01 (AIFeedbackJob model, session/models.py)
  provides:
    - session/tasks.py run_ai_feedback skeleton
    - django-q2 ORM broker configuration
    - sync-mode test settings for task testing
  affects:
    - session/tests.py (new RunAIFeedbackTaskTests class)
    - MockIT/settings.py (Q_CLUSTER, INSTALLED_APPS)
    - MockIT/settings_test.py (Q_CLUSTER sync override)
    - requirements.txt (django-q2 dependency)
tech_stack:
  added:
    - django-q2==1.9.0 (ORM-backed task queue, no Redis required)
    - django-picklefield==3.4.0 (django-q2 dependency)
  patterns:
    - Deferred import inside task function to avoid circular imports
    - Sync mode Q_CLUSTER in test settings for deterministic task testing
    - PENDING -> PROCESSING -> DONE status transition pattern
    - Graceful error handling with FAILED status and error_message capture
key_files:
  created:
    - session/tasks.py
  modified:
    - requirements.txt
    - MockIT/settings.py
    - MockIT/settings_test.py
    - session/tests.py
decisions:
  - "Deferred import of AIFeedbackJob inside task function prevents circular imports at module load time"
  - "Q_CLUSTER sync=True in test settings enables synchronous task execution in tests without a worker process"
  - "Pre-existing session test failures (5 tests) are out of scope — scheduled_at=None bug predates this plan"
metrics:
  duration: "~15 minutes"
  completed: "2026-04-07T17:37:52Z"
  tasks_completed: 2
  files_changed: 5
  commits: 3
---

# Phase 10 Plan 02: django-q2 Task Infrastructure Summary

**One-liner:** django-q2 installed with ORM broker, run_ai_feedback skeleton transitions PENDING→PROCESSING→DONE, sync mode enables deterministic task testing.

## What Was Built

- **requirements.txt**: Added `django-q2` dependency
- **MockIT/settings.py**: Added `'django_q'` to `INSTALLED_APPS`; added `Q_CLUSTER` config with ORM broker, 2 workers, timeout=300, retry=360, poll=0.5
- **MockIT/settings_test.py**: Added `Q_CLUSTER = {'sync': True, 'orm': 'default'}` override for deterministic test execution
- **session/tasks.py**: Created `run_ai_feedback(job_id: int)` task skeleton that transitions `AIFeedbackJob` status `PENDING → PROCESSING → DONE`, handles `DoesNotExist` gracefully, and captures unexpected exceptions into `FAILED` status + `error_message`
- **session/tests.py**: Added `RunAIFeedbackTaskTests` class with 3 tests covering status transitions, missing job robustness, and async_task enqueue in sync mode

## Commits

| Commit | Type | Description |
|--------|------|-------------|
| `1e01bfa` | chore | Install django-q2, configure ORM broker, add sync test settings |
| `523be8a` | test | Add failing tests for run_ai_feedback task (RED) |
| `a1a09d0` | feat | Implement run_ai_feedback task skeleton (GREEN) |

## Test Results

```
RunAIFeedbackTaskTests:
  test_async_task_enqueue ... ok
  test_task_handles_missing_job ... ok
  test_task_transitions_to_done ... ok

Ran 3 tests in 2.08s - OK
```

## Deviations from Plan

### Deviation: Merged milestone branch before execution

**Found during:** Plan start
**Issue:** Worktree branch `worktree-agent-ab2e22e8` was based on `main` which did not have the 10-01 changes (AIFeedbackJob model). Plan 02 depends on Plan 01.
**Fix:** Merged `gsd/v1.3-ai-feedback-assessment` branch (which contained 10-01 commits) into the worktree branch before executing.
**Files modified:** session/models.py, session/migrations/0010_criterionscore_source_aifeedbackjob.py, and planning files.

### Deferred Items (out of scope)

5 pre-existing test failures in `SessionStateMachineTests` (predated this plan):
- `test_start_valid`, `test_start_invalid_status`, `test_start_no_candidate`, `test_can_start_*` — `can_start()` does not guard against `scheduled_at=None`, causing `TypeError: '>=' not supported between 'datetime.datetime' and 'NoneType'`
- These exist in session/models.py `can_start()` at line 117 and were not introduced by this plan.
- Logged to deferred-items: fix `can_start()` to handle `scheduled_at is None` case.

## Known Stubs

`session/tasks.py` - `run_ai_feedback` function is a skeleton:
- Lines 20-21: Phase 11 transcription placeholder (no actual Whisper call yet)
- Lines 22: Phase 12 AI scoring placeholder (no actual Claude API call yet)

These stubs are **intentional** — the plan objective is to provide the skeleton only. Phase 11 and Phase 12 will wire in the actual implementation.

## Self-Check: PASSED

- `session/tasks.py` exists and contains `def run_ai_feedback`
- `requirements.txt` contains `django-q2`
- `MockIT/settings.py` contains `Q_CLUSTER` with `'orm': 'default'`
- `MockIT/settings_test.py` contains `Q_CLUSTER` with `'sync': True`
- Commits `1e01bfa`, `523be8a`, `a1a09d0` exist in git log
- `RunAIFeedbackTaskTests` (3 tests) all pass
