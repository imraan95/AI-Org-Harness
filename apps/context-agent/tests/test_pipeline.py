from datetime import datetime, timezone

import pytest
from knowledge_model import KnowledgeRecord, KnowledgeType
from llm_router import FakeLLM
from openviking_client import FakeOpenVikingClient
from shared_schemas import Transcript

from context_agent import process_transcript
from context_agent.pipeline import _classify, _compare, _extract, _retrieve


def _transcript() -> Transcript:
    return Transcript(
        id="meeting_test",
        meeting_title="Test meeting",
        attendees=["Alice"],
        meeting_date=datetime.now(timezone.utc),
        source="test",
        raw_text="Alice: Three enterprise customers have asked for SSO.",
    )


def _knowledge_record(**overrides) -> KnowledgeRecord:
    kwargs = dict(
        id="K-00001",
        type="customer_insight",
        topic="enterprise_sso",
        statement="SSO is an occasional customer request",
        status="active",
        confidence=0.5,
        source_ids=["meeting_earlier"],
        people=[],
        created_at=datetime.now(timezone.utc),
        observed_at=datetime.now(timezone.utc),
        last_updated_at=datetime.now(timezone.utc),
    )
    kwargs.update(overrides)
    return KnowledgeRecord(**kwargs)


async def test_extract_calls_llm_with_transcript_text_and_returns_candidates():
    fake_llm = FakeLLM()
    fake_llm.set_next_extract_result(
        [{"topic": "enterprise_sso", "statement": "SSO is being requested"}]
    )
    transcript = _transcript()

    candidates = await _extract(fake_llm, transcript)

    assert fake_llm.extract_calls == [transcript.raw_text]
    assert candidates == [
        {"topic": "enterprise_sso", "statement": "SSO is being requested"}
    ]


async def test_retrieve_returns_existing_knowledge_for_matching_topic():
    client = FakeOpenVikingClient()
    existing_record = _knowledge_record()
    await client.write_knowledge(existing_record)

    candidates = [{"topic": "enterprise_sso", "statement": "..."}]

    results = await _retrieve(client, candidates)

    assert len(results) == 1
    candidate, existing = results[0]
    assert candidate == candidates[0]
    assert len(existing) == 1
    assert existing[0].id == existing_record.id


async def test_compare_returns_new_when_llm_says_new():
    fake_llm = FakeLLM()
    fake_llm.set_next_compare_result("new")
    candidate = {"topic": "enterprise_sso", "statement": "..."}

    results = await _compare(fake_llm, [(candidate, [])])

    assert results == [(candidate, [], "new")]


async def test_compare_returns_corroborating_when_llm_says_corroborating():
    fake_llm = FakeLLM()
    fake_llm.set_next_compare_result("corroborating")
    existing = [_knowledge_record()]
    candidate = {"topic": "enterprise_sso", "statement": "..."}

    results = await _compare(fake_llm, [(candidate, existing)])

    assert results[0][2] == "corroborating"


async def test_compare_returns_superseding_when_llm_says_superseding():
    fake_llm = FakeLLM()
    fake_llm.set_next_compare_result("superseding")
    existing = [_knowledge_record()]
    candidate = {"topic": "enterprise_sso", "statement": "..."}

    results = await _compare(fake_llm, [(candidate, existing)])

    assert results[0][2] == "superseding"


async def test_compare_returns_contradicting_when_llm_says_contradicting():
    fake_llm = FakeLLM()
    fake_llm.set_next_compare_result("contradicting")
    existing = [_knowledge_record()]
    candidate = {"topic": "enterprise_sso", "statement": "..."}

    results = await _compare(fake_llm, [(candidate, existing)])

    assert results[0][2] == "contradicting"


async def test_classify_assigns_type_via_llm_and_confidence_via_rules():
    fake_llm = FakeLLM()
    fake_llm.set_next_classify_result("customer_insight")
    candidate = {
        "topic": "enterprise_sso",
        "statement": "SSO is being requested",
        "source_context": "customer_statement",
    }
    compared = [(candidate, [], "new")]

    classified = await _classify(fake_llm, compared)

    assert len(classified) == 1
    result = classified[0]
    assert result["type"] == "customer_insight"
    assert result["confidence"] == pytest.approx(0.6)
    assert result["relationship"] == "new"
    assert fake_llm.classify_calls == [
        ("SSO is being requested", [t.value for t in KnowledgeType])
    ]


async def test_process_transcript_still_returns_without_raising():
    fake_llm = FakeLLM()
    fake_llm.set_next_extract_result([])
    client = FakeOpenVikingClient()

    result = await process_transcript(_transcript(), fake_llm, client)

    assert result is None
