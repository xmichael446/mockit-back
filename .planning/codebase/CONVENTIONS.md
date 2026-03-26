# Coding Conventions

**Analysis Date:** 2026-03-27

## Naming Patterns

**Files:**
- Django app structure: `models.py`, `views.py`, `serializers.py`, `consumers.py`, `urls.py`, `routing.py`, `admin.py`, `services/`, `migrations/`
- Service modules: `session/services/hms.py` (feature-focused service files with multiple related functions)
- Test files: `tests.py` (single test file per Django app, not dispersed)

**Functions:**
- Private/internal functions use leading underscore: `_generate_invite_token()`, `_is_examiner()`, `_is_candidate()`, `_session_qs()`, `_broadcast()`, `_authenticate()`, `_is_participant()`
- Public async methods in consumers use `async def`: `async def connect()`, `async def receive()`, `async def session_event()`
- Helper methods in consumers use leading underscore: `async def _authenticate()`, `async def _get_user_from_token()`, `@database_sync_to_async def _is_participant()`
- Getter methods on models use `@property` decorator: `is_expired`, `duration`, `prep_duration`, `speaking_duration`, `total_duration`
- Validation methods in serializers use `validate_<field>()` pattern: `validate_part_1()`, `validate_part_2()`, `validate_part_3()`, `validate_token()`, `validate_invite_token()`
- Internal validation helpers use leading underscore: `_validate_part(topics, expected_part, label)`

**Variables:**
- snake_case for all variables: `invite_token`, `session_id`, `room_id`, `hms_token`, `request_user`, `status_filter`
- Model field names use snake_case: `created_at`, `updated_at`, `started_at`, `ended_at`, `invite_token`, `video_room_id`, `overall_feedback`
- Query variables use descriptive names: `qs` for QuerySet, `obj` for single model instance
- Error messages stored in variables for reuse

**Types:**
- IntegerChoices for model choices: `SessionStatus`, `SpeakingCriterion`, `IELTSSpeakingPart`, `User.Role`, `Question.Difficulty`
- Choices defined as nested classes within models or at module level
- Related field names follow pattern: `related_name="model_plural"` (e.g., `related_name="sessions"`, `related_name="parts"`, `related_name="scores"`)

## Code Style

**Formatting:**
- No linter/formatter explicitly configured in codebase
- 4-space indentation (Python standard)
- Line length varies (some lines exceed 100 characters)
- Imports organized manually (no automatic formatting)

**Linting:**
- No `.pylintrc`, `pyproject.toml`, or linting config detected
- No Black, Flake8, or similar formatters in dependencies
- Django-extensions included (`django-extensions==4.1`)

## Import Organization

**Order:**
1. Python standard library (`import uuid`, `import time`, `import json`, `from datetime import timedelta`)
2. Third-party Django/DRF imports (`from django.conf import settings`, `from rest_framework.response import Response`)
3. Django Channels imports (`from channels.db import database_sync_to_async`, `from channels.generic.websocket import AsyncWebsocketConsumer`)
4. Internal app imports (`from main.models import User`, `from .models import IELTSMockSession`)

**Path Aliases:**
- Relative imports used for same-app references: `from .models import`, `from .serializers import`
- Absolute imports for cross-app references: `from main.models import User`, `from questions.models import Question`
- No explicit path aliases configured

## Error Handling

**Patterns:**
- Try-catch for external API calls: `try: ... except Exception:` with descriptive error messages
- Model.DoesNotExist exceptions caught explicitly: `except IELTSMockSession.DoesNotExist:`
- DRF serializer validation via `raise_exception=True` on serializer validation
- HTTP error responses returned directly: `Response({"detail": "..."}, status=403)`
- Exception details logged to response: `raise Exception(f"100ms API error {response.status_code}: {detail}")`

**Examples from codebase:**
```python
# External API error handling
if not response.ok:
    try:
        detail = response.json()
    except Exception:
        detail = response.text
    raise Exception(f"100ms API error {response.status_code}: {detail}")

# Model lookup with explicit exception
try:
    session = _session_qs().get(pk=pk)
except IELTSMockSession.DoesNotExist:
    return Response({"detail": "Not found."}, status=404)

# Serializer validation
serializer = SessionCreateSerializer(data=request.data)
serializer.is_valid(raise_exception=True)
```

## Logging

**Framework:** Console only (no explicit logging configuration detected)

**Patterns:**
- Observability achieved via HTTP response status codes and error messages
- No `logging` module imports found in codebase
- Error messages in Response objects serve as event logging

## Comments

**When to Comment:**
- Docstrings on APIView classes explain HTTP methods and broadcast events:
  ```python
  class StartSessionView(APIView):
      """
      POST /api/sessions/<id>/start/
      Examiner starts the session. Creates the 100ms video room.
      Broadcasts: session.started
      """
  ```
- Inline comments for non-obvious logic (rare in codebase)
- Comment section headers with special formatting: `# ─── Section Name ─────────────────────`

**JSDoc/TSDoc:**
- Not applicable (Python project, no TypeScript)
- Docstrings on functions document purpose and parameters when needed

## Function Design

**Size:**
- Views typically 15-30 lines per method
- Helper functions 5-15 lines
- Models include @property methods for computed fields (typically 3-8 lines)

**Parameters:**
- Views accept `self, request, pk=None` or similar
- Helper functions minimize parameters: `_is_examiner(user)`, `_broadcast(session_id, event_type, data)`
- Serializer methods use Django convention: `validate_<field>(self, value)`

**Return Values:**
- REST views return `Response(data, status=code)` consistently
- Model @property methods return computed values or None
- Helper functions return data or raise exceptions
- Async methods in consumers use `await` pattern

## Module Design

**Exports:**
- No `__all__` declarations found
- All classes and functions at module level are implicitly public
- Private functions marked with leading underscore

**Barrel Files:**
- No barrel files (index.py with re-exports) used
- Each module imports directly from its source: `from session.models import`, `from session.views import`
- Service modules group related utilities: `session/services/hms.py` contains `generate_management_token()`, `create_room()`, `generate_app_token()`

## Async Pattern

**WebSocket Consumers:**
- Use `AsyncWebsocketConsumer` from channels (lowercase 's')
- Mix async and sync methods: `async def` for channel operations, `@database_sync_to_async def` for database queries
- Event handlers prefixed with handler name: REST views send `{"type": "session_event", "data": {...}}` routed to `async def session_event(self, event)`

```python
async def connect(self):
    # async setup
    user = await self._authenticate()
    await self.channel_layer.group_add(self.group_name, self.channel_name)
    await self.accept()

@database_sync_to_async
def _get_user_from_token(self, token_key):
    # sync database query wrapped
    token = Token.objects.get(key=token_key)
    return token.user
```

---

*Convention analysis: 2026-03-27*
