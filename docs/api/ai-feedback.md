# AI Feedback

Endpoints for triggering AI-powered transcription and feedback generation on a completed session,
and for retrieving the job status and transcript.

---

### POST /api/sessions/<id>/ai-feedback/

Trigger AI feedback generation for a completed session. Creates an `AIFeedbackJob` and enqueues
the transcription task as a background job.

**Auth:** Token (examiner only — must be the session examiner)

**Preconditions:**
- Session must be in `COMPLETED` status.
- No `PENDING` or `PROCESSING` job may already exist for this session.
  Retrying after a `FAILED` job is allowed.

**Response 202 Accepted:**
```json
{
  "job_id": 1,
  "status": "Pending"
}
```

**Errors:**

| Status | Detail |
|--------|--------|
| `400` | `"Session must be completed before triggering AI feedback."` |
| `403` | `"Only the session examiner can trigger AI feedback."` |
| `404` | `"Not found."` |
| `409` | `"An AI feedback job is already in progress for this session."` |

---

### GET /api/sessions/<id>/ai-feedback/

Retrieve the latest AI feedback job status and transcript for a session.

**Auth:** Token (examiner or candidate — any session participant)

**Response 200 OK:**
```json
{
  "job_id": 1,
  "status": "Done",
  "transcript": "Examiner: Tell me about your hometown...\nCandidate: I come from...",
  "error_message": null
}
```

`status` values: `"Pending"`, `"Processing"`, `"Done"`, `"Failed"`

`transcript` and `error_message` are `null` until the job completes or fails.

**Errors:**

| Status | Detail |
|--------|--------|
| `403` | `"You are not a participant of this session."` |
| `404` | `"Not found."` (session) or `"No AI feedback job found for this session."` |
