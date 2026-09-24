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


def test_invalid_type_raises_validation_error():
    with pytest.raises(ValidationError):
        KnowledgeRecord(
            id="K-00001",
            type="not_a_real_type",
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
