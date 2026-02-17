from __future__ import annotations

import re
import time
import uuid
from datetime import datetime

import requests
from sqlalchemy import asc

from app_config import settings
from models import Conversation, Event, Message


class ChatServiceError(Exception):
    pass


MAX_ASSISTANT_REPLY_CHARS = 560
MAX_ASSISTANT_REPLY_LINES = 6


def _normalize_assistant_reply(content: str) -> str:
    """Keep assistant output readable inside constrained AMP chat viewports."""
    text = (content or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return "I can help with fit, materials, shipping, and recommendations. What would you like to know?"

    # Remove markdown-heavy formatting that renders poorly in AMP chat bubbles.
    text = re.sub(r"`{1,3}", "", text)
    text = re.sub(r"\*\*(.*?)\*\*", r"\1", text)
    text = re.sub(r"^\s{0,3}(#{1,6}|\*|-|\d+\.)\s*", "", text, flags=re.MULTILINE)
    text = re.sub(r"\n{3,}", "\n\n", text)

    lines = [line.strip() for line in text.split("\n") if line.strip()]
    if len(lines) > MAX_ASSISTANT_REPLY_LINES:
        lines = lines[:MAX_ASSISTANT_REPLY_LINES]
    text = " ".join(lines)
    text = re.sub(r"\s{2,}", " ", text).strip()

    if len(text) > MAX_ASSISTANT_REPLY_CHARS:
        text = text[: MAX_ASSISTANT_REPLY_CHARS - 1].rstrip() + "…"

    return text


def _provider_messages(db_session, conversation_id: str) -> list[dict[str, str]]:
    history = (
        db_session.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(asc(Message.created_at), asc(Message.id))
        .all()
    )
    messages = [{"role": "system", "content": settings.chat_system_prompt}]
    messages.extend({"role": m.role, "content": m.content} for m in history)
    return messages


def _call_openrouter(messages: list[dict[str, str]]) -> tuple[str, int]:
    if not settings.openrouter_api_key:
        raise ChatServiceError("Missing OpenRouter API key")

    payload = {"model": settings.openrouter_model, "messages": messages}
    headers = {
        "Authorization": f"Bearer {settings.openrouter_api_key}",
        "Content-Type": "application/json",
    }

    last_error: Exception | None = None
    for attempt in range(settings.provider_retries + 1):
        start = time.monotonic()
        try:
            response = requests.post(
                settings.openrouter_chat_completions_url,
                headers=headers,
                json=payload,
                timeout=settings.request_timeout_sec,
            )
            latency_ms = int((time.monotonic() - start) * 1000)

            if response.status_code != 200:
                raise ChatServiceError(f"Provider returned {response.status_code}: {response.text[:500]}")

            body = response.json()
            content = body["choices"][0]["message"]["content"]
            return content, latency_ms
        except Exception as exc:  # noqa: BLE001
            last_error = exc
            if attempt >= settings.provider_retries:
                break
            time.sleep(0.5 * (2**attempt))

    raise ChatServiceError(f"Failed to fetch response from model provider: {last_error}")


def _get_or_create_conversation(db_session, campaign_id: str, recipient_email: str, token_id: str, convo_id: str | None):
    if convo_id:
        convo = db_session.query(Conversation).filter_by(id=convo_id).one_or_none()
        if convo is None:
            raise ChatServiceError("Conversation not found")
        if convo.campaign_id != campaign_id or convo.recipient_email != recipient_email:
            raise ChatServiceError("Conversation ownership mismatch")
        return convo

    convo = Conversation(
        id=str(uuid.uuid4()),
        campaign_id=campaign_id,
        recipient_email=recipient_email,
        token_id=token_id,
    )
    db_session.add(convo)
    db_session.flush()
    return convo


def handle_message(
    db_session,
    campaign_id: str,
    recipient_email: str,
    token_id: str,
    user_message: str,
    convo_id: str | None = None,
) -> tuple[str, str, int]:
    convo = _get_or_create_conversation(db_session, campaign_id, recipient_email, token_id, convo_id)

    db_session.add(
        Message(
            conversation_id=convo.id,
            role="user",
            content=user_message,
            provider="inbox",
            created_at=datetime.utcnow(),
        )
    )
    db_session.flush()

    provider_messages = _provider_messages(db_session, convo.id)
    assistant_reply, latency_ms = _call_openrouter(provider_messages)
    assistant_reply = _normalize_assistant_reply(assistant_reply)

    db_session.add(
        Message(
            conversation_id=convo.id,
            role="assistant",
            content=assistant_reply,
            provider="openrouter",
            latency_ms=latency_ms,
            created_at=datetime.utcnow(),
        )
    )
    convo.last_message_at = datetime.utcnow()

    db_session.add(
        Event(
            campaign_id=campaign_id,
            conversation_id=convo.id,
            event_type="chat_message_completed",
            payload_json=f'{{"latency_ms": {latency_ms}}}',
        )
    )
    db_session.commit()
    return convo.id, assistant_reply, latency_ms


def get_conversation_messages(db_session, convo_id: str) -> list[dict[str, str]]:
    rows = (
        db_session.query(Message)
        .filter(Message.conversation_id == convo_id)
        .order_by(asc(Message.created_at), asc(Message.id))
        .all()
    )
    return [
        {
            "role": row.role,
            "content": row.content,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
        for row in rows
    ]
