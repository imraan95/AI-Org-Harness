from __future__ import annotations

from datetime import datetime

from knowledge_model import KnowledgeRecord, KnowledgeStatus, KnowledgeType

from .interface import OpenVikingClient


class FakeOpenVikingClient(OpenVikingClient):
    """In-memory stand-in for OpenViking.

    Used before the real forked service exists (build-plan Phase 6), and in
    every test elsewhere so tests never depend on a running OpenViking.
    """

    def __init__(self) -> None:
        self._records: list[KnowledgeRecord] = []

    async def write_knowledge(self, record: KnowledgeRecord) -> None:
        self._records.append(record)

    async def get_knowledge_by_id(self, knowledge_id: str) -> KnowledgeRecord | None:
        for record in self._records:
            if record.id == knowledge_id:
                return record
        return None

    async def get_relevant_knowledge(self, topic: str) -> list[KnowledgeRecord]:
        return [r for r in self._records if topic.lower() in r.topic.lower()]

    async def list_conflicts(self) -> list[KnowledgeRecord]:
        return [r for r in self._records if r.status == KnowledgeStatus.CONFLICTING]

    async def list_by_type(self, knowledge_type: KnowledgeType) -> list[KnowledgeRecord]:
        return [r for r in self._records if r.type == knowledge_type]

    async def list_all(self) -> list[KnowledgeRecord]:
        return list(self._records)

    async def update_knowledge_status(
        self, knowledge_id: str, status: KnowledgeStatus
    ) -> None:
        for i, record in enumerate(self._records):
            if record.id == knowledge_id:
                self._records[i] = record.model_copy(update={"status": status})
                return

    async def update_knowledge_fields(
        self, knowledge_id: str, updates: dict, edited_by: str
    ) -> None:
        for i, record in enumerate(self._records):
            if record.id == knowledge_id:
                self._records[i] = record.model_copy(
                    update={**updates, "edited_by": edited_by}
                )
                return

    async def mark_superseded(self, knowledge_id: str, superseded_at: datetime) -> None:
        for i, record in enumerate(self._records):
            if record.id == knowledge_id:
                self._records[i] = record.model_copy(
                    update={
                        "status": KnowledgeStatus.SUPERSEDED,
                        "superseded_at": superseded_at,
                    }
                )
                return
