import hashlib
import hmac
import json
import logging

from fastapi.testclient import TestClient

from ingestion_service.main import ANARLOG_WEBHOOK_SECRET, app

# Matches main.py's ANARLOG_WEBHOOK_SECRET fallback - tests sign with the
# same secret the app verifies against, same as a real Anarlog webhook
# would with its own registered whsec_... secret.
_SECRET = ANARLOG_WEBHOOK_SECRET


def _signed_post(client: TestClient, payload: dict):
    body = json.dumps(payload).encode()
    signature = "sha256=" + hmac.new(_SECRET.encode(), body, hashlib.sha256).hexdigest()
    return client.post(
        "/webhooks/anarlog",
        content=body,
        headers={
            "content-type": "application/json",
            "x-anarlog-signature": signature,
        },
    )


def test_webhook_endpoint_returns_200_and_logs_the_payload(caplog):
    client = TestClient(app)
    payload = {"event": "transcript.created", "meeting_id": "meeting_fixture_1"}

    with caplog.at_level(logging.INFO, logger="ingestion_service.main"):
        response = _signed_post(client, payload)

    assert response.status_code == 200
    assert response.json() == {"status": "received"}
    assert any(
        "meeting_fixture_1" in record.message for record in caplog.records
    ), "expected the raw payload to be logged"


def test_webhook_endpoint_rejects_a_bad_signature():
    client = TestClient(app)
    payload = {"event": "transcript.created", "meeting_id": "meeting_fixture_1"}
    body = json.dumps(payload).encode()

    response = client.post(
        "/webhooks/anarlog",
        content=body,
        headers={
            "content-type": "application/json",
            "x-anarlog-signature": "sha256=not-a-real-signature",
        },
    )

    assert response.status_code == 401


def test_webhook_endpoint_rejects_a_missing_signature():
    client = TestClient(app)
    payload = {"event": "transcript.created", "meeting_id": "meeting_fixture_1"}

    response = client.post("/webhooks/anarlog", json=payload)

    assert response.status_code == 401
