# Phase 11: Transcription Service - Research

**Researched:** 2026-04-07
**Domain:** faster-whisper CPU transcription integrated into a django-q2 background task
**Confidence:** HIGH

## Summary

Phase 11 fleshes out the `run_ai_feedback()` task skeleton (from Phase 10) with real transcription logic using `faster-whisper`. The library is not yet installed in the project venv and must be added to `requirements.txt` and installed as part of this phase. Audio files are stored as `.webm` (confirmed from `media/recordings/`); faster-whisper handles webm natively via its bundled PyAV dependency — no separate ffmpeg install needed.

The `AIFeedbackJob` model needs one new field: `transcript = TextField(null=True, blank=True)`. A single migration covers this. The task reads `job.session.recording.audio_file.path`, builds an `initial_prompt` from all `SessionQuestion` texts, runs `WhisperModel.transcribe()`, assembles plain-text output with `Examiner:`/`Candidate:` speaker labels, and saves the result to `job.transcript`.

**Primary recommendation:** Implement a `session/services/transcription.py` module with a single `transcribe_session(job)` function, called from `run_ai_feedback()`. Keep model loading lazy (instantiated inside the function) to avoid import-time cost and match the existing deferred-import pattern in the codebase.

## Project Constraints (from CLAUDE.md)

- Tests run via `python manage.py test` (Django test runner, not pytest)
- Single test via `python manage.py test session.tests.TestClassName.test_method`
- Test settings: `DJANGO_SETTINGS_MODULE=MockIT.settings_test` (SQLite in-memory, Q_CLUSTER sync=True)
- django-q2 with ORM broker — no Redis/Celery
- Deferred imports inside task functions to prevent circular dependency at module load
- Side effects (broadcast, etc.) placed after `transaction.atomic` exits
- Background task pattern: `run_ai_feedback()` in `session/tasks.py`

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Transcript Storage & Format**
- Store transcript as a TextField on AIFeedbackJob model (co-located with job status, simple query)
- Transcript format: plain text with speaker labels (Examiner:/Candidate:) — readable, sufficient for Claude API input
- Whisper model size configured via Django setting `WHISPER_MODEL_SIZE` with env variable override (matches existing env config pattern)

**Question Context Integration**
- Use Whisper's `initial_prompt` parameter with session question text to improve transcription accuracy
- Include all SessionQuestions from all parts (not just current part)
- Build prompt string by concatenating question texts separated by periods

**Error Handling & Edge Cases**
- Missing audio file: set job status to FAILED with clear error message
- Whisper import failure: graceful FAILED status with install instructions in error_message
- Empty/corrupt audio: FAILED status with descriptive error message

### Claude's Discretion
- Internal structure of the transcription service module
- Whisper model loading strategy (lazy load vs eager)
- Exact speaker label format details

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope.
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| TRNS-01 | Examiner can trigger transcription of a session recording after the session ends | `run_ai_feedback()` is the trigger point; job is created and enqueued by the caller (already established in Phase 10); this task does the work |
| TRNS-02 | System transcribes audio to text using faster-whisper (CPU, configurable model size) | `WhisperModel(model_size, device="cpu", compute_type="int8")` where `model_size = getattr(settings, "WHISPER_MODEL_SIZE", "base")` |
| TRNS-03 | Transcript is stored and associated with the session for later retrieval | `AIFeedbackJob.transcript` TextField; queryable via `AIFeedbackJob.objects.get(session=session)` |
| TRNS-04 | Transcription incorporates SessionQuestion context for improved accuracy | Whisper `initial_prompt` parameter built from all `SessionQuestion` texts across all parts |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| faster-whisper | 1.2.1 (released 2026-10-31) | CPU speech-to-text via CTranslate2 | Locked decision; 4x faster than openai/whisper, CPU-friendly int8 mode |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyAV | (bundled with faster-whisper) | Audio decoding including webm | Installed automatically as faster-whisper dependency; no extra install |
| ctranslate2 | (bundled with faster-whisper) | CTranslate2 inference engine | Installed automatically as faster-whisper dependency |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| faster-whisper | openai-whisper | 4x slower, higher memory, locked decision against it |
| lazy model load | eager load at import | Eager load delays server startup, wastes memory if task never runs; lazy is correct here |

**Installation:**
```bash
pip install faster-whisper==1.2.1
```

Add to `requirements.txt`:
```
faster-whisper==1.2.1
```

**Version verification:** Confirmed against PyPI on 2026-04-07. Latest stable is 1.2.1 (released 2025-10-31).

## Architecture Patterns

### Recommended Project Structure
```
session/
├── tasks.py              # run_ai_feedback() — calls transcription service
├── services/
│   ├── hms.py            # existing HMS video room service
│   └── transcription.py  # NEW: transcribe_session(job) function
```

### Pattern 1: Lazy-Loaded WhisperModel in Service Module
**What:** Instantiate `WhisperModel` inside the service function, not at module import time.
**When to use:** Always — matches project's existing deferred-import pattern; avoids startup cost when Whisper is not needed.
**Example:**
```python
# session/services/transcription.py
import logging
from django.conf import settings

logger = logging.getLogger(__name__)


def transcribe_session(job) -> str:
    """
    Transcribe session audio and return plain-text transcript with speaker labels.
    Raises on unrecoverable error; caller handles status update.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError(
            "faster-whisper is not installed. Run: pip install faster-whisper"
        )

    # Validate recording exists
    try:
        recording = job.session.recording
    except Exception:
        raise RuntimeError("Session has no associated recording.")

    audio_path = recording.audio_file.path
    if not audio_path:
        raise RuntimeError("SessionRecording.audio_file is empty.")

    # Build initial_prompt from all session question texts
    from session.models import SessionQuestion
    questions = (
        SessionQuestion.objects
        .filter(session_part__session=job.session)
        .select_related("question")
        .order_by("session_part__part", "order")
    )
    prompt_parts = [sq.question.text for sq in questions if sq.question.text]
    initial_prompt = ". ".join(prompt_parts) if prompt_parts else None

    # Load model (lazy, inside function)
    model_size = getattr(settings, "WHISPER_MODEL_SIZE", "base")
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    segments, _info = model.transcribe(
        audio_path,
        beam_size=5,
        initial_prompt=initial_prompt,
        language="en",
    )

    # Assemble transcript — segments are a generator; consume once
    lines = []
    for segment in segments:
        # Speaker labels: Phase 11 uses "Examiner:" for all (no diarization yet)
        lines.append(f"Examiner: {segment.text.strip()}")

    return "\n".join(lines)
```

### Pattern 2: Task Integration in run_ai_feedback()
**What:** Call `transcribe_session(job)` inside the existing task skeleton and save result to `job.transcript`.
**When to use:** The only integration point — don't duplicate status logic.
**Example:**
```python
# session/tasks.py  (Phase 11 additions only)
def run_ai_feedback(job_id: int) -> None:
    from session.models import AIFeedbackJob

    try:
        job = AIFeedbackJob.objects.get(pk=job_id)
        job.status = AIFeedbackJob.Status.PROCESSING
        job.save(update_fields=["status", "updated_at"])

        # Phase 11: transcription
        from session.services.transcription import transcribe_session
        transcript = transcribe_session(job)
        job.transcript = transcript
        job.save(update_fields=["transcript", "updated_at"])

        # Phase 12 will add: AI scoring via Claude API

        job.status = AIFeedbackJob.Status.DONE
        job.save(update_fields=["status", "updated_at"])

    except AIFeedbackJob.DoesNotExist:
        logger.error("run_ai_feedback: job_id=%s not found", job_id)
    except Exception as exc:
        logger.exception("run_ai_feedback job_id=%s failed: %s", job_id, exc)
        try:
            job.status = AIFeedbackJob.Status.FAILED
            job.error_message = str(exc)
            job.save(update_fields=["status", "error_message", "updated_at"])
        except Exception:
            pass
```

### Pattern 3: Model Field Addition + Migration
**What:** Add `transcript = TextField(null=True, blank=True)` to `AIFeedbackJob`.
**When to use:** One migration for this phase.
**Example:**
```python
# In AIFeedbackJob model
transcript = models.TextField(null=True, blank=True)
```
Migration command: `python manage.py makemigrations session --name add_transcript_to_aifeedbackjob`

### Pattern 4: Django Setting for Model Size
**What:** Add `WHISPER_MODEL_SIZE` to settings.py, reading from env var.
**When to use:** Matches existing env-driven config pattern (`HMS_APP_ACCESS_KEY`, etc.).
**Example:**
```python
# settings.py
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base")
```

### Anti-Patterns to Avoid
- **Eager WhisperModel instantiation at module level:** Runs at server startup; wastes memory if transcription is never triggered; causes ImportError if faster-whisper is missing.
- **Consuming segments generator twice:** `model.transcribe()` returns a lazy generator; calling it twice yields nothing the second time. Consume into a list or build output in one pass.
- **Storing audio path as string directly:** Always use `recording.audio_file.path` (Django resolves MEDIA_ROOT prefix); don't concatenate manually.
- **Missing select_related on SessionQuestion query:** Causes N+1 queries fetching `question.text` for each row. Use `select_related("question")`.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Speech-to-text | Custom audio parsing | faster-whisper | Handles silence, accents, noise; CTranslate2 inference is heavily optimized |
| Audio format decoding (webm, mp4, etc.) | ffmpeg subprocess calls | faster-whisper + PyAV | PyAV bundles FFmpeg libs; no subprocess, no system dependency |
| Vocabulary/context injection | Custom audio preprocessing | `initial_prompt` parameter | Whisper's built-in context window conditioning is the correct mechanism |

**Key insight:** The `initial_prompt` parameter is the correct, library-supported mechanism for vocabulary priming. Don't preprocess audio or fine-tune the model.

## Common Pitfalls

### Pitfall 1: faster-whisper Not Installed
**What goes wrong:** `ImportError: No module named 'faster_whisper'` inside the background task; job gets FAILED status with an unhelpful traceback.
**Why it happens:** Package is not yet in `requirements.txt` and has not been installed in the venv.
**How to avoid:** Install in venv AND add to `requirements.txt` before running any task tests. The `try/except ImportError` in `transcribe_session()` produces a readable error message.
**Warning signs:** `ModuleNotFoundError` in task error_message field.

### Pitfall 2: SessionRecording Does Not Exist
**What goes wrong:** `RelatedObjectDoesNotExist` when accessing `job.session.recording`; task crashes to FAILED.
**Why it happens:** Not all sessions have a recording (session ended without the client uploading audio).
**How to avoid:** Wrap recording access in a try/except and raise a clear `RuntimeError("Session has no associated recording.")`. The error propagates to the outer handler which sets FAILED + error_message.
**Warning signs:** `session.sessionrecording.RelatedObjectDoesNotExist` in logs.

### Pitfall 3: Segments Generator Exhausted
**What goes wrong:** Transcript is empty even though audio exists.
**Why it happens:** `model.transcribe()` returns a lazy generator. If code iterates it once (e.g., to check `len()`), the second iteration yields nothing.
**How to avoid:** Consume the generator in a single pass. Never call `list(segments)` and then iterate `segments` again.
**Warning signs:** Empty `job.transcript` with no error, job status DONE.

### Pitfall 4: Whisper Model Download on First Run
**What goes wrong:** First transcription task takes minutes because the model weights are downloaded from HuggingFace Hub at runtime.
**Why it happens:** faster-whisper downloads model weights on first use if not already cached (`~/.cache/huggingface/hub`).
**How to avoid:** Pre-download the model once on the deployment machine: `python -c "from faster_whisper import WhisperModel; WhisperModel('base', device='cpu')"`. Document this as a deployment step.
**Warning signs:** Task times out on first run only; subsequent runs are fast.

### Pitfall 5: Missing update_fields for transcript
**What goes wrong:** `transcript` save overwrites status field if `update_fields` is omitted.
**Why it happens:** Django's `save()` without `update_fields` updates all fields; race with another process updating status.
**How to avoid:** Always use `save(update_fields=["transcript", "updated_at"])`.

## Code Examples

### Full WhisperModel CPU Usage
```python
# Source: https://github.com/SYSTRAN/faster-whisper
from faster_whisper import WhisperModel

model = WhisperModel("base", device="cpu", compute_type="int8")
segments, info = model.transcribe("audio.webm", beam_size=5, language="en",
                                   initial_prompt="Tell me about your hobbies.")
for segment in segments:
    print(f"[{segment.start:.2f}s -> {segment.end:.2f}s] {segment.text}")
```

### SessionQuestion Prompt Builder
```python
# Fetch all questions for the session, ordered by part then question order
from session.models import SessionQuestion
questions = (
    SessionQuestion.objects
    .filter(session_part__session=session)
    .select_related("question")
    .order_by("session_part__part", "order")
)
initial_prompt = ". ".join(sq.question.text for sq in questions if sq.question.text)
```

### settings.py env-driven config pattern (existing)
```python
# Existing pattern in settings.py
HMS_APP_ACCESS_KEY = os.environ["HMS_APP_ACCESS_KEY"]

# New — same pattern, with default
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base")
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| openai/whisper (Python) | faster-whisper (CTranslate2) | 2023 | 4x faster, 50% less memory, int8 CPU mode |
| System ffmpeg required | PyAV bundled | faster-whisper v0.x | No system dependency for audio decoding |
| Large model by default | `base` or `small` for CPU | Always recommended | `base` is fast enough for IELTS sessions; `large-v3` on CPU is too slow |

**Deprecated/outdated:**
- `openai-whisper`: Not in scope (locked out by decisions). Requires separate ffmpeg system install.

## Open Questions

1. **Speaker diarization (Examiner vs Candidate labels)**
   - What we know: The decision says `Examiner:`/`Candidate:` labels; faster-whisper alone has no diarization.
   - What's unclear: Whether Phase 11 should apply `Examiner:` to all segments (placeholder) or attempt simple heuristic diarization.
   - Recommendation: Apply `Examiner:` to all segments as a placeholder — consistent with "Claude's Discretion" on exact format. Phase 12 (Claude API) can interpret context. Document as known limitation.

2. **Whisper model cache location on deployment server**
   - What we know: Models are cached in `~/.cache/huggingface/hub` on first use.
   - What's unclear: Whether the deployment environment has write access to that path.
   - Recommendation: Include a one-time pre-download command in deployment notes. Planner should add as a Wave 0 or setup step.

## Environment Availability

| Dependency | Required By | Available | Version | Fallback |
|------------|------------|-----------|---------|----------|
| faster-whisper | TRNS-02 transcription | No | — | None — must install |
| PyAV | webm audio decode | No (comes with faster-whisper) | — | Installed automatically |
| Python 3.11 | faster-whisper >=3.9 req | Yes | 3.11.9 | — |
| `.webm` audio files | TRNS-02 | Yes (confirmed in media/recordings/) | — | — |

**Missing dependencies with no fallback:**
- `faster-whisper==1.2.1` — must be installed with `pip install faster-whisper==1.2.1` and added to `requirements.txt` before any task can run.

**Missing dependencies with fallback:**
- None.

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Django TestCase (built-in) |
| Config file | `MockIT/settings_test.py` |
| Quick run command | `python manage.py test session.tests.RunAIFeedbackTaskTests --settings=MockIT.settings_test` |
| Full suite command | `python manage.py test --settings=MockIT.settings_test` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| TRNS-01 | `run_ai_feedback()` reads recording from completed session and sets transcript | integration | `python manage.py test session.tests.RunAIFeedbackTaskTests.test_task_transcribes_audio --settings=MockIT.settings_test` | No — Wave 0 |
| TRNS-02 | WhisperModel called with correct model_size, device=cpu, compute_type=int8 | unit (mock) | `python manage.py test session.tests.TranscriptionServiceTests.test_calls_whisper_model --settings=MockIT.settings_test` | No — Wave 0 |
| TRNS-03 | After task completes, job.transcript is non-empty and job is queryable by session | integration | `python manage.py test session.tests.RunAIFeedbackTaskTests.test_transcript_stored_on_job --settings=MockIT.settings_test` | No — Wave 0 |
| TRNS-04 | initial_prompt includes all SessionQuestion texts joined by periods | unit | `python manage.py test session.tests.TranscriptionServiceTests.test_initial_prompt_built_from_questions --settings=MockIT.settings_test` | No — Wave 0 |

**Note:** All faster-whisper calls in tests MUST be mocked with `unittest.mock.patch` — loading a real model requires downloaded weights and takes minutes. Mock `faster_whisper.WhisperModel` to return fake segments.

### Sampling Rate
- **Per task commit:** `python manage.py test session.tests.RunAIFeedbackTaskTests --settings=MockIT.settings_test`
- **Per wave merge:** `python manage.py test --settings=MockIT.settings_test`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `session/tests.py` — `TranscriptionServiceTests` class (unit tests for `transcription.py` service, mocking WhisperModel)
- [ ] `session/tests.py` — `RunAIFeedbackTaskTests` (extend existing class with TRNS-01, TRNS-03 integration tests using mocked WhisperModel)
- [ ] `session/services/__init__.py` — empty init file if `session/services/` directory does not exist
- [ ] `session/services/transcription.py` — new transcription service module
- [ ] `session/migrations/0011_add_transcript_to_aifeedbackjob.py` — generated by `makemigrations`
- [ ] `requirements.txt` — add `faster-whisper==1.2.1`

## Sources

### Primary (HIGH confidence)
- https://pypi.org/project/faster-whisper/ — version 1.2.1, Python requirements, CPU compute_type recommendations
- https://github.com/SYSTRAN/faster-whisper — WhisperModel constructor, transcribe() parameters, segment attributes, CPU recommendations

### Secondary (MEDIUM confidence)
- WebSearch + PyPI page cross-verification — confirmed version 1.2.1, release date 2025-10-31
- faster-whisper GitHub issue #207 — PyAV bundles FFmpeg, no system dependency; webm works natively

### Tertiary (LOW confidence)
- None.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — version confirmed against PyPI registry on research date
- Architecture: HIGH — patterns derived from existing codebase conventions + official faster-whisper API
- Pitfalls: HIGH — most derived from direct codebase inspection (missing recording, generator exhaustion) + confirmed faster-whisper behavior

**Research date:** 2026-04-07
**Valid until:** 2026-05-07 (faster-whisper is stable; SYSTRAN maintains it actively)
