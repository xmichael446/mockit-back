# Project Research Summary

**Project:** MockIT v1.2 — Profiles, Availability Scheduling, Session Booking, Email Notifications
**Domain:** IELTS mock exam platform — tutor/examiner marketplace layer on top of existing session platform
**Researched:** 2026-03-30
**Confidence:** HIGH

## Executive Summary

MockIT v1.2 adds a booking layer — examiner profiles, candidate profiles, weekly availability scheduling, and session request flow — on top of an already-functional IELTS session platform. The established pattern for this class of feature (tutor/examiner marketplace) is well-documented: recurring weekly availability stored as simple weekday+hour pairs (not a full calendaring library), a state-machine booking request model (PENDING → ACCEPTED/REJECTED), and profile data in dedicated OneToOne extension models rather than on the base User model. The entire feature set is buildable with a single new pip dependency (Pillow for ImageField, though profile photo upload is deferred), a new `scheduling/` Django app, and two new models in `main/`.

The recommended approach is to build in strict dependency order: data models first, then profile read/write endpoints, then availability CRUD and the slot-calculation service, then the session request state machine, and finally the score auto-update hook into the existing release flow. Email notifications should be stubbed as synchronous service functions throughout, wired at trigger points but not blocking the request cycle — the async queue (Celery/Redis) is out of scope for v1.2. This order ensures each phase is testable independently and that the booking flow has a valid slot model to validate against before any request is created.

The top risks are: (1) double-booking under concurrent load if `select_for_update()` is omitted from the booking accept transaction; (2) timezone naive datetime storage breaking the slot-to-session handoff with the existing `scheduled_at` guard; and (3) gradual erosion of the existing REST API contract if new profile data is embedded in existing serializers rather than returned from new endpoints. All three are preventable at design time and expensive to retrofit after data exists in production.

## Key Findings

### Recommended Stack

The existing stack (Django 5.2, DRF, PostgreSQL, Channels/Daphne, Resend SDK) covers all v1.2 requirements without additional libraries. The only new pip dependency is `Pillow==12.1.1`, required the moment any model uses `ImageField` — but since profile photo upload is deferred to v2, Pillow can be added at that point. The Resend SDK already installed handles the three new email triggers (request received, accepted, rejected). No scheduling library, no calendar library, no async queue — all would add complexity without proportional value at this scope.

**Core technologies:**
- Django 5.2 + DRF 3.16.1: framework and REST API — already installed, no change
- PostgreSQL + psycopg2-binary 2.9.11: availability slot rows, session request state — queryable, indexable, uniqueness-enforceable
- Resend SDK 2.10.0: transactional email for booking notifications — already wired in `main/services/email.py`, extend with new functions
- Pillow 12.1.1: required only when `ImageField` is added to a model — defer until profile photo upload milestone
- Django Channels 4.3.2 / Daphne 4.2.1: no changes needed — WebSocket layer is for in-session events, not booking flow

### Expected Features

**Must have (table stakes for v1.2):**
- Examiner profile (bio, credentials, phone, is_verified) — candidates evaluate before booking
- Candidate profile (best band, score history) — computed from existing `SessionResult` records
- Weekly availability schedule (recurring weekday+hour slots) — examiners set once, recurs
- Available slots endpoint (schedule minus accepted bookings) — computed on-the-fly, not stored
- Session request model (PENDING / ACCEPTED / REJECTED state machine) — candidate initiates
- Accept/reject endpoints — ACCEPTED atomically creates `IELTSMockSession`
- Email: request received (examiner), request accepted/rejected (candidate) — via Resend SDK
- Session reminder email — stubbed only; logs intent; async delivery deferred

**Should have (competitive, v1.x):**
- Session reminder wired to task runner — add when Celery/Redis infra milestone ships
- Examiner session count / experience indicator — add when examiner listing surfaces demand
- Specialization tags with filtering — add when candidate search behavior is observed

**Defer (v2+):**
- Profile photo upload — requires S3/media storage provision
- Rating/review system — premature without user base
- Calendar sync (Google/Outlook) — OAuth complexity, marginal gain at this stage
- Payment integration — separate PCI-scoped milestone

### Architecture Approach

A new `scheduling/` Django app owns all booking logic: `AvailabilitySlot` and `SessionRequest` models, profile/availability/request views, permissions, and email service stubs. Profile models (`ExaminerProfile`, `CandidateProfile`) live in `main/models.py` as OneToOne extensions of `User` — colocated with `User` per Django convention and to avoid circular imports. `session/views.py` is modified in exactly one place: the `release_result` view gets an explicit call to `CandidateProfile.update_best_scores()`. No other existing files expand.

**Major components:**
1. `ExaminerProfile` / `CandidateProfile` in `main/models.py` — role-specific profile data as OneToOne extensions; profiles created lazily
2. `scheduling/models.py` — `AvailabilitySlot` (weekday+hour recurring pattern) and `SessionRequest` (state machine with guard methods mirroring `IELTSMockSession`)
3. `scheduling/services/availability.py` — `compute_available_slots(examiner, week_start)` pure function: fetch slot rows, subtract accepted bookings, return sorted UTC datetimes
4. `scheduling/services/email.py` — notification stubs (log + Resend call) for request received, accepted, rejected
5. `scheduling/views.py` + `scheduling/permissions.py` — profile CRUD, availability CRUD, request accept/reject, with `IsExaminer` / `IsCandidate` role guards

### Critical Pitfalls

1. **Double-booking race condition** — use `select_for_update()` inside `transaction.atomic()` on the acceptance path; enforce a DB-level uniqueness constraint so two concurrent accepts on the same slot are structurally impossible, not just logically guarded.

2. **Naive datetime storage for availability** — store all slot datetimes UTC-aware (`DateTimeField` not `TimeField`); require examiner timezone in slot creation requests; use `django.utils.timezone.make_aware()` everywhere; never `datetime.now()`.

3. **Missing state machine on `SessionRequest`** — apply the same `IntegerChoices` + guard method pattern from `IELTSMockSession`; `accept()` and `reject()` raise `ValidationError` on invalid transitions; DRF surfaces these as 400 automatically.

4. **Email calls inside `transaction.atomic()`** — a Resend timeout would roll back the booking itself; email service functions must be called after the transaction exits, matching the existing `_broadcast()` discipline already established in `session/views.py`.

5. **Existing API contract breakage** — new profile data must live at new endpoints, never embedded into existing session serializers; no existing field may be renamed, removed, or type-changed; audit `docs/api/` diff before every merge.

## Implications for Roadmap

Based on research, all four research files converge on the same build order. The dependency chain is unambiguous: data layer → profiles → availability → booking → notifications. No phase can be safely reordered.

### Phase 1: Data Models and Profiles

**Rationale:** Nothing else compiles without the models. Profile endpoints validate model shape early and have zero inter-model dependencies — fast feedback loop. `ExaminerProfile` and `CandidateProfile` must exist before availability or booking can reference them.
**Delivers:** `ExaminerProfile`, `CandidateProfile` models + migrations; `GET/PATCH /api/examiners/` and `/api/profiles/` endpoints; `scheduling/` app scaffolded with correct module structure.
**Addresses:** Examiner profile (P1), Candidate profile (P1) from FEATURES.md.
**Avoids:** Profile model bloat on User (Pitfall 5); views.py growth (Pitfall 4) — new modules established here become the template for all subsequent phases.

### Phase 2: Availability Scheduling

**Rationale:** The session request flow must validate that a requested slot is within the examiner's available windows. The `AvailabilitySlot` model and `compute_available_slots()` service must exist and be correct before any booking endpoint is built. Timezone handling must be designed here — not retrofittable after data exists.
**Delivers:** `AvailabilitySlot` model + migration; `PATCH/GET /api/availability/` for examiners; `GET /api/examiners/<id>/availability/?week=` for candidates; `compute_available_slots()` service function.
**Implements:** Availability as recurring weekday+hour rows (Architecture Pattern 2); on-the-fly slot calculation (avoids pre-generation anti-pattern).
**Avoids:** Timezone naive datetime (Pitfall 2 — must be addressed at model design time, not after); availability N+1 query (Pitfall 8 — `Exists` annotation or `prefetch_related` built into initial queryset design).

### Phase 3: Session Request Flow

**Rationale:** The highest-value deliverable for v1.2 — enables candidates to book sessions. Depends on Phase 1 (profiles for participant FKs) and Phase 2 (availability service for slot validation). The accept path creates `IELTSMockSession` atomically, which is the bridge to the existing session lifecycle.
**Delivers:** `SessionRequest` model + migration; `POST /api/requests/`; `POST /api/requests/<id>/accept/` (creates `IELTSMockSession`); `POST /api/requests/<id>/reject/`; `GET /api/requests/` (role-filtered list).
**Implements:** State machine pattern (Architecture Pattern 3); `transaction.atomic()` + `select_for_update()` on accept path.
**Avoids:** Double-booking race condition (Pitfall 1 — `select_for_update()` must be in the initial implementation); missing state machine (Pitfall 3); orphaned session creation (Pitfall 9 — session only created inside `BookingRequest.accept()`).

### Phase 4: Candidate Score Auto-Update

**Rationale:** Relatively contained change to the existing release flow. Depends on `CandidateProfile` existing (Phase 1) and the session scoring flow being stable (existing). Isolated to a single explicit call in `session/views.py:release_result` — safer than a `post_save` signal.
**Delivers:** `CandidateProfile.update_best_scores()` method; explicit call in `release_result`; candidate profile shows current best bands after session completion.
**Avoids:** Score auto-update on wrong trigger (Pitfall 6 — explicit call at release, not `post_save` signal that fires on every save).

### Phase 5: Email Notifications

**Rationale:** Stubs should be wired at each trigger point during Phases 1-4 (the functions already exist, just log). This phase fills in the Resend calls and validates email delivery end-to-end. Keeping it as a final phase means blocking email issues cannot prevent booking flow from shipping.
**Delivers:** Filled `notify_examiner_new_request()`, `notify_candidate_accepted()`, `notify_candidate_rejected()` functions in `scheduling/services/email.py`; session reminder stub documented with async gap noted.
**Avoids:** Email blocking request cycle (Pitfall 7 — all sends called after transaction exits); Resend timeout rolling back bookings.

### Phase 6: API Documentation Update

**Rationale:** All endpoints must be stable before documentation is written. Documenting during development leads to drift. Final phase ensures `docs/api/` reflects actual API surface.
**Delivers:** New domain files under `docs/api/` covering profiles, availability, and requests; updated `docs/api/index.md`.
**Avoids:** API contract breakage (Pitfall 10 — documentation audit confirms no existing field has changed shape).

### Phase Ordering Rationale

- Phases 1-3 follow a hard dependency chain: models before services, services before views that depend on them.
- Phase 4 (score auto-update) is decoupled from the booking flow and can be pulled into Phase 1 if the team wants to ship it early — the only constraint is that `CandidateProfile` exists.
- Phase 5 (email) stubs are wired in Phases 3-4 and filled here; this avoids the email implementation blocking the booking feature from being testable end-to-end.
- Phase 6 (docs) is always last because it depends on endpoint signatures being frozen.
- The `scheduling/` app structure is established in Phase 1 so that no subsequent phase creates new module layout decisions under time pressure.

### Research Flags

Phases likely needing deeper research during planning:
- **Phase 3 (Session Request Flow):** The `select_for_update()` + `transaction.atomic()` interaction with the existing `_broadcast()` WebSocket pattern needs careful sequencing. Verify the existing codebase's stated rule ("broadcast after transaction") holds for the accept flow before writing the view.
- **Phase 4 (Score Auto-Update):** The exact trigger point in `session/views.py` (which view, which line after which save) needs codebase confirmation before implementation to avoid touching the wrong save path.

Phases with standard patterns (skip research-phase):
- **Phase 1 (Profiles):** OneToOne profile extension is a well-documented Django pattern; direct implementation is safe.
- **Phase 2 (Availability):** `AvailabilitySlot` as weekday+hour rows and `compute_available_slots()` as a pure function are standard and fully specified in ARCHITECTURE.md.
- **Phase 5 (Email):** Service function stubs following the existing `main/services/email.py` pattern; no new pattern needed.
- **Phase 6 (Docs):** Standard documentation update, no architectural decisions.

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | All new additions verified against current PyPI; existing stack confirmed from codebase inspection |
| Features | HIGH | Domain patterns well-established (Preply, iTalki, Calendly analogues); implementation grounded in existing codebase |
| Architecture | HIGH | Directly derived from codebase inspection + established Django patterns; code samples provided for all major components |
| Pitfalls | HIGH | Most claims verified against Django docs and community post-mortems; several pitfalls confirmed against existing codebase state (e.g., views.py at 1031 lines, InMemoryChannelLayer) |

**Overall confidence:** HIGH

### Gaps to Address

- **Reminder email async delivery:** The session reminder email requires Celery/Django-Q, which is out of scope for v1.2. The stub approach is confirmed correct, but the async gap should be explicitly flagged in `docs/api/` and in the `notify_session_reminder` function's docstring so the next infra milestone can wire it without archaeology.
- **`MEDIA_URL` / `MEDIA_ROOT` configuration:** STACK.md notes these may already be configured (a `media/` directory exists for `SessionRecording`). Confirm before adding duplicate config in Phase 1 — duplicate `MEDIA_ROOT` settings cause silent media file routing errors.
- **`IELTSMockSession` status on booking-created sessions:** The existing session lifecycle starts at a status that assumes the examiner manually created the session. When `SessionRequest.accept()` creates an `IELTSMockSession`, the initial status and the `invite_token` flow need to be confirmed compatible with the existing `can_start()` guards. This should be validated in Phase 3 before the accept endpoint goes live.
- **Phone field visibility in profile serializer:** The security rules state phone should only be returned to the profile owner, not all authenticated users. The serializer implementation needs a conditional field or two serializer classes (`ExaminerProfileDetailSerializer` for owner, `ExaminerProfilePublicSerializer` for candidates).

## Sources

### Primary (HIGH confidence)
- Codebase inspection: `main/models.py`, `session/models.py`, `session/views.py`, `main/services/email.py`, `requirements.txt`, `MockIT/settings.py`
- [Django OneToOne profile extension](https://docs.djangoproject.com/en/5.2/topics/db/examples/one_to_one/) — profile model pattern
- [Django timezones](https://docs.djangoproject.com/en/6.0/topics/i18n/timezones/) — USE_TZ handling
- [Pillow 12.1.1 on PyPI](https://pypi.org/project/pillow/) — version confirmed
- [Mastering select_for_update() in Django](https://dev.to/karaa1122/mastering-selectforupdate-in-django-prevent-race-conditions-the-right-way-4l56) — double-booking prevention

### Secondary (MEDIUM confidence)
- [How to Build an Online Tutoring Marketplace Platform — yo-coach.com](https://www.yo-coach.com/blog/how-to-build-an-online-tutoring-marketplace-platform/) — feature landscape
- [12 Best Online Booking Systems for Tutors — Tutorbase](https://tutorbase.com/blog/best-online-booking-systems-for-tutors) — competitor feature analysis
- [How to Prevent Double Bookings — Medium/Vikas Jha](https://medium.com/@get2vikasjha/how-to-prevent-double-bookings-and-ensure-real-time-availability-in-any-scheduling-system-1f311781497f) — booking race condition patterns

### Tertiary (LOW confidence — needs validation during implementation)
- [Resend Django integration guide](https://resend.com/docs/send-with-django) — confirms existing direct SDK approach is valid; no action needed

---
*Research completed: 2026-03-30*
*Ready for roadmap: yes*
