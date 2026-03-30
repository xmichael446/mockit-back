---
phase: 5
slug: availability-scheduling
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 5 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Django TestCase (unittest) |
| **Config file** | manage.py (default Django test runner) |
| **Quick run command** | `python manage.py test scheduling.tests --settings=MockIT.settings_test --verbosity=1` |
| **Full suite command** | `python manage.py test --settings=MockIT.settings_test --verbosity=1` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python manage.py test scheduling.tests --settings=MockIT.settings_test --verbosity=1`
- **After every plan wave:** Run `python manage.py test --settings=MockIT.settings_test --verbosity=1`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 05-01-01 | 01 | 1 | AVAIL-01 | unit | `python manage.py test scheduling.tests.TestAvailabilitySlot --settings=MockIT.settings_test` | ❌ W0 | ⬜ pending |
| 05-01-02 | 01 | 1 | AVAIL-05 | unit | `python manage.py test scheduling.tests.TestBlockedDate --settings=MockIT.settings_test` | ❌ W0 | ⬜ pending |
| 05-01-03 | 01 | 1 | AVAIL-03 | unit | `python manage.py test scheduling.tests.TestComputeAvailableSlots --settings=MockIT.settings_test` | ❌ W0 | ⬜ pending |
| 05-02-01 | 02 | 2 | AVAIL-01, AVAIL-02 | integration | `python manage.py test scheduling.tests.TestAvailabilityCRUDAPI --settings=MockIT.settings_test` | ❌ W0 | ⬜ pending |
| 05-02-02 | 02 | 2 | AVAIL-03 | integration | `python manage.py test scheduling.tests.TestAvailableSlotsAPI --settings=MockIT.settings_test` | ❌ W0 | ⬜ pending |
| 05-02-03 | 02 | 2 | AVAIL-04 | integration | `python manage.py test scheduling.tests.TestIsAvailableAPI --settings=MockIT.settings_test` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `scheduling/tests.py` — test stubs for models, service, and API endpoints

*Existing infrastructure: Django test runner configured, settings_test.py available for SQLite*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Timezone display conversion | AVAIL-03 | Depends on user's local timezone | Pass `?timezone=Asia/Tashkent` and verify times are converted |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
