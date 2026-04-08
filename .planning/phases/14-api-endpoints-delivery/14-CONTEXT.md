# Phase 14: API Endpoints & Delivery - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Examiners and candidates can trigger, monitor, and retrieve AI feedback through REST endpoints and receive real-time notification on completion. Builds on the existing AIFeedbackTriggerView (Phase 11) and extends it with complete response shapes, WebSocket push event, and full API documentation.

</domain>

<decisions>
## Implementation Decisions

### API Endpoints
- Single unified endpoint at sessions/<id>/ai-feedback/ (already exists from Phase 11 gap closure)
- POST returns 202 with job_id (already implemented)
- GET returns status + transcript (already implemented) — needs enhancement to include AI scores and per-criterion feedback when job is DONE
- Response shape for GET when DONE: {status, transcript, scores: [{criterion, band, feedback}]}

### WebSocket Event
- ai_feedback_ready event pushed in run_ai_feedback task after status=DONE, using existing _broadcast() pattern from session/views.py
- Minimal payload: {type: "ai_feedback_ready", job_id, status: "done", session_id}
- Client fetches full details via GET endpoint (not in event payload)
- Must follow _broadcast() discipline: call after transaction exits

### API Documentation
- Update existing docs/api/ai-feedback.md with complete request/response schemas
- Include error scenarios (401, 403, 404, 409, 429)
- Update docs/api/index.md

### Claude's Discretion
- Exact response JSON field names and nesting
- Whether to add serializers or keep inline response building

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AIFeedbackTriggerView` in session/views.py — POST + GET already working
- `_broadcast()` helper in session/views.py for WebSocket events
- `SessionConsumer` in session/consumers.py handles session_event forwarding
- `CriterionScore` model with feedback field
- docs/api/ai-feedback.md — basic docs from Phase 11

### Established Patterns
- _broadcast(session_id, event_type, data) → channel_layer.group_send
- async_to_sync for channel layer calls from sync code
- All REST views push events via _broadcast after state changes

### Integration Points
- run_ai_feedback() in session/tasks.py — add _broadcast call after DONE
- AIFeedbackTriggerView.get() — enhance response to include AI scores
- docs/api/ai-feedback.md — expand with complete schemas

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches following the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
