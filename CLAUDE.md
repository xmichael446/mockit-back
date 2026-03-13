# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
# Run dev server (HTTP only)
python manage.py runserver

# Run with WebSocket support (required for session features)
daphne MockIT.asgi:application

# Migrations
python manage.py migrate
python manage.py makemigrations

# Run tests
python manage.py test
python manage.py test session.tests.TestClassName.test_method  # single test

# Create superuser for admin panel
python manage.py createsuperuser
```

## Architecture

MockIT is an IELTS Speaking mock exam platform. Examiners conduct live sessions with candidates over video, asking questions from a question bank in real-time.

**Apps:**
- `main/` — custom `User` model with `role` field (`EXAMINER=1`, `CANDIDATE=2`)
- `questions/` — read-only question bank: `Topic → Question → FollowUpQuestion`, plus `QuestionSet`
- `session/` — full session lifecycle: models, REST views, WebSocket consumer

**Session lifecycle:**
1. Examiner creates a `MockPreset` (topics for each IELTS part)
2. Examiner creates `IELTSMockSession` from preset → shares `invite_token` with candidate
3. Candidate accepts invite → both connect to WebSocket
4. Examiner drives session: start → parts → ask questions → end
5. Examiner submits `CriterionScore` (FC, GRA, LR, PR, bands 1–9) → `SessionResult` auto-computes overall band → released to candidate

**Real-time (Django Channels):**
- WebSocket URL: `ws/session/<session_id>/?token=<auth_token>`
- Consumer: `session/consumers.py` — `SessionConsumer(AsyncWebsocketConsumer)` (lowercase 's')
- All REST views push events via `_broadcast(session_id, event_type, data)` in `session/views.py`, which calls `async_to_sync(channel_layer.group_send)` to group `"session_<session_id>"`
- Consumer's `session_event()` method forwards events as-is to the WebSocket client

**Authentication:**
- HTTP: `Authorization: Token <token>` (DRF TokenAuthentication)
- WebSocket: `?token=<token>` query param, validated in `SessionConsumer._authenticate()`

**Video rooms:**
- 100ms API integration in `session/services/hms.py` — `create_room()` and `generate_app_token()`
- Room created on `session.start`, fresh token generated on `session.join`

**IELTS band scoring:**
- Overall band = average of 4 criteria bands, rounded to nearest 0.5 (0.25 rounds down)
- Formula: `(sum(bands) // 2) / 2` in `SessionResult.compute_overall_band()`

## Key Files

- `docs/api.md` — complete REST + WebSocket API reference (read before touching session logic)
- `MockIT/settings.py` — `daphne` must be first in `INSTALLED_APPS`; channel layer is `InMemoryChannelLayer`
- `MockIT/asgi.py` — `ProtocolTypeRouter` splitting HTTP and WebSocket traffic
- `session/consumers.py` — WebSocket consumer
- `session/views.py` — all REST views + `_broadcast()` helper
