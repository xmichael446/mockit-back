# Stack Research

**Domain:** IELTS mock exam platform — v1.2 profiles, availability scheduling, session booking, email notifications
**Researched:** 2026-03-30
**Confidence:** HIGH (all new additions verified against current PyPI/official docs; existing stack confirmed from codebase)

---

## Context: What Already Exists (Do Not Re-add)

The following are already in `requirements.txt` and must not be added again:

| Already Present | Version | Role |
|-----------------|---------|------|
| Django | 5.2.11 | Framework |
| djangorestframework | 3.16.1 | REST API |
| channels + daphne | 4.3.2 / 4.2.1 | WebSocket |
| psycopg2-binary | 2.9.11 | PostgreSQL |
| resend | 2.10.0 | Transactional email (direct SDK) |
| PyJWT | 2.11.0 | JWT for 100ms tokens |
| requests | 2.32.5 | HTTP client |
| python-dotenv | 1.1.0 | Env vars |
| django-cors-headers | 4.9.0 | CORS |

---

## New Stack Additions for v1.2

### Required New Library

| Library | Version | Purpose | Why |
|---------|---------|---------|-----|
| Pillow | 12.1.1 | Profile photo uploads via `ImageField` | Django's `ImageField` hard-requires Pillow; no alternative. Used for examiner/candidate profile photos. Resize on save to cap storage cost. |

That is the only pip dependency needed. Everything else is handled by existing stack or Django builtins.

### No New Library Needed For

| Capability | Why No New Dep |
|------------|---------------|
| Availability scheduling (weekly 1-hour slots) | Model it as `AvailabilitySlot(day_of_week, hour)` rows in PostgreSQL. Native Django ORM queries cover conflict detection and slot listing. No scheduling library needed — they add complexity for a simple weekly grid. |
| Session booking/request flow | State machine pattern already proven in `IELTSMockSession`. Add `SessionRequest` model with `PENDING/ACCEPTED/REJECTED` status. Same `IntegerChoices` + guard methods pattern already in codebase. |
| Email notifications | `resend` SDK v2.10.0 already installed and wired in `main/services/email.py`. Add new functions to that service module. Do NOT add django-anymail — it adds a dependency to replace existing working code. |
| Profile models | OneToOneField extension of existing `User` model. Standard Django pattern, no library. |
| Timezone handling for scheduling | `django.utils.timezone` already imported in `session/models.py`. |
| Phone number storage | `CharField` with basic validation is sufficient for an MVP. `django-phonenumber-field` adds complexity with libphonenumber C binding — skip it. |

---

## Recommended Stack (New Only)

### Supporting Libraries

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Pillow | >=12.1.1 | Validate + resize profile photo uploads | Required as soon as any model uses `ImageField` |

### Installation

```bash
pip install Pillow==12.1.1
```

Add to `requirements.txt`:
```
Pillow==12.1.1
```

---

## Design Patterns (No New Deps Required)

### Availability Scheduling

Store individual `AvailabilitySlot` rows, not a bitfield. Each row is `(examiner, day_of_week, hour)` where `day_of_week` is 0–6 (Monday–Sunday) and `hour` is 8–21 (08:00–21:00 start, window is `hour` to `hour+1`).

Why rows over bitfield:
- Queryable: `AvailabilitySlot.objects.filter(examiner=x, day_of_week=2, hour=14)` is readable and indexable
- Django admin works natively
- No bit manipulation in application code
- Uniqueness enforced with `unique_together = [("examiner", "day_of_week", "hour")]`

Real-time availability (which slots are still open) = set of `AvailabilitySlot` rows minus any `SessionRequest` rows with `ACCEPTED` status at the same day/hour.

### Session Booking Flow

`SessionRequest` model with `PENDING/ACCEPTED/REJECTED` status using `IntegerChoices`. Guard methods on the model (`can_accept()`, `can_reject()`). Same pattern as `IELTSMockSession.start()` / `.end()`. On accept: create the `IELTSMockSession` immediately. On reject: status becomes `REJECTED`, no session created.

### Email Notification Pattern

Add `send_*` functions to `main/services/email.py` (or a new `session/services/email.py` for booking-specific emails). Each function calls `resend.Emails.send()` directly — same pattern as `send_verification_email()`. Keep it synchronous for now (Resend responds in ~200ms; async queue is out of scope per PROJECT.md constraints).

Trigger points: request created (to examiner), request accepted (to candidate), request rejected (to candidate).

### Profile Models

`ExaminerProfile(user OneToOneField, bio, credentials, verification_badge, phone, avatar ImageField)` in `main/` or a new `profiles/` app.

`CandidateProfile(user OneToOneField, best_band DecimalField, session_count PositiveIntegerField)` — `best_band` and `session_count` auto-updated via `post_save` signal on `SessionResult`.

---

## Alternatives Considered

| Recommended | Alternative | Why Not |
|-------------|-------------|---------|
| Plain `AvailabilitySlot` rows | `django-scheduler` or `django-agenda` | Both are full calendaring apps with recurring events, timezone handling, and occurrence materialization. Overkill for a fixed weekly 1-hour grid. Adds migration complexity to existing project. |
| `resend` SDK direct calls | `django-anymail[resend]` | django-anymail v14 is excellent, but switching requires removing `resend` 2.10.0, updating all call sites, and changing the email module. Zero benefit for the 3 new email triggers being added. Only switch if email provider diversity is needed. |
| `CharField` for phone | `django-phonenumber-field` | Requires `libphonenumber` C extension. Phone number is a display field (not used for SMS), so E.164 validation is over-engineered for MVP. |
| Pillow `ImageField` with resize-on-save | Cloudinary / django-storages | Valid for production S3 uploads but out of scope. Keep file uploads local (as with `SessionRecording`) for now. |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `django-appointment` | Full appointment booking app — assumes it owns the UI and booking logic entirely. Cannot integrate with existing session state machine. | Custom `SessionRequest` model |
| `django-scheduler` | Calendar app with recurring events, timezone occurrences, and iCal export. Zero overlap with a fixed 08:00–22:00 weekly grid. | `AvailabilitySlot` model rows |
| `celery` + `redis` | Async email queue. Resend API latency (~200ms) does not justify the operational overhead. Redis is deferred to a separate milestone per PROJECT.md. | Synchronous `resend.Emails.send()` |
| `django-anymail` | Would replace the already-working `resend` SDK integration without adding value for this milestone. | Existing `resend` 2.10.0 SDK |
| `django-phonenumber-field` | C extension dependency for a display-only field | `CharField(max_length=20, blank=True)` |

---

## Version Compatibility

| Package | Version | Compatible With | Notes |
|---------|---------|-----------------|-------|
| Pillow | 12.1.1 | Python >=3.10, Django 5.x | Latest stable (Feb 2026). Works with Django's `ImageField` and `FileField`. No conflicts with existing deps. |

---

## File/Configuration Changes Required

1. `requirements.txt` — add `Pillow==12.1.1`
2. `MockIT/settings.py` — add `MEDIA_URL` and `MEDIA_ROOT` if not present (check before adding; `SessionRecording` uses `FileField` so `media/` may already be configured)
3. `MockIT/urls.py` — add `static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)` for dev serving of uploaded images

Check settings first:

```python
# settings.py — add if not already present
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
```

The `media/` directory already exists in the project root (confirmed from `ls` output), suggesting MEDIA_ROOT is already configured for `SessionRecording`. Verify before adding duplicate config.

---

## Sources

- [Pillow 12.1.1 on PyPI](https://pypi.org/project/pillow/) — latest stable version confirmed HIGH confidence
- [django-anymail 14.0 on PyPI](https://pypi.org/project/django-anymail/) — Django 5.2 compatibility confirmed, Resend supported HIGH confidence
- [Resend Django integration guide](https://resend.com/docs/send-with-django) — recommends django-anymail, but existing direct SDK approach is equally valid HIGH confidence
- [Anymail 14.0 documentation](https://anymail.dev/en/stable/index.html) — changelog and compatibility confirmed HIGH confidence
- Codebase inspection (`requirements.txt`, `main/services/email.py`, `session/models.py`) — existing patterns confirmed directly HIGH confidence

---

*Stack research for: MockIT v1.2 — Profiles & Scheduling milestone*
*Researched: 2026-03-30*

---
---

# Stack Research — v1.3 AI Feedback & Assessment

**Domain:** AI-powered IELTS feedback additions — transcription, LLM scoring, async processing, usage limiting
**Researched:** 2026-04-07
**Confidence:** HIGH (all library versions verified against PyPI and official docs)

---

## Context

Subsequent-milestone research. The existing stack (Django 5.2, DRF, Channels 4.x,
Daphne, psycopg2, Resend, python-dotenv, Pillow) is validated and NOT re-evaluated.
This section covers only what is NEW for v1.3.

---

## New Stack Additions for v1.3

### Core Technologies

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| faster-whisper | 1.2.1 | Local speech-to-text transcription | 4x faster than openai-whisper at identical accuracy; uses CTranslate2 (C++ inference) instead of PyTorch, so CPU inference is viable on a VPS without a dedicated GPU; lower memory footprint; same model weights as openai-whisper so quality is identical |
| anthropic | 0.89.0 | Claude API client for feedback generation | Official Anthropic SDK; released April 3 2026; supports sync and async; native type safety; `client.messages.create()` is the stable interface for structured prompt/response |
| django-q2 | 1.9.0 | Background task queue with DB broker | Supports PostgreSQL as broker via Django ORM — no Redis required, consistent with the project's deferred Redis migration decision; multiprocessing workers run as a separate process (`qcluster`) so they are immune to the ASGI event loop closure problem that breaks `asyncio.create_task()` under Daphne; Django 4.2–6.0 supported, Django 5.2 explicitly tested |

### Supporting Dependencies

| Library | Version | Purpose | Notes |
|---------|---------|---------|-------|
| torch (CPU build) | latest stable | Runtime dependency of faster-whisper | Install CPU-only build to avoid pulling in ~2 GB CUDA libraries; use the PyTorch CPU wheel index |
| ffmpeg | system package | Audio decoding required by faster-whisper and openai-whisper | Must be installed via `apt install ffmpeg`; NOT a pip package |

### No New Library Needed For

| Capability | Why No New Dep |
|------------|---------------|
| Monthly usage limiting | A plain `AIFeedbackUsage(examiner, year, month, count)` model with `unique_together` enforces the limit at the DB level. Increment inside an `atomic()` block before enqueuing. No rate-limit library needed — this is per-month aggregate, not per-request rate. |
| Task status polling | `django_q.models.Task` records every enqueued task's state. Store the `task_id` on a new `AIFeedbackJob` model; poll via `Task.objects.get(id=task_id)`. No additional library. |
| Source tracking on scores | Add `source = IntegerChoices(EXAMINER=1, CLAUDE=2)` field to existing `CriterionScore` model. No new model or library needed. |

---

## Installation

```bash
# Transcription
pip install faster-whisper==1.2.1

# LLM client
pip install anthropic==0.89.0

# Background task queue
pip install django-q2==1.9.0

# PyTorch CPU-only (dependency of faster-whisper; avoids CUDA download)
pip install torch --index-url https://download.pytorch.org/whl/cpu

# System dependency (run once on server, not in requirements.txt)
apt install -y ffmpeg
```

Add to `requirements.txt`:
```
faster-whisper==1.2.1
anthropic==0.89.0
django-q2==1.9.0
torch  # CPU wheel installed separately; pin version after first install
```

---

## Configuration Patterns

### django-q2 with ORM Broker (settings.py)

```python
INSTALLED_APPS = [
    ...
    'django_q',
]

Q_CLUSTER = {
    'name': 'mockit',
    'workers': 2,        # Keep low — Whisper is CPU-heavy per worker
    'timeout': 300,      # 5-minute ceiling for transcription + LLM call combined
    'retry': 360,        # Retry window longer than timeout to prevent double-execution
    'orm': 'default',    # Use existing PostgreSQL DB as broker — no Redis needed
}
```

Run the worker alongside Daphne (separate terminal or systemd unit):
```bash
python manage.py qcluster
```

### Task enqueueing and status polling

```python
from django_q.tasks import async_task
from django_q.models import Task

# Enqueue — returns task_id (UUID string stored in django_q_task table)
task_id = async_task('session.tasks.generate_ai_feedback', session_id)

# Status check (called by REST polling endpoint)
task = Task.objects.filter(id=task_id).first()
if task is None:
    status = 'queued'          # not yet picked up by worker
elif task.success is None:
    status = 'processing'
elif task.success:
    status = 'done'
else:
    status = 'failed'
```

Store `task_id` on an `AIFeedbackJob` model linked to the session so the polling
endpoint has a stable foreign key to query.

### Whisper model selection

```python
# settings.py
WHISPER_MODEL = os.getenv('WHISPER_MODEL', 'base')
# Use 'small' for better accuracy at acceptable CPU cost (~500 MB model)
# Use 'base' as safe default on constrained VPS (~150 MB model)
# Do NOT hardcode 'large' — requires ~3 GB memory, unusable on CPU
```

```python
# session/tasks.py
from faster_whisper import WhisperModel
from django.conf import settings

def generate_ai_feedback(session_id):
    model = WhisperModel(settings.WHISPER_MODEL, device='cpu', compute_type='int8')
    segments, _ = model.transcribe(audio_path)
    transcript = ' '.join(s.text for s in segments)
    # ... then call Claude API
```

### Claude API call pattern

```python
import anthropic
from django.conf import settings

client = anthropic.Anthropic(api_key=settings.ANTHROPIC_API_KEY)

response = client.messages.create(
    model='claude-sonnet-4-6',    # or settings.CLAUDE_MODEL
    max_tokens=1024,
    messages=[{'role': 'user', 'content': prompt}],
)
feedback_text = response.content[0].text
```

Use the synchronous client inside django-q2 task functions. The task runs in a
subprocess (not the async event loop), so sync calls are correct here.

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| faster-whisper 1.2.1 | openai-whisper 20250625 | Only if GPU is available and PyTorch is already in the environment; openai-whisper is heavier on CPU |
| django-q2 ORM broker | Celery + Redis | When Redis is already in the stack or task volume exceeds hundreds/day; the Redis milestone is planned separately — switch then |
| django-q2 subprocess worker | `asyncio.create_task()` in async view | Fire-and-forget asyncio tasks are silently dropped under Daphne: the event loop closes after the response is sent. django-q2 workers run in a separate OS process and are immune to this |
| django-q2 | django-simple-task | django-simple-task requires ASGI lifespan protocol support; Daphne does not implement it as of 2025 — tasks would never execute |
| django-q2 | Huey | Huey requires Redis or SQLite as broker; adds another dependency; django-q2 reuses the existing PostgreSQL DB with zero new infrastructure |
| Plain model counter for usage | django-ratelimit | django-ratelimit is per-request throttling (in-memory or cache); monthly aggregate AI usage needs a persistent DB counter that survives restarts |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `asyncio.create_task()` inside Django views/consumers | Under Daphne, the event loop closes after the response is returned, silently killing in-flight coroutines. This is a well-documented ASGI gotcha. | django-q2 subprocess worker (`qcluster`) |
| `django-simple-task` | Requires ASGI lifespan protocol; Daphne does not support it as of 2025 | django-q2 |
| openai-whisper with full CUDA PyTorch | Pulls in CUDA libraries (~2 GB+); no benefit on CPU VPS; model download is larger | faster-whisper with `--index-url https://download.pytorch.org/whl/cpu` torch |
| Whisper "large" or "large-v3" model as default | ~3–10 GB RAM required; completely unusable on CPU for real-time use | `base` or `small` model, configurable via `WHISPER_MODEL` env var |
| Calling Claude API synchronously inside the HTTP request cycle | LLM calls take 5–30+ seconds; will hit proxy/Nginx timeouts and block the WSGI/ASGI worker | Enqueue via django-q2; return `task_id` immediately; client polls a status endpoint |
| Storing raw audio bytes in the Claude prompt | Claude API context window is text; audio bytes are meaningless without ASR. Also wildly over token limits. | Whisper transcript → Claude text prompt |

---

## Version Compatibility

| Package | Version | Compatible With | Notes |
|---------|---------|-----------------|-------|
| django-q2 | 1.9.0 | Django 4.2–6.0, Python 3.9–3.14 | Django 5.2 explicitly supported per changelog |
| faster-whisper | 1.2.1 | Python 3.8+, requires ffmpeg system binary | Falls back to CPU int8 silently if no GPU detected |
| anthropic | 0.89.0 | Python 3.9+ | Sync and async clients both supported |
| torch (CPU) | latest stable | Python 3.9–3.12 | Install from `pytorch.org/whl/cpu` to avoid CUDA |

---

## Integration Points with Existing Code

| Existing Component | How v1.3 Uses It |
|-------------------|------------------|
| `SessionRecording.audio_file` (FileField) | Path passed to `faster_whisper.WhisperModel.transcribe()` |
| `CriterionScore` | AI writes to this model; add `source IntegerChoices(EXAMINER=1, CLAUDE=2)` field |
| `SessionResult.overall_feedback` | AI populates this TextField |
| `SessionResult.compute_overall_band()` | Called after AI writes all 4 `CriterionScore` rows |
| `IELTSMockSession` | `session_id` is the task argument; session fetched inside the task function |
| `User` (examiner) | Monthly usage counter keyed on `(examiner_id, year, month)` |

New models required (no existing model modified except `CriterionScore`):
- `AIFeedbackJob(session OneToOneField, task_id CharField, status IntegerChoices, requested_at, completed_at)`
- `AIFeedbackUsage(examiner ForeignKey, year, month, count — unique_together on examiner+year+month)`

---

## Sources

- [anthropic PyPI](https://pypi.org/project/anthropic/) — version 0.89.0, April 3 2026. HIGH confidence.
- [openai-whisper PyPI](https://pypi.org/project/openai-whisper/) — version 20250625. HIGH confidence.
- [faster-whisper PyPI](https://pypi.org/project/faster-whisper/) — version 1.2.1, October 2025. HIGH confidence.
- [SYSTRAN/faster-whisper GitHub](https://github.com/SYSTRAN/faster-whisper) — 4x faster than openai-whisper, same accuracy, CTranslate2 backend. HIGH confidence.
- [django-q2 PyPI](https://pypi.org/project/django-q2/) — version 1.9.0, December 2025; Django 4.2–6.0 support confirmed. HIGH confidence.
- [django-q2 brokers documentation](https://django-q2.readthedocs.io/en/master/brokers.html) — ORM broker `'orm': 'default'` configuration. HIGH confidence.
- [modal.com whisper variants comparison](https://modal.com/blog/choosing-whisper-variants) — faster-whisper vs openai-whisper vs WhisperX analysis. MEDIUM confidence (third-party).
- [django-simple-task GitHub](https://github.com/ericls/django-simple-task) — confirms Daphne does not support ASGI lifespan protocol, ruling out django-simple-task. HIGH confidence.

---

*Stack research for: MockIT v1.3 — AI Feedback & Assessment milestone*
*Researched: 2026-04-07*
