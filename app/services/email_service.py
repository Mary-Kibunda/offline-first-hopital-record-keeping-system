"""Outgoing email.

Plain ``smtplib`` so there is no extra dependency. Sending is blocking, so the
API layer schedules these functions with FastAPI's ``BackgroundTasks``: the
request returns immediately, and an SMTP outage can never fail (or slow down)
creating a user or requesting a reset.

If ``SMTP_HOST`` is not configured the message is logged instead of sent, so
local development and the test suite need no mail server.
"""

import logging
import smtplib
import ssl
from email.message import EmailMessage
from email.utils import formataddr
from urllib.parse import urlencode

from app.core.config import settings

logger = logging.getLogger(__name__)

SMTP_TIMEOUT_SECONDS = 40


def send_email(to: str, subject: str, text_body: str) -> bool:
    """Send a plain-text email. Returns True on success; never raises."""
    message = EmailMessage()
    message["From"] = formataddr((settings.EMAIL_FROM_NAME, settings.EMAIL_FROM))
    message["To"] = to
    message["Subject"] = subject
    message.set_content(text_body)

    if not settings.SMTP_HOST:
        # Deliberately not logging the body: it can contain a password or reset link.
        logger.warning("SMTP_HOST is not set; email %r to %s was NOT sent.", subject, to)
        return False

    try:
        if settings.SMTP_USE_SSL:
            smtp = smtplib.SMTP_SSL(
                settings.SMTP_HOST,
                settings.SMTP_PORT,
                timeout=SMTP_TIMEOUT_SECONDS,
                context=ssl.create_default_context(),
            )
        else:
            smtp = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=SMTP_TIMEOUT_SECONDS)
        with smtp:
            if settings.SMTP_USE_TLS and not settings.SMTP_USE_SSL:
                smtp.starttls(context=ssl.create_default_context())
            if settings.SMTP_USERNAME:
                smtp.login(settings.SMTP_USERNAME, settings.SMTP_PASSWORD)
            smtp.send_message(message)
    except Exception:
        logger.exception("Failed to send email %r to %s", subject, to)
        return False
    return True


def build_reset_url(token: str) -> str:
    base = settings.FRONTEND_URL.rstrip("/")
    return f"{base}{settings.PASSWORD_RESET_PATH}?{urlencode({'token': token})}"


def send_welcome_email(to: str, name: str, username: str, password: str) -> bool:
    """Tell a newly created user how to sign in."""
    login_url = settings.FRONTEND_URL.rstrip("/") + settings.LOGIN_PATH
    body = f"""Hello {name},

An account has been created for you on {settings.PROJECT_NAME}.

    Username: {username}
    Password: {password}

Sign in here: {login_url}

For your security, please change this password after you first sign in
(use "Forgot password" on the sign-in page if you need to set a new one).
If you were not expecting this email, please contact your administrator.
"""
    return send_email(to, f"Your {settings.PROJECT_NAME} account", body)


def send_password_reset_email(to: str, name: str, token: str) -> bool:
    """Send the link to the reset form."""
    minutes = settings.PASSWORD_RESET_TOKEN_EXPIRE_MINUTES
    body = f"""Hello {name},

We received a request to reset the password for your {settings.PROJECT_NAME} account.

Open this link to choose a new password (valid for {minutes} minutes, one use only):

{build_reset_url(token)}

If you did not request this, you can ignore this email - your password will
not change.
"""
    return send_email(to, f"Reset your {settings.PROJECT_NAME} password", body)
