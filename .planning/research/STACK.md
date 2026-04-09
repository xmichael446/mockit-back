# Stack Research

**Domain:** IELTS mock exam platform — v1.4 Gemini Audio Assessment Pipeline
**Researched:** 2026-04-09
**Confidence:** HIGH (SDK version from PyPI; model capabilities from Vertex AI official docs; audio MIME types from Vertex AI Gemini 2.5 Pro docs; structured output from official API docs)

---

## Context: What Already Exists (Do Not Re-add)

The following are confirmed in `requirements.txt` and must not be touched:

| Already Present | Version | Role |
|-----------------|---------|------|
| Django | 5.2.11 | Framework |
| djangorestframework | 3.16.1 | REST API |
| channels + daphne | 4.3.2 / 4.2.1 | WebSocket |
| psycopg2-binary | 2.9.11 | PostgreSQL |
| resend | 2.10.0 | Transactional email |
| PyJWT | 2.11.0 | JWT for 100ms tokens |
| requests | 2.32.5 | HTTP client |
| python-dotenv | 1.1.0 | Env vars |
| django-q2 | (unpinned) | Background task queue with ORM broker |

---

## Packages to Remove

| Remove | Current Version | Reason |
|--------|----------------|--------|
| `faster-whisper` | 1.2.1 | Transcription step eliminated — Gemini assesses audio directly |
| `anthropic` | 0.91.0 | Claude API replaced by Gemini API |

Both are in `requirements.txt` and must be deleted from that file.

---

## New Stack Additions for v1.4

### Core Addition

| Technology | Version | Purpose | Why Recommended |
|------------|---------|---------|-----------------|
| `google-genai` | `>=1.71.0` | Google Gemini API client — send audio + receive structured assessment | The **new unified SDK** (GA since May 2025). Replaces deprecated `google-generativeai` (0.8.6, maintenance-only since Nov 2025). Version 1.71.0 released April 8, 2026. Actively maintained, supports all Gemini 2.x/2.5 models including audio input and structured output. |

### Supporting Library (likely already present transitively)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `pydantic` | `>=2.0` | Define response schema for structured output | Used with `response_json_schema=YourModel.model_json_schema()` in generate_content config. Gemini 2.5 Pro natively supports Pydantic schema shapes for guaranteed JSON responses. Check if already installed before adding explicitly. |

---

## Recommended Model: `gemini-2.5-pro`

**Exact model ID:** `gemini-2.5-pro`

**Why this model:**
- Supports audio input natively, including `audio/webm` (the format produced by browser MediaRecorder)
- 1M token context window; up to 8.4 hours of audio per prompt
- Structured output (JSON schema enforcement) confirmed working on GA release
- General availability since June 17, 2025 — not a preview

**Why not other models:**

| Model | Status | Issue |
|-------|--------|-------|
| `gemini-2.5-pro-preview-03-25` | Preview (old) | Known structured output breakage — responses wrapped in markdown fences, `response.parsed` returns None. Multiple libraries affected (LiteLLM, LangChain). Avoid. |
| `gemini-2.0-flash` | GA | No pronunciation/prosody capability needed for IELTS speaking assessment; weaker audio reasoning |
| `gemini-2.5-flash` | GA | Lower reasoning depth than Pro; IELTS band scoring benefits from Pro's stronger analytical capability |

---

## Audio Input: WebM Support Confirmed

The `SessionRecording` model stores `.webm` audio files from browser MediaRecorder. Gemini 2.5 Pro accepts `audio/webm` as a valid MIME type.

**Full supported audio MIME list (Gemini 2.5 Pro):**
`audio/x-aac`, `audio/flac`, `audio/mp3`, `audio/m4a`, `audio/mpeg`, `audio/mpga`, `audio/mp4`, `audio/ogg`, `audio/pcm`, `audio/wav`, **`audio/webm`**

Source: [Vertex AI Gemini 2.5 Pro docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-pro) (verified April 2026)

**File size handling:**

| File Size | Approach | SDK Method |
|-----------|----------|------------|
| Under 100MB | Inline bytes in request | `types.Part.from_bytes(data=audio_bytes, mime_type='audio/webm')` |
| Over 100MB | Upload via Files API (48-hour TTL, 2GB max per file) | `client.files.upload(file=path)` then pass returned object as content |

Typical IELTS speaking session (11–14 minutes) at standard webm bitrate (~128kbps) is approximately 10–14MB — well within the inline 100MB limit. Files API is not needed unless recordings exceed 100MB.

---

## Structured Output Integration

Gemini 2.5 Pro (GA) supports enforced JSON output via `response_mime_type` + `response_json_schema`.

**Pattern to use:**

```python
from google import genai
from google.genai import types
from pydantic import BaseModel, Field

class CriterionScore(BaseModel):
    band: float = Field(description="IELTS band 1-9 in 0.5 increments")
    feedback: str = Field(description="Actionable feedback for this criterion")

class IELTSAssessment(BaseModel):
    fluency_coherence: CriterionScore
    grammatical_range: CriterionScore
    lexical_resource: CriterionScore
    pronunciation: CriterionScore

client = genai.Client()
response = client.models.generate_content(
    model="gemini-2.5-pro",
    contents=[
        types.Part.from_bytes(data=audio_bytes, mime_type="audio/webm"),
        system_prompt,
    ],
    config=types.GenerateContentConfig(
        response_mime_type="application/json",
        response_json_schema=IELTSAssessment.model_json_schema(),
    ),
)
assessment = IELTSAssessment.model_validate_json(response.text)
```

This replaces the Claude `tool_use` pattern used in v1.3. The JSON is guaranteed by the API — no regex fallback needed when using the stable model.

---

## Django-Q2 Integration

No infrastructure changes are needed. The existing django-q2 ORM broker setup from v1.3 remains unchanged.

**How the task function changes:**

| v1.3 (being replaced) | v1.4 (new) |
|-----------------------|------------|
| Read audio → faster-whisper transcribe → Claude tool_use assess | Read audio → `google-genai` send audio + receive JSON |
| Two external API calls (Whisper local + Claude remote) | One external API call (Gemini remote) |
| `anthropic.Anthropic()` client in task | `genai.Client()` client in task |

The task function (`session/tasks.py` or equivalent) instantiates `genai.Client()` synchronously inside the django-q2 worker — no async wrapper needed. The `google-genai` SDK supports both sync and async; sync is correct for django-q2's process-based workers.

**Environment variable to add:**
```
GEMINI_API_KEY=<your_key>
```

Configure via `genai.Client(api_key=settings.GEMINI_API_KEY)` or set the `GEMINI_API_KEY` environment variable (SDK auto-reads it).

---

## Installation

```bash
# Remove deprecated packages
# (delete from requirements.txt):
# faster-whisper==1.2.1
# anthropic==0.91.0

# Add new package
pip install google-genai>=1.71.0
```

Add to `requirements.txt`:
```
google-genai>=1.71.0
```

---

## Alternatives Considered

| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| `google-genai` (new unified SDK) | `google-generativeai` (old SDK) | Never for new projects — deprecated since Nov 2025, maintenance-only (critical bug fixes), last version 0.8.6 |
| `gemini-2.5-pro` (GA) | `gemini-2.5-pro-preview-*` | Only if a specific preview capability is needed that GA lacks; avoid for production due to structured output instability |
| Inline bytes (`Part.from_bytes`) | Files API upload | Only if recording exceeds 100MB — not expected for IELTS sessions |
| Pydantic schema for structured output | Prompt-only JSON instruction | Never — prompt-only is unreliable; `response_json_schema` enforces the schema at the API level |

---

## What NOT to Use

| Avoid | Why | Use Instead |
|-------|-----|-------------|
| `google-generativeai` (PyPI) | Deprecated Nov 2025, no new features, active development stopped | `google-genai` |
| `gemini-2.5-pro-preview-03-25` | Structured output broken — JSON wrapped in markdown fences, `response.parsed` returns None, affects multiple client libraries simultaneously | `gemini-2.5-pro` (GA stable) |
| Separate transcription library (e.g., `faster-whisper`, `openai-whisper`) | Gemini assesses audio directly — transcription is not a step in this pipeline | None needed |
| `instructor` library | Adds an extra abstraction over `response_json_schema`; unnecessary since google-genai natively supports Pydantic schemas | Native `response_json_schema` in `GenerateContentConfig` |

---

## Version Compatibility

| Package | Compatible With | Notes |
|---------|-----------------|-------|
| `google-genai>=1.71.0` | Python 3.10+ | Project already uses Python 3.x; no conflict |
| `google-genai>=1.71.0` | Django 5.2, django-q2, DRF | No framework-level conflicts; SDK is a pure HTTP client |
| `google-genai>=1.71.0` | `google-generativeai` (if somehow still installed) | They can coexist on the same environment but `google-generativeai` should be removed to avoid confusion |

---

## Sources

- [Vertex AI Gemini 2.5 Pro docs](https://docs.cloud.google.com/vertex-ai/generative-ai/docs/models/gemini/2-5-pro) — audio MIME types, model ID, GA date (HIGH confidence)
- [google-genai PyPI](https://pypi.org/project/google-genai/) — version 1.71.0, Python requirements (HIGH confidence)
- [google-generativeai PyPI](https://pypi.org/project/google-generativeai/) — deprecated status, version 0.8.6 (HIGH confidence)
- [Gemini API structured output docs](https://ai.google.dev/gemini-api/docs/structured-output) — `response_json_schema` pattern, Gemini 2.5 Pro support (HIGH confidence)
- [python-genai GitHub issue #637](https://github.com/googleapis/python-genai/issues/637) — structured output breakage on preview models (MEDIUM confidence — issue closed but still reported)
- [Gemini file input methods](https://ai.google.dev/gemini-api/docs/file-input-methods) — inline 100MB limit, Files API threshold (HIGH confidence)

---
*Stack research for: v1.4 Gemini Audio Assessment Pipeline*
*Researched: 2026-04-09*
