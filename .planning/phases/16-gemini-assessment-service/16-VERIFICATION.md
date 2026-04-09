---
phase: 16-gemini-assessment-service
verified: 2026-04-09T13:18:13Z
status: passed
score: 5/5 must-haves verified
re_verification: false
---

# Phase 16: Gemini Assessment Service Verification Report

**Phase Goal:** The AI feedback pipeline produces IELTS band scores and a transcript by sending session audio directly to Gemini Pro in a single call
**Verified:** 2026-04-09T13:18:13Z
**Status:** passed
**Re-verification:** No — initial verification

---

## Goal Achievement

### Observable Truths

| # | Truth | Status | Evidence |
|---|-------|--------|----------|
| 1 | assess_session uploads session audio to Gemini Files API and calls generate_content with structured output | VERIFIED | `client.files.upload(file=audio_path, ...)` at line 157, `client.models.generate_content(model="gemini-2.5-pro", contents=[uploaded_file, user_prompt], config=config)` at line 174 |
| 2 | Gemini response is parsed via Pydantic schema with band scores validated 1-9 for all four criteria | VERIFIED | `CriterionAssessment` with `band: int = Field(ge=1, le=9)` at lines 21-23; `IELTSAssessment.model_validate_json(response.text)` at line 196 |
| 3 | Safety filter rejections raise RuntimeError with clear finish_reason message | VERIFIED | `if candidate.finish_reason != types.FinishReason.STOP: raise RuntimeError(f"Gemini content blocked: finish_reason={candidate.finish_reason}")` at lines 189-192 |
| 4 | Transcript is extracted from Gemini response and returned alongside scores | VERIFIED | `transcript = parsed.transcript` at line 209; `return scores, transcript` at line 217; function signature is `-> tuple[list[dict], str]` |
| 5 | System prompt contains full IELTS band descriptors for all 4 criteria with audio-specific pronunciation/intonation/rhythm instructions | VERIFIED | SYSTEM_PROMPT (lines 36-98) contains all four criteria sections plus "Audio-Specific Pronunciation Assessment" block covering Intonation patterns, Stress placement, Connected speech, Rhythm and pacing |

**Score:** 5/5 truths verified

---

### Required Artifacts

| Artifact | Expected | Status | Details |
|----------|----------|--------|---------|
| `session/services/assessment.py` | Gemini-based IELTS assessment service containing IELTSAssessment | VERIFIED | 218 lines, fully substantive. Contains `CriterionAssessment`, `IELTSAssessment`, `SYSTEM_PROMPT`, `CRITERION_MAP`, `assess_session`. Zero anthropic/tool_use references. |
| `session/tests.py` | Gemini-aware AssessmentServiceTests containing test_calls_gemini_with_audio | VERIFIED | All 7 test methods present (lines 1521-1650). Class `AssessmentServiceTests` inherits `TestCase`. Uses `@patch("google.genai.Client")` mock pattern. |

---

### Key Link Verification

| From | To | Via | Status | Details |
|------|----|-----|--------|---------|
| `session/services/assessment.py` | `google.genai` | deferred `from google import genai` inside `assess_session` | WIRED | Line 122 — inside function body, deferred correctly |
| `session/services/assessment.py` | `session/models.py` | `SessionQuestion.objects.filter(session_part__session=job.session)` | WIRED | Line 134 — query with select_related, ordered by part and order |
| `session/tests.py` | `session/services/assessment.py` | `from session.services.assessment import assess_session` | WIRED | Lines 1523, 1543 — direct import inside each test method |

---

### Data-Flow Trace (Level 4)

`assess_session` is a service function (not a rendering component), so the data-flow trace focuses on the pipeline end-to-end rather than state-to-render.

| Step | Data Variable | Source | Produces Real Data | Status |
|------|---------------|--------|--------------------|--------|
| Audio path | `audio_path` | `job.session.recording.audio_file.path` | Yes — real FileField path from DB | FLOWING |
| Question context | `questions_text` | `SessionQuestion.objects.filter(...)` | Yes — DB query with select_related | FLOWING |
| Gemini response | `response` | `client.models.generate_content(...)` with uploaded audio + prompt | Yes — Gemini API call with real audio | FLOWING |
| Parsed result | `parsed` | `IELTSAssessment.model_validate_json(response.text)` | Yes — Pydantic parse of structured JSON | FLOWING |
| Return value | `scores, transcript` | `parsed.transcript`, `CRITERION_MAP` iteration | Yes — 4-element list + string | FLOWING |

Note: `tasks.py` at line 28 calls `assess_session(job)` and assigns the return to `scores_data`, then iterates it as `for entry in scores_data` (line 38). Since `assess_session` now returns a `tuple[list[dict], str]`, this iteration would yield two elements (the list and the string), not 4 dicts — **breaking runtime behavior**. This is an explicitly deferred scope item documented in PLAN.md interfaces, CONTEXT.md `<deferred>`, and SUMMARY.md. It is not a gap for Phase 16. Phase 17 will update `tasks.py`.

---

### Behavioral Spot-Checks

| Behavior | Command | Result | Status |
|----------|---------|--------|--------|
| assessment.py imports cleanly | `python -c "from session.services.assessment import CRITERION_MAP, IELTSAssessment, SYSTEM_PROMPT, assess_session; print('imports OK')"` | `imports OK` | PASS |
| SYSTEM_PROMPT contains all required keywords | Python assertion on 8 keyword strings | All 8 present | PASS |
| Pydantic model validates correct input | `IELTSAssessment.model_validate({...band:7...})` | Model validates, `.transcript` accessible | PASS |
| All 7 AssessmentServiceTests pass | `python manage.py test session.tests.AssessmentServiceTests --settings=MockIT.settings_test -v 2` | `Ran 7 tests in 6.506s OK` | PASS |
| No anthropic references remain | `grep -c "anthropic" session/services/assessment.py` | 0 matches | PASS |
| No tool_use references remain | `grep -c "tool_use" session/services/assessment.py` | 0 matches | PASS |

---

### Requirements Coverage

| Requirement | Source Plan | Description | Status | Evidence |
|-------------|------------|-------------|--------|----------|
| ASMT-01 | 16-01-PLAN.md | Examiner can trigger AI feedback that sends session audio directly to Gemini Pro for scoring all 4 IELTS criteria (FC, GRA, LR, PR) | SATISFIED | `assess_session` uploads audio via Files API and calls `generate_content` with `IELTSAssessment` schema covering all 4 criteria. `CRITERION_MAP` maps all four to integer codes 1-4. |
| ASMT-02 | 16-01-PLAN.md | Gemini response parsed via Pydantic schema with integer band validation (1-9) for each criterion | SATISFIED | `CriterionAssessment.band: int = Field(ge=1, le=9)` enforces constraint. `model_validate_json` raises on band=0 (verified by `test_raises_on_pydantic_validation_error`). |
| ASMT-03 | 16-01-PLAN.md | Safety filter rejections handled gracefully (job marked FAILED with clear error, not silent crash) | SATISFIED (service layer) | `RuntimeError` raised with `finish_reason=` message when `candidate.finish_reason != FinishReason.STOP`. The task layer in `tasks.py` catches any `Exception` and sets `job.status = FAILED` with `job.error_message = str(exc)` (tasks.py lines 53-59). End-to-end wiring is intact. |
| ASMT-04 | 16-01-PLAN.md | Transcript extracted from Gemini response as byproduct and stored in AIFeedbackJob.transcript | PARTIAL — extraction delivered; storage deferred to Phase 17 | `transcript = parsed.transcript` and `return scores, transcript` deliver the transcript from Gemini. However `tasks.py` does not yet unpack the tuple return or write transcript to `job.transcript`. Storing to `AIFeedbackJob.transcript` is explicitly deferred to Phase 17 per PLAN interfaces and CONTEXT.md. |
| PRMT-01 | 16-01-PLAN.md | System prompt includes full IELTS Speaking band descriptors for all 4 criteria with audio-aware assessment instructions | SATISFIED | SYSTEM_PROMPT (98 lines) contains band descriptors for FC, GRA, LR, PR (Bands 1-3, 4-5, 6-7, 8-9 for each) plus dedicated "Audio-Specific Pronunciation Assessment" block with intonation, stress, connected speech, and rhythm instructions. |

**ASMT-04 note:** The requirement states "stored in AIFeedbackJob.transcript". Phase 16 delivers the transcript _out of_ the Gemini call. The storage step (tasks.py update) is a documented Phase 17 deliverable. The requirement is marked PARTIAL but this does not block phase goal achievement — the scope boundary is explicit and pre-declared in the plan.

---

### Anti-Patterns Found

| File | Line | Pattern | Severity | Impact |
|------|------|---------|----------|--------|
| `session/tasks.py` | 28-38 | `scores_data = assess_session(job)` iterated as list, but `assess_session` now returns `tuple[list,str]` | Warning | Runtime breakage when `run_ai_feedback` task executes. Explicitly deferred to Phase 17. Does not affect Phase 16 goal (assessment service itself). |

No stub patterns found in `session/services/assessment.py`. No TODO/FIXME/placeholder comments. No empty return values. No hardcoded static data in rendering paths.

---

### Human Verification Required

None. All phase 16 behaviors are programmatically verifiable via unit tests and import checks.

---

### Gaps Summary

No gaps blocking Phase 16 goal achievement. The phase goal ("AI feedback pipeline produces IELTS band scores and a transcript by sending session audio directly to Gemini Pro in a single call") is fully achieved in `session/services/assessment.py`.

The ASMT-04 partial satisfaction (transcript extracted but not yet stored) and the tasks.py tuple-incompatibility are both pre-declared scope boundaries, explicitly documented in the PLAN, CONTEXT, and SUMMARY. They are Phase 17 work items, not Phase 16 gaps.

**Commits verified:** b8210a8 (assessment.py rewrite) and 69e03a5 (test replacement) both exist in git history with correct authorship and commit messages matching the work described.

---

_Verified: 2026-04-09T13:18:13Z_
_Verifier: Claude (gsd-verifier)_
