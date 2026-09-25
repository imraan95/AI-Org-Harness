import uuid

from db import (
    create_custom_knowledge_type,
    delete_custom_knowledge_type,
    get_engine,
    get_session_factory,
    list_custom_knowledge_types,
)


async def test_create_list_delete_lifecycle():
    engine = get_engine()
    session_factory = get_session_factory(engine)
    workspace_id = f"test-{uuid.uuid4().hex[:8]}"
    key = "meeting_notes"

    async with session_factory() as session:
        created = await create_custom_knowledge_type(
            session, workspace_id, key, "Meeting Notes"
        )
    assert created is not None
    assert created.key == key
    assert created.label == "Meeting Notes"

    async with session_factory() as session:
        types = await list_custom_knowledge_types(session, workspace_id)
    assert [t.key for t in types] == [key]

    async with session_factory() as session:
        deleted = await delete_custom_knowledge_type(session, workspace_id, key)
    assert deleted is True

    async with session_factory() as session:
        types_after = await list_custom_knowledge_types(session, workspace_id)
    assert types_after == []

    await engine.dispose()


async def test_create_returns_none_on_duplicate_key():
    engine = get_engine()
    session_factory = get_session_factory(engine)
    workspace_id = f"test-{uuid.uuid4().hex[:8]}"

    async with session_factory() as session:
        first = await create_custom_knowledge_type(
            session, workspace_id, "dup_key", "First"
        )
    assert first is not None

    async with session_factory() as session:
        second = await create_custom_knowledge_type(
            session, workspace_id, "dup_key", "Second"
        )
    assert second is None

    async with session_factory() as session:
        await delete_custom_knowledge_type(session, workspace_id, "dup_key")

    await engine.dispose()


async def test_delete_returns_false_for_unknown_key():
    engine = get_engine()
    session_factory = get_session_factory(engine)
    workspace_id = f"test-{uuid.uuid4().hex[:8]}"

    async with session_factory() as session:
        deleted = await delete_custom_knowledge_type(session, workspace_id, "nope")
    assert deleted is False

    await engine.dispose()
