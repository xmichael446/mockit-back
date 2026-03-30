# Deferred Items — Phase 06

## Pre-existing Test Failures (out of scope)

**5 failing tests in session.tests** — discovered during full test suite run after plan 06-02.

- `SessionStateMachineTests.test_can_start_scheduled_with_candidate`
- `SessionStateMachineTests.test_start_valid`
- `SessionStartTransactionTests.test_no_broadcast_on_failure`
- `SessionStartTransactionTests.test_rollback_on_room_failure`
- 1 additional related test

**Root cause:** `can_start()` in `session/models.py` (line 112) checks `timezone.now() >= self.scheduled_at` but `self.scheduled_at` can be `None`. The guard was added in v1.2 but existing tests create sessions without `scheduled_at`.

**Fix needed:** Guard `can_start()` against `None` scheduled_at: `and self.scheduled_at is not None and timezone.now() >= self.scheduled_at`

**Verified pre-existing:** Confirmed failures occur on git stash (before plan 06-02 changes).
