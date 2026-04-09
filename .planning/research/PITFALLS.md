# Pitfalls Research

**Domain:** Replacing text-based AI assessment pipeline (faster-whisper + Claude) with Gemini Pro direct audio assessment
**Researched:** 2026-04-09
**Confidence:** HIGH (Gemini file limits, audio format support, SDK differences); MEDIUM (latency, cost projections, safety filter behavior on speech)

---

## Critical Pitfalls

### Pitfall 1: webm MIME type listed in Firebase AI docs but absent from core Gemini API audio docs

**What goes wrong:**
The Gemini API audio documentation page (`ai.google.dev/gemini-api/docs/audio`) lists supported formats as: WAV, MP3, AIFF, AAC, OGG Vorbis, FLAC. It does not mention `audio/webm`. The Firebase AI Logic documentation does list `audio/webm`. These two sources contradict each other. If you assume webm is universally supported and call the API with `mime_type="audio/webm"`, you may receive a 400 INVALID_ARGUMENT error at runtime in production — silently silenced in tests that mock the Gemini client.

**Why it happens:**
The existing pipeline stores recordings as webm (browser MediaRecorder default). The developer assumes format support from Firebase docs without verifying the core Gemini API docs, or tests pass because the Gemini client is mocked.

**How to avoid:**
1. Before writing any audio upload code, call the Gemini API with a short real webm file and confirm acceptance.
2. If webm is rejected, add a pre-upload conversion step using `ffmpeg` or `pydub` to convert to MP3 or FLAC before sending. This must happen inside the background task, before the Gemini API call.
3. Set `mime_type` explicitly in every audio upload — never rely on auto-detection.
4. Add an integration smoke-test (can be outside the main suite) that sends a real 5-second webm to the Gemini API to confirm acceptance.

**Warning signs:**
- 400 INVALID_ARGUMENT errors in Gemini API calls referencing mime type
- `FinishReason.OTHER` without explanation
- Tests pass locally (all mocked) but production jobs fail immediately

**Phase to address:** Phase 1 (Gemini client setup and audio format validation) — validate webm acceptance before writing the assessment logic.

---

### Pitfall 2: Files API 48-hour TTL causes silent failures for background jobs

**What goes wrong:**
The Gemini Files API automatically deletes uploaded files after 48 hours. If you upload an audio file to the Files API and store the file URI in the AIFeedbackJob, any retry of a failed job after 48 hours will receive a 404 NOT_FOUND error on the file URI. More subtly: files uploaded to the Files API require polling until their state transitions from `PROCESSING` to `ACTIVE`. If the background task sends the file URI to the model while the file is still `PROCESSING`, the API returns an error.

**Why it happens:**
Developers coming from the inline-data pattern (or from faster-whisper's local file access) don't account for the asynchronous activation step in the Files API. The background task `run_ai_feedback` currently does a synchronous pipeline (transcribe → assess). With the Files API, there is now an additional async step (upload → poll → use) that breaks the linear pattern.

**How to avoid:**
1. Poll `client.files.get(name=file.name)` in a loop until `file.state.name == "ACTIVE"`, with a sleep of 5–10 seconds per iteration and a maximum retry count (e.g., 30 attempts = 5 minutes timeout).
2. Raise `RuntimeError` if the file never becomes ACTIVE — this surfaces as a FAILED job with a clear error message.
3. Do not store file URIs in the database for later re-use — they expire. The upload is always per-job.
4. For sessions where the audio is under ~15 MB total request size (short sessions), use inline data (`types.Part.from_bytes()`) instead of the Files API to eliminate the TTL and polling concerns entirely.

**Warning signs:**
- Jobs fail intermittently only on retry (first attempt succeeds)
- Error messages contain "File not found" or "File state is not ACTIVE"
- Processing time spikes under load (file processing backlog at Google's end)

**Phase to address:** Phase 1 (Gemini client setup) — implement the upload-and-poll helper before any assessment logic is written.

---

### Pitfall 3: Test suite mocks the wrong layer — 103 tests break or give false confidence

**What goes wrong:**
The existing 103 tests mock `session.services.transcription.transcribe_session` and `session.services.assessment.assess_session` at the function level (e.g., `@patch("session.services.assessment.assess_session", return_value=MOCK_ASSESSMENT_RESULT)`). They also mock `anthropic` via `patch.dict(sys.modules, {"anthropic": mock_module})`. After replacing Claude with Gemini, the `anthropic` mock becomes irrelevant, and the `assess_session` function signature and raise contract must be preserved exactly — otherwise the 103 tests that mock at the service boundary will silently diverge from production behavior.

There are also transcription tests that mock `faster_whisper.WhisperModel` directly. After removing faster-whisper, these tests will either fail to import or mock a nonexistent module.

**Why it happens:**
When replacing two services simultaneously (transcription + assessment), developers focus on getting the new code to work and forget to audit which tests mock at module level vs. function level. Module-level mocks survive the replacement cleanly; SDK-level mocks don't.

**How to avoid:**
1. Inventory every test that uses `patch.dict(sys.modules, {"anthropic": ...})` or `patch("faster_whisper.WhisperModel", ...)` — these are the only tests that need to change.
2. Tests that mock at the service function boundary (`patch("session.services.assessment.assess_session", ...)`) need zero changes — they mock the same function name regardless of what's inside it.
3. Replace anthropic module-level tests with equivalent google-genai module-level tests using `patch("google.genai.Client", ...)` or equivalent mock for the new SDK.
4. Confirm the `assess_session` function still raises `RuntimeError` on all failure paths (missing criteria, invalid band, API error) — the task's `except Exception` block depends on this contract.
5. Run `python manage.py test session` after removing `faster-whisper` from requirements; any remaining `ImportError` on WhisperModel indicates a test that needs updating.

**Warning signs:**
- `ImportError: No module named 'faster_whisper'` in tests after requirements cleanup
- Tests pass with `patch("anthropic", ...)` that no longer imports in production
- `assert_called_once_with` on the old SDK client passes because the mock was never exercised

**Phase to address:** Phase 2 (replace assessment service) — run the full test suite immediately after removing the anthropic import; fix all SDK-level mocks before writing new Gemini tests.

---

### Pitfall 4: Gemini structured output integer constraints are not enforced by the SDK validator

**What goes wrong:**
Claude's `tool_use` with `tool_choice={"type": "tool"}` forces a structured tool call with strict schema enforcement. Gemini's `response_schema` with Pydantic or JSON schema does not enforce `minimum`/`maximum` constraints on integer fields at the SDK level — the SDK validates structure (required fields, types) but leaves value-range constraints as model-best-effort. Gemini can return a band score of 0 or 10 — values that pass SDK parsing but violate the IELTS 1–9 requirement. The existing `assess_session` function validates `1 <= band <= 9` and raises `RuntimeError` on violation; this validation must be preserved in the new implementation.

**Why it happens:**
Developers see "structured output" and assume it provides the same guarantees as Claude's tool enforcement. The Pydantic model compiles and the API call succeeds, but the band value is wrong. Since unit tests mock `assess_session`, the invalid-band path is only exercised in dedicated assessment service tests — which may have been updated to mock Gemini without preserving the validation test.

**How to avoid:**
1. Keep the explicit `if not isinstance(band, int) or not (1 <= band <= 9)` validation in `assess_session` regardless of schema.
2. Do not remove the existing `TestAssessmentService` tests for invalid band values — they must all pass against the new Gemini implementation.
3. Include the range constraint in the system prompt as a redundant instruction: "band must be an integer from 1 to 9 inclusive".
4. If using Pydantic schema, add a `Field(ge=1, le=9)` annotation even though it won't be enforced by the SDK — it documents intent and may be enforced by future SDK versions.

**Warning signs:**
- Band value of 0 or 10 in CriterionScore records
- `overall_band` computation returns unexpected values (e.g., 4.5 from a band-0 score)
- Integration tests pass but production scores are out of range

**Phase to address:** Phase 2 (replace assessment service) — ensure validation tests from `TestAssessmentServiceWithClaude` are ported to `TestAssessmentServiceWithGemini` before removing the old tests.

---

### Pitfall 5: Gemini safety filters block legitimate IELTS speaking samples

**What goes wrong:**
Gemini's default safety settings (`BLOCK_MEDIUM_AND_ABOVE`) can classify IELTS speaking samples as potentially harmful if candidates discuss sensitive topics (crime, violence, health issues, political events — all common IELTS Part 3 themes). When a response is blocked, `response.candidates[0].finish_reason` is `FinishReason.SAFETY`, and `response.text` raises a `ValueError` (it does not return empty string). If the assessment code accesses `response.text` or the structured response without checking `finish_reason` first, it crashes with an unhandled exception — the job fails with a cryptic error message, not a clear "safety block" message.

**Why it happens:**
Claude does not have equivalent safety filters that block educational/assessment content at this level. Developers porting from Claude assume the response is always a valid content completion if no exception was raised.

**How to avoid:**
1. After every `generate_content` call, check `response.candidates[0].finish_reason` before accessing any response content.
2. If `finish_reason == "SAFETY"`, raise a descriptive `RuntimeError("Gemini safety filter blocked the response. Consider adjusting safety settings or rephrasing the prompt.")` — the task will record this in `job.error_message`.
3. For the assessment use case, configure safety settings to `BLOCK_ONLY_HIGH` for `HARM_CATEGORY_DANGEROUS_CONTENT` and `HARM_CATEGORY_HARASSMENT` — these are the categories most likely to be triggered by spoken language assessment. Do not disable safety filters entirely.
4. Test with IELTS Part 3 topics that involve crime, politics, or controversial social issues to verify safety settings are appropriate.

**Warning signs:**
- Jobs fail with `ValueError: response.text` or `AttributeError` accessing structured output
- `finish_reason` is `SAFETY` in logs
- Certain session topics consistently cause failures while others succeed

**Phase to address:** Phase 2 (replace assessment service) — add safety filter handling before any test with real audio content.

---

### Pitfall 6: Removing the transcription step silently breaks the `transcript` field contract

**What goes wrong:**
`AIFeedbackJob.transcript` was populated by faster-whisper in the v1.3 pipeline. With Gemini direct audio, there is no separate transcription step — Gemini processes audio natively. If the new pipeline sets `job.transcript = None` (or never writes to it), the GET endpoint's response schema will silently change: the API currently returns `transcript` in the response body. The API docs (`docs/api/ai-feedback.md`) document this field. Downstream clients that rely on the transcript field will break.

There is also a migration concern: existing `AIFeedbackJob` records in production have non-null `transcript` values from the v1.3 pipeline. New jobs will have null transcripts. The field must remain in the model and the API response — but its semantics change from "always populated" to "populated only if transcription was performed separately."

**Why it happens:**
When removing the transcription step, developers delete the `job.transcript = transcript` line and the `save(update_fields=["transcript", "updated_at"])` call without checking what the GET endpoint returns for that field.

**How to avoid:**
1. Do not remove `AIFeedbackJob.transcript` from the model — it must remain for backward compatibility with existing records.
2. In the new pipeline, if Gemini provides a transcript alongside scores (via structured output), write it to `job.transcript`. If not, leave the field null and update the API docs to note it is optional.
3. Update `docs/api/ai-feedback.md` to reflect that `transcript` may be null for Gemini-processed jobs.
4. No migration needed — the field is already nullable.

**Warning signs:**
- GET `/api/sessions/{id}/ai-feedback/` starts returning `"transcript": null` for new jobs while old jobs returned a string
- Frontend parsing errors if the frontend treats transcript as non-nullable

**Phase to address:** Phase 1 (design review) — decide the transcript field policy before writing any new assessment code.

---

### Pitfall 7: django-q2 worker timeout too short for Gemini audio processing

**What goes wrong:**
The existing pipeline runs two serial operations: faster-whisper CPU transcription (typically 30–120 seconds for a 15-minute session on the deploy target) + Claude API call (typically 5–15 seconds). Total: ~2 minutes. Gemini audio processing may take 30–120 seconds depending on audio length and model load, but also includes a Files API upload (network I/O to Google's servers) and a polling wait for the file to become ACTIVE. Under the default django-q2 timeout, long jobs may be killed mid-execution and left in PROCESSING status indefinitely (the task is killed, not gracefully interrupted — `except` blocks don't run).

**Why it happens:**
The django-q2 `timeout` setting in `Q_CLUSTER` was sized for the CPU-bound faster-whisper workload. Network latency to Google's API adds an unpredictable ceiling. 504 DEADLINE_EXCEEDED errors from Gemini itself for large audio have been reported in community forums.

**How to avoid:**
1. Check `settings.Q_CLUSTER["timeout"]` — if not set, the default is `None` (no timeout). If a timeout is set, increase it to at least 300 seconds (5 minutes).
2. Set a connection timeout on the Gemini client separately to fail fast if the API hangs, before the django-q2 timeout kills the worker process.
3. If the Files API upload is used, count the polling loop time in the total budget.
4. Test with a 15-minute webm file from the deploy target to measure actual end-to-end task duration before deploying.

**Warning signs:**
- Jobs stuck in PROCESSING status without ever transitioning to DONE or FAILED
- django-q2 worker logs show "Task timed out" or worker restarts
- `job.error_message` is null on FAILED jobs (indicates worker was killed, not that an exception was caught)

**Phase to address:** Phase 1 (infrastructure setup) — audit `Q_CLUSTER` config and Gemini client timeout before writing assessment code.

---

### Pitfall 8: Wrong SDK package — `google-generativeai` is deprecated

**What goes wrong:**
A search for "google gemini python sdk" returns both `google-generativeai` (deprecated) and `google-genai` (the current unified SDK). If `google-generativeai` is installed, the import path is `import google.generativeai as genai`. The new SDK uses `from google import genai` with a `genai.Client()` pattern. These are incompatible. Mixing documentation examples from the two SDKs produces `AttributeError` errors that are difficult to diagnose.

**Why it happens:**
PyPI search results and older tutorials still reference `google-generativeai`. The deprecation notice is not prominent in all documentation paths.

**How to avoid:**
1. Install `google-genai` (the new unified SDK), not `google-generativeai`.
2. Use `from google import genai` and `client = genai.Client(api_key=...)` throughout.
3. Add `# Uses google-genai SDK (not deprecated google-generativeai)` as a comment in `assessment.py` to prevent future confusion.

**Warning signs:**
- `AttributeError: module 'google.generativeai' has no attribute 'Client'`
- Import path confusion between `google.generativeai` and `google.genai`

**Phase to address:** Phase 1 (Gemini client setup) — lock the correct package in requirements before any code is written.

---

## Technical Debt Patterns

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Upload audio inline (skip Files API) for all files | Simpler code, no polling | Fails for sessions > ~15 MB audio (100 MB request limit); silent 400 error | Only if sessions are guaranteed short (< 5 minutes) |
| Skip transcript storage in new pipeline | Less code, cleaner pipeline | Breaks API contract for clients that read `transcript`; loses debugging aid | Never — keep the field, set to null if not transcribing |
| Remove `assess_session`'s band validation after switching to structured output | Simpler code | Out-of-range bands from Gemini reach the database silently | Never — validation costs 4 lines, prevents corrupt scores |
| Reuse existing anthropic-style `patch.dict(sys.modules, ...)` tests with Gemini mock | Less test rewriting | Tests exercise mock infrastructure that doesn't match Gemini SDK's actual interface | Never — mock the correct module for each SDK |
| Not polling for Files API ACTIVE state | Simpler upload code | Race condition: model returns error if file still PROCESSING | Never — polling is required by the API |
| Disable all safety filters via `BLOCK_NONE` | Eliminates safety-blocked failures | Violates Google API ToS for some use cases; may expose model to prompt injection via audio | Avoid — use `BLOCK_ONLY_HIGH` instead |

---

## Integration Gotchas

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Gemini Files API | Call `generate_content` immediately after `client.files.upload()` returns | Poll `client.files.get(name)` until `file.state == "ACTIVE"` before calling generate_content |
| Gemini Files API | Assume uploaded file persists for the job's lifetime | Files expire after 48 hours; upload fresh per-job, do not store the URI |
| google-genai SDK | Access `response.text` to get model output | Check `response.candidates[0].finish_reason` first; use structured response object |
| google-genai SDK | Catch `Exception` generically with no distinction | Use `google.api_core.exceptions.GoogleAPIError` hierarchy; distinguish `ResourceExhausted` (429) from `DeadlineExceeded` (504) |
| google-genai SDK | Import `google.generativeai` (deprecated library) | Use `google.genai` (new unified SDK, `pip install google-genai`) |
| Gemini structured output | Assume Pydantic `ge=1, le=9` enforces the range | Validate bands explicitly after parsing — the SDK does not enforce integer range constraints |
| Gemini safety filters | Assume no exception means content was generated | Check `finish_reason` — `SAFETY` blocks return no exception but also no content |
| webm audio | Pass `mime_type="audio/webm"` without verifying support | Validate against a real file in a smoke-test before deployment; prepare MP3 fallback conversion |

---

## Performance Traps

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Loading full audio file into memory for inline upload | High memory per concurrent job | Use streaming upload via Files API; avoid `audio_file.read()` for large files | At ~2 concurrent jobs with 50 MB audio each |
| Synchronous polling loop inside background task | Worker thread blocked; other tasks starved | Cap polling to 30 iterations × 10 seconds = 5 minutes; raise RuntimeError on timeout | At high job concurrency (5+ simultaneous jobs) |
| Always using Files API for all audio | Extra upload latency (~2–10 sec) for short sessions | Use inline data for files under 15 MB; Files API only for larger files | Latency noticeable for short sessions (< 5 minutes) |
| No retry logic for transient Gemini 503 errors | FAILED job on a retriable error | Catch `google.api_core.exceptions.ServiceUnavailable`, retry up to 3 times with exponential backoff | Intermittently, under Google API load |

---

## Cost Considerations

Audio input to Gemini costs 3–7x more per token than text input, depending on model. Gemini counts 32 tokens per second of audio. A 15-minute IELTS session = 900 seconds = 28,800 audio input tokens. At Gemini 2.5 Flash rates ($1.00/M audio tokens), one assessment costs ~$0.029 in audio input alone — roughly 6–10x the previous Claude text-based assessment cost (which consumed ~2,000–3,000 text tokens per session at $3/M). The monthly limit of 10 jobs per examiner (`AI_FEEDBACK_MONTHLY_LIMIT`) was sized for the old cost model. Verify this limit remains appropriate at the new cost level before removing it.

---

## Security Mistakes

| Mistake | Risk | Prevention |
|---------|------|------------|
| Logging audio file path in Gemini error messages | Audio path leaks into `error_message` field, visible in job status response | Sanitize error messages before storing in `job.error_message`; log full path only to server logs |
| Storing `GOOGLE_API_KEY` in settings.py directly | Key committed to version control | Use `settings.GOOGLE_API_KEY = os.environ.get("GOOGLE_API_KEY")`; add to `.env`; same pattern as existing `ANTHROPIC_API_KEY` |
| Passing raw candidate audio to Gemini without content review | Audio may contain PII or sensitive content not intended for Google | This is a policy decision, not a code fix; document it; ensure privacy policy covers AI processing of recordings |

---

## "Looks Done But Isn't" Checklist

- [ ] **webm format acceptance:** Gemini client was tested with a real webm file, not just a mock — verify actual API acceptance in a smoke-test.
- [ ] **Files API polling:** Code checks `file.state == "ACTIVE"` before calling `generate_content` — verify by inspecting the upload helper, not trusting that "it works in dev."
- [ ] **Band validation preserved:** `assess_session` still raises `RuntimeError` for bands outside 1–9 — verify the existing `test_invalid_band_raises` test passes against the new implementation.
- [ ] **Safety filter handling:** Code checks `finish_reason` before accessing response content — verify by patching a `SAFETY`-blocked response in a unit test.
- [ ] **transcript field contract:** GET `/api/sessions/{id}/ai-feedback/` response still includes `transcript` key — verify by running the existing delivery tests after replacing the pipeline.
- [ ] **Monthly limit and select_for_update preserved:** The race-prevention logic in views.py was not accidentally removed — verify the existing monthly limit tests still pass.
- [ ] **Error message in FAILED job:** When Gemini returns a 429, the job transitions to FAILED with `error_message` set — verify by mocking `ResourceExhausted` and checking `job.error_message`.
- [ ] **django-q2 timeout:** `Q_CLUSTER` timeout is at least 300 seconds OR explicitly set to `None` — verify `settings.Q_CLUSTER` before deploying.
- [ ] **Old SDK removed from requirements:** `anthropic` and `faster-whisper` are absent from `requirements.txt` after replacement — verify no lingering import in any production code path.
- [ ] **API docs updated:** `docs/api/ai-feedback.md` reflects that `transcript` may be null for Gemini jobs — verify docs match the actual response.
- [ ] **Correct SDK package:** `google-genai` is installed, not `google-generativeai` — verify `pip show google-genai` and `pip show google-generativeai` outputs.

---

## Recovery Strategies

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| webm rejected in production | MEDIUM | Add ffmpeg conversion in the background task; redeploy; re-trigger failed jobs manually |
| Jobs stuck in PROCESSING (timeout kill) | LOW | Write a management command to reset PROCESSING jobs older than N minutes to FAILED; configure `Q_CLUSTER["timeout"]` |
| Safety filter blocks legitimate sessions | LOW | Add safety settings config to generate_content call (`BLOCK_ONLY_HIGH`); redeploy |
| Out-of-range bands in database | HIGH | Write a data migration to delete CriterionScore records with band outside 1–9; add DB-level constraint via migration; re-trigger affected jobs |
| Tests pass but production assessment broken | MEDIUM | Add a real-API smoke-test excluded from CI but run manually pre-deploy; use it to gate releases |
| Transcript field unexpectedly null in API response | LOW | Update API docs; confirm frontend handles null gracefully; no model migration needed |
| Wrong SDK package installed | LOW | `pip uninstall google-generativeai && pip install google-genai`; update imports; re-run test suite |

---

## Pitfall-to-Phase Mapping

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| webm format unverified | Phase 1: Gemini client setup | Smoke-test with real webm file passes against live API |
| Files API TTL + polling missing | Phase 1: Gemini client setup | Upload helper tested with polling loop; `ACTIVE` check present |
| Wrong SDK package (`google-generativeai`) | Phase 1: Gemini client setup | `pip show google-generativeai` returns "not installed" |
| django-q2 timeout too short | Phase 1: Infrastructure setup | `Q_CLUSTER` timeout documented and set in settings |
| Transcript field contract broken | Phase 1: Design review | Existing delivery tests pass without modification |
| Test suite mocks wrong layer | Phase 2: Replace assessment service | `python manage.py test session` passes with anthropic and faster-whisper uninstalled |
| Band validation removed | Phase 2: Replace assessment service | Existing band-validation tests pass unchanged against new assess_session |
| Safety filter crash | Phase 2: Replace assessment service | Unit test for `SAFETY` finish_reason passes |
| Monthly limit / select_for_update lost | Phase 2: Replace assessment service | Existing monthly limit tests pass unchanged |
| Old SDK not removed from requirements | Phase 3: Cleanup | Fresh venv install has no `anthropic` or `faster-whisper` |
| API docs not updated | Phase 3: Cleanup | `docs/api/ai-feedback.md` reflects nullable transcript |

---

## Sources

- [Gemini API audio documentation](https://ai.google.dev/gemini-api/docs/audio) — confirmed supported formats list (webm absent from this page); 32 tokens/second; inline 20 MB limit
- [Firebase AI Logic input file requirements](https://firebase.google.com/docs/ai-logic/input-file-requirements) — `audio/webm` listed as supported MIME type
- [Gemini Files API documentation](https://ai.google.dev/gemini-api/docs/files) — 48-hour TTL, 2 GB max file size, 20 GB project limit
- [Gemini API structured outputs](https://ai.google.dev/gemini-api/docs/structured-output) — JSON Schema support, Pydantic integration, no integer range enforcement
- [Gemini API pricing](https://ai.google.dev/gemini-api/docs/pricing) — audio input 3–7x more expensive than text per million tokens
- [Google Gen AI Python SDK documentation](https://googleapis.github.io/python-genai/) — current unified SDK reference (`google-genai` package)
- [Gemini API safety settings](https://ai.google.dev/gemini-api/docs/safety-settings) — HARM_BLOCK_THRESHOLD configuration
- [Gemini API 504 DEADLINE_EXCEEDED community reports](https://discuss.ai.google.dev/t/gemini-2-5-pro-throws-504-deadline-exceeded-error/90991) — confirmed latency issues for large audio files
- [Structured output reliability comparison across LLM providers](https://www.glukhov.org/post/2025/10/structured-output-comparison-popular-llm-providers) — Gemini does not enforce integer range constraints
- [Gemini Files API always PROCESSING community issue](https://discuss.ai.google.dev/t/file-api-always-processing/85107) — confirmed polling required before use
- [Gemini API increased file size limits blog post](https://blog.google/innovation-and-ai/technology/developers-tools/gemini-api-new-file-limits/) — inline data increased from 20 MB to 100 MB
- Session codebase: `session/tasks.py`, `session/services/assessment.py`, `session/services/transcription.py`, `session/tests.py`, `session/models.py`, `session/views.py`

---
*Pitfalls research for: Replacing text-based AI assessment pipeline with Gemini audio assessment (MockIT v1.4)*
*Researched: 2026-04-09*
