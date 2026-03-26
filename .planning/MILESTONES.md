# Milestones

## v1.0 — Initial Platform (Pre-GSD)

**Shipped:** Before 2026-03-27 (brownfield)
**Summary:** Full IELTS Speaking mock exam platform with session lifecycle, real-time WebSocket events, 100ms video integration, and IELTS band scoring.

**Validated capabilities:**
- Custom User model (EXAMINER/CANDIDATE/GUEST roles)
- Token authentication (HTTP + WebSocket)
- Question bank hierarchy (Topic -> Question -> FollowUp)
- MockPreset templates
- Full session lifecycle (create -> invite -> start -> conduct -> score -> release)
- Real-time WebSocket broadcast events
- 100ms video room integration
- Email verification via Resend
- Guest join flow
- IELTS band scoring (4 criteria, 0.5 rounding)

**Phases:** Pre-GSD (no phase tracking)

---

## v1.1 — Clean-up, Security & Edge Cases (Current)

**Started:** 2026-03-27
**Goal:** Harden the codebase for production readiness.
**Status:** Defining requirements
