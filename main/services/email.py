import resend
from django.conf import settings


def send_verification_email(user, token_uuid):
    resend.api_key = settings.RESEND_API_KEY
    verification_url = f"{settings.FRONTEND_URL}/verify-email?token={token_uuid}"

    resend.Emails.send({
        "from": settings.RESEND_FROM_EMAIL,
        "to": user.email,
        "subject": "Verify your MockIT account",
        "html": f"""
            <div style="font-family: sans-serif; max-width: 480px; margin: 0 auto;">
                <h2>Welcome to MockIT, {user.first_name or user.username}!</h2>
                <p>Click the button below to verify your email address. This link expires in 24 hours.</p>
                <a href="{verification_url}"
                   style="display: inline-block; padding: 12px 24px; background: #1a1a1a;
                          color: #fff; text-decoration: none; border-radius: 6px; margin: 16px 0;">
                    Verify Email
                </a>
                <p style="color: #666; font-size: 14px;">
                    If you didn't create a MockIT account, you can safely ignore this email.
                </p>
            </div>
        """,
    })
