# Phase 4: Profiles - Research

**Researched:** 2026-03-30
**Domain:** Django profile models, DRF serializers, signals, ImageField, denormalized counters
**Confidence:** HIGH

<user_constraints>
## User Constraints (from CONTEXT.md)

### Locked Decisions

**Profile API Design**
- Profiles auto-create via `post_save` signal on User creation — zero friction for frontend
- Role-scoped endpoints: `/api/profiles/examiner/me/` and `/api/profiles/candidate/me/` for own profile; `/api/profiles/examiner/<id>/` and `/api/profiles/candidate/<id>/` for public view
- Profile views and serializers live in `main/views.py` and `main/serializers.py` — profiles are extensions of User model already in main/
- GET on own profile returns nested User fields (`user: {id, username, email, first_name, last_name}`) as read-only

**Data Model Details**
- Separate `ExaminerCredential` model for IELTS credentials with fields for all bands (listening, reading, writing, speaking) + certificate URL
- Denormalized `completed_session_count` field on ExaminerProfile, updated when sessions complete
- Candidate `target_speaking_score`: DecimalField(max_digits=2, decimal_places=1) with 0.5 step validation (1.0-9.0)
- Profile pictures: ImageField stored in `/media/` directory (no S3) — both ExaminerProfile and CandidateProfile

**Score History & Permissions**
- Denormalized `ScoreHistory` model to store band score records per completed session
- Candidate profiles are viewable by examiners (public candidate profiles)
- `is_verified` on ExaminerProfile is admin-managed only (Django admin panel)

### Claude's Discretion
- Admin registration details for new profile models
- Signal implementation specifics for auto-create
- Serializer field ordering and response shape details

### Deferred Ideas (OUT OF SCOPE)
None — discussion stayed within phase scope
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|------------------|
| EXAM-01 | Examiner can create/update their profile with bio, full legal name, and profile picture URL | ExaminerProfile model + PATCH endpoint in main/ |
| EXAM-02 | Examiner profile displays IELTS credentials (band scores and certificate URL) | ExaminerCredential OneToOne model on ExaminerProfile |
| EXAM-03 | Examiner profile shows is_verified badge status (admin-managed boolean) | is_verified field on ExaminerProfile, read-only in API |
| EXAM-04 | Examiner profile includes phone number field supporting Uzbekistan format | CharField with regex validator for +998 format |
| EXAM-05 | Examiner profile displays completed session count | Denormalized completed_session_count, incremented in EndSessionView |
| EXAM-06 | User (candidate) can view an examiner's public profile | GET /api/profiles/examiner/<id>/ with phone field hidden |
| STUD-01 | Candidate can create/update their profile with profile picture URL and target speaking score | CandidateProfile model + PATCH endpoint |
| STUD-02 | Student profile stores current_speaking_score (initially set manually) | DecimalField on CandidateProfile, writable on own profile |
| STUD-04 | Student profile exposes band score history data from all completed sessions | ScoreHistory model with FK to CandidateProfile |
</phase_requirements>

---

## Summary

Phase 4 adds role-specific profile models as OneToOne extensions on the existing `main/User` model. The `ExaminerProfile` covers bio, legal name, phone, credentials, session count and verified status. The `CandidateProfile` covers target and current speaking scores plus a `ScoreHistory` record per completed session. A `post_save` signal auto-creates both profiles at user registration so the frontend never needs to manually create them.

All views, serializers and URL patterns extend the existing `main/` app. `ImageField` requires Pillow which is NOT currently in requirements.txt — this must be installed before running migrations. The `media/` directory already exists with `MEDIA_URL`/`MEDIA_ROOT` configured, used by `SessionRecording`; the new profile images will land in `media/profile_pictures/`.

`completed_session_count` is incremented directly in `EndSessionView.post()` (session/views.py line ~287, after `session.save()`). `ScoreHistory` records are appended in `ReleaseResultView.post()` (session/views.py line ~935, after `result.save()`), which is the correct trigger because that is when the candidate sees the result.

**Primary recommendation:** Build all four models in `main/models.py`, wire the signal in `main/apps.py`, install Pillow, then add views and URL patterns in `main/`. Use `F()` expressions for atomic increment of `completed_session_count` to be safe under concurrent requests.

---

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Django ORM | 5.2.11 (project) | OneToOne models, signals, ImageField | Already in project |
| Django REST Framework | 3.16.1 (project) | Serializers, APIView, parsers | Already in project |
| Pillow | latest (NEW — not in requirements) | Required for ImageField to function | Django official requirement for ImageField |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| django.db.models.F | built-in | Atomic field increment | Increment completed_session_count without race condition |
| django.db.models.signals.post_save | built-in | Auto-create profiles on User save | Zero-friction profile creation |
| rest_framework.parsers.MultiPartParser | built-in | Multipart form-data for image upload | Profile picture PATCH |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| ImageField (local media) | URLField | URLField simpler but doesn't store files; decision locked to ImageField |
| Denormalized ScoreHistory | Computed from SessionResult on the fly | Live computation simpler but slower; denormalized is the locked decision |

**Installation (new dependency only):**
```bash
pip install Pillow
# then add to requirements.txt
```

---

## Architecture Patterns

### Recommended Project Structure
```
main/
├── models.py          # Add ExaminerProfile, CandidateProfile, ExaminerCredential, ScoreHistory
├── serializers.py     # Add profile serializers (detail + public variants)
├── views.py           # Add profile APIView classes
├── urls.py            # Add profile URL patterns
├── admin.py           # Register new models
└── apps.py            # Wire post_save signal in ready()
```

### Pattern 1: OneToOne Profile via post_save Signal

**What:** Create a profile row automatically whenever a User row is created.
**When to use:** Profile is always present — frontend and views can assume it exists.
**Example:**
```python
# main/models.py
class ExaminerProfile(TimestampedModel):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="examiner_profile",
    )
    bio = models.TextField(blank=True)
    full_legal_name = models.CharField(max_length=255, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    profile_picture = models.ImageField(upload_to="profile_pictures/", blank=True, null=True)
    is_verified = models.BooleanField(default=False)
    completed_session_count = models.PositiveIntegerField(default=0)

    def __str__(self):
        return f"ExaminerProfile({self.user.username})"
```

```python
# main/apps.py
from django.apps import AppConfig

class MainConfig(AppConfig):
    name = "main"

    def ready(self):
        from . import signals  # noqa: F401
```

```python
# main/signals.py  (NEW file)
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.conf import settings
from .models import ExaminerProfile, CandidateProfile, User

@receiver(post_save, sender=settings.AUTH_USER_MODEL)
def create_user_profile(sender, instance, created, **kwargs):
    if not created:
        return
    if instance.role == User.Role.EXAMINER:
        ExaminerProfile.objects.get_or_create(user=instance)
    elif instance.role == User.Role.CANDIDATE:
        CandidateProfile.objects.get_or_create(user=instance)
```

### Pattern 2: Dual Serializers for Public vs Own Profile

**What:** Owner sees full profile (phone, editable fields). Public viewer sees read-only subset with phone hidden.
**When to use:** Any time a resource has both private and public consumers.
**Example:**
```python
# main/serializers.py

class ExaminerProfileDetailSerializer(serializers.ModelSerializer):
    """Owner view — phone visible, all fields writable."""
    user = UserMinimalSerializer(read_only=True)

    class Meta:
        model = ExaminerProfile
        fields = (
            "id", "user", "bio", "full_legal_name", "phone",
            "profile_picture", "is_verified", "completed_session_count",
        )
        read_only_fields = ("is_verified", "completed_session_count")


class ExaminerProfilePublicSerializer(serializers.ModelSerializer):
    """Public view — phone hidden."""
    user = UserMinimalSerializer(read_only=True)

    class Meta:
        model = ExaminerProfile
        fields = (
            "id", "user", "bio", "full_legal_name",
            "profile_picture", "is_verified", "completed_session_count",
        )
        read_only_fields = fields
```

### Pattern 3: Atomic Increment with F()

**What:** Increment `completed_session_count` without a read-then-write race.
**When to use:** Whenever a counter is updated from a view that could be called concurrently.
**Example:**
```python
# session/views.py — inside EndSessionView.post(), after session.save()
from django.db.models import F
from main.models import ExaminerProfile

ExaminerProfile.objects.filter(user=session.examiner).update(
    completed_session_count=F("completed_session_count") + 1
)
```

### Pattern 4: ScoreHistory Denormalized Record

**What:** Append a `ScoreHistory` row when a result is released, linking to the candidate's profile.
**When to use:** Band history must be queryable without aggregating across sessions.
**Example:**
```python
# main/models.py
class ScoreHistory(TimestampedModel):
    candidate_profile = models.ForeignKey(
        CandidateProfile, on_delete=models.CASCADE, related_name="score_history"
    )
    session = models.ForeignKey(
        "session.IELTSMockSession", on_delete=models.CASCADE, related_name="score_history"
    )
    overall_band = models.DecimalField(max_digits=3, decimal_places=1)

    class Meta:
        ordering = ["-created_at"]
        unique_together = [("candidate_profile", "session")]

    def __str__(self):
        return f"ScoreHistory({self.candidate_profile.user.username}, band={self.overall_band})"
```

```python
# session/views.py — inside ReleaseResultView.post(), after result.save()
from main.models import CandidateProfile, ScoreHistory

if session.candidate and result.overall_band is not None:
    try:
        candidate_profile = CandidateProfile.objects.get(user=session.candidate)
        ScoreHistory.objects.get_or_create(
            candidate_profile=candidate_profile,
            session=session,
            defaults={"overall_band": result.overall_band},
        )
    except CandidateProfile.DoesNotExist:
        pass  # Guest candidates or pre-signal users have no profile
```

### Pattern 5: Phone Validation for Uzbekistan Format

**What:** CharField with RegexValidator for `+998XXXXXXXXX` (13 chars).
**When to use:** EXAM-04 requirement.
**Example:**
```python
from django.core.validators import RegexValidator

uzbek_phone_validator = RegexValidator(
    regex=r"^\+998\d{9}$",
    message="Phone number must be in format: +998XXXXXXXXX",
)

# on ExaminerProfile:
phone = models.CharField(max_length=13, blank=True, validators=[uzbek_phone_validator])
```

### Pattern 6: target_speaking_score Step Validation

**What:** Accept only 0.5-step values 1.0–9.0.
**When to use:** STUD-01 requirement — DecimalField(max_digits=2, decimal_places=1).
**Example:**
```python
# main/serializers.py
def validate_target_speaking_score(self, value):
    if value is not None:
        if value < 1 or value > 9:
            raise serializers.ValidationError("Score must be between 1.0 and 9.0.")
        # 0.5-step check: value * 2 must be a whole integer
        if (value * 2) % 1 != 0:
            raise serializers.ValidationError("Score must be a multiple of 0.5.")
    return value
```

### Anti-Patterns to Avoid

- **Creating signal in models.py directly:** Import cycles. Always use a separate `signals.py` file wired in `apps.py:ready()`.
- **Using `get_or_create` on every request in views:** Signal handles creation; views can use `profile = request.user.examiner_profile` safely after signal wires up.
- **Incremental update via read + write:** `profile.completed_session_count += 1; profile.save()` — race condition under load. Always use `F()` expression.
- **Registering signal without `apps.py` ready hook:** Signal won't fire if wired outside `ready()`.
- **Using `post_save` with `update_fields` set:** Django only fires the signal but the profile creation only needs to happen when `created=True` — always guard with `if not created: return`.
- **Skipping Pillow install before makemigrations:** Django raises `django.core.exceptions.ImproperlyConfigured` if Pillow is missing when ImageField is present.

---

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Profile auto-creation | Custom middleware or view-level creation | `post_save` signal | Signal is atomic with user creation; view-level creates timing gaps |
| Atomic counter increment | `profile.count += 1; profile.save()` | `F("completed_session_count") + 1` | Race condition under concurrent requests |
| Image storage | Custom file handler | Django `ImageField` + `MEDIA_ROOT` | Django handles naming, storage, and URL generation |
| Phone format validation | View-level regex check | `RegexValidator` on the model field | Enforced at DB write, reusable across admin and API |

**Key insight:** Django's ORM provides all primitives needed (signals, F expressions, ImageField, validators). No extra libraries required except Pillow.

---

## Runtime State Inventory

Not applicable — this is a greenfield phase (new models, no rename/migration of existing data).

---

## Common Pitfalls

### Pitfall 1: Missing Pillow Breaks Migration

**What goes wrong:** `python manage.py makemigrations` succeeds, but `migrate` raises `ImproperlyConfigured: Cannot use ImageField because Pillow is not installed.`
**Why it happens:** Django validates ImageField requires Pillow at runtime, not at migration generation time.
**How to avoid:** Run `pip install Pillow` and add it to `requirements.txt` BEFORE running migrations.
**Warning signs:** Any `ImageField` in the codebase will fail if Pillow is absent.

### Pitfall 2: Signal Not Firing for Guest Users

**What goes wrong:** `CandidateProfile.DoesNotExist` in `ReleaseResultView` when the session candidate is a guest.
**Why it happens:** Guest users are created with `User.objects.create(...)` but the signal fires and tries to create a `CandidateProfile` — it WILL fire. However, accessing `user.candidate_profile` after `get_or_create` may raise DoesNotExist if an earlier code path created the guest before the signal was registered (e.g., pre-migration guests). Also, `ScoreHistory` write must use `get_or_create` to be idempotent (result.release can be called again on rerelease if logic changes).
**How to avoid:** Always wrap `CandidateProfile.objects.get()` in try/except in cross-app integration points.
**Warning signs:** Guest candidates created before Phase 4 migrations are applied have no profile rows.

### Pitfall 3: Circular Import from Cross-App Signal

**What goes wrong:** `ImportError: cannot import name 'ScoreHistory' from 'main.models'` when session/views.py imports from main/models.py.
**Why it happens:** `session/views.py` already imports `from main.models import User`. Adding `CandidateProfile, ScoreHistory` to that import is safe because `main` doesn't import from `session` at module level. BUT if you move session-related logic into `main/signals.py`, you risk a circular import (`main` → `session` → `main`).
**How to avoid:** Cross-app integration code (increment counter, append ScoreHistory) belongs in `session/views.py`, not in `main/signals.py`. The signal only creates the profile row.
**Warning signs:** `AppRegistryNotReady` or `ImportError` on startup with session-related imports in `main/signals.py`.

### Pitfall 4: MEDIA_URL Not Served in Development After Adding Profile Pictures

**What goes wrong:** Profile picture URL returned by API is a path like `/media/profile_pictures/foo.jpg` but returns 404.
**Why it happens:** Django doesn't serve media in production mode, but even in DEBUG mode it requires the `static()` helper in `urls.py`.
**How to avoid:** `MockIT/urls.py` already has `+ static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)` — this is already in place. No action needed.
**Warning signs:** 404 on `/media/` URLs during tests.

### Pitfall 5: ExaminerCredential Confusion with is_verified on User vs ExaminerProfile

**What goes wrong:** The `User` model ALREADY has an `is_verified` field (email verification). `ExaminerProfile` needs its OWN `is_verified` (IELTS examiner badge status). These are different fields.
**Why it happens:** Developer reuses `user.is_verified` thinking it means "verified examiner."
**How to avoid:** Name the ExaminerProfile field `is_verified` (same name but on a different model). Serializer returns `profile.is_verified` not `user.is_verified`. Document the distinction in admin help_text.
**Warning signs:** Public profile serializer accidentally exposing `user.is_verified` (email status) instead of `profile.is_verified` (badge status).

### Pitfall 6: completed_session_count Updated at Wrong Lifecycle Point

**What goes wrong:** Count incremented in `ReleaseResultView` instead of `EndSessionView`, or vice versa, causing mismatches.
**Why it happens:** Ambiguity between "session ended" vs "result released."
**How to avoid:** `completed_session_count` tracks sessions the examiner has conducted — increment in `EndSessionView.post()` when `session.end()` transitions to COMPLETED. `ScoreHistory` is candidate-facing — append in `ReleaseResultView.post()` when the result is made visible. These are two different integration points.
**Warning signs:** Count includes sessions without scores (if updated at end), or misses sessions where result was never released.

---

## Code Examples

Verified patterns from existing codebase and Django docs:

### Existing Pattern: Error Response Format
```python
# From session/views.py (existing pattern)
return Response({"detail": "Only the examiner can release results."}, status=403)
```

### Existing Pattern: APIView Docstring Convention
```python
class ExaminerProfileMeView(APIView):
    """
    GET  /api/profiles/examiner/me/  — Retrieve own examiner profile (examiner only)
    PATCH /api/profiles/examiner/me/ — Update own examiner profile (examiner only)
    """
```

### Existing Pattern: Role Check
```python
# From session/views.py
def _is_examiner(user):
    return user.role == User.Role.EXAMINER
```

### Profile View Pattern
```python
class ExaminerProfileMeView(APIView):
    """
    GET  /api/profiles/examiner/me/
    PATCH /api/profiles/examiner/me/
    """
    parser_classes = [MultiPartParser, JSONParser]

    def get(self, request):
        if not _is_examiner(request.user):
            return Response({"detail": "Examiner profile not found."}, status=404)
        profile = request.user.examiner_profile
        return Response(ExaminerProfileDetailSerializer(profile).data)

    def patch(self, request):
        if not _is_examiner(request.user):
            return Response({"detail": "Examiner profile not found."}, status=404)
        profile = request.user.examiner_profile
        serializer = ExaminerProfileDetailSerializer(profile, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)
```

### Admin Registration Pattern
```python
# main/admin.py additions
from .models import CandidateProfile, ExaminerCredential, ExaminerProfile, ScoreHistory

@admin.register(ExaminerProfile)
class ExaminerProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "full_legal_name", "is_verified", "completed_session_count")
    list_filter = ("is_verified",)
    readonly_fields = ("completed_session_count",)
    search_fields = ("user__username", "full_legal_name")
    # is_verified is editable inline — admin manages this field
```

---

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Inline profile fields on User model | Separate OneToOne profile models | Django 1.x → modern | Cleaner separation; User model stays focused on auth |
| Custom file storage class | Django ImageField + MEDIA_ROOT | Django 1.4+ | Built-in, no custom code needed |

**Deprecated/outdated:**
- Storing profile data directly on AbstractUser subclass: Works but violates single responsibility; hard to extend per-role.

---

## Open Questions

1. **ExaminerCredential relationship to ExaminerProfile**
   - What we know: Locked as a separate model for IELTS credentials (listening, reading, writing, speaking bands + cert URL)
   - What's unclear: Is it OneToOne (one credential set per examiner) or OneToMany (can have multiple over time)? The CONTEXT.md implies a single credential set ("ExaminerCredential model" singular).
   - Recommendation: Implement as OneToOne. If multiple are needed in future, a new migration can convert it. This matches the simpler "display credentials" use case.

2. **ScoreHistory for guest candidates**
   - What we know: Guest users (is_guest=True) have `role=CANDIDATE` — the `post_save` signal WILL create a `CandidateProfile` for them.
   - What's unclear: Should ghost candidates accumulate score history? They are ephemeral by design.
   - Recommendation: Allow it — the signal creates the profile, and ScoreHistory is appended if the result is released. This is fine since `ScoreHistory` is only readable via authenticated candidate endpoints, which guests won't access after their session ends.

3. **current_speaking_score (STUD-02) vs target_speaking_score (STUD-01)**
   - What we know: STUD-02 says `current_speaking_score` is "initially set manually." STUD-03 (Phase 7) makes it auto-update from completed sessions.
   - What's unclear: Should Phase 4 also expose `current_speaking_score` as a writable field for manual entry?
   - Recommendation: Yes — add `current_speaking_score` as a writable DecimalField(max_digits=2, decimal_places=1) on `CandidateProfile`, same validation as `target_speaking_score`. Phase 7 will later add the auto-update hook.

---

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | Django TestCase (unittest runner) |
| Config file | none — `python manage.py test` |
| Quick run command | `python manage.py test main --keepdb` |
| Full suite command | `python manage.py test --keepdb` |

### Phase Requirements → Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| EXAM-01 | Examiner PATCH updates bio/name/picture | integration | `python manage.py test main.tests.ExaminerProfileTests --keepdb` | Wave 0 |
| EXAM-02 | ExaminerCredential create/update | integration | `python manage.py test main.tests.ExaminerCredentialTests --keepdb` | Wave 0 |
| EXAM-03 | is_verified read-only in API, writable in admin | unit | `python manage.py test main.tests.ExaminerProfileTests --keepdb` | Wave 0 |
| EXAM-04 | Phone validator accepts +998XXXXXXXXX, rejects others | unit | `python manage.py test main.tests.ExaminerProfileTests --keepdb` | Wave 0 |
| EXAM-05 | completed_session_count increments on session end | integration | `python manage.py test main.tests.SessionCountTests --keepdb` | Wave 0 |
| EXAM-06 | Public profile endpoint hides phone field | integration | `python manage.py test main.tests.ExaminerProfilePublicTests --keepdb` | Wave 0 |
| STUD-01 | Candidate PATCH updates target_speaking_score, validates 0.5 steps | integration | `python manage.py test main.tests.CandidateProfileTests --keepdb` | Wave 0 |
| STUD-02 | current_speaking_score writable by candidate | integration | `python manage.py test main.tests.CandidateProfileTests --keepdb` | Wave 0 |
| STUD-04 | ScoreHistory appended on result release | integration | `python manage.py test main.tests.ScoreHistoryTests --keepdb` | Wave 0 |

### Sampling Rate
- **Per task commit:** `python manage.py test main --keepdb`
- **Per wave merge:** `python manage.py test --keepdb`
- **Phase gate:** Full suite green before `/gsd:verify-work`

### Wave 0 Gaps
- [ ] `main/tests.py` — all test classes above (currently boilerplate only)

---

## Sources

### Primary (HIGH confidence)
- Django 5.2 source / official docs — ImageField, post_save signal, F() expressions, OneToOne field
- Direct codebase inspection — `main/models.py`, `session/views.py`, `MockIT/settings.py`, `requirements.txt`

### Secondary (MEDIUM confidence)
- Django docs on signals: https://docs.djangoproject.com/en/5.2/topics/signals/
- Django docs on ImageField: https://docs.djangoproject.com/en/5.2/ref/models/fields/#imagefield

### Tertiary (LOW confidence)
- None

---

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — all libraries are in-project or Django built-ins; Pillow absence confirmed by requirements.txt inspection
- Architecture: HIGH — patterns derived directly from existing codebase conventions
- Pitfalls: HIGH — Pillow and circular import risks are well-documented Django specifics, confirmed against codebase

**Research date:** 2026-03-30
**Valid until:** 2026-06-30 (Django 5.2 LTS patterns are stable)
