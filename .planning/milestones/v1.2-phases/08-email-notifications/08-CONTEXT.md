# Phase 8: Email Notifications - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire email notification sends at session request trigger points using the existing Resend API pattern from main/services/email.py. Emails fire after transaction exits and must not block or roll back on Resend failure.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — infrastructure phase. Key constraints:
- Follow the existing `main/services/email.py` Resend pattern
- Email sends must occur AFTER the transaction exits (same discipline as `_broadcast`)
- Email send returns bool, does not raise — callers decide how to surface failure (per v1.1 decision)
- Three trigger points: new request (to examiner), accept (to candidate), reject (to candidate)

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `main/services/email.py` — existing Resend API wrapper pattern
- `scheduling/views.py` — trigger points in `SessionRequestListCreateView.post()`, `AcceptRequestView.post()`, `RejectRequestView.post()`
- `MockIT/settings.py` — `RESEND_API_KEY` already configured

### Established Patterns
- Email send returns bool (v1.1 decision from Phase 03-01)
- External calls after transaction.atomic block (broadcast discipline)
- Service functions in `{app}/services/` directory

### Integration Points
- `scheduling/services/email.py` — new email notification functions
- `scheduling/views.py` — call email functions after successful operations

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase

</specifics>

<deferred>
## Deferred Ideas

None

</deferred>
