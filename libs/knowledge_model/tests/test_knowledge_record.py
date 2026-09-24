from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from knowledge_model import KnowledgeRecord


def _valid_kwargs(**overrides):
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
    return kwargs


def test_valid_knowledge_record_constructs_and_exposes_fields():
    record = KnowledgeRecord(**_valid_kwargs())
    assert record.id == "K-00001"
    assert record.topic == "enterprise_sso"
    assert record.confidence == 0.82
    assert record.supersedes is None


def test_missing_required_field_raises_validation_error():
    kwargs = _valid_kwargs()
    del kwargs["topic"]
    with pytest.raises(ValidationError):
        KnowledgeRecord(**kwargs)
