# Availability

### GET /api/scheduling/availability/
Examiner only. List own recurring availability slots.
`day_of_week`: 0=Monday through 6=Sunday.
```json
// Response 200
[
  { "id": 1, "day_of_week": 0, "start_time": "09:00:00", "created_at": "2024-06-01T10:00:00Z" }
]
```

Errors:
- `403` — `"Only examiners can view availability slots."`

### POST /api/scheduling/availability/
Examiner only. Create a recurring availability slot. `start_time` must be on the hour, between 08:00 and 21:00.
```json
// Request
{ "day_of_week": 0, "start_time": "09:00" }
// Response 201
{ "id": 1, "day_of_week": 0, "start_time": "09:00:00", "created_at": "2024-06-01T10:00:00Z" }
```

Errors:
- `403` — `"Only examiners can create availability slots."`
- `400` — `"start_time must be on the hour (e.g., 08:00, 14:00)."` | `"start_time must be between 08:00 and 21:00 inclusive."` | `"You already have an availability slot for this day and time."`

### PATCH /api/scheduling/availability/<id>/
Examiner only. Partial update of own slot. Updatable fields: `day_of_week`, `start_time`.
```json
// Request
{ "start_time": "10:00" }
// Response 200
{ "id": 1, "day_of_week": 0, "start_time": "10:00:00", "created_at": "2024-06-01T10:00:00Z" }
```

Errors:
- `403` — `"Only examiners can update availability slots."`
- `404` — Not found

### DELETE /api/scheduling/availability/<id>/
Examiner only. Delete own slot.
```json
// Response 204 (no body)
```

Errors:
- `403` — `"Only examiners can delete availability slots."`
- `404` — Not found

### GET /api/scheduling/blocked-dates/
Examiner only. List own blocked dates.
```json
// Response 200
[
  { "id": 1, "date": "2024-06-15", "reason": "Holiday", "created_at": "2024-06-01T10:00:00Z" }
]
```

Errors:
- `403` — `"Only examiners can view blocked dates."`

### POST /api/scheduling/blocked-dates/
Examiner only. Create a blocked date. `reason` is optional.
```json
// Request
{ "date": "2024-06-15", "reason": "Holiday" }
// Response 201
{ "id": 1, "date": "2024-06-15", "reason": "Holiday", "created_at": "2024-06-01T10:00:00Z" }
```

Errors:
- `403` — `"Only examiners can create blocked dates."`

### DELETE /api/scheduling/blocked-dates/<id>/
Examiner only. Delete own blocked date.
```json
// Response 204 (no body)
```

Errors:
- `403` — `"Only examiners can delete blocked dates."`
- `404` — Not found

### GET /api/scheduling/examiners/<id>/available-slots/
Any authenticated user. Returns computed available slots for a 7-day window starting from `week`.

Query params:
- `week` (required) — ISO date string, e.g. `2024-06-10`. Week window starts on this date.
- `timezone` (optional) — IANA timezone string, e.g. `Asia/Tashkent`. Informational; response remains in UTC.

Slot `status` values: `"available"`, `"booked"`, `"blocked"`.
```json
// Response 200
[
  {
    "date": "2024-06-10",
    "day_of_week": 0,
    "slots": [
      { "slot_id": 1, "start_time": "09:00", "status": "available" }
    ]
  }
]
```

Errors:
- `400` — `"week query parameter is required."` | `"Invalid week format. Use YYYY-MM-DD."`
- `404` — Examiner not found

### GET /api/scheduling/examiners/<id>/is-available/
Any authenticated user. Real-time check of whether an examiner is currently available (i.e. has an active slot right now).
```json
// Response 200 — available
{ "is_available": true, "current_slot": { "slot_id": 1, "start_time": "09:00", "status": "available" } }
// Response 200 — not available
{ "is_available": false, "current_slot": null }
```

Errors:
- `404` — Examiner not found
