from __future__ import annotations

from abc import ABC, abstractmethod

from knowledge_model import KnowledgeRecord, KnowledgeStatus, KnowledgeType


class OpenVikingClient(ABC):
    """Contract for talking to the OpenViking service (PRD §12, architecture.md §4).

    Every other service reads and writes knowledge exclusively through an
    implementation of this interface - never directly against OpenViking's
    own storage.
    """

    @abstractmethod
    async def get_relevant_knowledge(self, topic: str) -> list[KnowledgeRecord]: ...

    @abstractmethod
    async def write_knowledge(self, record: KnowledgeRecord) -> None: ...

    @abstractmethod
    async def get_knowledge_by_id(
        self, knowledge_id: str
    ) -> KnowledgeRecord | None: ...

    @abstractmethod
    async def list_conflicts(self) -> list[KnowledgeRecord]: ...

    @abstractmethod
    async def list_by_type(self, knowledge_type: KnowledgeType) -> list[KnowledgeRecord]: ...

    @abstractmethod
    async def update_knowledge_status(
        self, knowledge_id: str, status: KnowledgeStatus
    ) -> None: ...
