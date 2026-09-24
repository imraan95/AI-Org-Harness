from datetime import datetime, timezone

import pytest
from knowledge_model import KnowledgeRecord, KnowledgeStatus, KnowledgeType
from llm_router import FakeLLM
from openviking_client import FakeOpenVikingClient
from shared_schemas import Transcript

from context_agent import process_transcript
from context_agent.pipeline import _classify, _compare, _extract, _retrieve, _write


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


async def test_compare_returns_new_without_calling_llm_when_no_existing_knowledge():
    """T041: nothing to compare against means "new" by definition - no LLM
    call needed (and none made, since OllamaLLM.compare isn't even wired up
    yet - see llm_router/ollama.py)."""
    fake_llm = FakeLLM()
    # Deliberately not setting a canned compare result: if the pipeline
    # called llm.compare() here, this test would still "pass" on the
    # empty-string default, silently masking the bug T041 fixes. The real
    # assertion is that compare_calls stays empty.
    candidate = {"topic": "enterprise_sso", "statement": "..."}

    results = await _compare(fake_llm, [(candidate, [])])

    assert results == [(candidate, [], "new")]
    assert fake_llm.compare_calls == []


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


async def test_write_persists_records_with_correct_statuses_for_impact_level():
    client = FakeOpenVikingClient()
    conflicting_existing = _knowledge_record()
    classified = [
        {
            "topic": "enterprise_sso",
            "statement": "SSO decided for November",
            "existing": [],
            "relationship": "new",
            "type": "decision",
            "confidence": 0.9,
        },
        {
            "topic": "enterprise_sso",
            "statement": "Speculation nobody else has corroborated",
            "existing": [],
            "relationship": "new",
            "type": "hypothesis",
            "confidence": 0.3,
        },
        {
            "topic": "enterprise_sso",
            "statement": "SSO not planned for Q4",
            "existing": [conflicting_existing],
            "relationship": "contradicting",
            "type": "decision",
            "confidence": 0.9,
        },
    ]

    written = await _write(client, classified)

    assert len(written) == 3
    assert written[0].status == KnowledgeStatus.ACTIVE
    assert written[0].conflicts_with == []
    assert written[1].status == KnowledgeStatus.PENDING_REVIEW
    assert written[1].conflicts_with == []
    assert written[2].status == KnowledgeStatus.CONFLICTING
    assert written[2].conflicts_with == [conflicting_existing.id]

    for record in written:
        fetched = await client.get_knowledge_by_id(record.id)
        assert fetched is not None


async def test_full_pipeline_writes_a_knowledge_record_matching_prd_example():
    """PRD §6: "Three enterprise customers have asked for SSO..." end to end
    through Extract -> Retrieve -> Compare -> Classify -> Write."""
    transcript = Transcript(
        id="meeting_sso_2026_09",
        meeting_title="September product meeting",
        attendees=["Sales", "Product"],
        meeting_date=datetime.now(timezone.utc),
        source="test",
        raw_text=(
            "Three enterprise customers have asked for SSO and Sales says "
            "it's becoming a blocker."
        ),
    )

    fake_llm = FakeLLM()
    fake_llm.set_next_extract_result(
        [
            {
                "topic": "enterprise_sso",
                "statement": (
                    "Three enterprise customers have asked for SSO; Sales "
                    "considers it a potential deal blocker."
                ),
            }
        ]
    )
    fake_llm.set_next_classify_result("customer_insight")
    client = FakeOpenVikingClient()

    written = await process_transcript(transcript, fake_llm, client)

    assert len(written) == 1
    record = written[0]
    assert record.topic == "enterprise_sso"
    assert record.type == KnowledgeType.CUSTOMER_INSIGHT

    stored = await client.get_knowledge_by_id(record.id)
    assert stored is not None


async def test_process_transcript_returns_empty_list_when_nothing_extracted():
    fake_llm = FakeLLM()
    fake_llm.set_next_extract_result([])
    client = FakeOpenVikingClient()

    result = await process_transcript(_transcript(), fake_llm, client)

    assert result == []


async def test_full_pipeline_writes_a_conflict_record_when_llm_says_contradicting():
    """T042: a contradiction produces an explicit conflict record - linking
    both knowledge ids via `conflicts_with` - instead of silently
    overwriting or superseding the existing belief."""
    existing_record = _knowledge_record(
        statement="SSO is not planned for this fiscal year"
    )
    client = FakeOpenVikingClient()
    await client.write_knowledge(existing_record)

    fake_llm = FakeLLM()
    fake_llm.set_next_extract_result(
        [{"topic": "enterprise_sso", "statement": "SSO shipped last week"}]
    )
    fake_llm.set_next_compare_result("contradicting")
    fake_llm.set_next_classify_result("decision")

    written = await process_transcript(_transcript(), fake_llm, client)

    assert len(written) == 1
    record = written[0]
    assert record.status == KnowledgeStatus.CONFLICTING
    assert record.conflicts_with == [existing_record.id]

    conflicts = await client.list_conflicts()
    assert [c.id for c in conflicts] == [record.id]


async def test_first_ever_mention_of_a_topic_is_written_with_no_supersedes_link():
    """T041: a brand-new topic (nothing in OpenViking about it yet) should
    be written cleanly as new knowledge, with no `supersedes` link."""
    fake_llm = FakeLLM()
    fake_llm.set_next_extract_result(
        [{"topic": "brand_new_topic", "statement": "Something nobody has said before."}]
    )
    fake_llm.set_next_classify_result("fact")
    client = FakeOpenVikingClient()  # nothing seeded - retrieval will be empty

    written = await process_transcript(_transcript(), fake_llm, client)

    assert len(written) == 1
    assert written[0].supersedes is None
    assert fake_llm.compare_calls == []
