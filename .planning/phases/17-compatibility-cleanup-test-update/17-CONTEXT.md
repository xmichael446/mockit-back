# Phase 17: Compatibility, Cleanup & Test Update - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

Wire tasks.py to the new Gemini assess_session (tuple return), delete transcription.py, update all remaining test mocks from anthropic/faster-whisper to google-genai, and verify the existing API contract is fully preserved (same endpoint shapes, same WebSocket events, same monthly limits).

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure/cleanup phase. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

Key integration points:
- tasks.py currently calls `transcribe_session(job)` then `assess_session(job)` — needs to call only `assess_session(job)` and unpack the tuple return `(scores_list, transcript)`
- tasks.py stores transcript on `job.transcript` — needs to get it from the tuple
- `AIFeedbackTaskTests` mock `assess_session` returning `list[dict]` — needs to return `tuple[list[dict], str]`
- `session/services/transcription.py` — delete entirely
- Monthly limit + select_for_update tests must still pass

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `session/tasks.py` — current task with transcribe→assess pipeline (lines 19-28 need rewriting)
- `session/tests.py` — AIFeedbackTaskTests class mocks both transcription and assessment
- `session/services/transcription.py` — file to delete

### Established Patterns
- Deferred imports inside task function body
- `_broadcast` called after job status set to DONE
- `select_for_update` for race prevention in trigger view

### Integration Points
- `session/views.py` — trigger endpoint (unchanged, just calls async_task)
- `session/views.py` — GET ai-feedback endpoint (reads CriterionScore, unchanged)
- `session/consumers.py` — WebSocket ai_feedback_ready event (unchanged)
- `MockIT/settings.py` — GEMINI_API_KEY (already configured in Phase 15)

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure/cleanup phase. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — this is the final phase of v1.4.

</deferred>
