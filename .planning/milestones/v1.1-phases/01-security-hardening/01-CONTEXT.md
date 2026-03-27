# Phase 1: Security Hardening - Context

**Gathered:** 2026-03-27
**Status:** Ready for planning

<domain>
## Phase Boundary

This phase delivers SEC-01 (secrets to env vars) and SEC-02 (rate limiting on auth/invite endpoints). No session logic, no refactoring, no new features — purely hardening existing configuration and adding abuse protection.

</domain>

<decisions>
## Implementation Decisions

### Environment Configuration
- Use python-dotenv for .env loading — lightweight, no magic, widely adopted
- Crash on startup when required env vars are missing — fail fast, no silent fallbacks with dev defaults
- Move secrets only to .env: SECRET_KEY, HMS_APP_ACCESS_KEY, HMS_APP_SECRET, HMS_TEMPLATE_ID, RESEND_API_KEY, DB NAME/USER/PASSWORD/HOST/PORT — DEBUG, CORS, ALLOWED_HOSTS stay hardcoded (out of scope per deferred SEC-03/SEC-04)
- Include .env.example template documenting all required vars for fresh clones

### Rate Limiting
- Use DRF built-in throttling (ScopedRateThrottle) — already in stack, zero new dependencies
- Differentiated thresholds: register 10/hour, guest-join 20/hour, accept-invite 20/hour — register is one-shot; join/accept need headroom for shared IPs (classrooms)
- Scope per IP using AnonRateThrottle — these are pre-auth endpoints, no user identity available
- Standard DRF 429 response with retry-after header — no custom error formatting needed

### Claude's Discretion
- Exact .env variable naming conventions
- Order of settings.py refactoring
- Whether to use os.environ.get() or dotenv's specific API

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- MockIT/settings.py already has `import os` — partial groundwork for env vars
- REST_FRAMEWORK config dict in settings.py — throttle classes can be added here
- DRF's built-in throttling classes (AnonRateThrottle, ScopedRateThrottle) — no new deps needed

### Established Patterns
- Settings follow standard Django layout with grouped sections (DB, auth, middleware, etc.)
- Views use class-based APIView pattern — throttle_classes can be set per-view
- Authentication uses DRF TokenAuthentication configured globally in REST_FRAMEWORK dict

### Integration Points
- MockIT/settings.py — all env var changes and throttle config live here
- main/views.py — RegisterView (line 21), GuestJoinView (line 132) need throttle_classes
- session/views.py — AcceptInviteView (line 154) needs throttle_classes
- .gitignore — must include .env
- requirements.txt — add python-dotenv

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>
