import logging

import resend
from django.conf import settings

logger = logging.getLogger("mockit.email")


def notify_new_request(session_request):
    """
    Notify the examiner that a candidate has submitted a new session request.
    Returns True on success, False on failure (fire-and-forget; caller ignores return value).
    """
    resend.api_key = settings.RESEND_API_KEY

    candidate = session_request.candidate
    examiner = session_request.examiner
    candidate_name = candidate.first_name or candidate.username
    formatted_date = session_request.requested_date.strftime("%B %d, %Y")
    formatted_time = session_request.availability_slot.start_time.strftime("%H:%M")

    try:
        resend.Emails.send({
            "from": settings.RESEND_FROM_EMAIL,
            "to": examiner.email,
            "subject": "New session request on MockIT",
            "html": f"""
                <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
                    <h2>New Session Request</h2>
                    <p>
                        <strong>{candidate_name}</strong> has requested a session with you
                        on <strong>{formatted_date}</strong> at <strong>{formatted_time}</strong>.
                    </p>
                    <p>Log in to MockIT to accept or reject this request.</p>
                    <a href="{settings.FRONTEND_URL}"
                       style="display: inline-block; padding: 12px 24px; background: #1a1a1a;
                              color: #fff; text-decoration: none; border-radius: 6px; margin: 16px 0;">
                        View Request
                    </a>
                    <p style="color: #666; font-size: 14px;">
                        If you were not expecting this request, you can safely ignore this email.
                    </p>
                </div>
            """,
        })
        return True
    except Exception as exc:
        logger.error(
            "Failed to send new_request email to %s: %s",
            examiner.email,
            exc,
        )
        return False


def notify_request_accepted(session_request):
    """
    Notify the candidate that their session request has been accepted.
    Returns True on success, False on failure.
    """
    resend.api_key = settings.RESEND_API_KEY

    candidate = session_request.candidate
    examiner = session_request.examiner
    examiner_name = examiner.first_name or examiner.username
    formatted_date = session_request.requested_date.strftime("%B %d, %Y")
    formatted_time = session_request.availability_slot.start_time.strftime("%H:%M")

    try:
        resend.Emails.send({
            "from": settings.RESEND_FROM_EMAIL,
            "to": candidate.email,
            "subject": "Your MockIT session request was accepted",
            "html": f"""
                <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
                    <h2>Session Request Accepted</h2>
                    <p>
                        Your session request for <strong>{formatted_date}</strong> at
                        <strong>{formatted_time}</strong> with examiner
                        <strong>{examiner_name}</strong> has been accepted.
                    </p>
                    <p>Log in to MockIT to view your upcoming session.</p>
                    <a href="{settings.FRONTEND_URL}"
                       style="display: inline-block; padding: 12px 24px; background: #1a1a1a;
                              color: #fff; text-decoration: none; border-radius: 6px; margin: 16px 0;">
                        View Session
                    </a>
                    <p style="color: #666; font-size: 14px;">
                        Good luck with your IELTS Speaking practice!
                    </p>
                </div>
            """,
        })
        return True
    except Exception as exc:
        logger.error(
            "Failed to send request_accepted email to %s: %s",
            candidate.email,
            exc,
        )
        return False


def notify_request_rejected(session_request):
    """
    Notify the candidate that their session request has been rejected.
    Includes the rejection comment if provided.
    Returns True on success, False on failure.
    """
    resend.api_key = settings.RESEND_API_KEY

    candidate = session_request.candidate
    formatted_date = session_request.requested_date.strftime("%B %d, %Y")
    formatted_time = session_request.availability_slot.start_time.strftime("%H:%M")

    rejection_comment_html = ""
    if session_request.rejection_comment:
        rejection_comment_html = f"""
                    <p style="background: #f5f5f5; padding: 12px; border-radius: 4px; margin: 16px 0;">
                        <strong>Reason:</strong> {session_request.rejection_comment}
                    </p>
        """

    try:
        resend.Emails.send({
            "from": settings.RESEND_FROM_EMAIL,
            "to": candidate.email,
            "subject": "Your MockIT session request was rejected",
            "html": f"""
                <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
                    <h2>Session Request Not Accepted</h2>
                    <p>
                        Unfortunately, your session request for <strong>{formatted_date}</strong>
                        at <strong>{formatted_time}</strong> was not accepted.
                    </p>
                    {rejection_comment_html}
                    <p>You can browse other available slots and submit a new request.</p>
                    <a href="{settings.FRONTEND_URL}"
                       style="display: inline-block; padding: 12px 24px; background: #1a1a1a;
                              color: #fff; text-decoration: none; border-radius: 6px; margin: 16px 0;">
                        Browse Slots
                    </a>
                    <p style="color: #666; font-size: 14px;">
                        We hope to see you schedule another session soon.
                    </p>
                </div>
            """,
        })
        return True
    except Exception as exc:
        logger.error(
            "Failed to send request_rejected email to %s: %s",
            candidate.email,
            exc,
        )
        return False
