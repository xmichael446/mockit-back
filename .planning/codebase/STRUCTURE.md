# Codebase Structure

**Analysis Date:** 2026-03-27

## Directory Layout

```
MockIT/                                   # Project root
├── MockIT/                               # Django project package (settings, ASGI, URLs)
│   ├── settings.py                       # Django configuration (DB, apps, secrets)
│   ├── asgi.py                           # ASGI application entry point (Daphne + Channels)
│   ├── urls.py                           # Root URL dispatcher (routes to app URLs)
│   └── wsgi.py                           # WSGI entry point (not used with Daphne)
├── main/                                 # User/auth app
│   ├── models.py                         # User, EmailVerificationToken, TimestampedModel
│   ├── views.py                          # Auth views: register, login, verify, guest join
│   ├── serializers.py                    # User, auth request/response serializers
│   ├── urls.py                           # Auth endpoints
│   ├── permissions.py                    # IsEmailVerified permission class
│   ├── services/
│   │   └── email.py                      # Email sending via Resend API
│   ├── admin.py                          # Django admin configuration
│   └── migrations/                       # Schema migrations
├── questions/                            # Question bank app (read-only)
│   ├── models.py                         # Topic, Question, FollowUpQuestion
│   ├── views.py                          # Question listing/detail views
│   ├── serializers.py                    # Question serializers
│   ├── urls.py                           # Question endpoints
│   ├── admin.py                          # Nested admin for topic/question hierarchy
│   ├── management/                       # Django management commands (data load)
│   └── migrations/                       # Schema migrations
├── session/                              # Session/exam app (core business logic)
│   ├── models.py                         # IELTSMockSession, SessionPart, SessionQuestion, etc.
│   ├── views.py                          # 1031 LOC: all session REST endpoints
│   ├── serializers.py                    # 376 LOC: session serializers (nested structures)
│   ├── consumers.py                      # WebSocket consumer for real-time events
│   ├── routing.py                        # WebSocket URL pattern
│   ├── urls.py                           # HTTP endpoints (67 LOC, extensively documented)
│   ├── services/
│   │   └── hms.py                        # 100ms video room API client
│   ├── admin.py                          # Admin configuration for session models
│   └── migrations/                       # Schema migrations
├── docs/                                 # Documentation
│   ├── api.md                            # Complete REST + WebSocket API reference
│   ├── architecture.md                   # Existing architecture overview (5.5K)
│   ├── admin.md                          # Django admin setup guide
│   ├── email_verification.md             # Email verification flow
│   └── landing_page.md                   # Frontend landing page specs
├── .planning/
│   └── codebase/                         # Generated codebase analysis documents
├── static/                               # Collected static files (Django admin, DRF browsable API)
├── templates/                            # HTML templates (empty, frontend is separate React app)
├── media/                                # User uploads
│   └── recordings/                       # Session audio/video files
├── manage.py                             # Django CLI entry point
├── requirements.txt                      # Python dependencies
├── CLAUDE.md                             # Project instructions for Claude Code
├── data.json                             # Initial fixture data (topics, questions)
└── .gitignore                            # Git ignore rules
```

## Directory Purposes

**MockIT/ (project config):**
- Purpose: Django project configuration and ASGI/routing setup
- Contains: settings.py (database, installed apps, secrets), asgi.py (protocol router), urls.py (HTTP routing), wsgi.py (unused in production)
- Key files: `settings.py` defines INSTALLED_APPS order (daphne must be first), channel layer config (InMemoryChannelLayer), HMS credentials, database credentials

**main/ (auth & user management):**
- Purpose: User model, authentication, email verification, guest signup
- Contains: Custom AbstractUser subclass with role/is_verified/is_guest fields, token-based auth views, email service
- Key files:
  - `main/models.py`: User, EmailVerificationToken (24hr expiry), TimestampedModel (abstract base with created_at/updated_at)
  - `main/views.py`: RegisterView, LoginView, VerifyEmailView, GuestJoinView, MeView, LogoutView
  - `main/serializers.py`: RegisterSerializer, LoginSerializer, UserMinimalSerializer, GuestJoinSerializer
  - `main/services/email.py`: Resend API wrapper for verification emails

**questions/ (question bank - read-only):**
- Purpose: IELTS question bank with hierarchical organization (Topic → Question → FollowUpQuestion)
- Contains: Three immutable models representing IELTS question structures
- Key files:
  - `questions/models.py`: Topic (with part 1/2/3 selection and auto-numbering), Question (difficulty levels, bullet points for Part 2), FollowUpQuestion
  - `questions/views.py`: TopicListView, TopicDetailView, QuestionDetailView (read-only, no create/update)
  - `questions/admin.py`: django-nested-admin setup for editing topic/question hierarchies inline
  - `questions/management/`: Custom command for data import

**session/ (main business logic):**
- Purpose: Complete session lifecycle, real-time orchestration, scoring
- Contains:
  - 14 models tracking session state (IELTSMockSession, SessionPart, SessionQuestion, SessionFollowUp, SessionResult, CriterionScore, MockPreset, SessionRecording, Note)
  - 20+ APIView classes covering all operations (create, start, join, ask, end, score, release)
  - WebSocket consumer for real-time participant communication
  - 100ms video API integration
- Key files:
  - `session/models.py` (214 LOC): State machine models with temporal tracking
  - `session/views.py` (1031 LOC): All REST endpoints, _broadcast() helper for WebSocket push
  - `session/serializers.py` (376 LOC): Nested serializers for complex relationships
  - `session/consumers.py`: AsyncWebsocketConsumer for real-time events
  - `session/services/hms.py`: 100ms room creation and token generation
  - `session/urls.py` (67 LOC): Comprehensive URL patterns with clear comments

**docs/ (reference documentation):**
- Purpose: Detailed specifications and guides
- Key files:
  - `docs/api.md` (19K): Complete REST API + WebSocket event reference
  - `docs/architecture.md` (5.5K): Data model diagram and session lifecycle
  - `docs/admin.md`: Admin interface setup instructions
  - `docs/email_verification.md`: Email flow documentation

**static/ & templates/:**
- static/: Django admin CSS/JS, DRF browsable API assets (auto-collected, not committed)
- templates/: Empty (frontend is separate React/TypeScript app deployed independently)

**media/:**
- Purpose: User-uploaded files (session recordings, etc.)
- Subdirs: recordings/ (audio/video files per session)

## Key File Locations

**Entry Points:**
- `manage.py`: Django CLI (runserver, migrate, shell, etc.)
- `MockIT/asgi.py`: ASGI server entry point (Daphne)
- `MockIT/wsgi.py`: WSGI entry point (unused with Daphne, kept for compatibility)
- `MockIT/urls.py`: Root URL routing to app-specific URLs

**Configuration:**
- `MockIT/settings.py`: All Django settings (DB connection, auth, secrets, installed apps)
- `requirements.txt`: Python package dependencies
- `CLAUDE.md`: Claude-specific project instructions

**Core Logic:**
- `session/models.py`: Session state machines and related models
- `session/views.py`: REST endpoint implementations with broadcast logic
- `session/consumers.py`: WebSocket consumer
- `main/models.py`: User model with role field

**Database:**
- `session/migrations/`: Schema migrations for session models
- `main/migrations/`: Schema migrations for User model
- `questions/migrations/`: Schema migrations for question models

**Testing:**
- `session/tests.py`: (empty, minimal test coverage)
- `main/tests.py`: (empty, minimal test coverage)
- `questions/tests.py`: (empty, minimal test coverage)

## Naming Conventions

**Files:**
- `models.py`: Django ORM models (one per app)
- `views.py`: APIView or View subclasses for HTTP routing (one per app)
- `serializers.py`: DRF Serializer subclasses for validation/transformation (one per app)
- `urls.py`: URL patterns and routing (one per app, root in MockIT/)
- `admin.py`: Django admin configuration (one per app)
- `consumers.py`: Django Channels consumer classes (only session app)
- `routing.py`: Channels URL patterns (only session app)
- `permissions.py`: Custom permission classes (main app)
- `services/`: Utility modules for external integrations (hms.py, email.py)
- `management/commands/`: Custom Django management commands (questions app for data import)
- `migrations/`: Auto-generated by Django makemigrations

**Directories:**
- `MockIT/`: Project-level config (not an app)
- `{app}/`: Each app contains models, views, tests, admin, serializers, migrations
- `{app}/services/`: External integrations (100ms, Resend)
- `{app}/migrations/`: Schema version control
- `docs/`: Reference docs (not code)

**Classes:**
- `*View`: APIView or View subclasses (e.g., SessionDetailView, RegisterView)
- `*Consumer`: Channels consumer subclasses (e.g., SessionConsumer)
- `*Serializer`: DRF serializer subclasses (e.g., SessionSerializer, RegisterSerializer)
- Models: PascalCase (e.g., IELTSMockSession, SessionQuestion, MockPreset)
- Choices: PascalCase IntegerChoices (e.g., SessionStatus, SpeakingCriterion, UserRole)

**Functions:**
- `_broadcast()`: Private helper (underscore prefix)
- `_session_qs()`: Private ORM helper (underscore prefix)
- `_is_examiner()`, `_is_candidate()`: Private role checks (underscore prefix)

**Variables:**
- `session_id`: Parameter or variable
- `request`: HTTP request object (uniform DRF convention)
- `user`: Authenticated user
- `pk`: Primary key identifier (Django convention)
- `qs`: QuerySet (DRF/Django convention for database queries)

## Where to Add New Code

**New API Endpoint:**
1. Add APIView subclass to `session/views.py` (or appropriate app)
2. Import in `session/urls.py` and add path() entry
3. Create serializers in `session/serializers.py` as needed
4. If broadcasting needed, call `_broadcast(session_id, event_type, data)` from view
5. Document in `docs/api.md`

**New Model:**
1. Add to `{app}/models.py` in appropriate app
2. Inherit from `TimestampedModel` for created_at/updated_at
3. Run `python manage.py makemigrations {app}` → `python manage.py migrate`
4. Add serializer to `{app}/serializers.py`
5. Add admin config to `{app}/admin.py` if CRUD needed

**New WebSocket Event:**
1. Define event structure (payload) in `docs/api.md`
2. Emit from view via `_broadcast(session_id, "event.type", {payload})`
3. Handle in frontend (consumer already forwards all events as-is)
4. No changes to `SessionConsumer` needed (it's event-agnostic)

**New External Service:**
1. Create `{app}/services/{service}.py`
2. Implement wrapper functions (e.g., `create_room()`, `send_email()`)
3. Store credentials in `MockIT/settings.py` (never hardcode)
4. Import and call from views as needed
5. Add error handling (try/except with 502 response in views)

**New Permission/Validation:**
1. Custom permission: Subclass `rest_framework.permissions.BasePermission` in `{app}/permissions.py`
2. Model validation: Add `clean()` method to model (e.g., MockPreset.clean())
3. Serializer validation: Add `validate_*()` methods in serializers
4. View-level: Add explicit `if not` checks before operations (e.g., `if not _is_examiner(user)`)

## Special Directories

**migrations/:**
- Purpose: Schema version control (auto-generated by Django)
- Generated: Yes (via `makemigrations`)
- Committed: Yes (all migrations in git)
- Pattern: Numbered files (0001_initial.py, 0002_alter_field.py) applied sequentially

**management/commands/:**
- Purpose: Custom Django CLI commands (e.g., data import, cleanup)
- Example: `questions/management/commands/load_questions.py` for initial data
- Run: `python manage.py load_questions`
- Generated: No (manually created)
- Committed: Yes

**services/:**
- Purpose: Encapsulated external API clients and utilities
- Examples: `session/services/hms.py` (100ms), `main/services/email.py` (Resend)
- Pattern: Pure functions, no side effects, error handling with exceptions
- Tested: Not currently (no test files) — candidate for improvement

**docs/:**
- Purpose: Reference documentation (not code)
- Generated: No (manually maintained)
- Committed: Yes
- Pattern: Markdown files with API specs, architecture diagrams, flow docs

---

*Structure analysis: 2026-03-27*
