import uuid

import chat_service
from database import SessionLocal
from models import Campaign, CampaignRecipient
from server import app
from token_service import sign_token


def _seed_campaign_and_recipient(campaign_id: str, email: str, token_id: str) -> None:
    with SessionLocal() as db:
        existing = db.query(Campaign).filter_by(id=campaign_id).one_or_none()
        if existing is None:
            db.add(
                Campaign(
                    id=campaign_id,
                    brand_id="acme",
                    name="Test Campaign",
                    subject="Testing",
                    from_email="sender@example.com",
                    reply_to="reply@example.com",
                    status="draft",
                )
            )
        db.add(
            CampaignRecipient(
                campaign_id=campaign_id,
                email=email,
                first_name="Test",
                token_id=token_id,
            )
        )
        db.commit()


def test_chat_message_success(monkeypatch):
    monkeypatch.setattr(chat_service, "_call_openrouter", lambda messages: ("stubbed", 9))
    client = app.test_client()

    campaign_id = str(uuid.uuid4())
    token_id = str(uuid.uuid4())
    email = "chat-success@example.com"
    _seed_campaign_and_recipient(campaign_id, email, token_id)

    token = sign_token(campaign_id, email, token_id=token_id, ttl_seconds=600)

    response = client.post(
        "/api/v1/chat/message",
        json={"token": token, "message": "hello"},
    )

    assert response.status_code == 200
    payload = response.get_json()
    assert payload["response"] == "stubbed"
    assert payload["convo_id"]


def test_chat_message_rejects_invalid_token(monkeypatch):
    monkeypatch.setattr(chat_service, "_call_openrouter", lambda messages: ("stubbed", 9))
    client = app.test_client()

    response = client.post(
        "/api/v1/chat/message",
        json={"token": "not-a-real-token", "message": "hello"},
    )

    assert response.status_code == 401


def test_chat_message_rejects_expired_token(monkeypatch):
    monkeypatch.setattr(chat_service, "_call_openrouter", lambda messages: ("stubbed", 9))
    client = app.test_client()

    campaign_id = str(uuid.uuid4())
    token_id = str(uuid.uuid4())
    email = "chat-expired@example.com"
    _seed_campaign_and_recipient(campaign_id, email, token_id)

    token = sign_token(campaign_id, email, token_id=token_id, ttl_seconds=-10)
    response = client.post(
        "/api/v1/chat/message",
        json={"token": token, "message": "hello"},
    )

    assert response.status_code == 401
