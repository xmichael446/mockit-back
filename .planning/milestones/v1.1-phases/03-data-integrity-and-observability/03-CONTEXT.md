# Phase 3: Data Integrity and Observability - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase ensures scoring completeness before release, handles email delivery failures gracefully, and adds audit logging to critical session actions. Covers REF-02, EDGE-02, EDGE-03.

</domain>

<decisions>
## Implementation Decisions

### Scoring Validation (EDGE-02)
- Validate all 4 criterion scores exist in ReleaseResultView before releasing — check `result.scores.count() == 4` and verify all 4 criteria (FC, GRA, LR, PR) are present
- Return 400 listing missing criteria by name — e.g., `{"detail": "Cannot release: missing scores for LR, PR"}`
- Allow partial/incremental score submission — only block at release time, not at submit time
- Examiners can submit scores one at a time or all at once; release is the gate

### Email Error Handling (EDGE-03)
- Catch exceptions from `resend.Emails.send()` in `send_verification_email()`, log the error, still complete the registration/action
- Return success with warning field when email fails — `{"message": "...", "email_warning": "Verification email could not be sent"}`
- Use Python `logging` module for email error logging — standard, no new dependencies
- Registration should never fail because the email service is down — user account is created regardless

### Audit Logging (REF-02)
- Use Python `logging` module with structured log messages — no new dependencies, configurable
- Log 5 critical actions per REF-02: session create, session start, session end, result submit, result release
- Log format: `[AUDIT] action=<action> user=<user_id> session=<session_id> timestamp=<iso>` — structured, parseable
- Configure logging in settings.py to output to both console and a file (e.g., `logs/audit.log`)
- Audit log file is viewable without direct database access — meets success criteria for admin visibility

### Claude's Discretion
- Exact logging configuration in settings.py (handlers, formatters, log levels)
- Whether to create a dedicated audit logger or use the root logger
- How to structure the email warning response alongside existing response fields
- Whether to add the logging import at module level or per-function

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SpeakingCriterion(IntegerChoices)` already defines FC=1, GRA=2, LR=3, PR=4 — use for validation
- `SessionResult` model with `scores` related manager — `result.scores.values_list("criterion", flat=True)` gives existing criteria
- `CriterionScore` model tracks individual scores per criterion
- `main/services/email.py` has `send_verification_email()` — the single email function to wrap

### Established Patterns
- Views return `Response({"detail": "..."}, status=400)` for validation errors
- No logging configuration exists yet — settings.py has no LOGGING dict
- `_broadcast()` pattern in views.py for real-time events — audit logging goes before broadcast

### Integration Points
- session/views.py — ReleaseResultView (scoring validation), SessionListCreateView, StartSessionView, EndSessionView, SessionResultView, ReleaseResultView (all need audit logging)
- main/services/email.py — wrap `resend.Emails.send()` in try/except
- main/views.py — RegisterView and ResendVerificationView call email function, need to handle warning response
- MockIT/settings.py — add LOGGING configuration

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>
