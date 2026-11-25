import logging

from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from .email_verification import CODE_VALID_MINUTES, issue_code

logger = logging.getLogger(__name__)


def send_email_verification(user):
    """Email the user a new 6-digit verification code (replacing any older one).

    Returns True if the email was handed to the mail server, False if sending
    failed (wrong SMTP settings, no internet, Gmail refused the login...).
    A failure is logged instead of crashing the page, so the account is never
    left half-created; the user can ask for a new code later.
    """
    context = {"user": user, "code": issue_code(user), "minutes": CODE_VALID_MINUTES}
    subject = render_to_string("accounts/emails/email_verification_subject.txt").strip()
    text_body = render_to_string("accounts/emails/email_verification_email.txt", context)
    html_body = render_to_string("accounts/emails/email_verification_email.html", context)
    message = EmailMultiAlternatives(subject, text_body, None, [user.email])
    message.attach_alternative(html_body, "text/html")
    try:
        message.send()
    except Exception:  # smtplib errors, socket errors, timeouts
        # Log the user id only, never the code or the SMTP password.
        logger.exception("Failed to send the verification email to user %s", user.pk)
        return False
    return True
