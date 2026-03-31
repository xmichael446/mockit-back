# Profiles

### GET /api/profiles/examiners/
Any authenticated user. Lists all examiner public profiles (paginated). Phone field is hidden.

Query parameters:
- `is_verified` (optional): `true` to show only verified examiners, `false` for unverified only
- `ordering` (optional): `completed_session_count` (ascending) or `-completed_session_count` (descending)

```json
// Response 200
{
  "count": 25,
  "next": "https://example.com/api/profiles/examiners/?page=2",
  "previous": null,
  "results": [
    {
      "id": 1,
      "user": { "id": 1, "username": "john_examiner", "email": "john@example.com", "first_name": "John", "last_name": "Doe" },
      "bio": "IELTS examiner with 10 years experience",
      "full_legal_name": "John Michael Doe",
      "profile_picture": "https://example.com/media/profiles/john.jpg",
      "is_verified": true,
      "completed_session_count": 5,
      "credential": { "id": 1, "listening_score": 8.5, "reading_score": 8.0, "writing_score": 7.5, "speaking_score": 9.0, "certificate_url": "https://example.com/media/credentials/cert.pdf" }
    }
  ]
}
```

Errors:
- `401` — Authentication required

### GET /api/profiles/examiner/me/
Examiner only. Returns own full profile including phone and credential.
```json
// Response 200
{
  "id": 1,
  "user": { "id": 1, "username": "john_examiner", "email": "john@example.com", "first_name": "John", "last_name": "Doe" },
  "bio": "IELTS examiner with 10 years experience",
  "full_legal_name": "John Michael Doe",
  "phone": "+998901234567",
  "profile_picture": "https://example.com/media/profiles/john.jpg",
  "is_verified": true,
  "completed_session_count": 5,
  "credential": {
    "id": 1,
    "listening_score": 8.5,
    "reading_score": 8.0,
    "writing_score": 7.5,
    "speaking_score": 9.0,
    "certificate_url": "https://example.com/media/credentials/cert.pdf"
  }
}
```

Errors:
- `404` — `"Examiner profile not found."` (caller is not an examiner)

### PATCH /api/profiles/examiner/me/
Examiner only. Partial update of own profile. Writable fields: `bio`, `full_legal_name`, `phone`, `profile_picture`. Fields `is_verified` and `completed_session_count` are read-only.
```json
// Request
{ "bio": "IELTS examiner with 10 years experience" }
// Response 200 — same shape as GET /api/profiles/examiner/me/
```

Errors:
- `404` — `"Examiner profile not found."` (caller is not an examiner)
- `400` — Validation errors

### GET /api/profiles/examiner/<id>/
Any authenticated user. Public view of an examiner's profile. Phone field is hidden.
```json
// Response 200
{
  "id": 1,
  "user": { "id": 1, "username": "john_examiner", "email": "john@example.com", "first_name": "John", "last_name": "Doe" },
  "bio": "IELTS examiner with 10 years experience",
  "full_legal_name": "John Michael Doe",
  "profile_picture": "https://example.com/media/profiles/john.jpg",
  "is_verified": true,
  "completed_session_count": 5,
  "credential": {
    "id": 1,
    "listening_score": 8.5,
    "reading_score": 8.0,
    "writing_score": 7.5,
    "speaking_score": 9.0,
    "certificate_url": "https://example.com/media/credentials/cert.pdf"
  }
}
```

Errors:
- `404` — `"Examiner profile not found."`

### GET /api/profiles/examiner/me/credential/
Examiner only. Returns the examiner's IELTS credential scores.
```json
// Response 200
{
  "id": 1,
  "listening_score": 8.5,
  "reading_score": 8.0,
  "writing_score": 7.5,
  "speaking_score": 9.0,
  "certificate_url": "https://example.com/media/credentials/cert.pdf"
}
```

Errors:
- `404` — `"Examiner profile not found."` | `"No credential found."`

### PUT /api/profiles/examiner/me/credential/
Examiner only. Create or update (idempotent) own credential. All fields required.
```json
// Request
{
  "listening_score": 8.5,
  "reading_score": 8.0,
  "writing_score": 7.5,
  "speaking_score": 9.0,
  "certificate_url": "https://example.com/media/credentials/cert.pdf"
}
// Response 200 — credential object
{
  "id": 1,
  "listening_score": 8.5,
  "reading_score": 8.0,
  "writing_score": 7.5,
  "speaking_score": 9.0,
  "certificate_url": "https://example.com/media/credentials/cert.pdf"
}
```

Errors:
- `404` — `"Examiner profile not found."`
- `400` — Validation errors

### GET /api/profiles/candidate/me/
Candidate only. Returns own full profile including score history.
```json
// Response 200
{
  "id": 1,
  "user": { "id": 2, "username": "jane_candidate", "email": "jane@example.com", "first_name": "Jane", "last_name": "Smith" },
  "profile_picture": "https://example.com/media/profiles/jane.jpg",
  "target_speaking_score": 7.0,
  "current_speaking_score": 6.5,
  "score_history": [
    { "id": 1, "session_id": 5, "overall_band": 6.5, "created_at": "2024-06-01T14:00:00Z" }
  ]
}
```

Errors:
- `404` — `"Candidate profile not found."` (caller is not a candidate)

### PATCH /api/profiles/candidate/me/
Candidate only. Partial update of own profile. Writable fields: `profile_picture`, `target_speaking_score`, `current_speaking_score`. Scores must be between 1.0 and 9.0 in 0.5 increments.
```json
// Request
{ "target_speaking_score": 7.5 }
// Response 200 — same shape as GET /api/profiles/candidate/me/
```

Errors:
- `404` — `"Candidate profile not found."` (caller is not a candidate)
- `400` — `"Score must be between 1.0 and 9.0."` | `"Score must be a multiple of 0.5."`

### GET /api/profiles/candidate/<id>/
Any authenticated user. Public read-only view of a candidate's profile, includes score history.
```json
// Response 200
{
  "id": 1,
  "user": { "id": 2, "username": "jane_candidate", "email": "jane@example.com", "first_name": "Jane", "last_name": "Smith" },
  "profile_picture": "https://example.com/media/profiles/jane.jpg",
  "target_speaking_score": 7.0,
  "current_speaking_score": 6.5,
  "score_history": [
    { "id": 1, "session_id": 5, "overall_band": 6.5, "created_at": "2024-06-01T14:00:00Z" }
  ]
}
```

Errors:
- `404` — `"Candidate profile not found."`
