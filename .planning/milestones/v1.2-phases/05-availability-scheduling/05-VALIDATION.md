---
phase: 5
slug: availability-scheduling
status: draft
nyquist_compliant: true
wave_0_complete: true
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
| 05-01-02 | 01 | 1 | AVAIL-03, AVAIL-04 | unit | `python manage.py test scheduling.tests.TestComputeAvailableSlots scheduling.tests.TestIsCurrentlyAvailable --settings=MockIT.settings_test` | Yes (W0) | ⬜ pending |
| 05-02-01 | 02 | 2 | AVAIL-01, AVAIL-02 | integration | `python manage.py test scheduling.tests.TestAvailabilitySlotAPI --settings=MockIT.settings_test` | Yes (W0) | ⬜ pending |
| 05-02-02 | 02 | 2 | AVAIL-05 | integration | `python manage.py test scheduling.tests.TestBlockedDateAPI --settings=MockIT.settings_test` | Yes (W0) | ⬜ pending |
| 05-02-03 | 02 | 2 | AVAIL-03 | integration | `python manage.py test scheduling.tests.TestAvailableSlotsEndpoint --settings=MockIT.settings_test` | Yes (W0) | ⬜ pending |
| 05-02-04 | 02 | 2 | AVAIL-04 | integration | `python manage.py test scheduling.tests.TestIsAvailableEndpoint --settings=MockIT.settings_test` | Yes (W0) | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [x] `scheduling/tests.py` — Plan 01 Task 2 creates `TestComputeAvailableSlots` and `TestIsCurrentlyAvailable` (TDD task, tests written first)
- [x] `scheduling/tests.py` — Plan 02 Task 2 creates `TestAvailabilitySlotAPI`, `TestBlockedDateAPI`, `TestAvailableSlotsEndpoint`, `TestIsAvailableEndpoint` (TDD task, tests written first)

*Existing infrastructure: Django test runner configured, settings_test.py available for SQLite*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Timezone display conversion | AVAIL-03 | Depends on user's local timezone | Pass `?timezone=Asia/Tashkent` and verify times are converted |

---

## Validation Sign-Off

- [x] All tasks have `<automated>` verify or Wave 0 dependencies
- [x] Sampling continuity: no 3 consecutive tasks without automated verify
- [x] Wave 0 covers all MISSING references
- [x] No watch-mode flags
- [x] Feedback latency < 5s
- [x] `nyquist_compliant: true` set in frontmatter

**Approval:** approved
