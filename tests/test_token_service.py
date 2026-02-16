import pytest

from token_service import TokenError, sign_token, verify_token


def test_token_roundtrip():
    token = sign_token("cmp-1", "alice@example.com", token_id="tok-1", ttl_seconds=60)
    payload = verify_token(token)

    assert payload["campaign_id"] == "cmp-1"
    assert payload["recipient"] == "alice@example.com"
    assert payload["token_id"] == "tok-1"


def test_token_tamper_rejected():
    token = sign_token("cmp-2", "bob@example.com", token_id="tok-2", ttl_seconds=60)
    payload_part, sig_part = token.split(".", 1)
    tampered_payload = ("A" if payload_part[0] != "A" else "B") + payload_part[1:]
    bad = f"{tampered_payload}.{sig_part}"

    with pytest.raises(TokenError):
        verify_token(bad)


def test_token_expired_rejected():
    token = sign_token("cmp-3", "cory@example.com", token_id="tok-3", ttl_seconds=-1)

    with pytest.raises(TokenError):
        verify_token(token)
