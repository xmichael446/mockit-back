# Phase 2: Session Hardening - Research

**Researched:** 2026-03-27
**Domain:** Django model state machines, transaction atomicity, cryptographic token generation
**Confidence:** HIGH

## Summary

Phase 2 involves four tightly coupled changes to `session/models.py` and `session/views.py`. The changes are: (1) centralizing all status validation into model methods on `IELTSMockSession`, (2) replacing the insecure invite token generator with a `secrets`-based letter-only format, (3) wrapping the multi-step session start operation in `transaction.atomic()`, and (4) enforcing preset immutability via `MockPreset.save()` and `delete()` overrides.

The codebase audit confirms exactly 10 occurrences of `if session.status != SessionStatus.X` in `session/views.py` and 1 in `main/serializers.py`. These are all candidates for replacement. The session start flow is the only operation with a meaningful atomicity risk — it performs status update + external room creation (100ms API) in sequence with no rollback path. The key design constraint is that `_broadcast()` calls must stay outside the transaction boundary because they push to WebSocket clients and should never broadcast uncommitted state.

There is no existing test infrastructure beyond stub files (`session/tests.py` is empty). All validation for this phase will be manual.

**Primary recommendation:** Implement state machine methods directly on `IELTSMockSession` as described in CONTEXT.md. Use `ValidationError` from `rest_framework.exceptions` (already imported in models.py) for transition errors — views catch these as 400 automatically through DRF's exception handler.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**State Machine Design:**
- State machine methods live on the IELTSMockSession model — `can_start()`, `can_end()`, `can_join()`, `can_ask_question()` etc.
- Invalid transitions raise `ValidationError` with a descriptive message — consistent with DRF, views catch and return 400
- Transition methods validate AND perform the status change — e.g., `start()` checks `can_start()` then sets `status = IN_PROGRESS` and `started_at`
- Cover all session-level status checks: start, end, join, ask_question, start_part, end_part — eliminate all scattered `if session.status != ...` checks from views

**Invite Token Format:**
- Format: `xxx-yyyy` (3 lowercase letters + dash + 4 lowercase letters) — matches Google Meet style
- Character set: lowercase a-z only, no digits
- Use `secrets` module for cryptographic security (e.g., `secrets.choice(string.ascii_lowercase)`)
- No migration for existing tokens — only new sessions get the new format, existing tokens continue to work
- Update max_length on model field if needed (current is 9, new format is 8 chars — fits)

**Transactions & Preset Immutability:**
- Wrap session start in `transaction.atomic()` — the multi-step operation (status update + room creation + token generation) that risks partial state
- On room creation failure: rollback — status stays SCHEDULED, no partial state in database
- Enforce preset immutability via model-level `save()` override on MockPreset — check `self.pk` and whether any IELTSMockSession references this preset
- Block preset deletion too if sessions exist — consistent with immutability rule (override `delete()`)

### Claude's Discretion

- Exact method signatures and internal logic flow
- How to handle the `_broadcast()` calls relative to transaction boundaries
- Whether to add `select_for_update()` for concurrent access protection
- Naming of helper methods for status validation

### Deferred Ideas (OUT OF SCOPE)

None — discussion stayed within phase scope
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| REF-01 | Session status checks extracted into model methods (can_start, can_end, can_ask_question, etc.) | 10 occurrences in views.py + 1 in main/serializers.py mapped; model already imports ValidationError |
| REF-03 | Invite token uses letter-only format like Google Meet (e.g. xyz-abcd) | `_generate_invite_token()` at models.py:14 is the single replacement target; `secrets` module is stdlib |
| EDGE-01 | Multi-step operations wrapped in transaction.atomic() (session start) | `StartSessionView.post()` at views.py:196-238 is the sole target; room creation via HMS API is the external call that can fail |
| EDGE-04 | Preset cannot be modified after a session has been created from it | No preset update/delete views currently exist — enforcement belongs in `MockPreset.save()` and `MockPreset.delete()` overrides |
</phase_requirements>

---

## Standard Stack

### Core

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| `django.db.transaction` | Django 5.2 (stdlib) | `transaction.atomic()` context manager and decorator | Built-in Django; zero extra dependencies |
| `secrets` | Python 3.11 (stdlib) | Cryptographically strong random choices | PEP 506 standard for security-sensitive randomness; replaces `random.choices()` |
| `rest_framework.exceptions.ValidationError` | DRF (already installed) | Raising errors from model methods that views convert to 400 | Already imported in session/models.py; DRF exception handler converts it automatically |
| `string` | Python 3.11 (stdlib) | `string.ascii_lowercase` character set | Already imported in session/models.py |

### No New Dependencies

This phase adds zero new packages. All required tools (`transaction`, `secrets`, `ValidationError`) are already present in the environment.

**Installation:**
```bash
# No new packages needed
```

---

## Architecture Patterns

### Recommended Project Structure

No new files. Changes are confined to:
```
session/
├── models.py     # Add state machine methods to IELTSMockSession, override MockPreset.save()/delete()
└── views.py      # Replace inline status checks with model method calls
main/
└── serializers.py  # Replace 1 inline status check with model method call
```

### Pattern 1: State Machine on Django Model

**What:** Validation and transition logic lives on the model. Views call `session.start()`, not `if session.status != ...`.

**When to use:** When multiple views perform the same status check, or when the check carries side effects (setting `started_at`, etc.).

**Example — guard + transition method pattern:**
```python
# session/models.py
from rest_framework.exceptions import ValidationError
from django.utils import timezone

class IELTSMockSession(TimestampedModel):
    # ... existing fields ...

    def can_start(self):
        return self.status == SessionStatus.SCHEDULED and self.candidate is not None

    def start(self):
        if not self.can_start():
            raise ValidationError(
                f"Session cannot be started. Current status: {self.get_status_display()}."
            )
        self.status = SessionStatus.IN_PROGRESS
        self.started_at = timezone.now()
        # Caller is responsible for calling .save() with update_fields
```

**In the view:**
```python
# session/views.py
def post(self, request, pk):
    session = get_session_or_404(pk)
    # ... permission check ...
    try:
        session.start()   # raises ValidationError if invalid
    except ValidationError as exc:
        return Response({"detail": exc.detail}, status=400)
    session.save(update_fields=["status", "started_at", "updated_at"])
```

**Alternative — let DRF handle it automatically:**

DRF's default exception handler converts `rest_framework.exceptions.ValidationError` to a 400 response automatically in any `APIView`. So the try/except in the view is optional — raising from the model method is sufficient if you trust DRF's handler.

**Recommended:** Raise from the model, let DRF handle the 400 conversion. This keeps views clean.

### Pattern 2: transaction.atomic() for Multi-Step Session Start

**What:** Wrap status update + external API call in a transaction. If the external call fails, the transaction rolls back the DB write.

**When to use:** Any operation where a DB write and a non-DB side effect must be atomic from the DB's perspective.

**Key constraint:** `_broadcast()` must be called AFTER the `with transaction.atomic()` block exits successfully. Broadcasting inside the block would send WebSocket events for state that might be rolled back.

**Example:**
```python
from django.db import transaction

def post(self, request, pk):
    session = get_session_or_404(pk)
    # ... permission check ...
    session.start()  # validates, sets fields in memory

    with transaction.atomic():
        session.save(update_fields=["status", "started_at", "updated_at"])
        try:
            room_id = create_room(session.pk)
        except Exception as exc:
            raise  # causes atomic block to roll back the save above

    # Only reached if transaction committed successfully
    session.video_room_id = room_id
    session.save(update_fields=["video_room_id", "updated_at"])
    _broadcast(pk, "session.started", {...})
```

**Note on room_id save:** The `video_room_id` save after the atomic block is intentionally outside it. If this second save fails (very unlikely), the session is IN_PROGRESS without a room_id — the existing `if not session.video_room_id` guard in `JoinSessionView` handles this gracefully by returning 400. This is an acceptable residual risk given the low probability.

**Simpler alternative** (all in one atomic block):
```python
with transaction.atomic():
    session.save(update_fields=["status", "started_at", "updated_at"])
    room_id = create_room(session.pk)  # raises on failure → rollback
    session.video_room_id = room_id
    session.save(update_fields=["video_room_id", "updated_at"])

_broadcast(pk, "session.started", {...})  # AFTER block
```

This is cleaner and should be preferred. The entire DB state is committed together before broadcasting.

### Pattern 3: Preset Immutability via save()/delete() Override

**What:** Override `MockPreset.save()` and `MockPreset.delete()` to block mutations once sessions exist.

**When to use:** When enforcement must happen at the model layer regardless of which code path triggers the save.

**Example:**
```python
class MockPreset(TimestampedModel):
    # ... existing fields + clean() ...

    def save(self, *args, **kwargs):
        if self.pk and self.sessions.exists():
            raise ValidationError(
                "Cannot modify a preset that has sessions created from it."
            )
        super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.sessions.exists():
            raise ValidationError(
                "Cannot delete a preset that has sessions created from it."
            )
        super().delete(*args, **kwargs)
```

**Important:** DRF's `APIView` does not automatically catch `rest_framework.exceptions.ValidationError` raised from `Model.save()` — it only catches it during serializer validation. The view must catch it explicitly, or use `django.core.exceptions.ValidationError` which DRF also handles.

**Recommendation:** Use `rest_framework.exceptions.ValidationError` (already imported in models.py) and ensure view code wraps `preset.save()` in a try/except, or use DRF's `perform_update()`/`perform_destroy()` hooks if a ViewSet is used. Since this project uses `APIView`, the simplest path is to check at the view layer before calling save — but the model-level guard is still valuable as a belt-and-suspenders defense.

**Practical approach for preset endpoints:** There are currently no PUT/PATCH/DELETE endpoints for presets (only GET list and POST create in `MockPresetListCreateView`). The immutability enforcement in `save()`/`delete()` will protect against future endpoints and admin panel mutations. For Phase 2, since no update endpoint exists, the model override is the primary (and only) needed enforcement mechanism.

### Pattern 4: New Invite Token Format

**What:** Replace `_generate_invite_token()` with a `secrets`-based implementation producing `xxx-yyyy` (letters only).

**Example:**
```python
import secrets
import string

def _generate_invite_token():
    """Generate a Google Meet-style token: 3 letters + dash + 4 letters."""
    letters = string.ascii_lowercase
    part1 = "".join(secrets.choice(letters) for _ in range(3))
    part2 = "".join(secrets.choice(letters) for _ in range(4))
    return f"{part1}-{part2}"
```

**Entropy:** 26^7 ≈ 8 billion combinations. The `unique=True` constraint on `invite_token` handles the negligible collision probability.

**Field change:** `invite_token = models.CharField(max_length=9, ...)` — current max_length is 9, new token is 8 chars. No field migration needed.

**`max_length` in serializer:** `main/serializers.py` line 75 has `invite_token = serializers.CharField(max_length=9)`. This remains valid since 8 < 9.

### Anti-Patterns to Avoid

- **Broadcasting inside transaction.atomic():** Sends WebSocket events for state that may be rolled back. Always broadcast after the transaction commits.
- **Using `random.choices()` for security-sensitive tokens:** Not cryptographically secure. `secrets.choice()` is required.
- **Raising `django.core.exceptions.ValidationError` from model methods called by views:** DRF does not auto-convert Django's ValidationError to a 400 (it will become a 500). Use `rest_framework.exceptions.ValidationError` consistently throughout.
- **Putting state machine logic only in can_X() methods:** The transition method (e.g., `start()`) must also perform the state change, otherwise callers must duplicate field-setting logic.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Transaction rollback on external API failure | Custom try/except with manual revert | `transaction.atomic()` context manager | Handles rollback automatically, even for nested operations |
| Cryptographic randomness | `random.choices()` with more characters | `secrets.choice()` | `random` is not cryptographically secure (predictable seed) |
| 400 error response from model validation | Manual `if/return Response(...)` in every view | `raise ValidationError(...)` + DRF exception handler | One raise covers all call sites |

---

## Common Pitfalls

### Pitfall 1: Broadcasting Inside a Transaction

**What goes wrong:** `_broadcast()` sends a WebSocket event while the transaction is still open. If the transaction rolls back (e.g., due to an exception after the broadcast), clients receive an event for state that was never committed to the database.

**Why it happens:** Developers place `_broadcast()` at the end of the view method without noticing it's inside the `with transaction.atomic():` block.

**How to avoid:** Always place `_broadcast()` calls after the `with transaction.atomic():` block exits. In `StartSessionView`, this means the broadcast happens after both the status save and the room creation have committed.

**Warning signs:** `_broadcast()` call appears inside the indentation of `with transaction.atomic():`.

### Pitfall 2: ValidationError Import Mismatch

**What goes wrong:** `models.py` raises `rest_framework.exceptions.ValidationError`, but a view or caller imports `django.core.exceptions.ValidationError` and catches the wrong type, or vice versa. DRF's auto-handler only catches `rest_framework.exceptions.ValidationError`.

**Why it happens:** Both Django and DRF have a `ValidationError` class with the same name.

**How to avoid:** `session/models.py` already imports `from rest_framework.exceptions import ValidationError` at line 8. Keep all `ValidationError` raises in this file consistent with that import. Do not mix in `django.core.exceptions.ValidationError`.

**Warning signs:** `from django.core.exceptions import ValidationError` appearing in models.py.

### Pitfall 3: Forgetting save() in Transition Methods

**What goes wrong:** Transition method sets fields in memory but does not save. Caller forgets to call `session.save()`. Status change is lost.

**Why it happens:** The decision to have transition methods validate AND set fields (but let the caller save) requires discipline at every call site.

**How to avoid:** Document clearly that transition methods set in-memory state only. Alternatively, have transition methods call `save(update_fields=[...])` themselves — but this is harder to compose with `transaction.atomic()` in the view.

**Recommendation:** Transition methods set fields in memory only. Views call `session.save(update_fields=[...])` explicitly. The pattern is explicit and consistent with existing view code.

**Warning signs:** View calls `session.start()` but has no subsequent `session.save(...)` call.

### Pitfall 4: select_for_update() Scope

**What goes wrong:** Two simultaneous requests both read a SCHEDULED session and both attempt to start it. Without row-level locking, both might pass the status check before either commits.

**Why it happens:** No locking on the session row fetch before status validation.

**How to avoid:** This is listed as Claude's discretion. Given the system's single-examiner model (only the session examiner can start a session), concurrent starts by two different users are impossible. The risk is negligible without `select_for_update()`. Only add it if there's evidence of concurrent access problems.

**Recommendation:** Skip `select_for_update()` for Phase 2. The single-examiner invariant makes concurrent start impossible.

### Pitfall 5: Preset immutability breaking M2M updates

**What goes wrong:** `MockPreset.save()` is called by Django when M2M relations (part_1, part_2, part_3) are updated — but actually, M2M changes do not trigger `save()`. They use `add()`, `set()`, `remove()` on the M2M manager directly.

**Why it happens:** Developers assume that changing a M2M field triggers `save()` on the parent model.

**How to avoid:** The `save()` override correctly protects against updating the preset's non-M2M fields (name). M2M changes via the API would only occur if a PUT/PATCH endpoint is added, which it currently is not. The `save()` override is still correct for its purpose.

**Note:** If future phases add a preset update endpoint that sends M2M data, the serializer's `update()` method will need to explicitly handle this — but that is out of scope for Phase 2.

---

## Code Examples

### Complete State Machine Method Set

```python
# session/models.py — IELTSMockSession additions

def can_start(self):
    return self.status == SessionStatus.SCHEDULED and self.candidate is not None

def can_end(self):
    return self.status == SessionStatus.IN_PROGRESS

def can_join(self):
    return self.status == SessionStatus.IN_PROGRESS

def can_ask_question(self):
    return self.status == SessionStatus.IN_PROGRESS

def can_start_part(self):
    return self.status == SessionStatus.IN_PROGRESS

def can_end_part(self):
    return self.status == SessionStatus.IN_PROGRESS

def start(self):
    if not self.can_start():
        if self.candidate is None:
            raise ValidationError(
                "Cannot start session: no candidate has accepted the invite yet."
            )
        raise ValidationError(
            f"Session cannot be started. Current status: {self.get_status_display()}."
        )
    self.status = SessionStatus.IN_PROGRESS
    self.started_at = timezone.now()

def end(self):
    if not self.can_end():
        raise ValidationError(
            f"Session is not in progress. Current status: {self.get_status_display()}."
        )
    self.status = SessionStatus.COMPLETED
    self.ended_at = timezone.now()
```

### Refactored StartSessionView with transaction.atomic()

```python
# session/views.py — StartSessionView.post()

def post(self, request, pk):
    try:
        session = _session_qs().get(pk=pk)
    except IELTSMockSession.DoesNotExist:
        return Response({"detail": "Not found."}, status=404)

    if request.user != session.examiner:
        return Response({"detail": "Only the session examiner can start the session."}, status=403)

    session.start()  # raises ValidationError → DRF converts to 400

    try:
        with transaction.atomic():
            session.save(update_fields=["status", "started_at", "updated_at"])
            room_id = create_room(session.pk)
            session.video_room_id = room_id
            session.save(update_fields=["video_room_id", "updated_at"])
    except Exception as exc:
        if not isinstance(exc, ValidationError):
            return Response({"detail": f"Failed to create video room: {exc}"}, status=502)
        raise

    hms_token = generate_app_token(room_id, request.user.pk, settings.HMS_EXAMINER_ROLE)

    _broadcast(pk, "session.started", {
        "session_id": pk,
        "started_at": session.started_at.isoformat(),
    })

    session = _session_qs().get(pk=session.pk)
    data = SessionSerializer(session).data
    data["hms_token"] = hms_token
    data["room_id"] = room_id
    return Response(data)
```

### Simplified View Pattern (for IN_PROGRESS checks)

For all views that only check `if session.status != SessionStatus.IN_PROGRESS`, the replacement is one line:

```python
# Before
if session.status != SessionStatus.IN_PROGRESS:
    return Response({"detail": "Session is not in progress."}, status=400)

# After — DRF exception handler converts ValidationError to 400 automatically
session.assert_in_progress()  # or: session.end() / session.can_ask_question() etc.
```

Where `assert_in_progress()` is a convenience guard:

```python
def assert_in_progress(self):
    if self.status != SessionStatus.IN_PROGRESS:
        raise ValidationError(
            f"Session is not in progress. Current status: {self.get_status_display()}."
        )
```

This keeps views clean without requiring try/except at each call site.

### Serializer Status Check Replacement

```python
# main/serializers.py — validate_invite_token(), line 87
# Before:
if session.status != SessionStatus.SCHEDULED:
    raise serializers.ValidationError(...)

# After:
if not session.status == SessionStatus.SCHEDULED:
    raise serializers.ValidationError(
        f"Session is not accepting guests (status: {session.get_status_display()})."
    )
```

Since `AcceptInviteSerializer` is doing its own validation (not calling a model method), the cleanest approach is to add a `can_accept_invite()` method to the model and call it from the serializer. This keeps the status logic in one place.

---

## Status Check Inventory (All Locations)

All 11 inline status checks to replace:

| File | Line | Context | Replacement Method |
|------|------|---------|-------------------|
| session/views.py | 205 | StartSessionView — SCHEDULED check | `session.start()` |
| session/views.py | 257 | JoinSessionView — IN_PROGRESS check | `session.assert_in_progress()` or `can_join()` |
| session/views.py | 292 | EndSessionView — IN_PROGRESS check | `session.end()` |
| session/views.py | 350 | SessionPartView.post — IN_PROGRESS check | `session.assert_in_progress()` |
| session/views.py | 391 | EndSessionPartView — IN_PROGRESS check | `session.assert_in_progress()` |
| session/views.py | 501 | AskQuestionView — IN_PROGRESS check | `session.assert_in_progress()` |
| session/views.py | 601 | AnswerStartView — IN_PROGRESS check | `session.assert_in_progress()` |
| session/views.py | 642 | EndQuestionView — IN_PROGRESS check | `session.assert_in_progress()` |
| session/views.py | 686 | AskFollowUpView — IN_PROGRESS check | `session.assert_in_progress()` |
| session/views.py | 740 | EndFollowUpView — IN_PROGRESS check | `session.assert_in_progress()` |
| main/serializers.py | 87 | AcceptInviteSerializer — SCHEDULED check | `session.can_accept_invite()` |

---

## Open Questions

1. **Error message format consistency**
   - What we know: Views currently return `{"detail": "..."}` for status errors. DRF's ValidationError can return either a string or a list/dict under the `detail` key.
   - What's unclear: Whether the frontend expects a string at `detail` or can handle a list.
   - Recommendation: Raise `ValidationError("string message")` (not `ValidationError({"field": "msg"})`), which produces `{"detail": "string message"}` — consistent with current view behavior.

2. **select_for_update() for session start**
   - What we know: Concurrent starts are impossible due to single-examiner model.
   - What's unclear: Whether to add it anyway for correctness.
   - Recommendation: Skip for Phase 2. Single-examiner invariant makes this unnecessary.

---

## Validation Architecture

Config has no `workflow.nyquist_validation` key — treating as enabled.

### Test Framework

| Property | Value |
|----------|-------|
| Framework | Django TestCase (built-in, no extra install needed) |
| Config file | None — `python manage.py test` discovers tests automatically |
| Quick run command | `python manage.py test session.tests` |
| Full suite command | `python manage.py test` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| REF-01 | `session.start()` raises ValidationError when status is not SCHEDULED | unit | `python manage.py test session.tests.SessionStateMachineTests.test_start_invalid_status` | Wave 0 |
| REF-01 | `session.end()` raises ValidationError when status is not IN_PROGRESS | unit | `python manage.py test session.tests.SessionStateMachineTests.test_end_invalid_status` | Wave 0 |
| REF-01 | `session.assert_in_progress()` raises ValidationError for non-IN_PROGRESS sessions | unit | `python manage.py test session.tests.SessionStateMachineTests.test_assert_in_progress` | Wave 0 |
| REF-01 | No inline `if session.status !=` remains in views.py | code audit | (manual grep verification) | N/A — manual |
| REF-03 | `_generate_invite_token()` returns string matching `^[a-z]{3}-[a-z]{4}$` | unit | `python manage.py test session.tests.InviteTokenTests.test_token_format` | Wave 0 |
| REF-03 | Token uses only `secrets` module (no `random`) | code audit | (manual inspection) | N/A — manual |
| EDGE-01 | Session start rolls back status if `create_room()` raises | unit | `python manage.py test session.tests.SessionStartTransactionTests.test_rollback_on_room_failure` | Wave 0 |
| EDGE-01 | `_broadcast()` is not called when room creation fails | unit | `python manage.py test session.tests.SessionStartTransactionTests.test_no_broadcast_on_failure` | Wave 0 |
| EDGE-04 | `MockPreset.save()` raises ValidationError when sessions exist | unit | `python manage.py test session.tests.PresetImmutabilityTests.test_save_blocked_with_sessions` | Wave 0 |
| EDGE-04 | `MockPreset.delete()` raises ValidationError when sessions exist | unit | `python manage.py test session.tests.PresetImmutabilityTests.test_delete_blocked_with_sessions` | Wave 0 |

### Sampling Rate

- **Per task commit:** `python manage.py test session.tests`
- **Per wave merge:** `python manage.py test`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps

- [ ] `session/tests.py` — `SessionStateMachineTests` class covering REF-01
- [ ] `session/tests.py` — `InviteTokenTests` class covering REF-03
- [ ] `session/tests.py` — `SessionStartTransactionTests` class covering EDGE-01 (requires `unittest.mock.patch` for `create_room`)
- [ ] `session/tests.py` — `PresetImmutabilityTests` class covering EDGE-04

No framework install needed — Django TestCase is already available.

---

## Sources

### Primary (HIGH confidence)

- Django 5.2 official docs — `transaction.atomic()` behavior: https://docs.djangoproject.com/en/5.2/topics/db/transactions/#controlling-transactions-explicitly
- Python 3.11 stdlib — `secrets` module: https://docs.python.org/3/library/secrets.html
- DRF source — exception handler behavior: `rest_framework.views.exception_handler` converts `ValidationError` to 400 automatically
- Direct codebase inspection — `session/models.py`, `session/views.py` (line numbers verified above)

### Secondary (MEDIUM confidence)

- DRF docs — exception handling: https://www.django-rest-framework.org/api-guide/exceptions/

### Tertiary (LOW confidence)

None — all findings are based on direct code inspection or stdlib documentation.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all tools are stdlib or already installed
- Architecture: HIGH — patterns derived from direct codebase inspection + official Django/DRF docs
- Pitfalls: HIGH — derived from direct analysis of the existing code structure

**Research date:** 2026-03-27
**Valid until:** 2026-09-27 (Django/DRF APIs in this area are highly stable)
