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

    # Permissions scaffold (PRD §18): "one trusted workspace, no complex
    # RBAC" for MVP, but every record carries these so a real permissions
    # model can be added later without a rewrite. Not enforced anywhere
    # yet - see build-plan T039 and ADR 0003 (OpenViking has no schema of
    # its own to patch; this scaffold lives entirely in our own model).
    workspace_id: str = "default"
    source_id: str = "unspecified"
    visibility: str = "internal"
    owner: str | None = None
    access_level: str = "standard"
