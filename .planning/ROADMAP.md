# Roadmap: MockIT v1.1 — Clean-up, Security & Edge Cases

**Milestone:** v1.1
**Goal:** Harden the codebase for production readiness — fix security vulnerabilities, handle edge cases, and refactor fragile patterns.
**Requirements:** 9 total (SEC-01, SEC-02, REF-01, REF-02, REF-03, EDGE-01, EDGE-02, EDGE-03, EDGE-04)
**Coverage:** 9/9

---

## Phases

- [x] **Phase 1: Security Hardening** - Move secrets out of source control and protect critical endpoints from abuse (completed 2026-03-27)
- [ ] **Phase 2: Session Hardening** - Centralize status validation, strengthen invite tokens, and make multi-step operations atomic
- [ ] **Phase 3: Data Integrity and Observability** - Enforce scoring completeness, handle email failures gracefully, and add audit logging

---

## Phase Details

### Phase 1: Security Hardening

**Goal**: Secrets are out of source control and critical endpoints cannot be abused
**Depends on**: Nothing (independent)
**Requirements**: SEC-01, SEC-02
**Success Criteria** (what must be TRUE):
  1. The settings.py file contains no hardcoded credentials — SECRET_KEY, HMS keys, RESEND key, and DB credentials all read from environment variables
  2. A `.env` file exists (and is gitignored) containing all required secrets; the app starts correctly from a fresh clone with only this file
  3. Registration, guest-join, and accept-invite endpoints return 429 when called more than their configured threshold within the rate window
  4. Legitimate users can still register and join without hitting rate limits under normal usage
**Plans:** 2/2 plans complete

Plans:
- [x] 01-01-PLAN.md — Move secrets from settings.py to .env via python-dotenv
- [x] 01-02-PLAN.md — Add rate limiting to registration, guest-join, and accept-invite endpoints

### Phase 2: Session Hardening

**Goal**: Session status transitions are centralized and validated, invite tokens are cryptographically stronger, and multi-step operations are atomic
**Depends on**: Phase 1
**Requirements**: REF-01, REF-03, EDGE-01, EDGE-04
**Success Criteria** (what must be TRUE):
  1. Starting, ending, and conducting a session all enforce status rules through model methods (can_start, can_end, etc.) — no scattered inline `if session.status != ...` checks in views
  2. Invalid state transitions (e.g., ending a session that is not in progress) return a 400 with a clear error message
  3. New sessions are created with letter-only invite tokens in Google Meet format (e.g., `xyz-abcd`) rather than alphanumeric tokens
  4. If the server crashes between status update and room creation during session start, the database is left in a consistent state (no partial updates)
  5. A MockPreset that has at least one session created from it cannot be modified — the API returns a 400 if an examiner attempts to edit it
**Plans:** 2 plans

Plans:
- [x] 02-01-PLAN.md — Add state machine methods, invite token, and preset immutability to models
- [x] 02-02-PLAN.md — Replace inline status checks in views with model methods and wrap session start in transaction.atomic()

### Phase 3: Data Integrity and Observability

**Goal**: Scoring requires all criteria, email failures surface explicitly, and critical actions leave an audit trail
**Depends on**: Phase 2
**Requirements**: REF-02, EDGE-02, EDGE-03
**Success Criteria** (what must be TRUE):
  1. Releasing a result without all 4 criterion scores (FC, GRA, LR, PR) returns a 400 error — the release cannot proceed with incomplete scoring
  2. Email delivery failures (network error, invalid API key, bounce) are caught and logged — no silent failures; the view returns a meaningful error or warning rather than silently continuing
  3. Session creation, session start, session end, result submission, and result release all produce a log entry that identifies the acting user, the session ID, and the timestamp
  4. Audit log entries are visible in the Django admin or application logs without requiring direct database access
**Plans:** 2 plans

Plans:
- [ ] 03-01-PLAN.md — Enforce scoring completeness on release and handle email failures gracefully
- [ ] 03-02-PLAN.md — Add structured audit logging to critical session actions

---

## Progress

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Security Hardening | 2/2 | Complete   | 2026-03-27 |
| 2. Session Hardening | 0/2 | Not started | - |
| 3. Data Integrity and Observability | 0/2 | Not started | - |
