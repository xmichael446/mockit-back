# Pitfalls Research

**Domain:** Adding profiles, availability scheduling, and booking request flow to an existing Django exam platform
**Researched:** 2026-03-30
**Confidence:** HIGH (most claims verified against Django docs, community post-mortems, and known codebase state)

---

## Critical Pitfalls

### Pitfall 1: Double-Booking from Missing Row-Level Lock

**What goes wrong:**
Two candidates simultaneously request the same availability slot. Both requests read the slot as "available," both pass validation, and both BookingRequest records are created. The examiner ends up with two confirmed sessions at the same time.

**Why it happens:**
`transaction.atomic()` provides atomicity (all-or-nothing), but it does NOT lock the rows being checked. Between the `SELECT` (availability check) and the `INSERT` (booking creation), another transaction can sneak in and claim the same slot. This is especially likely when the booking endpoint becomes popular.

**How to avoid:**
Wrap the availability check and booking creation inside a single `transaction.atomic()` block and use `select_for_update()` on the availability record before checking it:

```python
with transaction.atomic():
    slot = AvailabilitySlot.objects.select_for_update().get(pk=slot_id)
    if slot.is_booked:
        raise ValidationError("Slot already taken.")
    slot.is_booked = True
    slot.save(update_fields=["is_booked", "updated_at"])
    BookingRequest.objects.create(slot=slot, candidate=request.user)
```

Do NOT put the `_broadcast()` call inside the `atomic()` block. The existing codebase already follows the pattern of broadcasting after the transaction closes (STATE.md: "Broadcast calls placed after transaction.atomic block to prevent stale events on rollback"). Keep this discipline here.

**Warning signs:**
- Examiner sees two pending requests for the same time window
- Duplicate `BookingRequest` rows in the database with the same slot FK
- No `unique_together` or DB-level uniqueness constraint on (slot, status=ACCEPTED)

**Phase to address:**
Phase: Availability + Booking (the phase that creates `BookingRequest`). The lock must be in place before any booking endpoint goes live — it cannot be retrofitted safely.

---

### Pitfall 2: Timezone Confusion in Availability Windows

**What goes wrong:**
The examiner sets "available Monday 10:00–11:00." The system stores this as a naive datetime or interprets it in the server's timezone (UTC). A candidate in a different timezone sees the wrong slot time, books it, and the session starts at the wrong moment.

**Why it happens:**
The project already uses `USE_TZ = True` and `TIME_ZONE = 'UTC'` (settings.py line 160–162). All existing datetimes (`session.scheduled_at`, `session.started_at`, etc.) are stored UTC-aware. But availability windows are recurring weekly schedules — they represent "local wall-clock time for the examiner." Developers often store these as plain `time` fields or naive `DateTimeField` values, forgetting to attach a timezone to them.

**How to avoid:**
- Store availability slots as UTC-aware `DateTimeField` instances (not `TimeField`).
- When an examiner creates a slot, require a `timezone` string in the request (e.g., `"Europe/London"`) and convert to UTC before saving.
- On retrieval, convert back to the examiner's timezone for display only.
- Never compare availability slots to `timezone.now()` without confirming both sides are aware.
- Use `django.utils.timezone.make_aware(naive_dt, tz)` for any conversion.

**Warning signs:**
- `RuntimeWarning: DateTimeField received a naive datetime` in logs
- Slots appearing shifted by exactly N hours (classic UTC/local offset bug)
- `can_start()` passes too early or refuses to start when examiner expects it to work (the existing guard checks `timezone.now() >= self.scheduled_at` — the new booking flow must produce the same kind of aware scheduled_at)

**Phase to address:**
Phase: Availability model design. Timezone handling must be designed upfront — retrofitting it after data exists requires a migration that converts all stored values.

---

### Pitfall 3: Missing State Machine for BookingRequest (Parallel to Session State Machine)

**What goes wrong:**
The `BookingRequest` object transitions through states: PENDING → ACCEPTED or REJECTED → (on accept) a `IELTSMockSession` is created. Without guards on these transitions, double-accept is possible (accept called twice), or a session is created even after the request is rejected, or the examiner accepts an expired request.

**Why it happens:**
The v1.1 work explicitly centralized session state into a state machine on the model. But when adding a new `BookingRequest` model, developers treat it as a simple CRUD model and put the transition logic in the view, duplicating the anti-pattern that was fixed in v1.1.

**How to avoid:**
Apply the same pattern used for `IELTSMockSession`:
- `BookingRequestStatus` as `IntegerChoices` on the model
- `can_accept()`, `can_reject()`, `can_expire()` guard methods
- `accept()`, `reject()`, `expire()` transition methods that raise `ValidationError` on invalid state
- The accept() method should create the `IELTSMockSession` inside a transaction

This is documented in the existing codebase as working well: STATE.md entry "ValidationError from model methods propagates through DRF -- no try/except needed in views."

**Warning signs:**
- Transition logic in the view (`if request.status == 'PENDING': request.status = 'ACCEPTED'`)
- No `ValidationError` raised on duplicate accept
- No DB-level uniqueness preventing two accepted requests for the same slot

**Phase to address:**
Phase: BookingRequest model. Design state machine before writing any view that acts on it.

---

### Pitfall 4: views.py Grows Beyond 1031 Lines

**What goes wrong:**
`session/views.py` is already 1031 lines. Adding profile CRUD, availability management, and booking request views to the same file creates a 1500–2000-line monster that is untestable, unsearchable, and causes merge conflicts on every feature branch.

**Why it happens:**
The quick-task and incremental approach (which has worked well for v1.1) defaults to appending to the existing file because all imports are already there. There is no natural forcing function to stop and restructure.

**How to avoid:**
Create new views in their own modules from the start:
- `main/views/` package with `profiles.py`
- A new `scheduling/` app (or `session/views/availability.py` and `session/views/booking.py`)

Do NOT refactor the existing `session/views.py` as part of v1.2 — that risks breaking the 26 existing tests and the live API. Only new views go into new files.

**Warning signs:**
- PR diffs show changes to `session/views.py` for profile or availability features
- Import conflicts when two features both add to the same views file
- "It's just one more view" reasoning

**Phase to address:**
Phase 1 (profiles). Establish the new module structure before writing any view code.

---

### Pitfall 5: Profile Model Bloat on the User Model

**What goes wrong:**
Examiner bio, credentials, verification badge, phone, and student score history are added directly as fields on the existing `User` model (in `main/models.py`). Over time, the `User` table accumulates 20+ fields, most of which are NULL for guests and the opposite role.

**Why it happens:**
It is faster to add fields to the existing model. The custom `User` model already has `is_guest`, `max_sessions`, `is_verified` — adding a few more seems harmless. Each individual field decision is locally defensible.

**How to avoid:**
Create separate profile models with `OneToOneField(User, ...)`:
- `ExaminerProfile` — bio, credentials, verification badge, phone
- `CandidateProfile` — auto-updated score history fields

Keep `User` for authentication only. This matches the Django documentation recommendation for post-hoc extensions and avoids the "all NULLs for wrong role" problem.

Use `get_or_create` patterns in serializers and signals rather than assuming the profile always exists (it may not for legacy guest accounts).

**Warning signs:**
- Migration that adds nullable fields to the `main_user` table
- View code checking `request.user.role` to decide which fields to include in the serializer response
- Serializer with `required=False` on 8+ fields because they only apply to one role

**Phase to address:**
Phase: Profiles. Architecture decision must be made before any migration is written.

---

### Pitfall 6: Candidate Score Auto-Update Breaking Existing Session Completion Flow

**What goes wrong:**
A `post_save` signal on `SessionResult` is added to update `CandidateProfile.last_band`. The signal fires whenever `SessionResult` is saved — including during intermediate saves (e.g., `is_released = False` initial creation). The candidate's profile gets updated with an unreleased, potentially incomplete band score.

**Why it happens:**
Django's `post_save` signal fires on every save, not only when a result is released. The signal author checks `created=True` but forgets that the band update should only happen when `is_released` transitions to `True`.

**How to avoid:**
Check the `is_released` flag inside the signal, and use `update_fields` to detect that this is specifically a release save:

```python
@receiver(post_save, sender=SessionResult)
def update_candidate_profile_band(sender, instance, **kwargs):
    if instance.is_released and instance.overall_band is not None:
        CandidateProfile.objects.filter(user=instance.session.candidate).update(
            last_band=instance.overall_band,
            last_session_at=instance.released_at,
        )
```

Alternatively: trigger the update from the `ReleaseResultView` view directly (explicit is safer than signal-based side effects in this codebase).

**Warning signs:**
- Signal fires but `is_released` is False
- Candidate sees a band score before the examiner releases it
- Existing `ReleaseResultView` test breaks because profile update happens at wrong time

**Phase to address:**
Phase: Profiles (score auto-update sub-task). Must be validated against the existing release flow.

---

### Pitfall 7: Email Notifications Blocking the Request Cycle

**What goes wrong:**
Booking-related emails (request received, accepted, rejected) are sent synchronously inside the view using the existing Resend integration. If Resend is slow (>2s) or times out, the HTTP response to the candidate or examiner hangs. Under load, all request workers block waiting for email delivery.

**Why it happens:**
The existing email pattern (v1.1) was designed for low-volume operations like email verification — one email per registration. Booking events generate multiple emails per transaction (candidate confirmation + examiner notification). The synchronous pattern that worked for verify-email now becomes a latency problem.

**How to avoid:**
The PROJECT.md scope says email notifications are "stubbed" for v1.2. Use this to your advantage: implement email sending as a separate function (`send_booking_email(trigger, context)`) that is called after the transaction commits, but keep it synchronous for now with a clear comment marking it for async migration. Do not inline email calls inside `transaction.atomic()` blocks — a Resend timeout would roll back the booking itself.

The existing pattern from v1.1 (email send returns bool, callers decide how to surface failure) is the right model. Extend it.

**Warning signs:**
- `resend.Emails.send(...)` called inside a `with transaction.atomic():` block
- Request latency spikes correlated with email volume
- Booking creation fails when Resend is down

**Phase to address:**
Phase: Booking + Email notifications. Enforce the "email after transaction" rule from day one.

---

### Pitfall 8: Availability Calculation N+1 Query on Slot Listing

**What goes wrong:**
The `/api/examiners/` or `/api/examiners/<pk>/availability/` endpoint iterates over availability slots and for each slot checks whether a `BookingRequest` or `IELTSMockSession` exists at that time. This generates one query per slot — 20 slots = 20 queries. At page load this is invisible in dev (SQLite is fast, few records) but hits hard in production with real data.

**Why it happens:**
Availability slot models are designed in isolation. The serializer that renders "is this slot available?" reaches back into `BookingRequest` or `IELTSMockSession` without the view having prefetched that data.

**How to avoid:**
Design the availability list queryset with explicit prefetches from the start:

```python
AvailabilitySlot.objects.filter(examiner=pk).prefetch_related(
    Prefetch("booking_requests", queryset=BookingRequest.objects.filter(status=BookingRequestStatus.ACCEPTED))
)
```

Annotate "is_taken" at the queryset level using `annotate(is_taken=Exists(...))` rather than computing it in Python.

**Warning signs:**
- Django Debug Toolbar (or `connection.queries`) shows repeated identical queries during slot listing
- Query count scales linearly with number of slots
- Slot listing endpoint is slow even with small data sets

**Phase to address:**
Phase: Availability model and API. Add the prefetch in the initial queryset design, not as a retrofit.

---

### Pitfall 9: Invite Token Flow and BookingRequest Flow Creating Orphaned Sessions

**What goes wrong:**
The existing flow creates a session first, then sends an invite token. The new booking flow creates a `BookingRequest` first, then creates a session on accept. If a developer adds a "create session on booking request creation" shortcut (to reuse existing session code), there will be sessions without a confirmed booking request — ghost sessions that the examiner never intended to confirm.

**Why it happens:**
The `IELTSMockSession` model is already well-understood; the `BookingRequest` model is new. Developers anchor new logic to familiar patterns and create the session too early.

**How to avoid:**
`IELTSMockSession` should only be created inside `BookingRequest.accept()`. The session is the output of acceptance, not a precondition. Enforce this with a clear comment in `BookingRequest.accept()` and never expose a "create session from booking request" path in the API that bypasses the state machine.

**Warning signs:**
- `IELTSMockSession` records with `status=SCHEDULED` and no linked `BookingRequest`
- `BookingRequest` records with `status=PENDING` that already have a session FK set
- Session list showing entries the examiner does not recognise

**Phase to address:**
Phase: BookingRequest model and accept flow.

---

### Pitfall 10: Breaking the Existing REST API Contract

**What goes wrong:**
New profile-related fields are added to existing serializers (e.g., `SessionSerializer` includes examiner's profile, `UserSerializer` includes profile fields). The React frontend, which is not versioned and ships independently, starts receiving unexpected fields or — worse — has an existing field removed or renamed.

**Why it happens:**
The backend and frontend are developed separately. A "small" serializer change (renaming `is_verified` to `verification_status`, or nesting user data under a `profile` key) looks trivial on the backend but requires a coordinated frontend deploy.

**How to avoid:**
- Never rename, remove, or change the type of existing fields in any serializer that the frontend currently uses.
- New fields on existing serializers are safe if they are additive and nullable (frontend ignores unknown fields in JSON).
- New profile data should be returned from new endpoints (`/api/profiles/examiner/<pk>/`), not embedded into existing session endpoints.
- Audit existing `docs/api/` docs before each migration: confirm that no field in a currently-documented response is being changed.

**Warning signs:**
- Frontend logs `Cannot read properties of undefined` for a field that used to exist
- A serializer field is renamed "for clarity" without a frontend coordination ticket
- `SessionSerializer` diff shows structural changes to the response shape

**Phase to address:**
Throughout all phases. This is a cross-cutting constraint, not a one-time fix.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Add profile fields directly to `User` model | No new migration complexity | NULLs for wrong role, bloated auth table, profile/auth concerns mixed | Never — the custom User model is already defined |
| Put booking logic in views.py | Faster to write | views.py grows past 1500 lines, logic untestable in isolation | Never — new features must go in new modules |
| Send email inside `transaction.atomic()` | Simpler code path | Resend timeout rolls back booking; email and DB state diverge | Never — this already caused grief in v1.1 |
| Generate available slots on-the-fly without caching | No stored data to go stale | N+1 queries on every availability listing | Acceptable in Phase 1 if annotated properly; revisit at scale |
| Single `status` field on BookingRequest without transitions | Fewer model methods to write | Duplicate accepts possible; no audit trail of state transitions | Never — apply the same state machine pattern as IELTSMockSession |
| Skip `select_for_update()` in booking accept | Simpler code | Silent double-booking under concurrent load | Never |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Resend (email) | Calling `resend.Emails.send()` inside `transaction.atomic()` — network failure rolls back the DB transaction | Call email send after `atomic()` block exits; use the existing bool-return pattern from v1.1 |
| 100ms (video) | Calling `create_room()` inside booking accept before session is confirmed live | Room is created on `session.start`, not on booking accept. Keep this separation. |
| Django Channels `_broadcast()` | Broadcasting inside `atomic()` — if transaction rolls back, stale event is already sent to WebSocket clients | Existing codebase places `_broadcast()` after the transaction; maintain this rule for all booking events |
| DRF `ValidationError` from model methods | Wrapping model state machine calls in try/except and returning 500 | Let `ValidationError` propagate — DRF converts it to 400 automatically. This is already established in v1.1 |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| N+1 on availability slot listing | Slot list endpoint is slow; query count = number of slots | Use `prefetch_related` + `Exists` annotations in queryset | Visible at 20+ slots per examiner |
| Unindexed `BookingRequest` status filter | Slow booking dashboard queries | Add `db_index=True` to `status` field (same as `IELTSMockSession.status`) | Visible at 100+ booking requests |
| Serializer-level availability calculation | `is_available` computed in Python per slot by hitting DB | Move to ORM annotation at queryset layer | Visible at 10+ concurrent API calls |
| Naive recurring slot expansion | Weekly schedule expanded into individual `DateTimeField` rows for 52 weeks upfront | Store as weekly template + generate on read (or generate only 4 weeks ahead via a management command) | Hits immediately if expansion happens at signup |

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Candidate can accept their own booking request | Examiner auth bypass — candidate sets their own session to ACCEPTED | Check `request.user == booking_request.examiner` in accept/reject views, not just that the user is authenticated |
| Examiner profile exposes phone to unauthenticated users | Phone number harvesting | Require `IsAuthenticated` on all profile endpoints; return phone only to the profile owner |
| BookingRequest list returns all requests, not scoped to user | Candidate sees other candidates' requests for the same examiner | Filter queryset to `Q(candidate=request.user) | Q(slot__examiner=request.user)` |
| IELTS score history exposed to wrong role | Candidate A sees Candidate B's scores | `CandidateProfile` endpoint must filter to `profile.user == request.user` OR the examiner who conducted the session |
| Rate limit missing on booking creation | Slot flooding — candidate creates 100 booking requests | Apply `ScopedRateThrottle` on the booking create endpoint (same pattern as auth endpoints in v1.1) |

---

## UX Pitfalls

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Showing slot times in server UTC | Examiner sees "Monday 08:00" but means their local "Monday 10:00" | Always render slot times in the user's timezone; accept timezone in the request |
| No expiry on pending BookingRequest | Candidate books a slot 3 weeks out, never shows up; slot remains "pending" forever | Add `expires_at` field on `BookingRequest`; auto-expire PENDING requests at session start time minus buffer |
| Accepting a booking creates a session silently | Examiner does not know a session was created | Send examiner an email and/or WebSocket event when a booking is accepted and a session is created |
| Availability calendar shows no feedback when slot is taken mid-browse | Candidate sees "available," clicks, gets 409 | Return clear error: "This slot was just taken. Please choose another." — the `select_for_update()` path naturally surfaces this |

---

## "Looks Done But Isn't" Checklist

- [ ] **Booking double-book prevention:** `select_for_update()` present in booking accept transaction — verify with a concurrent request test (even manual)
- [ ] **Timezone storage:** All `DateTimeField` values created via `timezone.make_aware()` or `timezone.now()`, never `datetime.now()` — grep for `datetime.now()` before merging
- [ ] **BookingRequest state machine:** `accept()` raises `ValidationError` if already accepted — verify duplicate accept returns 400, not 200
- [ ] **Profile endpoint auth:** Profile detail endpoint tested with unauthenticated request (should 401) and wrong-user request (should 403) — not just happy-path
- [ ] **Existing API contract:** Run a diff of all serializer output against `docs/api/` before merging any phase — confirm no field renamed or removed
- [ ] **Session creation gate:** Confirm no `IELTSMockSession` is created before `BookingRequest.accept()` is called — check for any shortcut that creates sessions directly from booking endpoints
- [ ] **Email outside transaction:** No `resend.Emails.send()` call inside any `transaction.atomic()` block — grep for this pattern before each phase merge
- [ ] **views.py line count:** `session/views.py` should not grow. Profile, availability, and booking views live in new modules — verify with `wc -l session/views.py` before and after each phase

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Double-booking discovered in production | HIGH | Identify duplicate sessions; manually cancel one; add `select_for_update()` hotfix; notify affected examiner |
| Timezone data stored as naive | HIGH | Write a migration to convert stored datetimes to UTC-aware; requires knowing original timezone of each record — often impossible after the fact |
| User model bloat (profile fields on User) | MEDIUM | Write a data migration to move fields to a new `ExaminerProfile`/`CandidateProfile` model; update all serializers and views referencing those fields |
| views.py becomes 1500+ lines | MEDIUM | Extract new views to separate files without touching existing ones; update `urls.py` imports; no logic changes needed |
| BookingRequest missing state guards | MEDIUM | Add state machine methods to model; add migration for `status` db_index; test all transitions |
| API contract broken (field renamed) | HIGH | Coordinate immediate frontend hotfix deploy; add deprecated alias field returning old value while frontend migrates |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Double-booking race condition | Booking + Session creation phase | Manual concurrent request test; check for `select_for_update()` in booking accept view |
| Timezone naive datetime | Availability model design phase | Grep for `datetime.now()` and `make_naive`; check migration uses `DateTimeField` not `TimeField` |
| BookingRequest missing state machine | BookingRequest model phase | Duplicate accept returns 400; state diagram documented in model comments |
| views.py bloat | Phase 1 (profiles) | `wc -l session/views.py` must not change; new views in new module |
| Profile model bloat on User | Profiles phase | Migration touches `main_examinerprofile` / `main_candidateprofile`, not `main_user` |
| Score auto-update on wrong trigger | Profiles + session result phase | Create unreleased result; verify candidate profile not updated; release result; verify profile updated |
| Email blocking request cycle | Booking + notification phase | Grep: no `resend.Emails.send` inside `atomic()`; introduce artificial Resend delay in dev and confirm booking still returns fast |
| Availability N+1 | Availability API phase | Django Debug Toolbar query count on slot listing; query count must be O(1) not O(n) |
| Orphaned sessions from early creation | Booking accept phase | Check `IELTSMockSession` count before and after booking creation (not accept) — must not increase |
| API contract broken | Every phase | Diff serializer output against `docs/api/` before merging; no field removed or renamed |

---

## Sources

- [Mastering select_for_update() in Django — DEV Community](https://dev.to/karaa1122/mastering-selectforupdate-in-django-prevent-race-conditions-the-right-way-4l56)
- [Django @atomic Doesn't Prevent Race Conditions — Medium](https://medium.com/@anas-issath/djangos-atomic-decorator-didn-t-prevent-my-race-condition-and-the-docs-never-warned-me-58a98177cb9e)
- [Guarding Critical Operations: SELECT FOR UPDATE — DEV Community](https://dev.to/alairjt/guarding-critical-operations-mastering-select-for-update-for-race-condition-prevention-in-django--32mg)
- [Time zones — Django documentation](https://docs.djangoproject.com/en/6.0/topics/i18n/timezones/)
- [Mastering Django Timezones — Piotr Gryko](https://www.piotrgryko.com/posts/django-timezone-handling/)
- [Extending Django's User Model with OneToOneField — Crunchy Data](https://www.crunchydata.com/blog/extending-djangos-user-model-with-onetoonefield)
- [Django Signals Guide: Best Practices — NuVenture Connect](https://nuventureconnect.com/blog/2024/01/12/django-signals-guide-best-practices/)
- [Asynchronous Email Sending in Django — blog.adonissimo.com](https://blog.adonissimo.com/how-to-efficiently-sending-emails-asynchronously-in-django)
- [Refactoring a Legacy Django Codebase — DEV Community](https://dev.to/myroslavmokhammadabd/refactoring-a-legacy-django-codebase-without-breaking-production-1ee0)
- [How to Organize Views in Django — desarrollolibre.net](https://www.desarrollolibre.net/blog/django/how-to-organize-your-views-in-django-split-a-giant-viewspy-into-clean-modular-files)
- [MockIT codebase: session/models.py, session/views.py, main/models.py, .planning/STATE.md, .planning/PROJECT.md]

---
*Pitfalls research for: Profiles, availability scheduling, and session booking flow on existing Django exam platform*
*Researched: 2026-03-30*
