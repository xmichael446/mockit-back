---
phase: 11
slug: transcription-service
status: draft
nyquist_compliant: false
wave_0_complete: false
created: 2026-04-07
---

# Phase 11 — Validation Strategy

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
| 11-01-01 | 01 | 1 | TRNS-01 | unit | `python manage.py test session.tests --settings=MockIT.settings_test` | ❌ W0 | ⬜ pending |
| 11-01-02 | 01 | 1 | TRNS-02 | unit | `python manage.py test session.tests --settings=MockIT.settings_test` | ❌ W0 | ⬜ pending |
| 11-01-03 | 01 | 1 | TRNS-03 | unit | `python manage.py test session.tests --settings=MockIT.settings_test` | ❌ W0 | ⬜ pending |
| 11-01-04 | 01 | 1 | TRNS-04 | unit | `python manage.py test session.tests --settings=MockIT.settings_test` | ❌ W0 | ⬜ pending |

*Status: ⬜ pending · ✅ green · ❌ red · ⚠️ flaky*

---

## Wave 0 Requirements

- [ ] Tests for transcription service added to `session/tests.py` with mocked WhisperModel
- [ ] `WHISPER_MODEL_SIZE` setting added to `settings_test.py`

---

## Manual-Only Verifications

| Behavior | Requirement | Why Manual | Test Instructions |
|----------|-------------|------------|-------------------|
| Actual audio transcription quality | TRNS-02 | Requires real audio file and Whisper model weights | Upload test recording, trigger transcription, verify output quality |

---

## Validation Sign-Off

- [ ] All tasks have `<automated>` verify or Wave 0 dependencies
- [ ] Sampling continuity: no 3 consecutive tasks without automated verify
- [ ] Wave 0 covers all MISSING references
- [ ] No watch-mode flags
- [ ] Feedback latency < 15s
- [ ] `nyquist_compliant: true` set in frontmatter

**Approval:** pending
