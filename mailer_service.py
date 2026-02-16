from __future__ import annotations

import smtplib
import time
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid

from app_config import settings


class MailerError(Exception):
    pass


def _build_message(campaign: dict[str, str], recipient_email: str, amp_html: str, html_html: str, text_body: str):
    msg = MIMEMultipart("alternative")
    msg["Subject"] = campaign["subject"]
    msg["From"] = campaign["from_email"]
    msg["To"] = recipient_email
    msg["Reply-To"] = campaign["reply_to"]
    msg["Message-ID"] = make_msgid()

    msg.attach(MIMEText(text_body, "plain", "utf-8"))
    msg.attach(MIMEText(html_html, "html", "utf-8"))
    msg.attach(MIMEText(amp_html, "x-amp-html", "utf-8"))
    return msg


def send_campaign_email(
    campaign: dict[str, str],
    recipient_email: str,
    amp_html: str,
    html_html: str,
    text_body: str,
    retries: int = 2,
) -> str:
    if not settings.smtp_host:
        raise MailerError("SMTP_HOST is not configured")

    msg = _build_message(campaign, recipient_email, amp_html, html_html, text_body)
    last_error: Exception | None = None

    for attempt in range(retries + 1):
        try:
            with smtplib.SMTP(settings.smtp_host, settings.smtp_port, timeout=20) as client:
                if settings.smtp_use_tls:
                    client.starttls()
                if settings.smtp_username:
                    client.login(settings.smtp_username, settings.smtp_password)
                client.sendmail(campaign["from_email"], [recipient_email], msg.as_string())
                return msg["Message-ID"]
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= retries:
                break
            time.sleep(0.5 * (2**attempt))

    raise MailerError(f"Failed to send email: {last_error}")
