import logging

logger = logging.getLogger(__name__)


def run_ai_feedback(job_id: int) -> None:
    """
    Background task: transcribe audio and generate AI feedback for a session.
    Enqueued via: async_task('session.tasks.run_ai_feedback', job_id)
    """
    from session.models import AIFeedbackJob

    try:
        job = AIFeedbackJob.objects.get(pk=job_id)
        job.status = AIFeedbackJob.Status.PROCESSING
        job.save(update_fields=["status", "updated_at"])

        # Phase 11: transcription via faster-whisper
        from session.services.transcription import transcribe_session
        transcript = transcribe_session(job)
        job.transcript = transcript
        job.save(update_fields=["transcript", "updated_at"])

        # Phase 12 will add: AI scoring via Claude API

        job.status = AIFeedbackJob.Status.DONE
        job.save(update_fields=["status", "updated_at"])

    except AIFeedbackJob.DoesNotExist:
        logger.error("run_ai_feedback: job_id=%s not found", job_id)
    except Exception as exc:
        logger.exception("run_ai_feedback job_id=%s failed: %s", job_id, exc)
        try:
            job.status = AIFeedbackJob.Status.FAILED
            job.error_message = str(exc)
            job.save(update_fields=["status", "error_message", "updated_at"])
        except Exception:
            pass
