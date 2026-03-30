# Phase 4: Profiles - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Examiner and candidate profile models, CRUD endpoints, and public/private visibility rules. Profiles are OneToOne extensions of the User model in main/. Includes credentials as a separate model, denormalized session count, band score history, and profile pictures stored locally.

</domain>

<decisions>
## Implementation Decisions

### Profile API Design
- Profiles auto-create via `post_save` signal on User creation — zero friction for frontend
- Role-scoped endpoints: `/api/profiles/examiner/me/` and `/api/profiles/candidate/me/` for own profile; `/api/profiles/examiner/<id>/` and `/api/profiles/candidate/<id>/` for public view
- Profile views and serializers live in `main/views.py` and `main/serializers.py` — profiles are extensions of User model already in main/
- GET on own profile returns nested User fields (`user: {id, username, email, first_name, last_name}`) as read-only

### Data Model Details
- Separate `ExaminerCredential` model for IELTS credentials with fields for all bands (listening, reading, writing, speaking) + certificate URL
- Denormalized `completed_session_count` field on ExaminerProfile, updated when sessions complete
- Candidate `target_speaking_score`: DecimalField(max_digits=2, decimal_places=1) with 0.5 step validation (1.0-9.0)
- Profile pictures: ImageField stored in `/media/` directory (no S3) — both ExaminerProfile and CandidateProfile

### Score History & Permissions
- Denormalized `ScoreHistory` model to store band score records per completed session
- Candidate profiles are viewable by examiners (public candidate profiles)
- `is_verified` on ExaminerProfile is admin-managed only (Django admin panel)

### Claude's Discretion
- Admin registration details for new profile models
- Signal implementation specifics for auto-create
- Serializer field ordering and response shape details

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `TimestampedModel` abstract base in `main/models.py` — use for all new profile models
- `main/services/email.py` — Resend API wrapper pattern for future email triggers
- `session/models.py` — `SessionResult` and `CriterionScore` models for score history derivation
- `IELTSMockSession.Status.COMPLETED` — status to filter for completed_session_count

### Established Patterns
- OneToOne relationships: not yet used but standard Django pattern
- DRF APIView classes with docstrings documenting HTTP methods and broadcast events
- Role checks via `_is_examiner(user)` and `_is_candidate(user)` helpers in session/views.py
- Serializer validation via `validate_<field>()` methods
- Error responses: `Response({"detail": "..."}, status=4xx)`

### Integration Points
- `main/urls.py` — add profile endpoint URL patterns
- `main/admin.py` — register ExaminerProfile, CandidateProfile, ExaminerCredential, ScoreHistory
- `session/views.py` — wire `completed_session_count` update on session completion
- User `post_save` signal — auto-create profiles on registration

</code_context>

<specifics>
## Specific Ideas

- ExaminerCredential should have fields for ALL IELTS bands (listening, reading, writing, speaking), not just speaking
- Profile pictures use Django ImageField with local media storage
- ScoreHistory is a denormalized model, not computed from SessionResult on the fly

</specifics>

<deferred>
## Deferred Ideas

None — discussion stayed within phase scope

</deferred>
