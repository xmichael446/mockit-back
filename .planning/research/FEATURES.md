# Feature Research

**Domain:** AI-powered IELTS Speaking feedback (milestone add-on to existing exam platform)
**Researched:** 2026-04-07
**Confidence:** HIGH (existing codebase well-understood; AI feedback patterns from live competitor analysis)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features users assume exist when "AI feedback" is advertised. Missing these makes the feature feel broken or incomplete.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Transcription of session audio | AI cannot assess what it cannot read; transcript is the foundation for all other features | MEDIUM | `SessionRecording.audio_file` (webm) already stored — Whisper reads it directly |
| Per-criterion AI band score (FC, GRA, LR, PR, bands 1–9) | Users compare AI vs examiner at criterion level, not just overall | LOW | Reuses existing `SpeakingCriterion` choices; needs source field on `CriterionScore` |
| Per-criterion AI text feedback (3–4 sentences) | Scores without explanation are useless; industry standard is criterion-aligned narrative | LOW | Mirrors existing `CriterionScore.feedback` field; AI fills the same shape |
| Source distinction on scores (examiner vs AI) | Candidate must know which score came from a human and which from AI; trust depends on it | LOW | Add `source` enum to `CriterionScore`; existing examiner scores become source=EXAMINER |
| AI overall band (computed from 4 AI criteria) | Consistent with how examiner overall band is computed; candidate expects one number | LOW | Reuse `SessionResult.compute_overall_band()` logic on AI criterion bands |
| Async processing with status tracking | Transcription + AI inference takes 30–120 seconds; synchronous response will time out | MEDIUM | Status model with PENDING / PROCESSING / DONE / FAILED states; frontend polls |
| Trigger endpoint (POST) | Examiner initiates AI analysis explicitly after session ends | LOW | POST to trigger; gated on recording exists, session COMPLETED, usage limit not exceeded |
| Status endpoint (GET) | Frontend polls until processing is complete or failed | LOW | Returns `{status, ...}` — simple polling pattern |
| Retrieve AI feedback endpoint (GET) | Fetch completed AI scores and feedback once status=DONE | LOW | Returns same shape as existing result GET, scoped to source=AI |

### Differentiators (Competitive Advantage)

Features that set MockIT apart from standalone AI IELTS tools (SmallTalk2Me, Lingo Copilot, cathoven.com) — because those tools have no human examiner baseline to compare against.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Side-by-side examiner vs AI scores | No standalone AI tool can do this — MockIT has real human scores to compare | LOW | Display layer only; backend just needs source=EXAMINER / source=AI on same result |
| Monthly usage cap per examiner (default 10/month) | Prevents cost overruns on Claude API; creates scarcity that signals premium value | LOW | Counter on ExaminerProfile or separate UsageRecord; checked at trigger time |
| Transcript stored and surfaced to candidate | Candidate reads exactly what they said — valuable for self-review; no standalone tool ties transcript to a real exam session | LOW | Store transcript text on a new `SessionTranscript` model; return via AI feedback or recording endpoint |
| Question-level context in AI prompt | AI receives the actual questions asked (from `SessionQuestion` records) alongside the transcript — improves accuracy vs raw transcript alone | MEDIUM | Enrich prompt with question text + answer segments using existing recording timecodes |
| Explicit "AI score is advisory" labeling | Builds trust by being honest about AI limitations (correlation 0.70–0.85 with real scores); distinguishes MockIT as professional | LOW | API response field + frontend display pattern; no backend complexity |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Automatic AI analysis on session end | Seems convenient — no extra click | Wastes API credits for sessions the examiner decides not to analyse; removes examiner agency; candidates may receive AI feedback before examiner has scored | Keep explicit trigger; examiner decides when AI analysis is worth running |
| Real-time AI feedback during the session | Would feel futuristic | Requires streaming audio pipeline, WebSocket integration, sub-2s latency — a separate engineering project; distracts from the live exam UX | Post-session batch analysis only |
| AI replacing examiner scores on result release | Could simplify workflow | IELTS is high-stakes; AI scores have 0.70–0.85 correlation with real scores — not reliable enough to replace a trained examiner; legal and trust risk | AI scores are additive context, never the primary score |
| Whisper run locally on the server | Avoids API cost, no data leaves server | Whisper large-v3 requires 6–10 GB GPU RAM; current deployment is almost certainly CPU-only; local inference would block the process for minutes per file and fail under any concurrency | Use OpenAI Whisper API ($0.006/min); cost for a 15-min IELTS session is ~$0.09 — trivial at this scale |
| Per-question granular AI scores | More detail sounds better | IELTS criteria are assessed holistically across the full exam; per-question scores misalign with official band descriptors and could mislead candidates | One AI score set per session, same as examiner |
| Streaming AI response to frontend via WebSocket | Would feel faster | Adds WebSocket event complexity for a one-time analysis job; polling is simpler and sufficient given 30–120s processing time | Simple status polling: PENDING → PROCESSING → DONE / FAILED |

---

## Feature Dependencies

```
SessionRecording (already exists)
    └──required by──> Transcription Job
                          └──required by──> AI Feedback Generation (Claude API)
                                                └──required by──> AI CriterionScores
                                                                      └──required by──> AI Overall Band

Monthly Usage Counter
    └──gates──> Transcription Job trigger (429 if limit reached)

Session COMPLETED status
    └──required by──> Transcription Job trigger (cannot run on in-progress sessions)

Existing CriterionScore model
    └──extended by──> source enum (EXAMINER / AI)

SessionQuestion + recording timecodes (already exists via recording API)
    └──enhances──> AI Feedback Generation (richer prompt context)
```

### Dependency Notes

- **Transcription requires SessionRecording:** No recording file means nothing to transcribe. Trigger endpoint must 404 (or 400) if `session.recording` does not exist.
- **AI feedback requires transcription:** Claude API receives the transcript as input. Transcription and AI generation must be sequential steps in the same background job, not separately triggerable jobs.
- **source enum extends CriterionScore:** One new integer field. Existing examiner scores default to `source=EXAMINER`. All existing queries unaffected if filtered by source.
- **Monthly counter gates the trigger:** Checked synchronously before enqueuing the background job. Return 429 with reset date if limit reached.
- **COMPLETED status gates the trigger:** Mirrors the examiner scoring requirement; AI analysis only makes sense after the session is fully over.

---

## MVP Definition

This is a milestone add-on. MVP means: minimum to ship AI feedback as a useful, trustworthy addition without breaking existing examiner/candidate flows.

### Launch With (v1.3)

- [ ] `source` field on `CriterionScore` — backbone of examiner vs AI distinction; existing scores get EXAMINER
- [ ] `SessionTranscript` model — stores Whisper output text; linked OneToOne to session
- [ ] `AIFeedbackJob` model — tracks async job status (PENDING, PROCESSING, DONE, FAILED) with error message field
- [ ] `POST /api/sessions/<id>/ai-feedback/` — trigger endpoint; checks recording exists, session COMPLETED, usage limit; enqueues job
- [ ] `GET /api/sessions/<id>/ai-feedback/` — status + result endpoint; returns job status and AI CriterionScores when DONE
- [ ] Background job: Whisper API transcription → Claude API feedback → write AI CriterionScores + SessionTranscript
- [ ] Monthly usage counter per examiner (model field or count query on AIFeedbackJob)
- [ ] Claude prompt with IELTS band descriptors + question context (from SessionQuestion records) + transcript

### Add After Validation (v1.3.x)

- [ ] Transcript surfaced in GET recording response — once confirmed candidates want to read it
- [ ] Usage stats endpoint (how many AI analyses used this month, reset date) — once examiners ask
- [ ] Retry mechanism for failed jobs — once failure rate is measured in production

### Future Consideration (v2+)

- [ ] AI feedback broken out per IELTS Part (Part 1 / 2 / 3) — once holistic feedback validated as useful
- [ ] Configurable usage limits per examiner tier — once pricing tiers exist
- [ ] Phoneme-level pronunciation detail — requires dedicated speech analysis beyond Whisper + Claude

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| source enum on CriterionScore | HIGH | LOW | P1 |
| SessionTranscript model | HIGH | LOW | P1 |
| AIFeedbackJob model + status tracking | HIGH | MEDIUM | P1 |
| Transcription via Whisper API | HIGH | MEDIUM | P1 |
| AI feedback generation via Claude API | HIGH | MEDIUM | P1 |
| Trigger endpoint (POST) | HIGH | LOW | P1 |
| Status + result endpoint (GET) | HIGH | LOW | P1 |
| Monthly usage limit | HIGH | LOW | P1 |
| Question context in AI prompt | MEDIUM | MEDIUM | P2 |
| Transcript in recording/AI response | MEDIUM | LOW | P2 |
| Usage stats endpoint | LOW | LOW | P3 |
| Retry mechanism for failed jobs | MEDIUM | MEDIUM | P2 |

**Priority key:**
- P1: Must have for v1.3 launch
- P2: Should have, add when possible in v1.3.x
- P3: Nice to have, future consideration

---

## Competitor Feature Analysis

| Feature | SmallTalk2Me / Lingo Copilot / cathoven | MockIT v1.3 Approach |
|---------|----------------------------------------|----------------------|
| Transcription | Built-in, real-time or post-session | Post-session via Whisper API, triggered explicitly by examiner |
| Per-criterion feedback | Yes — FC, GRA, LR, PR aligned to IELTS band descriptors | Yes — same 4 criteria, same 1–9 bands, same descriptor alignment |
| Human vs AI comparison | No — AI is the only scorer | Yes — unique advantage; examiner scored first, AI is additive |
| Usage limits | Subscription paywalls | Monthly cap per examiner (default 10); cheaper and simpler than subscription tiers |
| Async processing | Varies; some instant (lower quality models) | PENDING → PROCESSING → DONE / FAILED polling |
| Score reliability disclosure | Rarely explicit | Explicit source enum; "advisory" framing enforced at API level |
| Question context in assessment | No (assesses raw audio without knowing what questions were asked) | Yes — SessionQuestion records enriched into Claude prompt |

---

## Sources

- [Can AI Give Accurate IELTS Speaking Scores? — Lingo Copilot](https://speaking.lingo-copilot.com/blog/can-ai-give-accurate-ielts-speaking-scores)
- [IELTS Speaking Practice with AI — TalkNative](https://www.talknative.io/blog/ielts-speaking-practice-with-ai)
- [AI IELTS Speaking Practice App: Complete Guide 2026 — Migration Vis Portal](https://www.migrationvisportal.com/2025/10/ai-ielts-speaking-practice-app-complete-guide-2025.html?m=1)
- [OpenAI Whisper API vs Local vs Server-Side — AssemblyAI](https://www.assemblyai.com/blog/openai-whisper-developers-choosing-api-local-server-side-transcription)
- [Cheapest Audio Transcription APIs 2025 — DEV Community](https://dev.to/fredpsantos33/cheapest-audio-transcription-apis-in-2025-whisper-via-api-vs-assemblyai-vs-deepgram-2f2a)
- [Django Background Tasks Without Celery 2025 — Medium](https://medium.com/@joyichiro/django-background-tasks-without-celery-lightweight-alternatives-for-2025-22c5940e6928)
- [Django Channels Worker System — official docs](https://channels.readthedocs.io/en/stable/topics/worker.html)
- [AI's effectiveness in language testing — ScienceDirect](https://www.sciencedirect.com/article/pii/S2590291125006205)
- Existing codebase: `session/models.py`, `docs/api/recording.md`, `docs/api/results.md`

---

*Feature research for: MockIT v1.3 — AI Feedback & Assessment milestone*
*Researched: 2026-04-07*
