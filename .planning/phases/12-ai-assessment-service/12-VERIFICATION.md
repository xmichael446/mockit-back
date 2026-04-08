---
phase: 12-ai-assessment-service
verified: 2026-04-07T00:00:00Z
status: passed
score: 8/8 must-haves verified
re_verification: false
---

# Phase 12: AI Assessment Service Verification Report

**Phase Goal:** The background job generates IELTS band scores and actionable feedback for all four criteria using Claude API
**Verified:** 2026-04-07
**Status:** passed
**Re-verification:** No — initial verification

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | `assess_session(job)` calls Claude API with transcript and session questions and returns 4 criterion dicts | VERIFIED | `session/services/assessment.py` L207-213: `client.messages.create(model="claude-sonnet-4-20250514", ...)` with user_message built from questions + transcript; returns list of 4 dicts L242 |
| 2 | Each dict contains criterion enum int, band (1-9), and feedback string | VERIFIED | `assessment.py` L242: `result.append({"criterion": criterion_int, "band": band, "feedback": feedback})` |
| 3 | Missing criteria in Claude response raises RuntimeError (all-or-nothing) | VERIFIED | `assessment.py` L228-231: `missing = REQUIRED_KEYS - set(data.keys()); if missing: raise RuntimeError(...)` |
| 4 | ANTHROPIC_API_KEY is configurable via Django settings | VERIFIED | `MockIT/settings.py` L139: `ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")` |
| 5 | `run_ai_feedback` task calls `assess_session` after transcription and creates 4 CriterionScore records with source=AI | VERIFIED | `session/tasks.py` L25-39: deferred import, `assess_session(job)`, `bulk_create(...)` with `source=ScoreSource.AI` |
| 6 | Each CriterionScore has band 1-9 and feedback text | VERIFIED | `tasks.py` L30-38: `band=entry["band"], feedback=entry["feedback"]`; band validated 1-9 in `assess_session` before return |
| 7 | Claude API error causes job to transition to FAILED with error_message | VERIFIED | `tasks.py` L46-52: outer `except Exception as exc` sets `job.status = FAILED`, `job.error_message = str(exc)` |
| 8 | Session questions are included in the Claude API prompt | VERIFIED | `assessment.py` L183-199: queries `SessionQuestion.objects.filter(session_part__session=job.session)` with `select_related`, formats as `[Part N] question text` lines |

**Score:** 8/8 truths verified

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `session/services/assessment.py` | Claude API assessment service | VERIFIED | 249 lines; exports `assess_session`, `CRITERION_MAP`, `REQUIRED_KEYS`, `TOOL_DEFINITION`, `SYSTEM_PROMPT` |
| `requirements.txt` | anthropic SDK dependency | VERIFIED | Contains `anthropic==0.91.0` at line 46 |
| `MockIT/settings.py` | ANTHROPIC_API_KEY setting | VERIFIED | `ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")` at line 139 |
| `session/tasks.py` | AI scoring integration in run_ai_feedback | VERIFIED | Contains `assess_session`, `bulk_create`, `get_or_create`, `source=ScoreSource.AI` |
| `session/tests.py` | Unit and integration tests for AI assessment | VERIFIED | Contains `AssessmentServiceTests` class and all required test methods |

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `session/services/assessment.py` | `anthropic.Anthropic` | deferred `import anthropic` inside `assess_session` | VERIFIED | L172-177: `try: import anthropic except ImportError: raise RuntimeError(...)` |
| `session/services/assessment.py` | `session.models.SessionQuestion` | query `SessionQuestion.objects.filter` | VERIFIED | L184: `SessionQuestion.objects.filter(session_part__session=job.session).select_related(...)` |
| `session/tasks.py` | `session/services/assessment.py` | deferred import of `assess_session` | VERIFIED | L25: `from session.services.assessment import assess_session` inside try block |
| `session/tasks.py` | `CriterionScore.objects.bulk_create` | bulk create 4 AI scores | VERIFIED | L30: `CriterionScore.objects.bulk_create([...])` |
| `session/tasks.py` | `SessionResult.objects.get_or_create` | get or create session result for FK | VERIFIED | L29: `result, _ = SessionResult.objects.get_or_create(session=job.session)` |

### Data-Flow Trace (Level 4)

| Artifact | Data Variable | Source | Produces Real Data | Status |
|----------|---------------|--------|--------------------|--------|
| `session/tasks.py` | `scores_data` | `assess_session(job)` -> Claude API | Yes — live API call returning validated criterion dicts | FLOWING |
| `session/tasks.py` | `result` (SessionResult) | `SessionResult.objects.get_or_create(session=job.session)` | Yes — real DB query | FLOWING |
| `session/tasks.py` | CriterionScore records | `CriterionScore.objects.bulk_create(...)` | Yes — bulk insert of 4 records | FLOWING |

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| `assess_session` importable from module | `python -c "from session.services.assessment import assess_session, CRITERION_MAP, REQUIRED_KEYS, TOOL_DEFINITION, SYSTEM_PROMPT; print('OK')"` | OK | PASS |
| `anthropic` SDK importable | `python -c "import anthropic; print(anthropic.__version__)"` | 0.91.0 | PASS |
| All 13 AI assessment tests pass | `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test session.tests.RunAIFeedbackTaskTests session.tests.AssessmentServiceTests -v2` | Ran 13 tests in 7.981s — OK | PASS |

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|-------------|-------------|--------|----------|
| AIAS-02 | 12-01, 12-02 | AI generates band scores (1-9) for each IELTS criterion (FC, GRA, LR, PR) | SATISFIED | `assess_session` returns `{"criterion": int, "band": int, ...}` for all 4; `tasks.py` bulk_creates 4 CriterionScore records; `test_task_creates_ai_scores` asserts count==4 with correct bands |
| AIAS-03 | 12-01, 12-02 | AI generates 3-4 sentence actionable feedback per criterion | SATISFIED | SYSTEM_PROMPT explicitly instructs "3-4 sentences of specific, actionable feedback"; TOOL_DEFINITION `feedback` field required in each criterion object; `test_task_stores_feedback` asserts non-empty feedback stored |
| AIAS-04 | 12-01, 12-02 | AI prompt includes actual session questions for context-aware assessment | SATISFIED | `assess_session` queries `SessionQuestion` with `select_related`, formats as `[Part N] question text` lines, includes in user message before transcript; `test_builds_question_context` asserts both question texts and `[Part 1]` prefix appear in API call |

No orphaned requirements — REQUIREMENTS.md traceability table maps AIAS-02, AIAS-03, AIAS-04 exclusively to Phase 12, all claimed and verified.

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| None | — | — | — | — |

No TODO/FIXME/placeholder patterns found in phase-modified files. No empty implementations. No stub returns. The comment at `tasks.py` L24 ("Phase 12: AI scoring via Claude API") is documentation, not a placeholder — it is followed by a full implementation.

### Human Verification Required

None. All goal truths are verifiable programmatically. The Claude API call itself cannot be exercised in tests without a live key, but the wiring (deferred import, client construction, response parsing, DB persistence) is fully covered by unit tests using `patch.dict(sys.modules)` and mock responses.

### Gaps Summary

No gaps. All 8 observable truths verified. All 5 artifacts exist, are substantive, and are wired. All 5 key links confirmed. All 3 requirement IDs (AIAS-02, AIAS-03, AIAS-04) satisfied with test evidence. 13 tests pass green.

---

_Verified: 2026-04-07_
_Verifier: Claude (gsd-verifier)_
