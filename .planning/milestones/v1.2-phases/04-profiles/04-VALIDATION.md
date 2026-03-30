---
phase: 4
slug: profiles
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-03-30
---

# Phase 4 — Validation Strategy

> Per-phase validation contract for feedback sampling during execution.

---

## Test Infrastructure

| Property | Value |
|----------|-------|
| **Framework** | Django TestCase (unittest) |
| **Config file** | manage.py (default Django test runner) |
| **Quick run command** | `python manage.py test main.tests --verbosity=1` |
| **Full suite command** | `python manage.py test --verbosity=1` |
| **Estimated runtime** | ~5 seconds |

---

## Sampling Rate

- **After every task commit:** Run `python manage.py test main.tests --verbosity=1`
- **After every plan wave:** Run `python manage.py test --verbosity=1`
- **Before `/gsd:verify-work`:** Full suite must be green
- **Max feedback latency:** 5 seconds

---

## Per-Task Verification Map

| Task ID | Plan | Wave | Requirement | Test Type | Automated Command | File Exists | Status |
|---------|------|------|-------------|-----------|-------------------|-------------|--------|
| 04-01-01 | 01 | 1 | EXAM-01 | unit | `python manage.py test main.tests.TestExaminerProfile` | ❌ W0 | ⬜ pending |
| 04-01-02 | 01 | 1 | EXAM-02 | unit | `python manage.py test main.tests.TestExaminerCredential` | ❌ W0 | ⬜ pending |
| 04-01-03 | 01 | 1 | EXAM-03 | unit | `python manage.py test main.tests.TestExaminerProfile` | ❌ W0 | ⬜ pending |
| 04-01-04 | 01 | 1 | STUD-01 | unit | `python manage.py test main.tests.TestCandidateProfile` | ❌ W0 | ⬜ pending |
| 04-01-05 | 01 | 1 | STUD-02 | unit | `python manage.py test main.tests.TestCandidateProfile` | ❌ W0 | ⬜ pending |
| 04-01-06 | 01 | 1 | STUD-04 | unit | `python manage.py test main.tests.TestScoreHistory` | ❌ W0 | ⬜ pending |
| 04-02-01 | 02 | 2 | EXAM-01 | integration | `python manage.py test main.tests.TestExaminerProfileAPI` | ❌ W0 | ⬜ pending |
| 04-02-02 | 02 | 2 | EXAM-04 | integration | `python manage.py test main.tests.TestExaminerProfileAPI` | ❌ W0 | ⬜ pending |
| 04-02-03 | 02 | 2 | EXAM-05 | integration | `python manage.py test main.tests.TestExaminerProfileAPI` | ❌ W0 | ⬜ pending |
| 04-02-04 | 02 | 2 | EXAM-06 | integration | `python manage.py test main.tests.TestExaminerProfileAPI` | ❌ W0 | ⬜ pending |
| 04-02-05 | 02 | 2 | STUD-01 | integration | `python manage.py test main.tests.TestCandidateProfileAPI` | ❌ W0 | ⬜ pending |
| 04-02-06 | 02 | 2 | STUD-04 | integration | `python manage.py test main.tests.TestCandidateProfileAPI` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] `main/tests.py` — test stubs for ExaminerProfile, CandidateProfile, ExaminerCredential, ScoreHistory models
- [ ] `main/tests.py` — test stubs for profile API endpoints (CRUD + permissions)

*Existing infrastructure: Django test runner already configured, 26 tests from v1.1 in session/tests.py*

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Profile picture upload via ImageField | EXAM-01, STUD-01 | File upload requires multipart form test | POST multipart form data with image file to profile endpoint |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 5s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
