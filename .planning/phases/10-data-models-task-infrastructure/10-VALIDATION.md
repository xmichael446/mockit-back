---
phase: 10
slug: data-models-task-infrastructure
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-07
---

# Phase 10 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Django TestCase (unittest) |
| **Config file** | MockIT/settings_test.py |
| **Quick run command** | `python manage.py test --settings=MockIT.settings_test` |
| **Full suite command** | `python manage.py test --settings=MockIT.settings_test` |
| **Estimated runtime** | ~10 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python manage.py test --settings=MockIT.settings_test`
- **After every plan wave:** Run `python manage.py test --settings=MockIT.settings_test`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 10 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 10-01-01 | 01 | 1 | AIAS-01 | unit | `python manage.py test session.tests --settings=MockIT.settings_test` | ✅ | ⬜ pending |
| 10-01-02 | 01 | 1 | AIAS-05 | unit | `python manage.py test session.tests --settings=MockIT.settings_test` | ✅ | ⬜ pending |
| 10-02-01 | 02 | 1 | BGPR-02 | unit | `python manage.py test session.tests --settings=MockIT.settings_test` | ❌ W0 | ⬜ pending |
| 10-02-02 | 02 | 1 | BGPR-01 | unit | `python manage.py test session.tests --settings=MockIT.settings_test` | ❌ W0 | ⬜ pending |
| 10-02-03 | 02 | 1 | BGPR-03 | unit | `python manage.py test session.tests --settings=MockIT.settings_test` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `session/tests/test_ai_feedback.py` — stubs for BGPR-01, BGPR-02, BGPR-03
- [ ] `Q_CLUSTER = {'sync': True}` in settings_test.py for synchronous task execution

*Existing test infrastructure (Django TestCase, factories) covers AIAS-01 and AIAS-05.*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| qcluster starts without errors | BGPR-01 | Requires running worker process | Run `python manage.py qcluster` and verify startup output |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 10s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
