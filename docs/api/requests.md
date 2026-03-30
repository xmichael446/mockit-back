# Session Requests

Session request `status` values: `1=PENDING`, `2=ACCEPTED`, `3=REJECTED`, `4=CANCELLED`.

### GET /api/scheduling/requests/
Both roles. Examiner sees requests where they are the examiner; candidate sees own submitted requests.

Query params:
- `status` (optional) — filter by status integer, e.g. `?status=1`

```json
// Response 200
[
  {
    "id": 1,
    "candidate": 2,
    "examiner": 1,
    "availability_slot": 5,
    "requested_date": "2024-06-12",
    "session": null,
    "comment": "Looking forward to the session",
    "rejection_comment": null,
    "status": 1,
    "created_at": "2024-06-01T10:00:00Z",
    "updated_at": "2024-06-01T10:00:00Z"
  }
]
```

### POST /api/scheduling/requests/
Candidate only. Submit a session request for an examiner's availability slot.

Validation:
- `requested_date` weekday must match the slot's `day_of_week`
- `requested_date` cannot be in the past
- Slot must be available (not booked or blocked)
- Candidate must not already have an active (PENDING or ACCEPTED) request for the same slot and date

```json
// Request
{
  "availability_slot": 5,
  "requested_date": "2024-06-12",
  "comment": "Looking forward to the session"
}
// Response 201
{
  "id": 1,
  "candidate": 2,
  "examiner": 1,
  "availability_slot": 5,
  "requested_date": "2024-06-12",
  "session": null,
  "comment": "Looking forward to the session",
  "rejection_comment": null,
  "status": 1,
  "created_at": "2024-06-01T10:00:00Z",
  "updated_at": "2024-06-01T10:00:00Z"
}
```

Errors:
- `403` — `"Only candidates can submit session requests."`
- `400` — `"Requested date does not match the slot's day of week."` | `"Requested date cannot be in the past."` | `"This slot is booked and cannot be booked."` | `"You already have an active request for this slot and date."`

### POST /api/scheduling/requests/<id>/accept/
Examiner only. Accept a PENDING request. Atomically creates a linked `IELTSMockSession` scheduled at the requested date and slot start time.

Broadcasts WS event: `session_request.accepted`
```json
// Response 200 — request object with session field populated
{
  "id": 1,
  "candidate": 2,
  "examiner": 1,
  "availability_slot": 5,
  "requested_date": "2024-06-12",
  "session": 7,
  "comment": "Looking forward to the session",
  "rejection_comment": null,
  "status": 2,
  "created_at": "2024-06-01T10:00:00Z",
  "updated_at": "2024-06-10T09:00:00Z"
}
```

Errors:
- `403` — `"Only examiners can accept session requests."`
- `404` — `"Not found."`
- `400` — ValidationError if request is not PENDING

### POST /api/scheduling/requests/<id>/reject/
Examiner only. Reject a PENDING request. `rejection_comment` is required.
```json
// Request
{ "rejection_comment": "I am unavailable on that date." }
// Response 200 — request object with rejection_comment populated
{
  "id": 1,
  "candidate": 2,
  "examiner": 1,
  "availability_slot": 5,
  "requested_date": "2024-06-12",
  "session": null,
  "comment": "Looking forward to the session",
  "rejection_comment": "I am unavailable on that date.",
  "status": 3,
  "created_at": "2024-06-01T10:00:00Z",
  "updated_at": "2024-06-10T09:00:00Z"
}
```

Errors:
- `403` — `"Only examiners can reject session requests."`
- `404` — Not found
- `400` — `rejection_comment` required

### POST /api/scheduling/requests/<id>/cancel/
Candidate or examiner. Cancel a PENDING or ACCEPTED request.
```json
// Response 200 — request object with status=4 (CANCELLED)
{
  "id": 1,
  "candidate": 2,
  "examiner": 1,
  "availability_slot": 5,
  "requested_date": "2024-06-12",
  "session": null,
  "comment": "Looking forward to the session",
  "rejection_comment": null,
  "status": 4,
  "created_at": "2024-06-01T10:00:00Z",
  "updated_at": "2024-06-10T09:00:00Z"
}
```

Errors:
- `403` — `"You are not a participant in this request."`
- `404` — `"Not found."`
- `400` — ValidationError if request is not PENDING or ACCEPTED
