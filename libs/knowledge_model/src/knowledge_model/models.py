from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from .enums import KnowledgeStatus, KnowledgeType


class KnowledgeRecord(BaseModel):
    """A single unit of organisational knowledge (PRD §7)."""

    id: str
    type: KnowledgeType
    topic: str
    statement: str
    status: KnowledgeStatus
    confidence: float
    source_ids: list[str]
    people: list[str]
    created_at: datetime
    observed_at: datetime
    last_updated_at: datetime
    supersedes: str | None = None
