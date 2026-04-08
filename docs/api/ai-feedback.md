# AI Feedback

Endpoints for triggering AI-powered transcription and feedback generation on a completed session,
and for retrieving the job status, transcript, and AI-generated IELTS scores.

---

### POST /api/sessions/<id>/ai-feedback/

Trigger AI feedback generation for a completed session. Creates an `AIFeedbackJob` and enqueues
the transcription + AI assessment task as a background job.

**Auth:** Token (examiner only — must be the session examiner)

**Preconditions:**
- Session must be in `COMPLETED` status.
- No `PENDING` or `PROCESSING` job may already exist for this session.
  Retrying after a `FAILED` job is allowed.
- Examiner must not have exceeded their monthly AI feedback limit (default: 10/month).

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
| `429` | `"Monthly AI feedback limit reached (10/10). Resets next month."` |

---

### GET /api/sessions/<id>/ai-feedback/

Retrieve the latest AI feedback job status, transcript, and AI-generated scores for a session.

**Auth:** Token (examiner or candidate — any session participant)

**Response 200 OK (job DONE with AI scores):**
```json
{
  "job_id": 1,
  "status": "Done",
  "transcript": "Examiner: Tell me about your hometown...\nCandidate: I come from...",
  "error_message": null,
  "scores": [
    {
      "criterion": "Fluency and Coherence",
      "band": 7,
      "feedback": "The candidate demonstrates good fluency with only occasional hesitation. Ideas are logically organized with clear progression throughout the response."
    },
    {
      "criterion": "Grammatical Range & Accuracy",
      "band": 6,
      "feedback": "A mix of simple and complex structures is used. Some errors occur with complex forms but these rarely impede communication."
    },
    {
      "criterion": "Lexical Resource",
      "band": 7,
      "feedback": "Good range of vocabulary is used flexibly. Some less common items are used with awareness of style and collocation."
    },
    {
      "criterion": "Pronunciation",
      "band": 7,
      "feedback": "Clear pronunciation throughout with good use of features such as stress and intonation. Only occasional mispronunciations."
    }
  ]
}
```

**Response 200 OK (job not DONE):**
```json
{
  "job_id": 1,
  "status": "Processing",
  "transcript": null,
  "error_message": null,
  "scores": null
}
```

**Field reference:**

| Field | Type | Description |
|-------|------|-------------|
| `job_id` | int | AI feedback job ID |
| `status` | string | `"Pending"`, `"Processing"`, `"Done"`, or `"Failed"` |
| `transcript` | string\|null | Session transcript (available when Done) |
| `error_message` | string\|null | Error details (available when Failed) |
| `scores` | array\|null | AI-generated IELTS scores (available when Done, `null` otherwise) |
| `scores[].criterion` | string | IELTS criterion name (FC, GRA, LR, PR) |
| `scores[].band` | int | Band score (1-9) |
| `scores[].feedback` | string | 3-4 sentences of actionable feedback |

**Errors:**

| Status | Detail |
|--------|--------|
| `403` | `"You are not a participant of this session."` |
| `404` | `"Not found."` (session) or `"No AI feedback job found for this session."` |

---

### WebSocket Event: ai_feedback_ready

When an AI feedback job completes successfully, a WebSocket event is pushed to all clients
connected to the session group.

**Channel:** `session_<session_id>`

**Event payload:**
```json
{
  "type": "ai_feedback_ready",
  "job_id": 1,
  "session_id": 42
}
```

Clients should fetch the full results via `GET /api/sessions/<id>/ai-feedback/` after receiving
this event. The event payload is intentionally minimal — full scores and transcript are retrieved
via the REST endpoint.

**Connection:** Clients connect to the WebSocket at `ws/session/<session_id>/?token=<auth_token>`.
The event is delivered through the existing `SessionConsumer` event forwarding mechanism.
