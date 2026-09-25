from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from knowledge_model import KnowledgeRecord, KnowledgeStatus, KnowledgeType

EXPECTED_TYPES = {
    "decision",
    "fact",
    "customer_insight",
    "strategy",
    "product_requirement",
    "process",
    "policy",
    "person",
    "ownership",
    "action",
    "hypothesis",
    "conflict",
}

EXPECTED_STATUSES = {
    "active",
    "superseded",
    "conflicting",
    "pending_review",
    "rejected",
}


def test_knowledge_type_values_match_prd():
    assert {t.value for t in KnowledgeType} == EXPECTED_TYPES


def test_knowledge_status_values_match_prd():
    assert {s.value for s in KnowledgeStatus} == EXPECTED_STATUSES


def test_custom_type_strings_are_accepted_by_the_model():
    """T077: `type` was loosened from `KnowledgeType` to `str` so a
    workspace's own custom types (libs/db's `custom_knowledge_types`) can be
    stored - this model no longer rejects an unrecognised type string
    itself; harness-api's /taxonomy/types + edit_knowledge validate against
    built-in ∪ custom instead."""
    record = KnowledgeRecord(
        id="K-00001",
        type="meeting_notes",
        topic="enterprise_sso",
        statement="SSO is becoming a recurring enterprise requirement",
        status="active",
        confidence=0.5,
        source_ids=[],
        people=[],
        created_at=datetime.now(timezone.utc),
        observed_at=datetime.now(timezone.utc),
        last_updated_at=datetime.now(timezone.utc),
    )
    assert record.type == "meeting_notes"


def test_invalid_status_still_raises_validation_error():
    """`status` is unaffected by T077 - still a strict `KnowledgeStatus`."""
    with pytest.raises(ValidationError):
        KnowledgeRecord(
            id="K-00001",
            type="fact",
            topic="enterprise_sso",
            statement="SSO is becoming a recurring enterprise requirement",
            status="not_a_real_status",
            confidence=0.5,
            source_ids=[],
            people=[],
            created_at=datetime.now(timezone.utc),
            observed_at=datetime.now(timezone.utc),
            last_updated_at=datetime.now(timezone.utc),
        )
