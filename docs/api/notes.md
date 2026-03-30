# Notes

### GET /api/sessions/<id>/session-questions/<sq_id>/notes/
Examiner only. Returns notes for a question.
```json
[{ "id": 1, "content": "Good use of complex sentences", "created_at": "..." }]
```

Errors:
- `404` — `"Not found."` (session) | `"Session question not found."`
- `403` — `"Examiner only."`

### POST /api/sessions/<id>/session-questions/<sq_id>/notes/
Examiner only. Creates a note.
```json
// Request
{ "content": "Good use of complex sentences" }
// Response 201 — note object
// Broadcasts WS event: note.added
```

Errors:
- `404` — `"Not found."` (session) | `"Session question not found."`
- `403` — `"Examiner only."`
- `400` — `"content is required."` | `"content must be 1000 characters or fewer."`

### DELETE /api/sessions/<id>/notes/<note_id>/
Examiner only. Returns 204 no content.
Broadcasts WS event: note.deleted

Errors:
- `404` — `"Not found."` (session) | `"Note not found."`
- `403` — `"Examiner only."`
