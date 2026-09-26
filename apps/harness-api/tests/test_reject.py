"""T056: POST /knowledge/{id}/reject, seeding fixtures through whichever
knowledge store harness-api is actually configured to use
(get_knowledge_store() - Postgres by default, see openviking_client's
router.py). No skip-guard needed: matches every other Postgres-backed
test in this codebase (e.g. libs/db's own tests).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from fastapi.testclient import TestClient
from knowledge_model import KnowledgeRecord
from openviking_client import get_knowledge_store

from harness_api.auth import HARNESS_API_SERVICE_KEY
from harness_api.main import app

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
    openviking = get_knowledge_store()
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
