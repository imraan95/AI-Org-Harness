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


def test_permissions_scaffold_fields_have_mvp_defaults():
    """PRD §18: every record carries these even though MVP doesn't enforce
    them yet (T039)."""
    record = KnowledgeRecord(**_valid_kwargs())
    assert record.workspace_id == "default"
    assert record.source_id == "unspecified"
    assert record.visibility == "internal"
    assert record.owner is None
    assert record.access_level == "standard"


def test_permissions_scaffold_fields_can_be_overridden():
    record = KnowledgeRecord(
        **_valid_kwargs(
            workspace_id="acme",
            source_id="anarlog",
            visibility="confidential",
            owner="person_12",
            access_level="restricted",
        )
    )
    assert record.workspace_id == "acme"
    assert record.source_id == "anarlog"
    assert record.visibility == "confidential"
    assert record.owner == "person_12"
    assert record.access_level == "restricted"
