# Roadmap: MockIT

## Milestones

- ✅ **v1.0 Initial Platform** - Pre-GSD (shipped before 2026-03-27)
- ✅ **v1.1 Clean-up, Security & Edge Cases** - Phases 1-3 (shipped 2026-03-27)
- 🚧 **v1.2 Profiles & Scheduling** - Phases 4-9 (in progress)

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

### 🚧 v1.2 Profiles & Scheduling (In Progress)

**Milestone Goal:** Examiners and candidates have profiles, examiners can define weekly availability, and candidates can book sessions through a request flow backed by a state machine.

#### Phase 4: Profiles
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

#### Phase 5: Availability Scheduling
**Goal**: Examiners can define recurring weekly availability and candidates can view computed open slots
**Depends on**: Phase 4 (ExaminerProfile must exist for FK reference)
**Requirements**: AVAIL-01, AVAIL-02, AVAIL-03, AVAIL-04, AVAIL-05
**Success Criteria** (what must be TRUE):
  1. Examiner can create, update, and delete recurring 1-hour availability windows by weekday (08:00-22:00)
  2. Examiner can block specific dates as exceptions that override their recurring schedule
  3. Candidate can retrieve computed available slots for an examiner for a given week (schedule minus accepted bookings minus exceptions)
  4. API returns a real-time is_currently_available boolean for an examiner at request time
**Plans**: TBD

Plans:
- [ ] 05-01: AvailabilitySlot and BlockedDate models + migrations + compute_available_slots() service
- [ ] 05-02: Availability CRUD endpoints and available-slots/is-available read endpoints

#### Phase 6: Session Request Flow
**Goal**: Candidates can request sessions and examiners can accept or reject them, with accepted requests atomically creating a linked session
**Depends on**: Phase 5 (availability service must exist for slot validation)
**Requirements**: REQ-01, REQ-02, REQ-03, REQ-04, REQ-05, REQ-06, REQ-07
**Success Criteria** (what must be TRUE):
  1. Candidate can submit a session request for a valid time slot (validated against availability) with an optional comment
  2. Examiner can accept a pending request; acceptance atomically creates a linked IELTSMockSession and marks the slot unavailable
  3. Examiner can reject a pending request with a required rejection comment
  4. Candidate or examiner can cancel an accepted session request
  5. Concurrent accept attempts on the same slot are prevented at the database level via select_for_update
**Plans**: TBD

Plans:
- [ ] 06-01: SessionRequest model with state machine + migrations
- [ ] 06-02: Request submit, accept, reject, cancel endpoints with role-based permissions

#### Phase 7: Candidate Score Auto-Update
**Goal**: A candidate's current speaking score automatically reflects their most recent completed session result
**Depends on**: Phase 4 (CandidateProfile must exist), Phase 6 (booking flow stable, release_result trigger confirmed)
**Requirements**: STUD-03
**Success Criteria** (what must be TRUE):
  1. After an examiner releases session results, the candidate's current_speaking_score updates to the overall band from that session without any manual action
  2. The update fires only on result release, not on intermediate saves, and does not break the existing release flow
**Plans**: TBD

Plans:
- [ ] 07-01: CandidateProfile.update_speaking_score() method wired into release_result view

#### Phase 8: Email Notifications
**Goal**: Examiner receives email on new booking requests; candidate receives email on accept and reject
**Depends on**: Phase 6 (trigger points exist in request flow)
**Requirements**: EMAIL-01, EMAIL-02, EMAIL-03
**Success Criteria** (what must be TRUE):
  1. Examiner receives an email (via Resend) when a candidate submits a new session request
  2. Candidate receives an email when their request is accepted
  3. Candidate receives an email when their request is rejected
  4. Email sends occur after the transaction exits and do not block or roll back the request cycle on Resend failure
**Plans**: TBD

Plans:
- [ ] 08-01: scheduling/services/email.py notification functions wired at all trigger points

#### Phase 9: API Documentation
**Goal**: All v1.2 endpoints are fully documented in docs/api/ and the index is updated
**Depends on**: Phase 8 (all endpoint signatures frozen)
**Requirements**: DOCS-01
**Success Criteria** (what must be TRUE):
  1. docs/api/ contains new domain files covering profiles, availability, and session requests with request/response schemas and error scenarios
  2. docs/api/index.md links to all new domain files
  3. No existing docs/api/ file has had its documented field names, types, or status codes changed (contract audit passes)
**Plans**: TBD

Plans:
- [ ] 09-01: New docs/api/ domain files for profiles, availability, and requests; index update

## Progress

**Execution Order:**
Phases execute in numeric order: 4 → 5 → 6 → 7 → 8 → 9

| Phase | Milestone | Plans Complete | Status | Completed |
|-------|-----------|----------------|--------|-----------|
| 1. Security Hardening | v1.1 | 2/2 | Complete | 2026-03-27 |
| 2. State Machine & Transactions | v1.1 | 2/2 | Complete | 2026-03-27 |
| 3. Scoring, Audit & Email Errors | v1.1 | 2/2 | Complete | 2026-03-27 |
| 4. Profiles | v1.2 | 2/2 | Complete   | 2026-03-30 |
| 5. Availability Scheduling | v1.2 | 0/2 | Not started | - |
| 6. Session Request Flow | v1.2 | 0/2 | Not started | - |
| 7. Candidate Score Auto-Update | v1.2 | 0/1 | Not started | - |
| 8. Email Notifications | v1.2 | 0/1 | Not started | - |
| 9. API Documentation | v1.2 | 0/1 | Not started | - |
