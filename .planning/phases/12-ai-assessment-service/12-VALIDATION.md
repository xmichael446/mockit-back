---
phase: 12
slug: ai-assessment-service
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-08
---

# Phase 12 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Django TestCase (unittest) |
| **Config file** | MockIT/settings_test.py |
| **Quick run command** | `python manage.py test session.tests --settings=MockIT.settings_test` |
| **Full suite command** | `python manage.py test --settings=MockIT.settings_test` |
| **Estimated runtime** | ~15 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python manage.py test session.tests --settings=MockIT.settings_test`
- **After every plan wave:** Run `python manage.py test --settings=MockIT.settings_test`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 15 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 12-01-01 | 01 | 1 | AIAS-02, AIAS-03, AIAS-04 | unit | `python manage.py test session.tests --settings=MockIT.settings_test` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Tests for assessment service added to `session/tests.py` with mocked Claude API
- [ ] ANTHROPIC_API_KEY setting placeholder in settings_test.py

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| AI feedback quality and accuracy | AIAS-02 | Requires real Claude API call with real transcript | Trigger AI feedback on a completed session, review scores and feedback |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
