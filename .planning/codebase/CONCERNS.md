# Codebase Concerns

**Analysis Date:** 2026-03-27

## Security Issues

**Hardcoded Secrets in Settings:**
- Issue: `SECRET_KEY`, `HMS_APP_ACCESS_KEY`, `HMS_APP_SECRET`, `RESEND_API_KEY`, and database credentials are committed to `MockIT/settings.py` instead of using environment variables
- Files: `MockIT/settings.py` (lines 23, 104-106, 170, 114-122)
- Impact: Any attacker with repository access can compromise 100ms video rooms, email delivery, and database. Production credentials are exposed in version control history.
- Fix approach: Move all secrets to `.env` file (add to `.gitignore`), load via `python-decouple` or similar. Rotate all exposed credentials immediately.

**DEBUG = True in Production Settings:**
- Issue: `DEBUG = True` (line 26 in `MockIT/settings.py`) exposes detailed error pages with source code, environment variables, and database queries
- Files: `MockIT/settings.py:26`
- Impact: Debug pages leak sensitive information (stack traces, settings, query details). Must be `False` in production.
- Fix approach: Use environment variable: `DEBUG = os.getenv("DEBUG", "False") == "True"`

**CORS Misconfiguration:**
- Issue: `CORS_ALLOW_ALL_ORIGINS = True` (line 101 in `MockIT/settings.py`) allows any frontend to access the API
- Files: `MockIT/settings.py:101`
- Impact: Credentials can be stolen from any malicious site. Defeats CSRF protection.
- Fix approach: Replace with `CORS_ALLOWED_ORIGINS = ["https://mockit.live", ...]` using environment variable

**Weak Invite Token Generation:**
- Issue: Invite token uses `random.choices()` from `string` module (9 chars, 36 possibilities). Only ~47 bits of entropy.
- Files: `session/models.py:14-21`
- Impact: Invite tokens can be brute-forced. Attacker could scan tokens sequentially to find valid sessions.
- Fix approach: Use `secrets.token_urlsafe(6)` (~48 bits) or UUID4 (~128 bits). Current approach is marginally acceptable if invite expiry is enforced strictly.

---

## Critical Missing Test Coverage

**Zero Unit Tests:**
- Issue: Test files are completely empty: `session/tests.py`, `main/tests.py` contain only boilerplate
- Files: `session/tests.py:1-3`, `main/tests.py:1-3`
- Impact: No regression detection. Cannot safely refactor core logic (session lifecycle, scoring, permissions, auth). 1031-line `session/views.py` has zero test coverage.
- Priority: **HIGH** — All REST endpoints and WebSocket consumer need integration tests
- Suggested patterns:
  - Session lifecycle: create → accept invite → start → ask question → end
  - Scoring: verify band calculation formula, constraint validation (1-9 bands)
  - Permissions: examiner-only, candidate-only, participant checks
  - WebSocket: connection auth, event broadcast, participant filtering

---

## Performance & Scalability Concerns

**Inefficient Query Patterns in Large Collections:**
- Issue: `session/views.py:447` uses `.all()` without prefetch on preset topics: `getattr(session.preset, part_field).all()`. Also line 948 uses `result.scores.all()` without prior prefetch.
- Files: `session/views.py:447`, `session/views.py:948`
- Impact: If a session has many questions or many criterion scores, this creates unoptimized queries
- Fix approach: Ensure all M2M and reverse FK relations are prefetched before serialization. Line 447 should use `session.preset.part_1.all()` after prefetch in `_session_qs()`. Line 948 should be `result.scores` (already prefetched in line 877).

**InMemoryChannelLayer for Production:**
- Issue: `MockIT/settings.py:55-59` uses `InMemoryChannelLayer` — suitable for development, not scalable
- Files: `MockIT/settings.py:55-59`
- Impact: WebSocket broadcasts don't persist across server restarts. Multi-process deployments lose messages. Sessions can crash if memory grows.
- Fix approach: Use Redis channel layer in production: `channels_redis.core.RedisChannelLayer`. Keep InMemory only for development.

**Database Connection Credentials Hardcoded:**
- Issue: PostgreSQL credentials in `MockIT/settings.py:114-122` are hardcoded, not environment-variable-driven
- Files: `MockIT/settings.py:114-122`
- Impact: Cannot use different credentials for dev/staging/prod without editing settings.py. Exposes database user/pass in version control.
- Fix approach: Load from environment: `os.getenv("DB_NAME")`, `os.getenv("DB_USER")`, etc.

---

## Fragile Areas

**Session Status State Machine Has No Validation:**
- Issue: `session/views.py` has many manual checks like `if session.status != SessionStatus.IN_PROGRESS`, repeated across multiple endpoints (lines 204-208, 256-260, 291-295, 349-350, 390-391, etc.)
- Files: `session/views.py` (scattered)
- Impact: Easy to miss a status check, allowing invalid operations (e.g., end a part before session starts). No centralized state machine.
- Safe modification: Extract status validation into model method: `session.can_start()`, `session.can_end()`, `part.can_be_started()`. Add tests for all transitions.

**Band Scoring Calculation Not Fully Validated:**
- Issue: `session/models.py:182-186` computes overall band as `(sum(bands) // 2) / 2`. No validation that exactly 4 criterion scores exist before calculation.
- Files: `session/models.py:182-186`
- Impact: If fewer than 4 scores provided, returns `None` (silently). No error raised. Frontend may assume score exists.
- Fix approach: Add validation in `SessionResultWriteSerializer` to require all 4 criteria before allowing release. Enforce in `create()` method.

**WebSocket Authentication Uses Query String Token:**
- Issue: `session/consumers.py:64-73` parses token from query string. Tokens may leak in server logs, browser history, or referrer headers.
- Files: `session/consumers.py:64-73`
- Impact: Tokens can be compromised via log leakage. Query params are less secure than headers.
- Mitigation currently in place: Tokens are short-lived (1 hour in `session/services/hms.py:53`), tied to a specific user and room. Still, headers are preferred.
- Fix approach: Support both query string (for backward compat) and custom header (for security). Document header approach for frontend.

**No Rate Limiting on Critical Endpoints:**
- Issue: No rate limiting on `/api/auth/register/`, `/api/auth/guest-join/`, or `/api/sessions/accept-invite/`
- Files: `main/views.py`, `session/views.py`
- Impact: Account enumeration, invitation token brute-force, session creation spam
- Fix approach: Install `djangorestframework-throttling` or similar. Apply per-IP throttles: 5 registrations/hour, 50 invites/hour.

---

## Test Coverage Gaps

**Invite Token Expiry Not Tested:**
- Issue: `session/serializers.py:159-167` validates `invite_expires_at` and `invite_accepted_at`, but no test confirms expired tokens are rejected
- Files: `session/serializers.py:159-167`
- Risk: Expired invites may still be accepted if validation breaks
- Priority: **MEDIUM**

**Guest Join Flow Not Tested:**
- Issue: `main/views.py:150-180` creates guest user and sets as candidate, but no test verifies guest can join without registration, that is_guest flag persists, or guest can't use email-based features
- Files: `main/views.py:150-180`
- Risk: Guest account behavior may regress silently

**100ms Video Room Creation Errors:**
- Issue: `session/views.py:216-219` catches generic `Exception` from `create_room()` but doesn't test failure modes (API downtime, invalid template, rate limit)
- Files: `session/views.py:216-219`, `session/services/hms.py:22-38`
- Risk: Vague error messages (e.g., "Failed to create video room: ...") don't help users. No retry logic.
- Suggestion: Add specific error classes for `HMS_API_Error`, `HMS_Template_NotFound`, etc. Implement exponential backoff retry in `create_room()`.

---

## Known Limitations

**No Transaction Management:**
- Issue: Multi-step operations like session start (update status, create room, generate token) span multiple database queries without transaction wrapping
- Files: `session/views.py:195-237` (StartSessionView)
- Impact: If server crashes between status update and room creation, session state is inconsistent
- Fix approach: Wrap in `@transaction.atomic` decorator or use explicit `with transaction.atomic():`

**Email Delivery Not Verified:**
- Issue: `main/services/email.py:9-27` calls `resend.Emails.send()` but doesn't handle failures (network error, invalid key, bounces)
- Files: `main/services/email.py:9-27`
- Impact: Verification emails may silently fail; users can't verify accounts
- Fix approach: Wrap in try/except, log failures, optionally retry. Return success/failure to view.

**No Logging for Audit Trail:**
- Issue: No audit logs for critical actions (session creation, scoring, result release)
- Files: Throughout `session/views.py`
- Impact: Cannot trace who did what and when. Harder to debug issues or detect abuse.
- Fix approach: Add `logging.info()` calls or use Django admin's LogEntry model for sensitive actions.

---

## Dependencies & Environment Concerns

**Django 5.2 Early Adoption:**
- Stack: Django 5.2.11 (released Dec 2024, very new)
- Risk: Limited community testing, potential edge cases. LTS versions (4.2) are more battle-tested.
- Current status: Likely acceptable since no critical bugs reported so far. Monitor for patch releases.

**Channels 4.x Lowercase Consumer:**
- Note: Code uses `AsyncWebsocketConsumer` (lowercase 's') correctly per MEMORY.md. Django Channels 4.x changed naming from `AsyncWebSocketConsumer` in Channels 3.x.
- Impact: None currently; documented in MEMORY.md.

---

## Session Logic Edge Cases

**Session Can't Be Started Without Candidate:**
- Issue: `session/views.py:210-214` checks `if session.candidate is None` and rejects start. But guest-join flow (`main/views.py:170`) sets candidate immediately.
- Files: `session/views.py:210-214`, `main/views.py:170`
- Impact: Works as intended (prevents examiner from starting before candidate joins), but flow complexity. Not a bug, but fragile assumption.

**Preset Can Be Modified After Session Uses It:**
- Issue: MockPreset can be edited after a session has been created from it. No snapshot of topics taken.
- Files: `session/models.py:68`
- Impact: If examiner edits preset after creating session, examiner might expect old topics when session runs
- Fix approach: Snapshot preset topics into session_part records on session start, or make preset immutable once a session is created.

---

## UI/Documentation Gaps

**No API Documentation:**
- Issue: REST API endpoints documented in `docs/api.md` (per CLAUDE.md), but frontend integration points are unclear
- Files: `docs/api.md` (exists but not audited)
- Impact: Frontend and backend can drift. Unclear which endpoints return WebSocket event subscriptions vs. one-shot responses.

**No WebSocket Client Example:**
- Issue: WebSocket consumer exists (`session/consumers.py`) but no example client in codebase or docs
- Files: None
- Impact: Frontend developers must reverse-engineer event schema from code

---

## Summary: Priority Order for Fixes

1. **CRITICAL**: Move hardcoded secrets to environment variables (security audit failure)
2. **CRITICAL**: Set `DEBUG = False` in production (information leak)
3. **HIGH**: Add unit/integration tests for session lifecycle and scoring logic
4. **HIGH**: Fix CORS to allowlist specific origins only
5. **MEDIUM**: Add rate limiting to auth/invite endpoints
6. **MEDIUM**: Switch to Redis channel layer for production
7. **MEDIUM**: Document WebSocket event schema and provide client example
8. **LOW**: Refactor repeated status checks into state machine methods
9. **LOW**: Add audit logging for critical operations

---

*Concerns audit: 2026-03-27*
