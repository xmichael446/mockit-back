# External Integrations

**Analysis Date:** 2026-03-27

## APIs & External Services

**Video Infrastructure:**
- 100ms (formerly HyperX) - Live video conferencing platform for mock exam sessions
  - SDK/Client: Direct HTTPS API (no SDK, uses raw HTTP + JWT tokens)
  - Auth: JWT tokens (management token for room creation, app token for join)
  - Configuration:
    - `HMS_APP_ACCESS_KEY` - API access key
    - `HMS_APP_SECRET` - API secret for JWT signing
    - `HMS_TEMPLATE_ID` - Pre-configured room template with examiner/candidate roles
  - Endpoints:
    - `POST https://api.100ms.live/v2/rooms` - Create video room
  - Implementation: `session/services/hms.py`
    - `create_room(session_id)` - Creates room with unique name and template
    - `generate_app_token(room_id, user_id, role)` - Generates JWT for session participant
    - Token TTL: 1 hour (sufficient for IELTS mock session)

**Email Service:**
- Resend - Transactional email delivery
  - SDK/Client: `resend` package (v2.10.0)
  - Auth: API key via `RESEND_API_KEY`
  - Configuration:
    - `RESEND_API_KEY` - API key (required env var)
    - `RESEND_FROM_EMAIL` - Sender email address
  - Use cases:
    - Email verification for examiner registration
    - Verification link sent to examiner's email
  - Implementation: `main/services/email.py`
    - `send_verification_email(user, token_uuid)` - Sends HTML email with verification link
    - Uses template with verification URL from `FRONTEND_URL`

## Data Storage

**Databases:**

**Primary Database:**
- PostgreSQL
  - Connection: `127.0.0.1:5432` (configurable via settings)
  - Database: `mockit`
  - User: `ytpg_user` (credentials in `MockIT/settings.py`)
  - Client: Django ORM (psycopg2-binary adapter)
  - Tables:
    - `main_user` - Extended User model with role field
    - `main_emailverificationtoken` - Email verification tokens
    - `questions_topic` - IELTS topics
    - `questions_question` - Question bank
    - `questions_followupquestion` - Follow-up questions
    - `questions_questionset` - Grouped question sets
    - `session_ieltsmocksession` - Mock exam sessions
    - `session_mockpreset` - Examiner's preset topic selections
    - `session_sessionpart` - Part 1, 2, 3 progress tracking
    - `session_sessionquestion` - Questions asked in session
    - `session_criterionscore` - Scoring for FC, GRA, LR, PR
    - `session_sessionresult` - Overall session results

**File Storage:**
- Local filesystem only
  - Static files: `STATIC_ROOT` = `static/` directory
  - Media files: `MEDIA_ROOT` = `media/` directory
  - Not using cloud storage (S3, GCS, etc.)

**Caching:**
- In-memory only via Django Channels' InMemoryChannelLayer
  - Used for WebSocket group messaging (not traditional caching)
  - Not suitable for production (no persistence across server restarts)

## Authentication & Identity

**Auth Provider:**
- Custom token-based system
  - Implementation: Django REST Framework TokenAuthentication
  - Token model: `rest_framework.authtoken.models.Token`
  - Tokens stored in database, linked to User
  - HTTP: `Authorization: Token <token_key>`
  - WebSocket: `?token=<token_key>` query parameter
  - Validation:
    - HTTP: Handled by DRF middleware
    - WebSocket: Validated in `SessionConsumer._authenticate()` in `session/consumers.py`

**User Roles:**
- EXAMINER (1) - Conducts mock exams, creates presets, scores candidates
- CANDIDATE (2) - Takes mock exams, joins via invite token
- Guest mode - Candidates can join without registration using invite token

**Session Management:**
- Token auto-created on successful registration or login
- Token persists across sessions
- Logout invalidates token via delete

## Monitoring & Observability

**Error Tracking:**
- Not detected - no Sentry, Rollbar, or similar integration

**Logs:**
- Django logging to console/file
  - Server log: `server.log` present in root
  - No external log aggregation detected

**Health Checks:**
- Not implemented

## CI/CD & Deployment

**Hosting:**
- Self-hosted or VPS (based on domain `mockit.live`, `mi-back.xmichael446.com`)
- Not AWS/GCP/Azure-detected (no boto3, google-cloud, azure packages)

**CI Pipeline:**
- Not detected - no GitHub Actions, GitLab CI, Jenkins config found

**Database Migrations:**
- Django migrations in `*/migrations/` directories
- Run via: `python manage.py migrate`

## Environment Configuration

**Required Environment Variables (Production):**
- `HMS_APP_ACCESS_KEY` - 100ms API access key
- `HMS_APP_SECRET` - 100ms API secret
- `HMS_TEMPLATE_ID` - 100ms room template ID
- `RESEND_API_KEY` - Resend email API key
- `RESEND_FROM_EMAIL` - Sender email address (e.g., noreply@xmichael446.com)
- `FRONTEND_URL` - Frontend base URL for email verification links (e.g., https://mockit.live)
- Database connection details:
  - `DB_NAME` - PostgreSQL database name (default: mockit)
  - `DB_USER` - PostgreSQL user (default: ytpg_user)
  - `DB_PASSWORD` - PostgreSQL password
  - `DB_HOST` - PostgreSQL host (default: 127.0.0.1)
  - `DB_PORT` - PostgreSQL port (default: 5432)

**Optional Configuration:**
- `DEBUG` - Django debug mode (default: True in settings.py - should be False in production)
- `SECRET_KEY` - Django secret key (currently hardcoded in settings.py)
- `ALLOWED_HOSTS` - Comma-separated list of allowed hosts

**Secrets Location:**
- Currently hardcoded in `MockIT/settings.py` (security risk)
- Production should load from environment variables or secrets manager

## Webhooks & Callbacks

**Incoming:**
- None detected

**Outgoing:**
- 100ms API calls (not webhooks - synchronous HTTP requests)
- Resend API calls (not webhooks - synchronous HTTP requests)

## Session State Management

**WebSocket Channel Layer:**
- Backend: `channels.layers.InMemoryChannelLayer`
- Group pattern: `"session_<session_id>"`
- Used for broadcasting session events to all connected participants
- Flow:
  1. REST views push events via `_broadcast(session_id, event_type, data)` in `session/views.py`
  2. Helper calls `async_to_sync(channel_layer.group_send)` to target group
  3. Consumer's `session_event()` method receives and forwards to WebSocket client
  - Events include: session start, part changes, questions asked, scoring updates

---

*Integration audit: 2026-03-27*
