# Architecture Research

**Domain:** IELTS Mock Exam Platform — Profiles, Availability Scheduling, Session Booking
**Researched:** 2026-03-30
**Confidence:** HIGH (direct codebase inspection + established Django patterns)

## Standard Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        REST API Layer                            │
├───────────────┬───────────────┬──────────────────────────────────┤
│  main/ app    │ scheduling/   │  session/ app (existing)         │
│  ─────────    │  app (NEW)    │  ──────────────────────          │
│  Auth views   │  Profile views│  Session lifecycle views         │
│  User model   │  Avail. views │  WS Consumer                     │
│  Email svc    │  Request views│  _broadcast() helper             │
│               │  Email svc    │                                  │
└───────────────┴───────────────┴──────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────────┐
│                      Data Layer (PostgreSQL)                      │
│  User   ExaminerProfile   CandidateProfile   AvailabilitySlot    │
│  EmailVerificationToken   SessionRequest     IELTSMockSession     │
└──────────────────────────────────────────────────────────────────┘
                         │
┌────────────────────────▼─────────────────────────────────────────┐
│                   External Services                               │
│  Resend (email notifications)   100ms (video rooms, existing)    │
└──────────────────────────────────────────────────────────────────┘
```

### Component Responsibilities

| Component | Responsibility | Location |
|-----------|----------------|----------|
| `ExaminerProfile` | Bio, credentials, verification badge, phone | `main/models.py` (OneToOne) |
| `CandidateProfile` | Best scores, auto-update from session results | `main/models.py` (OneToOne) |
| `AvailabilitySlot` | Weekly recurring 1-hour windows (weekday + hour) | `scheduling/models.py` |
| `SessionRequest` | Request from candidate → examiner, pending/accepted/rejected | `scheduling/models.py` |
| `scheduling/views.py` | Profile CRUD, availability CRUD, request flow endpoints | `scheduling/views.py` |
| `scheduling/services/email.py` | Email notifications at booking trigger points | `scheduling/services/email.py` |
| `scheduling/services/availability.py` | Real availability = schedule minus booked windows | `scheduling/services/availability.py` |

## Recommended Project Structure

```
MockIT/
├── main/
│   ├── models.py           # ADD: ExaminerProfile, CandidateProfile (OneToOne)
│   ├── serializers.py      # ADD: profile serializers
│   ├── views.py            # UNCHANGED (auth only)
│   ├── urls.py             # UNCHANGED (auth URLs only)
│   ├── permissions.py      # UNCHANGED
│   └── services/
│       └── email.py        # UNCHANGED (verification email)
│
├── scheduling/             # NEW APP — contains all v1.2 booking logic
│   ├── __init__.py
│   ├── apps.py
│   ├── models.py           # AvailabilitySlot, SessionRequest
│   ├── serializers.py      # All scheduling serializers
│   ├── views.py            # Profile, availability, request endpoints
│   ├── urls.py             # /api/profiles/, /api/availability/, /api/requests/
│   ├── permissions.py      # IsExaminer, IsCandidate role guards
│   ├── admin.py
│   └── services/
│       ├── __init__.py
│       ├── availability.py # compute_available_slots(examiner, week_start)
│       └── email.py        # notification stubs + Resend calls
│
├── session/                # EXISTING — minimal changes
│   ├── models.py           # UNCHANGED
│   ├── views.py            # UNCHANGED (session lifecycle)
│   └── ...
│
└── MockIT/
    └── urls.py             # ADD: include("scheduling.urls")
```

**Why a new `scheduling/` app rather than extending `main/` or `session/`:**
- `main/` is authentication-only; mixing booking logic violates single-responsibility and grows the app into an unrelated domain.
- `session/` owns the live exam lifecycle (start → score → release); booking is pre-session and causally prior.
- A new app keeps migrations isolated and makes the domain boundary explicit in the codebase.

**Why profiles live in `main/models.py` rather than `scheduling/models.py`:**
- Profiles are extensions of `User`, which lives in `main/`. Django convention is to colocate tightly coupled models.
- `CandidateProfile` is auto-updated from `session/` signal/call; keeping it in `main/` avoids a circular import between `scheduling/` and `session/`.

## Architectural Patterns

### Pattern 1: OneToOne Profile Extension

**What:** `ExaminerProfile` and `CandidateProfile` as `OneToOne` fields on `User`, created lazily on first access or eagerly via post-save signal.
**When to use:** Role-specific data that should not bloat the base `User` model and is read/written independently.
**Trade-offs:** Clean separation; requires `select_related("examiner_profile")` in querysets to avoid N+1. Signal-based creation adds a tiny write on every user save — acceptable at this scale.

```python
# main/models.py
class ExaminerProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="examiner_profile",
        limit_choices_to={"role": User.Role.EXAMINER},
    )
    bio = models.TextField(blank=True)
    credentials = models.TextField(blank=True)
    phone = models.CharField(max_length=20, blank=True)
    is_verified_examiner = models.BooleanField(default=False)  # admin-set badge
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

class CandidateProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="candidate_profile",
        limit_choices_to={"role": User.Role.CANDIDATE},
    )
    best_overall_band = models.DecimalField(max_digits=3, decimal_places=1, null=True, blank=True)
    best_fc = models.PositiveSmallIntegerField(null=True, blank=True)
    best_gra = models.PositiveSmallIntegerField(null=True, blank=True)
    best_lr = models.PositiveSmallIntegerField(null=True, blank=True)
    best_pr = models.PositiveSmallIntegerField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
```

### Pattern 2: Availability as Weekly Recurring Slots

**What:** `AvailabilitySlot` stores `(weekday: 0–6, hour: 8–21)` pairs per examiner — no date, only a recurring pattern. Available windows for a given week are computed on-the-fly by subtracting accepted `SessionRequest` datetimes.
**When to use:** Examiners set their weekly availability once; it recurs every week without re-entry.
**Trade-offs:** Simple model; requires a service function to hydrate slots into actual datetimes for a given week. Does not support one-off exceptions (out of scope for v1.2).

```python
# scheduling/models.py
class AvailabilitySlot(models.Model):
    examiner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="availability_slots",
        limit_choices_to={"role": User.Role.EXAMINER},
    )
    weekday = models.PositiveSmallIntegerField()  # 0=Mon … 6=Sun
    hour = models.PositiveSmallIntegerField()     # 8–21 (windows 08:00–22:00)

    class Meta:
        unique_together = [("examiner", "weekday", "hour")]
        ordering = ["weekday", "hour"]
```

```python
# scheduling/services/availability.py
from datetime import date, datetime, timezone, timedelta
from .models import AvailabilitySlot, SessionRequest

def compute_available_slots(examiner, week_start: date) -> list[datetime]:
    """
    Return list of UTC datetimes for examiner's free 1-hour windows
    in the week starting on week_start (Monday).
    """
    slots = AvailabilitySlot.objects.filter(examiner=examiner)
    booked = SessionRequest.objects.filter(
        examiner=examiner,
        status=SessionRequest.Status.ACCEPTED,
        requested_datetime__gte=week_start,
        requested_datetime__lt=week_start + timedelta(days=7),
    ).values_list("requested_datetime", flat=True)

    booked_set = {dt.replace(minute=0, second=0, microsecond=0) for dt in booked}
    available = []
    for slot in slots:
        day_offset = slot.weekday - week_start.weekday()
        if day_offset < 0:
            day_offset += 7
        slot_dt = datetime(
            week_start.year, week_start.month, week_start.day,
            slot.hour, 0, 0, tzinfo=timezone.utc
        ) + timedelta(days=day_offset)
        if slot_dt not in booked_set:
            available.append(slot_dt)
    return sorted(available)
```

### Pattern 3: SessionRequest State Machine (mirrors IELTSMockSession)

**What:** `SessionRequest` carries a status field with PENDING → ACCEPTED / REJECTED transitions. Acceptance atomically creates the `IELTSMockSession` and a scheduled datetime. Rejection is terminal.
**When to use:** Any multi-party workflow with explicit approval. State machine on the model matches the existing pattern in `IELTSMockSession`.
**Trade-offs:** Keeps the pattern consistent; logic is discoverable in one place. Acceptance creates a session — this is a two-model write that must be wrapped in `transaction.atomic()`.

```python
# scheduling/models.py
class SessionRequest(models.Model):
    class Status(models.IntegerChoices):
        PENDING  = 1, "Pending"
        ACCEPTED = 2, "Accepted"
        REJECTED = 3, "Rejected"

    candidate = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="sent_requests",
        limit_choices_to={"role": User.Role.CANDIDATE},
    )
    examiner = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.CASCADE,
        related_name="received_requests",
        limit_choices_to={"role": User.Role.EXAMINER},
    )
    requested_datetime = models.DateTimeField()  # exact 1-hour window start
    message = models.TextField(blank=True)
    status = models.PositiveSmallIntegerField(
        choices=Status.choices, default=Status.PENDING, db_index=True
    )
    session = models.OneToOneField(
        "session.IELTSMockSession",
        on_delete=models.SET_NULL, null=True, blank=True,
        related_name="booking_request",
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def accept(self, preset=None):
        if self.status != self.Status.PENDING:
            raise ValidationError("Can only accept a pending request.")
        self.status = self.Status.ACCEPTED

    def reject(self):
        if self.status != self.Status.PENDING:
            raise ValidationError("Can only reject a pending request.")
        self.status = self.Status.REJECTED
```

### Pattern 4: Email Notifications as a Thin Service

**What:** Each notification trigger (request submitted, request accepted, request rejected) calls a dedicated function in `scheduling/services/email.py`. Functions are stubbed (log only) initially and filled in iteratively.
**When to use:** Email is a side-effect of a state change; isolating it in a service keeps views clean and makes stubs easy to swap for real Resend calls.
**Trade-offs:** No async queue (Celery) in scope; email is synchronous. Failure is caught and logged, not raised — matches the existing pattern in `main/services/email.py`. This means a Resend timeout could slow a request response; acceptable at low scale, revisit if needed.

```python
# scheduling/services/email.py
import logging
import resend
from django.conf import settings

logger = logging.getLogger("mockit.email")

def notify_examiner_new_request(request_obj):
    """Stub: notify examiner that a candidate has requested a session."""
    logger.info("notify_examiner_new_request: request_id=%s", request_obj.pk)
    # TODO: send Resend email

def notify_candidate_accepted(request_obj):
    """Stub: notify candidate their request was accepted."""
    logger.info("notify_candidate_accepted: request_id=%s", request_obj.pk)
    # TODO: send Resend email

def notify_candidate_rejected(request_obj):
    """Stub: notify candidate their request was rejected."""
    logger.info("notify_candidate_rejected: request_id=%s", request_obj.pk)
    # TODO: send Resend email
```

## Data Flow

### Session Booking Request Flow

```
Candidate calls POST /api/requests/
    ↓
scheduling/views.py: validate slot is in examiner's available windows
    ↓
Create SessionRequest(status=PENDING)
    ↓
scheduling/services/email.notify_examiner_new_request()
    ↓
200 OK → candidate

Examiner calls POST /api/requests/<id>/accept/
    ↓
scheduling/views.py: validate examiner owns request, request is PENDING
    ↓
transaction.atomic():
    request.accept()
    IELTSMockSession.objects.create(
        examiner=request.examiner,
        candidate=request.candidate,
        scheduled_at=request.requested_datetime,
        status=SCHEDULED,
    )
    request.session = new_session
    request.save()
    ↓
scheduling/services/email.notify_candidate_accepted()
    ↓
200 OK → examiner (includes session_id)
```

### Candidate Profile Auto-Update Flow

```
Examiner submits CriterionScore (existing flow in session/views.py)
    ↓
SessionResult.compute_overall_band() called
    ↓
SessionResult saved with overall_band
    ↓
[Signal or explicit call in session/views.py]
CandidateProfile.update_best_scores(session_result)
    — updates best_overall_band, best_fc, best_gra, best_lr, best_pr if improved
    ↓
CandidateProfile saved
```

The signal vs. explicit call decision: prefer an explicit call in the existing `release_result` view rather than a `post_save` signal. Signals create hidden control flow; the release point is the single correct trigger and is already a known location in `session/views.py`.

### Availability Read Flow

```
Candidate calls GET /api/examiners/<id>/availability/?week=2026-03-30
    ↓
scheduling/views.py: parse week_start from query param (default: current week)
    ↓
scheduling/services/availability.compute_available_slots(examiner, week_start)
    — fetches AvailabilitySlot rows for examiner
    — fetches accepted SessionRequest datetimes for that week
    — returns sorted list of free UTC datetimes
    ↓
200 OK → [{datetime: "2026-04-01T09:00:00Z"}, ...]
```

## Integration Points

### New vs Modified Components

| Component | Status | Notes |
|-----------|--------|-------|
| `main/models.py` — `ExaminerProfile`, `CandidateProfile` | **NEW** (added to existing file) | OneToOne on User; colocated with User per Django convention |
| `main/serializers.py` | **MODIFIED** | Add profile serializers; extend `UserMinimalSerializer` if profile data needed in auth responses |
| `scheduling/` app | **NEW** | Entire app; register in `INSTALLED_APPS` and include URLs |
| `scheduling/models.py` | **NEW** | `AvailabilitySlot`, `SessionRequest` |
| `scheduling/services/availability.py` | **NEW** | `compute_available_slots()` pure function |
| `scheduling/services/email.py` | **NEW** | Stubbed notification functions |
| `session/views.py` — `release_result` view | **MODIFIED** | Add explicit call to `CandidateProfile.update_best_scores()` after result release |
| `MockIT/urls.py` | **MODIFIED** | Add `include("scheduling.urls")` |
| `MockIT/settings.py` | **MODIFIED** | Add `scheduling.apps.SchedulingConfig` to `INSTALLED_APPS` |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `scheduling/` → `main/` | Direct model import (`ExaminerProfile`, `CandidateProfile`) | One-way; no circular dependency |
| `scheduling/` → `session/` | Import `IELTSMockSession` for creation on accept | One-way; `scheduling` creates sessions, never owns them |
| `session/` → `main/` | Import `CandidateProfile` for score update on release | One-way; `session/` calls `main/` after result release |
| `scheduling/` → `Resend` | Via `scheduling/services/email.py` | Mirrors `main/services/email.py` pattern |

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Resend | Same as existing `main/services/email.py` — synchronous, catch exceptions, return bool | Reuse `settings.RESEND_API_KEY` and `settings.RESEND_FROM_EMAIL` |
| 100ms | No change — video room created on `session.start`, not on booking | Session created by accept flow uses existing `IELTSMockSession`; 100ms integration untouched |

## API Surface (new endpoints)

```
GET  /api/examiners/                          — list examiners with profiles (candidate view)
GET  /api/examiners/<id>/                     — examiner profile detail
GET  /api/examiners/<id>/availability/        — available slots (?week=YYYY-MM-DD)
PATCH /api/profiles/examiner/                 — update own examiner profile (examiner only)
PATCH /api/profiles/candidate/                — update own candidate profile (candidate only)
GET  /api/profiles/candidate/                 — view own candidate profile with scores

POST /api/requests/                           — candidate submits session request
GET  /api/requests/                           — list requests (own; role-filtered)
GET  /api/requests/<id>/                      — request detail
POST /api/requests/<id>/accept/               — examiner accepts (creates IELTSMockSession)
POST /api/requests/<id>/reject/               — examiner rejects

PATCH /api/availability/                      — examiner bulk-replaces their weekly slots
GET  /api/availability/                       — examiner views own slots
```

All endpoints under `/api/` and behind `IsEmailVerified` permission (existing default). Role guards added per-view in `scheduling/permissions.py`.

## Build Order (dependency-aware)

1. **Data layer first** — `ExaminerProfile`, `CandidateProfile` in `main/models.py` + `AvailabilitySlot`, `SessionRequest` in `scheduling/models.py` + migrations. Nothing else works without these.

2. **Profile read/write endpoints** — `GET/PATCH /api/examiners/`, `GET/PATCH /api/profiles/`. No inter-model dependencies; validates model shape against frontend needs early.

3. **Availability management** — `AvailabilitySlot` CRUD + `compute_available_slots()` service. Needed before requests can validate slot availability.

4. **Session request flow** — `POST /api/requests/`, `POST /api/requests/<id>/accept/` (creates session), `POST /api/requests/<id>/reject/`. Depends on availability service (step 3) for validation, and on `IELTSMockSession` creation logic already existing in `session/`.

5. **Candidate profile auto-update** — hook into `session/views.py` release_result. Depends on `CandidateProfile` existing (step 1) and scoring flow being stable (existing).

6. **Email notifications** — stub functions wired at trigger points in steps 3–5. Can be filled in independently after stubs are in place.

7. **API documentation update** — `docs/api/` additions after all endpoints stabilize.

## Anti-Patterns

### Anti-Pattern 1: Storing Computed Availability in the Database

**What people do:** Pre-generate a row for every available slot datetime for the next N weeks.
**Why it's wrong:** Requires background jobs to regenerate when schedule changes; availability for past/future weeks needs recalculation anyway; stale rows accumulate.
**Do this instead:** Store only the weekly pattern (`AvailabilitySlot.weekday` + `hour`). Compute actual datetimes on demand in `compute_available_slots()`. The computation is a simple loop over O(14 * 7) rows maximum — negligible cost.

### Anti-Pattern 2: Putting Scheduling Logic in `session/` or `main/`

**What people do:** Add availability and request models to `session/models.py` because booking eventually creates a session.
**Why it's wrong:** Conflates the booking domain (pre-session, marketplace) with the exam lifecycle domain (in-session, scoring). Grows `session/models.py` and `session/views.py` further beyond their current 10.5K and 37.8K sizes.
**Do this instead:** New `scheduling/` app. `scheduling/` creates `IELTSMockSession` objects via import; it does not own them after creation.

### Anti-Pattern 3: Modifying `IELTSMockSession` to Carry Booking State

**What people do:** Add `request_status` fields to `IELTSMockSession` to track whether it came from a booking.
**Why it's wrong:** Sessions created via the booking flow and sessions created directly by examiners (existing flow) are both valid. Pollutes the session model with pre-session state.
**Do this instead:** `SessionRequest.session` OneToOne FK is sufficient. A session either has a `booking_request` reverse relation or it doesn't — no changes to `IELTSMockSession`.

### Anti-Pattern 4: Async Email Without a Queue

**What people do:** Fire off email in a new thread or with `asyncio.create_task()` from a sync view.
**Why it's wrong:** Django sync views are not async-safe. Thread-based email delivery loses exceptions silently.
**Do this instead:** Keep email synchronous (matching existing `main/services/email.py`), wrapped in try/except, returning bool. If Resend latency becomes a problem, add Celery in a dedicated infrastructure milestone (already scoped out in PROJECT.md).

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-1k users | Current monolith + InMemoryChannelLayer is fine; sync email acceptable |
| 1k-10k users | Add `db_index=True` on `SessionRequest.status`, `SessionRequest.examiner`; migrate channel layer to Redis (already planned) |
| 10k+ users | Email queue (Celery + Redis); availability computation cacheable per examiner per week (Redis, short TTL) |

## Sources

- Direct codebase inspection: `main/models.py`, `session/models.py`, `session/views.py`, `main/services/email.py`, `session/services/hms.py`, `MockIT/settings.py`
- Django OneToOne profile extension pattern: established Django convention (docs.djangoproject.com/en/5.2/topics/db/examples/one_to_one/)
- State machine on model pattern: matches existing `IELTSMockSession` implementation in this codebase
- Email service pattern: matches existing `main/services/email.py` in this codebase

---
*Architecture research for: MockIT v1.2 Profiles & Scheduling*
*Researched: 2026-03-30*
