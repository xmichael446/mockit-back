# Follow-Ups

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

Errors:
- `404` — `"Session question not found."` | `"Follow-up not found or does not belong to this question."`
- `403` — `"Only the examiner can ask follow-ups."`
- `400` — `"Session is not in progress. Current status: ..."` | `"follow_up_id is required."`

### POST /api/sessions/<id>/session-follow-ups/<sf_id>/end/
Examiner only. Ends the follow-up.
```json
// Response 200 — SessionFollowUp object
// Broadcasts WS event: followup.ended
```

Errors:
- `404` — `"Session follow-up not found."`
- `403` — `"Only the examiner can end follow-ups."`
- `400` — `"Session is not in progress. Current status: ..."` | `"Follow-up has already ended."`
