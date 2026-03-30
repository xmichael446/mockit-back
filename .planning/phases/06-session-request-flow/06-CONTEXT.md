# Phase 6: Session Request Flow - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Session request model with state machine, CRUD and action endpoints (submit/accept/reject/cancel), atomic session creation on accept with double-booking prevention, and extension of availability service to subtract accepted requests. Lives in `scheduling/` app.

</domain>

<decisions>
## Implementation Decisions

### Session Request Model & State Machine
- `SessionRequest` model with `Status` IntegerChoices: `PENDING=1, ACCEPTED=2, REJECTED=3, CANCELLED=4` — matches existing session model pattern
- Both candidate and examiner can cancel ACCEPTED requests (per REQ-07)
- FKs: `candidate` (FK to User), `examiner` (FK to User), `availability_slot` (FK to AvailabilitySlot), `requested_date` (DateField), `session` (FK to IELTSMockSession, null=True until accepted), `comment` (TextField, optional), `rejection_comment` (TextField, null until rejected)
- Extend `compute_available_slots()` to also subtract ACCEPTED session requests — accepted requests mark slots as taken in the calendar

### API Design & Accept Flow
- Action endpoints: `POST /api/scheduling/requests/` (create), `GET /api/scheduling/requests/` (list my requests), `POST /api/scheduling/requests/<id>/accept/`, `POST /api/scheduling/requests/<id>/reject/`, `POST /api/scheduling/requests/<id>/cancel/`
- Accept view: `select_for_update()` on the SessionRequest row, create `IELTSMockSession` with examiner+candidate, link via FK — all inside `transaction.atomic()`
- No MockPreset auto-creation on accept — examiner chooses preset at session start time
- WebSocket broadcasts: `session_request.accepted` and `session_request.rejected` events via `_broadcast()` pattern for real-time frontend updates

### Claude's Discretion
- List endpoint filtering (by status, by role)
- Validation error messages
- State transition validation method naming

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `scheduling/models.py` — AvailabilitySlot, BlockedDate models already exist
- `scheduling/services/availability.py` — `compute_available_slots()` to extend
- `session/views.py` — `_broadcast()` helper for WebSocket events
- `session/models.py` — `IELTSMockSession` model for FK reference, status state machine pattern
- `TimestampedModel` in `main/models.py` — base for new model

### Established Patterns
- State machine validation via model methods (from v1.1 `IELTSMockSession.assert_in_progress()`)
- `transaction.atomic()` + `select_for_update()` used in session scoring
- Action endpoints (e.g., `/api/sessions/<id>/start/`, `/api/sessions/<id>/end/`)
- Role checks via `_is_examiner()` / `_is_candidate()` helpers

### Integration Points
- `scheduling/models.py` — add SessionRequest model
- `scheduling/views.py` — add request views
- `scheduling/urls.py` — add request URL patterns
- `scheduling/services/availability.py` — extend to subtract accepted requests
- `session/views.py` — import `_broadcast()` pattern or use `async_to_sync(channel_layer.group_send)`

</code_context>

<specifics>
## Specific Ideas

- Accept must use `select_for_update()` to prevent concurrent accepts on the same slot (REQ-06)
- Rejection requires a `rejection_comment` (REQ-04) — validated in serializer
- The created IELTSMockSession should have status=CREATED (default), examiner and candidate set

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>
