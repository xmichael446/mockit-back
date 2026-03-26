# Architecture

**Analysis Date:** 2026-03-27

## Pattern Overview

**Overall:** Django REST Framework + WebSocket (Django Channels) architecture with three functional domains: authentication/users, question bank management, and live session orchestration.

**Key Characteristics:**
- RESTful HTTP API for session management and admin operations, WebSocket for real-time participant communication
- Event-driven broadcast pattern: REST views trigger database state changes, then broadcast WebSocket events to connected clients
- Role-based access control via custom `User` model with EXAMINER and CANDIDATE roles
- Token authentication for both HTTP (Authorization header) and WebSocket (query parameter)
- Three-tier session state: overall session → parts (Part 1/2/3) → individual questions with timestamps

## Layers

**Presentation (REST + WebSocket):**
- Purpose: HTTP API endpoints and WebSocket consumer for frontend interaction
- Location: `session/views.py`, `session/consumers.py`, `main/views.py`, `questions/views.py`
- Contains: APIView classes, AsyncWebsocketConsumer, request/response handling
- Depends on: Models, serializers, DRF, Channels, external services (100ms, Resend)
- Used by: Frontend (React/TypeScript), external integrations

**Serialization Layer:**
- Purpose: Convert between Python models and JSON, validation, nested relationships
- Location: `session/serializers.py`, `main/serializers.py`, `questions/serializers.py`
- Contains: ModelSerializer subclasses, custom validators, nested serializers
- Depends on: Models
- Used by: Views for request/response handling

**Domain Logic (Models & Services):**
- Purpose: Core business logic, data validation, state transitions, external integrations
- Location: `session/models.py`, `main/models.py`, `questions/models.py`, `session/services/`, `main/services/`
- Contains: Django models with methods/properties, utility functions, API client wrappers
- Depends on: Django ORM, external APIs (100ms, Resend)
- Used by: Views, serializers, other services

**Data Access (ORM):**
- Purpose: Database schema and query optimization
- Location: Model `Meta` classes, querysets, indexes
- Depends on: PostgreSQL
- Used by: All application layers

**Real-time Broadcast:**
- Purpose: Asynchronous event distribution to WebSocket clients
- Location: `_broadcast()` helper in `session/views.py`, `session/consumers.py`
- Contains: Channels group management, event routing
- Depends on: Django Channels, InMemoryChannelLayer (dev) or Redis (production)
- Used by: All session-related views

## Data Flow

**Session Lifecycle (Create → Start → Conduct → Score → Release):**

1. **Create Session**
   - Examiner POST to `/api/sessions/` with preset_id
   - `SessionCreateSerializer` validates preset and role
   - `SessionListCreateView.post()` creates `IELTSMockSession`, returns invite_token
   - Returns: `{id, invite_token, status="scheduled"}`

2. **Candidate Accepts Invite**
   - Option A (registered candidate): POST `/api/sessions/accept-invite/` with invite_token
   - Option B (guest): POST `/api/auth/guest-join/` with invite_token and first_name
   - Updates `session.candidate` and `invite_accepted_at`
   - **Broadcasts** `invite.accepted` event to WebSocket group `"session_{session_id}"`

3. **Start Session (Examiner)**
   - Examiner POST to `/api/sessions/{id}/start/`
   - Calls `create_room()` → 100ms API → returns room_id
   - Sets `session.status = IN_PROGRESS`, `session.started_at`
   - **Broadcasts** `session.started` event with room_id and examiner's HMS token
   - Returns: `{session, hms_token, room_id}`

4. **Both Participants Join Video**
   - Both POST `/api/sessions/{id}/join/`
   - Returns: `{room_id, hms_token}` (role-scoped via `HMS_EXAMINER_ROLE` or `HMS_CANDIDATE_ROLE`)
   - Connects to 100ms room

5. **Conduct Session (per-part, per-question flow)**
   - Examiner POST `/api/sessions/{id}/parts/` with `{"part": 1|2|3}`
   - Creates `SessionPart` with `started_at`, **broadcasts** `part.started`
   - Examiner POST `/api/sessions/{id}/parts/{part_num}/available-questions/` (GET filtered questions)
   - Examiner POST `/api/sessions/{id}/parts/{part_num}/ask/` with question_id
   - Creates `SessionQuestion` with `asked_at`, **broadcasts** `question.asked`
   - Examiner POST `/api/sessions/{id}/session-questions/{sq_id}/answer-start/`
   - Sets `answer_started_at` (for Part 2 prep timer), **broadcasts** `answer.started`
   - Examiner POST `/api/sessions/{id}/session-questions/{sq_id}/end/`
   - Sets `ended_at` on question, **broadcasts** `question.ended`
   - Examiner may POST `/api/sessions/{id}/session-questions/{sq_id}/follow-ups/` with follow_up_id
   - Creates `SessionFollowUp`, **broadcasts** `followup.asked` and later `followup.ended`

6. **Submit Notes (mid-session)**
   - Examiner POST `/api/sessions/{id}/session-questions/{sq_id}/notes/`
   - Creates `Note` record (examiner observations)
   - No broadcast (internal record)

7. **End Part & Session**
   - Examiner POST `/api/sessions/{id}/parts/{part_num}/end/`
   - Sets `SessionPart.ended_at`, **broadcasts** `part.ended`
   - Examiner POST `/api/sessions/{id}/end/`
   - Sets `session.status = COMPLETED`, `session.ended_at`, **broadcasts** `session.ended`

8. **Score & Release Results**
   - Examiner POST `/api/sessions/{id}/result/` with criterion bands (1-9 each)
   - Creates/updates `SessionResult` with 4 `CriterionScore` records
   - `compute_overall_band()` calculates IELTS band = (sum(bands) // 2) / 2
   - Examiner POST `/api/sessions/{id}/result/release/`
   - Sets `is_released=True`, `released_at=now()`, **broadcasts** `result.released`
   - Candidate can now see overall_band and feedback

**State Management:**
- Session state persisted to PostgreSQL (synchronous)
- WebSocket events broadcast asynchronously via Channels (in-memory layer in dev, Redis in prod)
- No client-side state management required: all state from REST API
- Events are push-initiated (examiner actions trigger broadcasts), not pull-based

## Key Abstractions

**IELTSMockSession:**
- Purpose: Root aggregate for a mock exam instance (links examiner, candidate, questions, results)
- Files: `session/models.py`, `session/serializers.py`, `session/views.py`
- Pattern: Persistent state machine (status transitions: scheduled → in_progress → completed/cancelled)

**SessionPart:**
- Purpose: Group questions by IELTS part (1, 2, or 3), track timing per part
- Files: `session/models.py`
- Pattern: Composite with SessionQuestion children

**SessionQuestion:**
- Purpose: Single question instance in a session with fine-grained timing (asked_at, answer_started_at, ended_at)
- Files: `session/models.py`
- Pattern: Temporal tracking (timestamps compute prep_duration, speaking_duration, total_duration)

**MockPreset:**
- Purpose: Reusable template for selecting topics across all three parts
- Files: `session/models.py`, `session/serializers.py`
- Pattern: Factory/template (preset → session copies structure, not questions themselves)

**SessionResult + CriterionScore:**
- Purpose: Scoring aggregate with four criteria (FC, GRA, LR, PR) and overall band calculation
- Files: `session/models.py`, `session/serializers.py`
- Pattern: Transactional isolation (scores added after session ends, overall_band computed on demand)

**User (custom AbstractUser):**
- Purpose: Participant identity with role-based access control
- Files: `main/models.py`
- Pattern: Role polymorphism (EXAMINER vs CANDIDATE vs GUEST with different behaviors)

**Topic + Question + FollowUpQuestion:**
- Purpose: Read-only question bank organized hierarchically
- Files: `questions/models.py`
- Pattern: Immutable (questions created via admin or data load, never edited by views)

## Entry Points

**HTTP Routing:**
- Location: `MockIT/urls.py`, `main/urls.py`, `questions/urls.py`, `session/urls.py`
- Triggers: Django's URL dispatcher routes requests to APIView subclasses
- Responsibilities: Request method routing, parameter extraction, middleware stack

**WebSocket Routing:**
- Location: `MockIT/asgi.py`, `session/routing.py`
- Triggers: Connection attempts to `ws/session/{session_id}/` with token query param
- Responsibilities: ProtocolTypeRouter splits HTTP/WebSocket, URLRouter matches session_id, SessionConsumer authenticates and joins group

**Authentication Entry Points:**
- REST: `Authorization: Token {key}` header → DRF TokenAuthentication
- WebSocket: `?token={key}` query param → `SessionConsumer._authenticate()` → Token lookup and user retrieval

**Admin Interface:**
- Location: `MockIT/admin.py`, `main/admin.py`, `questions/admin.py`, `session/admin.py`
- Triggers: Django admin site at `/admin/`
- Responsibilities: CRUD for models, nested admin for Topic/Question/FollowUpQuestion hierarchy

## Error Handling

**Strategy:** Explicit status codes + JSON error responses for all API endpoints, no exceptions bubble to client

**Patterns:**

1. **Authentication/Authorization Errors:**
   - 401 Unauthorized: Missing or invalid token
   - 403 Forbidden: User not participant, wrong role, or permission denied
   - Returns: `{"detail": "Only {role} can {action}."}`

2. **Validation Errors:**
   - 400 Bad Request: Invalid input (serializer validation, status check, constraints)
   - Returns: `{"detail": "message"}` or `{"field": ["error1", "error2"]}` from serializers

3. **Not Found Errors:**
   - 404 Not Found: Resource doesn't exist
   - Returns: `{"detail": "Not found."}`

4. **State Machine Errors:**
   - 400 Bad Request: Invalid state transition (e.g., start completed session, ask follow-up when no question active)
   - Returns: `{"detail": "Session is not in progress. Current status: {status}."}`

5. **External Service Errors:**
   - 502 Bad Gateway: 100ms API error when creating room
   - Returns: `{"detail": "Failed to create video room: {error}"}`

6. **Database Constraint Errors:**
   - 400 Bad Request: Unique constraint, FK violation (caught by serializers)
   - Returns: Serializer validation errors

## Cross-Cutting Concerns

**Logging:**
- Approach: Django logging (minimal, no custom logger setup detected)
- Available via Django's default logger for request/response, SQL queries in debug mode
- Consider: Add detailed logging for state transitions and broadcast events in future

**Validation:**
- Approach: DRF serializers + model validators + custom view logic
- Serializer validation: `is_valid(raise_exception=True)` blocks invalid data early
- Model validation: `clean()` methods on MockPreset (part validation)
- View-level: Explicit role checks, status checks, participant checks (lines like `if request.user != session.examiner`)

**Authentication:**
- Approach: DRF Token Authentication (HTTP) + custom token extraction (WebSocket)
- HTTP: `rest_framework.authentication.TokenAuthentication` via `REST_FRAMEWORK["DEFAULT_AUTHENTICATION_CLASSES"]`
- WebSocket: Token passed as query param, validated by `SessionConsumer._authenticate()`, user role checked by `_is_participant()`
- No session-based auth (stateless token-based only)

**Authorization:**
- Approach: Role-based (User.role == EXAMINER/CANDIDATE/GUEST) + participatory (user is examiner or candidate of session)
- Custom permission class: `main/permissions.py` - `IsEmailVerified` (permission_classes = [IsEmailVerified] in REST_FRAMEWORK settings)
- View-level: Explicit checks e.g. `if not _is_examiner(request.user): return Response(..., 403)`

**CORS:**
- Approach: Enabled globally in `CORS_ALLOW_ALL_ORIGINS = True` (development only, restrict in production)
- Middleware: `corsheaders.middleware.CorsMiddleware` at top of MIDDLEWARE stack

---

*Architecture analysis: 2026-03-27*
