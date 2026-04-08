# Phase 12: AI Assessment Service - Context

**Gathered:** 2026-04-08
**Status:** Ready for planning

<domain>
## Phase Boundary

The background job generates IELTS band scores and actionable feedback for all four criteria using Claude API. Extends the existing run_ai_feedback task (which already does transcription) to call Claude API after transcription completes, parse the structured response, and create CriterionScore records with source=AI.

</domain>

<decisions>
## Implementation Decisions

### Claude API Integration
- Use claude-sonnet-4-20250514 model (cost-effective for scoring tasks)
- API key configured via ANTHROPIC_API_KEY env variable + Django setting (matches existing env config pattern)
- Use tool_use (structured output) for reliable JSON parsing of scores and feedback

### Score Creation & Prompt Design
- Bulk create all 4 CriterionScore records in one call with source=AI
- System prompt includes IELTS band descriptors for each criterion; user prompt includes transcript and actual session questions
- All-or-nothing: FAILED status if any criterion missing from API response (no partial saves)

### Claude's Discretion
- Exact IELTS band descriptor text in system prompt
- Token limits and temperature settings
- Internal structure of the assessment service module

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `run_ai_feedback()` in `session/tasks.py` — already does transcription, needs AI scoring after
- `CriterionScore` model with `source` field (ScoreSource.AI = 2) from Phase 10
- `SpeakingCriterion` enum (FC=1, GRA=2, LR=3, PR=4) in session/models.py
- `SessionResult` model linked to IELTSMockSession
- `AIFeedbackJob` with transcript field from Phase 11

### Established Patterns
- Services in `session/services/` (e.g., `hms.py`, `transcription.py`)
- Deferred imports inside task functions
- Error handling: capture exception, set FAILED + error_message

### Integration Points
- `run_ai_feedback()` — add AI scoring call after transcription
- `CriterionScore.objects.bulk_create()` for creating 4 AI scores
- `SessionResult` — need to get or create for the session to FK the scores
- `anthropic` Python SDK — new dependency in requirements.txt

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches following the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
