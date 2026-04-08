# Phase 13: Usage Control - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

Examiners are subject to a monthly AI feedback limit and receive a clear error when that limit is reached. Enforcement happens at the HTTP trigger point with select_for_update to prevent race conditions.

</domain>

<decisions>
## Implementation Decisions

### Usage Control Design
- Monthly limit stored as Django setting `AI_FEEDBACK_MONTHLY_LIMIT = 10` with env variable override
- Usage counted by querying AIFeedbackJob records per examiner per calendar month (filter by created_at)
- Enforcement in AIFeedbackTriggerView before job creation (not in background task)
- select_for_update + transaction.atomic on the count query to prevent concurrent requests exceeding the limit
- 429 Too Many Requests response with clear error message when limit reached

### Claude's Discretion
- Exact error message wording
- Whether to include remaining usage count in successful responses

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AIFeedbackTriggerView` in `session/views.py` — the enforcement point
- `AIFeedbackJob` model with session FK (session.examiner gives the user)
- `select_for_update` pattern already used in scheduling app (session request accept)
- `transaction.atomic()` pattern established in v1.1

### Established Patterns
- select_for_update + transaction.atomic for race-condition-sensitive writes (Phase 6)
- Settings with env override pattern (WHISPER_MODEL_SIZE, ANTHROPIC_API_KEY)

### Integration Points
- `AIFeedbackTriggerView.post()` — add limit check before job creation
- `AI_FEEDBACK_MONTHLY_LIMIT` setting in MockIT/settings.py

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches following the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
