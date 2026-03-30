# WebSocket — Session Room

**URL:** `ws://host/ws/session/<session_id>/?token=<auth_token>`

Connect when the session is IN_PROGRESS (or just before). Both the examiner and candidate should connect. The server sends JSON events; clients should send `{"type":"ping"}` periodically to keep the connection alive and expect `{"type":"pong"}` back.

Close codes:
- `4001` — authentication failed (bad or missing token)
- `4003` — user is not a participant of this session

---

### WebSocket Events (server → client)

All events are JSON objects with a top-level `"type"` field.

#### `invite.accepted`
Fired when a candidate accepts the invite. The examiner receives this and knows they can start the session.
```json
{
  "type": "invite.accepted",
  "session_id": 5,
  "candidate": { "id": 2, "username": "jane", "first_name": "Jane", "last_name": "Doe" },
  "invite_accepted_at": "2024-01-04T12:00:00Z"
}
```

#### `session.started`
```json
{ "type": "session.started", "session_id": 5, "started_at": "2024-01-05T14:00:00Z" }
```

#### `session.ended`
```json
{ "type": "session.ended", "session_id": 5, "ended_at": "2024-01-05T15:00:00Z" }
```

#### `part.started`
```json
{ "type": "part.started", "part": 1, "part_id": 1, "started_at": "2024-01-05T14:05:00Z" }
```

#### `part.ended`
```json
{ "type": "part.ended", "part": 1, "part_id": 1, "ended_at": "2024-01-05T14:25:00Z" }
```

#### `question.asked`
Broadcast when examiner clicks "Ask". The candidate's page should display this question.
```json
{
  "type": "question.asked",
  "session_question_id": 7,
  "part": 1,
  "order": 1,
  "asked_at": "2024-01-05T14:06:00Z",
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
}
```

#### `question.answer_started`
```json
{ "type": "question.answer_started", "session_question_id": 7, "answer_started_at": "2024-01-05T14:06:10Z" }
```

#### `question.ended`
```json
{ "type": "question.ended", "session_question_id": 7, "ended_at": "2024-01-05T14:07:30Z" }
```

#### `followup.asked`
```json
{
  "type": "followup.asked",
  "session_follow_up_id": 3,
  "session_question_id": 7,
  "asked_at": "2024-01-05T14:07:45Z",
  "follow_up": { "id": 10, "text": "How often do you spend time together?" }
}
```

#### `followup.ended`
```json
{ "type": "followup.ended", "session_follow_up_id": 3, "session_question_id": 7, "ended_at": "2024-01-05T14:08:20Z" }
```

#### `note.added`
Only visible to examiner (both connect, but notes are private context; broadcast goes to both — examiner should show it, candidate may ignore it).
```json
{ "type": "note.added", "note_id": 1, "session_question_id": 7, "content": "Good use of complex sentences", "created_at": "..." }
```

#### `note.deleted`
```json
{ "type": "note.deleted", "note_id": 1, "session_question_id": 7 }
```

#### `result.released`
Fired when the examiner releases the result. The candidate should wait for this event — do **not** poll the result endpoint. The event carries the full result so the candidate can display it immediately without an extra GET request.
```json
{
  "type": "result.released",
  "session_id": 5,
  "overall_band": "7.0",
  "released_at": "2024-01-05T16:00:00Z",
  "scores": [
    { "id": 1, "criterion": 1, "criterion_label": "Fluency and Coherence", "band": 7, "feedback": "..." },
    { "id": 2, "criterion": 2, "criterion_label": "Grammatical Range & Accuracy", "band": 6, "feedback": "..." },
    { "id": 3, "criterion": 3, "criterion_label": "Lexical Resource", "band": 7, "feedback": "..." },
    { "id": 4, "criterion": 4, "criterion_label": "Pronunciation", "band": 7, "feedback": "..." }
  ]
}
```
