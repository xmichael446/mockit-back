# Phase 6: Session Request Flow - Research

**Researched:** 2026-03-30
**Domain:** Django state machine model, atomic accept flow, DRF action endpoints
**Confidence:** HIGH

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Session Request Model & State Machine**
- `SessionRequest` model with `Status` IntegerChoices: `PENDING=1, ACCEPTED=2, REJECTED=3, CANCELLED=4` — matches existing session model pattern
- Both candidate and examiner can cancel ACCEPTED requests (per REQ-07)
- FKs: `candidate` (FK to User), `examiner` (FK to User), `availability_slot` (FK to AvailabilitySlot), `requested_date` (DateField), `session` (FK to IELTSMockSession, null=True until accepted), `comment` (TextField, optional), `rejection_comment` (TextField, null until rejected)
- Extend `compute_available_slots()` to also subtract ACCEPTED session requests — accepted requests mark slots as taken in the calendar

**API Design & Accept Flow**
- Action endpoints: `POST /api/scheduling/requests/` (create), `GET /api/scheduling/requests/` (list my requests), `POST /api/scheduling/requests/<id>/accept/`, `POST /api/scheduling/requests/<id>/reject/`, `POST /api/scheduling/requests/<id>/cancel/`
- Accept view: `select_for_update()` on the SessionRequest row, create `IELTSMockSession` with examiner+candidate, link via FK — all inside `transaction.atomic()`
- No MockPreset auto-creation on accept — examiner chooses preset at session start time
- WebSocket broadcasts: `session_request.accepted` and `session_request.rejected` events via `_broadcast()` pattern for real-time frontend updates

### Claude's Discretion
- List endpoint filtering (by status, by role)
- Validation error messages
- State transition validation method naming

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REQ-01 | Candidate can submit a session request for a specific valid time slot with optional comment | Submit view validates slot via `compute_available_slots()` — slot must appear as "available" |
| REQ-02 | Requested time is strictly validated against examiner's actual availability (schedule minus bookings minus exceptions) | `compute_available_slots()` already handles this; submit view calls it with examiner + requested_date, verifies slot_id is present with status="available" |
| REQ-03 | Examiner can accept a pending request (auto-creates linked IELTSMockSession) | Accept view: `select_for_update()` + `transaction.atomic()` + `IELTSMockSession.objects.create()` |
| REQ-04 | Examiner can reject a pending request with required rejection comment | Reject serializer requires `rejection_comment` (non-blank); status → REJECTED |
| REQ-05 | Session request uses state machine pattern (PENDING -> ACCEPTED/REJECTED/CANCELLED) | `SessionRequest` model methods: `assert_pending()`, `accept()`, `reject()`, `cancel()` mirroring `IELTSMockSession` patterns |
| REQ-06 | Accept flow uses select_for_update to prevent double-booking race conditions | `SessionRequest.objects.select_for_update().get(pk=pk)` inside `transaction.atomic()` — row-level lock |
| REQ-07 | Candidate or examiner can cancel an accepted session request | Cancel view allows both roles if request.candidate or request.examiner matches authenticated user |
</phase_requirements>

---

## Summary

Phase 6 adds the `SessionRequest` model to the `scheduling/` app and implements five action endpoints. The domain is well-understood Django: a simple state machine model, atomic multi-row operations, and DRF APIView action patterns that already exist elsewhere in the codebase.

The most technically critical piece is the accept flow. The accept endpoint must acquire a row-level lock (`select_for_update()`) on the `SessionRequest` row inside `transaction.atomic()`, then verify the slot is still available, create the `IELTSMockSession`, update the request status, and commit — all atomically. This prevents two concurrent accept calls from double-booking the same slot.

The availability service (`compute_available_slots`) must be extended to treat ACCEPTED session requests as "booked" so that the slot calendar shown to candidates reflects pending bookings. The extension follows the exact same pattern used for `IELTSMockSession` bookings: query ACCEPTED requests for the examiner within the week window, build a set of booked `(date, slot_id)` pairs, and mark matching slots.

**Primary recommendation:** Mirror `IELTSMockSession` state machine structure exactly. Use `transaction.atomic()` + `select_for_update()` on the accept path. Place `_broadcast()` calls AFTER `transaction.atomic()` exits (established project discipline from v1.1).

---

## Standard Stack

### Core (all already installed in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django | 5.2 | ORM, transactions, select_for_update | Project stack |
| djangorestframework | installed | APIView, serializers, ValidationError | Project stack |
| django-channels | 4.x | WebSocket broadcast via `_broadcast()` | Project stack — `async_to_sync(channel_layer.group_send)` |

No new packages required for this phase.

---

## Architecture Patterns

### Recommended Project Structure

New code lives entirely in `scheduling/`:

```
scheduling/
├── models.py               # Add SessionRequest (and Status IntegerChoices)
├── serializers.py          # Add SessionRequestSerializer, RejectSerializer
├── views.py                # Add SessionRequestListCreateView + 3 action views
├── urls.py                 # Add request URL patterns
├── services/
│   └── availability.py     # Extend compute_available_slots() — add accepted requests
└── tests.py                # New test classes for model + API
```

### Pattern 1: State Machine on the Model

Mirrors `IELTSMockSession` exactly. Guards are `can_*()` predicates; transitions call them and raise `ValidationError` on failure. Views call the transition method, then `save()`.

```python
# scheduling/models.py
from rest_framework.exceptions import ValidationError
from main.models import TimestampedModel

class SessionRequest(TimestampedModel):

    class Status(models.IntegerChoices):
        PENDING    = 1, "Pending"
        ACCEPTED   = 2, "Accepted"
        REJECTED   = 3, "Rejected"
        CANCELLED  = 4, "Cancelled"

    candidate        = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="session_requests_as_candidate")
    examiner         = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="session_requests_as_examiner")
    availability_slot = models.ForeignKey("AvailabilitySlot", on_delete=models.CASCADE, related_name="session_requests")
    requested_date   = models.DateField()
    session          = models.OneToOneField("session.IELTSMockSession", on_delete=models.SET_NULL, null=True, blank=True, related_name="session_request")
    comment          = models.TextField(blank=True)
    rejection_comment = models.TextField(blank=True)
    status           = models.PositiveSmallIntegerField(choices=Status.choices, default=Status.PENDING, db_index=True)

    class Meta:
        ordering = ["-created_at"]

    # Guards
    def can_accept(self):
        return self.status == self.Status.PENDING

    def can_reject(self):
        return self.status == self.Status.PENDING

    def can_cancel(self):
        return self.status in (self.Status.PENDING, self.Status.ACCEPTED)

    # Transitions — raise ValidationError on bad state
    def accept(self):
        if not self.can_accept():
            raise ValidationError(f"Cannot accept a request with status: {self.get_status_display()}.")
        self.status = self.Status.ACCEPTED

    def reject(self, rejection_comment: str):
        if not self.can_reject():
            raise ValidationError(f"Cannot reject a request with status: {self.get_status_display()}.")
        self.rejection_comment = rejection_comment
        self.status = self.Status.REJECTED

    def cancel(self):
        if not self.can_cancel():
            raise ValidationError(f"Cannot cancel a request with status: {self.get_status_display()}.")
        self.status = self.Status.CANCELLED
```

### Pattern 2: Atomic Accept with select_for_update

The only complex view. The row-level lock must wrap the entire read-modify-create sequence.

```python
# scheduling/views.py — AcceptRequestView
from django.db import transaction
from session.models import IELTSMockSession, SessionStatus

class AcceptRequestView(APIView):
    def post(self, request, pk):
        if not _is_examiner(request.user):
            return Response({"detail": "Only examiners can accept requests."}, status=403)

        with transaction.atomic():
            try:
                # Row-level lock prevents concurrent accepts on same row
                req = SessionRequest.objects.select_for_update().get(pk=pk, examiner=request.user)
            except SessionRequest.DoesNotExist:
                return Response({"detail": "Not found."}, status=404)

            # Validate slot is still available (ACCEPTED requests already excluded by
            # the extended compute_available_slots, but double-check under lock)
            req.accept()  # raises ValidationError if not PENDING

            session = IELTSMockSession.objects.create(
                examiner=req.examiner,
                candidate=req.candidate,
                status=SessionStatus.SCHEDULED,
                scheduled_at=_build_scheduled_at(req.requested_date, req.availability_slot.start_time),
            )
            req.session = session
            req.save(update_fields=["status", "session", "updated_at"])

        # _broadcast AFTER atomic block — prevents stale events on rollback (v1.1 discipline)
        _broadcast(session.pk, "session_request.accepted", {
            "session_request_id": req.pk,
            "session_id": session.pk,
        })
        return Response(SessionRequestSerializer(req).data)
```

**Key detail:** `_broadcast()` is called AFTER the `with transaction.atomic()` block exits. This is the established project discipline from v1.1 (STATE.md decision: "Broadcast calls placed after transaction.atomic block to prevent stale events on rollback").

### Pattern 3: Slot Validation on Submit

REQ-02 requires strict validation against actual availability. The submit view must:
1. Resolve the AvailabilitySlot from `availability_slot` FK
2. Call `compute_available_slots(examiner_id, requested_date)` for the week containing `requested_date`
3. Find the specific day matching `requested_date`
4. Find the slot with `slot_id == availability_slot.id`
5. Verify status is `"available"` — if not, return 400

```python
# In submit view or serializer validate()
from scheduling.services.availability import compute_available_slots

def _validate_slot_available(examiner_id, slot_id, requested_date):
    week_data = compute_available_slots(examiner_id, requested_date)
    target_date_str = requested_date.isoformat()
    day_data = next((d for d in week_data if d["date"] == target_date_str), None)
    if not day_data:
        raise ValidationError("Requested date not found in examiner's schedule.")
    slot_data = next((s for s in day_data["slots"] if s["slot_id"] == slot_id), None)
    if not slot_data:
        raise ValidationError("This time slot does not exist in the examiner's schedule.")
    if slot_data["status"] != "available":
        raise ValidationError(f"This slot is {slot_data['status']} and cannot be booked.")
```

### Pattern 4: Extending compute_available_slots

Add ACCEPTED session requests to the "booked" set. The logic is analogous to existing IELTSMockSession booked check.

```python
# scheduling/services/availability.py — inside compute_available_slots()

from scheduling.models import AvailabilitySlot, BlockedDate, SessionRequest

# After booked_sessions query, add:
accepted_requests = SessionRequest.objects.filter(
    examiner_id=examiner_id,
    status=SessionRequest.Status.ACCEPTED,
    requested_date__gte=week_start,
    requested_date__lt=week_end,
).values_list("availability_slot_id", "requested_date")

# Build set of (date, slot_id) pairs that are taken by accepted requests
accepted_booked = {(slot_id, req_date) for slot_id, req_date in accepted_requests}

# In the day/slot loop, add check:
elif (slot.id, current_day) in accepted_booked:
    status = "booked"
```

Note: The slot loop already iterates `slot.id` and `current_day`, so this plugs in cleanly.

### Pattern 5: List Endpoint Filtering

Candidates see their own requests. Examiners see requests addressed to them. Optional `?status=` filter.

```python
class SessionRequestListCreateView(APIView):
    def get(self, request):
        if _is_examiner(request.user):
            qs = SessionRequest.objects.filter(examiner=request.user)
        else:
            qs = SessionRequest.objects.filter(candidate=request.user)

        status_param = request.query_params.get("status")
        if status_param:
            qs = qs.filter(status=status_param)

        return Response(SessionRequestSerializer(qs, many=True).data)
```

### Anti-Patterns to Avoid

- **`_broadcast()` inside `transaction.atomic()`:** If the DB rolls back after broadcast, the frontend gets a phantom event. All broadcasts go AFTER the atomic block exits.
- **`select_for_update()` without `transaction.atomic()`:** Django raises `TransactionManagementError`. The lock MUST be inside an explicit atomic block.
- **Checking slot availability outside the lock:** Re-checking availability before saving but without the lock does not prevent races. Validation and creation must be inside the same `transaction.atomic()` that holds the lock.
- **FK to `IELTSMockSession` with `on_delete=CASCADE`:** If the session is deleted, the request record would vanish. Use `SET_NULL` so the request history is preserved.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Row-level locking | Manual status flag checks | `select_for_update()` + `transaction.atomic()` | DB-level atomicity; flag checks have TOCTOU race |
| State validation | Ad-hoc `if status != X` in views | Model transition methods (`accept()`, `reject()`) raising `ValidationError` | DRF propagates `ValidationError` from model methods — no try/except in views (v1.1 decision) |
| Availability validation | Direct DB queries in the view | `compute_available_slots()` service | Reuses blocked-date and session-booking logic already tested |
| WebSocket notifications | Direct channel layer calls in views | `_broadcast()` helper from `session/views.py` | Encapsulates group name format and `async_to_sync` pattern |

---

## Common Pitfalls

### Pitfall 1: Broadcast Inside Transaction
**What goes wrong:** `_broadcast()` called inside `with transaction.atomic()` emits a WebSocket event. If the transaction rolls back afterward (e.g., an IntegrityError on session creation), the client receives a success event for a failed operation.
**Why it happens:** `async_to_sync(channel_layer.group_send)` executes immediately, before the DB commit.
**How to avoid:** Always place `_broadcast()` calls after the `with transaction.atomic():` block exits. This is a carry-forward decision from v1.1 (STATE.md).
**Warning signs:** Any `_broadcast()` call that is indented inside a `with transaction.atomic():` block.

### Pitfall 2: select_for_update Without transaction.atomic
**What goes wrong:** `Django raises django.db.transaction.TransactionManagementError: An error occurred in the current transaction. You can't execute queries until the end of the 'atomic' block.`
**Why it happens:** `select_for_update()` requires an open transaction to hold the lock.
**How to avoid:** Always wrap `select_for_update()` inside `with transaction.atomic():`.

### Pitfall 3: Slot Availability Validated Outside the Lock
**What goes wrong:** View checks slot status before acquiring the lock. Another request is accepted between the check and the `select_for_update()` call. Both requests end up ACCEPTED for the same slot.
**Why it happens:** TOCTOU (time-of-check to time-of-use) race.
**How to avoid:** Perform all availability validation INSIDE the `transaction.atomic()` after acquiring the lock. The lock ensures no concurrent modification.

### Pitfall 4: Missing requested_date / availability_slot weekday Mismatch
**What goes wrong:** A candidate submits `requested_date=2026-04-06` (a Monday) with an `availability_slot` that belongs to Thursday. The slot exists but will never appear in the Monday data returned by `compute_available_slots`.
**Why it happens:** No cross-field validation between `requested_date.weekday()` and `availability_slot.day_of_week`.
**How to avoid:** In the submit serializer validate method, check `requested_date.weekday() == availability_slot.day_of_week`. Return 400 if mismatch.

### Pitfall 5: scheduled_at Requires UTC-aware Datetime
**What goes wrong:** `IELTSMockSession.scheduled_at` is used in `compute_available_slots` with aware-datetime comparisons. Storing a naive datetime causes comparison failures.
**Why it happens:** `datetime.combine(date, time)` produces a naive datetime. Must pass `tzinfo=dt_timezone.utc`.
**How to avoid:** Use `datetime.combine(req.requested_date, req.availability_slot.start_time, tzinfo=dt_timezone.utc)` when setting `scheduled_at`.

### Pitfall 6: Cancel Permission — Both Roles
**What goes wrong:** Cancel view only checks if `request.user == req.examiner`, silently rejecting candidate cancellations.
**Why it happens:** Copy-pasting examiner-only action pattern.
**How to avoid:** Cancel view checks `request.user in (req.examiner, req.candidate)`. Return 403 if neither.

### Pitfall 7: Duplicate Active Requests
**What goes wrong:** A candidate submits multiple PENDING requests for the same examiner/slot/date combination.
**Why it happens:** No uniqueness constraint at the model level.
**How to avoid:** Add `unique_together = [("candidate", "examiner", "availability_slot", "requested_date")]` with a filter on PENDING status, OR validate in the submit view that no PENDING/ACCEPTED request already exists for that combination. A DB-level unique constraint cannot be conditional, so handle in the view or serializer.

---

## Code Examples

### Existing select_for_update pattern in project (session/views.py line 215)

The codebase already uses `transaction.atomic()` in the start-session view:
```python
# session/views.py:215
with transaction.atomic():
    session.save(update_fields=["status", "started_at", "updated_at"])
    room_id = create_room(session.pk)
    session.video_room_id = room_id
    session.save(update_fields=["video_room_id", "updated_at"])
```
Phase 6 follow-the-same-structure, but adds `select_for_update()` on the row read.

### Existing _broadcast pattern (session/views.py)
```python
# Source: session/views.py lines 66-75
def _broadcast(session_id, event_type, data):
    """Broadcast a WebSocket event to all clients connected to this session."""
    channel_layer = get_channel_layer()
    async_to_sync(channel_layer.group_send)(
        f"session_{session_id}",
        {
            "type": "session_event",
            "data": {"type": event_type, **data},
        },
    )
```
For session_request events, the group is `session_{session_id}` (the newly created session). This means the broadcast is only useful AFTER the session is created. Both `session_request.accepted` and `session_request.rejected` events should broadcast to the newly created session group (or be omitted until the frontend connects). This needs a decision — see Open Questions.

### Existing state machine pattern (session/models.py)
```python
# Source: session/models.py lines 159-163
def assert_in_progress(self):
    if self.status != SessionStatus.IN_PROGRESS:
        raise ValidationError(
            f"Session is not in progress. Current status: {self.get_status_display()}."
        )
```
SessionRequest transition methods follow this same raise-ValidationError pattern.

### Test fixture pattern (scheduling/tests.py)
```python
# All test classes follow this setUp pattern:
self.examiner = User.objects.create_user(
    username="examiner1", password="testpass123",
    role=User.Role.EXAMINER, is_verified=True,  # is_verified=True required (Phase 04 decision)
)
self.examiner_token = Token.objects.create(user=self.examiner)
self.client = APIClient()

def _auth(self, token):
    self.client.credentials(HTTP_AUTHORIZATION=f"Token {token.key}")
```
Test run command: `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test scheduling`

---

## Integration Points — Confirmed

| File | Change |
|------|--------|
| `scheduling/models.py` | Add `SessionRequest` model with `Status` IntegerChoices |
| `scheduling/serializers.py` | Add `SessionRequestSerializer`, `SessionRequestRejectSerializer` |
| `scheduling/views.py` | Add `SessionRequestListCreateView`, `AcceptRequestView`, `RejectRequestView`, `CancelRequestView` |
| `scheduling/urls.py` | Add 5 URL patterns for request endpoints |
| `scheduling/services/availability.py` | Extend `compute_available_slots()` to include ACCEPTED requests in booked set |
| `scheduling/tests.py` | Add `TestSessionRequestModel`, `TestSessionRequestAPI` classes |

**Import note:** `_broadcast()` is defined in `session/views.py`. The scheduling views should either import it directly (`from session.views import _broadcast`) or duplicate the two-line call. Direct import is cleaner but creates a cross-app dependency. Given the broadcast helper is a pure utility (no session model dependency), importing it is acceptable — or it can be moved to a shared `utils.py`.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Django TestCase (stdlib) |
| Config file | `MockIT/settings_test.py` (SQLite in-memory) |
| Quick run command | `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test scheduling.tests.TestSessionRequestAPI` |
| Full suite command | `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test scheduling` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REQ-01 | Candidate submits request with valid slot + optional comment | integration | `python manage.py test scheduling.tests.TestSessionRequestAPI.test_submit_request` | Wave 0 |
| REQ-02 | Submit rejected if slot is blocked/booked | integration | `python manage.py test scheduling.tests.TestSessionRequestAPI.test_submit_invalid_slot` | Wave 0 |
| REQ-03 | Accept creates IELTSMockSession, links FK, status→ACCEPTED | integration | `python manage.py test scheduling.tests.TestSessionRequestAPI.test_accept_creates_session` | Wave 0 |
| REQ-04 | Reject requires rejection_comment; missing → 400 | integration | `python manage.py test scheduling.tests.TestSessionRequestAPI.test_reject_requires_comment` | Wave 0 |
| REQ-05 | State machine: double-accept returns 400 | unit | `python manage.py test scheduling.tests.TestSessionRequestModel.test_double_accept_raises` | Wave 0 |
| REQ-06 | concurrent accept prevented (serialized via select_for_update) | integration | `python manage.py test scheduling.tests.TestSessionRequestAPI.test_concurrent_accept_prevention` | Wave 0 |
| REQ-07 | Candidate can cancel ACCEPTED request; examiner can cancel ACCEPTED request | integration | `python manage.py test scheduling.tests.TestSessionRequestAPI.test_cancel_by_candidate` | Wave 0 |

### Sampling Rate
- **Per task commit:** `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test scheduling`
- **Per wave merge:** `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `scheduling/tests.py` — add `TestSessionRequestModel` and `TestSessionRequestAPI` classes (file exists but needs new test classes)

---

## Open Questions

1. **_broadcast target group for session_request events**
   - What we know: `_broadcast(session_id, ...)` broadcasts to group `session_{session_id}`. For `session_request.accepted`, the session is created in the same accept call, so broadcasting to the new session's group works. For `session_request.rejected`, there is no session — broadcasting to `session_{request_id}` or a different group format would be needed.
   - What's unclear: The CONTEXT.md says broadcasts use `_broadcast()` pattern but doesn't specify the group name for request-level events. The rejected event has no session to attach to.
   - Recommendation: For `session_request.accepted`, broadcast to the new `session_{session.pk}` group. For `session_request.rejected`, either skip the broadcast (frontend polls the request detail endpoint) or use a user-level channel group (`user_{candidate_id}`). Decide during planning — the simpler option is to skip the rejected broadcast in Phase 6 and add user-level channels in a later phase.

2. **Duplicate pending request prevention strategy**
   - What we know: No `unique_together` can be conditional (SQLite/PostgreSQL). The constraint must be enforced in application code.
   - What's unclear: Whether to validate in the serializer (needs examiner context) or the view.
   - Recommendation: Validate in the submit view after serializer.is_valid(): query for existing PENDING or ACCEPTED request for the same candidate/examiner/slot/date combination and return 400 if found.

---

## Sources

### Primary (HIGH confidence)
- Codebase: `scheduling/models.py`, `scheduling/services/availability.py`, `scheduling/views.py`, `scheduling/tests.py` — verified directly
- Codebase: `session/models.py` — verified state machine pattern
- Codebase: `session/views.py` — verified `_broadcast()` helper, `transaction.atomic()` usage
- Codebase: `.planning/STATE.md` — verified carry-forward decisions

### Secondary (MEDIUM confidence)
- Django docs: `select_for_update()` requires `transaction.atomic()` — standard Django ORM behavior (HIGH, standard library feature)
- Django docs: `ValidationError` from model methods propagates through DRF — confirmed by STATE.md entry "[Phase 02]: ValidationError from model methods propagates through DRF"

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — no new packages; all libraries already in use
- Architecture patterns: HIGH — directly derived from existing codebase patterns
- Pitfalls: HIGH — most derived from actual project decisions in STATE.md and code inspection
- Open questions: LOW — require design decisions, not research

**Research date:** 2026-03-30
**Valid until:** 2026-04-30 (stable Django/DRF — not fast-moving)
