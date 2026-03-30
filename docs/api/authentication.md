# Authentication

### POST /api/auth/register/
No auth required.
```json
// Request
{ "username": "...", "password": "...", "first_name": "...", "email": "...", "role": 1 }
// Response 201 — EXAMINER (role=1): no token; must verify email before logging in
{ "message": "Account created. Check your email to verify your address." }
// Response 201 — CANDIDATE (role=2): no verification required, token returned immediately
{ "token": "abc123...", "user": { "id": 1, "username": "...", "role": 2, "role_label": "Candidate", ... } }
```

Errors:
- `400` — Validation errors (username already taken, password too short, missing required fields, invalid role value)

### POST /api/auth/login/
No auth required.
```json
// Request
{ "username": "...", "password": "..." }
// Response 200
{ "token": "abc123...", "user": { "id": 1, "username": "...", "role": 1, "role_label": "Examiner", ... } }
// Response 403 — examiner email not verified (does not apply to candidates or guests)
{ "error": "email_not_verified", "message": "Please verify your email before logging in." }
```

Errors:
- `400` — `"Invalid credentials."` | `"Account is disabled."`

### POST /api/auth/verify-email/
No auth required. Validates the token from the verification email. Logs the user in on success.
```json
// Request
{ "token": "<uuid>" }
// Response 200
{ "token": "abc123...", "user": { "id": 1, "username": "...", "role": 1, ... } }
// Response 400
{ "token": ["Invalid verification token."] }
{ "token": ["This token has already been used."] }
{ "token": ["This token has expired. Request a new one."] }
```

Errors:
- `400` — `"Invalid verification token."` | `"This token has already been used."` | `"This token has expired. Request a new one."`

### POST /api/auth/resend-verification/
No auth required. Sends a fresh verification email. Always returns 200 to prevent user enumeration.
Invalidates any existing unused tokens before creating a new one.
```json
// Request
{ "email": "user@example.com" }
// Response 200
{ "message": "If that email exists and is unverified, a new link has been sent." }
```

### POST /api/auth/logout/
```json
// Response 204 (no body)
```

### GET /api/auth/me/
```json
// Response 200
{ "id": 1, "username": "...", "first_name": "...", "last_name": "...", "email": "...", "role": 1, "role_label": "Examiner" }
```

### POST /api/auth/guest-join/
No auth required. Join a session as an ephemeral guest candidate without registration.
Creates a throwaway user with `is_guest=True` scoped to the session.
The returned token works for both REST and WebSocket.

Rate limit: 20 requests/hour (`throttle_scope: guest_join`).

```json
// Request
{ "invite_token": "<string>", "first_name": "<string> (optional)" }
// Response 201
{
  "token": "<drf-token>",
  "user": { "id": 1, "username": "guest_abc123...", "first_name": "Alice", "last_name": "", "role": 2, "is_guest": true },
  "session_id": 5
}
```

Errors:
- `400` — `"Invalid invite token."` | `"Session is not accepting guests (status: ...)."` | `"This invite has already been accepted."` | `"This invite has expired."`
