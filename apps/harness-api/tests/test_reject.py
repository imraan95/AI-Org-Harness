"""T056: POST /knowledge/{id}/reject against a REAL running OpenViking.

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


def _fixture_record(*, status: str) -> KnowledgeRecord:
    now = datetime.now(timezone.utc)
    return KnowledgeRecord(
        id=f"K-t056-{uuid.uuid4()}",
        type="fact",
        topic=f"t056_{uuid.uuid4().hex[:8]}",
        statement="Fixture statement for T056's reject test.",
        status=status,
        confidence=0.75,
        source_ids=["meeting_fixture"],
        people=["Alice"],
        created_at=now,
        observed_at=now,
        last_updated_at=now,
    )


async def test_reject_flips_a_pending_review_record_to_rejected():
    record = _fixture_record(status="pending_review")
    openviking = RealOpenVikingClient()
    try:
        await openviking.write_knowledge(record)
    finally:
        await openviking.aclose()

    client = TestClient(app)
    response = client.post(f"/knowledge/{record.id}/reject", headers=_AUTH_HEADERS)

    assert response.status_code == 200
    assert response.json()["status"] == "rejected"


def test_reject_returns_404_for_unknown_id():
    client = TestClient(app)
    response = client.post(
        f"/knowledge/K-does-not-exist-{uuid.uuid4()}/reject", headers=_AUTH_HEADERS
    )

    assert response.status_code == 404


def test_reject_returns_401_without_a_token_or_service_key():
    client = TestClient(app)
    response = client.post(f"/knowledge/K-does-not-exist-{uuid.uuid4()}/reject")

    assert response.status_code == 401
