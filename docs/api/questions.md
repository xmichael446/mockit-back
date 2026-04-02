# Questions

### GET /api/sessions/<id>/parts/<part_num>/available-questions/
Examiner only. Returns all questions from the preset for this part, with tracking.
```json
[
  {
    "session_question_id": null,  // null = not yet asked; int = SessionQuestion.id
    "asked": false,
    "question": {
      "id": 42,
      "topic": { "id": 1, "name": "Family", "part": 1, "slug": "family" },
      "text": "Do you have a large family?",
      "difficulty": 1,
      "bullet_points": null,
      "follow_ups": [
        { "id": 10, "text": "How often do you spend time together?" }
      ]
    }
  },
  {
    "session_question_id": 7,
    "asked": true,
    "question": { ... }
  }
]
```

Errors:
- `403` — `"Examiner only."`
- `400` — `"This session has no preset."` | `"part_num must be 1, 2, or 3."`

### POST /api/sessions/<id>/parts/<part_num>/ask/
Examiner only. Marks a question as asked. The part must have been started.
```json
// Request
{ "question_id": 42 }
// or with optional client timestamp for accurate recording offsets:
{ "question_id": 42, "client_ts": "2024-01-05T14:06:00.123Z" }
// Response 201 — SessionQuestion object (see below)
// Broadcasts WS event: question.asked
```

Errors:
- `404` — `"Question not found."`
- `403` — `"Only the examiner can ask questions."`
- `400` — `"Session is not in progress. Current status: ..."` | `"Part N has not been started yet."` | `"question_id is required."` | `"This question does not belong to the preset topics for this part."` | `"This question has already been asked in this part."`

### GET /api/sessions/<id>/parts/<part_num>/questions/
Any participant. Returns all asked SessionQuestions for this part.
```json
[
  {
    "id": 7,
    "session_part": 1,
    "question": { ...full question object... },
    "order": 1,
    "asked_at": "2024-01-05T14:06:00Z",
    "answer_started_at": null,
    "ended_at": null,
    "prep_duration_seconds": null,
    "speaking_duration_seconds": null,
    "total_duration_seconds": null,
    "session_follow_ups": [],
    "notes": []
  }
]
```

### POST /api/sessions/<id>/session-questions/<sq_id>/answer-start/
Candidate only. Signals the candidate has started speaking. Optional `"client_ts"` (ISO 8601) for accurate recording offsets.
```json
// Request (body is optional)
{ "client_ts": "2024-01-05T14:06:05.789Z" }
// Response 200 — SessionQuestion object
// Broadcasts WS event: question.answer_started
```

Errors:
- `404` — `"Session question not found."`
- `403` — `"Only the candidate can signal answer start."`
- `400` — `"Session is not in progress. Current status: ..."` | `"Question has not been asked yet."` | `"Answer has already been started."`

### POST /api/sessions/<id>/session-questions/<sq_id>/end/
Examiner only. Ends the current question. Optional `"client_ts"` (ISO 8601) for accurate recording offsets.
```json
// Request (body is optional)
{ "client_ts": "2024-01-05T14:08:00.000Z" }
// Response 200 — SessionQuestion object
// Broadcasts WS event: question.ended
```

Errors:
- `404` — `"Session question not found."`
- `403` — `"Only the examiner can end a question."`
- `400` — `"Session is not in progress. Current status: ..."` | `"Question has not been asked yet."` | `"Question has already ended."`
