# Contributing to MockIT

## Dev environment setup

See the README for full setup instructions. The short version:

1. Clone the repo and create a virtual environment.
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.env.example` to `.env` and fill in the required values.
4. Run migrations: `python manage.py migrate`
5. Start the server: `python manage.py runserver`

## Running tests

```bash
python manage.py test
```

To run a single test:

```bash
python manage.py test session.tests.TestClassName.test_method
```

All PRs must pass the full test suite before review.

## Code style

Follow PEP 8. There is no automated linter configured. Key points:

- 4-space indentation
- Descriptive variable and function names
- No unused imports
- Keep functions short and focused

## Submitting a PR

1. Fork the repository.
2. Create a branch from `main` with a descriptive name (e.g. `fix-band-rounding`, `add-reschedule-endpoint`).
3. Make your changes.
4. Open a pull request against `main`.

## What makes a good PR

- Focused scope: one logical change per PR.
- Tests included for any new or modified endpoint behavior.
- API docs updated: if you touch a REST endpoint or WebSocket event, update the relevant file under `docs/api/`.
- Clear PR description explaining what changed and why.

Large PRs without tests or doc updates will be asked to revise before review.
