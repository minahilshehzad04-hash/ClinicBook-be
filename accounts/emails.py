import logging

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode

from .tokens import email_token_generator

logger = logging.getLogger(__name__)


def build_verification_link(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = email_token_generator.make_token(user)
    # The link opens the Next.js page, which then calls the API.
    return f"{settings.FRONTEND_URL}/verify-email?uid={uid}&token={token}"


def send_verification_email(user):
    """Returns True if the mail was handed to the SMTP server, False otherwise."""
    link = build_verification_link(user)
    name = user.first_name or "there"

    text = (
        f"Hi {name},\n\n"
        "Welcome to ClinicBook! Please confirm your email address to activate your account:\n\n"
        f"{link}\n\n"
        "If you did not create this account, you can ignore this email.\n"
    )
    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:0 auto;padding:24px;color:#0f172a">
      <h2 style="margin:0 0 4px;color:#115e59">clinicbook</h2>
      <p style="margin-top:24px">Hi {name},</p>
      <p>Welcome to ClinicBook! Please confirm your email address to activate your account.</p>
      <p style="margin:28px 0">
        <a href="{link}"
           style="background:#134e4a;color:#ffffff;text-decoration:none;padding:12px 24px;
                  border-radius:8px;font-weight:bold;display:inline-block">
          Verify my email
        </a>
      </p>
      <p style="font-size:13px;color:#475569">
        Button not working? Paste this link into your browser:<br>
        <a href="{link}" style="color:#0f766e;word-break:break-all">{link}</a>
      </p>
      <p style="font-size:13px;color:#475569">
        If you did not create this account, you can ignore this email.
      </p>
    </div>
    """

    message = EmailMultiAlternatives(
        subject="Verify your ClinicBook email",
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(html, "text/html")

    try:
        message.send(fail_silently=False)
        return True
    except Exception:  # SMTP down, bad credentials, etc.
        logger.exception("Could not send verification email to user %s", user.pk)
        return False
