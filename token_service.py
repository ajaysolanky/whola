import base64
import hashlib
import hmac
import json
import time
import uuid
from typing import Any

from app_config import settings


class TokenError(Exception):
    pass


def _b64_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64_decode(data: str) -> bytes:
    pad = "=" * ((4 - (len(data) % 4)) % 4)
    return base64.urlsafe_b64decode(data + pad)


def sign_token(campaign_id: str, recipient: str, token_id: str | None = None, ttl_seconds: int = 86400) -> str:
    now = int(time.time())
    payload = {
        "campaign_id": campaign_id,
        "recipient": recipient,
        "token_id": token_id or str(uuid.uuid4()),
        "iat": now,
        "exp": now + ttl_seconds,
    }
    payload_raw = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    signature = hmac.new(settings.app_secret.encode("utf-8"), payload_raw, hashlib.sha256).digest()
    return f"{_b64_encode(payload_raw)}.{_b64_encode(signature)}"


def verify_token(token: str) -> dict[str, Any]:
    try:
        payload_part, sig_part = token.split(".", 1)
        payload_raw = _b64_decode(payload_part)
        actual_sig = _b64_decode(sig_part)
    except Exception as exc:  # noqa: BLE001
        raise TokenError("Malformed token") from exc

    expected_sig = hmac.new(settings.app_secret.encode("utf-8"), payload_raw, hashlib.sha256).digest()
    if not hmac.compare_digest(actual_sig, expected_sig):
        raise TokenError("Invalid signature")

    try:
        payload = json.loads(payload_raw.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise TokenError("Invalid payload") from exc

    now = int(time.time())
    if payload.get("exp") is None or now >= int(payload["exp"]):
        raise TokenError("Token expired")

    required = {"campaign_id", "recipient", "token_id", "iat", "exp"}
    if not required.issubset(payload.keys()):
        raise TokenError("Missing required claims")

    return payload
