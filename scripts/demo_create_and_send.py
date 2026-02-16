#!/usr/bin/env python3
import argparse
import json
import sys
import uuid
from datetime import datetime

from app_config import settings
from database import SessionLocal, init_db
from mailer_service import MailerError, send_campaign_email
from models import Campaign, CampaignRecipient, Event, TemplateRender
from template_service import load_brand_config, render_campaign_templates, sync_brands_table
from token_service import sign_token


def parse_recipient(value: str) -> tuple[str, str]:
    if ":" in value:
        email, first_name = value.split(":", 1)
    else:
        email, first_name = value, "there"
    return email.strip(), first_name.strip() or "there"


def main() -> int:
    parser = argparse.ArgumentParser(description="Create and send a themed demo campaign")
    parser.add_argument("--brand-id", required=True)
    parser.add_argument("--name", required=True)
    parser.add_argument("--subject", required=True)
    parser.add_argument("--from-email", required=True)
    parser.add_argument("--reply-to", required=True)
    parser.add_argument("--recipient", action="append", required=True, help="email[:first_name]")
    parser.add_argument("--base-url", default=settings.base_url)
    args = parser.parse_args()

    init_db()
    with SessionLocal() as db:
        sync_brands_table(db)
        brand_cfg = load_brand_config(args.brand_id)

        campaign = Campaign(
            id=str(uuid.uuid4()),
            brand_id=args.brand_id,
            name=args.name,
            subject=args.subject,
            from_email=args.from_email,
            reply_to=args.reply_to,
            status="draft",
        )
        db.add(campaign)
        db.flush()

        recipients = []
        for raw in args.recipient:
            email, first_name = parse_recipient(raw)
            row = CampaignRecipient(
                campaign_id=campaign.id,
                email=email,
                first_name=first_name,
                token_id=str(uuid.uuid4()),
            )
            db.add(row)
            recipients.append(row)

        db.add(TemplateRender(campaign_id=campaign.id, brand_id=args.brand_id, template_version="v1"))
        db.commit()

        sent = 0
        failed = []
        chat_endpoint = f"{args.base_url.rstrip('/')}/api/v1/chat/message"
        campaign_payload = {
            "subject": campaign.subject,
            "from_email": campaign.from_email,
            "reply_to": campaign.reply_to,
        }

        for row in recipients:
            token = sign_token(campaign.id, row.email, token_id=row.token_id)
            rendered = render_campaign_templates(
                brand_cfg,
                campaign={"subject": campaign.subject},
                recipient={"email": row.email, "first_name": row.first_name or "there"},
                chat_endpoint=chat_endpoint,
                token=token,
            )

            try:
                message_id = send_campaign_email(
                    campaign_payload,
                    row.email,
                    rendered["amp_html"],
                    rendered["html_html"],
                    rendered["text_body"],
                )
                row.sent_at = datetime.utcnow()
                db.add(
                    Event(
                        campaign_id=campaign.id,
                        event_type="campaign_send_success",
                        payload_json=json.dumps({"email": row.email, "message_id": message_id}),
                    )
                )
                sent += 1
            except MailerError as exc:
                failed.append({"email": row.email, "error": str(exc)})
                db.add(
                    Event(
                        campaign_id=campaign.id,
                        event_type="campaign_send_failure",
                        payload_json=json.dumps({"email": row.email, "error": str(exc)}),
                    )
                )

        campaign.status = "sent" if sent else "failed"
        db.commit()

        print(
            json.dumps(
                {
                    "campaign_id": campaign.id,
                    "brand_id": args.brand_id,
                    "sent": sent,
                    "failed": failed,
                },
                indent=2,
            )
        )
        return 0 if sent else 1


if __name__ == "__main__":
    sys.exit(main())
