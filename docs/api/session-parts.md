# Session Parts

### GET /api/sessions/<id>/parts/
Any participant. Returns list of session parts.
```json
[
  {
    "id": 1,
    "session": 5,
    "part": 1,
    "part_label": "Part 1",
    "started_at": "2024-01-05T14:05:00Z",
    "ended_at": null,
    "duration_seconds": null
  }
]
```

### POST /api/sessions/<id>/parts/
Examiner only. Session must be IN_PROGRESS. Creates and starts a part.
```json
// Request
{ "part": 1 }  // 1, 2, or 3
// Response 201 — part object
// Broadcasts WS event: part.started
```
Each part can only be started once per session.

Errors:
- `403` — `"You are not a participant of this session."` | `"Only the examiner can start a part."`
- `400` — `"Session is not in progress. Current status: ..."` | `"part must be 1, 2, or 3."` | `"Part N has already been started."`

### POST /api/sessions/<id>/parts/<part_num>/end/
Examiner only. Ends the specified part.
```json
// Response 200 — part object with ended_at populated
// Broadcasts WS event: part.ended
```

Errors:
- `404` — `"Part N has not been started."`
- `403` — `"Only the examiner can end a part."`
- `400` — `"Session is not in progress. Current status: ..."` | `"Part N has already ended."`
