from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class KnowledgeRecord(BaseModel):
    """A single unit of organisational knowledge (PRD §7)."""

    id: str
    type: str
    topic: str
    statement: str
    status: str
    confidence: float
    source_ids: list[str]
    people: list[str]
    created_at: datetime
    observed_at: datetime
    last_updated_at: datetime
    supersedes: str | None = None
