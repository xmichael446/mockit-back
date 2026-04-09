# Architecture Research

**Domain:** IELTS Speaking assessment platform — Gemini audio integration
**Researched:** 2026-04-09
**Confidence:** HIGH (official Google GenAI SDK docs + direct code inspection)

## Standard Architecture

### System Overview: Current vs Target

**Current (v1.3) — Two-step pipeline:**

```
POST /api/sessions/<id>/ai-feedback/
    ↓
session/views.py (trigger, monthly limit check)
    ↓
django-q2: async_task('session.tasks.run_ai_feedback', job_id)
    ↓
session/tasks.py: run_ai_feedback()
    ├── session/services/transcription.py: transcribe_session(job)
    │       └── faster-whisper WhisperModel
    │               audio_file.path → plain text transcript
    │               job.transcript = transcript  [DB SAVE]
    │
    └── session/services/assessment.py: assess_session(job)
            └── anthropic.Anthropic client
                    job.transcript (text) → Claude tool_use → 4 criterion dicts
                    ↓
            CriterionScore bulk_create (source=AI)
            AIFeedbackJob.status = DONE
            _broadcast("ai_feedback_ready")
```

**Target (v1.4) — Single-step pipeline:**

```
POST /api/sessions/<id>/ai-feedback/
    ↓
session/views.py (unchanged — trigger, monthly limit check)
    ↓
django-q2: async_task('session.tasks.run_ai_feedback', job_id)
    ↓
session/tasks.py: run_ai_feedback() [MODIFIED — remove transcription step]
    └── session/services/assessment.py: assess_session(job) [REWRITTEN]
            └── google.genai Client (Files API upload)
                    audio_file.path → client.files.upload() → file_ref
                    file_ref + system_prompt + question_context
                    → generate_content() with response_json_schema
                    → JSON: {transcript, fc, gra, lr, pr}
                    ↓
            job.transcript = result["transcript"]  [DB SAVE]
            CriterionScore bulk_create (source=AI)
            AIFeedbackJob.status = DONE
            _broadcast("ai_feedback_ready")
```

### Component Responsibilities

| Component | Current Responsibility | Target Responsibility | Change |
|-----------|----------------------|----------------------|--------|
| `session/services/transcription.py` | faster-whisper transcription | None | DELETE |
| `session/services/assessment.py` | Claude tool_use scoring on text transcript | Gemini audio upload + single-call scoring + transcript extraction | REWRITE |
| `session/tasks.py` | transcribe → save transcript → assess | assess (includes transcript) → save transcript | MODIFY |
| `session/views.py` | POST trigger + GET status/scores + monthly limit | Unchanged | NO CHANGE |
| `session/models.py` | AIFeedbackJob.transcript field | Unchanged (Gemini provides transcript too) | NO CHANGE |
| `requirements.txt` | faster-whisper==1.2.1, anthropic==0.91.0 | google-genai (latest) | MODIFY |
| `MockIT/settings.py` | WHISPER_MODEL_SIZE, ANTHROPIC_API_KEY | GEMINI_API_KEY | MODIFY |

## Recommended Project Structure

```
session/
├── services/
│   ├── __init__.py
│   ├── assessment.py     # REWRITTEN: Gemini audio assessment (replaces both services)
│   └── hms.py            # UNCHANGED
├── tasks.py              # MODIFIED: remove transcription step
├── views.py              # UNCHANGED
└── tests.py              # MODIFIED: replace transcription + Claude mocks with Gemini mocks
```

`transcription.py` is deleted. No new files are added.

### Structure Rationale

- **Single assessment.py:** The two-step pipeline collapses to one service function. A separate transcription module no longer has a reason to exist.
- **No new service file:** The Gemini call is not complex enough to warrant splitting. Keep the same interface (`assess_session(job) -> ...`).
- **tasks.py stays thin:** Remove the explicit transcription step and the intermediate DB save of the transcript. The task orchestrates job lifecycle; the service handles all AI interaction.

## Architectural Patterns

### Pattern 1: Files API Upload + generate_content

**What:** Upload the webm audio file via `client.files.upload()`, then pass the returned file reference as multimodal content alongside the text prompt in `generate_content()`.

**When to use:** When audio file size may exceed 20 MB (inline limit). SessionRecording files are webm recordings of IELTS sessions (typically 15-30 minutes), which will regularly exceed 20 MB. Files API is the correct path.

**Trade-offs:** Files persist for 48 hours then are auto-deleted by Google. Upload adds one extra API call per job but is mandatory for larger files. No storage cost concern for this use case.

**Example:**
```python
from google import genai
from django.conf import settings

client = genai.Client(api_key=settings.GEMINI_API_KEY)

audio_ref = client.files.upload(
    file=audio_path,
    config={"mime_type": "audio/webm"},
)

response = client.models.generate_content(
    model="gemini-2.5-flash",
    contents=[system_prompt_text, audio_ref, user_prompt_text],
    config={
        "response_mime_type": "application/json",
        "response_json_schema": ASSESSMENT_SCHEMA,
    },
)
import json
result = json.loads(response.text)
```

### Pattern 2: response_json_schema for Structured Output

**What:** Pass a JSON Schema dict as `response_json_schema` in the config. Gemini returns valid JSON guaranteed to match the schema — no tool_use dance, no regex, no retry on malformed output.

**When to use:** Whenever structured output is needed. This replaces Claude's `tool_use` pattern entirely. The schema includes all four criterion objects AND a transcript field in one response.

**Trade-offs:** Gemini's structured output is enforced at the model level (constrained decoding), making it more reliable than prompting for JSON. Unlike Claude's tool_use, there is no separate "tool block" to extract — the full response is `response.text` (a JSON string).

**Example schema definition:**
```python
ASSESSMENT_SCHEMA = {
    "type": "object",
    "properties": {
        "transcript": {"type": "string"},
        "fluency_and_coherence": {
            "type": "object",
            "properties": {
                "band": {"type": "integer", "minimum": 1, "maximum": 9},
                "feedback": {"type": "string"},
            },
            "required": ["band", "feedback"],
        },
        # ... gra, lr, pr same shape
    },
    "required": [
        "transcript",
        "fluency_and_coherence",
        "grammatical_range_and_accuracy",
        "lexical_resource",
        "pronunciation",
    ],
}
```

### Pattern 3: Preserve the assess_session(job) Interface With Tuple Return

**What:** Keep the same function name but change the return type to a tuple: `assess_session(job) -> tuple[list[dict], str]`. The first element is the same `[{"criterion": int, "band": int, "feedback": str}, ...]` list. The second is the transcript string.

**When to use:** The transcript can no longer be extracted from `job.transcript` (it doesn't exist yet when `assess_session` runs). The service must return it alongside the scores so the task can save both.

**Trade-offs:** Changing the return type breaks the existing mock in task tests (`return_value=MOCK_ASSESSMENT_RESULT` becomes `return_value=(MOCK_ASSESSMENT_RESULT, "mock transcript")`). This is a small, mechanical change and makes the data flow explicit.

**Recommended task call site:**
```python
scores_data, transcript = assess_session(job)
job.transcript = transcript
job.save(update_fields=["transcript", "updated_at"])
```

## Data Flow

### Request Flow (unchanged at HTTP layer)

```
Examiner: POST /api/sessions/<id>/ai-feedback/
    ↓
AIFeedbackTriggerView.post()
    - monthly limit check (select_for_update)
    - AIFeedbackJob.objects.create(session=session)
    - async_task('session.tasks.run_ai_feedback', job.pk)
    → 202 {"job_id": ..., "status": "pending"}
```

### Background Task Flow (modified)

**v1.3 (current):**
```
run_ai_feedback(job_id)
    job.status = PROCESSING → save
    transcript = transcribe_session(job)        # faster-whisper, ~minutes on CPU
    job.transcript = transcript → save          # intermediate save
    scores = assess_session(job)                # Claude API, text-only
    CriterionScore bulk_create
    job.status = DONE → save
    _broadcast("ai_feedback_ready")
```

**v1.4 (target):**
```
run_ai_feedback(job_id)
    job.status = PROCESSING → save
    scores, transcript = assess_session(job)    # single Gemini call (audio)
    job.transcript = transcript → save          # moved post-call
    CriterionScore bulk_create
    job.status = DONE → save
    _broadcast("ai_feedback_ready")
```

The intermediate `job.transcript` DB save between transcription and assessment is removed. The failure path is simplified: any exception from `assess_session` (including the Files API upload failing) still propagates to the outer `except` block and sets `job.status = FAILED`.

### Key Data Flows

1. **Audio to Gemini:** `recording.audio_file.path` (webm on disk) → `client.files.upload(path, config={"mime_type": "audio/webm"})` → Gemini Files API stores temporarily → `file_ref` URI returned → passed to `generate_content` as multimodal content part.

2. **Structured response parsing:** `response.text` is a JSON string matching `ASSESSMENT_SCHEMA`. `json.loads(response.text)` → dict with `transcript` + four criterion objects. No tool block extraction needed.

3. **Transcript field lifecycle:** `AIFeedbackJob.transcript` was written mid-task in v1.3 (after transcription, before assessment). In v1.4 it is written once after the single Gemini call. Field definition on the model is unchanged — the GET endpoint and WebSocket event are unaffected.

## Integration Points

### External Services

| Service | Integration Pattern | Notes |
|---------|---------------------|-------|
| Google Gemini Files API | `client.files.upload(file=path, config={"mime_type": "audio/webm"})` | Files persist 48h; no cleanup needed for job scope |
| Google Gemini generate_content | `client.models.generate_content(model, contents, config)` | `config.response_json_schema` enforces structured output |
| google-genai SDK | `pip install google-genai` — NOT `google-generativeai` (deprecated) | `from google import genai; client = genai.Client(api_key=...)` |

**Model string:** Use `"gemini-2.5-flash"` for the generate_content call. This is the model referenced in current SDK examples (GitHub README, April 2026). Supports audio understanding via Files API and structured JSON output via `response_json_schema`.

**webm support confirmed:** `audio/webm` is in the supported MIME type list per Firebase AI Logic docs. SessionRecording stores `.webm` files — no conversion needed.

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| `tasks.py` → `assessment.py` | Direct function call `assess_session(job)` | Return type changes: `list[dict]` → `tuple[list[dict], str]` |
| `tasks.py` → `views.py` | `_broadcast()` import | Unchanged |
| `assessment.py` → `session/models.py` | Read `job.session.recording.audio_file.path`, read `SessionQuestion` query | Same query pattern as current `assess_session` + `transcribe_session` combined |
| `settings.py` → `assessment.py` | `settings.GEMINI_API_KEY` | New setting; replaces `ANTHROPIC_API_KEY` and `WHISPER_MODEL_SIZE` |

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| Current load (dev/demo) | Single django-q2 worker, InMemoryChannelLayer — no change needed |
| Production growth | Gemini Files API upload is synchronous in the background task; for very large files (>500 MB) a streaming upload pattern exists but is not needed at current session lengths |
| Rate limits | Gemini API has per-minute token limits. Monthly limit of 10 jobs/user means this is not a concern at current scale |

## Anti-Patterns

### Anti-Pattern 1: Skipping Files API for webm Sessions

**What people do:** Pass audio inline as base64 bytes to save the upload roundtrip.

**Why it's wrong:** IELTS sessions are 10-30 minutes. A 20-minute webm easily exceeds the 20 MB inline limit. Inline upload will fail. The extra Files API call takes ~1 second for large files — acceptable in a background task.

**Do this instead:** Always use `client.files.upload()` for SessionRecording audio. Apply the same guard as current `transcribe_session`: check that `recording.audio_file.path` exists on disk before uploading.

### Anti-Pattern 2: Using google-generativeai (deprecated legacy package)

**What people do:** `pip install google-generativeai` because it appears in older docs and blog posts.

**Why it's wrong:** This package is deprecated as of 2025. The new unified SDK is `google-genai`. Import pattern is different: `from google import genai` (not `import google.generativeai as genai`). The API surface is different.

**Do this instead:** `pip install google-genai`. Verify with `from google import genai; client = genai.Client()`.

### Anti-Pattern 3: Leaving transcription.py as a Dead Module

**What people do:** Leave `session/services/transcription.py` in place with a deprecation comment.

**Why it's wrong:** Tests patching `session.services.transcription.transcribe_session` will still pass, giving false confidence. Future developers may accidentally re-enable it.

**Do this instead:** Delete `session/services/transcription.py` entirely. Delete `TranscriptionServiceTests` and all `@patch("session.services.transcription.transcribe_session")` decorators on task tests. Replace with `AssessmentServiceTests` that mock `google.genai`.

### Anti-Pattern 4: Mimicking Claude's tool_use Pattern With Gemini

**What people do:** Prompt Gemini to "call a tool" and parse a synthetic tool block from `response.text`.

**Why it's wrong:** Gemini does not use Claude's tool_use protocol. Prompting for tool-like output produces unreliable text requiring custom parsing.

**Do this instead:** Use `config={"response_mime_type": "application/json", "response_json_schema": ASSESSMENT_SCHEMA}`. The response is guaranteed valid JSON — no extraction logic needed.

## Build Order

The migration has clear dependency layers. Build in this order to preserve test stability at each step:

**Step 1 — Rewrite session/services/assessment.py**

Replace Claude client with `google.genai` client. Define `ASSESSMENT_SCHEMA` (includes `transcript` field + four criteria). Update `SYSTEM_PROMPT` for direct audio (remove references to "transcript provided"; add pronunciation guidance on intonation, rhythm, connected speech, stress patterns). Keep `CRITERION_MAP` constant — same integer mapping. Change function signature to `assess_session(job) -> tuple[list[dict], str]`.

At this point the new service is written but nothing calls it yet. Can be tested in isolation by mocking `google.genai.Client`.

**Step 2 — Update session/tasks.py**

Remove `from session.services.transcription import transcribe_session` and its call. Change the `assess_session` call site to unpack the tuple: `scores_data, transcript = assess_session(job)`. Move the transcript save to after `assess_session` returns. Remove the intermediate transcript save block that existed between the two old steps.

**Step 3 — Update settings.py and requirements.txt together**

Add `GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")` to settings. Remove `WHISPER_MODEL_SIZE` and `ANTHROPIC_API_KEY`. In `requirements.txt`, add `google-genai`, remove `faster-whisper==1.2.1` and `anthropic==0.91.0`.

**Step 4 — Delete session/services/transcription.py**

Delete the file. This intentionally breaks `TranscriptionServiceTests` and the double-patch decorators on task integration tests — expected and correct.

**Step 5 — Update session/tests.py**

- Delete `TranscriptionServiceTests` class entirely.
- Rewrite `AssessmentServiceTests` to mock `google.genai.Client` instead of `anthropic`.
- Update `AIFeedbackTaskTests`: replace the double `@patch` decorators (transcription + assessment) with a single `@patch("session.services.assessment.assess_session", return_value=(MOCK_ASSESSMENT_RESULT, "mock transcript"))`.
- `AIFeedbackTriggerTests` and `AIScoresDeliveryTests` — NO changes required (HTTP layer and WebSocket events are unchanged).

**Dependency graph:**
```
Step 1 (assessment.py rewrite)
    ↓
Step 2 (tasks.py update) — depends on new assess_session signature
    ↓
Steps 3 + 4 (settings/requirements + delete transcription) — do together
    ↓
Step 5 (tests) — depends on all prior steps complete
```

## API Contract Preservation

The following surfaces are **unchanged** and require no frontend coordination:

| Surface | Contract |
|---------|---------|
| `POST /api/sessions/<id>/ai-feedback/` | 202 `{"job_id": int, "status": "pending"}` |
| `GET /api/sessions/<id>/ai-feedback/` | `{"status": str, "transcript": str\|null, "scores": [...]}` |
| WebSocket event `ai_feedback_ready` | `{"type": "ai_feedback_ready", "job_id": int, "session_id": int}` |
| `AIFeedbackJob` model fields | `status`, `transcript`, `error_message` — all unchanged |
| `CriterionScore` records | `source=AI`, 4 records per job, same criterion integers — unchanged |

The only observable change from outside: the `transcript` field in the GET response contains a Gemini-generated transcript rather than a faster-whisper one. Content quality improves; field shape is identical.

## Sources

- [Google GenAI Python SDK (google-genai) — GitHub README](https://github.com/googleapis/python-genai)
- [Audio understanding — Gemini API docs](https://ai.google.dev/gemini-api/docs/audio)
- [Structured output — Gemini API docs](https://ai.google.dev/gemini-api/docs/structured-output)
- [File input methods — Gemini API docs](https://ai.google.dev/gemini-api/docs/file-input-methods)
- [Supported input files including audio/webm — Firebase AI Logic](https://firebase.google.com/docs/ai-logic/input-file-requirements)
- [google-genai PyPI package](https://pypi.org/project/google-genai/)

---
*Architecture research for: MockIT v1.4 — Gemini audio assessment integration*
*Researched: 2026-04-09*
