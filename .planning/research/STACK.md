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
