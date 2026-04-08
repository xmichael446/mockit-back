import logging

logger = logging.getLogger(__name__)

# ─── Constants ─────────────────────────────────────────────────────────────────

# Maps tool_use response keys to SpeakingCriterion enum integer values
# FC=1, GRA=2, LR=3, PR=4 (matches SpeakingCriterion.IntegerChoices in session/models.py)
CRITERION_MAP = {
    "fluency_and_coherence": 1,          # SpeakingCriterion.FC
    "grammatical_range_and_accuracy": 2, # SpeakingCriterion.GRA
    "lexical_resource": 3,               # SpeakingCriterion.LR
    "pronunciation": 4,                  # SpeakingCriterion.PR
}

REQUIRED_KEYS = set(CRITERION_MAP.keys())

SYSTEM_PROMPT = """You are an expert IELTS Speaking examiner with years of experience assessing \
candidates across all proficiency levels. Your task is to evaluate a candidate's speaking \
performance based on a session transcript and the questions that were asked, assigning band scores \
and providing actionable feedback for each of the four IELTS Speaking assessment criteria.

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

**Instructions:**
- Assign a band score (integer between 1 and 9) for each criterion.
- Provide 3-4 sentences of specific, actionable feedback for each criterion that refers to the \
candidate's actual speech patterns and gives concrete improvement advice.
- Base your assessment solely on the transcript provided and the questions that were asked.
- Call the submit_ielts_assessment tool exactly once with all four criterion assessments."""

TOOL_DEFINITION = {
    "name": "submit_ielts_assessment",
    "description": (
        "Submit IELTS Speaking band scores and actionable feedback for all four "
        "assessment criteria. Call this tool exactly once with scores for FC, GRA, LR, and PR."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "fluency_and_coherence": {
                "type": "object",
                "properties": {
                    "band": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 9,
                        "description": "Band score 1-9 for Fluency and Coherence",
                    },
                    "feedback": {
                        "type": "string",
                        "description": "3-4 sentences of specific, actionable feedback",
                    },
                },
                "required": ["band", "feedback"],
            },
            "grammatical_range_and_accuracy": {
                "type": "object",
                "properties": {
                    "band": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 9,
                        "description": "Band score 1-9 for Grammatical Range & Accuracy",
                    },
                    "feedback": {
                        "type": "string",
                        "description": "3-4 sentences of specific, actionable feedback",
                    },
                },
                "required": ["band", "feedback"],
            },
            "lexical_resource": {
                "type": "object",
                "properties": {
                    "band": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 9,
                        "description": "Band score 1-9 for Lexical Resource",
                    },
                    "feedback": {
                        "type": "string",
                        "description": "3-4 sentences of specific, actionable feedback",
                    },
                },
                "required": ["band", "feedback"],
            },
            "pronunciation": {
                "type": "object",
                "properties": {
                    "band": {
                        "type": "integer",
                        "minimum": 1,
                        "maximum": 9,
                        "description": "Band score 1-9 for Pronunciation",
                    },
                    "feedback": {
                        "type": "string",
                        "description": "3-4 sentences of specific, actionable feedback",
                    },
                },
                "required": ["band", "feedback"],
            },
        },
        "required": [
            "fluency_and_coherence",
            "grammatical_range_and_accuracy",
            "lexical_resource",
            "pronunciation",
        ],
    },
}


# ─── Service function ──────────────────────────────────────────────────────────

def assess_session(job) -> list[dict]:
    """
    Call Claude API with the session transcript and questions, returning structured
    IELTS band scores and feedback for all four speaking criteria.

    Returns a list of 4 dicts:
        [{"criterion": int, "band": int, "feedback": str}, ...]

    Raises RuntimeError on any failure (anthropic import missing, API error,
    missing criteria, or invalid band value). The caller (run_ai_feedback task)
    is responsible for updating job.status to FAILED on exception.

    Does NOT catch anthropic API exceptions — lets them propagate to the task's
    except block so the task can record the error_message and set FAILED.
    """
    try:
        import anthropic
    except ImportError:
        raise RuntimeError(
            "anthropic is not installed. Run: pip install anthropic==0.91.0"
        )

    from django.conf import settings
    from session.models import SessionQuestion

    # Build question context (AIAS-04)
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

    transcript_text = job.transcript or "(no transcript)"
    user_message = (
        f"Session questions asked:\n{questions_text}\n\n"
        f"Candidate transcript:\n{transcript_text}"
    )

    client = anthropic.Anthropic(
        api_key=getattr(settings, "ANTHROPIC_API_KEY", None)
    )

    logger.info("assess_session: calling Claude API for job_id=%s", job.pk)

    response = client.messages.create(
        model="claude-sonnet-4-20250514",
        max_tokens=1024,
        system=SYSTEM_PROMPT,
        tools=[TOOL_DEFINITION],
        tool_choice={"type": "tool", "name": "submit_ielts_assessment"},
        messages=[{"role": "user", "content": user_message}],
    )

    # Extract the tool_use block from the response
    tool_block = next(
        (b for b in response.content if b.type == "tool_use"), None
    )
    if tool_block is None:
        raise RuntimeError(
            f"Claude did not return a tool_use block. stop_reason={response.stop_reason}"
        )

    data = tool_block.input  # dict matching the TOOL_DEFINITION input_schema

    # All-or-nothing validation: all 4 criteria must be present
    missing = REQUIRED_KEYS - set(data.keys())
    if missing:
        raise RuntimeError(f"Claude response missing criteria: {missing}")

    # Validate each band is an int in range 1-9 and build result list
    result = []
    for key, criterion_int in CRITERION_MAP.items():
        entry = data[key]
        band = entry.get("band")
        feedback = entry.get("feedback", "")
        if not isinstance(band, int) or not (1 <= band <= 9):
            raise RuntimeError(
                f"Invalid band for {key!r}: expected integer 1-9, got {band!r}"
            )
        result.append({"criterion": criterion_int, "band": band, "feedback": feedback})

    logger.info(
        "assess_session: completed job_id=%s bands=%s",
        job.pk,
        [r["band"] for r in result],
    )
    return result
