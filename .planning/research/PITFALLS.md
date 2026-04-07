# Pitfalls Research

**Domain:** Adding AI transcription, LLM-based assessment, and async processing to an existing Django IELTS exam platform
**Researched:** 2026-04-07
**Confidence:** HIGH (claims cross-verified against Django 5.2 docs, Whisper GitHub, Anthropic API docs, and production post-mortems)

---

## Critical Pitfalls

### Pitfall 1: Whisper Model Loaded Per-Request, Blocking the Event Loop

**What goes wrong:**
`whisper.load_model("base")` is called inside the async background task (or view) on every transcription request. On CPU, loading the model alone takes 3–8 seconds and uses 1–4 GB RAM. When running under Daphne (ASGI), this synchronous CPU-bound call blocks the entire event loop, freezing all WebSocket connections and HTTP responses for all users while the model loads and runs inference.

**Why it happens:**
Developers treat Whisper like a lightweight API call. The model load is trivially written inline, and it works fine in a local test with one request. Under production load or even a second concurrent user, the blocking becomes catastrophic.

**How to avoid:**
Load the Whisper model once at process startup as a module-level singleton, not per-request. Wrap the inference call in `asyncio.get_event_loop().run_in_executor(None, ...)` or `sync_to_async` so it runs in a thread pool, not the event loop:

```python
# session/services/transcription.py — loaded once at import time
import whisper
_model = whisper.load_model("base")  # Loaded once per worker process

async def transcribe_async(audio_path: str) -> str:
    loop = asyncio.get_event_loop()
    result = await loop.run_in_executor(None, _model.transcribe, audio_path)
    return result["text"]
```

The GIL means CPU-bound work in a thread pool still serialises threads, but at least it does not block the event loop. For production, use `faster-whisper` with CTranslate2 int8 quantisation: 4x faster on CPU, 50–60% less RAM.

**Warning signs:**
- WebSocket heartbeats drop during a transcription
- `daphne` access log shows a request taking 30–120+ seconds
- Server OOM-kills after a few concurrent transcriptions
- Django Channels group messages delayed

**Phase to address:**
Transcription service implementation phase — before any endpoint wires it up.

---

### Pitfall 2: Fire-and-Forget asyncio Tasks Get Garbage-Collected Before Completion

**What goes wrong:**
A background transcription+assessment job is spawned with `asyncio.create_task(run_ai_feedback(...))` inside an async view or consumer handler. The task appears to start, but on Python 3.12+ it is silently garbage-collected mid-execution because the event loop only holds a weak reference to tasks not stored elsewhere. The job disappears with no error, no status update, and no log entry.

**Why it happens:**
`asyncio.create_task()` is documented to require the caller to retain a strong reference. Most developers miss this. The Python 3.12 garbage collector is more aggressive. In async Django views specifically, the framework closes the event loop after returning the HTTP response, killing any unfinished tasks spawned in that view.

**How to avoid:**
Keep a module-level set of running tasks. Add each task to it on creation; remove it via a done callback:

```python
# session/services/background.py
_running_tasks: set = set()

def spawn_background_task(coro):
    task = asyncio.create_task(coro)
    _running_tasks.add(task)
    task.add_done_callback(_running_tasks.discard)
    return task
```

Never spawn background jobs from a sync view — use an async view or the Channels consumer. Alternatively, use `database_sync_to_async` inside the consumer's `receive()` to kick off work from a safe async context.

**Warning signs:**
- `AIFeedbackJob` records stuck in `PENDING` status indefinitely
- No exception logs despite a failed job
- asyncio logs showing "Task was destroyed but it is pending!" in DEBUG mode
- Jobs complete in development (lower GC pressure) but not in production

**Phase to address:**
Background task infrastructure phase — establish the `spawn_background_task` pattern before writing any job logic.

---

### Pitfall 3: ORM Calls Inside an Async Context Without sync_to_async

**What goes wrong:**
A background coroutine updates job status or writes AI scores directly with `AIFeedbackJob.objects.filter(...).update(...)`. Django raises `SynchronousOnlyOperation: You cannot call this from an async context`. This crashes the background task silently (exceptions in unawaited tasks are not propagated) and leaves the job in a stale state with no error recorded anywhere visible.

**Why it happens:**
Django's ORM is sync-only by default. Running inside `async def` (even via `asyncio.create_task`) constitutes an async context. The `SynchronousOnlyOperation` check is strict, and the error is easy to miss because the task was fire-and-forget.

**How to avoid:**
All ORM operations inside async functions must use the async ORM interface or be wrapped:

```python
# Option A — async ORM methods (Django 4.1+, preferred for simple queries)
job = await AIFeedbackJob.objects.aget(pk=job_id)
job.status = "PROCESSING"
await job.asave(update_fields=["status", "updated_at"])

# Option B — sync_to_async for complex QuerySets or model methods
from asgiref.sync import sync_to_async

@sync_to_async
def _save_scores(session_result_id, scores):
    # Full sync ORM code here
    ...
```

Establish this discipline from the first line of background task code — it is harder to retrofit later.

**Warning signs:**
- `SynchronousOnlyOperation` in server logs (look carefully — unawaited tasks log to stderr, not request logs)
- Jobs stuck in PENDING after a trigger request returns 202
- Missing score rows in the database despite no explicit failure

**Phase to address:**
Background task infrastructure phase — alongside the fire-and-forget pattern (Pitfall 2).

---

### Pitfall 4: Monthly Usage Limit Has a Race Condition

**What goes wrong:**
Two concurrent trigger requests arrive for the same examiner at the same millisecond. Both read the current month's job count, both see `count < limit`, both pass the guard, and both create a new `AIFeedbackJob`. The examiner ends up with 11 jobs in a month where the limit is 10.

**Why it happens:**
A naive check-then-act pattern without a database-level lock:

```python
# WRONG — race condition
count = AIFeedbackJob.objects.filter(examiner=examiner, month=...).count()
if count >= LIMIT:
    raise PermissionDenied(...)
AIFeedbackJob.objects.create(...)
```

Two threads can both pass the `count >= LIMIT` check before either creates the record.

**How to avoid:**
Use `select_for_update()` on a per-examiner lock row, or use a database `unique_together` constraint combined with an atomic counter. The simplest approach for this scale:

```python
from django.db import transaction

with transaction.atomic():
    # Lock the examiner's usage record for this month
    usage = ExaminerUsage.objects.select_for_update().get_or_create(
        examiner=examiner, month=current_month
    )[0]
    if usage.ai_jobs_count >= settings.AI_JOBS_MONTHLY_LIMIT:
        raise PermissionDenied("Monthly AI feedback limit reached.")
    usage.ai_jobs_count = models.F("ai_jobs_count") + 1
    usage.save(update_fields=["ai_jobs_count"])
    AIFeedbackJob.objects.create(session=session, examiner=examiner)
```

`F()` expressions perform atomic increment at the database level, eliminating read-modify-write races.

**Warning signs:**
- Monthly job counts exceed the configured limit under concurrent load
- Examiners report seeing more feedback jobs than their tier allows
- `select_for_update()` absent from the trigger view

**Phase to address:**
Usage limit + trigger endpoint phase.

---

### Pitfall 5: AI Scores Overwrite or Conflict with Human Examiner Scores

**What goes wrong:**
`CriterionScore` has a `unique_together = [("session_result", "criterion")]` constraint. When AI feedback tries to create a score for `FC` on a session that the examiner already scored, the database raises `IntegrityError`. Alternatively, if the AI score creation path uses `update_or_create`, it silently overwrites the human examiner's band score — destroying authoritative data.

**Why it happens:**
The source (examiner vs. AI) is not part of the uniqueness constraint in the existing model. Adding a `source` enum without updating the unique constraint still leaves one score slot per criterion, not two. The AI path then collides with the human path.

**How to avoid:**
Add `source` to the `unique_together` constraint so both scores can coexist:

```python
class CriterionScore(TimestampedModel):
    class Source(models.IntegerChoices):
        EXAMINER = 1, "Examiner"
        AI = 2, "AI (Claude)"

    session_result = models.ForeignKey(SessionResult, ...)
    criterion = models.PositiveSmallIntegerField(choices=SpeakingCriterion.choices)
    source = models.PositiveSmallIntegerField(choices=Source.choices, default=Source.EXAMINER)
    band = models.PositiveSmallIntegerField(...)
    feedback = models.TextField(null=True, blank=True)

    class Meta:
        unique_together = [("session_result", "criterion", "source")]
```

The `compute_overall_band()` method on `SessionResult` must also be updated to filter by `source=EXAMINER` — otherwise AI bands contaminate the official IELTS score calculation.

**Warning signs:**
- `IntegrityError: UNIQUE constraint failed` in logs after adding source field
- `SessionResult.overall_band` changes after AI feedback runs
- API responses mixing examiner and AI scores without a `source` field

**Phase to address:**
Model migration phase — before any AI score writes are attempted.

---

### Pitfall 6: Claude API Latency Causes Downstream Timeout or Stale Status

**What goes wrong:**
The full pipeline (transcription + Claude API call) can take 60–180 seconds for a 15-minute audio file. If the status polling endpoint returns `PROCESSING` for that entire window, frustrated users may retry the trigger endpoint, creating duplicate jobs. If a proxy or load balancer imposes a 30-second timeout, the background task is orphaned mid-flight while the job record shows PROCESSING forever.

**Why it happens:**
Developers test locally with small audio clips and fast hardware. The assumption that "it will complete quickly" breaks in production with real IELTS recordings (12–17 minutes average speaking time). The background task is genuinely async but callers have no signal other than polling.

**How to avoid:**
- Set a maximum runtime on the background task itself (use `asyncio.wait_for` with a generous 300-second timeout).
- The trigger endpoint must return `202 Accepted` immediately — never wait for the job inside the request.
- Add a `failed_reason` field to `AIFeedbackJob` and catch all exceptions at the top of the task:

```python
async def run_ai_feedback(job_id: int):
    try:
        # ... pipeline ...
    except asyncio.TimeoutError:
        await _mark_failed(job_id, "Timed out after 300s")
    except Exception as e:
        await _mark_failed(job_id, str(e))
```

- For polling: document a reasonable retry interval (10 seconds) and a maximum poll count in the API contract to prevent client stampedes.

**Warning signs:**
- Jobs in PROCESSING status for more than 5 minutes
- Duplicate `AIFeedbackJob` records for the same session
- Unhandled exception logs mid-background-task

**Phase to address:**
Trigger endpoint + status polling phase.

---

## Technical Debt Patterns

Shortcuts that seem reasonable but create long-term problems.

| Shortcut | Immediate Benefit | Long-term Cost | When Acceptable |
|----------|-------------------|----------------|-----------------|
| Load Whisper model per-request | No singleton management | Server OOM, blocked event loop on every job | Never — load once at startup |
| Store AI and human scores in separate `AIScore` model (parallel table) | No migration to existing model | Two code paths for scoring display, complex `compute_overall_band`, duplicate serialisers | Never — use `source` enum on the existing `CriterionScore` |
| Hardcode monthly limit in view code | Fast to ship | Config change requires deployment, no per-examiner overrides possible | MVP only — move to settings constant immediately |
| Skip job status tracking, just await in-request | Simpler implementation | Request timeouts, no progress visibility, duplicate triggers | Never with 60–180s workloads |
| Use `whisper-large` on CPU | Higher accuracy | 8–16 GB RAM, 10+ minutes per session on CPU | Never without GPU — use `whisper-base` or `faster-whisper` |
| Use `asyncio.create_task` without strong reference set | Simple fire-and-forget | Silent task loss on Python 3.12+ | Never — always retain a reference |
| Write raw audio file path into Claude prompt | Avoids extra read step | Model cannot read files; the transcript must be extracted first | Never — always pass text, not paths |

---

## Integration Gotchas

Common mistakes when connecting to external services or libraries.

| Integration | Common Mistake | Correct Approach |
|-------------|----------------|------------------|
| Whisper | Calling `model.transcribe(path)` from within `async def` directly | Wrap in `run_in_executor` or `sync_to_async` — it is CPU-bound and synchronous |
| Whisper | Using `openai-whisper` package in production | Use `faster-whisper` (CTranslate2 backend): 4x faster, 50% less memory, same accuracy |
| Claude API | Not setting a timeout on the `httpx` client | A hung Claude API call will block the background task indefinitely — set `timeout=60.0` |
| Claude API | Requesting free-form text, then trying to parse band scores with regex | Use Claude's structured outputs (JSON schema mode) — guarantees parseable response every time |
| Claude API | Sending the full raw transcript in a system-prompt only | Put the transcript in the user turn, instructions in the system turn — Claude responds better to this split |
| Claude API | Trusting band scores without range validation | Claude can hallucinate values outside 1–9; always clamp/validate before writing to DB |
| InMemoryChannelLayer | Broadcasting job-complete events from a background thread | `async_to_sync(channel_layer.group_send)` works from sync; native `await` works only inside async context — use the correct adapter |
| Django ORM | Calling `.save()` or `.filter()` directly inside `async def` | Use `asave()`, `afilter()`, `aget()` (Django 4.1+ async ORM) or `sync_to_async` wrappers |
| Audio file storage | Saving to `MEDIA_ROOT` on local disk in production | Files are not persistent across deployments on most PaaS — use S3/object storage or ensure volume is mounted |

---

## Performance Traps

Patterns that work at small scale but fail as usage grows.

| Trap | Symptoms | Prevention | When It Breaks |
|------|----------|------------|----------------|
| Whisper inference blocks Daphne worker thread | All WebSocket clients freeze during transcription | Use `run_in_executor` with a bounded thread pool | Immediately with the first concurrent user |
| Unbounded background task queue | Memory grows unbounded if triggers arrive faster than jobs complete | Cap concurrent jobs per examiner (reject trigger if one already PROCESSING) | At 5+ concurrent examiners triggering simultaneously |
| Polling endpoint hits DB on every request | High DB load from impatient clients polling every 1s | Cache job status in Django cache (5s TTL) keyed by job ID | At 50+ concurrent pollers |
| Module-level Whisper model in multi-worker Daphne | N workers each hold one model in RAM | Document and enforce single-worker Daphne for AI processing, or isolate Whisper in a sidecar | With 2+ Daphne workers |
| Storing large audio files in `MEDIA_ROOT` without cleanup | Disk fills up | Add a retention policy: delete audio file after successful transcription (or after X days) | After a few hundred sessions |

---

## Security Mistakes

Domain-specific security issues beyond general web security.

| Mistake | Risk | Prevention |
|---------|------|------------|
| Trigger endpoint accessible to candidates | Candidate triggers AI feedback on their own session, bypassing examiner intent | Permission check: only the session's examiner can trigger AI feedback |
| Monthly limit checked in application code only | Malicious client bypasses limit with concurrent requests | Database-level lock via `select_for_update()` (Pitfall 4) |
| AI band scores exposed in result API without `source` field | Client cannot distinguish AI from human scores; could mislead candidate | Always include `source` in serialiser — never omit it |
| Audio file URL guessable from session ID | Candidate downloads raw audio of their own session before examiner consents to share | Use `uuid` in the upload path, not session ID; restrict `MEDIA_ROOT` behind auth |
| Claude API key in environment but logged on error | Key appears in Sentry/log aggregator on API failure | Scrub/mask `ANTHROPIC_API_KEY` in exception reporting config |

---

## UX Pitfalls

Common user experience mistakes in this domain.

| Pitfall | User Impact | Better Approach |
|---------|-------------|-----------------|
| Trigger returns 200 with immediate score (blocking) | Examiner waits 2–3 minutes for the response, assumes it crashed | Always 202 Accepted + job ID; examiner polls for completion |
| No distinction between AI and examiner scores in results UI | Candidates treat AI band of 6.5 as official IELTS result | `source` field on every score; API contract documents that AI score is indicative only |
| Status polling requires the examiner to refresh manually | Examiner has no idea when AI feedback is done | Push a WebSocket event (`ai_feedback_ready`) via Channels when the job completes — Channels consumer already has the broadcast pattern |
| AI feedback shown before examiner releases results | Candidate sees AI score before examiner decides to release | AI feedback visibility should follow the same `is_released` gate as examiner scores |
| Error state on job failure is opaque | Examiner sees "Failed" with no actionable message | Persist `failed_reason` on `AIFeedbackJob` and expose it in the status endpoint |

---

## "Looks Done But Isn't" Checklist

Things that appear complete but are missing critical pieces.

- [ ] **Whisper integration:** Model loads on import — verify with `import session.services.transcription` in a Django shell that it does NOT block, and that a second call reuses the singleton.
- [ ] **Background task:** Verify jobs survive a server restart (they will not — they are in-memory). Document this limitation and provide a recovery path (re-trigger endpoint).
- [ ] **Source enum migration:** Verify `compute_overall_band()` filters by `source=EXAMINER` — add a regression test before merging the migration.
- [ ] **Monthly limit:** Verify the limit is enforced when two requests arrive within 10ms — write a concurrent test with `asyncio.gather`.
- [ ] **Claude response validation:** Verify band scores outside 1–9 are rejected, not saved — test by mocking Claude to return `{"FC": 15}`.
- [ ] **Job cleanup:** Verify audio files are not accumulating indefinitely on the server — check `MEDIA_ROOT/recordings/` after 10 test sessions.
- [ ] **Status endpoint auth:** Verify a candidate cannot query the job status of another examiner's session — write a permission test.
- [ ] **WebSocket event:** Verify `ai_feedback_ready` is broadcast to the correct channel group — not all sessions, only the session the job belongs to.

---

## Recovery Strategies

When pitfalls occur despite prevention, how to recover.

| Pitfall | Recovery Cost | Recovery Steps |
|---------|---------------|----------------|
| Whisper OOM crash (wrong model size) | LOW | Switch to `faster-whisper` with `tiny` or `base.en` model; redeploy; re-trigger failed jobs |
| Jobs stuck in PROCESSING (orphaned task) | LOW | Add admin action to reset `AIFeedbackJob.status` to `FAILED`; expose re-trigger endpoint |
| AI scores overwrote examiner scores (missing source constraint) | HIGH | Write a data migration to back-fill `source=EXAMINER` on all existing `CriterionScore` rows; add constraint; recompute affected `overall_band` values |
| Monthly limit bypassed (race condition) | MEDIUM | Audit log shows over-limit jobs; admin soft-delete extra jobs; apply `select_for_update` fix; add test |
| Background tasks lost on worker restart | LOW | Document that jobs are fire-and-forget (no persistence across restarts); add a "re-run AI feedback" button to the examiner UI |
| Claude API down (extended outage) | LOW | Jobs fail with `failed_reason`; examiner can re-trigger when service restores; no data loss |

---

## Pitfall-to-Phase Mapping

How roadmap phases should address these pitfalls.

| Pitfall | Prevention Phase | Verification |
|---------|------------------|--------------|
| Whisper blocks event loop | Transcription service phase | Concurrent Daphne test: 2 simultaneous WebSocket pings don't freeze during transcription |
| Fire-and-forget task GC'd | Background task infrastructure phase | Python 3.12 test: verify task completes after 30s with strong reference set |
| ORM in async context | Background task infrastructure phase | Run linter or test that imports all task functions and asserts no direct `.save()` calls |
| Monthly limit race condition | Trigger endpoint + usage limit phase | Concurrent test: 11 simultaneous trigger requests result in exactly 10 jobs |
| AI scores overwrite human scores | Model migration phase | Assertion: `compute_overall_band()` returns same value before and after AI job runs |
| Claude API latency / timeout | Trigger + status polling phase | Integration test with mocked 120s Claude response; verify job reaches PROCESSING then COMPLETED |

---

## Sources

- Django async documentation (5.2): https://docs.djangoproject.com/en/5.2/topics/async/
- Django Forum — correct way to create async tasks: https://forum.djangoproject.com/t/what-is-the-correct-way-to-create-an-async-task/9627
- asyncio fire-and-forget pitfalls (Michael Kennedy): https://mkennedy.codes/posts/fire-and-forget-or-never-with-python-s-asyncio/
- Python issue tracker — create_task GC behavior: https://github.com/python/cpython/issues/104091
- Django Channels worker/background tasks docs: https://channels.readthedocs.io/en/stable/topics/worker.html
- Whisper memory leak discussion: https://github.com/openai/whisper/discussions/605
- Whisper memory requirements: https://github.com/openai/whisper/discussions/5
- faster-whisper (CTranslate2): https://github.com/AIXerum/faster-whisper
- Whisper microservice / OOM post-mortem: https://medium.com/@patelhet04/the-0-scalability-fix-how-whisper-microservice-saved-us-from-gpu-oom-65dfd41a2180
- DRF throttling race condition caveat: https://www.django-rest-framework.org/api-guide/throttling/
- Anthropic structured outputs docs: https://platform.claude.com/docs/en/build-with-claude/structured-outputs
- Anthropic latency reduction guide: https://platform.claude.com/docs/en/test-and-evaluate/strengthen-guardrails/reduce-latency
- Kraken engineering blog — async Django lessons (Jan 2026): https://engineering.kraken.tech/news/2026/01/12/using-django-async.html
- Loopwerk — async Django in practice (2025): https://www.loopwerk.io/articles/2025/async-django-why/

---
*Pitfalls research for: v1.3 AI Feedback & Assessment — MockIT*
*Researched: 2026-04-07*
