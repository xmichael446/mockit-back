# Phase 5: Availability Scheduling - Research

**Researched:** 2026-03-30
**Domain:** Django scheduling models, date/time arithmetic, DRF CRUD endpoints, new app scaffolding
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Availability Data Model**
- `AvailabilitySlot` model with `day_of_week` (IntegerChoices MON=0 through SUN=6) + `start_time` (TimeField) — each row = one 1-hour window
- Serializer validation enforces `start_time` on the hour between 08:00-21:00 (end implied as start+1h) — no `end_time` field stored
- `BlockedDate` model with `examiner` FK (to User) + `date` (DateField) + optional `reason` (CharField)
- `compute_available_slots()` service function lives in `scheduling/services/availability.py`

**API Design & Slot Computation**
- Standard CRUD endpoints: `/api/scheduling/availability/` (list/create), `/api/scheduling/availability/<id>/` (update/delete) — examiner-only
- BlockedDate CRUD: `/api/scheduling/blocked-dates/` and `/api/scheduling/blocked-dates/<id>/` — examiner-only
- Available slots endpoint: `GET /api/scheduling/examiners/<id>/available-slots/?week=2026-03-30` — returns full week calendar with booked/free flags for each slot (not just free slots)
- `is_currently_available` endpoint: `GET /api/scheduling/examiners/<id>/is-available/` — returns `{is_available: bool, current_slot: {...} | null}`
- All times stored in UTC; accept `timezone` query param on available-slots endpoint for display conversion

### Claude's Discretion
- Unique constraint details on AvailabilitySlot (examiner + day_of_week + start_time)
- Week calendar response format (list of day objects vs flat slot list)
- BlockedDate endpoint naming and response shape

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AVAIL-01 | Examiner can define weekly recurring availability as 1-hour windows (08:00-22:00) per day of week | AvailabilitySlot model, CRUD endpoints in scheduling/ |
| AVAIL-02 | Examiner can update/delete their recurring availability slots | PATCH/DELETE on /api/scheduling/availability/<id>/ — ownership enforced |
| AVAIL-03 | API returns computed available slots for an examiner (recurring schedule minus booked sessions) | compute_available_slots() service, GET /api/scheduling/examiners/<id>/available-slots/ |
| AVAIL-04 | API returns is_currently_available boolean for an examiner at request time | GET /api/scheduling/examiners/<id>/is-available/ using timezone.now() |
| AVAIL-05 | Examiner can block specific dates as exceptions to their recurring schedule | BlockedDate model, CRUD endpoints, used as filter in compute_available_slots() |
</phase_requirements>

---

## Summary

Phase 5 creates a brand-new `scheduling/` Django app (not yet scaffolded) with two models: `AvailabilitySlot` for recurring weekly windows and `BlockedDate` for date exceptions. A pure Python service function `compute_available_slots()` computes the full-week calendar by expanding the recurring schedule into concrete datetimes, subtracting any `IELTSMockSession` bookings (SCHEDULED or IN_PROGRESS status, examiner matches, scheduled_at falls within the slot), and subtracting any `BlockedDate` exceptions.

The project already has all necessary infrastructure: DRF APIView pattern, `IsEmailVerified` global permission, `_is_examiner()` role helper, `TimestampedModel` base class, and `ExaminerProfile` for FK reference. The `scheduling/` app must be created from scratch with `python manage.py startapp scheduling`, then wired into `INSTALLED_APPS` and `MockIT/urls.py`. Tests use `DJANGO_SETTINGS_MODULE=MockIT.settings_test` (SQLite in-memory) as established in Phase 4.

The critical design challenge is `compute_available_slots()`: it must work purely with Python datetime arithmetic on a given ISO week string (`?week=2026-03-30`). The `week` param is parsed to get the Monday of that week, then for each day (0=Mon through 6=Sun) the examiner's `AvailabilitySlot` rows are expanded to concrete UTC datetimes and compared against `IELTSMockSession.scheduled_at` to mark slots as booked.

**Primary recommendation:** Create `scheduling/` app, build both models with proper unique constraints, implement `compute_available_slots()` as a standalone service function using Python datetime arithmetic, then add APIView classes following the exact pattern from `session/views.py` and `main/views.py`.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django ORM | 5.2.11 (project) | Model definition, IntegerChoices, TimeField, DateField | Already in project |
| Django REST Framework | 3.16.1 (project) | APIView, serializers, Response | Already in project |
| Python datetime | stdlib | Timedelta, date/time arithmetic, weekday() | No external dependency |
| django.utils.timezone | builtin | timezone.now(), aware datetimes | Already used across project |
| pytz / zoneinfo | stdlib (Python 3.9+) | Timezone display conversion for ?timezone param | zoneinfo is in Python 3.9+ stdlib, no install needed |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| datetime.timedelta | stdlib | Compute week start from arbitrary date, add 1 hour | Slot boundary arithmetic |
| datetime.date.fromisoformat | stdlib | Parse `?week=2026-03-30` query param | Python 3.7+ built-in |
| zoneinfo.ZoneInfo | stdlib (3.9+) | Convert UTC slot datetimes to display timezone | Only for response formatting when ?timezone param provided |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Pure Python datetime | django-recurrence or celery beat | Overkill — weekly recurring windows are trivially computed with date arithmetic |
| zoneinfo (stdlib) | pytz | pytz is deprecated; zoneinfo is the modern replacement and is in stdlib since Python 3.9 |

**Installation:**
No new packages required. All libraries are already in `requirements.txt` or Python stdlib.

---

## Architecture Patterns

### New App Structure
```
scheduling/
├── migrations/          # auto-generated
├── services/
│   └── availability.py  # compute_available_slots() service
├── admin.py
├── apps.py
├── models.py            # AvailabilitySlot, BlockedDate
├── serializers.py       # all scheduling serializers
├── tests.py             # unit + integration tests
├── urls.py              # scheduling URL patterns
└── views.py             # CRUD + read-only endpoints
```

### Pattern 1: New App Scaffolding
**What:** Create the app with `manage.py startapp`, then wire into settings and root URL conf.
**When to use:** Any new bounded domain in this project.
**Example:**
```bash
python manage.py startapp scheduling
```
Then in `MockIT/settings.py` INSTALLED_APPS add `'scheduling.apps.SchedulingConfig'`.
Then in `MockIT/urls.py` add `path("api/scheduling/", include("scheduling.urls"))`.

### Pattern 2: Model Definition with IntegerChoices
**What:** Day-of-week uses Django IntegerChoices, mirroring the existing `SessionStatus` and `SpeakingCriterion` patterns from `session/models.py`.
**When to use:** Any enum field on a Django model.
**Example:**
```python
# Source: project pattern from session/models.py
class AvailabilitySlot(TimestampedModel):
    class DayOfWeek(models.IntegerChoices):
        MON = 0, "Monday"
        TUE = 1, "Tuesday"
        WED = 2, "Wednesday"
        THU = 3, "Thursday"
        FRI = 4, "Friday"
        SAT = 5, "Saturday"
        SUN = 6, "Sunday"

    examiner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="availability_slots",
    )
    day_of_week = models.PositiveSmallIntegerField(choices=DayOfWeek.choices)
    start_time = models.TimeField()

    class Meta:
        unique_together = [("examiner", "day_of_week", "start_time")]
        ordering = ["day_of_week", "start_time"]
```

Note: `unique_together` on `(examiner, day_of_week, start_time)` prevents duplicate windows. The database enforces this; the serializer should still validate and raise a friendly error before hitting the DB constraint.

### Pattern 3: BlockedDate Model
**What:** Simple model tying a User (examiner) to a specific calendar date.
```python
class BlockedDate(TimestampedModel):
    examiner = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="blocked_dates",
    )
    date = models.DateField()
    reason = models.CharField(max_length=255, blank=True)

    class Meta:
        unique_together = [("examiner", "date")]
        ordering = ["date"]
```

### Pattern 4: compute_available_slots() Service
**What:** Pure function that takes an `examiner_id` and a `week_date` (any date in the target week) and returns a structured week calendar.
**When to use:** Called by the available-slots view endpoint.
**Logic flow:**
1. Compute the Monday of the given week: `week_start = date - timedelta(days=date.weekday())`
2. Build 7-day range: `[week_start + timedelta(days=i) for i in range(7)]`
3. For each day, fetch examiner's `AvailabilitySlot` rows where `day_of_week == date.weekday()`
4. Each slot expands to: `slot_start = datetime.combine(day, slot.start_time, tzinfo=UTC)`, `slot_end = slot_start + timedelta(hours=1)`
5. Fetch blocking info: all `IELTSMockSession` objects where `examiner_id == examiner_id`, `status in (SCHEDULED, IN_PROGRESS)`, `scheduled_at >= week_start_dt`, `scheduled_at < week_end_dt`
6. Fetch blocked dates: all `BlockedDate` where `examiner_id == examiner_id`, `date__range=(week_start, week_end)`
7. Mark each expanded slot as `booked=True` if a session's `scheduled_at` falls within `[slot_start, slot_end)`, `blocked=True` if the day is in blocked_dates set, otherwise `available=True`
8. Return structured data

**Example:**
```python
# Source: scheduling/services/availability.py (to be created)
from datetime import date, datetime, timedelta, timezone as dt_timezone
from session.models import IELTSMockSession, SessionStatus
from scheduling.models import AvailabilitySlot, BlockedDate


def compute_available_slots(examiner_id: int, week_date: date) -> list[dict]:
    """
    Returns list of 7 day-objects covering the ISO week containing week_date.
    Each day: {"date": "2026-03-30", "slots": [{"start": "08:00", "end": "09:00", "status": "available"|"booked"|"blocked"}]}
    """
    week_start = week_date - timedelta(days=week_date.weekday())  # Monday
    week_end = week_start + timedelta(days=7)

    # Fetch all recurring slots for this examiner
    slots_qs = AvailabilitySlot.objects.filter(examiner_id=examiner_id)

    # Fetch booked sessions in this week
    booked_sessions = IELTSMockSession.objects.filter(
        examiner_id=examiner_id,
        status__in=[SessionStatus.SCHEDULED, SessionStatus.IN_PROGRESS],
        scheduled_at__date__gte=week_start,
        scheduled_at__date__lt=week_end,
    ).values_list("scheduled_at", flat=True)

    booked_starts = set(booked_sessions)

    # Fetch blocked dates in this week
    blocked_dates = set(
        BlockedDate.objects.filter(
            examiner_id=examiner_id,
            date__gte=week_start,
            date__lt=week_end,
        ).values_list("date", flat=True)
    )

    result = []
    for offset in range(7):
        current_day = week_start + timedelta(days=offset)
        day_slots = []
        for slot in slots_qs:
            if slot.day_of_week != current_day.weekday():
                continue
            slot_start_dt = datetime.combine(current_day, slot.start_time, tzinfo=dt_timezone.utc)
            slot_end_dt = slot_start_dt + timedelta(hours=1)
            if current_day in blocked_dates:
                status = "blocked"
            elif any(slot_start_dt <= bs < slot_end_dt for bs in booked_starts):
                status = "booked"
            else:
                status = "available"
            day_slots.append({
                "slot_id": slot.id,
                "start": slot.start_time.strftime("%H:%M"),
                "end": slot_end_dt.strftime("%H:%M"),
                "status": status,
            })
        day_slots.sort(key=lambda s: s["start"])
        result.append({"date": current_day.isoformat(), "slots": day_slots})
    return result
```

Note: The `booked_starts` set contains aware UTC datetimes from the DB. The comparison `slot_start_dt <= bs < slot_end_dt` works correctly as long as both are UTC-aware. Django stores DateTimeField values in UTC when `USE_TZ=True` (which is set in this project's settings).

### Pattern 5: is_currently_available Check
**What:** Determine if any of the examiner's `AvailabilitySlot` rows cover the current UTC time, the current day is not blocked, and no session occupies the current slot.
**Example:**
```python
# Source: scheduling/services/availability.py
def is_currently_available(examiner_id: int) -> dict:
    now = timezone.now()  # UTC-aware
    today = now.date()
    current_time = now.time().replace(second=0, microsecond=0)  # floor to minute

    # Check if today is blocked
    blocked = BlockedDate.objects.filter(examiner_id=examiner_id, date=today).exists()
    if blocked:
        return {"is_available": False, "current_slot": None}

    # Find a slot covering now (start_time <= current_time < start_time + 1h)
    from datetime import timedelta
    matching_slot = None
    for slot in AvailabilitySlot.objects.filter(examiner_id=examiner_id, day_of_week=today.weekday()):
        slot_end = (datetime.combine(today, slot.start_time) + timedelta(hours=1)).time()
        if slot.start_time <= current_time < slot_end:
            matching_slot = slot
            break

    if not matching_slot:
        return {"is_available": False, "current_slot": None}

    # Check for a booked session in this slot
    slot_start_dt = datetime.combine(today, matching_slot.start_time, tzinfo=dt_timezone.utc)
    slot_end_dt = slot_start_dt + timedelta(hours=1)
    booked = IELTSMockSession.objects.filter(
        examiner_id=examiner_id,
        status__in=[SessionStatus.SCHEDULED, SessionStatus.IN_PROGRESS],
        scheduled_at__gte=slot_start_dt,
        scheduled_at__lt=slot_end_dt,
    ).exists()

    if booked:
        return {"is_available": False, "current_slot": {
            "start": matching_slot.start_time.strftime("%H:%M"),
            "day_of_week": matching_slot.day_of_week,
        }}

    return {"is_available": True, "current_slot": {
        "start": matching_slot.start_time.strftime("%H:%M"),
        "day_of_week": matching_slot.day_of_week,
    }}
```

### Pattern 6: APIView CRUD (established project pattern)
**What:** All views use DRF `APIView` with explicit method handlers, `_is_examiner()` role checks, and `Response({"detail": "..."}, status=4xx)` for errors.
**When to use:** All new endpoints in this project.
**Example (from session/views.py and main/views.py):**
```python
# Source: session/views.py and main/views.py — established project pattern
from rest_framework.views import APIView
from rest_framework.response import Response
from main.models import User

def _is_examiner(user):
    return user.role == User.Role.EXAMINER

class AvailabilitySlotListCreateView(APIView):
    """
    GET  /api/scheduling/availability/    — list own slots (examiner only)
    POST /api/scheduling/availability/    — create a slot (examiner only)
    """
    def get(self, request):
        if not _is_examiner(request.user):
            return Response({"detail": "Only examiners can view availability slots."}, status=403)
        slots = AvailabilitySlot.objects.filter(examiner=request.user).order_by("day_of_week", "start_time")
        return Response(AvailabilitySlotSerializer(slots, many=True).data)

    def post(self, request):
        if not _is_examiner(request.user):
            return Response({"detail": "Only examiners can create availability slots."}, status=403)
        serializer = AvailabilitySlotSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(examiner=request.user)
        return Response(serializer.data, status=201)
```

### Pattern 7: Serializer Validation for start_time
**What:** Validate that `start_time` is exactly on the hour and between 08:00 and 21:00 (inclusive, since 21:00 + 1h = 22:00 is the stated max).
```python
# Source: scheduling/serializers.py (to be created)
from datetime import time
from rest_framework import serializers
from .models import AvailabilitySlot

class AvailabilitySlotSerializer(serializers.ModelSerializer):
    class Meta:
        model = AvailabilitySlot
        fields = ["id", "day_of_week", "start_time", "created_at"]
        read_only_fields = ["id", "created_at"]

    def validate_start_time(self, value):
        if value.minute != 0 or value.second != 0:
            raise serializers.ValidationError("start_time must be on the hour (e.g., 08:00, 14:00).")
        if not (time(8, 0) <= value <= time(21, 0)):
            raise serializers.ValidationError("start_time must be between 08:00 and 21:00 inclusive.")
        return value
```

### Anti-Patterns to Avoid
- **Storing `end_time`:** Decision is locked: only `start_time` is stored; end is always `start_time + 1h`. Do not add an `end_time` field.
- **Comparing naive datetimes with aware datetimes:** `datetime.combine(date, time)` produces a naive datetime. Always pass `tzinfo=dt_timezone.utc` to `datetime.combine()` or call `.replace(tzinfo=dt_timezone.utc)` before comparing with ORM-returned aware datetimes.
- **Using `pytz.localize()`:** The project uses `USE_TZ=True` and Django's `timezone` utilities. Use `zoneinfo.ZoneInfo` for display conversion, not `pytz` (pytz is deprecated in Python 3.9+).
- **Fetching all sessions then filtering in Python:** Always push date range filtering into the ORM query with `scheduled_at__date__gte` / `scheduled_at__date__lt` to avoid loading large result sets.
- **Forgetting ownership checks on update/delete:** Both `AvailabilitySlot` and `BlockedDate` belong to the requesting examiner. The detail view must verify `slot.examiner == request.user` before allowing update or delete.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Week-start calculation | Custom calendar math | `date - timedelta(days=date.weekday())` | weekday() returns 0=Monday, makes ISO week-start trivial |
| Timezone conversion for display | Custom UTC offset math | `zoneinfo.ZoneInfo` (stdlib) | Handles DST, historical offsets, IANA database |
| Unique slot validation | Custom duplicate check in view | `unique_together` on model + DB constraint | Database enforces atomically; serializer surfaces the error |
| Overlap detection | Interval tree / custom logic | Not needed — slots are exactly 1h on-the-hour, so `scheduled_at` in `[slot_start, slot_end)` is a simple datetime comparison | All sessions scheduled via this system will align to slot boundaries |

**Key insight:** Because slots are exactly 1 hour and always start on the hour, there is no complex overlap detection. A session "books" a slot if and only if `slot_start <= session.scheduled_at < slot_end`, which is a straightforward range query.

---

## Common Pitfalls

### Pitfall 1: Naive vs. Aware Datetime Comparison
**What goes wrong:** `datetime.combine(date, time)` returns a naive datetime. Comparing it with a Django ORM `DateTimeField` value (which is UTC-aware when `USE_TZ=True`) raises a `TypeError` or silently produces wrong results.
**Why it happens:** Python's datetime arithmetic defaults to naive unless `tzinfo` is explicitly supplied.
**How to avoid:** Always pass `tzinfo=dt_timezone.utc` to `datetime.combine()`:
```python
from datetime import datetime, timezone as dt_timezone
slot_start_dt = datetime.combine(current_day, slot.start_time, tzinfo=dt_timezone.utc)
```
**Warning signs:** `TypeError: can't compare offset-naive and offset-aware datetimes` in tests.

### Pitfall 2: weekday() vs. day_of_week Alignment
**What goes wrong:** Python's `date.weekday()` returns 0=Monday, 6=Sunday. The model stores `day_of_week` as IntegerChoices with MON=0, SUN=6. These MUST match or the slot expansion logic will silently produce wrong calendars.
**Why it happens:** Some developers expect 0=Sunday (JavaScript convention). Python uses 0=Monday.
**How to avoid:** The `DayOfWeek` IntegerChoices must be defined with MON=0 through SUN=6, matching Python's `weekday()` return value exactly. Document this in the model docstring.
**Warning signs:** Slots appearing on the wrong day of week in the calendar response.

### Pitfall 3: Missing Ownership Enforcement on Detail Views
**What goes wrong:** `GET /api/scheduling/examiners/<id>/available-slots/` is intentionally public (any authenticated user). But `PATCH /api/scheduling/availability/<id>/` must only allow the owning examiner to modify their own slot.
**Why it happens:** Forgetting to check `slot.examiner_id == request.user.id` in the detail view.
**How to avoid:** In every detail view handler (PATCH, DELETE), fetch the object with `get_object_or_404(AvailabilitySlot, pk=pk, examiner=request.user)` to combine the existence check and ownership check in one query.
**Warning signs:** An examiner can mutate another examiner's slots.

### Pitfall 4: week Query Param Parsing Errors
**What goes wrong:** `?week=bad-input` causes an unhandled exception in the view.
**Why it happens:** `date.fromisoformat()` raises `ValueError` on invalid input.
**How to avoid:** Wrap parsing in a try/except and return `Response({"detail": "Invalid week format. Use YYYY-MM-DD."}, status=400)`.
**Warning signs:** 500 errors on the available-slots endpoint with bad query params.

### Pitfall 5: Not Adding `scheduling` to INSTALLED_APPS
**What goes wrong:** Migrations are not discovered; models are not registered; `manage.py migrate` skips the new app.
**Why it happens:** New Django apps must be registered before Django recognizes them.
**How to avoid:** Add `'scheduling.apps.SchedulingConfig'` to `INSTALLED_APPS` in `MockIT/settings.py` immediately after creating the app. Verify with `python manage.py showmigrations scheduling`.

### Pitfall 6: IELTSMockSession.scheduled_at is nullable
**What goes wrong:** Some sessions have `scheduled_at=None` (sessions created without a scheduled time). Including them in the booked-slots filter would raise a database error or return wrong results.
**Why it happens:** `IELTSMockSession.scheduled_at` is `null=True, blank=True` (seen in session/models.py line 92).
**How to avoid:** Filter explicitly: `scheduled_at__isnull=False` in addition to the date range filter.

---

## Code Examples

### Week Start from Arbitrary Date
```python
# Source: Python stdlib datetime — verified behavior
from datetime import date, timedelta

def week_start(d: date) -> date:
    """Returns the Monday of the ISO week containing d."""
    return d - timedelta(days=d.weekday())  # weekday() == 0 on Monday

# Example: date(2026, 3, 30) is a Monday → returns date(2026, 3, 30)
# Example: date(2026, 4, 1) is a Wednesday → returns date(2026, 3, 30)
```

### Parsing ?week Query Param Safely
```python
# Source: scheduling/views.py (to be created)
from datetime import date

def get(self, request, pk):
    week_param = request.query_params.get("week")
    if not week_param:
        return Response({"detail": "week query param required (YYYY-MM-DD)."}, status=400)
    try:
        week_date = date.fromisoformat(week_param)
    except ValueError:
        return Response({"detail": "Invalid week format. Use YYYY-MM-DD."}, status=400)
    # ... proceed with compute_available_slots(examiner_id, week_date)
```

### Display Timezone Conversion
```python
# Source: Python stdlib zoneinfo — Python 3.9+
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError
from datetime import datetime, timezone as dt_timezone

def convert_to_display_tz(utc_dt: datetime, tz_name: str) -> datetime:
    try:
        tz = ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        return utc_dt  # Fall back to UTC on invalid tz name
    return utc_dt.astimezone(tz)
```

### URL Pattern for scheduling/ app
```python
# Source: scheduling/urls.py (to be created) — mirrors session/urls.py structure
from django.urls import path
from .views import (
    AvailabilitySlotListCreateView,
    AvailabilitySlotDetailView,
    BlockedDateListCreateView,
    BlockedDateDetailView,
    ExaminerAvailableSlotsView,
    ExaminerIsAvailableView,
)

urlpatterns = [
    # ── Availability slots ──────────────────────────────────────────────────
    path("availability/", AvailabilitySlotListCreateView.as_view(), name="availability-list-create"),
    path("availability/<int:pk>/", AvailabilitySlotDetailView.as_view(), name="availability-detail"),

    # ── Blocked dates ───────────────────────────────────────────────────────
    path("blocked-dates/", BlockedDateListCreateView.as_view(), name="blocked-date-list-create"),
    path("blocked-dates/<int:pk>/", BlockedDateDetailView.as_view(), name="blocked-date-detail"),

    # ── Read-only examiner views ─────────────────────────────────────────────
    path("examiners/<int:pk>/available-slots/", ExaminerAvailableSlotsView.as_view(), name="examiner-available-slots"),
    path("examiners/<int:pk>/is-available/", ExaminerIsAvailableView.as_view(), name="examiner-is-available"),
]
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `pytz.localize()` for timezone conversion | `zoneinfo.ZoneInfo` (stdlib) | Python 3.9 (2020) | pytz is deprecated; use zoneinfo in all new code |
| `datetime.utcnow()` | `datetime.now(timezone.utc)` | Python 3.12 deprecation warning | utcnow() returns naive datetime; now(utc) returns aware |

**Deprecated/outdated:**
- `pytz`: deprecated as of Python 3.9; `zoneinfo` is the stdlib replacement. This project doesn't use pytz; don't introduce it.
- `datetime.utcnow()`: deprecated in Python 3.12; use `datetime.now(dt_timezone.utc)` or `django.utils.timezone.now()`.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Django TestCase (unittest) — `python manage.py test` |
| Config file | `MockIT/settings_test.py` (SQLite in-memory) |
| Quick run command | `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test scheduling.tests --verbosity=1` |
| Full suite command | `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test --verbosity=1` |

### Phase Requirements to Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AVAIL-01 | Examiner can create AvailabilitySlot with valid day/time | unit | `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test scheduling.tests.TestAvailabilitySlotModel` | ❌ Wave 0 |
| AVAIL-01 | start_time outside 08:00-21:00 rejected | unit | `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test scheduling.tests.TestAvailabilitySlotValidation` | ❌ Wave 0 |
| AVAIL-02 | Examiner can update/delete own slot; cannot mutate another's | integration | `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test scheduling.tests.TestAvailabilitySlotAPI` | ❌ Wave 0 |
| AVAIL-03 | compute_available_slots returns correct free/booked/blocked flags | unit | `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test scheduling.tests.TestComputeAvailableSlots` | ❌ Wave 0 |
| AVAIL-03 | Available-slots endpoint returns full week calendar | integration | `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test scheduling.tests.TestAvailableSlotsEndpoint` | ❌ Wave 0 |
| AVAIL-04 | is_currently_available returns correct bool based on now() | unit | `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test scheduling.tests.TestIsCurrentlyAvailable` | ❌ Wave 0 |
| AVAIL-05 | BlockedDate overrides recurring slot; CRUD works | integration | `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test scheduling.tests.TestBlockedDateAPI` | ❌ Wave 0 |

### Sampling Rate
- **Per task commit:** `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test scheduling.tests --verbosity=1`
- **Per wave merge:** `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test --verbosity=1`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `scheduling/tests.py` — all test classes listed in the map above
- [ ] `scheduling/__init__.py`, `scheduling/apps.py`, `scheduling/models.py`, `scheduling/services/__init__.py`, `scheduling/services/availability.py` — app scaffold (Wave 0 creates the app before tests can run)
- [ ] Framework is already installed and configured; no new install needed

---

## Open Questions

1. **SessionRequest accepted bookings for slot computation (Phase 6 dependency)**
   - What we know: Phase 6 adds a `SessionRequest` model with PENDING/ACCEPTED/REJECTED states. An accepted `SessionRequest` represents a booking commitment.
   - What's unclear: Phase 5's `compute_available_slots()` currently filters `IELTSMockSession` (status SCHEDULED/IN_PROGRESS). Phase 6 will add `SessionRequest` as the booking object. Should Phase 5 also filter `SessionRequest` with status ACCEPTED?
   - Recommendation: Phase 5 scopes to `IELTSMockSession` only (matching REQUIREMENTS.md: "recurring schedule minus booked sessions"). Phase 6 will extend `compute_available_slots()` to also subtract `SessionRequest` accepted bookings. Document this as a known extension point.

2. **`?timezone` param scope**
   - What we know: Decision says "accept `timezone` query param on available-slots endpoint for display conversion."
   - What's unclear: Should `is-available` also accept `?timezone`? The `is_available` bool is timezone-independent; only the `current_slot.start` display time would change.
   - Recommendation: Support `?timezone` on both endpoints for consistency; convert `current_slot.start` string accordingly. If omitted, return UTC times.

---

## Sources

### Primary (HIGH confidence)
- Python stdlib `datetime` documentation — `date.weekday()`, `timedelta`, `datetime.combine()` behavior verified from stdlib specification
- Django 5.2 settings: `USE_TZ = True` confirmed in `MockIT/settings.py` — all DateTimeField values stored in UTC
- Project codebase direct read: `session/models.py` (IELTSMockSession.scheduled_at nullable), `main/models.py` (TimestampedModel, ExaminerProfile), `session/views.py` (_is_examiner pattern), `main/views.py` (APIView pattern), `MockIT/settings_test.py` (SQLite test settings)

### Secondary (MEDIUM confidence)
- Python 3.9 stdlib `zoneinfo` module — replaces pytz for timezone handling; confirmed as stdlib since 3.9
- Django docs: `unique_together` vs `UniqueConstraint` — both work; `unique_together` used throughout this project (main/models.py ScoreHistory, session/models.py SessionPart, SessionQuestion, CriterionScore) — consistent with project convention

### Tertiary (LOW confidence)
- None — all critical claims verified against project source or stdlib documentation

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries already in project or Python stdlib
- Architecture: HIGH — directly modeled on existing session/ and main/ patterns in the codebase
- Pitfalls: HIGH — verified against actual code (nullable scheduled_at, naive/aware datetime distinction)
- Service logic: HIGH — pure Python date arithmetic, no external dependencies

**Research date:** 2026-03-30
**Valid until:** 2026-06-30 (stable stack — Django 5.2, DRF 3.16, Python stdlib)
