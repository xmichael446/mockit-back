# Roadmap: MockIT

## Milestones

- ✅ **v1.0 Initial Platform** - Pre-GSD (shipped before 2026-03-27)
- ✅ **v1.1 Clean-up, Security & Edge Cases** - Phases 1-3 (shipped 2026-03-27)
- ✅ **v1.2 Profiles & Scheduling** - Phases 4-9 (shipped 2026-03-30)
- 🚧 **v1.3 AI Feedback & Assessment** - Phases 10-14 (in progress)

## Phases

<details>
<summary>✅ v1.0 Initial Platform - SHIPPED (Pre-GSD)</summary>

Full IELTS Speaking mock exam platform shipped before GSD tracking began.
Capabilities: User model, token auth, question bank, session lifecycle, WebSocket events, 100ms video, email verification, guest join, IELTS band scoring.

</details>

<details>
<summary>✅ v1.1 Clean-up, Security & Edge Cases (Phases 1-3) - SHIPPED 2026-03-27</summary>

### Phase 1: Security Hardening
**Goal**: All secrets are environment-managed and auth endpoints are rate-limited
**Plans**: 2 plans

Plans:
- [x] 01-01: Move secrets to environment variables
- [x] 01-02: Add rate limiting to auth and invite endpoints

### Phase 2: State Machine & Transactions
**Goal**: Session lifecycle is governed by a validated state machine with atomic operations
**Plans**: 2 plans

Plans:
- [x] 02-01: Implement session state machine and invite token hardening
- [x] 02-02: Wrap session start in transactions and add preset immutability

### Phase 3: Scoring, Audit & Email Error Handling
**Goal**: Scoring requires all criteria, critical actions are audited, email failures are graceful
**Plans**: 2 plans

Plans:
- [x] 03-01: Scoring completeness gate and email error handling
- [x] 03-02: Structured audit logging for critical session actions

</details>

<details>
<summary>✅ v1.2 Profiles & Scheduling (Phases 4-9) - SHIPPED 2026-03-30</summary>

### Phase 4: Profiles
**Goal**: Examiners and candidates can create and view role-specific profiles
**Depends on**: Phase 3 (existing User model and auth)
**Requirements**: EXAM-01, EXAM-02, EXAM-03, EXAM-04, EXAM-05, EXAM-06, STUD-01, STUD-02, STUD-04
**Success Criteria** (what must be TRUE):
  1. Examiner can create and update their profile with bio, full legal name, credentials, phone, and profile picture URL
  2. Examiner profile shows is_verified badge and completed session count (admin-managed)
  3. Candidate can view an examiner's public profile (phone field hidden from public view)
  4. Candidate can create and update their own profile with profile picture URL and target speaking score
  5. Candidate profile exposes band score history derived from all completed sessions
**Plans**: 2 plans

Plans:
- [x] 04-01: Profile models, signals, admin, and Pillow install
- [x] 04-02: Profile serializers, views, URL patterns, and cross-app integration

### Phase 5: Availability Scheduling
**Goal**: Examiners can define recurring weekly availability and candidates can view computed open slots
**Depends on**: Phase 4 (ExaminerProfile must exist for FK reference)
**Requirements**: AVAIL-01, AVAIL-02, AVAIL-03, AVAIL-04, AVAIL-05
**Success Criteria** (what must be TRUE):
  1. Examiner can create, update, and delete recurring 1-hour availability windows by weekday (08:00-22:00)
  2. Examiner can block specific dates as exceptions that override their recurring schedule
  3. Candidate can retrieve computed available slots for an examiner for a given week (schedule minus accepted bookings minus exceptions)
  4. API returns a real-time is_currently_available boolean for an examiner at request time
**Plans**: 2 plans

Plans:
- [x] 05-01: AvailabilitySlot and BlockedDate models + migrations + compute_available_slots() service
- [x] 05-02: Availability CRUD endpoints and available-slots/is-available read endpoints

### Phase 6: Session Request Flow
**Goal**: Candidates can request sessions and examiners can accept or reject them, with accepted requests atomically creating a linked session
**Depends on**: Phase 5 (availability service must exist for slot validation)
**Requirements**: REQ-01, REQ-02, REQ-03, REQ-04, REQ-05, REQ-06, REQ-07
**Success Criteria** (what must be TRUE):
  1. Candidate can submit a session request for a valid time slot (validated against availability) with an optional comment
  2. Examiner can accept a pending request; acceptance atomically creates a linked IELTSMockSession and marks the slot unavailable
  3. Examiner can reject a pending request with a required rejection comment
  4. Candidate or examiner can cancel an accepted session request
  5. Concurrent accept attempts on the same slot are prevented at the database level via select_for_update
**Plans**: 2 plans

Plans:
- [x] 06-01-PLAN.md -- SessionRequest model with state machine, migration, and availability service extension
- [x] 06-02-PLAN.md -- Request submit, accept, reject, cancel endpoints with integration tests

### Phase 7: Candidate Score Auto-Update
**Goal**: A candidate's current speaking score automatically reflects their most recent completed session result
**Depends on**: Phase 4 (CandidateProfile must exist), Phase 6 (booking flow stable, release_result trigger confirmed)
**Requirements**: STUD-03
**Success Criteria** (what must be TRUE):
  1. After an examiner releases session results, the candidate's current_speaking_score updates to the overall band from that session without any manual action
  2. The update fires only on result release, not on intermediate saves, and does not break the existing release flow
**Plans**: 1 plan

Plans:
- [x] 07-01: CandidateProfile.update_speaking_score() method wired into release_result view

### Phase 8: Email Notifications
**Goal**: Examiner receives email on new booking requests; candidate receives email on accept and reject
**Depends on**: Phase 6 (trigger points exist in request flow)
**Requirements**: EMAIL-01, EMAIL-02, EMAIL-03
**Success Criteria** (what must be TRUE):
  1. Examiner receives an email (via Resend) when a candidate submits a new session request
  2. Candidate receives an email when their request is accepted
  3. Candidate receives an email when their request is rejected
  4. Email sends occur after the transaction exits and do not block or roll back the request cycle on Resend failure
**Plans**: 1 plan

Plans:
- [x] 08-01: scheduling/services/email.py notification functions wired at all trigger points

### Phase 9: API Documentation
**Goal**: All v1.2 endpoints are fully documented in docs/api/ and the index is updated
**Depends on**: Phase 8 (all endpoint signatures frozen)
**Requirements**: DOCS-01
**Success Criteria** (what must be TRUE):
  1. docs/api/ contains new domain files covering profiles, availability, and session requests with request/response schemas and error scenarios
  2. docs/api/index.md links to all new domain files
  3. No existing docs/api/ file has had its documented field names, types, or status codes changed (contract audit passes)
**Plans**: 1 plan

Plans:
- [x] 09-01: New docs/api/ domain files for profiles, availability, and requests; index update

</details>

### 🚧 v1.3 AI Feedback & Assessment (In Progress)

**Milestone Goal:** Transcribe session recordings using Whisper and generate per-criterion IELTS scores and actionable feedback via Claude API, delivered asynchronously with monthly usage limits.

#### Phase 10: Data Models & Task Infrastructure
**Goal**: The data layer and background task infrastructure are in place so that all subsequent phases have a stable foundation to build on
**Depends on**: Phase 9 (v1.2 complete, CriterionScore model stable)
**Requirements**: AIAS-01, AIAS-05, BGPR-01, BGPR-02, BGPR-03
**Success Criteria** (what must be TRUE):
  1. CriterionScore has a source field distinguishing EXAMINER vs AI scores, and existing compute_overall_band only aggregates EXAMINER scores
  2. AIFeedbackJob model exists with PENDING/PROCESSING/DONE/FAILED status tracking linked to a session
  3. django-q2 is installed and configured with ORM broker; running qcluster starts the worker without errors
  4. A background task function skeleton exists that django-q2 can enqueue and execute
**Plans**: 2 plans

Plans:
- [x] 10-01-PLAN.md -- ScoreSource enum, CriterionScore.source field, compute_overall_band filter, AIFeedbackJob model
- [x] 10-02-PLAN.md -- django-q2 installation, ORM broker config, run_ai_feedback task skeleton

#### Phase 11: Transcription Service
**Goal**: Examiners can trigger transcription of a completed session's recording and retrieve the resulting transcript
**Depends on**: Phase 10 (AIFeedbackJob model and task infrastructure exist)
**Requirements**: TRNS-01, TRNS-02, TRNS-03, TRNS-04
**Success Criteria** (what must be TRUE):
  1. Triggering AI feedback on a completed session creates an AIFeedbackJob and enqueues a background task
  2. The background task transcribes the session's audio file using faster-whisper (CPU) and stores the transcript on the job record
  3. The transcript incorporates session question context (question text and follow-ups) to improve accuracy
  4. Transcription result is queryable: the stored transcript is associated with the correct session and retrievable
**Plans**: 3 plans

Plans:
- [x] 11-01-PLAN.md -- Install faster-whisper, transcript field migration, settings, transcription service module
- [x] 11-02-PLAN.md -- Task integration with transcribe_session and comprehensive tests
- [x] 11-03-PLAN.md -- Gap closure: HTTP trigger and status endpoint for AI feedback

#### Phase 12: AI Assessment Service
**Goal**: The background job generates IELTS band scores and actionable feedback for all four criteria using Claude API
**Depends on**: Phase 11 (transcript and session question context are produced by the background job)
**Requirements**: AIAS-02, AIAS-03, AIAS-04
**Success Criteria** (what must be TRUE):
  1. The background job calls Claude API with the transcript and actual session questions and receives a structured response
  2. Four CriterionScore records (FC, GRA, LR, PR) are created with source=AI and band scores in the 1-9 range
  3. Each AI criterion score has 3-4 sentences of actionable feedback stored on the score record
  4. AIFeedbackJob status transitions from PROCESSING to DONE on success, or to FAILED with an error message on Claude API error
**Plans**: TBD

Plans:

#### Phase 13: Usage Control
**Goal**: Examiners are subject to a monthly AI feedback limit and receive a clear error when that limit is reached
**Depends on**: Phase 10 (AIFeedbackJob model exists for counting), Phase 11 (trigger point identified)
**Requirements**: UCTL-01, UCTL-02, UCTL-03
**Success Criteria** (what must be TRUE):
  1. Each examiner has a monthly AI feedback generation limit (default: 10); the count resets each calendar month
  2. An examiner who has reached their limit receives a 429 response with a clear error message when attempting to trigger AI feedback
  3. Two concurrent trigger requests from the same examiner cannot both succeed past the limit check (select_for_update prevents race)
**Plans**: TBD

Plans:

#### Phase 14: API Endpoints & Delivery
**Goal**: Examiners and candidates can trigger, monitor, and retrieve AI feedback through REST endpoints and receive real-time notification on completion
**Depends on**: Phase 12 (AI scores written), Phase 13 (usage enforcement at trigger point)
**Requirements**: APID-01, APID-02, APID-03, APID-04, APID-05
**Success Criteria** (what must be TRUE):
  1. POST to the trigger endpoint returns 202 Accepted with a job ID; the session must be in a completed state
  2. GET to the status endpoint returns the current AIFeedbackJob status (PENDING/PROCESSING/DONE/FAILED)
  3. GET to the feedback endpoint returns AI-generated band scores and per-criterion feedback when the job is DONE
  4. When a job completes, a WebSocket event (ai_feedback_ready) is pushed to the session group so connected clients are notified without polling
  5. docs/api/ is updated with request/response schemas and error scenarios for all three new endpoints
**UI hint**: yes
**Plans**: TBD

Plans:

## Progress

**Execution Order:**
Phases execute in numeric order: 10 → 11 → 12 → 13 → 14

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Security Hardening | v1.1 | 2/2 | Complete | 2026-03-27 |
| 2. State Machine & Transactions | v1.1 | 2/2 | Complete | 2026-03-27 |
| 3. Scoring, Audit & Email Errors | v1.1 | 2/2 | Complete | 2026-03-27 |
| 4. Profiles | v1.2 | 2/2 | Complete | 2026-03-30 |
| 5. Availability Scheduling | v1.2 | 2/2 | Complete | 2026-03-30 |
| 6. Session Request Flow | v1.2 | 2/2 | Complete | 2026-03-30 |
| 7. Candidate Score Auto-Update | v1.2 | 1/1 | Complete | 2026-03-30 |
| 8. Email Notifications | v1.2 | 1/1 | Complete | 2026-03-30 |
| 9. API Documentation | v1.2 | 1/1 | Complete | 2026-03-30 |
| 10. Data Models & Task Infrastructure | v1.3 | 2/2 | Complete    | 2026-04-07 |
| 11. Transcription Service | v1.3 | 3/3 | Complete   | 2026-04-08 |
| 12. AI Assessment Service | v1.3 | 0/? | Not started | - |
| 13. Usage Control | v1.3 | 0/? | Not started | - |
| 14. API Endpoints & Delivery | v1.3 | 0/? | Not started | - |
