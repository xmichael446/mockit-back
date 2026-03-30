# Feature Research

**Domain:** Tutoring/exam marketplace — examiner profiles, student profiles, availability scheduling, session booking, email notifications
**Researched:** 2026-03-30
**Confidence:** HIGH (domain patterns well-established; implementation details grounded in existing codebase)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist. Missing these = product feels incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Examiner profile page | Examiners need public identity; candidates evaluate before booking | LOW | bio, photo URL, credentials text — no file upload needed for v1.2 |
| Verification badge on examiner | Trust signal; expected on any marketplace (Airbnb, TutorFinder, etc.) | LOW | Boolean `is_verified` already exists on User; surface in profile serializer |
| Candidate/student profile | Score history must live somewhere; candidates expect to see their progress | LOW | Computed from existing `SessionResult` records — no new score storage needed |
| Auto-update scores from sessions | Candidates expect their "official" band score to reflect completed sessions | MEDIUM | Query `SessionResult` on candidate's sessions; compute average or store latest |
| Weekly availability schedule (recurring) | Standard for any tutor/examiner booking platform — users expect to set "I'm available Tue/Thu 10:00-12:00" once | MEDIUM | Store slots as day-of-week + hour integer pairs, not datetime rows |
| List available slots for a given week | Candidates need to see when an examiner is free before requesting | MEDIUM | Compute from recurring schedule minus already-booked sessions |
| Session request (candidate initiates) | Core booking flow — candidate picks slot, sends request | MEDIUM | New model: `SessionRequest` with status (PENDING / ACCEPTED / REJECTED) |
| Examiner accept/reject request | Examiner controls their calendar; accept/reject is the standard pattern | LOW | Status transition on `SessionRequest`; ACCEPTED → auto-create `IELTSMockSession` |
| Email: request received (examiner) | Examiner must know a request arrived; they're not always logged in | LOW | Trigger: candidate submits request; recipient: examiner |
| Email: request accepted/rejected (candidate) | Candidate must know the outcome | LOW | Trigger: examiner acts on request; recipient: candidate |
| Email: session reminder | Standard on every booking platform — reduces no-shows | LOW | Trigger: 24h before `scheduled_at`; requires async task runner (Celery or Django-Q) |

### Differentiators (Competitive Advantage)

Features that set the product apart. Not required, but baseline-exceeding.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Real-time available slot calculation | Show live availability accounting for accepted bookings — not just raw schedule | MEDIUM | Query accepted `SessionRequest` rows to subtract from recurring slots at request time |
| Examiner specialization tags | Candidates can filter by examiner focus (Academic, General, test prep level) | LOW | Simple tags/CharField; enhances discoverability significantly |
| Student band history chart data | Candidates see trend over time (API payload only — frontend renders chart) | LOW | Serialize all `SessionResult` records ordered by `created_at` per candidate |
| Examiner session count / experience indicator | Proxy for trust; platforms like Preply surface session count prominently | LOW | Aggregate query on `examiner_sessions` count; no new model needed |
| Phone number on examiner profile | Allows direct contact for coordination outside platform if needed | LOW | Simple CharField on profile; optional |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time calendar sync (Google/Outlook) | Sounds modern and convenient | OAuth complexity, token refresh, webhook management — massive scope for marginal v1.2 gain | Set explicit recurring availability windows instead; sync can be v2+ |
| Payment/billing integration | "Complete marketplace" expectation | Doubles scope; payment flows need PCI compliance, refund logic, dispute handling — separate milestone | Gate behind "contact examiner" or external payment; out of scope for v1.2 |
| Automated session reminder via Celery beat | Reminder emails before session | Requires broker (Redis/Celery) — adds infra not in current stack; InMemoryChannelLayer already flagged for replacement | Stub the email send function; wire up task runner in dedicated infra milestone |
| Profile photo upload (file storage) | Profiles feel more personal with photos | S3/media storage complexity; not blocking for functional booking flow | Accept photo URL (string) in profile; actual upload is v2 |
| Rating/review system | Every marketplace has reviews | Review integrity, moderation, dispute logic; not needed to validate booking flow | Defer entirely; objective band score is already the "review" for IELTS context |
| Public examiner directory with search/filter | Discovery feature | Requires search infrastructure; premature before user base exists | Simple list endpoint with basic filter by name; full search is v2 |

---

## Feature Dependencies

```
[Examiner Profile]
    └──required by──> [List Examiners endpoint]
    └──required by──> [Session Request flow]

[Weekly Availability Schedule]
    └──required by──> [Available Slots calculation]
                          └──required by──> [Session Request — slot selection]

[Session Request model]
    └──required by──> [Accept/Reject flow]
                          └──on ACCEPTED──> [IELTSMockSession creation (existing)]
                          └──triggers──> [Email: request outcome to candidate]
    └──triggers──> [Email: new request to examiner]

[Student Profile]
    └──depends on──> [SessionResult (existing)]
    └──depends on──> [IELTSMockSession.candidate FK (existing)]

[Email notifications]
    └──depends on──> [Resend integration (existing — email_verification.md)]
    └──stub-friendly──> [all trigger points can fire send() calls; async delivery optional]

[Session reminder email]
    └──requires──> [scheduled_at field on IELTSMockSession (existing)]
    └──requires──> [async task runner (NOT in current stack)]
    └──BLOCKED by──> [Celery/Django-Q not installed]
```

### Dependency Notes

- **Session Request requires Availability Schedule:** A request must reference a specific slot; without the schedule model, there is no slot to reference.
- **IELTSMockSession creation depends on Session Request ACCEPTED:** On acceptance the existing session lifecycle begins unchanged — examiner can proceed to invite/start flow.
- **Student Profile depends on existing SessionResult:** No new score storage needed; query existing records filtered by `candidate`.
- **Reminder emails conflict with current stack:** Celery or Django-Q needed to schedule future sends. `scheduled_at` already exists on `IELTSMockSession`. Safe to stub the email function and document the async gap.
- **Examiner Profile is purely additive:** New model extending `User` (OneToOne `ExaminerProfile`) — no existing APIs broken.

---

## MVP Definition

### Launch With (v1.2)

Minimum needed to validate the booking layer on top of the existing session platform.

- [ ] Examiner profile model — bio, credentials, phone, is_verified surfaced, specialization (optional tags or free text)
- [ ] Student profile (read-only) — latest band, session history derived from existing `SessionResult`
- [ ] Weekly availability schedule — store recurring slots (day-of-week + hour), CRUD for examiners
- [ ] Available slots endpoint — compute free windows for a given examiner over next N days
- [ ] Session request model + endpoints — PENDING / ACCEPTED / REJECTED state machine
- [ ] Accept/reject endpoints — examiner action; ACCEPTED auto-creates `IELTSMockSession`
- [ ] Email: request received (examiner) — fire via existing Resend integration
- [ ] Email: request accepted/rejected (candidate) — fire via existing Resend integration
- [ ] Session reminder email — stub only; log intent, document async gap
- [ ] Updated API docs under `docs/api/`

### Add After Validation (v1.x)

- [ ] Reminder emails wired to task runner — add when infra milestone ships Redis + Celery
- [ ] Examiner session count / experience indicator — add when examiner listing surfaces demand
- [ ] Specialization tags with filtering — add when candidate search behavior is observed

### Future Consideration (v2+)

- [ ] Profile photo upload — add when S3/media storage is properly provisioned
- [ ] Rating/review system — add when user base large enough to need trust scaffolding
- [ ] Calendar sync (Google/Outlook) — add if examiners request it at scale
- [ ] Payment integration — separate milestone with dedicated PCI scope

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Examiner profile | HIGH | LOW | P1 |
| Student profile (score history) | HIGH | LOW | P1 |
| Weekly availability schedule CRUD | HIGH | MEDIUM | P1 |
| Available slots calculation | HIGH | MEDIUM | P1 |
| Session request flow | HIGH | MEDIUM | P1 |
| Accept/reject + auto-create session | HIGH | LOW | P1 |
| Email: request received/accepted/rejected | HIGH | LOW | P1 |
| Session reminder (stub) | MEDIUM | LOW | P1 |
| Examiner session count indicator | MEDIUM | LOW | P2 |
| Specialization tags + filter | MEDIUM | LOW | P2 |
| Session reminder (wired to task runner) | HIGH | HIGH | P2 |
| Profile photo upload | LOW | MEDIUM | P3 |
| Rating/review system | MEDIUM | HIGH | P3 |
| Calendar sync | LOW | HIGH | P3 |

**Priority key:**
- P1: Must have for v1.2 launch
- P2: Should have, add when possible in v1.x
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

These platforms represent the established pattern for examiner/tutor booking flows:

| Feature | Preply / iTalki | Calendly-style tools | Our Approach |
|---------|-----------------|----------------------|--------------|
| Tutor profile | Rich: photo, video intro, reviews, rate, languages | N/A | Lean: bio, credentials, is_verified, phone — no photo/video in v1.2 |
| Availability | Recurring weekly + exceptions | Recurring rules + blocked dates | Recurring weekly slots (day+hour), no exceptions in v1.2 |
| Booking initiation | Student initiates, picks slot, instant or pending | Invitee picks from calendar | Candidate requests specific slot, examiner approves (pending model) |
| Accept/reject | Auto-accept (instant book) or pending approval | Auto-accept | Explicit approval — appropriate given IELTS context (examiner evaluates candidate) |
| Email triggers | Confirmation, reminder, cancellation, reschedule | Confirmation + reminder | Confirmation (request received, accepted/rejected) + reminder stub |
| Reschedule/cancel | Present on all platforms | Present | Defer to v1.x — cancellation logic on `SessionRequest` and `IELTSMockSession` |
| Student score history | Not applicable (language learning, not standardized test) | N/A | Unique to MockIT — auto-computed from `SessionResult` records |

---

## Sources

- [How to Build an Online Tutoring Marketplace Platform in 2026 — yo-coach.com](https://www.yo-coach.com/blog/how-to-build-an-online-tutoring-marketplace-platform/)
- [Best Tutoring Center Scheduling Software 2026 — schedulingkit.com](https://schedulingkit.com/scheduling-software/tutoring-centers)
- [Online Booking System for Tutors — Calendesk](https://calendesk.com/online-booking-system-for-tutors)
- [12 Best Online Booking Systems for Tutors in 2026 — Tutorbase](https://tutorbase.com/blog/best-online-booking-systems-for-tutors)
- [Tutor Profile Setup Guide — TutorCruncher Help Center](https://help.tutorcruncher.com/en/articles/10079540-tutor-guide-how-to-set-up-your-tutoring-profile)
- [Verified Credentials for Tutors — tutor.cv](https://tutor.cv/verified-credentials-for-tutors)
- [How to Solve Race Conditions in a Booking System — HackerNoon](https://hackernoon.com/how-to-solve-race-conditions-in-a-booking-system)
- [How to Prevent Double Bookings and Ensure Real-Time Availability — Medium/Vikas Jha](https://medium.com/@get2vikasjha/how-to-prevent-double-bookings-and-ensure-real-time-availability-in-any-scheduling-system-1f311781497f)
- [Set Email Notifications for a Booking — FluentBooking](https://fluentbooking.com/docs/how-to-set-email-notifications-for-a-booking/)
- [Top Transactional Email Services for Developers 2026 — knock.app](https://knock.app/blog/the-top-transactional-email-services-for-developers)
- [The Ultimate 2026 Guide to Automating Meeting Booking Flow — Aurium Research](https://research.aurium.ai/meeting-scheduling/automating-meeting-booking-flow)

---

*Feature research for: MockIT v1.2 — Profiles, Availability Scheduling, Session Booking, Email Notifications*
*Researched: 2026-03-30*
