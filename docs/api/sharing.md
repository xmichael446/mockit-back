# Sharing

Share a completed session publicly. Anyone with the share link can view the recording, timeline, band scores, and participant profiles without logging in.

### POST /api/sessions/\<id\>/share/
Examiner or candidate. Creates a share token for the session (or returns the existing one). The session must have a released result.

```json
// Response 201 (first time) / 200 (already shared)
{
  "share_token": "abc-defg",
  "share_url": "/api/sessions/shared/abc-defg/"
}
```

Errors:
- `404` -- `"Not found."`
- `403` -- `"You are not a participant of this session."`
- `400` -- `"Session has no result yet."` | `"Session result has not been released yet."`

---

### GET /api/sessions/shared/\<share\_token\>/
**Public -- no authentication required.**

Returns the session's recording with full timeline, band scores (no feedback text), and participant profiles.

```json
// Response 200
{
  "recording": {
    "id": 1,
    "session": 5,
    "audio_url": "http://host/media/recordings/session.webm",
    "recording_started_at": "2024-01-05T14:00:00Z",
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
          }
        ]
      }
    ]
  },
  "scores": [
    { "criterion": 1, "criterion_label": "Fluency and Coherence", "band": 7 },
    { "criterion": 2, "criterion_label": "Grammatical Range & Accuracy", "band": 6 },
    { "criterion": 3, "criterion_label": "Lexical Resource", "band": 7 },
    { "criterion": 4, "criterion_label": "Pronunciation", "band": 7 }
  ],
  "overall_band": "7.0",
  "examiner": {
    "full_legal_name": "John Smith",
    "bio": "...",
    "profile_picture": "http://host/media/...",
    "is_verified": true,
    "credential": { "listening_score": "8.5", "reading_score": "9.0", "writing_score": "8.0", "speaking_score": "9.0", "certificate_url": "..." }
  },
  "candidate": {
    "profile_picture": "http://host/media/...",
    "target_speaking_score": "7.5",
    "current_speaking_score": "6.5"
  }
}
```

**What is NOT exposed:** feedback text on criterion scores, overall feedback, examiner notes.

**What IS exposed:** recording audio + full timeline (parts, questions, follow-ups with offsets), the 4 criterion band scores + overall band, examiner profile (name, bio, picture, credentials), candidate profile (picture, scores).

Errors:
- `404` -- `"Not found."` (invalid share token)
