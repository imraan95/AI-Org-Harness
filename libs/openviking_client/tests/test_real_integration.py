"""Integration tests against a REAL, running OpenViking service (T035-T037).

Unlike every other test in this repo, this one is NOT a fake/unit test - it
makes real HTTP calls to the container started in infra/docker-compose.yml.
It skips itself automatically if that service isn't reachable, so
`uv run pytest --all-packages` still passes on a machine with nothing
running (e.g. CI, or a laptop that hasn't started the container yet).
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

import httpx
import pytest

from knowledge_model import KnowledgeRecord, KnowledgeStatus, KnowledgeType
from openviking_client import RealOpenVikingClient

BASE_URL = os.environ.get("OPENVIKING_BASE_URL", "http://127.0.0.1:1933")


def _service_is_up() -> bool:
    try:
        response = httpx.get(f"{BASE_URL}/health", timeout=2.0)
        return response.status_code == 200 and response.json().get("status") == "ok"
    except httpx.HTTPError:
        return False


pytestmark = pytest.mark.skipif(
    not _service_is_up(),
    reason=(
        "No OpenViking service reachable at "
        f"{BASE_URL} - start it with "
        "`docker compose -f infra/docker-compose.yml up openviking`"
    ),
)


def _knowledge_record(
    *,
    topic: str = "enterprise_sso",
    statement: str = "...",
    status: str = "active",
    type: str = "customer_insight",
) -> KnowledgeRecord:
    now = datetime.now(timezone.utc)
    return KnowledgeRecord(
        id=f"K-{uuid.uuid4()}",
        type=type,
        topic=topic,
        statement=statement,
        status=status,
        confidence=0.6,
        source_ids=["meeting_test"],
        people=[],
        created_at=now,
        observed_at=now,
        last_updated_at=now,
    )


async def test_write_then_read_back_by_id_round_trips():
    client = RealOpenVikingClient()
    record = _knowledge_record()

    await client.write_knowledge(record)
    fetched = await client.get_knowledge_by_id(record.id)

    assert fetched == record

    await client.aclose()


async def test_get_knowledge_by_id_returns_none_for_unknown_id():
    client = RealOpenVikingClient()

    fetched = await client.get_knowledge_by_id(f"K-{uuid.uuid4()}")

    assert fetched is None

    await client.aclose()


async def test_get_relevant_knowledge_returns_only_the_matching_topic():
    # Unique topic names per run so leftover data from earlier test runs
    # (this container's storage persists across runs) can't cause a false
    # match or inflate the count.
    run_id = uuid.uuid4().hex[:8]
    topic_a = f"topic_a_{run_id}"
    topic_b = f"topic_b_{run_id}"

    client = RealOpenVikingClient()
    record_a = _knowledge_record(topic=topic_a, statement="About topic A.")
    record_b = _knowledge_record(topic=topic_b, statement="About topic B.")

    await client.write_knowledge(record_a)
    await client.write_knowledge(record_b)

    results = await client.get_relevant_knowledge(topic_a)

    assert [r.id for r in results] == [record_a.id]
    assert results[0] == record_a

    await client.aclose()


async def test_list_conflicts_includes_conflicting_records():
    run_id = uuid.uuid4().hex[:8]
    client = RealOpenVikingClient()
    conflict_1 = _knowledge_record(
        topic=f"conflict_a_{run_id}", statement="Version A.", status="conflicting"
    )
    conflict_2 = _knowledge_record(
        topic=f"conflict_b_{run_id}", statement="Version B.", status="conflicting"
    )

    await client.write_knowledge(conflict_1)
    await client.write_knowledge(conflict_2)

    conflicts = await client.list_conflicts()
    conflict_ids = {r.id for r in conflicts}

    # "confirms both appear" (build-plan T037) - not an exact-length
    # assertion, since this container's storage persists across test runs
    # and may hold conflicting records from earlier runs too.
    assert {conflict_1.id, conflict_2.id}.issubset(conflict_ids)
    assert all(r.status == KnowledgeStatus.CONFLICTING for r in conflicts)

    await client.aclose()


async def test_list_by_type_includes_only_matching_type_records():
    run_id = uuid.uuid4().hex[:8]
    client = RealOpenVikingClient()
    decision = _knowledge_record(
        topic=f"decision_{run_id}", statement="We picked X.", type="decision"
    )
    person = _knowledge_record(
        topic=f"person_{run_id}", statement="Alice owns Y.", type="person"
    )

    await client.write_knowledge(decision)
    await client.write_knowledge(person)

    decisions = await client.list_by_type(KnowledgeType.DECISION)
    decision_ids = {r.id for r in decisions}

    # Same "subset, not exact count" reasoning as list_conflicts above -
    # this container's storage persists across runs.
    assert decision.id in decision_ids
    assert person.id not in decision_ids
    assert all(r.type == KnowledgeType.DECISION for r in decisions)

    await client.aclose()


async def test_permissions_scaffold_fields_round_trip():
    """T039: workspace_id/etc. are just ordinary KnowledgeRecord fields now
    (ADR 0003) - confirm they survive a real write/read cycle like any
    other field."""
    client = RealOpenVikingClient()
    record = _knowledge_record(topic=f"perm_scaffold_{uuid.uuid4().hex[:8]}")
    record = record.model_copy(
        update={
            "workspace_id": "acme",
            "source_id": "anarlog",
            "visibility": "confidential",
            "owner": "person_12",
            "access_level": "restricted",
        }
    )

    await client.write_knowledge(record)
    fetched = await client.get_knowledge_by_id(record.id)

    assert fetched == record

    await client.aclose()


async def test_update_knowledge_status_persists():
    client = RealOpenVikingClient()
    record = _knowledge_record(topic=f"status_update_{uuid.uuid4().hex[:8]}")
    await client.write_knowledge(record)

    await client.update_knowledge_status(record.id, KnowledgeStatus.SUPERSEDED)
    refetched = await client.get_knowledge_by_id(record.id)

    assert refetched is not None
    assert refetched.status == KnowledgeStatus.SUPERSEDED
    # Everything else about the record should be untouched.
    assert refetched.model_copy(update={"status": record.status}) == record

    await client.aclose()
