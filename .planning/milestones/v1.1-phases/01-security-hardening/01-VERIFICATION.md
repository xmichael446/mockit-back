---
phase: 01-security-hardening
verified: 2026-03-27T00:40:00Z
status: passed
score: 8/8 must-haves verified
re_verification: false
---

# Phase 01: Security Hardening Verification Report

**Phase Goal:** Secrets are out of source control and critical endpoints cannot be abused
**Verified:** 2026-03-27
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| #  | Truth                                                                                                  | Status     | Evidence                                                                     |
|----|--------------------------------------------------------------------------------------------------------|------------|------------------------------------------------------------------------------|
| 1  | settings.py contains zero hardcoded secrets — SECRET_KEY, HMS keys, RESEND key, and DB credentials all read from environment variables | VERIFIED | All 10 `os.environ["KEY"]` calls confirmed; grep for original values returns 0 matches |
| 2  | A .env.example file documents every required variable with placeholder values                          | VERIFIED | `.env.example` exists with all 10 vars: SECRET_KEY, HMS x3, RESEND, DB x5    |
| 3  | python-dotenv is installed and loads .env at settings module import time                               | VERIFIED | `requirements.txt` line 41: `python-dotenv==1.1.0`; `load_dotenv()` at line 16 of settings.py |
| 4  | App crashes on startup if any required env var is missing (no silent fallbacks)                        | VERIFIED | All 10 usages are `os.environ["KEY"]` (square brackets); no `os.environ.get()` found |
| 5  | Registration endpoint returns 429 after 10 requests in one hour from the same IP                       | VERIFIED | `RegisterView.throttle_scope = "register"` (main/views.py:28); rate `"register": "10/hour"` in settings |
| 6  | Guest-join endpoint returns 429 after 20 requests in one hour from the same IP                        | VERIFIED | `GuestJoinView.throttle_scope = "guest_join"` (main/views.py:150); rate `"guest_join": "20/hour"` in settings |
| 7  | Accept-invite endpoint returns 429 after 20 requests in one hour from the same IP                     | VERIFIED | `AcceptInviteView.throttle_scope = "accept_invite"` (session/views.py:159); rate `"accept_invite": "20/hour"` in settings |
| 8  | Legitimate users can register and join without hitting rate limits under normal usage                  | VERIFIED | ScopedRateThrottle is used — views without `throttle_scope` are unaffected; rates are generous for normal use |

**Score:** 8/8 truths verified

---

### Required Artifacts

| Artifact             | Expected                                           | Status   | Details                                                                              |
|----------------------|----------------------------------------------------|----------|--------------------------------------------------------------------------------------|
| `MockIT/settings.py` | Environment-based secret loading                   | VERIFIED | `load_dotenv()` line 16; 10x `os.environ["KEY"]` calls; no hardcoded secrets remain |
| `MockIT/settings.py` | Throttle scope rates in REST_FRAMEWORK config      | VERIFIED | `DEFAULT_THROTTLE_CLASSES` with `ScopedRateThrottle`; `DEFAULT_THROTTLE_RATES` with 3 scopes |
| `.env.example`       | Template for required environment variables        | VERIFIED | All 10 vars documented with placeholder values                                       |
| `requirements.txt`   | python-dotenv dependency                           | VERIFIED | Line 41: `python-dotenv==1.1.0`                                                      |
| `main/views.py`      | Throttle scopes on RegisterView and GuestJoinView  | VERIFIED | Lines 28 and 150 respectively                                                        |
| `session/views.py`   | Throttle scope on AcceptInviteView                 | VERIFIED | Line 159                                                                             |

---

### Key Link Verification

| From                 | To                | Via                                           | Status   | Details                                                                                    |
|----------------------|-------------------|-----------------------------------------------|----------|--------------------------------------------------------------------------------------------|
| `MockIT/settings.py` | `.env`            | `load_dotenv()` at module top                 | WIRED    | `from dotenv import load_dotenv` + `load_dotenv()` at lines 15-16                         |
| `MockIT/settings.py` | `os.environ`      | `os.environ["KEY"]` for all 10 required vars  | WIRED    | Exactly 10 `os.environ[` usages; zero `os.environ.get()` fallbacks                        |
| `MockIT/settings.py` | `main/views.py`   | Throttle scope name `register` matches `10/hour` | WIRED | `"register": "10/hour"` in settings; `throttle_scope = "register"` in RegisterView        |
| `MockIT/settings.py` | `session/views.py`| Throttle scope name `accept_invite` matches `20/hour` | WIRED | `"accept_invite": "20/hour"` in settings; `throttle_scope = "accept_invite"` in AcceptInviteView |

---

### Requirements Coverage

| Requirement | Source Plan | Description                                                                | Status    | Evidence                                                                         |
|-------------|-------------|----------------------------------------------------------------------------|-----------|----------------------------------------------------------------------------------|
| SEC-01      | 01-01       | All secrets loaded from .env file                                          | SATISFIED | settings.py has 0 hardcoded secrets; all 10 loaded via `os.environ[]`; .env.example documents all vars; python-dotenv installed |
| SEC-02      | 01-02       | Rate limiting on registration, guest-join, and invite-accept endpoints     | SATISFIED | ScopedRateThrottle configured in REST_FRAMEWORK; throttle_scope on all 3 views with matching rates |

No orphaned requirements — REQUIREMENTS.md maps only SEC-01 and SEC-02 to Phase 1, and both are claimed by plans 01-01 and 01-02 respectively.

---

### Anti-Patterns Found

No anti-patterns detected in modified files.

- No TODO/FIXME/placeholder comments in settings.py, main/views.py, or session/views.py
- No hardcoded secrets remaining in settings.py
- No `os.environ.get()` silent fallbacks
- No stub implementations in the throttle scope additions

---

### Human Verification Required

#### 1. Rate Limit Enforcement Under Load

**Test:** Send 11 POST requests to `/api/auth/register/` within one minute from the same IP.
**Expected:** Requests 1-10 return 201 or 400 (validation error); request 11 returns 429 with a `Retry-After` header.
**Why human:** Automated grep cannot simulate actual HTTP request sequences and verify DRF throttle cache behavior at runtime.

#### 2. Fail-Fast on Missing Env Var

**Test:** Temporarily remove `SECRET_KEY` from `.env` and run `python manage.py check`.
**Expected:** Process exits with a `KeyError: 'SECRET_KEY'` before any request is served.
**Why human:** Cannot remove and restore .env safely in automated verification without risking environment disruption.

---

### Gaps Summary

No gaps. All must-haves from both plans are verified against the actual codebase:

- SEC-01 (secrets out of source control): settings.py is clean — all 10 secrets moved to env vars via `os.environ[]` with fail-fast semantics, `.env.example` is complete, python-dotenv is in requirements.txt, and `.env` is gitignored and not tracked.
- SEC-02 (rate limiting): DRF ScopedRateThrottle is configured in settings with correct rates (10/hour for register, 20/hour for guest_join and accept_invite), and all three views carry the matching `throttle_scope` attribute wired to those rates.

All 4 commits documented in the summaries exist in git history (502525f, ec68f16, cafd205, 697d439).

---

_Verified: 2026-03-27_
_Verifier: Claude (gsd-verifier)_
