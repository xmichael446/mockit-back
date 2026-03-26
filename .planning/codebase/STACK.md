# Technology Stack

**Analysis Date:** 2026-03-27

## Languages

**Primary:**
- Python 3.11.9 - Backend API, models, business logic, WebSocket consumers

## Runtime

**Environment:**
- Python 3.11 via virtual environment (`.venv/`)
- ASGI server: Daphne 4.2.1

**Package Manager:**
- pip
- Lockfile: `requirements.txt` present (42 packages)

## Frameworks

**Core:**
- Django 5.2.11 - Web framework, ORM, admin, authentication
- Django REST Framework 3.16.1 - REST API, serializers, token authentication
- Django Channels 4.3.2 - WebSocket support for real-time messaging
- Daphne 4.2.1 - ASGI application server for HTTP + WebSocket

**Admin & UI:**
- django-admin-dracula 0.0.3 - Admin panel styling
- django-nested-admin 4.1.6 - Nested admin panels for question hierarchy

**Extensions:**
- django-cors-headers 4.9.0 - CORS middleware
- django-extensions 4.1 - Development utilities
- rest_framework.authtoken - Token-based authentication

**Real-time:**
- Channels 4.3.2 - WebSocket routing and async consumer support
- Autobahn 25.12.2 - WebSocket protocol implementation
- Twisted 25.5.0 - Async networking framework
- Txaio 25.12.2 - Async abstraction layer

## Key Dependencies

**Critical:**
- psycopg2-binary 2.9.11 - PostgreSQL database adapter
- PyJWT 2.11.0 - JWT token encoding/decoding for 100ms API auth
- requests 2.32.5 - HTTP client for external API calls (100ms, Resend)
- resend 2.10.0 - Email service client for transactional emails

**Serialization & Protocol:**
- msgpack 1.1.2 - Message serialization for Channel layers
- cbor2 5.8.0 - CBOR binary serialization
- ujson 5.11.0 - Fast JSON parsing
- py-ubjson 0.16.1 - UBJSON format support

**WebSocket & Async:**
- asgiref 3.11.1 - ASGI utilities
- Incremental 24.11.0 - Versioning utility for Twisted
- zope.interface 8.2 - Interface definitions for async framework
- service-identity 24.2.0 - SSL certificate verification

**Cryptography & Security:**
- cryptography 46.0.5 - Cryptographic primitives
- pyOpenSSL 25.3.0 - OpenSSL bindings
- certifi 2026.1.4 - CA certificate bundle

**Other:**
- sqlparse 0.5.5 - SQL statement parsing
- django-extensions 4.1 - Management commands
- python-monkey-business 1.1.0 - Utility library

## Configuration

**Environment:**
- Settings module: `MockIT.settings` (via `DJANGO_SETTINGS_MODULE` env var)
- `.venv/` - Virtual environment with isolated packages
- No `.env` file detected (config is in `MockIT/settings.py`)

**Build/Deployment:**
- ASGI application: `MockIT.asgi:application`
- Allowed hosts: `localhost`, `127.0.0.1`, `mi-back.xmichael446.com`, `mockit.live`, `mockit.xmichael446.com`
- Debug mode: `True` in development

## Platform Requirements

**Development:**
- Python 3.11+
- PostgreSQL (tested with 127.0.0.1:5432)
- Virtual environment activation

**Production:**
- ASGI-compatible server (Daphne recommended, configured in settings)
- PostgreSQL database
- Environment variables:
  - `HMS_APP_ACCESS_KEY` - 100ms API access key
  - `HMS_APP_SECRET` - 100ms API secret
  - `HMS_TEMPLATE_ID` - 100ms room template ID
  - `RESEND_API_KEY` - Resend email API key
  - `RESEND_FROM_EMAIL` - Sender email address
  - `FRONTEND_URL` - Frontend base URL for email links
  - Database credentials (NAME, USER, PASSWORD, HOST, PORT)

**Deployment Target:**
- Runs on ASGI servers (Daphne, Uvicorn with async support)
- HTTP + WebSocket via single port via ProtocolTypeRouter
- Static files served from `STATIC_ROOT` (configured as `static/`)

---

*Stack analysis: 2026-03-27*
