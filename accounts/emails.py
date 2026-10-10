"""Verification e-mails and the signed links they contain."""

import logging

from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse

logger = logging.getLogger(__name__)

SALT = "accounts.email-verify"
MAX_AGE = 3 * 24 * 60 * 60  # links are valid for 3 days


def make_token(user):
    # Bound to the current address: changing the e-mail invalidates old links.
    return signing.dumps({"u": user.pk, "e": user.email}, salt=SALT)


def read_token(token):
    """Return `(user_id, email)` or None for a bad / expired token."""
    try:
        data = signing.loads(token, salt=SALT, max_age=MAX_AGE)
        return data["u"], data["e"]
    except (signing.BadSignature, KeyError, TypeError):
        return None


def send_verification_email(request, user):
    """Send the link; never raise (a mail outage must not break registration)."""
    link = request.build_absolute_uri(reverse("verify_email", args=[make_token(user)]))
    context = {"user": user, "link": link}
    try:
        send_mail(
            subject=render_to_string("accounts/verify_email_subject.txt", context).strip(),
            message=render_to_string("accounts/verify_email.txt", context),
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[user.email],
        )
    except Exception:
        logger.exception("Doğrulama e-postası gönderilemedi (kullanıcı %s)", user.pk)
        return False
    return True
