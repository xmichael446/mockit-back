# Phase 5: Availability Scheduling - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Examiner recurring weekly availability model, blocked dates model, CRUD endpoints, computed available slots service, and is-currently-available check. All lives in the new `scheduling/` app. Depends on ExaminerProfile from Phase 4.

</domain>

<decisions>
## Implementation Decisions

### Availability Data Model
- `AvailabilitySlot` model with `day_of_week` (IntegerChoices MON=0 through SUN=6) + `start_time` (TimeField) — each row = one 1-hour window
- Serializer validation enforces `start_time` on the hour between 08:00-21:00 (end implied as start+1h) — no `end_time` field stored
- `BlockedDate` model with `examiner` FK (to User) + `date` (DateField) + optional `reason` (CharField)
- `compute_available_slots()` service function lives in `scheduling/services/availability.py`

### API Design & Slot Computation
- Standard CRUD endpoints: `/api/scheduling/availability/` (list/create), `/api/scheduling/availability/<id>/` (update/delete) — examiner-only
- BlockedDate CRUD: `/api/scheduling/blocked-dates/` and `/api/scheduling/blocked-dates/<id>/` — examiner-only
- Available slots endpoint: `GET /api/scheduling/examiners/<id>/available-slots/?week=2026-03-30` — returns full week calendar with booked/free flags for each slot (not just free slots)
- `is_currently_available` endpoint: `GET /api/scheduling/examiners/<id>/is-available/` — returns `{is_available: bool, current_slot: {...} | null}`
- All times stored in UTC; accept `timezone` query param on available-slots endpoint for display conversion

### Claude's Discretion
- Unique constraint details on AvailabilitySlot (examiner + day_of_week + start_time)
- Week calendar response format (list of day objects vs flat slot list)
- BlockedDate endpoint naming and response shape

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TimestampedModel` in `main/models.py` — base for new models
- `ExaminerProfile` in `main/models.py` — FK reference for examiner identity
- `_is_examiner(user)` helper pattern in `session/views.py` — replicate for scheduling permissions
- `main/services/email.py` — pattern for service module organization

### Established Patterns
- DRF APIView with docstrings, `Response({"detail": "..."}, status=4xx)` for errors
- Role checks via helper functions (not permissions classes for granular control)
- `session/urls.py` pattern for URL organization with clear comments
- `IELTSMockSession` model — reference for session status filtering in slot computation

### Integration Points
- `MockIT/urls.py` — add `path("api/scheduling/", include("scheduling.urls"))`
- `MockIT/settings.py` — add `"scheduling"` to INSTALLED_APPS
- `session/models.py` — `IELTSMockSession` status used to filter accepted bookings from slots
- `main/models.py` — `ExaminerProfile` FK for availability ownership

</code_context>

<specifics>
## Specific Ideas

- Available slots endpoint returns a FULL week calendar with booked/free flags, not just free slots — frontend can render a complete schedule grid
- Slot computation: recurring schedule minus accepted session bookings minus blocked dates = available slots

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>
