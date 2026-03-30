---
gsd_state_version: 1.0
milestone: v1.2
milestone_name: Profiles & Scheduling
status: unknown
stopped_at: Completed 08-01-PLAN.md
last_updated: "2026-03-30T09:23:17.168Z"
progress:
  total_phases: 6
  completed_phases: 5
  total_plans: 8
  completed_plans: 8
---

# State

## Current Position

Phase: 08 (email-notifications) — EXECUTING
Plan: 1 of 1

## Project Reference

See: .planning/PROJECT.md (updated 2026-03-30)

**Core value:** Examiners can conduct a complete, real-time IELTS Speaking mock exam with a candidate -- from invite through scoring -- with minimal friction.
**Current focus:** Phase 08 — email-notifications
**Current milestone:** v1.2 Profiles & Scheduling

## Accumulated Context

### Decisions

From v1.1 (carry-forward constraints):

- [Phase 02]: ValidationError from model methods propagates through DRF -- no try/except needed in views
- [Phase 02]: Broadcast calls placed after transaction.atomic block to prevent stale events on rollback
- [Phase 03-01]: Email send returns bool rather than raising -- callers decide how to surface failure

For v1.2 (pre-implementation):

- Profile models (ExaminerProfile, CandidateProfile) go in main/models.py as OneToOne on User (avoid circular imports)
- scheduling/ app owns AvailabilitySlot, SessionRequest, views, permissions, email service stubs
- Email sends must be called after transaction exits (same discipline as _broadcast)
- select_for_update() + transaction.atomic() required on SessionRequest accept path (double-booking prevention)
- Phone field: ExaminerProfilePublicSerializer hides phone; ExaminerProfileDetailSerializer shows it to owner
- [Phase 04-01]: Tests run via DJANGO_SETTINGS_MODULE=MockIT.settings_test (SQLite in-memory) because PG 13 installed but Django 5.2 requires PG 14
- [Phase 04-01]: Updated .env DB_PORT to 5433 to match actual PostgreSQL cluster port
- [Phase 04-02]: Role mismatch on /me/ endpoints returns 404 (not 403) to avoid disclosing role information
- [Phase 04-02]: ScoreHistory uses get_or_create() to be idempotent — double-release safe
- [Phase 04-02]: CandidateProfile.DoesNotExist silently skipped for guest candidates without profiles
- [Phase 05-availability-scheduling]: DayOfWeek IntegerChoices uses MON=0..SUN=6 matching Python date.weekday() — no end_time stored (always start+1h)
- [Phase 05-availability-scheduling]: compute_available_slots filters scheduled_at__isnull=False to safely handle nullable IELTSMockSession.scheduled_at
- [Phase 05-02]: IntegrityError on unique_together caught in view POST and returned as 400 (DRF serializer cannot validate without examiner FK at validation time)
- [Phase 05-02]: Examiner test users need is_verified=True due to global IsEmailVerified permission class
- [Phase 06-01]: SessionRequest.Status uses IntegerChoices matching SessionStatus pattern; DRF ValidationError raised from model methods; accepted_booked keyed by (slot_id, date) not datetime
- [Phase 06]: select_for_update + transaction.atomic on accept path prevents double-booking under concurrency
- [Phase 06]: _broadcast called after transaction.atomic block to prevent stale WebSocket events on rollback
- [Phase 07-candidate-score-auto-update]: current_speaking_score update placed inside existing try/except CandidateProfile.DoesNotExist block — re-uses candidate_profile variable, guest candidates silently skipped
- [Phase 08-email-notifications]: Email sends are fire-and-forget (bool return, log on failure) consistent with v1.1 decision — callers ignore return value
- [Phase 08-email-notifications]: notify_request_accepted placed after transaction.atomic block, mirroring _broadcast() discipline

### Research Flags (needs codebase check during planning)

- Phase 6: Confirm _broadcast() discipline holds for accept flow before writing view
- Phase 7: Identify exact line in session/views.py:release_result where update_speaking_score() should be called
- Phase 4: Confirm MEDIA_ROOT/MEDIA_URL not duplicated (media/ directory may already exist for SessionRecording)

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-03-30T09:23:17.163Z
Stopped at: Completed 08-01-PLAN.md
Resume file: None
Next action: Run `/gsd:plan-phase 4` to plan Phase 4: Profiles
