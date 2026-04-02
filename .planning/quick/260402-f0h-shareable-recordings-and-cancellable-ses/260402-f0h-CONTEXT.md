# Quick Task 260402-f0h: Shareable recordings and cancellable sessions - Context

**Gathered:** 2026-04-02
**Status:** Ready for planning

<domain>
## Task Boundary

Two features:
1. **Shareable recordings** — examiner or candidate can generate a public share link for a completed session's recording. Anonymous viewers see recording with timeline, band scores (no feedback text), and participant profile info.
2. **Cancellable sessions** — examiner can cancel sessions where the invite hasn't been accepted yet. Cancelled sessions don't count toward max_sessions.

</domain>

<decisions>
## Implementation Decisions

### Share token model
- Separate model (e.g. `SharedRecording` or `SessionShare`) with its own token, linked to the session
- Single shared link per session (not per-user). Either examiner or candidate can generate it.
- Approval workflow deferred to backlog

### Data exposed to anonymous viewers
- Recording audio + full timeline (parts, questions, follow-ups with offsets)
- Band scores: 4 criterion bands (FC, GRA, LR, PR) + overall band. NO feedback text, NO overall_feedback
- Profile info: full name, profile picture, bio for both examiner and candidate
- Examiner credentials (their own IELTS scores) — included in response but frontend only shows names for now
- Examiner notes during session: NOT exposed

### Share availability
- Sharing only possible after results are released (`is_released = True`)

### API design
- `POST /api/sessions/<pk>/share/` — generates the share token (authenticated, examiner or candidate of the session)
- `GET /api/sessions/shared/<share_token>/` — public endpoint, no auth required, returns all shareable data in one response

### Cancellation rules
- Only sessions with status=SCHEDULED AND candidate=None (invite not accepted) can be cancelled
- Sets status to CANCELLED (already exists as SessionStatus.CANCELLED = 4)

### max_sessions fix
- Change session count query to exclude CANCELLED sessions: `.exclude(status=SessionStatus.CANCELLED)`

### Cancellation side effects
- Broadcast WebSocket event `session.cancelled` on cancellation
- Invalidate/delete the invite token on cancellation

</decisions>

<specifics>
## Specific Ideas

- Share token can follow similar pattern to invite_token (short, URL-safe string)
- The `SessionShare` model needs: session FK, share_token, created_by FK, created_at
- For cancellation, add `can_cancel()` guard and `cancel()` transition to IELTSMockSession model

</specifics>
