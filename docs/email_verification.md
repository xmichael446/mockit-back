# Email Verification Implementation Plan

## Overview
Standard flow: register → receive verification email → click link → verified → can log in. Unverified users cannot log in.

## Files to Create/Modify

| File | Action |
|------|--------|
| `requirements.txt` | Add `resend` |
| `MockIT/settings.py` | Add `RESEND_API_KEY`, `RESEND_FROM_EMAIL`, `FRONTEND_URL` |
| `main/models.py` | Add `is_verified` to `User`, add `EmailVerificationToken` model |
| `main/migrations/000X_...` | Auto-generated migration |
| `main/services/email.py` | **New** — Resend email helper |
| `main/serializers.py` | Add `VerifyEmailSerializer`, `ResendVerificationSerializer` |
| `main/views.py` | Modify `RegisterView` + `LoginView`, add `VerifyEmailView`, `ResendVerificationView` |
| `main/urls.py` | Add 2 new routes |
| `docs/api/authentication.md` | Document new endpoints + updated register/login behavior |

---

## 1. Settings

```python
RESEND_API_KEY = "re_WrKqx7Q6_CgyMv8DmjMW2ArG6Z5VRmb3i"
RESEND_FROM_EMAIL = "noreply@send.xmichael446.com"
FRONTEND_URL = "http://localhost:3000"
```

---

## 2. Model Changes

**`User`**: Add `is_verified = BooleanField(default=False)`

**New `EmailVerificationToken` model**:
```
user        FK → User (CASCADE)
token       UUIDField(auto, unique)
created_at  auto_now_add
expires_at  created_at + 24h
is_used     BooleanField(default=False)
```

---

## 3. `main/services/email.py` (new)

```python
# send_verification_email(user, token_uuid)
# Builds: {FRONTEND_URL}/verify-email?token={token}
# Calls resend.Emails.send(from, to, subject, html)
```

---

## 4. View Logic

| View | Change |
|------|--------|
| **RegisterView** | Create user (`is_verified=False`), create token, send email. Return `201 {"message": "Account created. Check your email to verify."}` — no token returned |
| **LoginView** | After auth, if `not user.is_verified` → `403 {"error": "email_not_verified"}`. Guest users (`is_guest=True`) are exempt. |
| **VerifyEmailView** *(new)* `POST /api/auth/verify-email/` | Body: `{"token": "<uuid>"}`. Validates token (exists, unused, not expired). Sets `is_verified=True`, `is_used=True`. Returns `{"token": "<auth_token>", "user": {...}}`. |
| **ResendVerificationView** *(new)* `POST /api/auth/resend-verification/` | Body: `{"email": "..."}`. Invalidates old tokens, creates new one, sends email. Always returns `200` (no user enumeration). |

**`GuestJoinView`**: unchanged — guests created with `is_verified=True` to avoid accidental blocks.

---

## 5. New Routes

```python
path("auth/verify-email/", VerifyEmailView.as_view())              # AllowAny
path("auth/resend-verification/", ResendVerificationView.as_view()) # AllowAny
```

---

## 6. `docs/api/authentication.md` Updates

Add to **Auth** section:

- `POST /api/auth/register/` — updated response (no token, returns message)
- `POST /api/auth/login/` — document new `403 email_not_verified` error
- `POST /api/auth/verify-email/` — new endpoint, request/response schema
- `POST /api/auth/resend-verification/` — new endpoint, request/response schema

---

## Domain
- Verified domain: `xmichael446.com`
- Sending subdomain: `send.xmichael446.com` (SPF + DKIM verified in Resend)
- From address: `noreply@send.xmichael446.com`
