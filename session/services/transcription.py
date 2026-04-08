import logging
import os

from django.conf import settings

logger = logging.getLogger(__name__)


def transcribe_session(job) -> str:
    """
    Transcribe session audio and return plain-text transcript.

    Raises RuntimeError on any unrecoverable error.
    The caller (run_ai_feedback task) handles status updates.
    """
    try:
        from faster_whisper import WhisperModel
    except ImportError:
        raise RuntimeError(
            "faster-whisper is not installed. Run: pip install faster-whisper"
        )

    # Validate recording exists
    try:
        recording = job.session.recording
    except Exception:
        raise RuntimeError("Session has no associated recording.")

    audio_path = recording.audio_file.path
    if not audio_path:
        raise RuntimeError("SessionRecording.audio_file is empty.")

    if not os.path.isfile(audio_path):
        raise RuntimeError(f"Audio file not found: {audio_path}")

    # Build initial_prompt from all session question texts to improve accuracy
    from session.models import SessionQuestion

    questions = (
        SessionQuestion.objects.filter(session_part__session=job.session)
        .select_related("question")
        .order_by("session_part__part", "order")
    )
    prompt_parts = [sq.question.text for sq in questions if sq.question.text]
    initial_prompt = ". ".join(prompt_parts) if prompt_parts else None

    # Load model lazily inside function (avoids import-time cost and startup delay)
    model_size = getattr(settings, "WHISPER_MODEL_SIZE", "base")
    logger.info("transcribe_session: loading WhisperModel size=%s", model_size)
    model = WhisperModel(model_size, device="cpu", compute_type="int8")

    segments, _info = model.transcribe(
        audio_path,
        beam_size=5,
        initial_prompt=initial_prompt,
        language="en",
    )

    # Consume segments generator in a single pass (generator exhausts on second iteration)
    lines = []
    for segment in segments:
        lines.append(segment.text.strip())

    logger.info(
        "transcribe_session: completed model_size=%s segments=%d",
        model_size,
        len(lines),
    )
    return "\n".join(lines)
