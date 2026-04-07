# Phase 10: Data Models & Task Infrastructure - Context

**Gathered:** 2026-04-07
**Status:** Ready for planning
**Mode:** Auto-generated (infrastructure phase — discuss skipped)

<domain>
## Phase Boundary

The data layer and background task infrastructure are in place so that all subsequent phases have a stable foundation to build on.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. Use ROADMAP phase goal, success criteria, and codebase conventions to guide decisions.

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `CriterionScore` model in `session/models.py:276` — needs `source` field addition
- `SessionResult.compute_overall_band()` in `session/models.py:266` — needs EXAMINER-only filter
- `unique_together` on CriterionScore is `("session_result", "criterion")` — must include `source`
- `SessionRecording` model exists at `session/models.py:289` with `audio_file = FileField(upload_to="recordings/")`
- `TimestampedModel` base class used across session models

### Established Patterns
- Models live in their respective app's `models.py`
- Django signals used for cross-model updates (e.g., score auto-update)
- `session/` app handles full session lifecycle
- `DJANGO_SETTINGS_MODULE=MockIT.settings_test` for tests (SQLite in-memory)

### Integration Points
- `CriterionScore` changes affect `SessionResult.compute_overall_band()` and serializers
- `AIFeedbackJob` will link to `IELTSMockSession` (FK)
- django-q2 config goes in `MockIT/settings.py`
- Background task skeleton in new module under `session/`

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase. Refer to ROADMAP phase description and success criteria.

</specifics>

<deferred>
## Deferred Ideas

None — infrastructure phase.

</deferred>
