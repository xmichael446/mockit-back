# Sessions

### GET /api/sessions/
Returns sessions where the current user is examiner or candidate.
Query params: `?status=1` (1=scheduled, 2=in_progress, 3=completed, 4=cancelled)
```json
[
  {
    "id": 1,
    "examiner": { "id": 1, "username": "...", "role": 1, ... },
    "candidate": null,
    "preset": { ... },
    "status": 1,
    "status_label": "Scheduled",
    "invite_token": "uuid-string",
    "invite_expires_at": "2024-01-08T00:00:00Z",
    "invite_accepted_at": null,
    "scheduled_at": "2024-01-05T14:00:00Z",
    "started_at": null,
    "ended_at": null,
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

### POST /api/sessions/
Examiner only.
```json
// Request
{ "preset": 1, "scheduled_at": "2024-01-05T14:00:00Z" }
// preset is optional (null allowed)
// Response 201 — same shape as session object above
```

`invite_expires_at` is set to **30 minutes after session creation**. The invite token becomes invalid after this window regardless of `scheduled_at`.

Errors:
- `403` — `"Only examiners can create sessions."` | `"Session limit reached. You can have at most N sessions."`
- `400` — `"scheduled_at must be in the future."`

### GET /api/sessions/<id>/
Returns the session object. User must be examiner or candidate.

Errors:
- `404` — `"Not found."`
- `403` — `"You are not a participant of this session."`

### POST /api/sessions/accept-invite/
Candidate only. Accepts an invite token. The token expires **30 minutes after the session was created** — candidates must accept within this window.
```json
// Request
{ "token": "uuid-string" }
// Response 200 — session object with candidate populated
```

Errors:
- `403` — `"Only candidates can accept invites."`
- `400` — `"Invalid invite token."` | `"Session is not accepting invitations (status: ...)."` | `"This invite has already been accepted."` | `"This invite has expired."`

### POST /api/sessions/<id>/start/
Examiner only. Session must be SCHEDULED. Candidate must have accepted invite. Current time must be at or after `scheduled_at`.
Creates the 100ms video room. Sets status to IN_PROGRESS.
```json
// Response 200
{
  ...session object...,
  "hms_token": "eyJhbG..."  // use this to join the 100ms room
}
// Broadcasts WS event: session.started
```

Errors:
- `403` — `"Only the session examiner can start the session."`
- `400` — `"Cannot start session: no candidate has accepted the invite yet."` | `"Cannot start session before the scheduled time."` | `"Session cannot be started. Current status: ..."`
- `502` — `"Failed to create video room: ..."`

### POST /api/sessions/<id>/join/
Any participant. Session must be IN_PROGRESS. Returns a fresh 100ms token.
```json
// Response 200
{ "room_id": "...", "hms_token": "eyJhbG..." }
```

Errors:
- `403` — `"You are not a participant of this session."`
- `400` — `"Session is not in progress. Current status: ..."` | `"Video room is not available."`

### POST /api/sessions/<id>/end/
Examiner only. Session must be IN_PROGRESS. Sets status to COMPLETED.
```json
// Response 200 — session object
// Broadcasts WS event: session.ended
```

Errors:
- `403` — `"Only the session examiner can end the session."`
- `400` — `"Session is not in progress. Current status: ..."`

### POST /api/sessions/<id>/cancel/
Examiner only. Cancels a SCHEDULED session that has no candidate (invite not yet accepted). Sets status to CANCELLED, expires the invite, and broadcasts a WebSocket event.
```json
// Response 200
{ "detail": "Session cancelled." }
// Broadcasts WS event: session.cancelled
```

Errors:
- `404` — `"Not found."`
- `403` — `"Only the session examiner can cancel the session."`
- `400` — `"Only scheduled sessions with no candidate can be cancelled."`

**Note:** Cancelled sessions do not count toward the examiner's `max_sessions` limit.
