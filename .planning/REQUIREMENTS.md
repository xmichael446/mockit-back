# Requirements: MockIT

**Defined:** 2026-04-07
**Core Value:** Examiners can conduct a complete, real-time IELTS Speaking mock exam with a candidate -- from invite through scoring -- with minimal friction.

## v1.3 Requirements

Requirements for AI Feedback & Assessment milestone. Each maps to roadmap phases.

### Transcription

- [x] **TRNS-01**: Examiner can trigger transcription of a session recording after the session ends
- [x] **TRNS-02**: System transcribes audio to text using faster-whisper (CPU, configurable model size)
- [x] **TRNS-03**: Transcript is stored and associated with the session for later retrieval
- [x] **TRNS-04**: Transcription incorporates SessionQuestion context for improved accuracy

### AI Assessment

- [x] **AIAS-01**: Source enum added to CriterionScore distinguishing examiner vs AI scores
- [x] **AIAS-02**: AI generates band scores (1-9) for each IELTS criterion (FC, GRA, LR, PR)
- [x] **AIAS-03**: AI generates 3-4 sentence actionable feedback per criterion
- [x] **AIAS-04**: AI prompt includes actual session questions for context-aware assessment
- [x] **AIAS-05**: Existing compute_overall_band filters by examiner source only (no regression)

### Background Processing

- [x] **BGPR-01**: AI feedback job runs asynchronously via django-q2 (ORM broker)
- [x] **BGPR-02**: AIFeedbackJob model tracks job status (PENDING/PROCESSING/DONE/FAILED)
- [x] **BGPR-03**: Transcription and AI generation run as one sequential background job

### Usage Control

- [x] **UCTL-01**: Monthly usage limit per examiner (default: 10 AI feedback generations/month)
- [x] **UCTL-02**: Usage check uses select_for_update + atomic increment to prevent race conditions
- [x] **UCTL-03**: Examiner receives clear error when monthly limit is reached

### API & Delivery

- [ ] **APID-01**: POST endpoint triggers AI feedback generation, returns 202 Accepted
- [ ] **APID-02**: GET endpoint returns AI feedback job status (polling)
- [ ] **APID-03**: GET endpoint retrieves AI-generated scores and feedback
- [ ] **APID-04**: WebSocket push event (ai_feedback_ready) sent on job completion
- [ ] **APID-05**: API docs updated for all new endpoints

## Future Requirements

### Enhanced AI Features

- **EAIF-01**: Candidate can view AI feedback comparison across multiple sessions
- **EAIF-02**: AI generates improvement plan based on score trends
- **EAIF-03**: Configurable monthly limits per examiner tier

### From v1.2 (carried forward)

- **REQ-08**: Candidate can reschedule a pending or accepted session request to a new valid slot
- **EMAIL-05**: Session reminder email wired to async task runner
- **DISC-01**: Examiner specialization tags with filtering
- **DISC-02**: Full search/filter on examiner directory

## Out of Scope

| Feature | Reason |
|---------|--------|
| Real-time transcription during session | High complexity, latency incompatible with CPU Whisper |
| AI feedback without examiner trigger | Wastes credits, removes examiner agency |
| GPU-based transcription | Deployment is CPU-only; faster-whisper handles this |
| Automatic re-scoring of examiner bands | AI is supplementary, not authoritative |
| Celery/Redis task queue | django-q2 with ORM broker covers needs without new infrastructure |
| Overall AI band score | Not requested; per-criterion scores sufficient |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| TRNS-01 | Phase 11 | Complete |
| TRNS-02 | Phase 11 | Complete |
| TRNS-03 | Phase 11 | Complete |
| TRNS-04 | Phase 11 | Complete |
| AIAS-01 | Phase 10 | Complete |
| AIAS-02 | Phase 12 | Complete |
| AIAS-03 | Phase 12 | Complete |
| AIAS-04 | Phase 12 | Complete |
| AIAS-05 | Phase 10 | Complete |
| BGPR-01 | Phase 10 | Complete |
| BGPR-02 | Phase 10 | Complete |
| BGPR-03 | Phase 10 | Complete |
| UCTL-01 | Phase 13 | Complete |
| UCTL-02 | Phase 13 | Complete |
| UCTL-03 | Phase 13 | Complete |
| APID-01 | Phase 14 | Pending |
| APID-02 | Phase 14 | Pending |
| APID-03 | Phase 14 | Pending |
| APID-04 | Phase 14 | Pending |
| APID-05 | Phase 14 | Pending |

**Coverage:**
- v1.3 requirements: 20 total
- Mapped to phases: 20
- Unmapped: 0

---
*Requirements defined: 2026-04-07*
*Last updated: 2026-04-07 after roadmap creation*
