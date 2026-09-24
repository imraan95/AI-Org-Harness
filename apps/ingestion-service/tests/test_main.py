import logging

from fastapi.testclient import TestClient

from ingestion_service.main import app


def test_webhook_endpoint_returns_200_and_logs_the_payload(caplog):
    client = TestClient(app)
    payload = {"event": "transcript.created", "meeting_id": "meeting_fixture_1"}

    with caplog.at_level(logging.INFO, logger="ingestion_service.main"):
        response = client.post("/webhooks/anarlog", json=payload)

    assert response.status_code == 200
    assert response.json() == {"status": "received"}
    assert any(
        "meeting_fixture_1" in record.message for record in caplog.records
    ), "expected the raw payload to be logged"
