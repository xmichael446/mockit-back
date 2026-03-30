# Phase 7: Candidate Score Auto-Update - Context

**Gathered:** 2026-03-30
**Status:** Ready for planning

<domain>
## Phase Boundary

Wire CandidateProfile.current_speaking_score auto-update into the existing release_result flow. When an examiner releases session results, the candidate's score updates automatically.

</domain>

<decisions>
## Implementation Decisions

### Claude's Discretion
All implementation choices are at Claude's discretion — pure infrastructure phase. The only constraints are:
- Update fires on result release only, not intermediate saves
- Must not break the existing release flow
- current_speaking_score updates to the overall band from that session

</decisions>

<code_context>
## Existing Code Insights

### Reusable Assets
- `main/models.py` — CandidateProfile with `current_speaking_score` DecimalField
- `session/views.py` — `ReleaseResultView.post()` is the trigger point
- `session/models.py` — `SessionResult.compute_overall_band()` computes the band

### Established Patterns
- ScoreHistory already appended in ReleaseResultView (Phase 4 wiring)
- F() atomic updates used for completed_session_count

### Integration Points
- `session/views.py:ReleaseResultView.post()` — add score update after result save

</code_context>

<specifics>
## Specific Ideas

No specific requirements — infrastructure phase

</specifics>

<deferred>
## Deferred Ideas

None

</deferred>
