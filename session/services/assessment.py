import logging

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

# ─── Constants ─────────────────────────────────────────────────────────────────

# Maps Pydantic field names to SpeakingCriterion enum integer values
# FC=1, GRA=2, LR=3, PR=4 (matches SpeakingCriterion.IntegerChoices in session/models.py)
CRITERION_MAP = {
    "fluency_and_coherence": 1,          # SpeakingCriterion.FC
    "grammatical_range_and_accuracy": 2, # SpeakingCriterion.GRA
    "lexical_resource": 3,               # SpeakingCriterion.LR
    "pronunciation": 4,                  # SpeakingCriterion.PR
}


# ─── Pydantic schema ──────────────────────────────────────────────────────────

class CriterionAssessment(BaseModel):
    band: int = Field(ge=1, le=9)
    feedback: str


class IELTSAssessment(BaseModel):
    fluency_and_coherence: CriterionAssessment
    grammatical_range_and_accuracy: CriterionAssessment
    lexical_resource: CriterionAssessment
    pronunciation: CriterionAssessment
    transcript: str


# ─── System prompt ─────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are an expert IELTS Speaking examiner with years of experience assessing \
candidates across all proficiency levels. Your task is to evaluate a candidate's speaking \
performance based on the audio recording of the session and the questions that were asked, \
assigning band scores and providing actionable feedback for each of the four IELTS Speaking \
assessment criteria.

Use the official IELTS Speaking band descriptors as your reference:

**Fluency and Coherence (FC)**
- Bands 1-3: Very limited speech; long pauses; fragmented utterances; little or no logical \
connection between ideas.
- Bands 4-5: Some fluency evident but frequent hesitation; repetition or self-correction affects \
communication; basic cohesive devices used but not always appropriately.
- Bands 6-7: Generally fluent with some hesitation; able to maintain speech flow; uses a range of \
cohesive devices; can extend discourse even if occasionally losing coherence.
- Bands 8-9: Speaks fluently with only occasional repetition or self-correction; uses a full range \
of discourse markers naturally and appropriately; ideas are coherent and logically sequenced.

**Grammatical Range and Accuracy (GRA)**
- Bands 1-3: Relies on a very limited range of structures; frequent errors with basic forms; \
communication may break down.
- Bands 4-5: Produces basic sentence forms with reasonable accuracy; attempts complex structures \
but errors are frequent; meaning is usually clear.
- Bands 6-7: Uses a mix of simple and complex structures; makes some errors but they rarely reduce \
communication; maintains generally accurate grammar.
- Bands 8-9: Uses a wide range of structures flexibly and accurately; errors are rare and minor; \
handles complex grammatical forms with confidence.

**Lexical Resource (LR)**
- Bands 1-3: Extremely limited vocabulary; may only use memorised phrases; communication severely \
limited.
- Bands 4-5: Basic vocabulary for familiar topics; paraphrases unsuccessfully at times; limited \
ability to use less common vocabulary or idiomatic expressions.
- Bands 6-7: Uses adequate vocabulary for most topics; uses some idiomatic language; aware of \
style and collocation though with some inaccuracies.
- Bands 8-9: Uses vocabulary resourcefully and flexibly; uses idiomatic expressions naturally and \
accurately; any errors are minor and do not affect communication.

**Pronunciation (PR)**
- Bands 1-3: Pronunciation problems are severe and persistent; very hard to understand throughout.
- Bands 4-5: Some intelligibility but frequent mispronunciation of individual sounds or words; \
limited range of pronunciation features.
- Bands 6-7: Generally intelligible; uses a range of phonological features with mixed control; \
some intrusive pronunciation features but they do not impede understanding.
- Bands 8-9: Easy to understand throughout; uses a full range of pronunciation features with \
precision and subtlety; only minor non-standard features that do not affect intelligibility.

**Audio-Specific Pronunciation Assessment:**
When assessing pronunciation, listen carefully to the actual audio for:
- **Intonation patterns**: Rising/falling tones, question intonation, emphasis for meaning
- **Stress placement**: Word stress accuracy, sentence stress for highlighting key information
- **Connected speech**: Linking, elision, assimilation between words in natural speech flow
- **Rhythm and pacing**: Natural speech rhythm vs. syllable-timed delivery, appropriate pausing
Base your pronunciation assessment primarily on what you HEAR in the audio, not just the \
transcript text.

**Instructions:**
- You are given the actual audio recording of the session. Use it to assess pronunciation, \
intonation, rhythm, and connected speech directly.
- Produce a verbatim transcript of the candidate's speech from the audio.
- Assign a band score (integer between 1 and 9) for each criterion.
- Provide 3-4 sentences of specific, actionable feedback for each criterion.
- Include the session questions as context for understanding the candidate's responses."""


# ─── Service function ──────────────────────────────────────────────────────────

def assess_session(job) -> tuple[list[dict], str]:
    """
    Upload session audio to Gemini Files API and call generate_content with a structured
    Pydantic schema, returning IELTS band scores and a transcript.

    Returns a tuple of:
        - list of 4 dicts: [{"criterion": int, "band": int, "feedback": str}, ...]
        - transcript string from the Gemini response

    Raises RuntimeError on any failure (missing audio file, API error, safety filter
    rejection, or Pydantic parse failure). The caller (run_ai_feedback task) is
    responsible for updating job.status to FAILED on exception.

    NOTE: tasks.py is updated in Phase 17 to unpack the tuple return value.
    """
    import os
    import time

    from django.conf import settings
    from google import genai
    from google.genai import types
    from session.models import SessionQuestion

    # ── Step a: Get audio path ────────────────────────────────────────────────
    recording = job.session.recording
    audio_path = recording.audio_file.path
    if not os.path.isfile(audio_path):
        raise RuntimeError(f"Audio file not found: {audio_path}")

    # ── Step b: Build question context ────────────────────────────────────────
    questions = (
        SessionQuestion.objects.filter(session_part__session=job.session)
        .select_related("question", "session_part")
        .order_by("session_part__part", "order")
    )
    question_lines = [
        f"[Part {sq.session_part.part}] {sq.question.text}"
        for sq in questions
        if sq.question.text
    ]
    questions_text = "\n".join(question_lines) if question_lines else "(no questions recorded)"

    # ── Step c: Build user prompt ─────────────────────────────────────────────
    user_prompt = (
        f"Session questions asked:\n{questions_text}\n\n"
        "Assess the candidate's IELTS Speaking performance from the audio above. "
        "Produce a verbatim transcript and band scores with feedback for all four criteria."
    )

    # ── Step d: Create Gemini client ──────────────────────────────────────────
    client = genai.Client(api_key=settings.GEMINI_API_KEY)

    # ── Step e: Upload audio ──────────────────────────────────────────────────
    logger.info("assess_session: uploading audio for job_id=%s path=%s", job.pk, audio_path)
    uploaded_file = client.files.upload(
        file=audio_path,
        config=types.UploadFileConfig(mime_type="audio/webm"),
    )
    # Brief wait for PROCESSING state — sufficient for typical session recordings.
    # NOTE: For very large files, a polling loop on FileState.ACTIVE may be needed.
    time.sleep(2)

    # ── Step f: Call generate_content with retry ──────────────────────────────
    config = types.GenerateContentConfig(
        system_instruction=SYSTEM_PROMPT,
        response_mime_type="application/json",
        response_schema=IELTSAssessment,
    )
    max_retries = 3
    for attempt in range(1, max_retries + 1):
        try:
            response = client.models.generate_content(
                model="gemini-2.5-pro",
                contents=[uploaded_file, user_prompt],
                config=config,
            )
            break
        except Exception as exc:
            status = getattr(exc, "status_code", None)
            if status in (503, 429) and attempt < max_retries:
                time.sleep(5 * attempt)
            else:
                raise

    # ── Step g: Safety filter check ───────────────────────────────────────────
    candidate = response.candidates[0]
    if candidate.finish_reason != types.FinishReason.STOP:
        raise RuntimeError(
            f"Gemini content blocked: finish_reason={candidate.finish_reason}"
        )

    # ── Step h: Parse response ────────────────────────────────────────────────
    try:
        parsed = IELTSAssessment.model_validate_json(response.text)
    except Exception as exc:
        raise RuntimeError(f"Failed to parse Gemini response: {exc}") from exc

    # ── Step i: Build scores list ─────────────────────────────────────────────
    scores = [
        {
            "criterion": CRITERION_MAP[key],
            "band": getattr(parsed, key).band,
            "feedback": getattr(parsed, key).feedback,
        }
        for key in CRITERION_MAP
    ]
    transcript = parsed.transcript

    # ── Step j: Log and return ────────────────────────────────────────────────
    logger.info(
        "assess_session: completed job_id=%s bands=%s",
        job.pk,
        [s["band"] for s in scores],
    )
    return scores, transcript
