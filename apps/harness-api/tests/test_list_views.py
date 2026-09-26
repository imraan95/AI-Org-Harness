"""T053: GET /decisions, GET /people, GET /conflicts, seeding fixtures
through whichever knowledge store harness-api is actually configured to
use (get_knowledge_store() - Postgres by default, see
openviking_client's router.py). No skip-guard needed: matches every
other Postgres-backed test in this codebase (e.g. libs/db's own tests).
Uses the static service key (T052) for auth rather than a Supabase user,
since these tests are about filtering behaviour, not auth - that's
already covered separately.
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


def _fixture_record(
    *, type: str, topic: str, statement: str, status: str = "active"
) -> KnowledgeRecord:
    now = datetime.now(timezone.utc)
    return KnowledgeRecord(
        id=f"K-t053-{uuid.uuid4()}",
        type=type,
        topic=topic,
        statement=statement,
        status=status,
        confidence=0.75,
        source_ids=["meeting_fixture"],
        people=["Alice"],
        created_at=now,
        observed_at=now,
        last_updated_at=now,
    )


async def _seed(record: KnowledgeRecord) -> None:
    openviking = get_knowledge_store()
    try:
        await openviking.write_knowledge(record)
    finally:
        await openviking.aclose()


async def test_get_decisions_returns_only_decision_records():
    run_id = uuid.uuid4().hex[:8]
    decision = _fixture_record(
        type="decision", topic=f"t053_decision_{run_id}", statement="We picked X."
    )
    person = _fixture_record(
        type="person", topic=f"t053_person_{run_id}", statement="Alice owns Y."
    )
    await _seed(decision)
    await _seed(person)

    client = TestClient(app)
    response = client.get("/decisions", headers=_AUTH_HEADERS)

    assert response.status_code == 200
    ids = {r["id"] for r in response.json()}
    assert decision.id in ids
    assert person.id not in ids


async def test_get_people_returns_only_person_records():
    run_id = uuid.uuid4().hex[:8]
    decision = _fixture_record(
        type="decision", topic=f"t053_decision2_{run_id}", statement="We picked X."
    )
    person = _fixture_record(
        type="person", topic=f"t053_person2_{run_id}", statement="Alice owns Y."
    )
    await _seed(decision)
    await _seed(person)

    client = TestClient(app)
    response = client.get("/people", headers=_AUTH_HEADERS)

    assert response.status_code == 200
    ids = {r["id"] for r in response.json()}
    assert person.id in ids
    assert decision.id not in ids


async def test_get_conflicts_returns_only_conflicting_status_records():
    run_id = uuid.uuid4().hex[:8]
    conflicting = _fixture_record(
        type="fact",
        topic=f"t053_conflict_{run_id}",
        statement="Two versions of this fact disagree.",
        status="conflicting",
    )
    active = _fixture_record(
        type="fact",
        topic=f"t053_active_{run_id}",
        statement="This fact is settled.",
        status="active",
    )
    await _seed(conflicting)
    await _seed(active)

    client = TestClient(app)
    response = client.get("/conflicts", headers=_AUTH_HEADERS)

    assert response.status_code == 200
    ids = {r["id"] for r in response.json()}
    assert conflicting.id in ids
    assert active.id not in ids


def test_get_decisions_returns_401_without_a_token_or_service_key():
    client = TestClient(app)
    response = client.get("/decisions")

    assert response.status_code == 401
