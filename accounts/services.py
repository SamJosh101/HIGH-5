from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string

from .email_verification import CODE_VALID_MINUTES, issue_code


def send_email_verification(user):
    """Email the user a new 6-digit verification code (replacing any older one)."""
    context = {"user": user, "code": issue_code(user), "minutes": CODE_VALID_MINUTES}
    subject = render_to_string("accounts/emails/email_verification_subject.txt").strip()
    text_body = render_to_string("accounts/emails/email_verification_email.txt", context)
    html_body = render_to_string("accounts/emails/email_verification_email.html", context)
    message = EmailMultiAlternatives(subject, text_body, None, [user.email])
    message.attach_alternative(html_body, "text/html")
    message.send()
