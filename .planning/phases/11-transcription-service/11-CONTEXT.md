# Phase 11: Transcription Service - Context

**Gathered:** 2026-04-07
**Status:** Ready for planning

<domain>
## Phase Boundary

Examiners can trigger transcription of a completed session's recording and retrieve the resulting transcript. The background task (skeleton from Phase 10) is fleshed out with faster-whisper transcription logic, transcript storage, and question context integration.

</domain>

<decisions>
## Implementation Decisions

### Transcript Storage & Format
- Store transcript as a TextField on AIFeedbackJob model (co-located with job status, simple query)
- Transcript format: plain text with speaker labels (Examiner:/Candidate:) — readable, sufficient for Claude API input
- Whisper model size configured via Django setting `WHISPER_MODEL_SIZE` with env variable override (matches existing env config pattern)

### Question Context Integration
- Use Whisper's `initial_prompt` parameter with session question text to improve transcription accuracy
- Include all SessionQuestions from all parts (not just current part)
- Build prompt string by concatenating question texts separated by periods

### Error Handling & Edge Cases
- Missing audio file: set job status to FAILED with clear error message
- Whisper import failure: graceful FAILED status with install instructions in error_message
- Empty/corrupt audio: FAILED status with descriptive error message

### Claude's Discretion
- Internal structure of the transcription service module
- Whisper model loading strategy (lazy load vs eager)
- Exact speaker label format details

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `AIFeedbackJob` model in `session/models.py` with Status enum (PENDING/PROCESSING/DONE/FAILED)
- `run_ai_feedback()` task skeleton in `session/tasks.py` with status transition logic and error handling
- `SessionRecording` model with `audio_file = FileField(upload_to="recordings/")`
- `SessionQuestion` model with FK to `Question`, timestamps for asked_at/ended_at
- `Question` model in `questions/` app with text field and follow-up questions

### Established Patterns
- Background tasks use deferred imports to avoid circular dependencies
- Error handling captures exceptions, sets FAILED status with error_message
- django-q2 with ORM broker, sync mode in tests
- Transaction discipline: side effects after transaction exits

### Integration Points
- `run_ai_feedback()` in `session/tasks.py` — flesh out skeleton with transcription logic
- `AIFeedbackJob` needs `transcript` TextField added (migration)
- `SessionRecording.audio_file` provides the audio path
- `SessionQuestion` → `Question.text` provides context for Whisper prompt

</code_context>

<specifics>
## Specific Ideas

No specific requirements — open to standard approaches following the decisions above.

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope.

</deferred>
