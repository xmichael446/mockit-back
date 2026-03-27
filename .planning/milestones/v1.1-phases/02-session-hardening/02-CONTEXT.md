# Phase 2: Session Hardening - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase centralizes session status validation into model methods, strengthens invite token generation, wraps multi-step operations in transactions, and makes presets immutable after session creation. Covers REF-01, REF-03, EDGE-01, EDGE-04.

</domain>

<decisions>
## Implementation Decisions

### State Machine Design
- State machine methods live on the IELTSMockSession model — `can_start()`, `can_end()`, `can_join()`, `can_ask_question()` etc.
- Invalid transitions raise `ValidationError` with a descriptive message — consistent with DRF, views catch and return 400
- Transition methods validate AND perform the status change — e.g., `start()` checks `can_start()` then sets `status = IN_PROGRESS` and `started_at`
- Cover all session-level status checks: start, end, join, ask_question, start_part, end_part — eliminate all scattered `if session.status != ...` checks from views

### Invite Token Format
- Format: `xxx-yyyy` (3 lowercase letters + dash + 4 lowercase letters) — matches Google Meet style
- Character set: lowercase a-z only, no digits
- Use `secrets` module for cryptographic security (e.g., `secrets.choice(string.ascii_lowercase)`)
- No migration for existing tokens — only new sessions get the new format, existing tokens continue to work
- Update max_length on model field if needed (current is 9, new format is 8 chars — fits)

### Transactions & Preset Immutability
- Wrap session start in `transaction.atomic()` — the multi-step operation (status update + room creation + token generation) that risks partial state
- On room creation failure: rollback — status stays SCHEDULED, no partial state in database
- Enforce preset immutability via model-level `save()` override on MockPreset — check `self.pk` and whether any IELTSMockSession references this preset
- Block preset deletion too if sessions exist — consistent with immutability rule (override `delete()`)

### Claude's Discretion
- Exact method signatures and internal logic flow
- How to handle the `_broadcast()` calls relative to transaction boundaries
- Whether to add `select_for_update()` for concurrent access protection
- Naming of helper methods for status validation

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `SessionStatus(IntegerChoices)` already defines SCHEDULED, IN_PROGRESS, COMPLETED, CANCELLED
- `_generate_invite_token()` function in session/models.py — needs replacement, not extension
- `TimestampedModel` base class provides created_at/updated_at

### Established Patterns
- Views use `if session.status != SessionStatus.X: return Response({"detail": "..."}, status=400)` — ~10+ occurrences to replace
- Model methods use `@property` for computed fields
- `_broadcast()` is called after state changes in views — must remain outside transaction to avoid broadcasting uncommitted state

### Integration Points
- session/models.py — IELTSMockSession gets state machine methods, MockPreset gets save/delete override
- session/views.py — all scattered status checks replaced with model method calls
- session/models.py:14 — `_generate_invite_token()` function to be replaced
- main/serializers.py:87 — has one status check that also needs updating

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>
