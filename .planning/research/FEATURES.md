# Feature Research

**Domain:** Audio-based IELTS Speaking assessment via Gemini Pro (milestone rebuild of existing AI pipeline)
**Researched:** 2026-04-09
**Confidence:** HIGH for Gemini audio API mechanics; MEDIUM for pronunciation scoring reliability (hallucination risk confirmed but not fully quantified for IELTS band tasks)

---

## Feature Landscape

### Table Stakes (Users Expect These)

Features that must work for the Gemini audio assessment rebuild to be a credible replacement for the existing faster-whisper + Claude pipeline. "Table stakes" here means: if these don't work, the feature is broken or worse than what it replaces.

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| Direct audio input to Gemini (no separate transcription step) | The entire point of replacing the pipeline is to give Gemini raw audio instead of pre-transcribed text; without this, the rebuild has no purpose | LOW | Gemini supports WAV/MP3/AIFF/AAC/OGG/FLAC as inline data (up to 100 MB) or Files API (up to 2 GB). SessionRecording stores `.webm` — must convert to a supported format first. |
| Pronunciation scoring from audio | PR is 25% of the IELTS speaking band; the v1.3 pipeline could not assess PR from transcript text; this is the primary motivation for the rebuild | MEDIUM | Confirmed possible: Gemini can detect stress, intonation, rhythm, and accent intelligibility from audio. However, Gemini's audio is downsampled to 16 Kbps — sufficient for speech intelligibility but reduces fine-grained phoneme analysis. Hallucination risk on precise scores exists; must be mitigated via explicit rubric in system prompt. |
| Transcription as a byproduct of audio assessment | Candidates and examiners expect to read what was said; transcript validates that Gemini heard the audio correctly | LOW | Gemini can simultaneously transcribe and assess in a single API call with a structured output schema. No separate transcription step needed — direct cost and latency saving vs. v1.3 which ran Whisper separately. |
| Per-criterion structured output (FC, GRA, LR, PR, bands 1–9 + feedback) | AI feedback is useless without criterion breakdown; must match the shape of existing `CriterionScore` records | LOW | Gemini `response_schema` with Pydantic `BaseModel` guarantees JSON conforming to a defined schema. Use `response_mime_type="application/json"` with `Mode.JSON` (not function calling — function calling does not work with multimodal inputs per Instructor docs). |
| Maintain existing API contract (POST trigger, GET status/scores, WebSocket push) | Frontend depends on this contract; breaking it requires frontend coordination that is out of scope | LOW | The AIFeedbackJob model, trigger endpoint, status endpoint, and WebSocket events are all unchanged. Only the internal job task changes (Gemini replaces faster-whisper + Claude). |
| Remove faster-whisper and anthropic SDK dependencies | Declared requirement in PROJECT.md; simplifies the dependency surface and eliminates the Whisper transcription subprocess | LOW | `requirements.txt` change: remove `faster-whisper`, `anthropic`; add `google-genai` (the new unified Google Gen AI Python SDK). Note: `google-generativeai` is now deprecated in favor of `google-genai`. |
| Files API upload for audio > 100 MB | Session recordings for a full 15-minute IELTS exam in webm can easily exceed inline data limits | MEDIUM | Use `client.files.upload()` before calling `generate_content`. Files are auto-deleted after 48 hours — no manual cleanup required for the assessment use case. Must poll `files.get()` until status = ACTIVE before calling generate_content. |
| Explicit IELTS band descriptor rubric in system prompt | Without a rubric, Gemini invents a scoring system or anchors to a vague notion of "good English"; band-aligned rubric is what makes scores meaningful and consistent | MEDIUM | System prompt must include the official IELTS band descriptors for each criterion (especially PR descriptors for Band 5–8 range which is where candidates cluster). Research confirms including rubric in prompt significantly improves consistency. |

### Differentiators (Competitive Advantage)

Features that the Gemini audio approach enables which the v1.3 faster-whisper + Claude pipeline could not deliver, or which become simpler/better with a unified audio model.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| Native Pronunciation (PR) criterion scoring | v1.3 assessed PR from transcript text — structurally impossible because text cannot capture stress, intonation, or accent clarity; Gemini from audio is the first time PR is genuinely assessed | MEDIUM | System prompt must explicitly instruct assessment of: segmental accuracy (individual sounds), suprasegmental features (stress, rhythm, intonation), and intelligibility. Gemini's 16 Kbps downsampled audio is adequate for these features. Low confidence on precise band differentiation (e.g., Band 6 vs Band 7 PR) — frame output as advisory. |
| Simultaneous transcription + assessment (single API call) | v1.3 ran Whisper first (network + CPU), then Claude second (network); two sequential API calls with separate latency and failure modes; Gemini does both in one call | LOW | Include `transcript` field in `response_schema` alongside criterion scores. This eliminates the `SessionTranscript` creation step as a separate operation — it becomes a field in the assessment result. |
| Intonation and rhythm observation in FC/PR feedback | Fluency and Coherence also benefits from prosodic observation — does the speaker pause naturally, use discourse markers with appropriate intonation, vary pace? Text-based Claude could not see this. | LOW | No special implementation needed — instruct Gemini to consider these features in the system prompt for FC and PR. The model observes them natively from audio. |
| Simpler background job (one task, one API) | v1.3 background task had two phases: transcription task and assessment task; Gemini collapses both into a single `generate_content` call with audio input | LOW | The `run_ai_feedback` django-q2 task becomes simpler: upload audio → call Gemini → parse structured output → write scores. Fewer failure modes, fewer task states needed. |
| Elimination of Whisper model size configuration | v1.3 required tuning `WHISPER_MODEL_SIZE` (tiny/base/medium/large-v3) and balancing accuracy vs. memory; Gemini has no such tuning burden | LOW | Remove the `WHISPER_MODEL_SIZE` setting. The Gemini model choice (2.5 Flash recommended — see STACK.md) is the only lever. |

### Anti-Features (Commonly Requested, Often Problematic)

| Feature | Why Requested | Why Problematic | Alternative |
|---------|---------------|-----------------|-------------|
| Real-time pronunciation feedback during session | Would feel premium; candidates could self-correct on the fly | Requires Live API (streaming audio), which is a separate product from the batch audio API; adds WebSocket complexity during an already-complex live session; Gemini Live API is in preview with known hallucination issues during non-blocking tool calls | Keep post-session batch analysis only; the live exam UX should not be disrupted |
| Phoneme-level pronunciation detail in scores | Sounds more precise and scientific | Gemini audio is downsampled to 16 Kbps mono; phoneme-level precision at this resolution is unreliable; LLM-based phoneme analysis requires weighted scoring pipelines (WAS + PMS + SS) that go beyond a single generate_content call; false precision misleads candidates | Band-level PR score (1–9) with qualitative feedback on intelligibility and specific features observed (e.g., "word stress on polysyllabic words needs attention") — this is exactly what IELTS examiners provide |
| Separate transcription endpoint (Gemini as Whisper replacement only) | Could use Gemini just for transcription and keep Claude for assessment | Defeats the purpose of the rebuild; adds complexity without delivering the pronunciation assessment benefit; still requires two API calls | Single-shot: Gemini receives audio, returns transcript + all 4 criterion scores in one structured response |
| Automatic audio format conversion in the job | .webm is not in Gemini's supported format list | ffmpeg adds a system dependency and conversion latency; if audio is stored as .webm you cannot skip this | Store recordings in a Gemini-supported format at capture time (MP3 or AAC preferred — supported by Gemini, small file size), OR convert at upload time only if format is not supported. This is a constraint to surface in ARCHITECTURE.md. |
| Gemini function_calling mode for structured output | Function calling is the pattern from Claude tool_use (v1.3); team may try to replicate it | Gemini function calling does not work with multimodal inputs — this is confirmed in the google-genai SDK documentation and the Instructor library notes; will silently fall back to text output or error | Use `response_mime_type="application/json"` with `response_schema` (Pydantic BaseModel) instead — this is the correct multimodal structured output pattern |
| Storing Gemini uploaded files long-term | Might try to reuse the uploaded audio file across retries or future assessments | Files API TTL is fixed at 48 hours and cannot be customized; do not design the system to depend on file persistence | Upload fresh for each assessment run; the source of truth is always the audio file stored by the platform, not the Gemini-hosted copy |
| Streaming response for the assessment | Would reduce time-to-first-token | Structured output (response_schema) and streaming are incompatible in the current Gemini API — you cannot stream a JSON-schema-constrained response | Accept the full latency; the job is async anyway, so no user is blocked |

---

## Feature Dependencies

```
AudioFile (SessionRecording.audio_file, .webm)
    └──format-check──> Convert to MP3/AAC if needed (at upload time)
                           └──required by──> Gemini Files API upload (client.files.upload)
                                                └──required by──> generate_content (audio + system prompt)
                                                                      └──produces──> structured JSON response
                                                                                        ├──> transcript field (replaces SessionTranscript creation)
                                                                                        ├──> FC band + feedback
                                                                                        ├──> GRA band + feedback
                                                                                        ├──> LR band + feedback
                                                                                        └──> PR band + feedback (NEW — only possible from audio)
                                                                                                  └──> AI CriterionScore bulk write (source=AI)
                                                                                                            └──> WebSocket ai_feedback_ready push (unchanged)

Existing AIFeedbackJob model (PENDING/PROCESSING/DONE/FAILED)
    └──wraps──> entire Gemini pipeline (unchanged lifecycle)

Monthly usage limit (unchanged)
    └──gates──> trigger endpoint (unchanged)

IELTS band descriptor rubric (system prompt content)
    └──required by──> generate_content (must be in system_instruction, not user message)
```

### Dependency Notes

- **Audio format constraint is a new dependency:** v1.3 Whisper accepted .webm natively; Gemini does not. This must be resolved before the job task can proceed. Options are: convert at upload, convert in job, or change recording format at capture. The job task should not embed ffmpeg complexity — surface this as a pre-condition.
- **Files API upload is asynchronous:** After `client.files.upload()`, the file is not immediately usable. Must poll `client.files.get(name)` until `state == ACTIVE` before calling `generate_content`. This is a new failure mode the job task must handle.
- **response_schema + multimodal requires Mode.JSON:** Function calling mode is incompatible with audio input. The structured output contract must be enforced via `response_mime_type="application/json"` + `response_schema` — not via tool_use (which was the v1.3 Claude pattern).
- **Transcript is now a byproduct, not a prerequisite:** In v1.3, transcript was created by Whisper and then fed to Claude. In v1.4, transcript is a field in the Gemini response alongside the scores. The `SessionTranscript` model write happens as part of parsing the response, not as a separate pipeline stage.
- **System prompt holds the rubric:** The IELTS band descriptors for all four criteria (especially the PR descriptors) must be in the `system_instruction` parameter (not the user message). This is how Gemini separates persistent role context from per-request content.

---

## MVP Definition

This is a milestone rebuild. MVP means: replace the pipeline internals while keeping the external API contract identical.

### Launch With (v1.4)

- [ ] google-genai SDK installed, faster-whisper and anthropic removed from requirements.txt
- [ ] Audio format conversion handling (.webm → MP3) — either in job or confirmed unnecessary for the recording format
- [ ] Gemini Files API upload with ACTIVE state poll in the background job
- [ ] System prompt with full IELTS band descriptors for FC, GRA, LR, PR (bands 1–9, with emphasis on 5–8 range)
- [ ] response_schema Pydantic model: `{transcript: str, fc_band: int, fc_feedback: str, gra_band: int, gra_feedback: str, lr_band: int, lr_feedback: str, pr_band: int, pr_feedback: str}` with int bands constrained 1–9
- [ ] generate_content call: audio Part + question context (from SessionQuestion records, unchanged from v1.3)
- [ ] Parse structured response → write AI CriterionScores (source=AI) + SessionTranscript (same as v1.3 outcome)
- [ ] Existing POST trigger, GET status/scores, WebSocket push: unchanged
- [ ] Existing monthly usage limit: unchanged

### Add After Validation (v1.4.x)

- [ ] Band confidence field in response schema — once reliability of PR scores is measured in production (flag low-confidence PR bands with a note to candidate)
- [ ] Retry on Gemini API errors (upload ACTIVE poll timeout, generate_content failure) — once error rate is measured

### Future Consideration (v2+)

- [ ] Dedicated pronunciation analysis via SpeechAce or Azure Pronunciation Assessment API — if PR scoring reliability is insufficient for high-stakes use
- [ ] IELTS Part-level breakdown (Part 1 / 2 / 3 separate scores) — once holistic scores are validated
- [ ] Configurable Gemini model per examiner tier (Flash vs Pro) — once cost/quality tradeoff is measured

---

## Feature Prioritization Matrix

| Feature | User Value | Implementation Cost | Priority |
|---------|------------|---------------------|----------|
| Native PR (pronunciation) scoring from audio | HIGH | MEDIUM | P1 |
| Structured JSON output via response_schema | HIGH | LOW | P1 |
| Transcript as byproduct of assessment | HIGH | LOW | P1 |
| IELTS rubric in system prompt | HIGH | MEDIUM | P1 |
| Files API upload with ACTIVE poll | HIGH | LOW | P1 |
| Audio format handling (.webm conversion) | HIGH | MEDIUM | P1 |
| Remove faster-whisper + anthropic deps | MEDIUM | LOW | P1 |
| Intonation/rhythm observation in FC/PR feedback | MEDIUM | LOW | P1 (free — prompt instruction only) |
| Band confidence / reliability signaling | MEDIUM | LOW | P2 |
| Retry mechanism for Gemini API failures | MEDIUM | MEDIUM | P2 |

**Priority key:**
- P1: Must have for v1.4 launch
- P2: Should have, add in v1.4.x
- P3: Nice to have, future consideration

---

## System Prompt Design Guidance

This section is specific to v1.4 and documents what the Gemini system prompt must contain.

### Structural Requirements

**Use `system_instruction` (not user message):** Gemini separates persistent role context via the `system_instruction` parameter in `GenerationConfig`. The IELTS examiner role and rubric go here. The audio + question context goes in the user message content.

**Include in system_instruction:**
1. Role: "You are a certified IELTS Speaking examiner with 10+ years of experience assessing non-native English speakers."
2. Task: Assess the candidate's speaking performance across the four IELTS criteria based on the provided audio recording.
3. Rubric: Full band descriptors for FC, GRA, LR, PR (bands 1–9). Emphasis on 5–8 range where most test-takers fall. PR descriptors must explicitly reference: segmental accuracy, word stress, sentence stress, intonation patterns, intelligibility.
4. Constraints: Score holistically across the full recording. Do not score per-question. Bands are integers 1–9. Feedback is 3–4 sentences per criterion. Frame PR assessment explicitly as "based on audio characteristics" to prevent the model from ignoring the audio signal.
5. Output format instruction: Direct the model to the response_schema fields; this redundancy with the schema constraint improves adherence.

**Include in user message content:**
1. The questions asked (from SessionQuestion records) — same enrichment as v1.3.
2. The audio file Part (Gemini Files API reference or inline bytes).
3. Brief instruction: "Assess the candidate's responses to the above questions."

### PR-Specific Prompt Engineering

PR assessment from audio is the primary new capability. The system prompt must explicitly instruct Gemini to:
- Listen for how clearly the candidate produces individual sounds (segmental features)
- Assess word-level and sentence-level stress patterns
- Observe intonation — does it fall/rise appropriately? Does it aid meaning?
- Note rhythm and pacing — is speech monotone or does it vary naturally?
- Anchor to intelligibility as the primary criterion (Band 5 = "generally intelligible but L1 accent noticeable"; Band 7 = "flexible use of features, easy to understand throughout")

Without explicit instruction on what to listen for, Gemini tends to score PR based on vocabulary and grammar errors visible in the transcript rather than acoustic pronunciation features.

### Hallucination Mitigation for Scores

Research confirms Gemini achieves κ = 0.64 agreement on language assessment tasks (highest among LLMs tested), but hallucination risk is real. Mitigations:
- Require reasoning before score: include a `pr_reasoning` field in response_schema that precedes `pr_band` — chain-of-thought before scoring reduces score hallucination.
- Constrain band to integer, not float: `int` schema type prevents Gemini from emitting "6.5" or "7+".
- Frame feedback as observation, not assertion: "The candidate demonstrates..." not "The candidate has perfect pronunciation."

---

## Sources

- [Gemini Audio Understanding — Google AI for Developers](https://ai.google.dev/gemini-api/docs/audio)
- [Gemini Files API — Google AI for Developers](https://ai.google.dev/gemini-api/docs/files)
- [Gemini Structured Output — Vertex AI Docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/multimodal/control-generated-output)
- [Multimodal Audio with Instructor (Mode.JSON requirement)](https://python.useinstructor.com/examples/multi_modal_gemini/)
- [AI-Powered Pronunciation Mistake Detection Using Gemini 1.5 Flash — Academia.edu](https://www.academia.edu/152382290/AI_Powered_Pronunciation_Mistake_Detection_Using_Gemini_1_5_Flash_A_Training_Free_Approach)
- [AudioJudge: Understanding What Works in Large Audio Models — arXiv](https://arxiv.org/pdf/2507.12705) (κ = 0.64 Gemini 2.5 Pro on language assessment)
- [IELTS Speaking Band Descriptors — Cambridge English](https://assets.cambridgeenglish.org/webinars/ielts-speaking-band-descriptors.pdf)
- [Gemini 2.0 Flash deprecation (June 2026) — Firebase AI Logic Models](https://firebase.google.com/docs/ai-logic/models)
- [Gemini Files API TTL 48h — googleapis/python-genai GitHub Issue #1172](https://github.com/googleapis/python-genai/issues/1172)
- [Gemini response_schema Pydantic BaseModel — googleapis/python-genai](https://googleapis.github.io/python-genai/)
- [Google Gemini Audio Inline Data limit increase to 100 MB — DataStudios](https://www.datastudios.org/post/google-gemini-file-upload-size-limits-supported-types-and-advanced-document-processing)

---

*Feature research for: MockIT v1.4 — AI Assessment Rebuild (Gemini Audio)*
*Researched: 2026-04-09*
