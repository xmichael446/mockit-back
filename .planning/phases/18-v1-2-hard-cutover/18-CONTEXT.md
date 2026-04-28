---
phase: 18
phase_name: v1.2 Hard Cutover
gathered: 2026-04-29
status: ready_for_planning
mode: auto
---

# Phase 18: v1.2 Hard Cutover - Context

**Gathered:** 2026-04-29
**Status:** Ready for planning
**Mode:** Auto-generated (--auto, recommended defaults)

<domain>
## Phase Boundary

The v1.2 scheduling app is cleanly retired before v1.5 booking work begins:

1. **PENDING SessionRequest candidates** receive an apology email explaining the cutover and asking them to rebook once the new Google Calendar flow ships.
2. **scheduling tables** are dropped via a destructive migration: `scheduling_availabilityslot`, `scheduling_blockeddate`, `scheduling_sessionrequest`.
3. **scheduling routes** removed from `MockIT/urls.py` (`api/scheduling/` include) and `INSTALLED_APPS` (`scheduling.apps.SchedulingConfig`).
4. **Cross-app import dependency** in `session/views.py` — verified during scout that no current import exists; the carry-forward note in STATE.md anticipated one. Plan must confirm and document the absence.
5. **scheduling/ source tree** is deleted entirely once the app is unregistered and migrations applied.

In scope: apology email, destructive migration, app/URL removal, code deletion, docs/api scrub of v1.2 scheduling references.

Out of scope: anything related to the new v1.5 Google booking surface (Phases 19-24).

</domain>

<decisions>
## Implementation Decisions

### Apology Email to PENDING Candidates
- **Trigger:** during the destructive migration, gather all `SessionRequest` rows in `Status.PENDING` and `Status.ACCEPTED` (both effectively still-pending from the candidate's POV) and send one email per candidate (deduplicated by candidate email).
- **Sender:** existing transactional email backend (no new infra). Subject: "Update on your MockIT mock exam booking". Tone: apologetic, action-oriented — explains the booking system is being rebuilt around Google Calendar, asks candidates to wait for an email invitation from their examiner once the new system is live, no further action required from them now.
- **Failure handling:** email send is best-effort (returns bool, same discipline as v1.3 carry-forward). Migration logs send failures but does NOT roll back — the table drop must succeed even if SMTP is flaky. Failed sends are written to a JSON manifest file `apology_email_failures.json` in the project root for manual follow-up.
- **Idempotency:** migration must be idempotent — if re-run on a fresh DB or after partial failure, should not crash. Use `RunPython(noop_reverse=True)` style.

### Migration Strategy
- **Single combined migration** (`scheduling/migrations/0003_drop_all_and_notify.py`):
  1. RunPython: collect candidate rows, send apology emails, log failures.
  2. DeleteModel for SessionRequest, BlockedDate, AvailabilitySlot (in dependency order).
- Migration runs within a single `transaction.atomic` block guarding only the email collection + DB writes — emails sent AFTER atomic exit (carry-forward discipline from v1.2).
- After successful migration, `scheduling` app config and `api/scheduling/` URL include are removed in the SAME commit as deleting the `scheduling/` directory.
- One squash commit per logical step (migration vs app removal) for review clarity.

### App / Code Deletion Sequence
1. Apply migration on dev — verify tables gone, emails sent (via Django console backend in dev).
2. Remove `'scheduling.apps.SchedulingConfig'` from `INSTALLED_APPS`.
3. Remove `path("api/scheduling/", include("scheduling.urls"))` from `MockIT/urls.py`.
4. Delete `scheduling/` directory entirely (including `tests.py`, `services/`, etc.).
5. Run full test suite — all session/main/questions/results/usage/assessment tests must still pass.

### Verification of session/views.py Import
- Plan must explicitly grep `from scheduling`/`import scheduling` across all non-scheduling apps before declaring the cutover complete.
- If any imports surface (none found during this scout), they are removed in the same migration commit.
- Document the result in the plan SUMMARY: "verified no cross-app imports of scheduling/ before deletion."

### Documentation Cleanup
- Remove `docs/api/scheduling.md` (or equivalent v1.2 scheduling API reference) entirely.
- Update `docs/api/index.md` to drop the scheduling entry.
- No deprecation notice in docs — hard cutover, not a graceful retirement.
- Update `CLAUDE.md` if it references scheduling app architecture (none currently).

### Claude's Discretion
- Exact apology email body wording (one paragraph, friendly, no marketing fluff).
- Whether to use `EmailMultiAlternatives` (HTML + plaintext) or plaintext-only — recommend plaintext-only for simplicity and deliverability on a one-shot apology.
- Test fixtures for the migration (use Django's `migrator` test helper or schema-only test).
- Whether to keep `scheduling/tests.py` test classes around as historical reference (recommend: delete with the rest of the app — git history is enough).

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `main/services/email.py` (or equivalent) — existing transactional email helper using bool-return discipline. Reuse for apology send.
- `TimestampedModel` base class — only used internally by scheduling models being dropped.
- Console email backend in dev (`MockIT/settings.py`) — sufficient for migration testing.

### Established Patterns
- Migrations use `transaction.atomic` plus post-atomic side effects (carry-forward from v1.2).
- Email sends return bool; callers decide failure handling.
- Tests run via `DJANGO_SETTINGS_MODULE=MockIT.settings_test` (in-memory SQLite).

### Integration Points
- `MockIT/urls.py` — line 27 includes `api/scheduling/`; remove.
- `MockIT/settings.py` — line 54 lists `'scheduling.apps.SchedulingConfig'`; remove.
- No FK references to scheduling models from other apps (verified by scout — `grep "from scheduling"` outside scheduling/ returns empty).

### Files To Delete
- `scheduling/` — entire directory (8 .py files + migrations/ + services/).
- Migration file lives in `scheduling/migrations/0003_*.py` until app is removed; afterwards the migration history is implicitly orphaned (we have already applied it; Django will not complain because the app is gone from `INSTALLED_APPS` and the migration table simply retains the records — no problem unless someone re-runs `migrate` on a fresh DB. For new envs this is acceptable since no tables need to exist.)
- For the fresh-DB case, after the cutover the migration is no longer needed because the tables won't be created in the first place — clean.

</code_context>

<specifics>
## Specific Ideas

- The apology email is a one-time blast; do NOT add any opt-out machinery (these candidates currently have no opt-out preference and will receive at most this one email plus their existing transactional emails for sessions they already took).
- Do NOT cancel ACCEPTED requests programmatically — examiners may have already conducted those sessions live. Just email candidates to inform them future bookings move to a new system.
- No schema migration on `IELTSMockSession` — `session_request` reverse OneToOne relation auto-clears when SessionRequest model is deleted (it's a SET_NULL FK pointing INTO scheduling, but the FK is on SessionRequest, so dropping that table dissolves the relation).

</specifics>

<deferred>
## Deferred Ideas

None — phase scope is precisely defined by ROADMAP.md and STATE.md.

</deferred>
