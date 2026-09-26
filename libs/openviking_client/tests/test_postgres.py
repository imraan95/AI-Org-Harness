"""PostgresOpenVikingClient exercised through the same OpenVikingClient
interface as test_fake.py/test_real_integration.py - against a real local
Postgres (same assumption as libs/db's own tests: no skip guard needed,
just a running `supabase start`/`db reset`), not a running OpenViking.
"""

import uuid
from datetime import datetime, timezone

from db import get_engine, get_session_factory
from knowledge_model import KnowledgeRecord, KnowledgeStatus, KnowledgeType

from openviking_client import PostgresOpenVikingClient


def _record(**overrides) -> KnowledgeRecord:
    now = datetime.now(timezone.utc)
    kwargs = dict(
        id=f"K-pgtest-{uuid.uuid4()}",
        type="customer_insight",
        topic=f"topic_{uuid.uuid4().hex[:8]}",
        statement="SSO is becoming a recurring enterprise requirement",
        status="active",
        confidence=0.82,
        source_ids=["meeting_123"],
        people=["person_12"],
        created_at=now,
        observed_at=now,
        last_updated_at=now,
    )
    kwargs.update(overrides)
    return KnowledgeRecord(**kwargs)


def _client(engine) -> PostgresOpenVikingClient:
    return PostgresOpenVikingClient(session_factory=get_session_factory(engine))


async def test_write_then_get_by_id():
    engine = get_engine()
    client = _client(engine)
    record = _record()

    await client.write_knowledge(record)
    fetched = await client.get_knowledge_by_id(record.id)

    assert fetched is not None
    assert fetched.id == record.id
    await engine.dispose()


async def test_get_relevant_knowledge_is_an_exact_topic_match():
    engine = get_engine()
    client = _client(engine)
    record = _record()
    await client.write_knowledge(record)

    exact = await client.get_relevant_knowledge(record.topic)
    prefix_only = await client.get_relevant_knowledge(record.topic[:5])

    assert len(exact) == 1
    assert exact[0].id == record.id
    assert prefix_only == []
    await engine.dispose()


async def test_list_by_type_matches_only_that_type():
    engine = get_engine()
    client = _client(engine)
    decision = _record(type="decision")
    person = _record(type="person")
    await client.write_knowledge(decision)
    await client.write_knowledge(person)

    results = await client.list_by_type(KnowledgeType.DECISION)

    ids = {r.id for r in results}
    assert decision.id in ids
    assert person.id not in ids
    await engine.dispose()


async def test_list_conflicts_returns_only_conflicting_status():
    engine = get_engine()
    client = _client(engine)
    conflicting = _record(status="conflicting")
    active = _record(status="active")
    await client.write_knowledge(conflicting)
    await client.write_knowledge(active)

    results = await client.list_conflicts()

    ids = {r.id for r in results}
    assert conflicting.id in ids
    assert active.id not in ids
    await engine.dispose()


async def test_update_knowledge_fields_persists_and_sets_edited_by():
    engine = get_engine()
    client = _client(engine)
    record = _record(statement="Original statement.")
    await client.write_knowledge(record)

    await client.update_knowledge_fields(
        record.id, {"statement": "Edited statement."}, edited_by="alice@rms.test"
    )
    refetched = await client.get_knowledge_by_id(record.id)

    assert refetched is not None
    assert refetched.statement == "Edited statement."
    assert refetched.edited_by == "alice@rms.test"
    await engine.dispose()


async def test_update_knowledge_status_changes_status():
    engine = get_engine()
    client = _client(engine)
    record = _record(status="pending_review")
    await client.write_knowledge(record)

    await client.update_knowledge_status(record.id, KnowledgeStatus.ACTIVE)
    refetched = await client.get_knowledge_by_id(record.id)

    assert refetched is not None
    assert refetched.status == KnowledgeStatus.ACTIVE
    await engine.dispose()


async def test_mark_superseded_sets_status_and_timestamp():
    engine = get_engine()
    client = _client(engine)
    record = _record()
    await client.write_knowledge(record)

    when = datetime.now(timezone.utc)
    await client.mark_superseded(record.id, when)
    refetched = await client.get_knowledge_by_id(record.id)

    assert refetched is not None
    assert refetched.status == KnowledgeStatus.SUPERSEDED
    assert refetched.superseded_at == when
    await engine.dispose()


async def test_write_knowledge_replaces_an_existing_record_with_the_same_id():
    engine = get_engine()
    client = _client(engine)
    record = _record(statement="First version.")
    await client.write_knowledge(record)

    replaced = record.model_copy(update={"statement": "Second version."})
    await client.write_knowledge(replaced)
    refetched = await client.get_knowledge_by_id(record.id)

    assert refetched is not None
    assert refetched.statement == "Second version."
    await engine.dispose()


async def test_list_all_returns_every_written_record():
    engine = get_engine()
    client = _client(engine)
    a = _record()
    b = _record()
    await client.write_knowledge(a)
    await client.write_knowledge(b)

    results = await client.list_all()

    ids = {r.id for r in results}
    assert a.id in ids
    assert b.id in ids
    await engine.dispose()


async def test_aclose_is_a_no_op():
    engine = get_engine()
    client = _client(engine)
    await client.aclose()
    await engine.dispose()
