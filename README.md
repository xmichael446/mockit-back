# MockIT

An IELTS Speaking mock exam platform where examiners conduct live sessions with candidates over video, drawing questions from a structured question bank in real-time.

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

---

## Features

- Examiner-driven session lifecycle: schedule, start, run parts, ask questions, score, and release results
- Live video rooms via 100ms, with role-based tokens (examiner / candidate)
- Real-time WebSocket events keep both participants in sync throughout the session
- Structured question bank: Topics → Questions → Follow-up Questions, organized by IELTS Speaking Part
- IELTS band scoring across four criteria (FC, GRA, LR, PR), with overall band auto-computed to the nearest 0.5
- AI-powered speech assessment using Gemini 2.5 Flash on uploaded audio recordings
- Examiner availability scheduling and candidate session-request workflow
- Public share links for completed sessions

## Tech Stack

| Layer | Technology |
|---|---|
| Framework | Django 5.2, Django REST Framework |
| Async / WebSocket | Django Channels 4, Daphne (ASGI) |
| Database | PostgreSQL (psycopg2) |
| Task queue | django-q2 (ORM-backed) |
| Video | 100ms |
| AI assessment | Google Gemini (`google-genai`) |
| Email | Resend |
| Auth | DRF Token authentication |

## Prerequisites

- Python 3.11+
- PostgreSQL 14+
- No Redis required — the channel layer uses `InMemoryChannelLayer` and the task queue uses the ORM backend

## Setup

**1. Clone and create a virtual environment**

```bash
git clone https://github.com/xmichael446/mockit-back.git
cd MockIT
python -m venv .venv
source .venv/bin/activate
```

**2. Install dependencies**

```bash
pip install -r requirements.txt
```

**3. Configure environment variables**

```bash
cp .env.example .env
```

Open `.env` and fill in every value. Required variables:

| Variable | Description |
|---|---|
| `SECRET_KEY` | Django secret key |
| `DB_NAME` / `DB_USER` / `DB_PASSWORD` / `DB_HOST` / `DB_PORT` | PostgreSQL connection |
| `HMS_APP_ACCESS_KEY` / `HMS_APP_SECRET` / `HMS_TEMPLATE_ID` | 100ms video credentials |
| `RESEND_API_KEY` | Resend email API key |
| `GEMINI_API_KEY` | Google Gemini API key |

Optional:

| Variable | Default | Description |
|---|---|---|
| `GEMINI_MODEL` | `gemini-2.5-flash` | Gemini model ID |
| `AI_FEEDBACK_MONTHLY_LIMIT` | `10` | Per-user AI feedback calls per month |

**4. Create the database**

```bash
createdb mockit   # or use your PostgreSQL client
```

**5. Apply migrations**

```bash
python manage.py migrate
```

**6. Create a superuser (optional, for admin panel)**

```bash
python manage.py createsuperuser
```

**7. Start the development server**

```bash
python manage.py runserver
```

The server runs at `http://localhost:8000`. Daphne is the ASGI server — both HTTP and WebSocket traffic are handled by the same process in development.

**8. Start the task queue worker (required for AI feedback jobs)**

```bash
python manage.py qcluster
```

## Running Tests

```bash
python manage.py test
```

To run a single test class or method:

```bash
python manage.py test session.tests.TestClassName.test_method
```

## Architecture

Two user roles exist: **Examiner** and **Candidate**. An examiner builds a `MockPreset` (selecting topics per IELTS part), then creates a session from it and shares an invite token with the candidate. Once both parties join, the examiner drives the session through its parts — asking questions, recording follow-ups, and taking notes — before submitting criterion scores (FC, GRA, LR, PR on a 1–9 band scale). A `SessionResult` is auto-computed and released to the candidate.

Real-time coordination uses Django Channels over WebSocket (`ws/session/<id>/?token=<token>`). All REST views that mutate session state call `_broadcast()`, which pushes events to a per-session channel group; the `SessionConsumer` forwards those events to connected clients.

Video rooms are created via the 100ms API at session start, and fresh role-specific tokens are issued whenever a participant joins. AI speech assessment runs as a background task via django-q2, processing audio recordings with the Gemini API and returning band scores and feedback.

## API Documentation

Full REST and WebSocket reference is in [`docs/api/`](docs/api/index.md).

Key sections: Authentication, Sessions, Session Parts, Questions, Results, AI Feedback, WebSocket events, and Typical Flows with end-to-end examples.

## License

MIT — see [LICENSE](LICENSE).
