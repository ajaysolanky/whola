from __future__ import annotations

import json
import uuid
from datetime import datetime

from flask import Flask, g, jsonify, make_response, redirect, render_template, request, url_for
from flask_cors import CORS
from sqlalchemy import func

from app_config import settings
from chat_service import ChatServiceError, get_conversation_messages, handle_message
from database import SessionLocal, init_db
from mailer_service import MailerError, send_campaign_email
from models import Campaign, CampaignRecipient, Conversation, Event, Message, TemplateRender
from template_service import (
    TemplateError,
    load_all_brand_configs,
    load_brand_config,
    render_campaign_templates,
    sync_brands_table,
)
from token_service import TokenError, sign_token, verify_token


app = Flask(__name__)
CORS(app, supports_credentials=True)


def _bootstrap() -> None:
    init_db()
    with SessionLocal() as db:
        sync_brands_table(db)


_bootstrap()


def _request_data() -> dict:
    if request.is_json:
        return request.get_json(silent=True) or {}
    return request.form.to_dict(flat=True)


def _error(message: str, status_code: int):
    return jsonify({"error": message, "request_id": g.request_id}), status_code


def _parse_recipients_from_text(raw: str) -> list[dict[str, str]]:
    recipients: list[dict[str, str]] = []
    for line in [ln.strip() for ln in raw.splitlines() if ln.strip()]:
        if "," in line:
            email, first_name = [part.strip() for part in line.split(",", 1)]
        else:
            email, first_name = line.strip(), "there"
        if not email:
            continue
        recipients.append({"email": email, "first_name": first_name or "there"})
    return recipients


@app.before_request
def _attach_request_id() -> None:
    g.request_id = request.headers.get("X-Request-Id", str(uuid.uuid4()))


@app.after_request
def _set_common_headers(response):
    response.headers["X-Request-Id"] = g.get("request_id", "")
    return response


def _set_amp_cors_headers(response):
    amp_sender = request.headers.get("AMP-Email-Sender")
    source_origin = request.args.get("__amp_source_origin")
    origin = request.headers.get("Origin")

    response.headers["AMP-Email-Allow-Sender"] = amp_sender or "*"
    response.headers["Access-Control-Allow-Credentials"] = "true"
    response.headers[
        "Access-Control-Expose-Headers"
    ] = "AMP-Access-Control-Allow-Source-Origin, AMP-Email-Allow-Sender"

    if origin:
        response.headers["Access-Control-Allow-Origin"] = origin
    if source_origin:
        response.headers["AMP-Access-Control-Allow-Source-Origin"] = source_origin

    return response


def amp_response(handler):
    def wrapped(*args, **kwargs):
        response = app.make_response(handler(*args, **kwargs))
        return _set_amp_cors_headers(response)

    wrapped.__name__ = handler.__name__
    return wrapped


@app.get("/health")
def health():
    return jsonify({"ok": True, "request_id": g.request_id})


@app.get("/demo/admin")
def admin_dashboard():
    message = request.args.get("message", "")
    error = request.args.get("error", "")
    preview_campaign_id = request.args.get("preview_campaign", "").strip()
    amp_simulation = None

    with SessionLocal() as db:
        brands = load_all_brand_configs()
        stats = {
            "campaign_count": db.query(func.count(Campaign.id)).scalar() or 0,
            "draft_count": db.query(func.count(Campaign.id)).filter(Campaign.status == "draft").scalar() or 0,
            "sent_count": db.query(func.count(Campaign.id)).filter(Campaign.status == "sent").scalar() or 0,
            "failed_count": db.query(func.count(Campaign.id)).filter(Campaign.status == "failed").scalar() or 0,
            "conversation_count": db.query(func.count(Conversation.id)).scalar() or 0,
        }
        campaigns = (
            db.query(
                Campaign.id,
                Campaign.brand_id,
                Campaign.name,
                Campaign.subject,
                Campaign.status,
                Campaign.created_at,
                func.count(CampaignRecipient.id).label("recipient_count"),
            )
            .outerjoin(CampaignRecipient, CampaignRecipient.campaign_id == Campaign.id)
            .group_by(
                Campaign.id,
                Campaign.brand_id,
                Campaign.name,
                Campaign.subject,
                Campaign.status,
                Campaign.created_at,
            )
            .order_by(Campaign.created_at.desc())
            .limit(25)
            .all()
        )
        conversations = db.query(Conversation).order_by(Conversation.last_message_at.desc()).limit(25).all()

        if preview_campaign_id:
            campaign = db.query(Campaign).filter_by(id=preview_campaign_id).one_or_none()
            if campaign is not None:
                recipient = db.query(CampaignRecipient).filter_by(campaign_id=campaign.id).first()
                if recipient is None:
                    recipient_payload = {"email": "preview@example.com", "first_name": "there"}
                    token_id = "preview-token"
                else:
                    recipient_payload = {
                        "email": recipient.email,
                        "first_name": recipient.first_name or "there",
                    }
                    token_id = recipient.token_id

                try:
                    brand_cfg = load_brand_config(campaign.brand_id)
                    token = sign_token(
                        campaign_id=campaign.id,
                        recipient=recipient_payload["email"],
                        token_id=token_id,
                    )
                    chat_endpoint = f"{settings.base_url.rstrip('/')}/api/v1/chat/message"
                    rendered = render_campaign_templates(
                        brand_cfg,
                        campaign={"subject": campaign.subject},
                        recipient=recipient_payload,
                        chat_endpoint=chat_endpoint,
                        token=token,
                    )
                    amp_simulation = {
                        "campaign_id": campaign.id,
                        "campaign_name": campaign.name,
                        "brand_id": campaign.brand_id,
                        "amp_html": rendered["amp_html"],
                    }
                except TemplateError as exc:
                    error = f"Unable to render AMP simulation: {exc}"

    return render_template(
        "admin/dashboard.html",
        brands=brands,
        stats=stats,
        campaigns=campaigns,
        conversations=conversations,
        base_url=settings.base_url,
        amp_simulation=amp_simulation,
        message=message,
        error=error,
    )


@app.post("/demo/admin/campaigns/create")
def admin_create_campaign():
    brand_id = request.form.get("brand_id", "").strip()
    name = request.form.get("name", "").strip()
    subject = request.form.get("subject", "").strip()
    from_email = request.form.get("from_email", "").strip()
    reply_to = request.form.get("reply_to", "").strip()
    recipients_raw = request.form.get("recipients", "")

    if not all([brand_id, name, subject, from_email, reply_to]):
        return redirect(url_for("admin_dashboard", error="All campaign fields are required"))

    recipients = _parse_recipients_from_text(recipients_raw)
    if not recipients:
        return redirect(url_for("admin_dashboard", error="Provide at least one recipient"))

    try:
        load_brand_config(brand_id)
    except TemplateError as exc:
        return redirect(url_for("admin_dashboard", error=f"Invalid brand config: {exc}"))

    campaign_id = str(uuid.uuid4())
    with SessionLocal() as db:
        campaign = Campaign(
            id=campaign_id,
            brand_id=brand_id,
            name=name,
            subject=subject,
            from_email=from_email,
            reply_to=reply_to,
            status="draft",
        )
        db.add(campaign)
        for recipient in recipients:
            db.add(
                CampaignRecipient(
                    campaign_id=campaign_id,
                    email=recipient["email"],
                    first_name=recipient["first_name"],
                    token_id=str(uuid.uuid4()),
                )
            )
        db.add(
            Event(
                campaign_id=campaign_id,
                event_type="campaign_created",
                payload_json=json.dumps({"name": name, "recipient_count": len(recipients)}),
            )
        )
        db.commit()

    return redirect(url_for("admin_dashboard", message=f"Campaign created: {campaign_id}"))


@app.post("/demo/admin/campaigns/<campaign_id>/send")
def admin_send_campaign(campaign_id: str):
    base_url = request.form.get("base_url", settings.base_url).strip().rstrip("/")
    chat_endpoint = f"{base_url}/api/v1/chat/message"

    sent = 0
    failures: list[dict[str, str]] = []

    with SessionLocal() as db:
        campaign = db.query(Campaign).filter_by(id=campaign_id).one_or_none()
        if campaign is None:
            return redirect(url_for("admin_dashboard", error="Campaign not found"))

        try:
            brand_cfg = load_brand_config(campaign.brand_id)
        except TemplateError as exc:
            return redirect(url_for("admin_dashboard", error=f"Invalid theme: {exc}"))

        recipients = db.query(CampaignRecipient).filter_by(campaign_id=campaign.id).all()
        campaign_payload = {"subject": campaign.subject, "from_email": campaign.from_email, "reply_to": campaign.reply_to}

        for recipient in recipients:
            token = sign_token(campaign_id=campaign.id, recipient=recipient.email, token_id=recipient.token_id)
            try:
                rendered = render_campaign_templates(
                    brand_cfg,
                    campaign={"subject": campaign.subject},
                    recipient={"email": recipient.email, "first_name": recipient.first_name or "there"},
                    chat_endpoint=chat_endpoint,
                    token=token,
                )
                message_id = send_campaign_email(
                    campaign_payload,
                    recipient.email,
                    rendered["amp_html"],
                    rendered["html_html"],
                    rendered["text_body"],
                )
                recipient.sent_at = datetime.utcnow()
                sent += 1
                db.add(
                    Event(
                        campaign_id=campaign.id,
                        event_type="campaign_send_success",
                        payload_json=json.dumps({"email": recipient.email, "message_id": message_id}),
                    )
                )
            except (TemplateError, MailerError) as exc:
                failures.append({"email": recipient.email, "error": str(exc)})
                db.add(
                    Event(
                        campaign_id=campaign.id,
                        event_type="campaign_send_failure",
                        payload_json=json.dumps({"email": recipient.email, "error": str(exc)}),
                    )
                )

        campaign.status = "sent" if sent else "failed"
        db.add(TemplateRender(campaign_id=campaign.id, brand_id=campaign.brand_id, template_version="v1"))
        db.commit()

    if failures:
        return redirect(url_for("admin_dashboard", error=f"Sent {sent}, failed {len(failures)}"))
    return redirect(url_for("admin_dashboard", message=f"Campaign sent to {sent} recipient(s)"))


@app.get("/demo/admin/conversations/<convo_id>")
def admin_conversation_detail(convo_id: str):
    with SessionLocal() as db:
        convo = db.query(Conversation).filter_by(id=convo_id).one_or_none()
        if convo is None:
            return redirect(url_for("admin_dashboard", error="Conversation not found"))
        messages = get_conversation_messages(db, convo.id)

    return render_template("admin/conversation.html", conversation=convo, messages=messages)


@app.post("/api/v1/demo/brands/sync")
def sync_brands_endpoint():
    with SessionLocal() as db:
        sync_brands_table(db)
    return jsonify({"ok": True, "request_id": g.request_id})


@app.post("/api/v1/demo/campaigns")
def create_campaign():
    data = _request_data()

    required = ["brand_id", "name", "subject", "from_email", "reply_to", "recipients"]
    for field in required:
        if field not in data:
            return _error(f"Missing required field: {field}", 400)

    recipients = data["recipients"]
    if not isinstance(recipients, list) or not recipients:
        return _error("recipients must be a non-empty list", 400)

    brand_id = str(data["brand_id"])

    try:
        load_brand_config(brand_id)
    except TemplateError as exc:
        return _error(str(exc), 400)

    campaign_id = str(uuid.uuid4())

    with SessionLocal() as db:
        sync_brands_table(db)

        campaign = Campaign(
            id=campaign_id,
            brand_id=brand_id,
            name=str(data["name"]),
            subject=str(data["subject"]),
            from_email=str(data["from_email"]),
            reply_to=str(data["reply_to"]),
            status="draft",
        )
        db.add(campaign)

        for recipient in recipients:
            email = str(recipient.get("email", "")).strip()
            if not email:
                db.rollback()
                return _error("Each recipient must include email", 400)
            db.add(
                CampaignRecipient(
                    campaign_id=campaign_id,
                    email=email,
                    first_name=str(recipient.get("first_name", "there")),
                    token_id=str(uuid.uuid4()),
                )
            )

        db.add(
            Event(
                campaign_id=campaign_id,
                event_type="campaign_created",
                payload_json=json.dumps({"name": data["name"], "recipient_count": len(recipients)}),
            )
        )
        db.commit()

    return (
        jsonify(
            {
                "campaign_id": campaign_id,
                "status": "draft",
                "recipient_count": len(recipients),
                "request_id": g.request_id,
            }
        ),
        201,
    )


@app.post("/api/v1/demo/campaigns/<campaign_id>/send")
def send_campaign(campaign_id: str):
    data = _request_data()
    base_url = str(data.get("base_url", settings.base_url)).rstrip("/")
    chat_endpoint = f"{base_url}/api/v1/chat/message"

    sent = 0
    failures: list[dict[str, str]] = []

    with SessionLocal() as db:
        campaign = db.query(Campaign).filter_by(id=campaign_id).one_or_none()
        if campaign is None:
            return _error("Campaign not found", 404)

        try:
            brand_cfg = load_brand_config(campaign.brand_id)
        except TemplateError as exc:
            return _error(str(exc), 400)

        recipients = db.query(CampaignRecipient).filter_by(campaign_id=campaign_id).all()
        if not recipients:
            return _error("Campaign has no recipients", 400)

        campaign_payload = {
            "subject": campaign.subject,
            "from_email": campaign.from_email,
            "reply_to": campaign.reply_to,
        }

        for recipient in recipients:
            token = sign_token(campaign_id=campaign.id, recipient=recipient.email, token_id=recipient.token_id)
            try:
                rendered = render_campaign_templates(
                    brand_cfg,
                    campaign={"subject": campaign.subject},
                    recipient={"email": recipient.email, "first_name": recipient.first_name or "there"},
                    chat_endpoint=chat_endpoint,
                    token=token,
                )
                message_id = send_campaign_email(
                    campaign_payload,
                    recipient.email,
                    rendered["amp_html"],
                    rendered["html_html"],
                    rendered["text_body"],
                )
                recipient.sent_at = datetime.utcnow()
                sent += 1
                db.add(
                    Event(
                        campaign_id=campaign.id,
                        event_type="campaign_send_success",
                        payload_json=json.dumps({"email": recipient.email, "message_id": message_id}),
                    )
                )
            except (TemplateError, MailerError) as exc:
                failures.append({"email": recipient.email, "error": str(exc)})
                db.add(
                    Event(
                        campaign_id=campaign.id,
                        event_type="campaign_send_failure",
                        payload_json=json.dumps({"email": recipient.email, "error": str(exc)}),
                    )
                )

        campaign.status = "sent" if sent else "failed"
        db.add(TemplateRender(campaign_id=campaign.id, brand_id=campaign.brand_id, template_version="v1"))
        db.commit()

    return jsonify(
        {
            "campaign_id": campaign_id,
            "sent": sent,
            "failed": failures,
            "status": "sent" if sent else "failed",
            "request_id": g.request_id,
        }
    )


@app.get("/api/v1/demo/preview/<brand_id>")
def preview_brand(brand_id: str):
    subject = request.args.get("subject", "Demo campaign")
    first_name = request.args.get("first_name", "there")
    preview_email = request.args.get("email", "preview@example.com")

    try:
        brand_cfg = load_brand_config(brand_id)
    except TemplateError as exc:
        return _error(str(exc), 404)

    campaign_id = f"preview-{brand_id}"
    token = sign_token(campaign_id=campaign_id, recipient=preview_email, token_id="preview-token", ttl_seconds=86400)
    chat_endpoint = f"{settings.base_url.rstrip('/')}/api/v1/chat/message"

    rendered = render_campaign_templates(
        brand_cfg,
        campaign={"subject": subject},
        recipient={"email": preview_email, "first_name": first_name},
        chat_endpoint=chat_endpoint,
        token=token,
    )

    return jsonify(
        {
            "brand_id": brand_id,
            "amp_module": rendered["amp_module"],
            "amp_html": rendered["amp_html"],
            "html_fallback": rendered["html_html"],
            "request_id": g.request_id,
        }
    )


@app.get("/demo/preview-page/<brand_id>")
def preview_page(brand_id: str):
    response = preview_brand(brand_id)
    if isinstance(response, tuple):
        return response

    body = response.get_json()["html_fallback"]
    return make_response(body, 200, {"Content-Type": "text/html; charset=utf-8"})


@app.post("/api/v1/chat/message")
@amp_response
def chat_message():
    data = _request_data()
    token = data.get("token")
    message = data.get("message")
    convo_id = data.get("convo_id") or None

    if not token:
        return _error("Missing token", 400)
    if not message:
        return _error("Missing message", 400)

    try:
        claims = verify_token(str(token))
    except TokenError as exc:
        return _error(str(exc), 401)

    campaign_id = str(claims["campaign_id"])
    recipient = str(claims["recipient"])
    token_id = str(claims["token_id"])

    with SessionLocal() as db:
        if not campaign_id.startswith("preview-"):
            recipient_row = (
                db.query(CampaignRecipient)
                .filter_by(campaign_id=campaign_id, email=recipient, token_id=token_id)
                .one_or_none()
            )
            if recipient_row is None:
                return _error("Token does not match a campaign recipient", 403)

        try:
            convo_id, response_text, latency_ms = handle_message(
                db,
                campaign_id=campaign_id,
                recipient_email=recipient,
                token_id=token_id,
                user_message=str(message),
                convo_id=str(convo_id) if convo_id else None,
            )
            db.add(
                Event(
                    campaign_id=campaign_id,
                    conversation_id=convo_id,
                    event_type="chat_response_returned",
                    payload_json=json.dumps({"latency_ms": latency_ms}),
                )
            )
            db.commit()
        except ChatServiceError as exc:
            status_code = 404 if "not found" in str(exc).lower() else 500
            db.rollback()
            return _error(str(exc), status_code)

    return jsonify({"convo_id": convo_id, "response": response_text, "request_id": g.request_id})


@app.get("/api/v1/demo/conversations")
def list_conversations():
    with SessionLocal() as db:
        rows = db.query(Conversation).order_by(Conversation.last_message_at.desc()).limit(100).all()
        payload = []
        for row in rows:
            last = (
                db.query(Message)
                .filter(Message.conversation_id == row.id)
                .order_by(Message.created_at.desc(), Message.id.desc())
                .first()
            )
            payload.append(
                {
                    "convo_id": row.id,
                    "campaign_id": row.campaign_id,
                    "recipient_email": row.recipient_email,
                    "last_message": last.content if last else "",
                    "last_message_at": row.last_message_at.isoformat() if row.last_message_at else None,
                }
            )

    return jsonify({"conversations": payload, "request_id": g.request_id})


@app.get("/api/v1/conversations/<convo_id>")
def conversation_detail(convo_id: str):
    with SessionLocal() as db:
        convo = db.query(Conversation).filter_by(id=convo_id).one_or_none()
        if convo is None:
            return _error("Conversation not found", 404)

        return jsonify(
            {
                "convo_id": convo.id,
                "campaign_id": convo.campaign_id,
                "recipient_email": convo.recipient_email,
                "messages": get_conversation_messages(db, convo.id),
                "request_id": g.request_id,
            }
        )


# Backward-compatible demo shims
@app.post("/ganggang")
@amp_response
def ganggang():
    data = _request_data()
    if data.get("auth") != settings.legacy_auth_key:
        return _error("Unauthorized", 401)

    message = data.get("message")
    if not message:
        return _error("Missing message", 400)

    convo_id = data.get("convo_id") or None

    with SessionLocal() as db:
        try:
            convo_id, reply, _ = handle_message(
                db,
                campaign_id="legacy",
                recipient_email="legacy-user@example.com",
                token_id="legacy-token",
                user_message=str(message),
                convo_id=str(convo_id) if convo_id else None,
            )
        except ChatServiceError as exc:
            return _error(str(exc), 500)

    return jsonify({"convo_id": convo_id, "response": reply, "request_id": g.request_id})


@app.post("/bangbang")
@amp_response
def bangbang():
    data = _request_data()
    convo_id = data.get("convo_id")
    if not convo_id:
        return _error("Missing convo_id", 400)

    with SessionLocal() as db:
        convo = db.query(Conversation).filter_by(id=str(convo_id)).one_or_none()
        if convo is None:
            return _error("Conversation not found", 404)

        return jsonify(get_conversation_messages(db, convo.id))


if __name__ == "__main__":
    app.run(port=8000, debug=True)
