"""T057: POST /knowledge/{id}/edit against a REAL running OpenViking.

Same skip-guard and service-key-auth approach as test_approve.py.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from knowledge_model import KnowledgeRecord
from openviking_client import RealOpenVikingClient

from harness_api.auth import HARNESS_API_SERVICE_KEY
from harness_api.main import app

OPENVIKING_BASE_URL = os.environ.get("OPENVIKING_BASE_URL", "http://127.0.0.1:1933")


def _openviking_is_up() -> bool:
    try:
        response = httpx.get(f"{OPENVIKING_BASE_URL}/health", timeout=2.0)
        return response.status_code == 200 and response.json().get("status") == "ok"
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not (_openviking_is_up() and os.environ.get("OPENVIKING_API_KEY")),
    reason="Needs a running OpenViking + OPENVIKING_API_KEY (see docs/research/openviking.md §7).",
)

_AUTH_HEADERS = {"x-service-key": HARNESS_API_SERVICE_KEY}


def _fixture_record() -> KnowledgeRecord:
    now = datetime.now(timezone.utc)
    return KnowledgeRecord(
        id=f"K-t057-{uuid.uuid4()}",
        type="fact",
        topic=f"t057_{uuid.uuid4().hex[:8]}",
        statement="Original statement for T057's edit test.",
        status="pending_review",
        confidence=0.5,
        source_ids=["meeting_fixture"],
        people=["Alice"],
        created_at=now,
        observed_at=now,
        last_updated_at=now,
    )


async def test_edit_updates_statement_and_sets_edited_by():
    record = _fixture_record()
    openviking = RealOpenVikingClient()
    try:
        await openviking.write_knowledge(record)
    finally:
        await openviking.aclose()

    client = TestClient(app)
    response = client.post(
        f"/knowledge/{record.id}/edit",
        headers=_AUTH_HEADERS,
        json={"edited_by": "alice@rms.test", "statement": "Corrected statement."},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["statement"] == "Corrected statement."
    assert body["edited_by"] == "alice@rms.test"
    # Unedited fields are untouched.
    assert body["topic"] == record.topic
    assert body["status"] == "pending_review"


async def test_edit_can_change_type_to_a_valid_custom_type():
    record = _fixture_record()
    openviking = RealOpenVikingClient()
    try:
        await openviking.write_knowledge(record)
    finally:
        await openviking.aclose()

    key = f"t077_{uuid.uuid4().hex[:8]}"
    client = TestClient(app)
    created = client.post(
        "/taxonomy/types",
        headers=_AUTH_HEADERS,
        json={"key": key, "label": "Meeting Notes"},
    )
    assert created.status_code == 201

    response = client.post(
        f"/knowledge/{record.id}/edit",
        headers=_AUTH_HEADERS,
        json={"edited_by": "alice@rms.test", "type": key},
    )

    assert response.status_code == 200
    assert response.json()["type"] == key

    client.delete(f"/taxonomy/types/{key}", headers=_AUTH_HEADERS)


async def test_edit_rejects_an_unknown_type():
    record = _fixture_record()
    openviking = RealOpenVikingClient()
    try:
        await openviking.write_knowledge(record)
    finally:
        await openviking.aclose()

    client = TestClient(app)
    response = client.post(
        f"/knowledge/{record.id}/edit",
        headers=_AUTH_HEADERS,
        json={"edited_by": "alice@rms.test", "type": "not_a_real_type"},
    )

    assert response.status_code == 400


def test_edit_returns_404_for_unknown_id():
    client = TestClient(app)
    response = client.post(
        f"/knowledge/K-does-not-exist-{uuid.uuid4()}/edit",
        headers=_AUTH_HEADERS,
        json={"edited_by": "alice@rms.test", "statement": "Anything."},
    )

    assert response.status_code == 404


def test_edit_returns_401_without_a_token_or_service_key():
    client = TestClient(app)
    response = client.post(
        f"/knowledge/K-does-not-exist-{uuid.uuid4()}/edit",
        json={"edited_by": "alice@rms.test", "statement": "Anything."},
    )

    assert response.status_code == 401
