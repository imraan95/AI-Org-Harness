from datetime import datetime, timezone

from knowledge_model import KnowledgeRecord

from openviking_client import FakeOpenVikingClient


def _record(**overrides) -> KnowledgeRecord:
    kwargs = dict(
        id="K-00001",
        type="customer_insight",
        topic="enterprise_sso",
        statement="SSO is becoming a recurring enterprise requirement",
        status="active",
        confidence=0.82,
        source_ids=["meeting_123"],
        people=["person_12"],
        created_at=datetime.now(timezone.utc),
        observed_at=datetime.now(timezone.utc),
        last_updated_at=datetime.now(timezone.utc),
    )
    kwargs.update(overrides)
    return KnowledgeRecord(**kwargs)


async def test_write_then_get_by_id():
    client = FakeOpenVikingClient()
    record = _record()

    await client.write_knowledge(record)
    fetched = await client.get_knowledge_by_id(record.id)

    assert fetched is not None
    assert fetched.id == record.id


async def test_get_relevant_knowledge_matches_by_topic():
    client = FakeOpenVikingClient()
    record = _record()
    await client.write_knowledge(record)

    results = await client.get_relevant_knowledge("enterprise_sso")

    assert len(results) == 1
    assert results[0].id == record.id
