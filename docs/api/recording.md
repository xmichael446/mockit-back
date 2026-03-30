# Recording

### POST /api/sessions/\<id\>/recording/
Examiner only. Upload the session's audio recording as a `webm` file.

Request: `multipart/form-data`

| Field | Type | Required |
|---|---|---|
| `audio_file` | File (webm) | Yes |
| `recording_started_at` | ISO 8601 datetime string | No (falls back to `session.started_at`) |

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
- `404` — `"Not found."`
- `403` — `"You are not a participant of this session."` | `"Only the examiner can upload recordings."`
- `400` — `"A recording already exists for this session."` | `"audio_file is required."` | `"recording_started_at must be a valid ISO 8601 datetime string."`

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
- `404` — `"Not found."` (session) | `"No recording found for this session."`
- `403` — `"You are not a participant of this session."`
