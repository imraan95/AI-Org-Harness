import uuid
from datetime import datetime, timezone

from knowledge_model import KnowledgeRecord, KnowledgeStatus, KnowledgeType

from db import (
    delete_knowledge_record,
    get_engine,
    get_knowledge_record_by_id,
    get_knowledge_records_by_topic,
    get_session_factory,
    list_all_knowledge_records,
    list_conflicting_knowledge_records,
    list_knowledge_records_by_type,
    mark_knowledge_record_superseded,
    update_knowledge_record_fields,
    update_knowledge_record_status,
    upsert_knowledge_record,
)


def _record(**overrides) -> KnowledgeRecord:
    now = datetime.now(timezone.utc)
    kwargs = dict(
        id=f"K-test-{uuid.uuid4()}",
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


async def test_write_then_get_by_id():
    engine = get_engine()
    session_factory = get_session_factory(engine)
    record = _record()

    async with session_factory() as session:
        await upsert_knowledge_record(session, record)

    async with session_factory() as session:
        fetched = await get_knowledge_record_by_id(session, record.id)

    assert fetched is not None
    assert fetched.id == record.id
    assert fetched.statement == record.statement
    assert fetched.source_ids == record.source_ids

    async with session_factory() as session:
        await delete_knowledge_record(session, record.id)
    await engine.dispose()


async def test_get_by_topic_is_an_exact_match_not_substring():
    engine = get_engine()
    session_factory = get_session_factory(engine)
    topic = f"enterprise_sso_{uuid.uuid4().hex[:8]}"
    record = _record(topic=topic)

    async with session_factory() as session:
        await upsert_knowledge_record(session, record)

    async with session_factory() as session:
        exact = await get_knowledge_records_by_topic(session, topic)
        prefix_only = await get_knowledge_records_by_topic(session, topic[:5])

    assert [r.id for r in exact] == [record.id]
    assert prefix_only == []

    async with session_factory() as session:
        await delete_knowledge_record(session, record.id)
    await engine.dispose()


async def test_list_by_type_matches_only_that_type():
    engine = get_engine()
    session_factory = get_session_factory(engine)
    decision = _record(type="decision")
    person = _record(type="person")

    async with session_factory() as session:
        await upsert_knowledge_record(session, decision)
        await upsert_knowledge_record(session, person)

    async with session_factory() as session:
        results = await list_knowledge_records_by_type(session, KnowledgeType.DECISION)

    assert decision.id in {r.id for r in results}
    assert person.id not in {r.id for r in results}

    async with session_factory() as session:
        await delete_knowledge_record(session, decision.id)
        await delete_knowledge_record(session, person.id)
    await engine.dispose()


async def test_list_conflicting_returns_only_conflicting_status():
    engine = get_engine()
    session_factory = get_session_factory(engine)
    conflicting = _record(status="conflicting")
    active = _record(status="active")

    async with session_factory() as session:
        await upsert_knowledge_record(session, conflicting)
        await upsert_knowledge_record(session, active)

    async with session_factory() as session:
        results = await list_conflicting_knowledge_records(session)

    assert conflicting.id in {r.id for r in results}
    assert active.id not in {r.id for r in results}

    async with session_factory() as session:
        await delete_knowledge_record(session, conflicting.id)
        await delete_knowledge_record(session, active.id)
    await engine.dispose()


async def test_update_fields_persists_and_sets_edited_by():
    engine = get_engine()
    session_factory = get_session_factory(engine)
    record = _record(statement="Original statement.")

    async with session_factory() as session:
        await upsert_knowledge_record(session, record)
        await update_knowledge_record_fields(
            session, record.id, {"statement": "Edited statement."}, edited_by="alice@rms.test"
        )

    async with session_factory() as session:
        refetched = await get_knowledge_record_by_id(session, record.id)

    assert refetched is not None
    assert refetched.statement == "Edited statement."
    assert refetched.edited_by == "alice@rms.test"

    async with session_factory() as session:
        await delete_knowledge_record(session, record.id)
    await engine.dispose()


async def test_update_status_changes_status():
    engine = get_engine()
    session_factory = get_session_factory(engine)
    record = _record(status="pending_review")

    async with session_factory() as session:
        await upsert_knowledge_record(session, record)
        await update_knowledge_record_status(session, record.id, KnowledgeStatus.ACTIVE)

    async with session_factory() as session:
        refetched = await get_knowledge_record_by_id(session, record.id)

    assert refetched is not None
    assert refetched.status.value == "active"

    async with session_factory() as session:
        await delete_knowledge_record(session, record.id)
    await engine.dispose()


async def test_mark_superseded_sets_status_and_timestamp():
    engine = get_engine()
    session_factory = get_session_factory(engine)
    record = _record()

    async with session_factory() as session:
        await upsert_knowledge_record(session, record)
        when = datetime.now(timezone.utc)
        await mark_knowledge_record_superseded(session, record.id, when)

    async with session_factory() as session:
        refetched = await get_knowledge_record_by_id(session, record.id)

    assert refetched is not None
    assert refetched.status.value == "superseded"
    assert refetched.superseded_at == when

    async with session_factory() as session:
        await delete_knowledge_record(session, record.id)
    await engine.dispose()


async def test_upsert_replaces_an_existing_record_with_the_same_id():
    engine = get_engine()
    session_factory = get_session_factory(engine)
    record = _record(statement="First version.")

    async with session_factory() as session:
        await upsert_knowledge_record(session, record)

    replaced = record.model_copy(update={"statement": "Second version."})
    async with session_factory() as session:
        await upsert_knowledge_record(session, replaced)

    async with session_factory() as session:
        refetched = await get_knowledge_record_by_id(session, record.id)

    assert refetched is not None
    assert refetched.statement == "Second version."

    async with session_factory() as session:
        await delete_knowledge_record(session, record.id)
    await engine.dispose()


async def test_list_all_returns_every_written_record():
    engine = get_engine()
    session_factory = get_session_factory(engine)
    a = _record()
    b = _record()

    async with session_factory() as session:
        await upsert_knowledge_record(session, a)
        await upsert_knowledge_record(session, b)

    async with session_factory() as session:
        results = await list_all_knowledge_records(session)

    ids = {r.id for r in results}
    assert a.id in ids
    assert b.id in ids

    async with session_factory() as session:
        await delete_knowledge_record(session, a.id)
        await delete_knowledge_record(session, b.id)
    await engine.dispose()
