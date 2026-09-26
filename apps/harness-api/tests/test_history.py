"""T059: GET /knowledge/{id}/history, seeding fixtures through whichever
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


def _fixture_record(*, statement: str, supersedes: str | None = None) -> KnowledgeRecord:
    now = datetime.now(timezone.utc)
    return KnowledgeRecord(
        id=f"K-t059-{uuid.uuid4()}",
        type="fact",
        topic=f"t059_{uuid.uuid4().hex[:8]}",
        statement=statement,
        status="active",
        confidence=0.75,
        source_ids=["meeting_fixture"],
        people=[],
        created_at=now,
        observed_at=now,
        last_updated_at=now,
        supersedes=supersedes,
    )


async def _seed(record: KnowledgeRecord) -> None:
    openviking = get_knowledge_store()
    try:
        await openviking.write_knowledge(record)
    finally:
        await openviking.aclose()


async def test_history_walks_the_full_supersedes_chain_newest_to_oldest():
    oldest = _fixture_record(statement="v1")
    middle = _fixture_record(statement="v2", supersedes=oldest.id)
    newest = _fixture_record(statement="v3", supersedes=middle.id)
    await _seed(oldest)
    await _seed(middle)
    await _seed(newest)

    client = TestClient(app)
    response = client.get(f"/knowledge/{newest.id}/history", headers=_AUTH_HEADERS)

    assert response.status_code == 200
    ids_in_order = [r["id"] for r in response.json()]
    assert ids_in_order == [newest.id, middle.id, oldest.id]


async def test_history_of_a_record_with_no_supersedes_returns_just_itself():
    record = _fixture_record(statement="only version")
    await _seed(record)

    client = TestClient(app)
    response = client.get(f"/knowledge/{record.id}/history", headers=_AUTH_HEADERS)

    assert response.status_code == 200
    assert [r["id"] for r in response.json()] == [record.id]


def test_history_returns_404_for_unknown_id():
    client = TestClient(app)
    response = client.get(
        f"/knowledge/K-does-not-exist-{uuid.uuid4()}/history", headers=_AUTH_HEADERS
    )

    assert response.status_code == 404


def test_history_returns_401_without_a_token_or_service_key():
    client = TestClient(app)
    response = client.get(f"/knowledge/K-does-not-exist-{uuid.uuid4()}/history")

    assert response.status_code == 401
