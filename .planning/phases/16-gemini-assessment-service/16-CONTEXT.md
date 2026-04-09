# Phase 16: Gemini Assessment Service - Context

**Gathered:** 2026-04-09
**Status:** Ready for planning

<domain>
## Phase Boundary

Rewrite the AI feedback pipeline to send session audio directly to Gemini Pro in a single call, producing IELTS band scores (FC, GRA, LR, PR) and a transcript as structured JSON output. This replaces the two-step faster-whisper + Claude pipeline with a single Gemini call. The function signature and return format must remain compatible with the existing tasks.py caller.

</domain>

<decisions>
## Implementation Decisions

### Prompt Engineering
- System prompt instructs Gemini to assess pronunciation from audio using explicit audio cues: intonation patterns, stress placement, connected speech, and rhythm (core IELTS PR descriptors)
- Transcript is a separate field in the Pydantic schema (not extracted from assessment text) — Gemini produces both scores and transcript in one structured response
- Session questions are included as context in the prompt (same pattern as v1.3 assessment.py lines 182-193)
- System prompt maintains same detail level as v1.3 — full IELTS band descriptors for all 4 criteria, with added audio-specific instructions for pronunciation/intonation/rhythm

### Pydantic Schema & Response Parsing
- Pydantic field names match existing CRITERION_MAP keys: `fluency_and_coherence`, `grammatical_range_and_accuracy`, `lexical_resource`, `pronunciation` — each with `band` (int) and `feedback` (str), plus top-level `transcript` (str)
- Band validation at Pydantic schema level using `Field(ge=1, le=9)` — cleaner than post-parse checks
- Function signature unchanged: `assess_session(job) -> list[dict]` — keeps tasks.py caller unchanged, but internally reads audio from recording instead of job.transcript
- Pydantic model lives in assessment.py (single-use schema, no separate file needed)

### Error Handling & Audio Upload
- Audio uploaded via Files API (proven in smoke test) — handles large files, returns URI for generate_content
- Safety filter rejections detected by checking `candidate.finish_reason` for non-STOP values — raise RuntimeError with clear message including safety category
- Transient errors (503/429) retried in service layer with max 3 retries and exponential backoff (same pattern as smoke test)
- Missing audio file raises RuntimeError early — check `os.path.isfile(audio_path)` before upload (same pattern as transcription.py:33)

### Claude's Discretion
- Exact wording of audio-specific pronunciation instructions in the system prompt
- Pydantic model class name and internal structure details
- Logging verbosity and message format
- Exact retry backoff timing

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `session/services/assessment.py` — current Claude-based assessment (full rewrite target). CRITERION_MAP, SYSTEM_PROMPT structure, and question context builder are reference patterns
- `session/tasks.py` — caller of assess_session(); expects `list[dict]` return with `criterion`, `band`, `feedback` keys
- `scripts/smoke_gemini.py` — proven Gemini Files API upload + generate_content pattern
- `session/services/transcription.py` — audio file path resolution pattern (recording.audio_file.path)

### Established Patterns
- Deferred imports inside functions to avoid circular imports at module load time (assessment.py:172-173, transcription.py:17)
- Integer literals in CRITERION_MAP (not enum) to avoid AppRegistryNotReady at import time
- Service functions raise RuntimeError on failure; task layer catches and sets FAILED status
- Logging via `logging.getLogger(__name__)` with structured messages

### Integration Points
- `tasks.py` calls `assess_session(job)` — currently after transcription, will be called directly
- `tasks.py` stores transcript on `job.transcript` — will need to get it from assess_session return or separate step
- `session/models.py` — AIFeedbackJob, SessionRecording, SessionQuestion, CriterionScore, ScoreSource
- `MockIT/settings.py` — GEMINI_API_KEY (added in Phase 15)

</code_context>

<specifics>
## Specific Ideas

- The Pydantic schema should include a `transcript` field so Gemini produces the transcript as part of the structured response, avoiding a separate extraction step
- The assess_session function should also return the transcript (in addition to the scores list) so tasks.py can store it on job.transcript
- Consider returning a tuple `(scores_list, transcript)` or adding transcript to the function's side effects

</specifics>

<deferred>
## Deferred Ideas

- tasks.py changes (wiring new assess_session, removing transcription step) — Phase 17
- Deleting transcription.py — Phase 17
- Updating test mocks — Phase 17

</deferred>
