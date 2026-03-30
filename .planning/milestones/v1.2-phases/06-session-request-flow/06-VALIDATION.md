---
phase: 6
slug: session-request-flow
status: draft
nyquist_compliant: true
wave_0_complete: true
created: 2026-03-30
---

# Phase 6 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Django TestCase (unittest) |
| **Config file** | manage.py (default Django test runner) |
| **Quick run command** | `python manage.py test scheduling.tests --settings=MockIT.settings_test --verbosity=1` |
| **Full suite command** | `python manage.py test --settings=MockIT.settings_test --verbosity=1` |
| **Estimated runtime** | ~8 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python manage.py test scheduling.tests --settings=MockIT.settings_test --verbosity=1`
- **After every plan wave:** Run `python manage.py test --settings=MockIT.settings_test --verbosity=1`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 8 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 06-01-01 | 01 | 1 | REQ-05 | unit | `python manage.py test scheduling.tests.TestSessionRequestStateMachine --settings=MockIT.settings_test` | Yes (W0) | ⬜ pending |
| 06-02-01 | 02 | 2 | REQ-01, REQ-02 | integration | `python manage.py test scheduling.tests.TestSessionRequestSubmitAPI --settings=MockIT.settings_test` | Yes (W0) | ⬜ pending |
| 06-02-02 | 02 | 2 | REQ-03, REQ-06 | integration | `python manage.py test scheduling.tests.TestSessionRequestAcceptAPI --settings=MockIT.settings_test` | Yes (W0) | ⬜ pending |
| 06-02-03 | 02 | 2 | REQ-04 | integration | `python manage.py test scheduling.tests.TestSessionRequestRejectAPI --settings=MockIT.settings_test` | Yes (W0) | ⬜ pending |
| 06-02-04 | 02 | 2 | REQ-07 | integration | `python manage.py test scheduling.tests.TestSessionRequestCancelAPI --settings=MockIT.settings_test` | Yes (W0) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `scheduling/tests.py` — Plan 01 Task 2 creates state machine tests (TDD)
- [x] `scheduling/tests.py` — Plan 02 Task 2 creates API integration tests (TDD)

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Concurrent accept race condition | REQ-06 | Requires two simultaneous requests | Send two accept POSTs in rapid succession, verify only one succeeds |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 8s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved
