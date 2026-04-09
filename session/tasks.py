import logging

logger = logging.getLogger(__name__)


def run_ai_feedback(job_id: int) -> None:
    """
    Background task: Generate AI feedback for a session via Gemini.
    Enqueued via: async_task('session.tasks.run_ai_feedback', job_id)
    """
    from session.models import AIFeedbackJob

    try:
        job = AIFeedbackJob.objects.get(pk=job_id)
        job.status = AIFeedbackJob.Status.PROCESSING
        job.save(update_fields=["status", "updated_at"])

        # Phase 16/17: single Gemini call returns (scores, transcript)
        from session.services.assessment import assess_session
        from session.models import SessionResult, CriterionScore, ScoreSource

        scores_data, transcript = assess_session(job)
        job.transcript = transcript
        job.save(update_fields=["transcript", "updated_at"])
        result, _ = SessionResult.objects.get_or_create(session=job.session)
        CriterionScore.objects.bulk_create([
            CriterionScore(
                session_result=result,
                criterion=entry["criterion"],
                source=ScoreSource.AI,
                band=entry["band"],
                feedback=entry["feedback"],
            )
            for entry in scores_data
        ])

        job.status = AIFeedbackJob.Status.DONE
        job.save(update_fields=["status", "updated_at"])

        # Phase 14: notify connected clients via WebSocket
        from session.views import _broadcast
        _broadcast(job.session_id, "ai_feedback_ready", {
            "job_id": job.pk,
            "session_id": job.session_id,
        })

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
