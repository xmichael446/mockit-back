# Architecture Research

**Domain:** AI feedback integration into existing Django IELTS mock exam platform
**Researched:** 2026-04-07
**Confidence:** HIGH (existing codebase inspected directly; patterns verified against Django/Channels docs)

## Standard Architecture

### System Overview — Current State (v1.2 baseline)

```
REST Client (React)                WebSocket Client (React)
       |                                    |
       | HTTP + Token auth                  | ws/?token=...
       v                                    v
┌─────────────────────────────────────────────────────────┐
│                   Daphne (ASGI)                          │
├──────────────────┬──────────────────────────────────────┤
│   HTTP Router    │         WebSocket Router              │
│  (Django views)  │      (SessionConsumer)                │
├──────────────────┴──────────────────────────────────────┤
│                   Django App Layer                        │
│  ┌────────┐  ┌──────────┐  ┌───────────┐  ┌──────────┐  │
│  │ main/  │  │questions/│  │ session/  │  │scheduling│  │
│  │ User   │  │ Question │  │ lifecycle │  │availability│ │
│  │profiles│  │ bank     │  │ models    │  │ requests │  │
│  └────────┘  └──────────┘  └─────┬─────┘  └──────────┘  │
│                                  │                        │
│                          _broadcast()                     │
│                     async_to_sync(group_send)             │
│                                  │                        │
│                    InMemoryChannelLayer                    │
│                                  │                        │
│               SessionConsumer.session_event()             │
│                (forwards to WS client as-is)              │
├──────────────────────────────────────────────────────────┤
│                    Data Layer                             │
│  ┌─────────────────┐  ┌────────────────┐                 │
│  │    PostgreSQL    │  │  Media Storage │                 │
│  │  (all models)   │  │ (audio_file,   │                 │
│  │                 │  │  profile pics) │                 │
│  └─────────────────┘  └────────────────┘                 │
└──────────────────────────────────────────────────────────┘
         |                    |
    100ms API            Resend API
  (video rooms)          (email)
```

### System Overview — Target State (v1.3 with AI Feedback)

```
REST Client                        WebSocket Client
       |                                    |
       | POST /sessions/<pk>/ai-feedback/   |
       v                                    v
┌─────────────────────────────────────────────────────────┐
│                   Daphne (ASGI)                          │
├──────────────────┬──────────────────────────────────────┤
│   HTTP Router    │         WebSocket Router              │
│  (Django views)  │      (SessionConsumer)                │
├──────────────────┴──────────────────────────────────────┤
│                   Django App Layer                        │
│  ┌────────┐  ┌──────────┐  ┌───────────────────────────┐ │
│  │ main/  │  │questions/│  │       session/            │ │
│  │  +     │  │ Question │  │  ┌─────────────────────┐  │ │
│  │monthly │  │ bank     │  │  │ AIFeedbackJob model  │  │ │
│  │usage   │  │          │  │  │ (status + result)   │  │ │
│  │model   │  │          │  │  └─────────────────────┘  │ │
│  └────────┘  └──────────┘  │  ┌─────────────────────┐  │ │
│                             │  │ CriterionScore      │  │ │
│                             │  │ source=CLAUDE enum  │  │ │
│                             │  └─────────────────────┘  │ │
│                             └───────────────────────────┘ │
│                                                           │
│              asyncio.create_task() [fire-and-forget]      │
│                         |                                 │
│         ┌───────────────┴──────────────────┐             │
│         │     session/services/ai.py        │             │
│         │                                   │             │
│         │  1. asyncio.to_thread(            │             │
│         │       whisper.transcribe)         │             │
│         │  2. await anthropic.messages.     │             │
│         │       create(...)                 │             │
│         │  3. ORM write - AIFeedbackJob     │             │
│         │  4. _broadcast("ai_feedback_done")│             │
│         └───────────────────────────────────┘            │
│                                                           │
│                    InMemoryChannelLayer                    │
├──────────────────────────────────────────────────────────┤
│                    Data Layer                             │
│  ┌─────────────────┐  ┌────────────────┐                 │
│  │    PostgreSQL    │  │  Media Storage │                 │
│  │  + AIFeedbackJob │  │  recordings/  │                 │
│  │  + AIMonthlyUsage│  │  (audio files)│                 │
│  └─────────────────┘  └────────────────┘                 │
└──────────────────────────────────────────────────────────┘
              |                   |
        Whisper (local)     Anthropic API
      (CPU-bound, thread)   (Claude messages)
```

## Component Responsibilities

### Existing Components (unchanged)

| Component | Responsibility |
|-----------|---------------|
| `session/models.py` | Session lifecycle, `CriterionScore`, `SessionResult`, `SessionRecording` |
| `session/views.py` | All REST endpoints + `_broadcast()` helper |
| `session/consumers.py` | WebSocket — forwards `session_event` channel messages to clients |
| `session/services/hms.py` | 100ms video room API integration |
| `main/models.py` | `User`, `ExaminerProfile`, `CandidateProfile`, `ScoreHistory` |

### New Components

| Component | Responsibility | Location | New or Modified |
|-----------|---------------|----------|-----------------|
| `AIFeedbackJob` model | Tracks async job status (PENDING/PROCESSING/DONE/FAILED), stores transcript + AI output | `session/models.py` | NEW |
| `AIFeedbackStatus` choices | Status enum for job lifecycle | `session/models.py` | NEW |
| `ScoreSource` choices | `EXAMINER=1`, `CLAUDE=2` — who generated the score | `session/models.py` | NEW |
| `CriterionScore.source` field | Tags each score with its source | `session/models.py` | MODIFIED |
| `AIMonthlyUsage` model | Per-examiner monthly usage counter; enforces limit | `main/models.py` | NEW |
| `session/services/ai.py` | Whisper transcription + Claude API call, writes results, broadcasts completion | `session/services/ai.py` | NEW |
| AI feedback trigger view | POST endpoint — usage check, job creation, task dispatch | `session/views.py` | NEW class |
| AI feedback status view | GET endpoint — returns job status | `session/views.py` | NEW class |
| AI feedback results view | GET endpoint — returns transcript + AI scores | `session/views.py` | NEW class |
| `AIFeedbackJobSerializer` | Serializes job status + result fields | `session/serializers.py` | NEW |

## Recommended Project Structure Changes

```
session/
├── migrations/
│   └── 00XX_ai_feedback_job_score_source.py  # new migration
├── services/
│   ├── hms.py                # unchanged
│   └── ai.py                 # NEW: transcription + Claude feedback pipeline
├── models.py                 # add AIFeedbackJob, ScoreSource enum, CriterionScore.source field
├── views.py                  # add 3 AI feedback view classes
├── urls.py                   # add 3 AI feedback URL patterns
└── serializers.py            # add AIFeedbackJobSerializer

main/
└── models.py                 # add AIMonthlyUsage model + migration
```

### Structure Rationale

- `session/services/ai.py` follows the existing `session/services/hms.py` pattern. External service integrations live in `services/`. The AI pipeline (Whisper + Claude) is session-scoped, so it belongs here, not in a new app.
- `AIFeedbackJob` lives in `session/models.py` because it is a one-to-one extension of `IELTSMockSession`, parallel to `SessionRecording` and `SessionResult`.
- `AIMonthlyUsage` goes in `main/models.py` because it is a per-User tracking model, matching the profile pattern — all user-scoped data (`ExaminerProfile`, `CandidateProfile`, `ScoreHistory`) lives in `main/`.
- No new Django app is needed. This is an extension of `session/`, not a new domain boundary. Creating a new app would introduce circular import complexity without benefit.

## Architectural Patterns

### Pattern 1: Fire-and-Forget Async Task via asyncio.create_task

**What:** The trigger endpoint spawns a background coroutine using `asyncio.create_task()`, returns HTTP 202 immediately, and the task runs to completion in the background under Daphne's event loop.

**When to use:** When Celery/Redis is out of scope and processing time is variable (Whisper takes 30-120s for a 15-min recording). The client polls for status or waits for a WebSocket push.

**Trade-offs:** Tasks are lost on server restart (acceptable — examiner can re-trigger). Results are persisted to DB so completed jobs survive restarts. django-simple-task is NOT compatible with Daphne (Daphne does not implement the ASGI lifespan protocol that django-simple-task requires), making raw `asyncio.create_task()` the correct choice here.

**Implementation:**

```python
# module-level strong reference set — prevents garbage collection in Python 3.12+
_background_tasks: set = set()

# In the trigger view (async def post)
task = asyncio.create_task(run_ai_feedback(session_id))
_background_tasks.add(task)
task.add_done_callback(_background_tasks.discard)
```

**Confidence:** HIGH — Daphne's lack of lifespan support is a confirmed, open issue in the django-simple-task repo. asyncio.create_task in async Django views under Daphne is the documented workaround.

### Pattern 2: Whisper as Blocking CPU Call Offloaded to Thread Pool

**What:** `whisper.transcribe()` is synchronous and CPU-intensive. Wrap it with `asyncio.to_thread()` (Python 3.9+, available in this stack) to avoid blocking Daphne's event loop during transcription.

**When to use:** Any time a synchronous CPU-bound or IO-bound blocking call must be made from an async coroutine.

**Trade-offs:** Occupies a thread pool slot for the duration of transcription (30-120s). Acceptable for infrequent per-session operations. Not appropriate if many concurrent AI jobs are expected (that would need Celery workers instead).

**Example:**

```python
# session/services/ai.py
import asyncio
import whisper

_whisper_model = None  # module-level singleton

def _get_model():
    global _whisper_model
    if _whisper_model is None:
        _whisper_model = whisper.load_model("base")
    return _whisper_model

async def transcribe_audio(file_path: str) -> str:
    model = _get_model()
    result = await asyncio.to_thread(model.transcribe, file_path)
    return result["text"]
```

**Model size recommendation:** `base` (~150MB) balances speed and accuracy for IELTS audio. Load at module import or first call, not per-request.

### Pattern 3: Status Polling via AIFeedbackJob Model

**What:** The trigger endpoint creates an `AIFeedbackJob` record (status=PENDING), returns 202 with job metadata. The background task updates the job as it progresses. The client polls a status endpoint.

**When to use:** Any long-running background operation where the client needs to know when results are ready without maintaining a persistent WebSocket connection for the duration.

**Suggested model design:**

```python
class AIFeedbackStatus(models.IntegerChoices):
    PENDING = 1, "Pending"
    PROCESSING = 2, "Processing"
    DONE = 3, "Done"
    FAILED = 4, "Failed"

class AIFeedbackJob(TimestampedModel):
    session = models.OneToOneField(
        IELTSMockSession, on_delete=models.CASCADE, related_name="ai_feedback_job"
    )
    status = models.PositiveSmallIntegerField(
        choices=AIFeedbackStatus.choices,
        default=AIFeedbackStatus.PENDING,
        db_index=True
    )
    transcript = models.TextField(blank=True)
    error_message = models.TextField(blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)
```

**Trade-offs:** Simple, no additional infrastructure. Results survive server restarts. Background task also broadcasts a WebSocket event on completion so clients with active connections get a push notification instead of waiting for the next poll cycle.

### Pattern 4: Source Enum on CriterionScore

**What:** Add a `source` IntegerChoices field to the existing `CriterionScore` model. AI-generated scores create rows with `source=CLAUDE`. Examiner scores use `source=EXAMINER` (default, backward-compatible).

**Why this over a separate model:** Avoids duplicating the scoring schema. Preserves the existing `CriterionScoreSerializer` and result API shape. The only change needed is relaxing the `unique_together = [("session_result", "criterion")]` constraint to `[("session_result", "criterion", "source")]` to allow both examiner and Claude scores per criterion.

**Migration impact:** Adding `source` with `default=1` (EXAMINER) is fully backward-compatible — all existing rows get `source=EXAMINER` automatically.

**Guard `compute_overall_band()`:** The method uses `self.scores.values_list("band", flat=True)`. After this change, it must filter by `source=EXAMINER` to avoid mixing AI bands into the examiner calculation unless that is explicitly desired behavior.

### Pattern 5: Monthly Usage Tracking with Atomic Increment

**What:** `AIMonthlyUsage` model with a `(examiner, year, month)` unique constraint. Before triggering, check `count < limit`. Increment atomically with `select_for_update` + `F()` expression.

**Suggested model design:**

```python
class AIMonthlyUsage(models.Model):
    examiner = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    year = models.PositiveSmallIntegerField()
    month = models.PositiveSmallIntegerField()
    count = models.PositiveIntegerField(default=0)

    class Meta:
        unique_together = [("examiner", "year", "month")]
```

**Increment pattern (consistent with existing `select_for_update` use in scheduling/):**

```python
with transaction.atomic():
    usage, _ = AIMonthlyUsage.objects.select_for_update().get_or_create(
        examiner=examiner, year=now.year, month=now.month, defaults={"count": 0}
    )
    if usage.count >= MONTHLY_LIMIT:
        raise ValidationError("Monthly AI feedback limit reached.")
    usage.count = F("count") + 1
    usage.save(update_fields=["count"])
```

## Data Flow

### AI Feedback Trigger Flow

```
Examiner POST /api/sessions/<pk>/ai-feedback/
    |
    +- Guard: Session status == COMPLETED? No -> 400
    +- Guard: SessionRecording exists? No -> 400
    +- Guard: AIFeedbackJob not PROCESSING or DONE? No -> 409
    +- Guard: Monthly usage < limit? No -> 429
    |
    +- Atomic: increment AIMonthlyUsage.count
    +- Create or reset AIFeedbackJob (status=PENDING)
    +- asyncio.create_task(run_ai_feedback(session_id))
    |
    <- HTTP 202 {"job_id": X, "status": "pending"}

Background coroutine: run_ai_feedback(session_id)
    |
    +- await AIFeedbackJob.objects.aupdate(status=PROCESSING)
    +- await asyncio.to_thread(whisper_model.transcribe, audio_path)
    |     (thread pool, 30-120s for 15-min audio)
    +- await AIFeedbackJob.objects.aupdate(transcript=text)
    +- await anthropic_client.messages.create(model=..., messages=[...])
    |     (async HTTP to Anthropic API)
    +- Parse response -> 4x CriterionScore rows (source=CLAUDE)
    +- await AIFeedbackJob.objects.aupdate(status=DONE, completed_at=now)
    +- _broadcast(session_id, "ai_feedback_done", {"job_id": X})
    |
    +- (on any exception): aupdate(status=FAILED, error_message=str(e))
```

### Status Poll Flow

```
GET /api/sessions/<pk>/ai-feedback/status/
    |
    <- {status, completed_at}  (200)
       404 if job never triggered
```

### Results Retrieval Flow

```
GET /api/sessions/<pk>/ai-feedback/
    |
    <- {transcript, scores: [CriterionScore x4 (source=CLAUDE)], completed_at}  (200)
       404 if status != DONE
```

## API Endpoint Structure

| Method | URL | Purpose | Auth |
|--------|-----|---------|------|
| `POST` | `/api/sessions/<pk>/ai-feedback/` | Trigger AI feedback pipeline | Examiner only |
| `GET` | `/api/sessions/<pk>/ai-feedback/status/` | Poll job status | Examiner or Candidate |
| `GET` | `/api/sessions/<pk>/ai-feedback/` | Retrieve transcript + AI scores | Examiner or Candidate |

All three are added to `session/urls.py` and implemented as view classes in `session/views.py`, consistent with all other session views.

## Integration Points

### External Services

| Service | Integration Point | Pattern | Notes |
|---------|-----------------|---------|-------|
| OpenAI Whisper (local) | `session/services/ai.py` | `await asyncio.to_thread(model.transcribe, path)` | Module-level singleton. `base` model recommended for speed vs accuracy balance. Requires `ffmpeg` installed on the server. |
| Anthropic Claude API | `session/services/ai.py` | `await AsyncAnthropic().messages.create(...)` | Use `anthropic` SDK's `AsyncAnthropic` client for non-blocking calls. Add `ANTHROPIC_API_KEY` to `.env`. |

### Internal Boundaries

| Boundary | Communication | Notes |
|----------|---------------|-------|
| Trigger view -> background task | `asyncio.create_task()` | Must keep strong reference in module-level set |
| Background task -> ORM | Django 4.1+ async ORM (`aget`, `aupdate`, `acreate`) | Avoids `sync_to_async` wrappers; cleaner in coroutines |
| Background task -> WebSocket | `_broadcast()` via existing `async_to_sync(channel_layer.group_send)` | Reuse the established pattern unchanged |
| `CriterionScore` (CLAUDE) -> `SessionResult.compute_overall_band()` | Filter by `source=EXAMINER` in the band calculation query | Must guard explicitly after adding source field |
| `AIMonthlyUsage` -> trigger view | Inline in view with `select_for_update` transaction | No service abstraction needed at this scale |

## Scaling Considerations

| Scale | Architecture Adjustments |
|-------|--------------------------|
| 0-50 examiners, <= 10 AI jobs/month each | asyncio.create_task, InMemoryChannelLayer, local Whisper base model — sufficient |
| 200+ examiners, concurrent AI jobs | Move Whisper transcription to Celery workers; `AIFeedbackJob` model already provides the status tracking needed for Celery without API changes |
| High scale | Whisper GPU inference node, Redis channel layer (already planned for production), dedicated transcription worker pool |

The v1.3 approach is deliberately constrained. The `AIFeedbackJob` status model means migrating to Celery later requires only changing task dispatch — not the API contract or data model.

## Anti-Patterns

### Anti-Pattern 1: Using django-simple-task with Daphne

**What people do:** Install `django-simple-task` to avoid Celery and call `defer(my_task)` from views.

**Why it's wrong:** `django-simple-task` requires the ASGI lifespan protocol to start its worker queue. Daphne does not implement the lifespan protocol. Tasks will silently not execute. This is a confirmed, open issue.

**Do this instead:** Use `asyncio.create_task()` from an async view with the module-level strong-reference set pattern.

### Anti-Pattern 2: Running Whisper Synchronously in an Async View

**What people do:** Call `model.transcribe(file_path)` directly inside `async def post(...)`.

**Why it's wrong:** Whisper is CPU-bound and synchronous. Calling it directly blocks Daphne's event loop, freezing all WebSocket connections and HTTP requests for 30-120s.

**Do this instead:** `await asyncio.to_thread(model.transcribe, file_path)`.

### Anti-Pattern 3: Storing AI Scores in a Parallel Model

**What people do:** Create a separate `AICriterionScore` model to avoid touching `CriterionScore`.

**Why it's wrong:** Duplicates the scoring schema, creates divergent serializers, and makes the result API return a different shape for AI scores vs examiner scores. The frontend must handle two schemas.

**Do this instead:** Add `source` IntegerChoices field to `CriterionScore`, relax the unique constraint to include `source`. Existing serializer and API shape are preserved.

### Anti-Pattern 4: Placing Monthly Usage in session/ Instead of main/

**What people do:** Add `AIMonthlyUsage` to `session/models.py` because AI feedback is triggered from a session view.

**Why it's wrong:** Monthly usage is a User-scoped concern. All User-tracking models live in `main/`. Placing it in `session/` breaks this pattern and creates a circular import risk (session already imports from main for `User`, `ExaminerProfile`).

**Do this instead:** Add `AIMonthlyUsage` to `main/models.py`.

### Anti-Pattern 5: Loading Whisper Model Per Request

**What people do:** Call `whisper.load_model("base")` inside the transcription function on each AI job.

**Why it's wrong:** Loading Whisper takes several seconds and allocates ~150-500MB of memory. Each job would reload the model, causing latency spikes and potential OOM under any concurrent load.

**Do this instead:** Use a module-level singleton in `session/services/ai.py`. Load once on first call, cache globally.

## Build Order (Recommended)

Dependencies are essentially linear:

1. **Data models + migrations** — `AIFeedbackJob`, `AIFeedbackStatus`, `ScoreSource`, `CriterionScore.source` field, `AIMonthlyUsage`. Nothing else can be built without these. Two migrations: one for `session/`, one for `main/`.

2. **Service layer** — `session/services/ai.py`: Whisper transcription function + Claude API call function. Testable in isolation before wiring to views.

3. **Trigger endpoint** — `POST /api/sessions/<pk>/ai-feedback/` with usage check, job creation, and `asyncio.create_task()` dispatch.

4. **Status + results endpoints** — `GET .../status/` and `GET .../` are read-only; depend only on the models from step 1.

5. **WebSocket broadcast** — Add `_broadcast("ai_feedback_done", ...)` call at end of background task. This is the lowest-risk change and can be added last.

## Sources

- Django Channels workers documentation: https://channels.readthedocs.io/en/stable/topics/worker.html
- django-simple-task Daphne incompatibility (confirmed open issue): https://github.com/ericls/django-simple-task/issues/2
- asyncio.create_task fire-and-forget with strong reference: https://mkennedy.codes/posts/fire-and-forget-or-never-with-python-s-asyncio/
- asyncio.to_thread for blocking calls (Python 3.9+): https://docs.python.org/3/library/asyncio-task.html
- Whisper async with run_in_executor pattern: https://github.com/openai/whisper/discussions/1310
- Django async ORM (4.1+): https://docs.djangoproject.com/en/5.0/topics/async/
- Anthropic Python SDK (AsyncAnthropic): https://github.com/anthropics/anthropic-sdk-python
- Background tasks in Django without Celery (2025): https://medium.com/@joyichiro/django-background-tasks-without-celery-lightweight-alternatives-for-2025-22c5940e6928

---
*Architecture research for: MockIT v1.3 AI Feedback integration*
*Researched: 2026-04-07*
