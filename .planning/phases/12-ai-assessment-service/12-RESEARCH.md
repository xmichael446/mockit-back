# Phase 12: AI Assessment Service - Research

**Researched:** 2026-04-07
**Domain:** Anthropic Python SDK / tool_use / Django background task integration
**Confidence:** HIGH

## Summary

Phase 12 extends the existing `run_ai_feedback()` task (which already transcribes audio) to call Claude API after transcription, parse a structured response via tool_use, and bulk-create four `CriterionScore` records with `source=AI`. All data models are already in place from Phase 10; the only new dependency is the `anthropic` Python SDK.

The locked decisions narrow the scope cleanly: model is `claude-sonnet-4-20250514`, structured output via tool_use (not JSON mode), all-or-nothing creation (no partial saves), and the service lives in `session/services/` following the `hms.py` / `transcription.py` pattern.

The Anthropic Python SDK (v0.91.0, April 2026) is synchronous by default. Since `run_ai_feedback()` is a synchronous Django-Q2 task, no async bridging is needed. The client reads `ANTHROPIC_API_KEY` from the environment automatically, matching the project's existing env var convention.

**Primary recommendation:** Create `session/services/assessment.py` containing `assess_session(job)` → returns a list of four `{criterion, band, feedback}` dicts. The task calls this after transcription, wraps `CriterionScore.objects.bulk_create()` outside the service, and sets FAILED on any exception.

---

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions
- Use `claude-sonnet-4-20250514` model (cost-effective for scoring tasks)
- API key configured via `ANTHROPIC_API_KEY` env variable + Django setting (matches existing env config pattern)
- Use tool_use (structured output) for reliable JSON parsing of scores and feedback
- Bulk create all 4 CriterionScore records in one call with `source=AI`
- System prompt includes IELTS band descriptors for each criterion; user prompt includes transcript and actual session questions
- All-or-nothing: FAILED status if any criterion missing from API response (no partial saves)

### Claude's Discretion
- Exact IELTS band descriptor text in system prompt
- Token limits and temperature settings
- Internal structure of the assessment service module

### Deferred Ideas (OUT OF SCOPE)
- None — discussion stayed within phase scope.
</user_constraints>

---

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| AIAS-02 | AI generates band scores (1-9) for each IELTS criterion (FC, GRA, LR, PR) | tool_use input_schema with `band` integer (1–9) per criterion; bulk_create four CriterionScore records with `source=AI` |
| AIAS-03 | AI generates 3-4 sentence actionable feedback per criterion | `feedback` string field in tool_use schema; system prompt instructs 3-4 sentences; stored in `CriterionScore.feedback` (TextField, already nullable) |
| AIAS-04 | AI prompt includes actual session questions for context-aware assessment | Query `SessionQuestion` objects ordered by part/order; include in user message alongside transcript — same pattern used in `transcription.py` for `initial_prompt` |
</phase_requirements>

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| anthropic | 0.91.0 | Official Anthropic Python SDK | Only official client; reads `ANTHROPIC_API_KEY` automatically; synchronous client matches Django-Q2 task context |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| (none new) | — | All other deps already in requirements.txt | — |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| tool_use (forced) | Plain JSON in system prompt | tool_use + `tool_choice={"type":"tool"}` gives schema-validated, reliably parseable output; plain JSON is fragile and requires manual regex |
| tool_use (forced) | `response_format` JSON mode | Claude API does not have a JSON mode equivalent; tool_use is the official structured output path |

**Installation:**
```bash
pip install anthropic==0.91.0
```
Add to `requirements.txt`: `anthropic==0.91.0`

**Version verification:** Confirmed against PyPI on 2026-04-07. Version 0.91.0 released 2026-04-07.

---

## Architecture Patterns

### Recommended Project Structure

```
session/services/
├── hms.py               # existing — 100ms video
├── transcription.py     # existing — faster-whisper
└── assessment.py        # NEW — Claude API scoring
```

The task in `session/tasks.py` grows by ~10 lines: call `assess_session(job)`, then `bulk_create`.

### Pattern 1: Forced tool_use for Structured Output

**What:** Define a single tool `submit_ielts_assessment` with a JSON schema containing four criterion objects. Use `tool_choice={"type": "tool", "name": "submit_ielts_assessment"}` to guarantee Claude always invokes it. Extract `response.content` blocks, find the `tool_use` block, read `.input`.

**When to use:** Any time you need machine-readable structured output from Claude without an agentic loop — one call, one response, done.

**Example (Python SDK, synchronous):**
```python
# Source: https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools
import anthropic

client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from environment

TOOL_DEFINITION = {
    "name": "submit_ielts_assessment",
    "description": (
        "Submit IELTS Speaking band scores and actionable feedback for all four "
        "assessment criteria. Call this tool exactly once with scores for FC, GRA, LR, and PR."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "fluency_and_coherence": {
                "type": "object",
                "properties": {
                    "band": {"type": "integer", "minimum": 1, "maximum": 9,
                             "description": "Band score 1-9"},
                    "feedback": {"type": "string",
                                 "description": "3-4 sentences of actionable feedback"},
                },
                "required": ["band", "feedback"],
            },
            "grammatical_range_and_accuracy": {
                "type": "object",
                "properties": {
                    "band": {"type": "integer", "minimum": 1, "maximum": 9},
                    "feedback": {"type": "string"},
                },
                "required": ["band", "feedback"],
            },
            "lexical_resource": {
                "type": "object",
                "properties": {
                    "band": {"type": "integer", "minimum": 1, "maximum": 9},
                    "feedback": {"type": "string"},
                },
                "required": ["band", "feedback"],
            },
            "pronunciation": {
                "type": "object",
                "properties": {
                    "band": {"type": "integer", "minimum": 1, "maximum": 9},
                    "feedback": {"type": "string"},
                },
                "required": ["band", "feedback"],
            },
        },
        "required": [
            "fluency_and_coherence",
            "grammatical_range_and_accuracy",
            "lexical_resource",
            "pronunciation",
        ],
    },
}

response = client.messages.create(
    model="claude-sonnet-4-20250514",
    max_tokens=1024,
    system=SYSTEM_PROMPT,
    tools=[TOOL_DEFINITION],
    tool_choice={"type": "tool", "name": "submit_ielts_assessment"},
    messages=[{"role": "user", "content": user_message}],
)

# Extract tool_use block
tool_use_block = next(
    block for block in response.content if block.type == "tool_use"
)
assessment_input = tool_use_block.input  # dict matching input_schema
```

### Pattern 2: Deferred Import in Service Function

Follow the project convention from `transcription.py` and `tasks.py`: import `anthropic` inside the function body, not at module top level. This prevents import-time cost and keeps circular import risk minimal.

```python
# session/services/assessment.py
def assess_session(job) -> list[dict]:
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic is not installed. Run: pip install anthropic"
        )
    from django.conf import settings
    client = anthropic.Anthropic(
        api_key=getattr(settings, "ANTHROPIC_API_KEY", None)
    )
    # ... build prompts, call API, parse ...
```

### Pattern 3: Mapping tool_use Output to SpeakingCriterion

The tool schema uses long English key names; map to `SpeakingCriterion` enum values before bulk_create:

```python
CRITERION_MAP = {
    "fluency_and_coherence": SpeakingCriterion.FC,
    "grammatical_range_and_accuracy": SpeakingCriterion.GRA,
    "lexical_resource": SpeakingCriterion.LR,
    "pronunciation": SpeakingCriterion.PR,
}
```

### Pattern 4: All-or-Nothing Validation Before bulk_create

Check that all four keys are present and bands are integers 1–9 before touching the database. Raise `ValueError` (or `RuntimeError`) if any key is missing — the task's outer except block catches this and sets FAILED.

```python
REQUIRED_KEYS = {"fluency_and_coherence", "grammatical_range_and_accuracy",
                 "lexical_resource", "pronunciation"}
missing = REQUIRED_KEYS - set(assessment_input.keys())
if missing:
    raise RuntimeError(f"Claude response missing criteria: {missing}")
```

### Pattern 5: Building the User Prompt (AIAS-04)

Reuse the same `SessionQuestion` query pattern from `transcription.py`:

```python
from session.models import SessionQuestion, SessionPart

questions = (
    SessionQuestion.objects.filter(session_part__session=job.session)
    .select_related("question", "session_part")
    .order_by("session_part__part", "order")
)
question_lines = []
for sq in questions:
    part_label = f"Part {sq.session_part.part}"
    question_lines.append(f"[{part_label}] {sq.question.text}")
questions_text = "\n".join(question_lines) if question_lines else "(no questions recorded)"

user_message = (
    f"Session questions asked:\n{questions_text}\n\n"
    f"Candidate transcript:\n{job.transcript}"
)
```

### Pattern 6: Task Integration (extending run_ai_feedback)

```python
# session/tasks.py — after transcription save, before DONE
from session.services.assessment import assess_session
from session.models import SessionResult, CriterionScore, ScoreSource, SpeakingCriterion

scores_data = assess_session(job)

result, _ = SessionResult.objects.get_or_create(session=job.session)
CriterionScore.objects.bulk_create([
    CriterionScore(
        session_result=result,
        criterion=entry["criterion"],
        source=ScoreSource.AI,
        band=entry["band"],
        feedback=entry["feedback"],
    )
    for entry in scores_data
])
```

### Anti-Patterns to Avoid

- **Importing `anthropic` at module top level:** Breaks the deferred-import convention; adds startup cost.
- **Parsing JSON from text content blocks:** Fragile. Always use tool_use + tool_choice=tool.
- **Partial saves on missing criteria:** Locked decision says all-or-nothing. Never `bulk_create` with fewer than 4 scores.
- **Creating `SessionResult` without `get_or_create`:** An examiner might have already created a result; use `get_or_create` to avoid IntegrityError (SessionResult has OneToOneField on session).
- **Hardcoding temperature=0:** No evidence this is necessary for structured tool_use where tool_choice forces the call. Leave at default unless testing reveals non-determinism issues.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Structured JSON from LLM | Custom prompt + regex JSON parser | `tool_use` + `tool_choice={"type":"tool"}` | Schema validation happens in the model; malformed output raises before your code runs |
| HTTP client for Anthropic API | `requests.post(...)` | `anthropic.Anthropic()` | Handles auth headers, retries, API versioning, response parsing, typed objects |
| Retry logic on transient errors | Custom loop | `anthropic` SDK default (auto-retry on 529/rate-limit) | Already built in |

**Key insight:** The `tool_use` pattern is Claude's canonical structured output mechanism. It is not an agentic loop in this context — with `tool_choice={"type":"tool","name":"..."}`, the model responds in one turn with the tool call, and you extract `.input` without sending a tool_result back.

---

## Common Pitfalls

### Pitfall 1: `stop_reason` is not always `"tool_use"` even with forced tool_choice

**What goes wrong:** If `max_tokens` is too low, the response may stop mid-generation with `stop_reason="max_tokens"` instead of `"tool_use"`. The `tool_use` block will be absent and `next(block for block in ...)` raises `StopIteration`.

**Why it happens:** The model needs to output the full JSON object within the token budget.

**How to avoid:** Set `max_tokens` to at least 1024 (safe for 4 criteria × ~100 tokens of feedback). 2048 is safer if band descriptors are verbose.

**Warning signs:** `StopIteration` on the `next(...)` call, or `response.stop_reason == "max_tokens"`.

### Pitfall 2: `anthropic.APIStatusError` vs `anthropic.APIConnectionError`

**What goes wrong:** Network errors, rate limits, and model errors all raise different exception subclasses. Catching only `Exception` is fine for the task's FAILED path, but test mocks need to raise the correct type.

**Why it happens:** The SDK raises `anthropic.APIConnectionError` for network failures, `anthropic.RateLimitError` (subclass of `APIStatusError`) for 429s, `anthropic.APIStatusError` for other 4xx/5xx.

**How to avoid:** In the service, let all `anthropic.*` exceptions propagate — the task's `except Exception` catches them. In tests, `side_effect=Exception("Claude error")` is sufficient for the FAILED-path test.

### Pitfall 3: `SessionResult` OneToOneField conflict

**What goes wrong:** `SessionResult.objects.create(session=job.session)` raises `IntegrityError` if an examiner has already submitted scores (Phase 10 creates SessionResult on examiner scoring).

**Why it happens:** `SessionResult` has a `OneToOneField` on `IELTSMockSession`.

**How to avoid:** Always use `SessionResult.objects.get_or_create(session=job.session)`.

### Pitfall 4: Stale `job.session` not prefetched

**What goes wrong:** Accessing `job.session.recording` or `job.session.parts` triggers extra queries because `job` was fetched in the task without select_related.

**Why it happens:** Django ORM lazy loading in background task context.

**How to avoid:** The assessment service receives the full `job` object (already loaded with `job.session` available). For session questions, always use `SessionQuestion.objects.filter(session_part__session=job.session).select_related(...)` as shown in the transcription service pattern.

### Pitfall 5: `ANTHROPIC_API_KEY` missing from settings/env

**What goes wrong:** `anthropic.Anthropic()` raises `anthropic.AuthenticationError` if the key is absent.

**Why it happens:** Key not set in `.env` or Django settings.

**How to avoid:** Mirror the existing `HMS_APP_ACCESS_KEY` pattern — add `ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "")` to `settings.py`. Add to `.env.example`. In test settings, patch the client rather than setting a real key.

---

## Code Examples

### Full assess_session service skeleton
```python
# Source: Anthropic SDK docs + project patterns
# session/services/assessment.py
import logging

logger = logging.getLogger(__name__)

CRITERION_MAP = {
    "fluency_and_coherence": 1,       # SpeakingCriterion.FC
    "grammatical_range_and_accuracy": 2,  # SpeakingCriterion.GRA
    "lexical_resource": 3,             # SpeakingCriterion.LR
    "pronunciation": 4,                # SpeakingCriterion.PR
}

REQUIRED_KEYS = set(CRITERION_MAP.keys())

SYSTEM_PROMPT = """You are an expert IELTS Speaking examiner..."""  # Claude's discretion

TOOL_DEFINITION = { ... }  # as shown in Pattern 1

def assess_session(job) -> list[dict]:
    """
    Call Claude API with transcript and session questions.
    Returns list of 4 dicts: [{"criterion": int, "band": int, "feedback": str}, ...]
    Raises RuntimeError on any failure (caller sets job.status=FAILED).
    """
    try:
        import anthropic
    except ImportError:
        raise RuntimeError("anthropic not installed. Run: pip install anthropic")

    from django.conf import settings
    from session.models import SessionQuestion

    # Build question context (AIAS-04)
    questions = (
        SessionQuestion.objects.filter(session_part__session=job.session)
        .select_related("question", "session_part")
        .order_by("session_part__part", "order")
    )
    question_lines = [
        f"[Part {sq.session_part.part}] {sq.question.text}"
        for sq in questions if sq.question.text
    ]
    questions_text = "\n".join(question_lines) or "(no questions recorded)"

    user_message = (
        f"Session questions asked:\n{questions_text}\n\n"
        f"Candidate transcript:\n{job.transcript or '(no transcript)'}"
    )

    client = anthropic.Anthropic(
        api_key=getattr(settings, "ANTHROPIC_API_KEY", None)
    )

    logger.info("assess_session: calling Claude API for job_id=%s", job.pk)
    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=[TOOL_DEFINITION],
        tool_choice={"type": "tool", "name": "submit_ielts_assessment"},
        messages=[{"role": "user", "content": user_message}],
    )

    tool_block = next(
        (b for b in response.content if b.type == "tool_use"), None
    )
    if tool_block is None:
        raise RuntimeError(
            f"Claude did not return tool_use block. stop_reason={response.stop_reason}"
        )

    data = tool_block.input  # dict
    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        raise RuntimeError(f"Claude response missing criteria: {missing}")

    result = []
    for key, criterion_int in CRITERION_MAP.items():
        entry = data[key]
        band = entry.get("band")
        feedback = entry.get("feedback", "")
        if not isinstance(band, int) or not (1 <= band <= 9):
            raise RuntimeError(f"Invalid band for {key}: {band!r}")
        result.append({"criterion": criterion_int, "band": band, "feedback": feedback})

    logger.info("assess_session: job_id=%s bands=%s", job.pk, [r["band"] for r in result])
    return result
```

### Task integration (diff view)
```python
# In run_ai_feedback(), after transcript save:

# Phase 12: AI scoring via Claude API
from session.services.assessment import assess_session
from session.models import SessionResult, CriterionScore, ScoreSource

scores_data = assess_session(job)
result, _ = SessionResult.objects.get_or_create(session=job.session)
CriterionScore.objects.bulk_create([
    CriterionScore(
        session_result=result,
        criterion=entry["criterion"],
        source=ScoreSource.AI,
        band=entry["band"],
        feedback=entry["feedback"],
    )
    for entry in scores_data
])
```

### Test mock pattern (following existing RunAIFeedbackTaskTests)
```python
# Patch target is session.services.assessment.assess_session
# (deferred import resolves from that module)
with patch(
    "session.services.assessment.assess_session",
    return_value=[
        {"criterion": 1, "band": 7, "feedback": "Good fluency."},
        {"criterion": 2, "band": 6, "feedback": "Some grammar errors."},
        {"criterion": 3, "band": 7, "feedback": "Good vocabulary."},
        {"criterion": 4, "band": 6, "feedback": "Clear pronunciation."},
    ],
):
    run_ai_feedback(self.job.pk)
```

---

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| anthropic Python SDK | Claude API calls | No | — | None — must install |
| ANTHROPIC_API_KEY env var | Client auth | Unknown (not in .env.example yet) | — | None — must set |
| PostgreSQL | ORM/tests | Yes (SQLite in tests) | psycopg2-binary in reqs | SQLite via settings_test.py |

**Missing dependencies with no fallback:**
- `anthropic` SDK: must add to `requirements.txt` and install
- `ANTHROPIC_API_KEY`: must add to `.env` and `.env.example`; add to `settings.py` (mirrors `HMS_APP_ACCESS_KEY` pattern)

**Missing dependencies with fallback:**
- None.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Django TestCase (built-in) |
| Config file | `MockIT/settings_test.py` |
| Quick run command | `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test session.tests.AssessmentServiceTests` |
| Full suite command | `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test session` |

### Phase Requirements → Test Map

| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| AIAS-02 | Four CriterionScore records created with source=AI and band 1-9 | integration | `python manage.py test session.tests.RunAIFeedbackTaskTests.test_task_creates_ai_scores` | No — Wave 0 |
| AIAS-02 | Missing criterion in Claude response → FAILED status | integration | `python manage.py test session.tests.RunAIFeedbackTaskTests.test_task_fails_on_missing_criterion` | No — Wave 0 |
| AIAS-03 | Feedback text stored on each CriterionScore | integration | `python manage.py test session.tests.RunAIFeedbackTaskTests.test_task_stores_feedback` | No — Wave 0 |
| AIAS-04 | assess_session builds question context from SessionQuestion objects | unit | `python manage.py test session.tests.AssessmentServiceTests.test_builds_question_context` | No — Wave 0 |
| AIAS-02 | Claude API error → FAILED status + error_message | integration | `python manage.py test session.tests.RunAIFeedbackTaskTests.test_task_fails_on_claude_error` | No — Wave 0 |

### Sampling Rate
- **Per task commit:** `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test session.tests.RunAIFeedbackTaskTests`
- **Per wave merge:** `DJANGO_SETTINGS_MODULE=MockIT.settings_test python manage.py test session`
- **Phase gate:** Full session test suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] New test class `AssessmentServiceTests` in `session/tests.py` — unit tests for `assess_session()` with mocked `anthropic.Anthropic`
- [ ] New tests in `RunAIFeedbackTaskTests` — integration tests for AI scoring path with mocked `assess_session`
- [ ] `ANTHROPIC_API_KEY` added to `settings_test.py` or patched in tests (no real key needed in CI)

*(All existing tests continue to pass — task mock must now also patch `assess_session` in the `test_task_transitions_to_done` test, as the task will call it after transcription.)*

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Prompt for JSON → parse text | tool_use with `tool_choice={"type":"tool"}` | Anthropic introduced tool_use ~2024 | Reliable schema-validated structured output; no regex |
| Manual HTTP to api.anthropic.com | `anthropic` Python SDK | SDK v0.x+ | Handles auth, versioning, retries, typed response objects |

**Deprecated/outdated:**
- JSON-in-system-prompt parsing: Claude sometimes adds prose around JSON; not recommended when tool_use is available.

---

## Open Questions

1. **IELTS band descriptor text in system prompt**
   - What we know: Must include descriptors for FC, GRA, LR, PR so Claude has IELTS-calibrated standards
   - What's unclear: Exact official IELTS descriptor text (Claude's discretion per CONTEXT.md)
   - Recommendation: Use publicly available IELTS band descriptor summaries in the system prompt; 3-4 bullet points per criterion describing what each band range looks like

2. **max_tokens value**
   - What we know: 4 criteria × ~80-150 tokens each = ~400-600 tokens of output; tool_use overhead ~300 tokens
   - What's unclear: Exact token count for a full response
   - Recommendation: Default to `max_tokens=1024`; raise to `2048` if test responses get truncated

3. **Existing `RunAIFeedbackTaskTests` patch scope**
   - What we know: `test_task_transitions_to_done` currently patches only `transcribe_session`; after Phase 12, the task also calls `assess_session`
   - What's unclear: Whether to update existing tests or add a separate outer patch
   - Recommendation: Add `patch("session.services.assessment.assess_session", return_value=[...])` to all existing `RunAIFeedbackTaskTests` that call `run_ai_feedback()` — otherwise they will attempt a real Claude API call and fail in CI

---

## Sources

### Primary (HIGH confidence)
- PyPI `anthropic` package page — version 0.91.0, published 2026-04-07
- `https://platform.claude.com/docs/en/agents-and-tools/tool-use/define-tools` — tool definition format, `tool_choice` options, `input_schema` structure
- `https://platform.claude.com/docs/en/agents-and-tools/tool-use/handle-tool-calls` — `stop_reason`, `tool_use` block structure, `block.input` dict
- Codebase: `session/tasks.py`, `session/services/transcription.py`, `session/models.py`, `session/tests.py`

### Secondary (MEDIUM confidence)
- `https://github.com/anthropics/anthropic-sdk-python` README — basic client instantiation pattern

### Tertiary (LOW confidence)
- None.

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — verified against PyPI (0.91.0, April 2026)
- Architecture: HIGH — verified against official Anthropic tool_use docs + existing codebase patterns
- Pitfalls: HIGH — derived from official docs (token limits, stop_reason, OneToOneField) + codebase inspection
- Test patterns: HIGH — mirrors existing `RunAIFeedbackTaskTests` structure directly

**Research date:** 2026-04-07
**Valid until:** 2026-05-07 (anthropic SDK moves fast; verify version before install)
