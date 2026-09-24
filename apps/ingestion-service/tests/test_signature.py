"""T049: the pure signature-verification function, independent of the
FastAPI endpoint (see test_webhook_persistence.py / test_main.py for the
endpoint-level 401/pass-through behaviour)."""

import hashlib
import hmac

from ingestion_service import verify_signature

SECRET = "test-secret"
BODY = b'{"event": "webhook.test"}'


def _sign(secret: str, body: bytes) -> str:
    return "sha256=" + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()


def test_valid_signature_is_accepted():
    assert verify_signature(SECRET, BODY, _sign(SECRET, BODY)) is True


def test_missing_signature_header_is_rejected():
    assert verify_signature(SECRET, BODY, None) is False


def test_empty_signature_header_is_rejected():
    assert verify_signature(SECRET, BODY, "") is False


def test_wrong_secret_is_rejected():
    assert verify_signature(SECRET, BODY, _sign("wrong-secret", BODY)) is False


def test_tampered_body_is_rejected():
    valid_signature = _sign(SECRET, BODY)
    tampered_body = BODY + b"tampered"
    assert verify_signature(SECRET, tampered_body, valid_signature) is False


def test_missing_prefix_is_rejected():
    raw_hex = hmac.new(SECRET.encode(), BODY, hashlib.sha256).hexdigest()
    assert verify_signature(SECRET, BODY, raw_hex) is False
