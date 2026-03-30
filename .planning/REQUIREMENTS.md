# Requirements: MockIT

**Defined:** 2026-03-30
**Core Value:** Examiners can conduct a complete, real-time IELTS Speaking mock exam with a candidate — from invite through scoring — with minimal friction.

## v1.2 Requirements

Requirements for Profiles & Scheduling milestone. Each maps to roadmap phases.

### Examiner Profile

- [x] **EXAM-01**: User (examiner) can create/update their profile with bio, full legal name, and profile picture URL
- [x] **EXAM-02**: Examiner profile displays IELTS credentials (band scores and certificate URL)
- [x] **EXAM-03**: Examiner profile shows is_verified badge status (admin-managed boolean)
- [x] **EXAM-04**: Examiner profile includes phone number field supporting Uzbekistan format
- [x] **EXAM-05**: Examiner profile displays completed session count
- [x] **EXAM-06**: User (candidate) can view an examiner's public profile

### Student Profile

- [x] **STUD-01**: User (candidate) can create/update their profile with profile picture URL and target speaking score
- [x] **STUD-02**: Student profile stores current_speaking_score (initially set manually)
- [ ] **STUD-03**: current_speaking_score auto-updates to latest session result score when a session is completed
- [x] **STUD-04**: Student profile exposes band score history data from all completed sessions

### Availability Scheduling

- [x] **AVAIL-01**: Examiner can define weekly recurring availability as 1-hour windows (08:00-22:00) per day of week
- [ ] **AVAIL-02**: Examiner can update/delete their recurring availability slots
- [x] **AVAIL-03**: API returns computed available slots for an examiner (recurring schedule minus booked sessions)
- [x] **AVAIL-04**: API returns is_currently_available boolean for an examiner at request time
- [x] **AVAIL-05**: Examiner can block specific dates as exceptions to their recurring schedule

### Session Request

- [ ] **REQ-01**: Candidate can submit a session request for a specific valid time slot with optional comment
- [ ] **REQ-02**: Requested time is strictly validated against examiner's actual availability (schedule minus bookings minus exceptions)
- [ ] **REQ-03**: Examiner can accept a pending request (auto-creates linked IELTSMockSession)
- [ ] **REQ-04**: Examiner can reject a pending request with required rejection comment
- [ ] **REQ-05**: Session request uses state machine pattern (PENDING -> ACCEPTED/REJECTED/CANCELLED)
- [ ] **REQ-06**: Accept flow uses select_for_update to prevent double-booking race conditions
- [ ] **REQ-07**: Candidate or examiner can cancel an accepted session request

### Email Notifications

- [ ] **EMAIL-01**: Examiner receives email when a new session request is created (stubbed via Resend pattern)
- [ ] **EMAIL-02**: Candidate receives email when their request is accepted (stubbed)
- [ ] **EMAIL-03**: Candidate receives email when their request is rejected (stubbed)

### API Documentation

- [ ] **DOCS-01**: All new endpoints documented in docs/api/ with request/response schemas and error scenarios

## Future Requirements

Deferred to future release. Tracked but not in current roadmap.

### Session Request

- **REQ-08**: Candidate can reschedule a pending or accepted session request to a new valid slot — deferred to keep v1.2 lean; cancel + rebook achieves same result

### Email Notifications

- **EMAIL-05**: Session reminder email wired to async task runner — requires Redis + Celery infrastructure milestone

### Examiner Discovery

- **DISC-01**: Examiner specialization tags with filtering
- **DISC-02**: Full search/filter on examiner directory

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Session reminder email (async) | No async task runner in current stack; requires Celery/Redis infra milestone |
| Profile photo upload (file storage) | Accept URL string only; S3/media storage complexity deferred |
| Rating/review system | Band scores serve as objective assessment; review system premature before user base |
| Calendar sync (Google/Outlook) | OAuth complexity; recurring weekly schedule is sufficient for v1.2 |
| Payment/billing integration | Separate milestone with PCI compliance scope |
| SMS verification for phone | Database field only; SMS verification logic deferred |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| EXAM-01 | Phase 4 | Complete |
| EXAM-02 | Phase 4 | Complete |
| EXAM-03 | Phase 4 | Complete |
| EXAM-04 | Phase 4 | Complete |
| EXAM-05 | Phase 4 | Complete |
| EXAM-06 | Phase 4 | Complete |
| STUD-01 | Phase 4 | Complete |
| STUD-02 | Phase 4 | Complete |
| STUD-03 | Phase 7 | Pending |
| STUD-04 | Phase 4 | Complete |
| AVAIL-01 | Phase 5 | Complete |
| AVAIL-02 | Phase 5 | Pending |
| AVAIL-03 | Phase 5 | Complete |
| AVAIL-04 | Phase 5 | Complete |
| AVAIL-05 | Phase 5 | Complete |
| REQ-01 | Phase 6 | Pending |
| REQ-02 | Phase 6 | Pending |
| REQ-03 | Phase 6 | Pending |
| REQ-04 | Phase 6 | Pending |
| REQ-05 | Phase 6 | Pending |
| REQ-06 | Phase 6 | Pending |
| REQ-07 | Phase 6 | Pending |
| EMAIL-01 | Phase 8 | Pending |
| EMAIL-02 | Phase 8 | Pending |
| EMAIL-03 | Phase 8 | Pending |
| DOCS-01 | Phase 9 | Pending |

**Coverage:**
- v1.2 requirements: 26 total
- Mapped to phases: 26
- Unmapped: 0 ✓

---
*Requirements defined: 2026-03-30*
*Last updated: 2026-03-30 after roadmap creation (all 26 requirements mapped)*
