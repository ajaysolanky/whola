#!/usr/bin/env python3
"""Send a test email with the AMP chatbot widget."""

import sys
from pathlib import Path

# Ensure project root is on sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import os
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.utils import make_msgid

from app_config import settings
from campaign_presets import DEFAULT_PRESET_ID, get_preset
from template_service import load_brand_config, render_campaign_templates
from token_service import sign_token

RECIPIENT_EMAIL = os.environ.get("RECIPIENT_EMAIL", "")
BRAND_ID = "acme"
PRESET_ID = DEFAULT_PRESET_ID
FROM_EMAIL = os.environ.get("FROM_EMAIL", RECIPIENT_EMAIL)
REPLY_TO = FROM_EMAIL

GMAIL_SMTP_HOST = "smtp.gmail.com"
GMAIL_SMTP_PORT = 587
GMAIL_APP_PASSWORD = os.environ.get("GMAIL_APP_PASSWORD", "")


def main():
    if not RECIPIENT_EMAIL or not GMAIL_APP_PASSWORD:
        print("Usage: RECIPIENT_EMAIL=you@gmail.com GMAIL_APP_PASSWORD='xxxx' python scripts/send_test_email.py")
        sys.exit(1)

    brand_cfg = load_brand_config(BRAND_ID)
    preset = get_preset(PRESET_ID)

    campaign_id = "test-email-001"
    token = sign_token(
        campaign_id=campaign_id,
        recipient=RECIPIENT_EMAIL,
        token_id="test-token-001",
        ttl_seconds=86400 * 7,  # 7-day expiry
    )
    # AMP4email requires HTTPS for action-xhr URLs
    base = settings.base_url.rstrip('/')
    if base.startswith("http://"):
        base = "https" + base[4:]
    chat_endpoint = f"{base}/api/v1/chat/message"

    rendered = render_campaign_templates(
        brand_cfg,
        campaign=preset,
        recipient={"email": RECIPIENT_EMAIL, "first_name": "Ajay"},
        chat_endpoint=chat_endpoint,
        token=token,
    )

    msg = MIMEMultipart("alternative")
    msg["Subject"] = preset["subject"]
    msg["From"] = FROM_EMAIL
    msg["To"] = RECIPIENT_EMAIL
    msg["Reply-To"] = REPLY_TO
    msg["Message-ID"] = make_msgid()

    msg.attach(MIMEText(rendered["text_body"], "plain", "utf-8"))
    msg.attach(MIMEText(rendered["amp_html"], "x-amp-html", "utf-8"))
    msg.attach(MIMEText(rendered["html_html"], "html", "utf-8"))

    print(f"Sending to {RECIPIENT_EMAIL} via {GMAIL_SMTP_HOST}:{GMAIL_SMTP_PORT} ...")
    with smtplib.SMTP(GMAIL_SMTP_HOST, GMAIL_SMTP_PORT, timeout=20) as client:
        client.starttls()
        client.login(FROM_EMAIL, GMAIL_APP_PASSWORD)
        client.sendmail(FROM_EMAIL, [RECIPIENT_EMAIL], msg.as_string())
    print(f"Sent! Message-ID: {msg['Message-ID']}")


if __name__ == "__main__":
    main()
