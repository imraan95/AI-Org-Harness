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
    # T066: set on the OLD record when a newer one supersedes it (paired
    # with that new record's own `supersedes` pointing back). None until
    # a record is actually superseded.
    superseded_at: datetime | None = None

    # PRD §9/§17, build-plan T042: when Compare finds a candidate
    # contradicts existing knowledge, it's written with
    # status=CONFLICTING and this field populated with the id(s) of every
    # existing record it contradicts - never silently overwritten or
    # auto-resolved. Empty for every other status.
    conflicts_with: list[str] = []

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

    # PRD §17/§20, build-plan T057: set when a human edits a proposed
    # record's fields before/instead of a plain approve/reject. None until
    # the first edit.
    edited_by: str | None = None
