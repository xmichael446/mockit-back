# Global Errors

These errors apply to **all authenticated endpoints** and are not repeated on every endpoint below.

- `401 Unauthorized` — Missing or invalid `Authorization: Token <token>` header.
- `429 Too Many Requests` — Rate limit exceeded. Specific limits:
  - `POST /api/auth/register/` — 10 requests/hour
  - `POST /api/auth/guest-join/` — 20 requests/hour
  - `POST /api/sessions/accept-invite/` — 20 requests/hour

### Error Response Formats

This API uses Django REST Framework defaults (no custom exception handler). Errors come in one of three JSON shapes depending on how the error was raised.

**Shape 1 — Detail object** (most 400/403/404/502 responses from views)

Views that return `Response({"detail": "..."})` directly produce this shape. Always has a single `"detail"` string field.

```json
{"detail": "Only examiners can create presets."}
```

Occurs on: permission checks, resource-not-found errors, business logic rejections (e.g. session state violations), and upstream service failures (100ms API down).

**Shape 2 — Field validation errors** (400 from serializer validation)

When a DRF serializer calls `is_valid(raise_exception=True)`, each failing field maps to an array of error strings. Cross-field errors (from the serializer's `validate()` method) appear under `"non_field_errors"`.

```json
{
  "field_name": ["Error message."],
  "other_field": ["Another error."],
  "non_field_errors": ["Cross-field validation error."]
}
```

Occurs on: `POST /api/auth/register/`, `POST /api/presets/`, `POST /api/sessions/`, `POST /api/sessions/<id>/scores/`, and any other endpoint that runs serializer validation.

**Shape 3 — List errors** (400 from model-level validation)

Model methods that raise `ValidationError(...)` produce a top-level JSON array of error strings.

```json
["Cannot start session: no candidate has accepted the invite yet."]
```

Occurs on: session lifecycle transitions (`start`, `end`, `next-part`, `submit-scores`) that call model-level validation.

**Client-side detection**

```js
if (typeof body === 'object' && 'detail' in body) // Shape 1
if (Array.isArray(body))                           // Shape 3
// otherwise                                       // Shape 2 (field validation)
```
