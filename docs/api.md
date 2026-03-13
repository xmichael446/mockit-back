# MockIT API Reference

All HTTP endpoints are prefixed with `/api/`. Authentication uses DRF Token auth: `Authorization: Token <token>`.

WebSocket connections authenticate via query-string token: `ws://host/ws/session/<id>/?token=<token>`.

---

## Authentication

### POST /api/auth/register/
No auth required.
```json
// Request
{ "username": "...", "password": "...", "first_name": "...", "last_name": "...", "email": "...", "role": 1 }
// role: 1=EXAMINER, 2=CANDIDATE
// Response 201
{ "id": 1, "username": "...", "first_name": "...", "last_name": "...", "email": "...", "role": 1, "role_label": "Examiner", "token": "abc123..." }
```

### POST /api/auth/login/
No auth required.
```json
// Request
{ "username": "...", "password": "..." }
// Response 200
{ "token": "abc123...", "user": { "id": 1, "username": "...", "role": 1, "role_label": "Examiner", ... } }
```

### POST /api/auth/logout/
```json
// Response 204 (no body)
```

### GET /api/auth/me/
```json
// Response 200
{ "id": 1, "username": "...", "first_name": "...", "last_name": "...", "email": "...", "role": 1, "role_label": "Examiner" }
```

---

## Presets (examiner only)

### GET /api/presets/
Returns all presets with nested topics.
```json
[
  {
    "id": 1,
    "name": "Standard IELTS Set A",
    "part_1": [{ "id": 1, "name": "Family", "part": 1, "slug": "family" }],
    "part_2": [{ "id": 5, "name": "Describe a place", "part": 2, "slug": "describe-a-place" }],
    "part_3": [{ "id": 9, "name": "Urban development", "part": 3, "slug": "urban-development" }],
    "created_at": "2024-01-01T00:00:00Z"
  }
]
```

### POST /api/presets/
```json
// Request
{
  "name": "My Preset",
  "part_1": [1, 2],   // topic IDs (must be Part 1 topics)
  "part_2": [5],       // topic IDs (must be Part 2 topics)
  "part_3": [9, 10]    // topic IDs (must be Part 3 topics)
}
// Response 201 — same shape as GET single preset
```

---

## Sessions

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

### GET /api/sessions/<id>/
Returns the session object. User must be examiner or candidate.

### POST /api/sessions/accept-invite/
Candidate only. Accepts an invite token.
```json
// Request
{ "token": "uuid-string" }
// Response 200 — session object with candidate populated
```

### POST /api/sessions/<id>/start/
Examiner only. Session must be SCHEDULED. Candidate must have accepted invite.
Creates the 100ms video room. Sets status to IN_PROGRESS.
```json
// Response 200
{
  ...session object...,
  "hms_token": "eyJhbG..."  // use this to join the 100ms room
}
// Broadcasts WS event: session.started
```

### POST /api/sessions/<id>/join/
Any participant. Session must be IN_PROGRESS. Returns a fresh 100ms token.
```json
// Response 200
{ "room_id": "...", "hms_token": "eyJhbG..." }
```

### POST /api/sessions/<id>/end/
Examiner only. Session must be IN_PROGRESS. Sets status to COMPLETED.
```json
// Response 200 — session object
// Broadcasts WS event: session.ended
```

---

## Session Parts

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

### POST /api/sessions/<id>/parts/<part_num>/end/
Examiner only. Ends the specified part.
```json
// Response 200 — part object with ended_at populated
// Broadcasts WS event: part.ended
```

---

## Questions

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

### POST /api/sessions/<id>/parts/<part_num>/ask/
Examiner only. Marks a question as asked. The part must have been started.
```json
// Request
{ "question_id": 42 }
// Response 201 — SessionQuestion object (see below)
// Broadcasts WS event: question.asked
```

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
Candidate only. Signals the candidate has started speaking.
```json
// Response 200 — SessionQuestion object
// Broadcasts WS event: question.answer_started
```

### POST /api/sessions/<id>/session-questions/<sq_id>/end/
Examiner only. Ends the current question.
```json
// Response 200 — SessionQuestion object
// Broadcasts WS event: question.ended
```

---

## Follow-Ups

### POST /api/sessions/<id>/session-questions/<sq_id>/follow-ups/
Examiner only. Asks a follow-up on the given SessionQuestion.
```json
// Request
{ "follow_up_id": 10 }
// The follow_up_id must belong to the question's follow_ups list.
// Response 201
{
  "id": 3,
  "follow_up": 10,
  "follow_up_text": "How often do you spend time together?",
  "asked_at": "2024-01-05T14:08:00Z",
  "ended_at": null,
  "duration_seconds": null
}
// Broadcasts WS event: followup.asked
```

### POST /api/sessions/<id>/session-follow-ups/<sf_id>/end/
Examiner only. Ends the follow-up.
```json
// Response 200 — SessionFollowUp object
// Broadcasts WS event: followup.ended
```

---

## Notes

### GET /api/sessions/<id>/session-questions/<sq_id>/notes/
Examiner only. Returns notes for a question.
```json
[{ "id": 1, "content": "Good use of complex sentences", "created_at": "..." }]
```

### POST /api/sessions/<id>/session-questions/<sq_id>/notes/
Examiner only. Creates a note.
```json
// Request
{ "content": "Good use of complex sentences" }
// Response 201 — note object
// Broadcasts WS event: note.added
```

### DELETE /api/sessions/<id>/notes/<note_id>/
Examiner only. Returns 204 no content.
Broadcasts WS event: note.deleted

---

## Results

### GET /api/sessions/<id>/result/
Examiner: always accessible.
Candidate: only accessible after result is released.
```json
{
  "id": 1,
  "overall_band": "7.0",
  "is_released": false,
  "released_at": null,
  "scores": [
    { "id": 1, "criterion": 1, "criterion_label": "Fluency and Coherence", "band": 7, "feedback": "..." },
    { "id": 2, "criterion": 2, "criterion_label": "Grammatical Range & Accuracy", "band": 6, "feedback": "..." },
    { "id": 3, "criterion": 3, "criterion_label": "Lexical Resource", "band": 7, "feedback": "..." },
    { "id": 4, "criterion": 4, "criterion_label": "Pronunciation", "band": 7, "feedback": "..." }
  ]
}
```
Criterion values: 1=FC, 2=GRA, 3=LR, 4=PR

### POST /api/sessions/<id>/result/
Examiner only. Session must be COMPLETED. Submit/update scores.
Calling this multiple times is idempotent — updates existing scores.
```json
// Request
{
  "scores": [
    { "criterion": 1, "band": 7, "feedback": "Speaks fluently with some hesitation." },
    { "criterion": 2, "band": 6, "feedback": "Good range but some errors." },
    { "criterion": 3, "band": 7, "feedback": "Wide vocabulary." },
    { "criterion": 4, "band": 7, "feedback": "Clear pronunciation." }
  ]
}
// Response 201 — result object (see GET)
// overall_band is auto-computed as avg of 4 bands rounded to nearest 0.5
```

### POST /api/sessions/<id>/result/release/
Examiner only. Makes the result visible to the candidate.
```json
// Response 200 — result object with is_released=true
// Broadcasts WS event: result.released
```

---

## Recording

### POST /api/sessions/\<id\>/recording/
Examiner only. Upload the session's audio recording as a `webm` file.

Request: `multipart/form-data`

| Field | Type | Required |
|---|---|---|
| `audio_file` | File (webm) | Yes |

```json
// Response 201
{
  "id": 1,
  "session": 5,
  "audio_url": "http://host/media/recordings/session.webm",
  "created_at": "2024-01-05T15:10:00Z",
  "parts": [ ... ]  // same shape as GET (see below)
}
```

Errors:
- `400` — `audio_file` field missing
- `400` — a recording already exists for this session
- `403` — only the examiner can upload

---

### GET /api/sessions/\<id\>/recording/
Any participant. Returns the recording URL and a full timecode map of every part, question, and follow-up relative to `session.started_at`.

All `*_offset` values are **seconds from `session.started_at`**. Any event whose timestamp was not recorded returns `null`.

```json
// Response 200
{
  "id": 1,
  "session": 5,
  "audio_url": "http://host/media/recordings/session.webm",
  "created_at": "2024-01-05T15:10:00Z",
  "parts": [
    {
      "part": 1,
      "part_label": "Part 1",
      "start_offset": 10.5,
      "end_offset": 310.2,
      "questions": [
        {
          "type": "question",
          "id": 7,
          "order": 1,
          "text": "Do you have a large family?",
          "asked_offset": 12.0,
          "answer_started_offset": 16.5,
          "ended_offset": 90.0
        },
        {
          "type": "followup",
          "id": 3,
          "text": "How often do you spend time together?",
          "asked_offset": 92.0,
          "ended_offset": 120.0
        },
        {
          "type": "question",
          "id": 8,
          "order": 2,
          "text": "Where did you grow up?",
          "asked_offset": 122.0,
          "answer_started_offset": 126.0,
          "ended_offset": 200.0
        }
      ]
    },
    {
      "part": 2,
      "part_label": "Part 2",
      "start_offset": 320.0,
      "end_offset": 560.0,
      "questions": [ ... ]
    }
  ]
}
```

`questions` lists entries in asked order. Follow-ups appear immediately after the question they belong to. Both are distinguished by the `type` field (`"question"` or `"followup"`).

Errors:
- `404` — no recording uploaded yet

---

## Questions & Topics (read-only reference)

### GET /api/topics/
Query params: `?part=1`, `?search=family`, `?limit=10`, `?offset=0`
```json
{
  "count": 50,
  "next": "...",
  "previous": null,
  "results": [{ "id": 1, "name": "Family", "part": 1, "slug": "family" }]
}
```

### GET /api/topics/<id>/
Returns topic with all questions and follow-ups.

### GET /api/questions/<id>/
Returns question with topic info and follow-ups.

---

## WebSocket — Session Room

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

---

## Typical Flows

### Examiner flow
1. `POST /api/auth/login/` → get token
2. `POST /api/presets/` → create preset with topics
3. `POST /api/sessions/` → create session, get `invite_token`
4. Share `invite_token` with candidate out-of-band
5. Connect `ws/session/<id>/?token=...` early — listen for `invite.accepted` to know when candidate is ready
6. `POST /api/sessions/<id>/start/` → get `hms_token`, join 100ms room
7. `POST /api/sessions/<id>/parts/` `{"part": 1}` → start Part 1
8. `GET /api/sessions/<id>/parts/1/available-questions/` → show question list
9. `POST /api/sessions/<id>/parts/1/ask/` `{"question_id": 42}` → ask question (WS fires)
10. `POST /api/sessions/<id>/session-questions/<sq_id>/end/` → stop question
11. Repeat 9–10, optionally ask follow-ups
12. `POST /api/sessions/<id>/parts/1/end/`
13. Repeat for Parts 2 and 3
14. `POST /api/sessions/<id>/end/`
15. `POST /api/sessions/<id>/recording/` (multipart, field `audio_file`) → upload the webm recording
16. `POST /api/sessions/<id>/result/` with all four criterion scores and feedback
17. `POST /api/sessions/<id>/result/release/` → triggers `result.released` WS event to candidate

### Candidate flow
1. `POST /api/auth/login/` → get token
2. `POST /api/sessions/accept-invite/` `{"token": "..."}` → link to session
3. Connect `ws/session/<id>/?token=...` immediately after accepting — listen for `session.started`
4. On `session.started`: `POST /api/sessions/<id>/join/` → get `hms_token`, join 100ms room
5. Listen for `question.asked` → display the question
6. `POST /api/sessions/<id>/session-questions/<sq_id>/answer-start/` when ready to speak
7. Listen for `question.ended`, `followup.asked`, etc.
8. On `session.ended`: show "waiting for examiner feedback" screen
9. On `result.released` WS event: display scores and feedback immediately (full result is included in the event — no extra GET needed)
10. `GET /api/sessions/<id>/recording/` → retrieve the recording URL and timecodes to review the session
