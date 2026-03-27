# Requirements: MockIT

**Defined:** 2026-03-27
**Core Value:** Examiners can conduct a complete, real-time IELTS Speaking mock exam with a candidate -- from invite through scoring -- with minimal friction.

## v1.1 Requirements

Requirements for milestone v1.1: Clean-up, Security & Edge Cases.

### Security

- [x] **SEC-01**: All secrets (SECRET_KEY, HMS keys, RESEND key, DB credentials) loaded from .env file
- [x] **SEC-02**: Rate limiting applied to registration, guest-join, and invite-accept endpoints

### Refactoring

- [x] **REF-01**: Session status checks extracted into model methods (can_start, can_end, can_ask_question, etc.)
- [ ] **REF-02**: Audit logging added for session creation, start, end, scoring, and result release
- [x] **REF-03**: Invite token uses letter-only format like Google Meet (e.g. xyz-abcd)

### Edge Cases

- [x] **EDGE-01**: Multi-step operations wrapped in transaction.atomic() (session start, scoring)
- [x] **EDGE-02**: Result release requires all 4 criterion scores to exist
- [x] **EDGE-03**: Email delivery failures caught and handled gracefully (no silent failures)
- [x] **EDGE-04**: Preset cannot be modified after a session has been created from it

## Future Requirements

### Security (Deferred)

- **SEC-03**: DEBUG flag controlled by environment variable
- **SEC-04**: CORS restricted to allowed origins only
- **SEC-05**: WebSocket authentication via header instead of query param

### Testing

- **TEST-01**: Integration tests for session lifecycle (create -> score -> release)
- **TEST-02**: Permission tests (examiner-only, candidate-only, participant checks)
- **TEST-03**: WebSocket connection auth and event broadcast tests
- **TEST-04**: Scoring calculation and constraint validation tests

## Out of Scope

| Feature | Reason |
|---------|--------|
| Full test suite | Deferred to dedicated testing milestone |
| Redis channel layer | Infrastructure change, separate milestone |
| OAuth/social login | Email/password sufficient for now |
| Mobile app | Web-first platform |
| WebSocket header auth | Breaking frontend change, requires coordination |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| SEC-01 | Phase 1 | Complete |
| SEC-02 | Phase 1 | Complete |
| REF-01 | Phase 2 | Complete |
| REF-03 | Phase 2 | Complete |
| EDGE-01 | Phase 2 | Complete |
| EDGE-04 | Phase 2 | Complete |
| REF-02 | Phase 3 | Pending |
| EDGE-02 | Phase 3 | Complete |
| EDGE-03 | Phase 3 | Complete |

**Coverage:**
- v1.1 requirements: 9 total
- Mapped to phases: 9
- Unmapped: 0

---
*Requirements defined: 2026-03-27*
*Last updated: 2026-03-27 after roadmap creation*
